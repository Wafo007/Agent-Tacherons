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

  AuthNotifier(this._ref) : super(const AuthState()) {
    _checkInitialAuthStatus();
  }

  Future<void> _checkInitialAuthStatus() async {
    final isLoggedIn = await _ref.read(authRepositoryProvider).isLoggedIn();
    state = state.copyWith(status: isLoggedIn ? AuthStatus.authenticated : AuthStatus.unauthenticated);
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
