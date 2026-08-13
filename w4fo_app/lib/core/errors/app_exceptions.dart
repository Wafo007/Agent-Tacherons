/// Exceptions applicatives, converties en messages utilisateur par la couche présentation.
sealed class AppException implements Exception {
  final String message;
  const AppException(this.message);
}

class UnauthorizedException extends AppException {
  const UnauthorizedException([super.message = 'Session expirée, merci de vous reconnecter.']);
}

/// Distincte de [UnauthorizedException] : un 403 authentique signifie que
/// l'utilisateur est bien authentifié mais n'a pas le droit d'effectuer cette
/// action. Contrairement à un 401, cela ne doit jamais déclencher un refresh
/// de session ni une déconnexion automatique.
class ForbiddenException extends AppException {
  const ForbiddenException([super.message = "Vous n'êtes pas autorisé à effectuer cette action."]);
}

class NetworkException extends AppException {
  const NetworkException([super.message = 'Impossible de contacter le serveur W4FO.']);
}

class ValidationException extends AppException {
  const ValidationException(super.message);
}

class UnknownException extends AppException {
  const UnknownException([super.message = 'Une erreur inattendue est survenue.']);
}
