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

  const VoiceChatState({
    this.phase = VoiceChatPhase.idle,
    this.messages = const [],
    this.liveTranscript,
    this.pendingToolCall,
    this.errorMessage,
  });

  VoiceChatState copyWith({
    VoiceChatPhase? phase,
    List<ConversationMessage>? messages,
    String? liveTranscript,
    Map<String, dynamic>? pendingToolCall,
    String? errorMessage,
    bool clearLiveTranscript = false,
    bool clearPendingToolCall = false,
  }) {
    return VoiceChatState(
      phase: phase ?? this.phase,
      messages: messages ?? this.messages,
      liveTranscript: clearLiveTranscript ? null : (liveTranscript ?? this.liveTranscript),
      pendingToolCall: clearPendingToolCall ? null : (pendingToolCall ?? this.pendingToolCall),
      errorMessage: errorMessage,
    );
  }
}
