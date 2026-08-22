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
import '../../core/voice/voice_state_machine.dart';
import '../../core/voice/wake_word_detector.dart';
import '../../domain/entities/conversation_message.dart';
import '../state/voice_chat_state.dart';
import 'whatsapp_provider.dart';

/// Un mot annoncé par le serveur (`response_word`), en attente d'être révélé
/// à l'écran au bon moment (relatif au DÉBUT de la lecture audio, pas à sa
/// réception réseau — voir § TEXTE PROGRESSIF dans `voice_ws.py`).
class _TimedWord {
  final String text;
  final int offsetMs;
  const _TimedWord(this.text, this.offsetMs);
}

/// Délai maximal, côté client, d'attente d'une réponse serveur (transcript,
/// timeout, etc.) après `end_of_speech` — filet de sécurité si la connexion
/// est perdue silencieusement (le serveur applique sa propre limite de 15s,
/// voir `COMMAND_TIMEOUT_SECONDS` dans `voice_ws.py`, mais si le réseau est
/// coupé le client ne recevra jamais cet événement serveur).
const _clientSafetyTimeout = Duration(seconds: 20);

/// Orchestre le cycle complet de la conversation vocale côté client, en miroir
/// exact du protocole défini côté backend (`voice_ws.py`).
///
/// Toute transition d'état passe par [VoiceStateMachine] (`_machine`) — voir
/// `core/voice/voice_state_machine.dart` pour la table de transitions
/// complète et les 9 états explicites demandés par l'architecture Always-On.
///
/// § TEXTE PROGRESSIF : le texte de la réponse n'est JAMAIS affiché d'un
/// bloc. Chaque mot (`ResponseWordEvent`) est mis en file d'attente
/// ([_pendingWords]) puis révélé par un `Timer` programmé au moment exact où
/// l'audio le prononce, à partir du DÉBUT réel de la lecture (voir
/// [_playBufferedAudio]) — jamais au moment de la réception réseau du mot
/// (sujette à la gigue), et jamais tout d'un coup à `end_of_turn`.
///
/// Cette classe est volontairement le seul endroit de l'app qui touche à la
/// fois `record` (capture micro) et `just_audio` (lecture) : les écrans ne
/// manipulent que `VoiceChatState`, jamais les plugins audio directement.
class VoiceChatNotifier extends StateNotifier<VoiceChatState> {
  final Ref _ref;
  final VoiceWebSocketClient _wsClient = VoiceWebSocketClient();
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  final VoiceStateMachine _machine = VoiceStateMachine();

  final BytesBuilder _incomingAudioBuffer = BytesBuilder();
  StreamSubscription<Uint8List>? _micSubscription;

  final List<_TimedWord> _pendingWords = [];
  final List<String> _revealedWords = [];
  final List<Timer> _wordRevealTimers = [];
  Timer? _finalizeTimer;
  String? _pendingFinalText;

  Timer? _clientSafetyTimer;

  WakeWordDetector _wakeWordDetector = NoOpWakeWordDetector();
  StreamSubscription<void>? _wakeWordSubscription;
  bool _wakeWordEnabled = false;

  bool _disposed = false;

  VoiceChatNotifier(this._ref) : super(const VoiceChatState());

  // ---------------------------------------------------------------------
  // Wake Word (écoute passive)
  // ---------------------------------------------------------------------

  /// Branche un détecteur de mot-clé de réveil et démarre l'écoute passive
  /// locale (LISTENING_FOR_WAKE_WORD).
  Future<void> enableWakeWord(WakeWordDetector detector) async {
    await _wakeWordSubscription?.cancel();
    await _wakeWordDetector.dispose();

    _wakeWordDetector = detector;
    _wakeWordEnabled = true;
    _wakeWordSubscription = detector.onWakeWordDetected.listen((_) {
      if (_machine.state == VoiceMachineState.listeningForWakeWord ||
          _machine.state == VoiceMachineState.idle) {
        _machine.fire(VoiceMachineEvent.wakeWordDetected);
        startListening();
      }
    });

    if (_machine.state == VoiceMachineState.idle) {
      _machine.fire(VoiceMachineEvent.start);
      await _wakeWordDetector.start();
      _setState(phase: VoiceChatPhase.idle, wakeWordActive: true);
    }
  }

  Future<void> disableWakeWord() async {
    _wakeWordEnabled = false;
    await _wakeWordSubscription?.cancel();
    _wakeWordSubscription = null;
    await _wakeWordDetector.stop();
    await _wakeWordDetector.dispose();
    _wakeWordDetector = NoOpWakeWordDetector();
    _machine.fire(VoiceMachineEvent.stop);
    _setState(phase: VoiceChatPhase.stopped, wakeWordActive: false);
  }

  Future<void> pauseWakeWordForBackground() async {
    await _wakeWordDetector.stop();
    _setState(wakeWordActive: false);
  }

  Future<void> resumeWakeWordFromBackground() async {
    if (_wakeWordEnabled && _machine.state == VoiceMachineState.idle) {
      _machine.fire(VoiceMachineEvent.start);
      await _wakeWordDetector.start();
      _setState(phase: VoiceChatPhase.idle, wakeWordActive: true);
    }
  }

  void _resumeWakeWordIfEnabled() {
    if (!_wakeWordEnabled) return;
    _machine.fire(VoiceMachineEvent.start);
    unawaited(_wakeWordDetector.start());
    _setState(wakeWordActive: true);
  }

  // ---------------------------------------------------------------------
  // Connexion
  // ---------------------------------------------------------------------

  Future<void> connect() async {
    final accessToken = await _ref.read(authRepositoryProvider).getAccessToken();
    if (accessToken == null) {
      _fireError('Non authentifié.');
      return;
    }

    try {
      await _wsClient.connect(accessToken: accessToken);
    } catch (_) {
      _fireError('Impossible de se connecter au service vocal.');
      return;
    }

    _wsClient.events.listen(
      _handleServerEvent,
      onError: (_) => _fireError('Connexion vocale perdue.'),
    );
  }

  /// Permet de retenter une connexion après une erreur réseau (§ INTERRUPTION :
  /// perte réseau). Réinitialise la machine à `idle` avant de reconnecter.
  Future<void> retryConnection() async {
    _machine.fire(VoiceMachineEvent.reset);
    _setState(phase: VoiceChatPhase.idle, errorMessage: null);
    await connect();
  }

  void _fireError(String message) {
    _cancelAllTimersAndAudio();
    _machine.fire(VoiceMachineEvent.errorOccurred);
    _setState(phase: VoiceChatPhase.error, errorMessage: message);
  }

  // ---------------------------------------------------------------------
  // Événements serveur
  // ---------------------------------------------------------------------

  void _handleServerEvent(VoiceServerEvent event) {
    switch (event) {
      case TranscriptEvent(text: final text):
        if (text.isEmpty) {
          _machine.fire(VoiceMachineEvent.interrupted);
          _setState(phase: VoiceChatPhase.idle, clearLiveTranscript: true);
          _resumeWakeWordIfEnabled();
          return;
        }
        final userMessage = ConversationMessage(role: MessageRole.user, content: text);
        _setState(messages: [...state.messages, userMessage], clearLiveTranscript: true);

      case AgentThinkingEvent():
        _setState(phase: VoiceChatPhase.thinking);

      case ToolCallsSummaryEvent(tools: final tools):
        // § EXECUTING_ACTION — voir limitation documentée dans le rapport de
        // livraison : cet événement est rétrospectif (les outils ont déjà
        // fini de s'exécuter côté serveur au moment où il arrive), pas un
        // flux temps réel outil par outil.
        _machine.fire(VoiceMachineEvent.toolsExecuting);
        _setState(phase: VoiceChatPhase.executingAction, lastExecutedTools: tools);

      case ResponseWordEvent(text: final text, offsetMs: final offsetMs):
        if (_pendingWords.isEmpty) {
          _machine.fire(VoiceMachineEvent.responseReady);
          _setState(phase: VoiceChatPhase.speaking, clearStreamingResponseText: true);
        }
        _pendingWords.add(_TimedWord(text, offsetMs));

      case ResponseTextFinalEvent(text: final text):
        // Réconciliation uniquement (voir doc de classe) : ne touche PAS
        // l'affichage progressif en cours, seulement le texte qui sera
        // enregistré dans l'historique une fois la lecture terminée.
        _pendingFinalText = text;

      case RequiresConfirmationEvent(toolCall: final toolCall):
        _setState(phase: VoiceChatPhase.awaitingConfirmation, pendingToolCall: toolCall);

      case ClientActionEvent(action: final action, payload: final payload):
        _handleClientAction(action, payload);

      case CommandTimeoutEvent():
        // Le serveur a abandonné l'attente d'un `end_of_speech` (§ INTERRUPTION :
        // timeout). Le micro côté client était probablement resté ouvert sans
        // que l'utilisateur ne parle : on nettoie et on revient à l'écoute passive.
        unawaited(_abortCommandCapture());
        _machine.fire(VoiceMachineEvent.timeout);
        _setState(phase: VoiceChatPhase.idle, clearLiveTranscript: true);
        _resumeWakeWordIfEnabled();

      case InterruptedEvent():
        // Confirmation serveur qu'un `interrupt` a bien annulé le traitement
        // ou la lecture en cours (barge-in réel, pas seulement local).
        _cancelAllTimersAndAudio();
        _machine.fire(VoiceMachineEvent.interrupted);
        _setState(phase: VoiceChatPhase.idle, clearStreamingResponseText: true);
        _resumeWakeWordIfEnabled();

      case AudioChunkEvent(data: final data):
        _incomingAudioBuffer.add(data);

      case EndOfTurnEvent():
        _playBufferedAudio();
    }
  }

  void _handleClientAction(String action, Map<String, dynamic> payload) {
    if (action == 'WHATSAPP_REPLY') {
      // § WHATSAPP : ce n'est pas une navigation — délègue à WhatsAppNotifier,
      // qui appelle le natif (RemoteInput sur la notification WhatsApp en
      // attente) et met à jour sa propre conversation locale (§ CONTEXTE :
      // jamais mélangée à `state.messages`, la conversation Flutter/voix).
      final text = payload['text'] as String?;
      if (text != null && text.isNotEmpty) {
        unawaited(_ref.read(whatsAppProvider.notifier).sendReply(text));
      }
      return;
    }

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

  // ---------------------------------------------------------------------
  // Lecture audio + révélation progressive du texte (§ TEXTE PROGRESSIF)
  // ---------------------------------------------------------------------

  /// Écrit l'audio accumulé dans un fichier temporaire, démarre la lecture,
  /// puis programme la révélation de chaque mot annoncé (`_pendingWords`) au
  /// moment EXACT où l'audio le prononce, à partir de l'instant réel où la
  /// lecture démarre — pas à la réception réseau du mot.
  Future<void> _playBufferedAudio() async {
    final audioBytes = _incomingAudioBuffer.takeBytes();
    final words = List<_TimedWord>.from(_pendingWords);
    _pendingWords.clear();

    if (audioBytes.isEmpty) {
      // Réponse sans audio (cas limite, ex. TTS indisponible) : on finalise
      // directement avec le texte complet plutôt que de rester bloqué.
      _finalizeTurn();
      return;
    }

    final tempDir = await getTemporaryDirectory();
    final file = File('${tempDir.path}/w4fo_response_${DateTime.now().millisecondsSinceEpoch}.mp3');
    await file.writeAsBytes(audioBytes);

    if (_disposed) return;

    await _player.setFilePath(file.path);
    unawaited(_player.play());

    for (final timer in _wordRevealTimers) {
      timer.cancel();
    }
    _wordRevealTimers.clear();
    _revealedWords.clear();

    for (final word in words) {
      final timer = Timer(Duration(milliseconds: word.offsetMs), () {
        if (_disposed) return;
        _revealedWords.add(word.text);
        _setState(streamingResponseText: _revealedWords.join(' '));
      });
      _wordRevealTimers.add(timer);
    }

    // Finalise le tour un court instant après le dernier mot prévu (laisse
    // le temps à l'audio de terminer sa dernière syllabe) — voir doc de
    // classe : c'est cette temporisation qui garantit que le texte reste
    // affiché progressivement jusqu'à la fin réelle de la lecture, plutôt
    // que de basculer d'un coup dès `end_of_turn` (qui arrive bien avant la
    // fin de la lecture audio).
    final lastOffset = words.isEmpty ? 0 : words.last.offsetMs;
    _finalizeTimer?.cancel();
    _finalizeTimer = Timer(Duration(milliseconds: lastOffset + 600), _finalizeTurn);
  }

  void _finalizeTurn() {
    if (_disposed) return;
    final finalText = _pendingFinalText ?? (_revealedWords.isEmpty ? null : _revealedWords.join(' '));
    _pendingFinalText = null;

    if (finalText != null && finalText.isNotEmpty) {
      final assistantMessage = ConversationMessage(role: MessageRole.assistant, content: finalText);
      _setState(messages: [...state.messages, assistantMessage], clearStreamingResponseText: true);
    } else {
      _setState(clearStreamingResponseText: true);
    }

    if (_machine.state == VoiceMachineState.responding) {
      _machine.fire(VoiceMachineEvent.turnComplete);
    } else {
      // Réponse sans aucun mot annoncé (ex. texte vide / TTS indisponible) :
      // on n'est jamais passé par `responding` (aucun ResponseWordEvent
      // reçu), donc `turnComplete` serait rejeté. `interrupted` est une
      // transition valide depuis `processing`/`executingAction` vers `idle`,
      // et couvre correctement ce cas limite sans bloquer la machine.
      _machine.fire(VoiceMachineEvent.interrupted);
    }
    _setState(phase: VoiceChatPhase.idle, clearPendingToolCall: false);
    _resumeWakeWordIfEnabled();
  }

  void _cancelAllTimersAndAudio() {
    for (final timer in _wordRevealTimers) {
      timer.cancel();
    }
    _wordRevealTimers.clear();
    _finalizeTimer?.cancel();
    _finalizeTimer = null;
    _pendingWords.clear();
    _revealedWords.clear();
    _pendingFinalText = null;
    _incomingAudioBuffer.clear();
    unawaited(_player.stop());
  }

  // ---------------------------------------------------------------------
  // Capture de commande
  // ---------------------------------------------------------------------

  /// Démarre la capture micro et transmet les chunks audio en direct au serveur.
  ///
  /// § INTERRUPTION (perte microphone) : toute erreur du flux d'enregistrement
  /// (permission révoquée en cours de session, périphérique audio perdu...)
  /// bascule proprement en état d'erreur plutôt que de laisser une capture
  /// fantôme ouverte.
  Future<void> startListening() async {
    if (_wakeWordEnabled) {
      await _wakeWordDetector.stop();
      _setState(wakeWordActive: false);
    }

    if (!await _recorder.hasPermission()) {
      _fireError('Permission microphone refusée.');
      return;
    }

    _machine.fire(VoiceMachineEvent.beginCommandCapture);
    _setState(phase: VoiceChatPhase.listening, clearLiveTranscript: true);

    _clientSafetyTimer?.cancel();
    _clientSafetyTimer = Timer(_clientSafetyTimeout, () {
      // Filet de sécurité : ni transcript, ni command_timeout, ni erreur du
      // serveur reçus après un délai large — connexion probablement perdue
      // silencieusement (§ INTERRUPTION : perte réseau).
      unawaited(_abortCommandCapture());
      _fireError('Aucune réponse du serveur vocal (connexion perdue ?).');
    });

    try {
      final stream = await _recorder.startStream(
        const RecordConfig(encoder: AudioEncoder.pcm16bits, sampleRate: 16000, numChannels: 1),
      );
      _micSubscription = stream.listen(
        (chunk) => _wsClient.sendAudioChunk(chunk),
        onError: (_) {
          unawaited(_abortCommandCapture());
          _fireError('Le microphone est devenu indisponible pendant la capture.');
        },
      );
    } catch (_) {
      _clientSafetyTimer?.cancel();
      _fireError("Impossible d'accéder au microphone.");
    }
  }

  /// Arrête la capture micro et signale la fin du segment de parole au serveur.
  Future<void> stopListening() async {
    _clientSafetyTimer?.cancel();
    await _recorder.stop();
    await _micSubscription?.cancel();
    // § CONTEXTE (WhatsApp) : si un message WhatsApp est en attente de
    // réponse, on l'attache à CE tour uniquement (voir
    // `WhatsAppNotifier.consumePendingContextForNextCommand` — contexte
    // transitoire, jamais mélangé à l'historique de conversation Flutter).
    final whatsappContext = _ref.read(whatsAppProvider.notifier).consumePendingContextForNextCommand();
    _wsClient.sendEndOfSpeech(whatsappContext: whatsappContext);
    _machine.fire(VoiceMachineEvent.endCommandCapture);
    _setState(phase: VoiceChatPhase.transcribing);
  }

  /// Nettoyage local (sans notifier le serveur, déjà fait pour nous côté
  /// serveur ou plus nécessaire) d'une capture de commande en cours —
  /// utilisé par le timeout serveur et le filet de sécurité client.
  Future<void> _abortCommandCapture() async {
    _clientSafetyTimer?.cancel();
    await _recorder.stop();
    await _micSubscription?.cancel();
  }

  /// Barge-in local : l'utilisateur interrompt la réponse en cours de lecture,
  /// ou annule une capture/un traitement en cours. Envoie `interrupt` au
  /// serveur (qui l'applique aussi bien pendant le raisonnement agent que
  /// pendant le streaming TTS — voir `voice_ws.py`), et nettoie l'état local
  /// immédiatement sans attendre la confirmation serveur (UX réactive).
  Future<void> interrupt() async {
    _cancelAllTimersAndAudio();
    await _micSubscription?.cancel();
    await _recorder.stop();
    _wsClient.sendInterrupt();
    _machine.fire(VoiceMachineEvent.interrupted);
    _setState(phase: VoiceChatPhase.idle, clearStreamingResponseText: true);
    _resumeWakeWordIfEnabled();
  }

  /// § INTERRUPTION (application suspendue) : à appeler depuis le cycle de
  /// vie de l'écran (`AppLifecycleState.paused`/`inactive`) quand une
  /// capture, un traitement ou une lecture est en cours — évite de laisser
  /// le micro ouvert ou une session fantôme pendant que l'app n'est plus au
  /// premier plan. Si le pipeline est simplement en écoute passive du mot-clé,
  /// utiliser [pauseWakeWordForBackground] à la place (comportement inchangé).
  Future<void> handleAppSuspended() async {
    switch (_machine.state) {
      case VoiceMachineState.listeningCommand:
      case VoiceMachineState.processing:
      case VoiceMachineState.executingAction:
      case VoiceMachineState.responding:
        await interrupt();
      case VoiceMachineState.idle:
      case VoiceMachineState.listeningForWakeWord:
      case VoiceMachineState.wakeWordDetected:
      case VoiceMachineState.error:
      case VoiceMachineState.stopped:
        break;
    }
    await pauseWakeWordForBackground();
  }

  // ---------------------------------------------------------------------

  void _setState({
    VoiceChatPhase? phase,
    List<ConversationMessage>? messages,
    String? liveTranscript,
    Map<String, dynamic>? pendingToolCall,
    String? errorMessage,
    String? streamingResponseText,
    List<Map<String, dynamic>>? lastExecutedTools,
    bool clearLiveTranscript = false,
    bool clearPendingToolCall = false,
    bool clearStreamingResponseText = false,
    bool? wakeWordActive,
  }) {
    if (_disposed) return;
    state = state.copyWith(
      phase: phase,
      machineState: _machine.state,
      messages: messages,
      liveTranscript: liveTranscript,
      pendingToolCall: pendingToolCall,
      errorMessage: errorMessage,
      streamingResponseText: streamingResponseText,
      lastExecutedTools: lastExecutedTools,
      clearLiveTranscript: clearLiveTranscript,
      clearPendingToolCall: clearPendingToolCall,
      clearStreamingResponseText: clearStreamingResponseText,
      wakeWordActive: wakeWordActive,
    );
  }

  @override
  void dispose() {
    _disposed = true;
    _clientSafetyTimer?.cancel();
    for (final timer in _wordRevealTimers) {
      timer.cancel();
    }
    _finalizeTimer?.cancel();
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
