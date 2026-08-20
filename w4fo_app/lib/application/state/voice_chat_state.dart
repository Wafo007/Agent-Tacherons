import '../../core/voice/voice_engine_state.dart';
import '../../domain/entities/conversation_message.dart';

/// Phase de la boucle vocale, pilote l'UI (icône micro, animation, texte d'état).
enum VoiceChatPhase {
  idle, // Micro inactif, en attente d'une action utilisateur
  listening, // Capture audio en cours
  transcribing, // En attente/réception de la transcription
  thinking, // L'orchestrateur d'agents traite la demande
  speaking, // Lecture de la réponse audio (TTS) en cours
  awaitingConfirmation, // Une action sensible attend confirmation utilisateur
  error,
}

class VoiceChatState {
  final VoiceChatPhase phase;
  final List<ConversationMessage> messages;
  final String? liveTranscript; // Transcription affichée en direct avant confirmation finale
  final Map<String, dynamic>? pendingToolCall;
  final String? errorMessage;

  /// Vrai lorsque l'écoute passive locale du Wake Word ("Wafo") est
  /// actuellement active (voir `core/voice/wafo_wake_word_detector.dart`).
  /// Mis à jour par `VoiceChatNotifier` : à `true` pendant les phases
  /// d'attente (idle) si le Wake Word a été activé, à `false` dès qu'une
  /// commande réelle est en cours de capture/traitement/lecture (le micro
  /// est alors dédié à la commande, pas à l'écoute passive).
  final bool wakeWordActive;

  const VoiceChatState({
    this.phase = VoiceChatPhase.idle,
    this.messages = const [],
    this.liveTranscript,
    this.pendingToolCall,
    this.errorMessage,
    this.wakeWordActive = false,
  });

  /// Macro-état architectural (IDLE / LISTENING / RECORDING_COMMAND /
  /// PROCESSING / SPEAKING / ERROR), dérivé de [phase]. Voir
  /// `core/voice/voice_engine_state.dart` pour la définition complète et le
  /// schéma des transitions. Simple projection en lecture, ne remplace pas
  /// [phase] qui reste la source de vérité utilisée par l'UI existante.
  VoiceEngineState get engineState => phase.toEngineState();

  VoiceChatState copyWith({
    VoiceChatPhase? phase,
    List<ConversationMessage>? messages,
    String? liveTranscript,
    Map<String, dynamic>? pendingToolCall,
    String? errorMessage,
    bool clearLiveTranscript = false,
    bool clearPendingToolCall = false,
    bool? wakeWordActive,
  }) {
    return VoiceChatState(
      phase: phase ?? this.phase,
      messages: messages ?? this.messages,
      liveTranscript: clearLiveTranscript ? null : (liveTranscript ?? this.liveTranscript),
      pendingToolCall: clearPendingToolCall ? null : (pendingToolCall ?? this.pendingToolCall),
      errorMessage: errorMessage,
      wakeWordActive: wakeWordActive ?? this.wakeWordActive,
    );
  }
}
