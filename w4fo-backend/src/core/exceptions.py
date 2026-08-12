"""Exceptions métier centralisées, converties en réponses HTTP par la couche presentation."""


class W4FOException(Exception):
    """Exception de base pour toutes les erreurs métier W4FO."""


class EntityNotFoundError(W4FOException):
    """Levée quand une entité demandée n'existe pas."""


class UnauthorizedError(W4FOException):
    """Levée en cas d'échec d'authentification ou d'autorisation."""


class EmailAlreadyExistsError(W4FOException):
    """Levée lors d'une tentative d'inscription avec un e-mail déjà utilisé."""


class ValidationError(W4FOException):
    """Levée en cas de violation d'une règle métier de validation."""
