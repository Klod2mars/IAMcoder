"""
Core File Manager
Gestion sécurisée des fichiers avec guardrail
"""
from pathlib import Path
from typing import Optional, List
from .guardrail import guardrail, GuardrailError


class FileManagerError(Exception):
    """Exception générique pour les erreurs de FileManager"""
    pass


class FileManager:
    """
    Gestionnaire de fichiers avec protection des zones sanctuaires.
    """
    
    def read_file(self, file_path: str) -> str:
        """
        Lit le contenu d'un fichier.
        
        Args:
            file_path: Le chemin du fichier à lire
            
        Returns:
            Le contenu du fichier
            
        Raises:
            FileManagerError: Si le fichier ne peut pas être lu
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise FileManagerError(f"File not found: {file_path}")
            
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
                
        except PermissionError as e:
            raise FileManagerError(f"Permission denied for file: {file_path}") from e
        except Exception as e:
            raise FileManagerError(f"Error reading file {file_path}: {str(e)}") from e
    
    def write_file(self, file_path: str, content: str, *, append: bool = False) -> None:
        """
        Écrit du contenu dans un fichier avec protection guardrail.
        
        Args:
            file_path: Le chemin du fichier à écrire
            content: Le contenu à écrire
            append: Ajoute le contenu en fin de fichier au lieu d'écraser
            
        Raises:
            FileManagerError: Si le fichier ne peut pas être écrit
            GuardrailError: Si le chemin est protégé
        """
        # Vérification guardrail
        operation = "append" if append else "write"
        guardrail.check_path(file_path, operation=operation)
        
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = 'a' if append else 'w'

            with open(path, mode, encoding='utf-8') as f:
                f.write(content)
                
        except PermissionError as e:
            raise FileManagerError(f"Permission denied for file: {file_path}") from e
        except Exception as e:
            raise FileManagerError(f"Error writing file {file_path}: {str(e)}") from e
    
    def file_exists(self, file_path: str) -> bool:
        """
        Vérifie si un fichier existe.
        
        Args:
            file_path: Le chemin du fichier
            
        Returns:
            True si le fichier existe, False sinon
        """
        return Path(file_path).exists()
    
    def list_files(self, directory: str, pattern: str = "*", recursive: bool = False) -> List[str]:
        """
        Liste les fichiers d'un répertoire.
        
        Args:
            directory: Le répertoire à explorer
            pattern: Pattern de filtrage (ex: "*.py")
            recursive: Explorer récursivement
            
        Returns:
            Liste des chemins de fichiers trouvés
        """
        try:
            path = Path(directory)
            if not path.exists():
                return []
            
            if recursive:
                files = list(path.rglob(pattern))
            else:
                files = list(path.glob(pattern))
            
            # Filtrage des chemins protégés
            file_paths = [str(f) for f in files if f.is_file()]
            allowed_paths = guardrail.filter_allowed_paths(file_paths)
            
            return sorted(allowed_paths)
            
        except Exception as e:
            raise FileManagerError(f"Error listing files in {directory}: {str(e)}") from e


# Instance globale du gestionnaire de fichiers
file_manager = FileManager()
