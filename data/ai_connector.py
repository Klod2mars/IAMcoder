"""
Data Layer: AI Connector
Interface avec Ollama pour les modèles IA locaux
"""
import json
import subprocess
from typing import List, Dict, Any, Optional
from core.settings import settings


class AIConnectorError(Exception):
    """Exception pour les erreurs de connexion IA"""
    pass


class AIConnector:
    """
    Connecteur vers Ollama pour l'exécution de modèles IA locaux.
    Supporte Qwen et DeepSeek.
    """
    
    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.ia_model_default
        self.engine = settings.ia_engine
        self.ollama_available = self._check_ollama_availability()
    
    def _check_ollama_availability(self) -> bool:
        """Vérifie si Ollama est disponible"""
        if self.engine != "ollama":
            return False
        
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                check=False,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        Génère une réponse à partir d'un prompt.
        
        Args:
            prompt: Le prompt utilisateur
            system_prompt: Le prompt système (instructions de rôle)
            temperature: La température pour la génération
            max_tokens: Nombre maximum de tokens à générer
            
        Returns:
            La réponse générée
            
        Raises:
            AIConnectorError: Si la génération échoue
        """
        if not self.ollama_available:
            raise AIConnectorError(
                "Ollama is not available. Please install and start Ollama."
            )
        
        # Construction du message pour Ollama
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        try:
            # Appel à Ollama via l'API
            result = subprocess.run(
                [
                    "ollama", "run",
                    self.model,
                    json.dumps(messages)
                ],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                # Fallback: essayer sans JSON
                result = subprocess.run(
                    [
                        "ollama", "run",
                        self.model,
                        prompt
                    ],
                    capture_output=True,
                    text=True,
                    check=False
                )
            
            if result.returncode != 0:
                raise AIConnectorError(
                    f"Ollama command failed: {result.stderr}"
                )
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired as e:
            raise AIConnectorError("Ollama request timed out") from e
        except Exception as e:
            raise AIConnectorError(f"Failed to generate response: {str(e)}") from e
    
    def list_available_models(self) -> List[str]:
        """
        Liste les modèles disponibles dans Ollama.
        
        Returns:
            Liste des noms de modèles
        """
        if not self.ollama_available:
            return []
        
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Parse la sortie
            models = []
            for line in result.stdout.splitlines()[1:]:  # Ignorer la ligne d'en-tête
                if line.strip():
                    model_name = line.split()[0]
                    models.append(model_name)
            
            return models
            
        except Exception:
            return []
    
    def check_model_available(self, model_name: str) -> bool:
        """
        Vérifie si un modèle est disponible.
        
        Args:
            model_name: Le nom du modèle
            
        Returns:
            True si le modèle est disponible
        """
        available_models = self.list_available_models()
        return model_name in available_models
    
    def switch_model(self, model_name: str) -> None:
        """
        Change de modèle IA.
        
        Args:
            model_name: Le nom du nouveau modèle
            
        Raises:
            AIConnectorError: Si le modèle n'est pas disponible
        """
        if not self.check_model_available(model_name):
            raise AIConnectorError(
                f"Model '{model_name}' is not available. "
                f"Available models: {', '.join(self.list_available_models())}"
            )
        
        self.model = model_name


# Instance globale du connecteur IA
ai_connector = AIConnector()
