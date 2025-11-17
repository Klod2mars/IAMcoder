"""
Data Layer: Diff Engine
Génération et application de diffs avec rollback Git
"""
import difflib
from pathlib import Path
from typing import Optional, List, Tuple
import subprocess
import tempfile
from domain.entities import DiffResult, DiffLine, DiffType
from core.file_manager import file_manager
from core.settings import settings


class DiffEngineError(Exception):
    """Exception pour les erreurs de diff engine"""
    pass


class DiffEngine:
    """
    Moteur de génération et d'application de diffs.
    Supporte le rollback via GitPython.
    """
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.git_available = self._check_git_availability()
    
    def _check_git_availability(self) -> bool:
        """Vérifie si Git est disponible"""
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True,
                cwd=self.project_root
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def compute_diff(
        self,
        old_content: str,
        new_content: str,
        file_path: str
    ) -> DiffResult:
        """
        Calcule le diff entre deux versions d'un fichier.
        
        Args:
            old_content: L'ancien contenu
            new_content: Le nouveau contenu
            file_path: Le chemin du fichier
            
        Returns:
            Un DiffResult contenant les différences
        """
        result = DiffResult(file_path=file_path)
        
        if old_content == new_content:
            return result
        
        # Utilisation de difflib pour calculer les différences
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f'a/{file_path}',
            tofile=f'b/{file_path}',
            lineterm=''
        )
        
        # Analyse des différences ligne par ligne
        line_num = 1
        old_idx = 0
        new_idx = 0
        
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                line_num += (i2 - i1)
                old_idx = i2
                new_idx = j2
            elif tag == 'delete':
                for i in range(i1, i2):
                    result.add_diff_line(DiffLine(
                        line_number=line_num,
                        old_content=old_lines[i].rstrip(),
                        new_content="",
                        diff_type=DiffType.REMOVED
                    ))
                    line_num += 1
                old_idx = i2
            elif tag == 'insert':
                for j in range(j1, j2):
                    result.add_diff_line(DiffLine(
                        line_number=line_num,
                        old_content="",
                        new_content=new_lines[j].rstrip(),
                        diff_type=DiffType.ADDED
                    ))
                    line_num += 1
                new_idx = j2
            elif tag == 'replace':
                # Lignes modifiées
                max_len = max(i2 - i1, j2 - j1)
                for k in range(max_len):
                    old_line = old_lines[i1 + k] if (i1 + k) < i2 else ""
                    new_line = new_lines[j1 + k] if (j1 + k) < j2 else ""
                    result.add_diff_line(DiffLine(
                        line_number=line_num,
                        old_content=old_line.rstrip() if old_line else "",
                        new_content=new_line.rstrip() if new_line else "",
                        diff_type=DiffType.MODIFIED
                    ))
                    line_num += 1
                old_idx = i2
                new_idx = j2
        
        return result
    
    def compute_file_diff(self, file_path: str, new_content: str) -> DiffResult:
        """
        Calcule le diff d'un fichier existant avec un nouveau contenu.
        
        Args:
            file_path: Le chemin du fichier
            new_content: Le nouveau contenu
            
        Returns:
            Un DiffResult contenant les différences
        """
        old_content = ""
        if file_manager.file_exists(file_path):
            old_content = file_manager.read_file(file_path)
        
        return self.compute_diff(old_content, new_content, file_path)
    
    def create_rollback_checkpoint(self) -> Optional[str]:
        """
        Crée un point de rollback Git.
        
        Returns:
            Le hash du commit ou None si Git n'est pas disponible
        """
        if not self.git_available or not settings.enable_rollback:
            return None
        
        try:
            # Vérifie si on est dans un repo Git
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=False
            )
            
            if result.returncode != 0:
                return None
            
            # Crée un commit de checkpoint
            commit_msg = f"aihomecoder checkpoint: {Path.cwd().name}"
            
            subprocess.run(
                ["git", "add", "-A"],
                capture_output=True,
                check=False,
                cwd=self.project_root
            )
            
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=False
            )
            
            if result.returncode == 0:
                # Récupère le hash du commit
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=self.project_root
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            
            return None
            
        except Exception as e:
            return None
    
    def rollback_to_checkpoint(self, checkpoint_hash: str) -> bool:
        """
        Effectue un rollback vers un checkpoint.
        
        Args:
            checkpoint_hash: Le hash du commit de checkpoint
            
        Returns:
            True si le rollback a réussi, False sinon
        """
        if not self.git_available:
            return False
        
        try:
            result = subprocess.run(
                ["git", "reset", "--hard", checkpoint_hash],
                capture_output=True,
                check=False,
                cwd=self.project_root
            )
            
            return result.returncode == 0
            
        except Exception as e:
            return False


# Instance globale du moteur de diff
diff_engine = DiffEngine()
