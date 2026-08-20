import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:record/record.dart';

import '../../core/voice/background_listening_controller.dart';
import 'voice_chat_provider.dart';

/// État local (non synchronisé au backend, non persistant entre redémarrages
/// de l'app pour l'instant — voir limitations) de l'écoute permanente en
/// arrière-plan.
class BackgroundListeningState {
  final bool enabled;
  final bool starting;
  final String? error;

  const BackgroundListeningState({this.enabled = false, this.starting = false, this.error});

  BackgroundListeningState copyWith({bool? enabled, bool? starting, String? error}) {
    return BackgroundListeningState(
      enabled: enabled ?? this.enabled,
      starting: starting ?? this.starting,
      error: error,
    );
  }
}

/// Orchestre le Foreground Service Android d'écoute permanente (§ ANDROID
/// SERVICE) depuis Flutter : démarrage/arrêt, permissions, et réception du
/// signal "l'app a été ramenée au premier plan par une détection du mot-clé
/// en arrière-plan" pour enchaîner directement sur la capture de commande.
///
/// ⚠️ Ne fonctionne que sur Android (le `MethodChannel` sous-jacent n'a pas
/// d'implémentation côté iOS/desktop dans ce chantier) : [enable] échoue
/// silencieusement (résultat `error`) sur toute autre plateforme plutôt que
/// de planter l'app.
class BackgroundListeningNotifier extends StateNotifier<BackgroundListeningState> {
  final Ref _ref;
  final BackgroundListeningController _controller;
  final AudioRecorder _recorder;

  BackgroundListeningNotifier(this._ref, {BackgroundListeningController? controller, AudioRecorder? recorder})
      : _controller = controller ?? BackgroundListeningController(),
        _recorder = recorder ?? AudioRecorder(),
        super(const BackgroundListeningState()) {
    _controller.setEventHandler(_handleNativeEvent);
  }

  Future<dynamic> _handleNativeEvent(MethodCall call) async {
    switch (call.method) {
      case 'onWakeWordLaunch':
        // L'app vient d'être ramenée au premier plan suite à une détection
        // en arrière-plan : le mot-clé a déjà été consommé côté service, on
        // démarre DIRECTEMENT la capture de commande (pas de re-passage par
        // l'écoute du mot-clé, qui gaspillerait une session micro).
        await _ref.read(voiceChatProvider.notifier).startListening();
    }
    return null;
  }

  /// Active l'écoute permanente en arrière-plan.
  ///
  /// Vérifie/demande la permission micro (obligatoire — le service refuse de
  /// démarrer sans elle) et la permission notification (Android 13+ ; sans
  /// elle, le service démarre quand même — obligation Android — mais sa
  /// notification persistante peut être moins visible selon l'appareil).
  /// N'active JAMAIS rien sans que ces vérifications aient été tentées.
  Future<void> enable() async {
    state = state.copyWith(starting: true, error: null);

    final hasMicPermission = await _recorder.hasPermission();
    if (!hasMicPermission) {
      state = state.copyWith(
        starting: false,
        error: "Permission microphone refusée : impossible d'activer l'écoute en arrière-plan.",
      );
      return;
    }

    if (!await _controller.hasNotificationPermission()) {
      await _controller.requestNotificationPermission();
    }

    try {
      await _controller.start();
      state = state.copyWith(enabled: true, starting: false);
    } on PlatformException catch (e) {
      state = state.copyWith(starting: false, error: e.message ?? "Impossible de démarrer l'écoute permanente.");
    } on MissingPluginException {
      // Plateforme non-Android (pas d'implémentation native du canal) : on
      // le signale proprement plutôt que de planter l'app.
      state = state.copyWith(
        starting: false,
        error: "L'écoute permanente en arrière-plan n'est disponible que sur Android pour le moment.",
      );
    }
  }

  Future<void> disable() async {
    try {
      await _controller.stop();
    } on MissingPluginException {
      // no-op hors Android
    }
    state = state.copyWith(enabled: false);
  }

  Future<bool> isBatteryOptimizationIgnored() async {
    try {
      return await _controller.isIgnoringBatteryOptimizations();
    } on MissingPluginException {
      return true; // n'est pertinent que sur Android
    }
  }

  Future<void> openBatteryOptimizationSettings() async {
    try {
      await _controller.openBatteryOptimizationSettings();
    } on MissingPluginException {
      // no-op hors Android
    }
  }
}

final backgroundListeningProvider =
    StateNotifierProvider<BackgroundListeningNotifier, BackgroundListeningState>(
  (ref) => BackgroundListeningNotifier(ref),
);
