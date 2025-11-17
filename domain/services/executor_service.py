"""
Domain Service: ExecutorService
Logique métier pour l'exécution des missions et tâches
"""
import logging
from typing import Callable, List, Optional

from core.context_bridge import ContextBridge, context_bridge as shared_context_bridge
from core.guardrail import GuardrailError, enforce_task_restrictions
from domain.entities import Mission, Task, MissionStatus, TaskStatus
from domain.services.task_logic_handler import TaskLogicHandler


logger = logging.getLogger(__name__)


class ExecutorService:
    """
    Service responsable de l'orchestration et de l'exécution des missions.
    Respecte les principes de Clean Architecture en ne dépendant que du domain.
    """
    
    def __init__(self, *, bridge: Optional[ContextBridge] = None):
        self.on_task_started: Optional[Callable[[Task], None]] = None
        self.on_task_completed: Optional[Callable[[Task], None]] = None
        self.on_task_failed: Optional[Callable[[Task, Exception], None]] = None
        self.on_mission_completed: Optional[Callable[[Mission], None]] = None
        self.on_mission_failed: Optional[Callable[[Mission], None]] = None
        self.handler = TaskLogicHandler()
        self.context_bridge = bridge or shared_context_bridge
    
    def execute_mission(
        self,
        mission: Mission,
        *,
        require_confirmation: bool = False,
        confirmer: Optional[Callable[[Task], bool]] = None,
    ) -> bool:
        """
        Exécute une mission complète.

        Args:
            mission: La mission à exécuter
            require_confirmation: Si True, demande une validation avant chaque tâche
            confirmer: Callback optionnel pour valider la poursuite d'une tâche

        Returns:
            True si la mission a réussi, False sinon
        """
        self.context_bridge.reset()
        self.context_bridge.attach_mission(mission)
        self._update_mission_snapshot(mission)

        mission.status = MissionStatus.RUNNING

        self.context_bridge.publish_diagnostic(
            "executor.mission",
            {"event": "started", "mission": mission.name},
        )

        auto_run = self.context_bridge.get_auto_run()
        confirmation_needed = require_confirmation and not auto_run
        confirmation_callback = confirmer or (
            lambda t: input(f"Continuer avec '{t.name}' ? (o/n) ").strip().lower().startswith("o")
        )

        try:
            for task in mission.tasks:
                if confirmation_needed and not confirmation_callback(task):
                    task.status = TaskStatus.CANCELLED
                    mission.status = MissionStatus.CANCELLED
                    self.context_bridge.publish_diagnostic(
                        "executor.mission",
                        {
                            "event": "cancelled",
                            "mission": mission.name,
                            "reason": "user_cancelled",
                            "task": task.name,
                        },
                    )
                    self._update_mission_snapshot(mission)
                    if self.on_mission_failed:
                        self.on_mission_failed(mission)
                    return False

                if not self._execute_task(task, mission):
                    mission.status = MissionStatus.FAILED
                    self.context_bridge.publish_diagnostic(
                        "executor.mission",
                        {"event": "failed", "mission": mission.name, "task": task.name},
                    )
                    self._update_mission_snapshot(mission)
                    if self.on_mission_failed:
                        self.on_mission_failed(mission)
                    return False

            mission.status = MissionStatus.COMPLETED
            self.context_bridge.publish_diagnostic(
                "executor.mission",
                {"event": "completed", "mission": mission.name},
            )
            self._update_mission_snapshot(mission)
            if self.on_mission_completed:
                self.on_mission_completed(mission)
            return True

        except Exception as exc:
            mission.status = MissionStatus.FAILED
            self.context_bridge.publish_diagnostic(
                "executor.mission",
                {"event": "failed", "mission": mission.name, "error": str(exc)},
            )
            self._update_mission_snapshot(mission)
            if self.on_mission_failed:
                self.on_mission_failed(mission)
            return False
    
    def _execute_task(self, task: Task, mission: Mission) -> bool:
        """
        Exécute une tâche individuelle.
        
        Args:
            task: La tâche à exécuter
            mission: La mission parente
            
        Returns:
            True si la tâche a réussi, False sinon
        """
        mode = self.context_bridge.get_mode()

        if (task.task_type or "").lower() == "generic":
            logger.warning(
                "Tâche '%s' sans type explicite (id=%s)",
                task.name,
                getattr(task, "name", None),
            )
        try:
            enforce_task_restrictions(task.goal or "", mode)
        except GuardrailError as exc:
            task.status = TaskStatus.FAILED
            task.error = str(exc)
            self.context_bridge.publish_diagnostic(
                "executor.task",
                {
                    "event": "blocked",
                    "task": task.name,
                    "goal": task.goal,
                    "mode": mode,
                    "error": str(exc),
                },
            )
            self._update_mission_snapshot(mission)
            if self.on_task_failed:
                self.on_task_failed(task, exc)
            return False

        task.status = TaskStatus.IN_PROGRESS
        self.context_bridge.publish_diagnostic(
            "executor.task",
            {"event": "started", "task": task.name, "goal": task.goal, "mode": mode},
        )
        self._update_mission_snapshot(mission)
        
        if self.on_task_started:
            self.on_task_started(task)
        
        try:
            # L'exécution réelle doit être déléguée à une couche supérieure
            # qui injectera les dépendances nécessaires (IA, fichiers, etc.)
            result = self._execute_task_logic(task, mission)
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            self.context_bridge.publish_diagnostic(
                "executor.task",
                {"event": "completed", "task": task.name, "result": result},
            )
            self._update_mission_snapshot(mission)
            
            if self.on_task_completed:
                self.on_task_completed(task)
            
            return True
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            self.context_bridge.publish_diagnostic(
                "executor.task",
                {"event": "failed", "task": task.name, "error": str(e)},
            )
            self._update_mission_snapshot(mission)
            
            if self.on_task_failed:
                self.on_task_failed(task, e)
            
            return False
    
    def _execute_task_logic(self, task: Task, mission: Mission) -> str:
        """
        Logique d'exécution d'une tâche.
        Cette méthode doit être surchargée ou injectée avec de la logique concrète.

        Args:
            task: La tâche à exécuter
            mission: La mission parente

        Returns:
            Le résultat de l'exécution
        """
        try:
            return self.handler.execute(task, mission)
        except Exception as exc:  # pragma: no cover - logged via return message
            return f"[ERROR] Erreur dans la logique de tâche : {exc}"
    
    def validate_mission(self, mission: Mission) -> List[str]:
        """
        Valide une mission avant son exécution.
        
        Args:
            mission: La mission à valider
            
        Returns:
            Liste des erreurs de validation (vide si valide)
        """
        errors = []
        
        if not mission.name:
            errors.append("Mission name is required")
        
        if not mission.tasks:
            errors.append("Mission must contain at least one task")
        
        for i, task in enumerate(mission.tasks):
            if not task.name:
                errors.append(f"Task {i+1} has no name")
            if not task.goal:
                errors.append(f"Task '{task.name}' has no goal")
        
        return errors

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _update_mission_snapshot(self, mission: Mission) -> None:
        """Expose a snapshot of the bridge state inside mission metadata."""

        mission.metadata["context_bridge"] = self.context_bridge.export_snapshot()
