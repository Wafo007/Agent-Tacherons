import '../entities/user.dart';

/// Interface (Port) : AuthRepository.
///
/// Définit ce dont le domaine a besoin pour l'authentification, sans connaître
/// le détail d'implémentation (appel HTTP, stockage sécurisé...). Implémentée
/// par `data/repositories_impl/auth_repository_impl.dart`.
abstract class AuthRepository {
  Future<User> register({
    required String email,
    required String fullName,
    required String password,
  });

  /// Connecte l'utilisateur et persiste les tokens (access + refresh) dans le stockage sécurisé.
  Future<void> login({required String email, required String password});

  Future<void> logout();

  /// Retourne l'access token courant, ou `null` si l'utilisateur n'est pas connecté.
  Future<String?> getAccessToken();

  Future<bool> isLoggedIn();

  /// Restaure la session au démarrage de l'application : valide l'access
  /// token en cache localement (sans appel réseau si possible), le rafraîchit
  /// via le refresh token si besoin, et ne renvoie `false` (session perdue)
  /// que si le refresh token est explicitement invalide/expiré. Voir
  /// `ApiClient.restoreSession` pour le détail du comportement.
  Future<bool> restoreSession();
}
