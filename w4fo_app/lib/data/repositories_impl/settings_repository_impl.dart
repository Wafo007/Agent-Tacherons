import '../datasources/remote/settings_remote_datasource.dart';
import '../../domain/repositories/settings_repository.dart';

class SettingsRepositoryImpl implements SettingsRepository {
  final SettingsRemoteDataSource _remoteDataSource;

  const SettingsRepositoryImpl(this._remoteDataSource);

  @override
  Future<UserSettingsData> getSettings() => _remoteDataSource.getSettings();

  @override
  Future<UserSettingsData> updateSettings(UserSettingsData settings) => _remoteDataSource.updateSettings(settings);
}
