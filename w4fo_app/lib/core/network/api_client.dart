import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../constants/app_constants.dart';
import '../errors/app_exceptions.dart';

/// Client HTTP centralisé pour tous les appels REST vers le backend W4FO.
///
/// Un seul point de configuration (base URL, timeouts, intercepteur JWT) :
/// les datasources ne créent jamais leur propre instance Dio.
///
/// --- Mécanisme de refresh automatique ---
///
/// Cause du 403 observé en production (corrigé précédemment) : l'access token
/// expire au bout de 15 minutes côté backend, et jusqu'ici (a) le backend
/// renvoyait un 403 (et non 401) quand aucun token n'était attaché à la
/// requête — comportement par défaut de FastAPI/`OAuth2PasswordBearer` — et
/// (b) même pour un 401 explicite, ce client ne faisait qu'étiqueter l'erreur
/// sans jamais utiliser le refresh token pourtant déjà stocké.
///
/// Ce client détecte un 401, utilise le refresh token pour obtenir un nouvel
/// access token, rejoue la requête originale, et ne déconnecte l'utilisateur
/// que si le refresh token est *réellement* rejeté par le backend (401 sur
/// `/auth/refresh`) — jamais sur une simple erreur réseau, pour éviter un
/// logout injustifié. Les refresh concurrents sont dé-dupliqués (un seul
/// appel réseau, les autres attendent son résultat).
///
/// `restoreSession()` (utilisé au démarrage de l'app, voir `auth_provider.dart`)
/// réutilise ce même mécanisme pour décider, sans flash d'écran ni appel
/// réseau superflu, si la session doit être restaurée telle quelle, rafraîchie,
/// ou si l'utilisateur doit être renvoyé au login.
class ApiClient {
  final Dio dio;
  final FlutterSecureStorage _secureStorage;

  /// Dio "nu", sans intercepteur, dédié aux appels de refresh : évite toute
  /// boucle (le refresh ne doit jamais lui-même déclencher un refresh) et
  /// évite d'attacher un access token expiré à cette requête.
  final Dio _plainDio;

  /// Dé-duplication des refresh concurrents : si un refresh est déjà en
  /// cours (ex. plusieurs requêtes échouent en même temps juste après un
  /// retour en premier plan), les appelants suivants attendent son résultat
  /// plutôt que de déclencher chacun leur propre appel `/auth/refresh`.
  Completer<_RefreshOutcome>? _refreshCompleter;

  /// Callback déclenché uniquement quand le refresh token est lui-même
  /// invalide/expiré (rejet explicite 401 du backend) : la session ne peut
  /// plus être renouvelée, il faut déconnecter proprement l'utilisateur.
  /// Branché depuis `AuthNotifier` (voir `auth_provider.dart`) pour éviter
  /// toute dépendance circulaire entre `ApiClient` et `AuthRepository`
  /// (`AuthRepository` dépend déjà de `ApiClient`, pas l'inverse).
  void Function()? onSessionExpired;

  ApiClient({FlutterSecureStorage? secureStorage})
      : _secureStorage = secureStorage ?? const FlutterSecureStorage(),
        dio = Dio(BaseOptions(
          baseUrl: AppConstants.apiBaseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
        )),
        _plainDio = Dio(BaseOptions(
          baseUrl: AppConstants.apiBaseUrl,
          connectTimeout: const Duration(seconds: 10),
          receiveTimeout: const Duration(seconds: 30),
        )) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _readAccessToken();
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (DioException error, handler) async {
          final statusCode = error.response?.statusCode;
          final requestPath = error.requestOptions.path;

          // Ne jamais tenter de refresh sur les endpoints d'auth eux-mêmes
          // (login/register/refresh) : un 401 sur `/auth/login` signifie
          // "mauvais identifiants", pas "session expirée".
          final isAuthEndpoint = requestPath.contains('/api/v1/auth/');

          // On ne retente qu'une seule fois par requête (marqueur posé dans
          // `extra`) pour éviter une boucle infinie si le nouveau token est,
          // pour une raison quelconque, encore rejeté.
          final alreadyRetried = error.requestOptions.extra['w4fo_retried'] == true;

          if (statusCode == 401 && !isAuthEndpoint && !alreadyRetried) {
            final outcome = await _refreshAccessToken();
            if (outcome.accessToken != null) {
              try {
                final retryOptions = error.requestOptions;
                retryOptions.extra['w4fo_retried'] = true;
                retryOptions.headers['Authorization'] = 'Bearer ${outcome.accessToken}';
                final response = await dio.fetch(retryOptions);
                handler.resolve(response);
                return;
              } on DioException catch (retryError) {
                handler.next(_mapError(retryError));
                return;
              }
            }

            if (outcome.refreshTokenInvalid) {
              // Le refresh token a été explicitement rejeté par le backend :
              // la session est définitivement terminée, il faut déconnecter.
              await _clearSession();
              onSessionExpired?.call();
              handler.next(_mapError(error, forceUnauthorized: true));
              return;
            }

            // Le refresh a échoué pour une raison réseau (pas de connexion,
            // timeout...) : on NE déconnecte PAS l'utilisateur — ce serait un
            // logout injustifié — on propage simplement l'erreur réseau, les
            // tokens restent en place pour une prochaine tentative.
            handler.next(_mapError(error));
            return;
          }

          handler.next(_mapError(error));
        },
      ),
    );
  }

  Future<String?> _readAccessToken() async {
    try {
      return await _secureStorage.read(key: AppConstants.secureStorageAccessTokenKey);
    } catch (_) {
      // Le Keystore Android peut occasionnellement échouer à déchiffrer les
      // valeurs stockées (ex. invalidation de la clé après un certain temps).
      // On traite ce cas comme "pas de token" plutôt que de laisser
      // l'exception remonter et casser la requête de façon opaque.
      return null;
    }
  }

  Future<String?> _readRefreshToken() async {
    try {
      return await _secureStorage.read(key: AppConstants.secureStorageRefreshTokenKey);
    } catch (_) {
      return null;
    }
  }

  Future<void> _clearSession() async {
    try {
      await _secureStorage.delete(key: AppConstants.secureStorageAccessTokenKey);
      await _secureStorage.delete(key: AppConstants.secureStorageRefreshTokenKey);
    } catch (_) {
      // Rien de plus à faire si même la suppression échoue ; l'utilisateur
      // sera de toute façon redirigé vers le login.
    }
  }

  /// Utilisé au démarrage de l'app pour décider l'état d'authentification
  /// initial (voir `AuthNotifier._checkInitialAuthStatus`) :
  ///
  /// - pas de refresh token stocké → session inexistante → `false` ;
  /// - access token encore valide (vérifié localement, décodage du JWT, SANS
  ///   appel réseau) → `true` immédiatement, aucun appel API superflu ;
  /// - access token expiré mais refresh token présent → tente un refresh ;
  /// - refresh explicitement rejeté (401) → session nettoyée → `false` ;
  /// - refresh impossible pour une raison réseau → `true` de façon
  ///   optimiste : on ne déconnecte jamais un utilisateur simplement parce
  ///   que le réseau n'était pas disponible au lancement. La prochaine
  ///   requête API réelle retentera le refresh via l'intercepteur ci-dessus.
  Future<bool> restoreSession() async {
    final refreshToken = await _readRefreshToken();
    if (refreshToken == null) {
      return false;
    }

    final accessToken = await _readAccessToken();
    if (accessToken != null && !_isJwtExpired(accessToken)) {
      return true;
    }

    final outcome = await _refreshAccessToken();
    if (outcome.accessToken != null) {
      return true;
    }
    if (outcome.refreshTokenInvalid) {
      await _clearSession();
      return false;
    }
    // Échec réseau pendant la tentative de restauration : optimiste, voir
    // la doc de la méthode ci-dessus.
    return true;
  }

  /// Échange le refresh token contre un nouvel access token, en dé-dupliquant
  /// les appels concurrents.
  Future<_RefreshOutcome> _refreshAccessToken() async {
    if (_refreshCompleter != null) {
      return _refreshCompleter!.future;
    }

    final completer = Completer<_RefreshOutcome>();
    _refreshCompleter = completer;

    try {
      final refreshToken = await _readRefreshToken();
      if (refreshToken == null) {
        const outcome = _RefreshOutcome(refreshTokenInvalid: true);
        completer.complete(outcome);
        return outcome;
      }

      final response = await _plainDio.post(
        '/api/v1/auth/refresh',
        data: {'refresh_token': refreshToken},
      );
      final data = response.data as Map<String, dynamic>;
      final newAccessToken = data['access_token'] as String;
      final newRefreshToken = data['refresh_token'] as String;

      await _secureStorage.write(key: AppConstants.secureStorageAccessTokenKey, value: newAccessToken);
      await _secureStorage.write(key: AppConstants.secureStorageRefreshTokenKey, value: newRefreshToken);

      final outcome = _RefreshOutcome(accessToken: newAccessToken);
      completer.complete(outcome);
      return outcome;
    } on DioException catch (e) {
      // Un 401 du endpoint /auth/refresh signifie que le refresh token
      // lui-même est invalide/expiré : c'est la SEULE situation qui doit
      // mener à un logout. Toute autre erreur (réseau, timeout, 5xx serveur)
      // est transitoire et ne doit pas déconnecter l'utilisateur.
      final isDefinitivelyInvalid = e.response?.statusCode == 401;
      final outcome = _RefreshOutcome(refreshTokenInvalid: isDefinitivelyInvalid);
      completer.complete(outcome);
      return outcome;
    } catch (_) {
      const outcome = _RefreshOutcome();
      completer.complete(outcome);
      return outcome;
    } finally {
      _refreshCompleter = null;
    }
  }

  DioException _mapError(DioException error, {bool forceUnauthorized = false}) {
    final statusCode = error.response?.statusCode;
    if (forceUnauthorized || statusCode == 401) {
      return error.copyWith(error: const UnauthorizedException());
    }
    if (statusCode == 403) {
      // Un 403 authentique (utilisateur authentifié mais non autorisé) ne
      // doit jamais être traité comme une session expirée : ni refresh, ni
      // logout automatique, juste une erreur d'autorisation à afficher.
      return error.copyWith(error: const ForbiddenException());
    }
    if (error.type == DioExceptionType.connectionError || error.type == DioExceptionType.connectionTimeout) {
      return error.copyWith(error: const NetworkException());
    }
    return error;
  }
}

/// Résultat interne d'une tentative de refresh. `refreshTokenInvalid` ne vaut
/// `true` que sur un rejet EXPLICITE (401) du endpoint `/auth/refresh` — pas
/// sur une simple erreur réseau — afin de ne jamais déconnecter l'utilisateur
/// à tort (voir la doc de [ApiClient.restoreSession] et de l'intercepteur).
class _RefreshOutcome {
  final String? accessToken;
  final bool refreshTokenInvalid;

  const _RefreshOutcome({this.accessToken, this.refreshTokenInvalid = false});
}

/// Décode localement (sans vérifier la signature — ce n'est pas nécessaire
/// ici, le backend est la seule autorité de validation réelle) le payload
/// d'un JWT pour lire son `exp` et éviter un aller-retour réseau quand
/// l'access token en cache est encore manifestement valide.
///
/// Marge de sécurité de 30 secondes : si le token expire dans les 30
/// prochaines secondes, on le traite comme déjà expiré pour éviter une
/// requête qui échouerait en cours de route (le temps que la requête HTTP
/// parte et arrive au backend).
bool _isJwtExpired(String token) {
  try {
    final parts = token.split('.');
    if (parts.length != 3) return true;

    var payloadSegment = parts[1];
    // Base64URL sans padding : on le rajoute avant de décoder.
    payloadSegment += '=' * ((4 - payloadSegment.length % 4) % 4);
    final payloadJson = utf8.decode(base64Url.decode(payloadSegment));
    final payload = jsonDecode(payloadJson) as Map<String, dynamic>;

    final exp = payload['exp'];
    if (exp is! int) return true;

    final expiryTime = DateTime.fromMillisecondsSinceEpoch(exp * 1000, isUtc: true);
    const safetyMargin = Duration(seconds: 30);
    return DateTime.now().toUtc().isAfter(expiryTime.subtract(safetyMargin));
  } catch (_) {
    // Token illisible/malformé : on le traite comme expiré par prudence,
    // ce qui déclenchera une tentative de refresh (ou un login si le
    // refresh token est lui aussi invalide).
    return true;
  }
}
