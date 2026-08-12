/// Constantes globales de l'application.
///
/// En développement, le backend tourne en local. En production, ces valeurs
/// doivent être injectées via `--dart-define` plutôt que codées en dur ici
/// (voir commentaire dans `main.dart`).
class AppConstants {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static const String wsBaseUrl = String.fromEnvironment(
    'WS_BASE_URL',
    defaultValue: 'ws://localhost:8000',
  );

  static const String secureStorageAccessTokenKey = 'w4fo_access_token';
  static const String secureStorageRefreshTokenKey = 'w4fo_refresh_token';
}
