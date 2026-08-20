"""
Registre centralisé des outils exposés à l'agent W4FO (function calling Mistral).

Avant cette étape, chaque domaine (Task, Calendar) exposait ses outils
directement à un node d'agent dédié (`task_agent_node`, `calendar_agent_node`),
qui ne connaissait QUE ses propres outils. L'agent ne pouvait donc jamais
combiner un outil Task et un outil Calendar dans le même tour de raisonnement.

Ce module introduit un registre unique, agnostique du domaine : chaque module
d'outils (task_tools, calendar_tools, et à terme MemoryTools, WhatsAppTools,
NotificationTools, AppTools, VoiceTools...) s'y enregistre via un `ToolSpec`,
et l'agent unifié (`nodes/agent_node.py`) reçoit TOUJOURS l'intégralité du
registre. C'est ce qui permet à un seul tour de raisonnement de sélectionner
plusieurs outils, potentiellement de domaines différents.

Ajouter un nouveau domaine d'outils ne nécessite de toucher ni à la boucle
agentique, ni au graphe : uniquement d'enregistrer de nouveaux `ToolSpec`
(cf. `tool_registry_factory.py`).
"""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

# Un executor reçoit toujours (arguments: dict, user_id: UUID) en kwargs et
# retourne un résultat structuré sérialisable (dict). Les dépendances propres
# à un domaine (repository, provider...) doivent être pré-liées via
# `functools.partial` au moment de l'enregistrement (voir tool_registry_factory.py) :
# cela garde l'interface de l'executor strictement identique quel que soit le domaine.
ToolExecutor = Callable[..., Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class ToolSpec:
    """Spécification complète d'un outil exposé à l'agent."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema des arguments (format function calling Mistral)
    executor: ToolExecutor
    sensitive: bool = False  # Niveau de sensibilité : True => confirmation utilisateur requise

    def as_mistral_definition(self) -> dict[str, Any]:
        """Sérialise la spec au format `tools=[...]` attendu par l'API Mistral."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """
    Registre extensible d'outils, construit à la demande pour chaque tour de
    conversation (car certains outils ont besoin d'une session DB par requête —
    voir `tool_registry_factory.build_tool_registry`).
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Outil déjà enregistré dans le registre : {spec.name}")
        self._tools[spec.name] = spec

    def register_many(self, specs: list[ToolSpec]) -> None:
        for spec in specs:
            self.register(spec)

    def is_registered(self, name: str) -> bool:
        return name in self._tools

    def is_sensitive(self, name: str) -> bool:
        return self._tools[name].sensitive

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"Outil inconnu du registre : {name}")
        return self._tools[name]

    def definitions(self) -> list[dict[str, Any]]:
        """Toutes les définitions au format Mistral, à passer tel quel à `LLMProvider.generate(tools=...)`."""
        return [spec.as_mistral_definition() for spec in self._tools.values()]

    async def execute(self, name: str, *, arguments: dict[str, Any], user_id: Any) -> dict[str, Any]:
        """
        Exécute un outil par son nom et retourne TOUJOURS un résultat structuré,
        même en cas d'erreur (§ ERREURS du brief) : une erreur d'outil ne doit
        jamais faire planter l'agent, elle doit lui être retournée comme une
        observation exploitable pour décider de la suite.
        """
        if not self.is_registered(name):
            return {"success": False, "tool": name, "error": f"Outil inconnu : {name}"}

        spec = self._tools[name]
        try:
            result = await spec.executor(arguments=arguments, user_id=user_id)
        except Exception as exc:  # noqa: BLE001 - conversion volontaire de TOUTE exception outil
            return {"success": False, "tool": name, "error": str(exc)}

        if isinstance(result, dict) and "success" in result:
            return result
        return {"success": True, "tool": name, "data": result}
