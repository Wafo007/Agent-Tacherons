import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../../../core/constants/app_constants.dart';

/// Wrapper autour de `flutter_secure_storage`, dédié aux tokens JWT.
///
/// Isole le reste de l'application du détail "quel mécanisme de stockage
/// sécurisé est utilisé" — un futur changement (ex. Keychain natif custom)
/// ne toucherait que ce fichier.
class SecureStorage {
  final FlutterSecureStorage _storage;

  const SecureStorage({FlutterSecureStorage storage = const FlutterSecureStorage()}) : _storage = storage;

  Future<void> saveTokens({required String accessToken, required String refreshToken}) async {
    await _storage.write(key: AppConstants.secureStorageAccessTokenKey, value: accessToken);
    await _storage.write(key: AppConstants.secureStorageRefreshTokenKey, value: refreshToken);
  }

  Future<String?> getAccessToken() => _storage.read(key: AppConstants.secureStorageAccessTokenKey);

  Future<String?> getRefreshToken() => _storage.read(key: AppConstants.secureStorageRefreshTokenKey);

  Future<void> clear() async {
    await _storage.delete(key: AppConstants.secureStorageAccessTokenKey);
    await _storage.delete(key: AppConstants.secureStorageRefreshTokenKey);
  }
}
