import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import 'package:flutter/foundation.dart';

import '../../core/di/injection.dart';
import '../../core/network/websocket_client.dart';
import '../../core/router/app_router.dart';
import '../../core/voice/wake_word_detector.dart';
import '../../domain/entities/conversation_message.dart';
import '../state/voice_chat_state.dart';

/// Orchestre le cycle complet de la conversation vocale côté client, en miroir
/// exact du protocole défini côté backend (`voice_ws.py`, §10.1/§10.2 du
/// document d'architecture) :
///
///   micro → chunks audio → WebSocket → [transcript, agent_thinking,
///   response_text, audio chunks, end_of_turn] → lecture audio
///
/// Cette classe est volontairement le seul endroit de l'app qui touche à la
/// fois `record` (capture micro) et `just_audio` (lecture) : les écrans ne
/// manipulent que `VoiceChatState`, jamais les plugins audio directement.
///
/// Wake Word (voir `core/voice/wake_word_detector.dart` et
/// `core/voice/wafo_wake_word_detector.dart`) : ce notifier orchestre le
/// cycle complet demandé —
///
///   IDLE → LISTENING_FOR_WAKE_WORD → WAKE_WORD_DETECTED →
///   LISTENING_COMMAND → PROCESSING → RESPONSE → LISTENING_FOR_WAKE_WORD
///
/// — via [enableWakeWord]/[disableWakeWord] (activation/désactivation
/// complète) et [pauseWakeWordForBackground]/[resumeWakeWordFromBackground]
/// (mise en pause légère, ex. lifecycle app). Le détecteur ne partage
/// jamais le micro avec la capture de commande : [startListening] met
/// systématiquement l'écoute passive en pause le temps de la commande, et
/// elle est reprise automatiquement au retour à `idle` (voir
/// [_resumeWakeWordIfEnabled]). Tant qu'aucun détecteur concret n'est
/// branché, le comportement reste celui d'avant (déclenchement manuel via
/// le bouton micro uniquement) : [_wakeWordDetector] vaut
/// [NoOpWakeWordDetector] par défaut, qui ne détecte jamais rien et n'ouvre
/// aucun accès micro ni réseau.
class VoiceChatNotifier extends StateNotifier<VoiceChatState> {
  final Ref _ref;
  final VoiceWebSocketClient _wsClient = VoiceWebSocketClient();
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  final BytesBuilder _incomingAudioBuffer = BytesBuilder();
  StreamSubscription<Uint8List>? _micSubscription;

  WakeWordDetector _wakeWordDetector = NoOpWakeWordDetector();
  StreamSubscription<void>? _wakeWordSubscription;

  /// Vrai si l'utilisateur/l'app a activé le Wake Word (via
  /// [enableWakeWord]), indépendamment du fait que l'écoute passive soit
  /// momentanément en pause (ex. pendant une commande, ou app en arrière-plan).
  bool _wakeWordEnabled = false;

  VoiceChatNotifier(this._ref) : super(const VoiceChatState());

  /// Branche un détecteur de mot-clé de réveil et démarre l'écoute passive
  /// locale (LISTENING_FOR_WAKE_WORD). Dès que le détecteur signale une
  /// détection (WAKE_WORD_DETECTED), la capture de commande réelle démarre
  /// automatiquement via le pipeline existant ([startListening]).
  ///
  /// Par construction (voir [WakeWordDetector]), le détecteur ne doit
  /// jamais transmettre de flux audio continu au réseau : il se contente
  /// d'émettre un signal local.
  Future<void> enableWakeWord(WakeWordDetector detector) async {
    await _wakeWordSubscription?.cancel();
    await _wakeWordDetector.dispose();

    _wakeWordDetector = detector;
    _wakeWordEnabled = true;
    _wakeWordSubscription = detector.onWakeWordDetected.listen((_) {
      if (state.phase == VoiceChatPhase.idle) {
        startListening();
      }
    });

    if (state.phase == VoiceChatPhase.idle) {
      await _wakeWordDetector.start();
      state = state.copyWith(wakeWordActive: true);
    }
  }

  /// Débranche le détecteur de mot-clé actif et revient à un détecteur
  /// neutre (aucune écoute passive, IDLE au sens du pipeline Wake Word).
  Future<void> disableWakeWord() async {
    _wakeWordEnabled = false;
    await _wakeWordSubscription?.cancel();
    _wakeWordSubscription = null;
    await _wakeWordDetector.stop();
    await _wakeWordDetector.dispose();
    _wakeWordDetector = NoOpWakeWordDetector();
    state = state.copyWith(wakeWordActive: false);
  }

  /// Met l'écoute passive du Wake Word en pause sans la désactiver
  /// (contrairement à [disableWakeWord], le détecteur n'est pas jeté). À
  /// utiliser quand l'app passe en arrière-plan : les restrictions Android
  /// modernes limitent de toute façon l'accès micro hors premier plan, donc
  /// on libère proactivement la ressource plutôt que de laisser une session
  /// STT tourner inutilement.
  Future<void> pauseWakeWordForBackground() async {
    await _wakeWordDetector.stop();
    state = state.copyWith(wakeWordActive: false);
  }

  /// Reprend l'écoute passive du Wake Word après une pause (ex. retour au
  /// premier plan), uniquement si elle avait été activée et que l'app est
  /// bien en attente (idle) — jamais pendant une commande en cours.
  Future<void> resumeWakeWordFromBackground() async {
    if (_wakeWordEnabled && state.phase == VoiceChatPhase.idle) {
      await _wakeWordDetector.start();
      state = state.copyWith(wakeWordActive: true);
    }
  }

  /// Reprend automatiquement l'écoute passive du Wake Word dès que l'on
  /// revient à `idle` après une commande (PROCESSING/RESPONSE terminés),
  /// bouclant ainsi le cycle LISTENING_COMMAND → PROCESSING → RESPONSE →
  /// LISTENING_FOR_WAKE_WORD. N'a aucun effet si le Wake Word n'a pas été
  /// activé.
  void _resumeWakeWordIfEnabled() {
    if (!_wakeWordEnabled) return;
    unawaited(_wakeWordDetector.start());
    state = state.copyWith(wakeWordActive: true);
  }

  /// Établit la connexion WebSocket vocale. À appeler une fois à l'ouverture de l'écran.
  Future<void> connect() async {
    final accessToken = await _ref.read(authRepositoryProvider).getAccessToken();
    if (accessToken == null) {
      state = state.copyWith(phase: VoiceChatPhase.error, errorMessage: 'Non authentifié.');
      return;
    }

    await _wsClient.connect(accessToken: accessToken);
    _wsClient.events.listen(_handleServerEvent, onError: (_) {
      state = state.copyWith(phase: VoiceChatPhase.error, errorMessage: 'Connexion vocale perdue.');
    });
  }

  void _handleServerEvent(VoiceServerEvent event) {
    switch (event) {
      case TranscriptEvent(text: final text):
        if (text.isEmpty) {
          state = state.copyWith(phase: VoiceChatPhase.idle, clearLiveTranscript: true);
          _resumeWakeWordIfEnabled();
          return;
        }
        final userMessage = ConversationMessage(role: MessageRole.user, content: text);
        state = state.copyWith(
          messages: [...state.messages, userMessage],
          clearLiveTranscript: true,
        );

      case AgentThinkingEvent():
        state = state.copyWith(phase: VoiceChatPhase.thinking);

      case ResponseTextEvent(text: final text):
        final assistantMessage = ConversationMessage(role: MessageRole.assistant, content: text);
        state = state.copyWith(messages: [...state.messages, assistantMessage]);

      case RequiresConfirmationEvent(toolCall: final toolCall):
        state = state.copyWith(phase: VoiceChatPhase.awaitingConfirmation, pendingToolCall: toolCall);

      case ClientActionEvent(action: final action, payload: final payload):
        _handleClientAction(action, payload);

      case AudioChunkEvent(data: final data):
        state = state.copyWith(phase: VoiceChatPhase.speaking);
        _incomingAudioBuffer.add(data);

      case EndOfTurnEvent():
        _playBufferedAudio();
        state = state.copyWith(phase: VoiceChatPhase.idle, clearPendingToolCall: false);
        _resumeWakeWordIfEnabled();
    }
  }

  /// Exécute une action applicative déclenchée par l'agent (§ ACTION GATEWAY
  /// côté backend, voir `infrastructure/actions/action_registry.py`).
  ///
  /// Sécurité : seuls les codes explicitement listés ci-dessous déclenchent
  /// une navigation réelle, vers une route EXISTANTE et FIXE de l'app
  /// (`AppRoutes`). Aucune route dynamique n'est construite à partir d'une
  /// chaîne fournie par le serveur — tout code inconnu est silencieusement
  /// ignoré (pas d'exécution "au mieux", pas de fallback permissif).
  void _handleClientAction(String action, Map<String, dynamic> payload) {
    final route = switch (action) {
      'OPEN_HOME' => AppRoutes.home,
      'OPEN_TASKS' => AppRoutes.tasks,
      'OPEN_CALENDAR' => AppRoutes.calendar,
      'OPEN_SETTINGS' => AppRoutes.settings,
      _ => null,
    };

    if (route == null) {
      if (kDebugMode) {
        debugPrint('VoiceChatNotifier: action applicative inconnue ignorée : $action');
      }
      return;
    }

    _ref.read(routerProvider).go(route);
  }

  /// Écrit l'audio accumulé (MP3, streamé chunk par chunk par edge-tts côté
  /// backend) dans un fichier temporaire, puis le joue via just_audio.
  ///
  /// Limitation assumée (cohérente avec le backend, voir §10.2) : la lecture
  /// démarre seulement une fois TOUS les chunks reçus, pas au fil de l'eau —
  /// le backend lui-même n'envoie la réponse qu'une fois le texte complet
  /// généré (pas de découpage phrase par phrase pour l'instant).
  Future<void> _playBufferedAudio() async {
    final audioBytes = _incomingAudioBuffer.takeBytes();
    if (audioBytes.isEmpty) return;

    final tempDir = await getTemporaryDirectory();
    final file = File('${tempDir.path}/w4fo_response_${DateTime.now().millisecondsSinceEpoch}.mp3');
    await file.writeAsBytes(audioBytes);

    await _player.setFilePath(file.path);
    await _player.play();
  }

  /// Démarre la capture micro et transmet les chunks audio en direct au serveur.
  ///
  /// Déclenché soit manuellement (bouton micro), soit automatiquement par
  /// [enableWakeWord] après détection de "Wafo" (WAKE_WORD_DETECTED →
  /// LISTENING_COMMAND). Dans les deux cas, l'écoute passive du Wake Word
  /// est mise en pause en premier : le micro ne doit jamais être partagé
  /// entre les deux usages simultanément.
  Future<void> startListening() async {
    if (_wakeWordEnabled) {
      await _wakeWordDetector.stop();
      state = state.copyWith(wakeWordActive: false);
    }

    if (!await _recorder.hasPermission()) {
      state = state.copyWith(phase: VoiceChatPhase.error, errorMessage: 'Permission micro refusée.');
      return;
    }

    state = state.copyWith(phase: VoiceChatPhase.listening, clearLiveTranscript: true);

    final stream = await _recorder.startStream(
      const RecordConfig(encoder: AudioEncoder.pcm16bits, sampleRate: 16000, numChannels: 1),
    );

    _micSubscription = stream.listen((chunk) => _wsClient.sendAudioChunk(chunk));
  }

  /// Arrête la capture micro et signale la fin du segment de parole au serveur.
  Future<void> stopListening() async {
    await _recorder.stop();
    await _micSubscription?.cancel();
    _wsClient.sendEndOfSpeech();
    state = state.copyWith(phase: VoiceChatPhase.transcribing);
  }

  /// Barge-in : l'utilisateur interrompt la réponse en cours de lecture.
  Future<void> interrupt() async {
    await _player.stop();
    _wsClient.sendInterrupt();
    state = state.copyWith(phase: VoiceChatPhase.idle);
    _resumeWakeWordIfEnabled();
  }

  @override
  void dispose() {
    _micSubscription?.cancel();
    _wakeWordSubscription?.cancel();
    _wakeWordDetector.dispose();
    _recorder.dispose();
    _player.dispose();
    _wsClient.disconnect();
    super.dispose();
  }
}

final voiceChatProvider = StateNotifierProvider.autoDispose<VoiceChatNotifier, VoiceChatState>(
  (ref) => VoiceChatNotifier(ref),
);
