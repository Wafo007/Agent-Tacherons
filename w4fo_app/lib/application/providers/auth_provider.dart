import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/di/injection.dart';
import '../../core/errors/app_exceptions.dart';

/// État d'authentification de l'application.
enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthState {
  final AuthStatus status;
  final String? errorMessage;
  final bool isLoading;

  const AuthState({this.status = AuthStatus.unknown, this.errorMessage, this.isLoading = false});

  AuthState copyWith({AuthStatus? status, String? errorMessage, bool? isLoading}) {
    return AuthState(
      status: status ?? this.status,
      errorMessage: errorMessage,
      isLoading: isLoading ?? this.isLoading,
    );
  }
}

/// Gère le cycle de vie de l'authentification (connexion, inscription, déconnexion,
/// vérification de session au démarrage). Consommé par le router pour rediriger
/// vers l'écran de login ou l'application principale.
class AuthNotifier extends StateNotifier<AuthState> {
  final Ref _ref;

  /// Empêche deux restaurations de session simultanées (ex. un premier appel
  /// au démarrage de l'app pas encore terminé et un second déclenché par un
  /// retour en premier plan quasi immédiat) : la seconde attend simplement le
  /// résultat de la première plutôt que de dupliquer l'appel réseau de refresh.
  Future<void>? _pendingRestore;

  AuthNotifier(this._ref) : super(const AuthState()) {
    // Branche le callback de session expirée sur l'ApiClient : c'est le seul
    // point d'entrée par lequel une expiration détectée en plein milieu d'un
    // appel API (refresh token lui-même invalide/expiré) peut redescendre
    // jusqu'à l'état d'authentification et déclencher la redirection vers le
    // login (voir `app_router.dart`, qui redirige sur `AuthStatus.unauthenticated`).
    _ref.read(apiClientProvider).onSessionExpired = _handleSessionExpired;
    _checkInitialAuthStatus();
  }

  void _handleSessionExpired() {
    if (!mounted) return;
    state = state.copyWith(
      status: AuthStatus.unauthenticated,
      errorMessage: 'Session expirée, merci de vous reconnecter.',
    );
  }

  /// Restauration de session au lancement de l'app : lit le stockage sécurisé,
  /// valide/rafraîchit le token si besoin (voir `ApiClient.restoreSession`),
  /// puis résout le statut `unknown` initial vers `authenticated` ou
  /// `unauthenticated`. Tant que ce statut reste `unknown`, le router affiche
  /// un écran de démarrage neutre (voir `app_router.dart`) au lieu de laisser
  /// apparaître brièvement l'écran de login ou de lancer des appels API sur
  /// un écran protégé avant que la session soit vraiment connue.
  Future<void> _checkInitialAuthStatus() async {
    final isSessionValid = await _ref.read(authRepositoryProvider).restoreSession();
    if (!mounted) return;
    state = state.copyWith(status: isSessionValid ? AuthStatus.authenticated : AuthStatus.unauthenticated);
  }

  /// À appeler quand l'application revient au premier plan (voir
  /// `main.dart`, `_W4FOAppState.didChangeAppLifecycleState`). Après une
  /// longue mise en arrière-plan, l'access token en cache a pu expirer ;
  /// on le revalide/rafraîchit proactivement plutôt que d'attendre qu'un
  /// appel API échoue une première fois. Ne fait rien si l'utilisateur
  /// n'était de toute façon pas authentifié, et ne déclenche jamais deux
  /// restaurations en parallèle.
  Future<void> revalidateOnResume() async {
    if (state.status != AuthStatus.authenticated) return;
    if (_pendingRestore != null) {
      await _pendingRestore;
      return;
    }

    final future = _checkInitialAuthStatus();
    _pendingRestore = future;
    try {
      await future;
    } finally {
      _pendingRestore = null;
    }
  }

  Future<void> login(String email, String password) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      await _ref.read(authRepositoryProvider).login(email: email, password: password);
      state = state.copyWith(status: AuthStatus.authenticated, isLoading: false);
    } on AppException catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.message);
    } catch (_) {
      state = state.copyWith(isLoading: false, errorMessage: 'Connexion impossible. Vérifiez vos identifiants.');
    }
  }

  Future<void> register(String email, String fullName, String password) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      await _ref.read(authRepositoryProvider).register(email: email, fullName: fullName, password: password);
      // Inscription réussie : on enchaîne automatiquement sur la connexion pour une UX fluide.
      await login(email, password);
    } on AppException catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.message);
    } catch (_) {
      state = state.copyWith(isLoading: false, errorMessage: "Impossible de créer le compte. Cet e-mail est peut-être déjà utilisé.");
    }
  }

  Future<void> logout() async {
    await _ref.read(authRepositoryProvider).logout();
    state = state.copyWith(status: AuthStatus.unauthenticated);
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) => AuthNotifier(ref));
