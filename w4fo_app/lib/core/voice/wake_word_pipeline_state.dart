import 'voice_engine_state.dart';

/// Cycle complet du pipeline Wake Word, tel que demandé pour W4FO :
///
/// ```
/// IDLE
///   ↓
/// LISTENING_FOR_WAKE_WORD   (écoute passive locale de "Wafo")
///   ↓
/// WAKE_WORD_DETECTED        (mot-clé reconnu, transition instantanée)
///   ↓
/// LISTENING_COMMAND         (capture de la commande utilisateur)
///   ↓
/// PROCESSING                (STT distant, orchestrateur d'agents, TTS)
///   ↓
/// RESPONSE                  (lecture de la réponse vocale)
///   ↓
/// LISTENING_FOR_WAKE_WORD   (retour à l'écoute passive)
/// ```
///
/// Ce type est une vue supplémentaire, dédiée à l'observabilité du cycle
/// Wake Word (UI future : badge "En écoute du mot-clé", pastille "Wafo
/// détecté !", etc.). Il ne remplace pas [VoiceEngineState] ni
/// `VoiceChatPhase`, qui restent les sources de vérité utilisées par le
/// provider et l'UI existante : il en est une projection.
enum WakeWordPipelineState {
  idle,
  listeningForWakeWord,
  wakeWordDetected,
  listeningCommand,
  processing,
  response,
}

/// Calcule le [WakeWordPipelineState] courant à partir du macro-état du
/// moteur vocal ([VoiceEngineState]) et du fait que l'écoute passive du
/// mot-clé soit active ou non (`wakeWordActive`, exposé par
/// `VoiceChatState.wakeWordActive`).
///
/// `justDetected` permet de représenter la transition instantanée
/// `WAKE_WORD_DETECTED` (émise brièvement par `VoiceChatNotifier` au moment
/// où le mot-clé vient d'être reconnu, avant que la capture de commande ne
/// démarre réellement) ; en dehors de cet instant, elle vaut `false`.
WakeWordPipelineState resolveWakeWordPipelineState({
  required VoiceEngineState engineState,
  required bool wakeWordActive,
  bool justDetected = false,
}) {
  if (justDetected) return WakeWordPipelineState.wakeWordDetected;

  switch (engineState) {
    case VoiceEngineState.idle:
      return wakeWordActive ? WakeWordPipelineState.listeningForWakeWord : WakeWordPipelineState.idle;
    case VoiceEngineState.listening:
      return WakeWordPipelineState.listeningForWakeWord;
    case VoiceEngineState.recordingCommand:
      return WakeWordPipelineState.listeningCommand;
    case VoiceEngineState.processing:
      return WakeWordPipelineState.processing;
    case VoiceEngineState.speaking:
      return WakeWordPipelineState.response;
    case VoiceEngineState.error:
      // Une erreur interrompt le cycle ; on la représente comme un retour à
      // idle du point de vue du pipeline Wake Word (la gestion fine de
      // l'erreur reste portée par VoiceChatPhase.error / errorMessage).
      return WakeWordPipelineState.idle;
  }
}
