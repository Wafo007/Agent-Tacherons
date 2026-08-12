"""
Configuration du moteur SQLAlchemy asynchrone et de la session de base de données.

Ce moteur reste ASYNCHRONE (asyncpg) : c'est celui utilisé par l'application
FastAPI à l'exécution (routers, use cases, agents LangGraph). Les migrations
Alembic, elles, utilisent un moteur SÉPARÉ et SYNCHRONE (voir alembic/env.py)
pour ne jamais dépendre de `greenlet` — une bibliothèque native requise par
SQLAlchemy dès qu'un moteur asyncio est utilisé, et qui peut poser des
problèmes d'installation sur certains environnements Windows (échec de
chargement de DLL). Ce découplage n'affecte en rien le fonctionnement normal
de l'application : elle continue d'utiliser AsyncSession partout.

`statement_cache_size=0` : désactive le cache de requêtes préparées d'asyncpg.
Obligatoire si tu utilises un connection pooler en mode "Transaction" (ex.
PgBouncer, y compris celui de Supabase sur le port 6543) — ce mode ne supporte
pas les prepared statements persistants entre requêtes. Sans incidence notable
sur les performances pour ce projet ; désactivé par défaut pour éviter un
piège difficile à diagnostiquer si tu passes un jour en pooler.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.core.config import get_settings

settings = get_settings()

_connect_args: dict = {"statement_cache_size": 0}
if settings.database_ssl_require:
    # Nécessaire pour Supabase et la plupart des PostgreSQL managés. Ne PAS
    # activer pour un PostgreSQL local sans SSL configuré (voir DATABASE_SSL_REQUIRE
    # dans core/config.py) — asyncpg n'a, contrairement à psycopg2, aucun mode
    # de repli automatique et échouera si le serveur ne sait pas négocier SSL.
    _connect_args["ssl"] = "require"

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Classe de base déclarative pour tous les modèles SQLAlchemy."""


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency FastAPI fournissant une session de base de données par requête."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
