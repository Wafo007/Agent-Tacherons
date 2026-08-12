import '../../data/datasources/remote/settings_remote_datasource.dart';

/// Interface (Port) : SettingsRepository.
///
/// Exception assumée à la règle générale : cette interface référence
/// directement `UserSettingsData` (défini dans la couche data) plutôt qu'une
/// entité de domaine dédiée, car ces données sont de pures préférences UI
/// sans règle métier associée. Documenté ici plutôt que masqué.
abstract class SettingsRepository {
  Future<UserSettingsData> getSettings();
  Future<UserSettingsData> updateSettings(UserSettingsData settings);
}
