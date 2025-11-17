"""
Domain Entity: Task
Représente une tâche individuelle issue d'un fichier .yalm
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum


class TaskStatus(Enum):
    """État d'une tâche"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """
    Une tâche représente une action unique à exécuter.
    Elle contient toutes les informations nécessaires pour son exécution.
    """
    name: str
    goal: str
    task_type: str = "generic"
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        """Validation après initialisation"""
        if not self.name:
            raise ValueError("Task name cannot be empty")
        if not self.goal:
            raise ValueError("Task goal cannot be empty")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la tâche en dictionnaire"""
        return {
            "name": self.name,
            "goal": self.goal,
            "task_type": self.task_type,
            "parameters": self.parameters,
            "status": self.status.value,
            "result": self.result,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Crée une tâche à partir d'un dictionnaire"""
        status = TaskStatus(data.get("status", "pending"))
        return cls(
            name=data["name"],
            goal=data["goal"],
            task_type=data.get("task_type", "generic"),
            parameters=data.get("parameters", {}),
            status=status,
            result=data.get("result"),
            error=data.get("error")
        )
