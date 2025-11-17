"""
Domain Entity: DiffResult
Représente le résultat d'une comparaison de fichiers
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class DiffType(Enum):
    """Type de modification"""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class DiffLine:
    """Représente une ligne de différence"""
    line_number: int
    old_content: str
    new_content: str
    diff_type: DiffType
    context: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la ligne en dictionnaire"""
        return {
            "line_number": self.line_number,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "diff_type": self.diff_type.value,
            "context": self.context
        }


@dataclass
class DiffResult:
    """
    Représente le résultat complet d'une comparaison entre deux fichiers.
    Peut être utilisé pour afficher un diff ou appliquer un patch.
    """
    file_path: str
    diff_lines: List[DiffLine] = field(default_factory=list)
    added_lines: int = 0
    removed_lines: int = 0
    modified_lines: int = 0
    
    def add_diff_line(self, line: DiffLine) -> None:
        """Ajoute une ligne de différence"""
        self.diff_lines.append(line)
        if line.diff_type == DiffType.ADDED:
            self.added_lines += 1
        elif line.diff_type == DiffType.REMOVED:
            self.removed_lines += 1
        elif line.diff_type == DiffType.MODIFIED:
            self.modified_lines += 1
    
    def get_summary(self) -> str:
        """Retourne un résumé du diff"""
        total_changes = self.added_lines + self.removed_lines + self.modified_lines
        if total_changes == 0:
            return f"{self.file_path}: No changes"
        return f"{self.file_path}: +{self.added_lines} -{self.removed_lines} ~{self.modified_lines}"
    
    def to_unified_diff(self) -> str:
        """Génère un diff unifié au format standard"""
        if not self.diff_lines:
            return f"No changes in {self.file_path}\n"
        
        lines = [f"--- a/{self.file_path}"]
        lines.append(f"+++ b/{self.file_path}")
        lines.append("@@")
        
        for diff_line in self.diff_lines:
            prefix = self._get_diff_prefix(diff_line.diff_type)
            if diff_line.diff_type in [DiffType.REMOVED, DiffType.MODIFIED]:
                lines.append(f"{prefix} {diff_line.old_content}")
            if diff_line.diff_type in [DiffType.ADDED, DiffType.MODIFIED]:
                lines.append(f"{prefix}+{diff_line.new_content}")
        
        return "\n".join(lines) + "\n"
    
    @staticmethod
    def _get_diff_prefix(diff_type: DiffType) -> str:
        """Retourne le préfixe pour le format unifié"""
        if diff_type == DiffType.ADDED:
            return "+"
        elif diff_type == DiffType.REMOVED:
            return "-"
        elif diff_type == DiffType.MODIFIED:
            return "-"
        return " "
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le résultat en dictionnaire"""
        return {
            "file_path": self.file_path,
            "diff_lines": [line.to_dict() for line in self.diff_lines],
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
            "modified_lines": self.modified_lines
        }
