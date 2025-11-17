"""
Core Settings
Configuration globale de l'application
"""
import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml


class Settings:
    """Paramètres globaux de l'application"""

    def __init__(
        self,
        config_path: str = "config/settings.yaml",
        *,
        project_root: Optional[Path] = None,
    ):
        self.config_path = config_path
        self.project_root = (project_root or Path.cwd()).resolve()
        self.logs_dir = self.project_root / "logs"
        self.data_dir = self.project_root / "data"
        self.config_dir = self.project_root / "config"
        
        # Chemins sanctuaire (protégés de toute modification)
        self.sanctuary_paths: List[str] = [
            "data/hive_boxes/**",
            ".env",
            "private/**",
            ".git/**"
        ]
        
        # Configuration IA
        self.ia_engine: str = "ollama"
        self.ia_model_default: str = "qwen2-coder:7b-instruct"
        self.ia_model_alt: str = "deepseek-coder:6.7b"
        
        # Rollback
        self.enable_rollback: bool = True
        
        # Python minimum requis
        self.min_python: str = "3.10"
        
        # Metadata
        self.metadata = {
            "version": "1.0.0",
            "project_name": "aihomecoder"
        }
        
        self._load_config()
    
    def _load_config(self) -> None:
        """Charge la configuration depuis le fichier YAML"""
        if not os.path.exists(self.config_path):
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config:
                    if 'ia' in config:
                        self.ia_engine = config['ia'].get('engine', self.ia_engine)
                        self.ia_model_default = config['ia'].get('model_default', self.ia_model_default)
                        self.ia_model_alt = config['ia'].get('alt_model', self.ia_model_alt)
                    
                    if 'security' in config:
                        self.enable_rollback = config['security'].get('rollback', self.enable_rollback)
                        if 'sanctuary_paths' in config['security']:
                            self.sanctuary_paths = config['security']['sanctuary_paths']
        except Exception as e:
            # Si erreur, on garde les valeurs par défaut
            pass
    
    def ensure_directories(self) -> None:
        """Crée les répertoires nécessaires s'ils n'existent pas"""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)


_SETTINGS_CACHE: Dict[str, Settings] = {}


def get_settings(workspace: Path | str | None = None) -> Settings:
    """Fabrique paresseuse de Settings basée sur le workspace."""

    key = str(Path(workspace).resolve()) if workspace else "__default__"
    if key in _SETTINGS_CACHE:
        return _SETTINGS_CACHE[key]

    root = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    settings = Settings(project_root=root)
    _SETTINGS_CACHE[key] = settings
    return settings


# Instance globale par défaut pour compatibilité rétro
settings = get_settings()
