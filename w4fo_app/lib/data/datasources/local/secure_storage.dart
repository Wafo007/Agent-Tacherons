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

  /// Ces lectures sont volontairement défensives : sur Android, la clé
  /// Keystore utilisée par `flutter_secure_storage` peut occasionnellement
  /// devenir indéchiffrable (ex. invalidation après un certain temps ou un
  /// changement de verrouillage d'écran), ce qui fait lever une
  /// `PlatformException` par `read()` plutôt que de renvoyer `null`. Sans ce
  /// `try/catch`, cette exception remontait telle quelle jusqu'à l'appelant
  /// (potentiellement l'intercepteur Dio), ce qui produisait des échecs de
  /// requête difficiles à diagnostiquer. On traite ce cas comme "pas de
  /// token" : le flux de refresh / redirection vers le login prend le relais
  /// normalement.
  Future<String?> getAccessToken() async {
    try {
      return await _storage.read(key: AppConstants.secureStorageAccessTokenKey);
    } catch (_) {
      return null;
    }
  }

  Future<String?> getRefreshToken() async {
    try {
      return await _storage.read(key: AppConstants.secureStorageRefreshTokenKey);
    } catch (_) {
      return null;
    }
  }

  Future<void> clear() async {
    try {
      await _storage.delete(key: AppConstants.secureStorageAccessTokenKey);
      await _storage.delete(key: AppConstants.secureStorageRefreshTokenKey);
    } catch (_) {
      // Rien de plus à faire si la suppression échoue elle aussi.
    }
  }
}
