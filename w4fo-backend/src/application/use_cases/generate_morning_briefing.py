"""
Use case : génération du briefing matinal (réveil intelligent).

Agrège les informations décrites au §2 du document d'architecture (heure, date,
météo, rendez-vous, tâches, rappels) et produit un texte de briefing naturel
via le LLM, prêt à être vocalisé. Les e-mails/notifications importants (Gmail)
sont prévus en V3 et ne sont pas encore agrégés ici.

TODO (V3) : intégrer la météo (weather_client à créer dans infrastructure/external_apis/)
et les e-mails importants (Gmail) dans les `structured_data` ci-dessous.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from src.application.use_cases.manage_calendar.list_events import ListCalendarEventsUseCase
from src.application.use_cases.manage_tasks.list_tasks import ListTasksUseCase
from src.domain.repositories.calendar_repository import CalendarEventRepository
from src.domain.repositories.task_repository import TaskRepository
from src.domain.services.llm_provider import LLMProvider
from src.domain.value_objects.priority import TaskStatus

BRIEFING_SYSTEM_PROMPT = """Tu es W4FO, l'assistant personnel qui réveille l'utilisateur chaque matin.
À partir des données structurées fournies (date, événements du jour, tâches en attente),
rédige un briefing matinal chaleureux et concis, adapté à une restitution vocale (phrases
courtes, ton motivant, pas de liste à puces). Commence par saluer l'utilisateur et annoncer
la date. Mentionne les rendez-vous du jour puis les tâches prioritaires. Si rien n'est prévu,
dis-le simplement de façon positive.
"""


@dataclass
class MorningBriefingResultDTO:
    briefing_text: str
    event_count: int
    task_count: int


class GenerateMorningBriefingUseCase:
    def __init__(
        self,
        task_repository: TaskRepository,
        calendar_repository: CalendarEventRepository,
        llm_provider: LLMProvider,
    ) -> None:
        self._task_repository = task_repository
        self._calendar_repository = calendar_repository
        self._llm_provider = llm_provider

    async def execute(self, user_id: UUID) -> MorningBriefingResultDTO:
        now = datetime.utcnow()
        end_of_day = now.replace(hour=23, minute=59, second=59)

        calendar_use_case = ListCalendarEventsUseCase(self._calendar_repository)
        today_events = await calendar_use_case.execute(user_id, start_range=now, end_range=end_of_day)

        tasks_use_case = ListTasksUseCase(self._task_repository)
        pending_tasks = await tasks_use_case.execute(user_id, status=TaskStatus.TODO)
        # Tâches en retard ou dues aujourd'hui, priorisées en tête du briefing
        urgent_tasks = [t for t in pending_tasks if t.due_date and t.due_date <= end_of_day]

        structured_data = {
            "date": now.strftime("%A %d %B %Y"),
            "events": [{"title": e.title, "start_time": e.start_time.strftime("%H:%M")} for e in today_events],
            "urgent_tasks": [{"title": t.title, "priority": t.priority.value} for t in urgent_tasks],
            "total_pending_tasks": len(pending_tasks),
        }

        result = await self._llm_provider.generate(
            messages=[
                {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
                {"role": "user", "content": f"Données du jour : {structured_data}"},
            ]
        )

        return MorningBriefingResultDTO(
            briefing_text=result["content"],
            event_count=len(today_events),
            task_count=len(urgent_tasks),
        )
