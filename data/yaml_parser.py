"""
Data Layer: YAML Parser
Lecture et validation des fichiers .yalm
"""
import yaml
from pathlib import Path
from typing import Dict, Any, List
from domain.entities import Mission, Task
from core.file_manager import file_manager, FileManagerError


class YAMLParserError(Exception):
    """Exception pour les erreurs de parsing YAML"""
    pass


class YAMLParser:
    """
    Parseur pour les fichiers .yalm (YAML-based task definitions).
    """
    
    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse un fichier .yalm et retourne son contenu.
        
        Args:
            file_path: Le chemin du fichier .yalm
            
        Returns:
            Le contenu parsé du fichier
            
        Raises:
            YAMLParserError: Si le fichier ne peut pas être parsé
        """
        try:
            content = file_manager.read_file(file_path)
            return self.parse_content(content)
        except FileManagerError as e:
            raise YAMLParserError(f"Failed to read YAML file: {str(e)}")
    
    def parse_content(self, content: str) -> Dict[str, Any]:
        """
        Parse du contenu YAML.
        
        Args:
            content: Le contenu YAML à parser
            
        Returns:
            Le contenu parsé
            
        Raises:
            YAMLParserError: Si le contenu ne peut pas être parsé
        """
        try:
            return yaml.safe_load(content) or {}
        except yaml.YAMLError as e:
            raise YAMLParserError(f"Invalid YAML syntax: {str(e)}")
    
    def create_mission_from_yaml(self, file_path: str) -> Mission:
        """
        Crée une mission à partir d'un fichier .yalm.
        
        Args:
            file_path: Le chemin du fichier .yalm
            
        Returns:
            Une instance de Mission
            
        Raises:
            YAMLParserError: Si le fichier ne peut pas être parsé ou est invalide
        """
        try:
            data = self.parse_file(file_path)
            return self._build_mission(data)
        except Exception as e:
            raise YAMLParserError(f"Failed to create mission from {file_path}: {str(e)}")
    
    def _build_mission(self, data: Dict[str, Any]) -> Mission:
        """
        Construit une mission à partir des données parsées.
        
        Args:
            data: Les données parsées du YAML
            
        Returns:
            Une instance de Mission
            
        Raises:
            YAMLParserError: Si les données sont invalides
        """
        # Extraction du nom de la mission (support formats alternatifs)
        meta = data.get("meta", {})
        mission_name = meta.get("project_name") or meta.get("mission_id") or "Unnamed Mission"
        
        # Extraction de la description
        description = meta.get("description", "")
        if not description:
            description = data.get("description", "")
        
        # Création de la mission
        mission = Mission(
            name=mission_name,
            description=description,
            metadata={
                "version": meta.get("version", "1.0.0"),
                "author": meta.get("author", ""),
                "architecture": meta.get("architecture", ""),
                "language": meta.get("language", ""),
                # Préserver la section meta complète pour accès à raw_output et autres champs
                "meta": meta,
                # Préserver d'autres sections potentielles pour usage ultérieur
                "context": data.get("context"),
                "outputs": data.get("outputs"),
                "post_actions": data.get("post_actions")
            }
        )
        
        # Extraction des tâches (supporte dicts et chaînes)
        tasks_data = data.get("tasks", [])
        for index, task_data in enumerate(tasks_data, start=1):
            if isinstance(task_data, dict):
                task_id = task_data.get("id")
                task_type = (
                    task_data.get("type")
                    or task_data.get("task_type")
                    or task_id
                    or "generic"
                )
                task_name = task_data.get("name") or task_id or f"task_{index}"

                raw_parameters = task_data.get("parameters")
                parameters = dict(raw_parameters) if isinstance(raw_parameters, dict) else {}

                if "output" in task_data and task_data.get("output") is not None:
                    parameters.setdefault("output", task_data.get("output"))

                task = Task(
                    name=task_name,
                    goal=task_data.get("goal", ""),
                    task_type=task_type,
                    parameters=parameters
                )
                mission.add_task(task)
            elif isinstance(task_data, str):
                # Mapper une instruction textuelle à une tâche générique
                task = Task(
                    name=f"task_{index}",
                    goal=task_data.strip(),
                    task_type="instruction",
                    parameters={}
                )
                mission.add_task(task)
        
        return mission
    
    def validate_yaml_structure(self, data: Dict[str, Any]) -> List[str]:
        """
        Valide la structure d'un fichier .yalm.
        
        Args:
            data: Les données parsées
            
        Returns:
            Liste des erreurs de validation (vide si valide)
        """
        errors = []
        
        # Vérification des sections obligatoires
        if "meta" not in data:
            errors.append("Missing 'meta' section")
        else:
            meta = data["meta"]
            # Accepte 'project_name' ou 'mission_id'
            if "project_name" not in meta and "mission_id" not in meta:
                errors.append("Missing 'meta.project_name' or 'meta.mission_id'")
        
        if "tasks" not in data:
            errors.append("Missing 'tasks' section")
        
        # Vérification des tâches
        tasks = data.get("tasks", [])
        if not isinstance(tasks, list):
            errors.append("'tasks' must be a list")
        else:
            for i, task in enumerate(tasks):
                # Autorise soit dict complet, soit chaîne simple
                if isinstance(task, dict):
                    if "goal" not in task and "name" not in task:
                        errors.append(f"Task {i+1} must have at least 'goal' or 'name'")
                elif isinstance(task, str):
                    if not task.strip():
                        errors.append(f"Task {i+1} string is empty")
                else:
                    errors.append(f"Task {i+1} must be a dictionary or a string")
        
        return errors


# Instance globale du parser
yaml_parser = YAMLParser()
