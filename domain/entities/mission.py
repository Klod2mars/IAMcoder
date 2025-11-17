"""
Domain Entity: Mission
Représente un ensemble cohérent de tâches à exécuter
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from .task import Task, TaskStatus


class MissionStatus(Enum):
    """État d'une mission"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Mission:
    """
    Une mission regroupe plusieurs tâches à exécuter séquentiellement.
    Elle maintient l'état global de l'exécution.
    """
    name: str
    description: str
    tasks: List[Task] = field(default_factory=list)
    status: MissionStatus = MissionStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validation après initialisation"""
        if not self.name:
            raise ValueError("Mission name cannot be empty")
    
    def add_task(self, task: Task) -> None:
        """Ajoute une tâche à la mission"""
        self.tasks.append(task)
    
    def get_task_by_name(self, name: str) -> Optional[Task]:
        """Récupère une tâche par son nom"""
        for task in self.tasks:
            if task.name == name:
                return task
        return None
    
    def get_completed_tasks(self) -> List[Task]:
        """Retourne les tâches complétées"""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]
    
    def get_failed_tasks(self) -> List[Task]:
        """Retourne les tâches échouées"""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]
    
    def get_progress(self) -> float:
        """Retourne le pourcentage de progression (0-100)"""
        if not self.tasks:
            return 100.0
        completed = len(self.get_completed_tasks())
        return (completed / len(self.tasks)) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la mission en dictionnaire"""
        return {
            "name": self.name,
            "description": self.description,
            "tasks": [task.to_dict() for task in self.tasks],
            "status": self.status.value,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Mission":
        """Crée une mission à partir d'un dictionnaire"""
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        status = MissionStatus(data.get("status", "pending"))
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            tasks=tasks,
            status=status,
            metadata=data.get("metadata", {})
        )
