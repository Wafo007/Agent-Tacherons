"""
Scheduler de tâches proactives — implémente le "Réveil intelligent" (§2 et
roadmap V2 du document d'architecture).

Approche V2 : un job APScheduler s'exécute chaque minute et vérifie, pour
chaque utilisateur, si l'heure LOCALE courante (calculée à partir de
`User.timezone`, ex. "Europe/Paris") correspond à son `briefing_time`
configuré. `UserSettings.briefing_time` est donc interprété comme une heure
locale au fuseau de l'utilisateur, pas en UTC — cohérent avec l'expérience
attendue ("réveille-moi à 7h30" signifie 7h30 chez l'utilisateur, pas à
Greenwich.

Reste une approche par polling plutôt que par planification individuelle (un
job par utilisateur) : suffisant tant que le nombre d'utilisateurs est faible ;
à remplacer par un job dédié par utilisateur (trigger="cron") en V3 si le
volume le justifie, pour éviter de comparer N utilisateurs à chaque tick.
"""

import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.application.use_cases.manage_notifications.run_morning_briefing import RunMorningBriefingForUserUseCase
from src.core.dependencies import get_calendar_provider, get_llm_provider
from src.infrastructure.persistence.database import AsyncSessionLocal
from src.infrastructure.persistence.repositories.calendar_repository_impl import SQLAlchemyCalendarEventRepository
from src.infrastructure.persistence.repositories.notification_repository_impl import SQLAlchemyNotificationRepository
from src.infrastructure.persistence.repositories.task_repository_impl import SQLAlchemyTaskRepository
from src.infrastructure.persistence.repositories.user_repository_impl import SQLAlchemyUserRepository
from src.infrastructure.persistence.repositories.user_settings_repository_impl import (
    SQLAlchemyUserSettingsRepository,
)

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _local_time_matches(now_utc: datetime, user_timezone: str, briefing_hour: int, briefing_minute: int) -> bool:
    """Convertit `now_utc` dans le fuseau de l'utilisateur et compare à son heure de briefing."""
    try:
        tz = ZoneInfo(user_timezone)
    except ZoneInfoNotFoundError:
        logger.warning("Fuseau horaire inconnu '%s', repli sur UTC.", user_timezone)
        tz = ZoneInfo("UTC")

    local_now = now_utc.astimezone(tz)
    return local_now.hour == briefing_hour and local_now.minute == briefing_minute


async def _check_and_run_morning_briefings() -> None:
    """Tick exécuté chaque minute : déclenche le briefing pour les utilisateurs dont c'est l'heure locale."""
    now_utc = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        settings_repository = SQLAlchemyUserSettingsRepository(session)
        user_repository = SQLAlchemyUserRepository(session)
        all_settings = await settings_repository.list_all()

        if not all_settings:
            return

        task_repository = SQLAlchemyTaskRepository(session)
        calendar_repository = SQLAlchemyCalendarEventRepository(session)
        notification_repository = SQLAlchemyNotificationRepository(session)
        llm_provider = get_llm_provider()

        use_case = RunMorningBriefingForUserUseCase(
            task_repository, calendar_repository, notification_repository, llm_provider
        )

        for user_settings in all_settings:
            user = await user_repository.get_by_id(user_settings.user_id)
            if user is None:
                continue  # Utilisateur supprimé entre-temps : paramètres orphelins ignorés

            if not _local_time_matches(
                now_utc, user.timezone, user_settings.briefing_time.hour, user_settings.briefing_time.minute
            ):
                continue

            try:
                await use_case.execute(user_settings.user_id)
                logger.info("Briefing matinal généré pour l'utilisateur %s (fuseau %s)", user.id, user.timezone)
            except Exception:
                # Un échec pour un utilisateur ne doit jamais interrompre le traitement des autres
                logger.exception("Échec du briefing matinal pour l'utilisateur %s", user_settings.user_id)


def start_scheduler() -> None:
    """Démarre le scheduler (appelé au démarrage de l'application FastAPI, voir main.py)."""
    scheduler.add_job(
        _check_and_run_morning_briefings,
        trigger="interval",
        minutes=1,
        id="morning_briefing_check",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler W4FO démarré (vérification du briefing matinal chaque minute, par fuseau utilisateur).")


def stop_scheduler() -> None:
    """Arrête proprement le scheduler (appelé à l'arrêt de l'application)."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
