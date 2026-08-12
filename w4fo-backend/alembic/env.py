"""
Environnement Alembic — exécuté en mode SYNCHRONE via psycopg2, volontairement
DÉCOUPLÉ du moteur asynchrone (asyncpg) utilisé par l'application FastAPI.

Pourquoi ce découplage :
SQLAlchemy en mode asyncio s'appuie sur la bibliothèque `greenlet` pour faire
le pont entre code async/await et driver DBAPI (qui reste, sous le capot,
toujours synchrone au niveau C). Sur certains environnements — notamment
Windows avec un interpréteur Python ou une architecture particulière —
l'import de `greenlet` peut échouer avec une erreur de chargement de DLL
(`ImportError: DLL load failed while importing _greenlet`).

Les migrations Alembic n'ont elles-mêmes AUCUN besoin d'être asynchrones :
elles s'exécutent une par une, séquentiellement, au moment du déploiement.
Ce fichier utilise donc un moteur SQLAlchemy classique (`create_engine`,
pas `create_async_engine`) avec le driver `psycopg2`, ce qui élimine
complètement la dépendance à `greenlet` pour la commande `alembic`.

IMPORTANT : ceci ne change RIEN au fonctionnement de l'application FastAPI
elle-même, qui continue d'utiliser AsyncSession + asyncpg comme avant
(voir src/infrastructure/persistence/database.py). Seul l'outil `alembic`,
utilisé ponctuellement en ligne de commande, est concerné par ce changement.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from src.core.config import get_settings
from src.infrastructure.persistence.database import Base

# Import explicite de tous les modèles pour qu'Alembic détecte les tables
from src.infrastructure.persistence.models.calendar_event_model import CalendarEventModel  # noqa: F401
from src.infrastructure.persistence.models.google_oauth_token_model import GoogleOAuthTokenModel  # noqa: F401
from src.infrastructure.persistence.models.memory_model import MemoryModel  # noqa: F401
from src.infrastructure.persistence.models.notification_model import NotificationModel  # noqa: F401
from src.infrastructure.persistence.models.task_model import TaskModel  # noqa: F401
from src.infrastructure.persistence.models.user_model import UserModel  # noqa: F401
from src.infrastructure.persistence.models.user_settings_model import UserSettingsModel  # noqa: F401

config = context.config
settings = get_settings()


def _to_sync_url(database_url: str) -> str:
    """
    Convertit l'URL de connexion async (`postgresql+asyncpg://...`) en URL
    synchrone (`postgresql+psycopg2://...`) pour Alembic.

    Seul le driver DBAPI change ; utilisateur, mot de passe, hôte, port et
    nom de base restent identiques. Le SSL n'a pas besoin d'être forcé
    explicitement ici : psycopg2 négocie automatiquement en mode "prefer"
    par défaut (SSL si le serveur le supporte, sans SSL sinon) — ce qui
    fonctionne aussi bien avec Supabase (SSL obligatoire) qu'avec un
    PostgreSQL local sans SSL configuré, sans configuration supplémentaire.
    """
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


SYNC_DATABASE_URL = _to_sync_url(settings.database_url)
config.set_main_option("sqlalchemy.url", SYNC_DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Génère le SQL des migrations sans connexion réelle à la base (mode `alembic upgrade --sql`)."""
    context.configure(
        url=SYNC_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Exécute les migrations avec une connexion réelle, synchrone (psycopg2).

    `poolclass=pool.NullPool` : pas de pool de connexions à maintenir pour un
    outil qui se lance, exécute ses migrations, puis se termine — inutile et
    potentiellement source de connexions orphelines sinon.
    """
    connectable = create_engine(SYNC_DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
