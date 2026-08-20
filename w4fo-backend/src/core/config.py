"""
Configuration centrale de l'application, chargée depuis les variables d'environnement.

Utilise pydantic-settings pour valider et typer la configuration dès le démarrage :
une variable manquante ou mal typée fait échouer le démarrage immédiatement,
plutôt que de provoquer une erreur silencieuse plus tard en production.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Application ---
    app_name: str = "W4FO"
    environment: str = "development"
    debug: bool = True

    # --- Base de données ---
    database_url: str
    # True par défaut : nécessaire pour Supabase (et la plupart des PostgreSQL
    # managés), qui exigent une connexion chiffrée. Mettre à False dans .env
    # si tu utilises un PostgreSQL local (Docker ou natif) sans SSL configuré
    # — sinon la connexion échouera (le serveur local ne sait pas répondre à
    # une négociation SSL qu'il ne supporte pas).
    database_ssl_require: bool = True

    # --- Sécurité / JWT ---
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # --- Mistral AI ---
    mistral_api_key: str
    mistral_model: str = "mistral-large-latest"

    # --- Google Calendar (V2) ---
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    # --- Boucle agentique ---
    # Nombre maximal d'itérations agent<->outils autorisées par tour de conversation,
    # avant de forcer une réponse finale (garde-fou anti-boucle infinie).
    agent_max_iterations: int = 6

    # --- Fuseau horaire applicatif ---
    # Utilisé pour ancrer la date/heure "actuelle" injectée dans le prompt système
    # de l'agent, et pour résoudre les expressions temporelles relatives des tâches
    # (§ DATE ET HEURE : "demain", "vendredi prochain", "dans 2 heures"...). Nom de
    # zone IANA standard (ex: "Europe/Paris", "Africa/Douala").
    app_timezone: str = "Europe/Paris"


@lru_cache
def get_settings() -> Settings:
    """Retourne une instance unique (singleton) des settings, mise en cache."""
    return Settings()
