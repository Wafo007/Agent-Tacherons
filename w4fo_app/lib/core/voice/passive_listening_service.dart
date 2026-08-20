/// Contrat pour un futur service d'écoute passive.
///
/// L'écoute passive est la phase pendant laquelle l'app "attend" un mot-clé
/// de réveil (ou une autre condition d'activation locale) sans intervention
/// de l'utilisateur.
///
/// Règle produit non négociable, rappelée ici pour toute implémentation
/// future : **l'écoute passive ne doit jamais envoyer de flux audio en
/// continu à Mistral (ni à aucun service distant)**. Le coût réseau/API et
/// le risque vie privée d'un tel flux permanent sont inacceptables.
///
/// Le flux attendu est donc strictement :
///
///   1. [PassiveListeningService] tourne en local (VAD + Wake Word),
///      consomme le micro mais n'émet rien vers le réseau.
///   2. Dès que le mot-clé est détecté, on bascule sur le pipeline de
///      capture de commande déjà existant (`VoiceChatNotifier.startListening`
///      → `RecordConfig` + `VoiceWebSocketClient.sendAudioChunk`), qui, lui,
///      envoie effectivement l'audio au backend le temps de la commande.
///   3. Une fois la commande traitée (`end_of_turn`), on repasse en écoute
///      passive locale (retour à l'étape 1), jamais en flux réseau continu.
///
/// Ce fichier ne fait qu'exposer l'interface : aucune implémentation
/// concrète (moteur de VAD, wake word natif, service Android Always-On)
/// n'est fournie ici. Voir aussi [WakeWordDetector] dans
/// `wake_word_detector.dart`, qui couvre spécifiquement la détection du
/// mot-clé — [PassiveListeningService] est le conteneur de plus haut niveau
/// qui orchestrera ce détecteur une fois le chantier Always-On lancé.
abstract class PassiveListeningService {
  /// Démarre l'écoute passive locale. Implémentation future : ne doit
  /// ouvrir aucune connexion WebSocket ni envoyer aucune donnée audio tant
  /// que le mot-clé n'a pas été détecté.
  Future<void> start();

  /// Arrête l'écoute passive locale.
  Future<void> stop();

  /// Indique si l'écoute passive est active.
  bool get isActive;
}
