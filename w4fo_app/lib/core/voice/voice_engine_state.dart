import '../../application/state/voice_chat_state.dart';

/// Macro-état du moteur vocal de W4FO.
///
/// Ce type formalise, au niveau architecture, les 6 états demandés pour
/// préparer l'assistant vocal avancé (Wake Word + écoute passive à venir) :
///
/// ```
///           ┌──────────────────────────────────────────────┐
///           │                                                │
///           ▼                                                │
///  ┌──────────────┐   wake word détecté   ┌───────────────┐  │
///  │     IDLE      │ ────────────────────▶ │   LISTENING   │  │
///  │ (rien ne se   │ ◀──────────────────── │ (écoute       │  │
///  │  passe)       │   timeout / annulé    │  passive,     │  │
///  └──────┬────────┘                       │  100% locale) │  │
///         │                                └───────┬───────┘  │
///         │ appui manuel micro                      │ wake word confirmé
///         ▼                                         ▼
///  ┌──────────────────┐                    ┌──────────────────┐
///  │ RECORDING_COMMAND │◀───────────────────│ RECORDING_COMMAND │
///  │ (capture + envoi  │                    │ (idem, déclenché  │
///  │  au WebSocket)    │                    │  par wake word)   │
///  └─────────┬─────────┘                    └───────────────────┘
///            │ end_of_speech
///            ▼
///     ┌──────────────┐
///     │  PROCESSING   │  (STT distant, agents LangGraph, TTS en préparation)
///     └──────┬────────┘
///            ▼
///     ┌──────────────┐
///     │   SPEAKING    │  (lecture de la réponse audio, interruption possible)
///     └──────┬────────┘
///            │ end_of_turn / interrupt
///            ▼
///          IDLE
///
///        (à tout moment) ──erreur──▶ ERROR ──reset──▶ IDLE
/// ```
///
/// Important (contrainte produit) : le passage `IDLE → LISTENING` correspond
/// à une écoute **passive et locale** (détection de mot-clé), qui ne doit
/// JAMAIS transmettre de flux audio continu à Mistral ou à tout autre
/// service distant. Seul le passage `LISTENING → RECORDING_COMMAND` (ou
/// l'appui manuel direct `IDLE → RECORDING_COMMAND`, comportement actuel de
/// l'app) doit ouvrir un flux réseau.
///
/// Ce fichier ne modifie AUCUN comportement existant : il fournit une lecture
/// architecturale supplémentaire au-dessus de [VoiceChatPhase], qui reste la
/// source de vérité utilisée par le provider et l'UI aujourd'hui.
enum VoiceEngineState {
  /// Rien ne se passe. Aucun accès micro, aucune connexion active nécessaire.
  idle,

  /// Écoute passive en attente d'un mot-clé de réveil ("Wake Word").
  /// Traitement 100% local (pas de streaming réseau). Non utilisé tant que
  /// le Wake Word Always-On n'est pas implémenté (voir [WakeWordDetector]).
  listening,

  /// Capture active de la commande de l'utilisateur : le micro est ouvert et
  /// les chunks audio sont transmis au WebSocket vocal backend. Correspond
  /// au comportement actuel déclenché par l'appui sur le bouton micro.
  recordingCommand,

  /// La commande a été envoyée : transcription (STT), raisonnement agent, et
  /// préparation de la réponse (TTS) sont en cours côté backend.
  processing,

  /// Lecture de la réponse audio (TTS) en cours. Une interruption (barge-in)
  /// est possible à tout moment dans cet état.
  speaking,

  /// Une erreur est survenue (permission refusée, connexion perdue, etc.).
  error,
}

/// Traduit l'état détaillé actuel de l'UI ([VoiceChatPhase]) vers le
/// macro-état architectural ([VoiceEngineState]).
///
/// Cette extension est purement une projection en lecture : elle ne remplace
/// pas [VoiceChatPhase], qui garde plus de granularité utile à l'UI
/// (`transcribing` vs `thinking`, `awaitingConfirmation`...). Elle sert de
/// point d'ancrage stable pour tout code futur (Wake Word, écoute passive)
/// qui doit raisonner en termes des 6 macro-états, sans se soucier des
/// sous-phases internes.
extension VoiceChatPhaseEngineMapping on VoiceChatPhase {
  VoiceEngineState toEngineState() {
    switch (this) {
      case VoiceChatPhase.idle:
        return VoiceEngineState.idle;
      case VoiceChatPhase.listening:
        // Comportement actuel : "listening" désigne la capture active de la
        // commande (micro ouvert + envoi au WebSocket), pas une écoute
        // passive. Elle correspond donc à recordingCommand au sens de la
        // nouvelle architecture. Le futur état "écoute passive locale"
        // utilisera VoiceEngineState.listening directement, sans jamais
        // passer par VoiceChatPhase.listening.
        return VoiceEngineState.recordingCommand;
      case VoiceChatPhase.transcribing:
      case VoiceChatPhase.thinking:
      case VoiceChatPhase.awaitingConfirmation:
        return VoiceEngineState.processing;
      case VoiceChatPhase.speaking:
        return VoiceEngineState.speaking;
      case VoiceChatPhase.error:
        return VoiceEngineState.error;
    }
  }
}
