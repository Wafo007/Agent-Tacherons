import 'package:flutter/services.dart';

/// Pont natif (MethodChannel `"w4fo/background_listening"`) vers le
/// Foreground Service Android (`WafoBackgroundService.kt`) qui permet à
/// W4FO d'écouter le mot-clé de réveil ("Wafo") lorsque l'application n'est
/// pas au premier plan.
///
/// § LIMITES à toujours garder à l'esprit côté appelant (voir aussi
/// `background_wakeword_entrypoint.dart` et le README de `core/voice/`) :
/// démarrer ce service affiche IMMÉDIATEMENT une notification persistante
/// (obligatoire, imposée par Android — ni masquable, ni contournable), et ne
/// garantit ni une écoute infinie (le système peut tuer le process), ni un
/// fonctionnement écran verrouillé identique sur tous les appareils.
class BackgroundListeningController {
  static const MethodChannel _channel = MethodChannel('w4fo/background_listening');

  /// Démarre le Foreground Service. Ne vérifie AUCUNE permission par
  /// lui-même : l'appelant doit s'assurer du micro (`record` package) et,
  /// idéalement, de la notification (voir [hasNotificationPermission]) au
  /// préalable — voir `background_listening_provider.dart`.
  Future<void> start() => _channel.invokeMethod('startBackgroundListening');

  /// Arrête le Foreground Service et libère le moteur Flutter headless associé.
  Future<void> stop() => _channel.invokeMethod('stopBackgroundListening');

  Future<bool> hasNotificationPermission() async {
    final result = await _channel.invokeMethod<bool>('hasNotificationPermission');
    return result ?? false;
  }

  /// Déclenche la boîte de dialogue système standard de demande de
  /// permission (Android 13+ uniquement ; no-op avant).
  Future<void> requestNotificationPermission() => _channel.invokeMethod('requestNotificationPermission');

  Future<bool> isIgnoringBatteryOptimizations() async {
    final result = await _channel.invokeMethod<bool>('isIgnoringBatteryOptimizations');
    return result ?? false;
  }

  /// Ouvre l'écran système "Optimisation de la batterie" — n'accorde rien
  /// automatiquement, l'utilisateur choisit explicitement dans un écran natif.
  Future<void> openBatteryOptimizationSettings() =>
      _channel.invokeMethod('requestIgnoreBatteryOptimizations');

  /// Écoute les événements envoyés PAR le natif (`MainActivity.kt`) :
  /// - `onWakeWordLaunch` : l'app vient d'être ramenée au premier plan suite
  ///   à une détection du mot-clé en arrière-plan ;
  /// - `onNotificationPermissionResult` (bool) : résultat de la demande de
  ///   permission notification.
  void setEventHandler(Future<dynamic> Function(MethodCall call) handler) {
    _channel.setMethodCallHandler(handler);
  }
}
