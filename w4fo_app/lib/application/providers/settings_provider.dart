import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/injection.dart';
import '../../data/datasources/remote/settings_remote_datasource.dart';

class SettingsState {
  final UserSettingsData? settings;
  final bool isLoading;

  const SettingsState({this.settings, this.isLoading = false});

  SettingsState copyWith({UserSettingsData? settings, bool? isLoading}) {
    return SettingsState(settings: settings ?? this.settings, isLoading: isLoading ?? this.isLoading);
  }
}

class SettingsNotifier extends StateNotifier<SettingsState> {
  final Ref _ref;

  SettingsNotifier(this._ref) : super(const SettingsState()) {
    loadSettings();
  }

  Future<void> loadSettings() async {
    state = state.copyWith(isLoading: true);
    try {
      final settings = await _ref.read(settingsRepositoryProvider).getSettings();
      state = state.copyWith(settings: settings, isLoading: false);
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  Future<void> update(UserSettingsData updated) async {
    state = state.copyWith(settings: updated); // Optimiste
    try {
      final saved = await _ref.read(settingsRepositoryProvider).updateSettings(updated);
      state = state.copyWith(settings: saved);
    } catch (_) {
      await loadSettings(); // Repli : on recharge la vraie valeur serveur en cas d'échec
    }
  }
}

final settingsProvider = StateNotifierProvider<SettingsNotifier, SettingsState>((ref) => SettingsNotifier(ref));
