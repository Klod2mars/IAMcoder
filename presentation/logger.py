"""
Presentation Layer: Logger
Gestion des journaux avec Loguru et Rich
"""
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    from loguru import logger as loguru_logger
    from rich.console import Console
    from rich.logging import RichHandler
    LOGURU_AVAILABLE = True
    RICH_AVAILABLE = True
except ImportError:
    LOGURU_AVAILABLE = False
    RICH_AVAILABLE = False

from core.file_manager import file_manager
from core.guardrail import guardrail
from core.settings import settings


def safe_print(text: str) -> str:
    """Supprime les emojis pour compatibilité console Windows"""
    emoji_map = {
        "🚀": "[START]",
        "✅": "[OK]",
        "❌": "[ERROR]",
        "📝": "[DIFF]",
        "ℹ️": "[INFO]",
        "⚠️": "[WARN]",
    }
    for emoji, replacement in emoji_map.items():
        text = text.replace(emoji, replacement)
    return text


class Logger:
    """
    Gestionnaire de logs avec support pour Rich et Loguru.
    Génère des journaux Markdown pour les sessions.
    """
    
    def __init__(self, session_name: Optional[str] = None):
        self.session_name = session_name or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log_file = settings.logs_dir / f"{self.session_name}.md"
        self.console = Console() if RICH_AVAILABLE else None
        self.log_level = os.getenv("AIHOMECODER_LOG_LEVEL", "INFO").upper()
        self.rotation_bytes = 2 * 1024 * 1024  # 2 Mo
        self.retention_count = 5
        
        # Configure Loguru si disponible
        if LOGURU_AVAILABLE:
            self._setup_loguru()
    
    def _setup_loguru(self) -> None:
        """Configure Loguru avec Rich handler"""
        loguru_logger.remove()  # Enlève le handler par défaut
        
        # Handler Rich pour la console
        if RICH_AVAILABLE:
            loguru_logger.add(
                RichHandler(console=self.console, rich_tracebacks=True),
                format="{message}",
                level=self.log_level,
            )
        
        # Handler fichier Markdown
        loguru_logger.add(
            str(self.log_file),
            format="{message}",
            level="DEBUG",
            rotation=self.rotation_bytes,
            retention=self.retention_count,
        )

    def set_level(self, level: str) -> None:
        """Met à jour le niveau minimum de log affiché dans la console."""

        if not level:
            return

        normalized = str(level).upper()
        if normalized not in {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}:
            normalized = "INFO"

        self.log_level = normalized

        if LOGURU_AVAILABLE:
            self._setup_loguru()
    
    def log_header(self, title: str) -> None:
        """
        Log un en-tête.
        
        Args:
            title: Le titre de l'en-tête
        """
        header = f"# {title}\n"
        self._write_markdown(header)
        if self.console:
            self.console.print(f"\n[bold cyan]{title}[/bold cyan]")
    
    def log_task_start(self, task_name: str) -> None:
        """
        Log le début d'une tâche.
        
        Args:
            task_name: Le nom de la tâche
        """
        content = f"\n## 🚀 Tâche: {task_name}\n\n**Heure:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        self._write_markdown(content)
        if self.console:
            self.console.print(safe_print(f"[bold green]🚀 Tâche:[/bold green] [bold]{task_name}[/bold]"))
    
    def log_task_complete(self, task_name: str, result: str) -> None:
        """
        Log la complétion d'une tâche.
        
        Args:
            task_name: Le nom de la tâche
            result: Le résultat de la tâche
        """
        content = f"\n### ✅ Complété\n\n{result}\n\n**Heure:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        self._write_markdown(content)
        if self.console:
            self.console.print(safe_print(f"[bold green]✅[/bold green] Complété: {task_name}"))
    
    def log_task_fail(self, task_name: str, error: str) -> None:
        """
        Log l'échec d'une tâche.
        
        Args:
            task_name: Le nom de la tâche
            error: Le message d'erreur
        """
        content = f"\n### ❌ Échec\n\n```\n{error}\n```\n\n**Heure:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        self._write_markdown(content)
        if self.console:
            self.console.print(safe_print(f"[bold red]❌ Échec:[/bold red] {task_name}"))
    
    def log_diff(self, diff_result) -> None:
        """
        Log un diff.
        
        Args:
            diff_result: Un objet DiffResult
        """
        content = f"\n### 📝 Diff: {diff_result.file_path}\n\n"
        content += "```diff\n"
        content += diff_result.to_unified_diff()
        content += "```\n\n"
        self._write_markdown(content)
        
        if self.console:
            self.console.print(safe_print(f"[cyan]📝 Diff:[/cyan] {diff_result.file_path}"))
            self.console.print(f"[dim]{diff_result.get_summary()}[/dim]")
    
    def log_info(self, message: str) -> None:
        """
        Log un message informatif.
        
        Args:
            message: Le message
        """
        content = f"ℹ️  {message}\n"
        self._write_markdown(content)
        if self.console:
            self.console.print(safe_print(f"[blue]ℹ️[/blue] {message}"))
    
    def log_warning(self, message: str) -> None:
        """
        Log un avertissement.
        
        Args:
            message: Le message
        """
        content = f"⚠️  {message}\n"
        self._write_markdown(content)
        if self.console:
            self.console.print(safe_print(f"[yellow]⚠️[/yellow] {message}"))
    
    def log_error(self, message: str) -> None:
        """
        Log une erreur.
        
        Args:
            message: Le message
        """
        content = f"❌ Erreur: {message}\n"
        self._write_markdown(content)
        if self.console:
            self.console.print(safe_print(f"[red]❌[/red] Erreur: {message}"))
    
    def _write_markdown(self, content: str) -> None:
        """Écrit dans le fichier Markdown de log"""
        try:
            log_path = str(self.log_file)
            guardrail.check_path(log_path, operation="append")
            file_manager.write_file(log_path, content, append=True)
        except Exception:
            pass  # Ignore les erreurs d'écriture
    
    def get_log_file_path(self) -> str:
        """Retourne le chemin du fichier de log"""
        return str(self.log_file)


# Instance globale du logger
app_logger = Logger()
