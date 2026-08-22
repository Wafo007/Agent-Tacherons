import '../../core/voice/voice_engine_state.dart';
import '../../core/voice/voice_state_machine.dart';
import '../../domain/entities/conversation_message.dart';

/// Phase de la boucle vocale, pilote l'UI (icône micro, animation, texte d'état).
///
/// Reste la source de vérité consommée par les écrans (granularité pratique
/// pour l'UI : distingue `transcribing` de `thinking`, etc.). Dérivée, à
/// CHAQUE changement, de [VoiceMachineState] via [VoiceStateMachine] — voir
/// `VoiceChatNotifier._phaseFor` — plutôt que fixée indépendamment : c'est la
/// machine d'état explicite qui décide des transitions légales, cette énum
/// n'est qu'une projection d'affichage.
enum VoiceChatPhase {
  idle, // Micro inactif, en attente d'une action utilisateur
  listening, // Capture audio en cours
  transcribing, // En attente/réception de la transcription
  thinking, // L'orchestrateur d'agents traite la demande
  executingAction, // L'agent exécute des outils (résumé rétrospectif, voir rapport)
  speaking, // Lecture de la réponse audio (TTS) en cours, texte progressif
  awaitingConfirmation, // Une action sensible attend confirmation utilisateur
  error,
  stopped,
}

class VoiceChatState {
  final VoiceChatPhase phase;

  /// État canonique de la machine d'état explicite (§ ÉTATS du brief) —
  /// source de vérité derrière [phase]. Exposé pour les tests/le débogage ;
  /// l'UI continue de lire [phase], plus granulaire pour l'affichage.
  final VoiceMachineState machineState;

  final List<ConversationMessage> messages;
  final String? liveTranscript; // Transcription affichée en direct avant confirmation finale
  final Map<String, dynamic>? pendingToolCall;
  final String? errorMessage;

  /// Texte de la réponse en cours de génération, révélé mot par mot en
  /// synchronisation avec l'audio (§ TEXTE PROGRESSIF) — jamais affiché d'un
  /// bloc. `null` tant qu'aucune réponse n'est en cours de lecture. Une fois
  /// le tour terminé, ce texte est finalisé dans [messages] et remis à `null`.
  final String? streamingResponseText;

  /// Liste des outils exécutés par l'agent durant le tour en cours (résumé
  /// rétrospectif reçu via `tool_calls_summary`), pour affichage optionnel
  /// pendant l'état `executingAction`.
  final List<Map<String, dynamic>> lastExecutedTools;

  /// Vrai lorsque l'écoute passive locale du Wake Word ("Wafo") est
  /// actuellement active (voir `core/voice/wafo_wake_word_detector.dart`).
  final bool wakeWordActive;

  const VoiceChatState({
    this.phase = VoiceChatPhase.idle,
    this.machineState = VoiceMachineState.idle,
    this.messages = const [],
    this.liveTranscript,
    this.pendingToolCall,
    this.errorMessage,
    this.streamingResponseText,
    this.lastExecutedTools = const [],
    this.wakeWordActive = false,
  });

  /// Macro-état architectural (IDLE / LISTENING / RECORDING_COMMAND /
  /// PROCESSING / SPEAKING / ERROR), dérivé de [phase]. Voir
  /// `core/voice/voice_engine_state.dart`.
  VoiceEngineState get engineState => phase.toEngineState();

  VoiceChatState copyWith({
    VoiceChatPhase? phase,
    VoiceMachineState? machineState,
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
    return VoiceChatState(
      phase: phase ?? this.phase,
      machineState: machineState ?? this.machineState,
      messages: messages ?? this.messages,
      liveTranscript: clearLiveTranscript ? null : (liveTranscript ?? this.liveTranscript),
      pendingToolCall: clearPendingToolCall ? null : (pendingToolCall ?? this.pendingToolCall),
      errorMessage: errorMessage,
      streamingResponseText:
          clearStreamingResponseText ? null : (streamingResponseText ?? this.streamingResponseText),
      lastExecutedTools: lastExecutedTools ?? this.lastExecutedTools,
      wakeWordActive: wakeWordActive ?? this.wakeWordActive,
    );
  }
}
