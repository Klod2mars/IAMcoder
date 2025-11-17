"""
Core Guardrail
Protection des chemins sanctuaires
"""
import fnmatch
from pathlib import Path
from typing import List
from .settings import settings


class GuardrailError(Exception):
    """Exception levée lors d'une violation de guardrail"""
    pass


class Guardrail:
    """
    Système de protection pour empêcher la modification de chemins critiques.
    """
    
    def __init__(self, sanctuary_paths: List[str] = None):
        self.sanctuary_paths = sanctuary_paths or settings.sanctuary_paths
    
    def is_sanctuary_path(self, file_path: str) -> bool:
        """
        Vérifie si un chemin est protégé (sanctuaire).
        
        Args:
            file_path: Le chemin à vérifier
            
        Returns:
            True si le chemin est protégé, False sinon
        """
        file_path_str = str(file_path).replace('\\', '/')
        
        for pattern in self.sanctuary_paths:
            # Conversion du pattern pour fnmatch
            normalized_pattern = pattern.replace('\\', '/')
            if fnmatch.fnmatch(file_path_str, normalized_pattern):
                return True
        
        return False
    
    def check_path(self, file_path: str, operation: str = "modify") -> None:
        """
        Vérifie qu'un chemin n'est pas protégé avant une opération.
        
        Args:
            file_path: Le chemin à vérifier
            operation: L'opération prévue (read, write, modify, delete)
            
        Raises:
            GuardrailError: Si le chemin est protégé
        """
        if self.is_sanctuary_path(file_path):
            raise GuardrailError(
                f"Operation '{operation}' on sanctuary path '{file_path}' is forbidden. "
                f"Protected pattern: {self._find_matching_pattern(file_path)}"
            )
    
    def _find_matching_pattern(self, file_path: str) -> str:
        """Trouve le pattern qui correspond au chemin"""
        file_path_str = str(file_path).replace('\\', '/')
        
        for pattern in self.sanctuary_paths:
            normalized_pattern = pattern.replace('\\', '/')
            if fnmatch.fnmatch(file_path_str, normalized_pattern):
                return pattern
        
        return "unknown"
    
    def filter_allowed_paths(self, paths: List[str]) -> List[str]:
        """
        Filtre une liste de chemins pour ne garder que ceux autorisés.
        
        Args:
            paths: Liste des chemins à filtrer
            
        Returns:
            Liste des chemins autorisés
        """
        return [p for p in paths if not self.is_sanctuary_path(p)]


# Instance globale du guardrail
guardrail = Guardrail()


def _get_current_mode_from_config() -> str:
    """Lit le mode courant depuis config/settings.yaml si disponible."""
    try:
        import yaml  # local import pour éviter dépendances globales ici
        from pathlib import Path as _Path
        cfg_path = _Path("config") / "settings.yaml"
        if not cfg_path.exists():
            return "write_enabled"
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        defaults = data.get("defaults", {})
        return defaults.get("mode", "write_enabled")
    except Exception:
        return "write_enabled"


def enforce_task_restrictions(task_text: str, mode: str | None = None) -> None:
    """
    Enforce read_only restrictions on task text.
    If mode is read_only and task contains write/delete/move, raise GuardrailError.
    """
    active_mode = mode or _get_current_mode_from_config()
    if str(active_mode).lower() == "read_only":
        lowered = (task_text or "").lower()
        for keyword in ("write", "delete", "move"):
            if keyword in lowered:
                raise GuardrailError("Forbidden in read_only mode")