import 'package:flutter/foundation.dart';

/// Les 9 états explicites du pipeline vocal Wake Word demandés par
/// l'architecture Always-On. Remplace toute déduction implicite de l'état :
/// chaque transition passe par [VoiceStateMachine.fire], qui valide qu'elle
/// est légale depuis l'état courant.
enum VoiceMachineState {
  /// Rien ne se passe. Aucun accès micro (ni passif, ni actif).
  idle,

  /// Écoute passive locale du mot-clé "Wafo" (aucun envoi réseau).
  listeningForWakeWord,

  /// Transition instantanée : le mot-clé vient d'être reconnu localement.
  wakeWordDetected,

  /// Capture active de la commande utilisateur (micro → WebSocket).
  listeningCommand,

  /// Transcription + raisonnement de l'agent en cours côté backend.
  processing,

  /// L'agent est en train d'exécuter un ou plusieurs outils (tâches, agenda,
  /// navigation...). Voir limitation documentée dans le rapport de livraison :
  /// cet état est actuellement déclenché de façon rétrospective (résumé des
  /// outils déjà exécutés), pas en flux temps réel outil par outil.
  executingAction,

  /// Lecture de la réponse audio (TTS), texte affiché progressivement en
  /// synchronisation avec l'audio. Interruption (barge-in) possible.
  responding,

  /// Une erreur est survenue (permission refusée, connexion perdue, etc.).
  error,

  /// Le pipeline vocal est arrêté explicitement (Wake Word désactivé, écran
  /// fermé, service arrière-plan stoppé). Distinct de [idle] : [idle] signifie
  /// "prêt, en attente d'une activation", [stopped] signifie "désactivé,
  /// nécessite une réactivation explicite (ex. rouvrir l'écran vocal)".
  stopped,
}

/// Événements qui font transitionner la machine d'état vocale.
enum VoiceMachineEvent {
  /// Démarre le pipeline (active l'écoute du mot-clé, ou reste idle si le
  /// Wake Word n'est pas activé pour cette session).
  start,
  wakeWordDetected,
  beginCommandCapture,
  endCommandCapture,
  toolsExecuting,
  toolsCompleted,
  responseReady,
  turnComplete,
  interrupted,
  timeout,
  errorOccurred,
  reset,
  stop,
}

/// Machine d'état explicite du pipeline vocal (§ ÉTATS du brief).
///
/// Toutes les transitions sont déclarées dans [_transitions] : une paire
/// (état courant, événement) non déclarée est REJETÉE (ignorée, jamais une
/// exception qui ferait planter l'app — les races réseau/audio produisent
/// occasionnellement des événements "hors séquence", ex. un `end_of_turn`
/// qui arrive après une interruption locale déjà traitée).
///
/// Usage : `VoiceChatNotifier` est seul propriétaire d'une instance de cette
/// classe et route CHAQUE changement d'état à travers [fire], plutôt que de
/// manipuler `VoiceChatState.phase` directement — voir
/// `application/providers/voice_chat_provider.dart`.
class VoiceStateMachine {
  VoiceMachineState _state;

  VoiceStateMachine({VoiceMachineState initial = VoiceMachineState.idle}) : _state = initial;

  VoiceMachineState get state => _state;

  static const Map<VoiceMachineState, Map<VoiceMachineEvent, VoiceMachineState>> _transitions = {
    VoiceMachineState.idle: {
      VoiceMachineEvent.start: VoiceMachineState.listeningForWakeWord,
      VoiceMachineEvent.beginCommandCapture: VoiceMachineState.listeningCommand,
      VoiceMachineEvent.errorOccurred: VoiceMachineState.error,
      VoiceMachineEvent.stop: VoiceMachineState.stopped,
    },
    VoiceMachineState.listeningForWakeWord: {
      VoiceMachineEvent.wakeWordDetected: VoiceMachineState.wakeWordDetected,
      VoiceMachineEvent.beginCommandCapture: VoiceMachineState.listeningCommand,
      VoiceMachineEvent.errorOccurred: VoiceMachineState.error,
      VoiceMachineEvent.stop: VoiceMachineState.stopped,
    },
    VoiceMachineState.wakeWordDetected: {
      VoiceMachineEvent.beginCommandCapture: VoiceMachineState.listeningCommand,
      VoiceMachineEvent.errorOccurred: VoiceMachineState.error,
      VoiceMachineEvent.stop: VoiceMachineState.stopped,
    },
    VoiceMachineState.listeningCommand: {
      VoiceMachineEvent.endCommandCapture: VoiceMachineState.processing,
      VoiceMachineEvent.interrupted: VoiceMachineState.idle,
      VoiceMachineEvent.timeout: VoiceMachineState.idle,
      VoiceMachineEvent.errorOccurred: VoiceMachineState.error,
      VoiceMachineEvent.stop: VoiceMachineState.stopped,
    },
    VoiceMachineState.processing: {
      VoiceMachineEvent.toolsExecuting: VoiceMachineState.executingAction,
      VoiceMachineEvent.responseReady: VoiceMachineState.responding,
      VoiceMachineEvent.interrupted: VoiceMachineState.idle,
      VoiceMachineEvent.errorOccurred: VoiceMachineState.error,
      VoiceMachineEvent.stop: VoiceMachineState.stopped,
    },
    VoiceMachineState.executingAction: {
      VoiceMachineEvent.toolsCompleted: VoiceMachineState.processing,
      VoiceMachineEvent.responseReady: VoiceMachineState.responding,
      VoiceMachineEvent.interrupted: VoiceMachineState.idle,
      VoiceMachineEvent.errorOccurred: VoiceMachineState.error,
      VoiceMachineEvent.stop: VoiceMachineState.stopped,
    },
    VoiceMachineState.responding: {
      VoiceMachineEvent.turnComplete: VoiceMachineState.idle,
      VoiceMachineEvent.interrupted: VoiceMachineState.idle,
      VoiceMachineEvent.errorOccurred: VoiceMachineState.error,
      VoiceMachineEvent.stop: VoiceMachineState.stopped,
    },
    VoiceMachineState.error: {
      VoiceMachineEvent.reset: VoiceMachineState.idle,
      VoiceMachineEvent.stop: VoiceMachineState.stopped,
    },
    VoiceMachineState.stopped: {
      VoiceMachineEvent.start: VoiceMachineState.listeningForWakeWord,
      VoiceMachineEvent.reset: VoiceMachineState.idle,
    },
  };

  /// Tente d'appliquer [event] à l'état courant. Retourne le nouvel état si la
  /// transition est légale, ou `null` si elle est rejetée (état inchangé,
  /// message de debug tracé — jamais une exception).
  VoiceMachineState? fire(VoiceMachineEvent event) {
    final nextState = _transitions[_state]?[event];
    if (nextState == null) {
      if (kDebugMode) {
        debugPrint('VoiceStateMachine: transition rejetée ($_state, $event)');
      }
      return null;
    }
    _state = nextState;
    return nextState;
  }

  /// Comme [fire], mais force l'état cible même si la transition n'était pas
  /// déclarée — réservé aux cas de reprise après erreur non prévue par la
  /// table (ex. dispose() en urgence). À utiliser avec parcimonie.
  void forceState(VoiceMachineState newState) {
    if (kDebugMode && _transitions[_state]?.values.contains(newState) != true) {
      debugPrint('VoiceStateMachine: forceState hors table ($_state -> $newState)');
    }
    _state = newState;
  }
}
