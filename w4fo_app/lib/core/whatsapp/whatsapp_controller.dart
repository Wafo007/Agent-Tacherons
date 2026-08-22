import 'package:flutter/services.dart';

/// Un message WhatsApp reçu, transmis par `WafoNotificationListenerService`
/// (natif) via l'`EventChannel`.
class WhatsAppMessage {
  final String sender;
  final String text;

  /// `true` si WhatsApp a fourni une action "Répondre" (`RemoteInput`) sur
  /// cette notification — condition nécessaire pour que [WhatsAppController.sendReply]
  /// puisse fonctionner. `false` dans de rares cas (notification système,
  /// message déjà consommé) : voir le README pour la limite documentée.
  final bool canReply;

  const WhatsAppMessage({required this.sender, required this.text, required this.canReply});

  factory WhatsAppMessage.fromMap(Map<dynamic, dynamic> map) {
    return WhatsAppMessage(
      sender: map['sender'] as String? ?? 'Inconnu',
      text: map['text'] as String? ?? '',
      canReply: map['canReply'] as bool? ?? false,
    );
  }
}

/// Pont natif vers `WafoNotificationListenerService.kt` (§ WHATSAPP).
///
/// Deux canaux distincts, cohérents avec le pattern déjà utilisé pour
/// l'écoute vocale en arrière-plan (`BackgroundListeningController`) :
/// - un `MethodChannel` (`w4fo/whatsapp_control`) pour les commandes
///   ponctuelles (vérifier/demander l'accès, activer/désactiver l'écoute,
///   envoyer une réponse) ;
/// - un `EventChannel` (`w4fo/whatsapp_events`) pour le flux des messages
///   WhatsApp reçus, poussés par le service natif au fil de l'eau.
///
/// § RAPPEL ARCHITECTURE (voir README du dossier) : ce contrôleur ne parle
/// JAMAIS à un serveur Meta/WhatsApp. Tout se passe en local sur l'appareil,
/// via les API Android officielles `NotificationListenerService` et
/// `RemoteInput`.
class WhatsAppController {
  static const MethodChannel _methodChannel = MethodChannel('w4fo/whatsapp_control');
  static const EventChannel _eventChannel = EventChannel('w4fo/whatsapp_events');

  Stream<WhatsAppMessage>? _messageStream;

  /// Vérifie si l'utilisateur a accordé l'accès aux notifications à W4FO.
  /// Permission jamais accordée silencieusement — voir [openNotificationAccessSettings].
  Future<bool> hasNotificationAccess() async {
    final result = await _methodChannel.invokeMethod<bool>('hasNotificationAccess');
    return result ?? false;
  }

  /// Ouvre l'écran système standard de gestion de l'accès aux notifications
  /// (liste de toutes les apps demandant cet accès sur l'appareil).
  /// L'utilisateur doit y activer W4FO explicitement.
  Future<void> openNotificationAccessSettings() => _methodChannel.invokeMethod('openNotificationAccessSettings');

  /// Active/désactive le filtrage des notifications WhatsApp par le service
  /// natif. Le service reste installé (l'accès aux notifications, une fois
  /// accordé, reste accordé), mais ne traite RIEN tant que
  /// `enabled = false` — c'est ce niveau applicatif, pas seulement la
  /// permission système, qui contrôle si W4FO lit réellement les messages.
  Future<void> setListeningEnabled(bool enabled) =>
      _methodChannel.invokeMethod('setListeningEnabled', {'enabled': enabled});

  Future<bool> hasPendingMessage() async {
    final result = await _methodChannel.invokeMethod<bool>('hasPendingMessage');
    return result ?? false;
  }

  /// Envoie [text] comme réponse au message WhatsApp actuellement en attente,
  /// via l'action "Répondre" native de la notification (`RemoteInput`).
  /// Retourne `false` si aucun message n'est en attente ou si l'envoi a échoué
  /// (jamais d'exception : un échec de réponse ne doit jamais faire planter
  /// l'app — voir `WhatsAppNotifier`, qui informe l'utilisateur du résultat).
  Future<bool> sendReply(String text) async {
    final result = await _methodChannel.invokeMethod<bool>('sendReply', {'text': text});
    return result ?? false;
  }

  Future<void> clearPendingMessage() => _methodChannel.invokeMethod('clearPendingMessage');

  /// Flux des messages WhatsApp reçus, tant que l'écoute est activée
  /// ([setListeningEnabled]). Le flux est mis en cache (`broadcast`) : peut
  /// être écouté par plusieurs abonnés sans rouvrir le canal natif.
  Stream<WhatsAppMessage> get messages {
    _messageStream ??= _eventChannel.receiveBroadcastStream().map(
          (event) => WhatsAppMessage.fromMap(event as Map<dynamic, dynamic>),
        );
    return _messageStream!;
  }
}
