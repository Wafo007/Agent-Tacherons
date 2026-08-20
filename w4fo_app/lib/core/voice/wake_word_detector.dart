import 'dart:async';

/// Contrat pour un futur détecteur de mot-clé de réveil ("Wake Word",
/// ex. "Dis W4FO").
///
/// ⚠️ Ce fichier définit uniquement une interface et une implémentation
/// neutre ([NoOpWakeWordDetector]). Aucune détection réelle n'est
/// implémentée ici : l'Always-On Android complet (service au premier plan,
/// écoute permanente en arrière-plan, etc.) sera traité dans un chantier
/// dédié ultérieur.
///
/// Contraintes de conception à respecter par toute implémentation future :
///
/// 1. La détection doit être **entièrement locale** (on-device). Elle ne
///    doit jamais transmettre de flux audio continu à un service distant
///    (ni Mistral, ni le WebSocket vocal backend). Seul le déclenchement
///    ponctuel (`onWakeWordDetected`) doit ensuite ouvrir une capture réelle
///    via le pipeline existant (`VoiceChatNotifier.startListening`).
/// 2. Le détecteur doit pouvoir démarrer/s'arrêter indépendamment du reste
///    du pipeline vocal (utile pour respecter le cycle de vie de l'app et
///    les permissions micro).
/// 3. Le détecteur ne doit ajouter aucune dépendance native lourde tant que
///    ce chantier n'est pas explicitement lancé (pas de faster-whisper, pas
///    de moteur Wake Word natif pour l'instant).
abstract class WakeWordDetector {
  /// Émet un événement chaque fois que le mot-clé de réveil est détecté.
  /// Ne transporte aucune donnée audio : c'est un simple signal de
  /// déclenchement, à charge de l'appelant de démarrer la capture de
  /// commande via le pipeline existant.
  Stream<void> get onWakeWordDetected;

  /// Démarre l'écoute passive locale. Ne doit ouvrir aucune connexion réseau.
  Future<void> start();

  /// Arrête l'écoute passive locale et libère les ressources associées.
  Future<void> stop();

  /// Indique si l'écoute passive est actuellement active.
  bool get isActive;

  Future<void> dispose();
}

/// Implémentation neutre ("no-op") de [WakeWordDetector], utilisée tant que
/// le Wake Word Always-On n'est pas implémenté.
///
/// Elle ne détecte jamais rien, n'ouvre aucun accès micro et n'a aucun coût
/// (aucune dépendance native). Elle permet au reste de l'application (et au
/// futur [VoiceSessionController]) de coder contre l'interface
/// [WakeWordDetector] dès aujourd'hui, sans dépendre d'une implémentation
/// concrète qui n'existe pas encore.
class NoOpWakeWordDetector implements WakeWordDetector {
  final StreamController<void> _controller = StreamController<void>.broadcast();

  @override
  Stream<void> get onWakeWordDetected => _controller.stream;

  @override
  bool get isActive => false;

  @override
  Future<void> start() async {
    // Volontairement vide : aucune écoute réelle tant que le Wake Word
    // n'est pas implémenté.
  }

  @override
  Future<void> stop() async {
    // Volontairement vide.
  }

  @override
  Future<void> dispose() async {
    await _controller.close();
  }
}
