import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../../core/di/injection.dart';
import '../../core/network/websocket_client.dart';
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
class VoiceChatNotifier extends StateNotifier<VoiceChatState> {
  final Ref _ref;
  final VoiceWebSocketClient _wsClient = VoiceWebSocketClient();
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();

  final BytesBuilder _incomingAudioBuffer = BytesBuilder();
  StreamSubscription<Uint8List>? _micSubscription;

  VoiceChatNotifier(this._ref) : super(const VoiceChatState());

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

      case AudioChunkEvent(data: final data):
        state = state.copyWith(phase: VoiceChatPhase.speaking);
        _incomingAudioBuffer.add(data);

      case EndOfTurnEvent():
        _playBufferedAudio();
        state = state.copyWith(phase: VoiceChatPhase.idle, clearPendingToolCall: false);
    }
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
  Future<void> startListening() async {
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
  }

  @override
  void dispose() {
    _micSubscription?.cancel();
    _recorder.dispose();
    _player.dispose();
    _wsClient.disconnect();
    super.dispose();
  }
}

final voiceChatProvider = StateNotifierProvider.autoDispose<VoiceChatNotifier, VoiceChatState>(
  (ref) => VoiceChatNotifier(ref),
);
