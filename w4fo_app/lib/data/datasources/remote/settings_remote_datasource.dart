import 'package:dio/dio.dart';

import '../../../core/network/api_client.dart';

/// Modèle simple pour les paramètres utilisateur (pas d'entité de domaine
/// dédiée pour l'instant : ces données sont purement des préférences UI,
/// sans règle métier associée côté client).
class UserSettingsData {
  final String voiceId;
  final int volumeLevel;
  final String briefingTime; // format "HH:MM:SS", tel que renvoyé par le backend
  final bool darkMode;
  final String language;
  final String autonomyLevel;

  const UserSettingsData({
    required this.voiceId,
    required this.volumeLevel,
    required this.briefingTime,
    required this.darkMode,
    required this.language,
    required this.autonomyLevel,
  });

  factory UserSettingsData.fromJson(Map<String, dynamic> json) {
    return UserSettingsData(
      voiceId: json['voice_id'] as String? ?? 'default',
      volumeLevel: json['volume_level'] as int? ?? 80,
      briefingTime: json['briefing_time'] as String? ?? '07:30:00',
      darkMode: json['dark_mode'] as bool? ?? true,
      language: json['language'] as String? ?? 'fr',
      autonomyLevel: json['autonomy_level'] as String? ?? 'medium',
    );
  }

  Map<String, dynamic> toJson() => {
        'voice_id': voiceId,
        'volume_level': volumeLevel,
        'briefing_time': briefingTime,
        'dark_mode': darkMode,
        'language': language,
        'autonomy_level': autonomyLevel,
      };

  UserSettingsData copyWith({
    String? voiceId,
    int? volumeLevel,
    String? briefingTime,
    bool? darkMode,
    String? language,
    String? autonomyLevel,
  }) {
    return UserSettingsData(
      voiceId: voiceId ?? this.voiceId,
      volumeLevel: volumeLevel ?? this.volumeLevel,
      briefingTime: briefingTime ?? this.briefingTime,
      darkMode: darkMode ?? this.darkMode,
      language: language ?? this.language,
      autonomyLevel: autonomyLevel ?? this.autonomyLevel,
    );
  }
}

/// Datasource distante : appels HTTP bruts vers `/api/v1/settings`.
class SettingsRemoteDataSource {
  final Dio _dio;

  SettingsRemoteDataSource(ApiClient apiClient) : _dio = apiClient.dio;

  Future<UserSettingsData> getSettings() async {
    final response = await _dio.get('/api/v1/settings');
    return UserSettingsData.fromJson(response.data as Map<String, dynamic>);
  }

  Future<UserSettingsData> updateSettings(UserSettingsData settings) async {
    final response = await _dio.put('/api/v1/settings', data: settings.toJson());
    return UserSettingsData.fromJson(response.data as Map<String, dynamic>);
  }
}
