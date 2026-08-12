/// Exceptions applicatives, converties en messages utilisateur par la couche présentation.
sealed class AppException implements Exception {
  final String message;
  const AppException(this.message);
}

class UnauthorizedException extends AppException {
  const UnauthorizedException([super.message = 'Session expirée, merci de vous reconnecter.']);
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
