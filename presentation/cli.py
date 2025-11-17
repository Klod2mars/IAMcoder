"""
Presentation Layer: CLI
Interface en ligne de commande principale
"""
import sys
from pathlib import Path
from typing import Optional

try:
    import typer
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    TYPER_AVAILABLE = True
    RICH_AVAILABLE = True
except ImportError:
    TYPER_AVAILABLE = False
    RICH_AVAILABLE = False

from domain.entities import Mission, Task, TaskStatus
from domain.services import ExecutorService
from data.yaml_parser import yaml_parser, YAMLParserError
from data.diff_engine import diff_engine, DiffEngineError
from data.context_index import ContextIndexError
from data.ai_connector import ai_connector, AIConnectorError
from core.guardrail import GuardrailError
from core.file_manager import FileManagerError
import core.settings as settings_module
from core.workspace_store import get_workspace_store
from presentation.logger import Logger
from presentation.ui_diff_view import ui_diff_view
from modules.output_handler import output_handler, OutputHandlerError


REPO_ROOT = Path(__file__).resolve().parent.parent


if TYPER_AVAILABLE:
    app = typer.Typer(help="AIHomeCoder - Moteur local de co-edition de code")
else:
    app = None
console = Console() if RICH_AVAILABLE else None


def init_app(workspace: Optional[Path] = None):
    """Initialise l'application avec les ressources nécessaires"""
    active_settings = settings_module.get_settings(workspace)
    active_settings.ensure_directories()
    return active_settings


def safe_print(text: str):
    """Affiche du texte sans emoji pour compatibilité Windows"""
    # Remplacer les emojis par des alternatives ASCII
    emoji_map = {
        "📄": "[FILE]",
        "❌": "[ERROR]",
        "✅": "[OK]",
        "⚠️": "[WARN]",
        "🚀": "[START]",
        "📝": "[DIFF]",
        "📊": "[SUMMARY]",
        "ℹ️": "[INFO]",
        "✓": "[OK]",
        "🔄": "[ACTION]",
        "📄": "[FILE]",
        "→": "->",
    }
    for emoji, replacement in emoji_map.items():
        text = text.replace(emoji, replacement)
    return text


# Définir les fonctions de commande seulement si typer est disponible
if TYPER_AVAILABLE:
    @app.command()
    def run(
        mission_file: str = typer.Argument(..., help="Chemin vers le fichier .yalm"),
        model: Optional[str] = typer.Option(None, "--model", "-m", help="Modèle IA à utiliser"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Mode simulation sans modifications"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Mode verbeux"),
        workspace: Optional[Path] = typer.Option(
            None,
            "--workspace",
            help="Chemin absolu du workspace ciblé",
        ),
        auto_run: Optional[bool] = typer.Option(
            None,
            "--auto-run/--no-auto-run",
            help="Active ou désactive la confirmation interactive entre les tâches",
        ),
    ):
        """
        Exécute une mission définie dans un fichier .yalm
        """
        store = get_workspace_store()
        invalid_cached_workspace = False

        if workspace is not None:
            resolved_workspace = workspace.expanduser().resolve()
            if not resolved_workspace.exists() or not resolved_workspace.is_dir():
                typer.echo("[ERROR] Workspace invalide : le chemin doit exister et être un répertoire.")
                raise typer.Exit(code=1)
        else:
            last_workspace = store.get_last_workspace()
            if last_workspace:
                candidate = Path(last_workspace)
                if candidate.exists() and candidate.is_dir():
                    resolved_workspace = candidate
                else:
                    invalid_cached_workspace = True
                    resolved_workspace = REPO_ROOT
            else:
                resolved_workspace = REPO_ROOT

        active_settings = init_app(resolved_workspace)

        store.set_workspace(
            str(resolved_workspace),
            auto_run=auto_run if auto_run is not None else None,
        )
        effective_auto_run = store.get_auto_run()

        if console:
            console.print(
                safe_print(
                    f"[blue]ℹ️[/blue] Workspace actif: {resolved_workspace} | Auto-run: {'ON' if effective_auto_run else 'OFF'}"
                )
            )
        
        # Logger
        logger = Logger()
        logger.log_header("AIHomeCoder - Exécution de mission")
        logger.log_info(f"Mission file: {mission_file}")
        logger.log_info(f"Workspace: {resolved_workspace}")
        logger.log_info(f"Mode auto-run: {'activé' if effective_auto_run else 'interactif'}")
        logger.log_info(f"Settings root: {active_settings.project_root}")
        if invalid_cached_workspace:
            logger.log_warning("Dernier workspace connu introuvable. Retour au dépôt courant.")
        
        try:
            # Parse du fichier YAML
            if console:
                console.print(safe_print(f"[cyan]📄 Reading mission file:[/cyan] {mission_file}"))
            
            mission = yaml_parser.create_mission_from_yaml(mission_file)
            mission.metadata.setdefault("workspace", str(resolved_workspace))
            mission.metadata.setdefault("auto_run", effective_auto_run)
            logger.log_info(f"Mission: {mission.name}")
            
            if console:
                console.print(Panel(
                    safe_print(f"[bold]{mission.name}[/bold]\n{mission.description}"),
                    title="[bold]Mission[/bold]",
                    border_style="cyan"
                ))
            
            # Validation
            errors = ExecutorService().validate_mission(mission)
            if errors:
                for error in errors:
                    logger.log_error(error)
                    if console:
                        console.print(safe_print(f"[red]❌ Validation error:[/red] {error}"))
                sys.exit(1)
            
            # Configuration du modèle IA si spécifié
            if model:
                try:
                    ai_connector.switch_model(model)
                    logger.log_info(f"Using model: {model}")
                except AIConnectorError as e:
                    logger.log_warning(str(e))
                    logger.log_info(f"Falling back to default model: {ai_connector.model}")
            
            # Exécution de la mission
            if dry_run:
                logger.log_info("Dry-run mode: No changes will be made")
                if console:
                    console.print(safe_print("[yellow]⚠️  DRY-RUN MODE - No changes will be made[/yellow]"))
            
            executor = ExecutorService()
            
            # Callbacks pour le logging
            def on_task_start(task: Task):
                logger.log_task_start(task.name)
            
            def on_task_complete(task: Task):
                logger.log_task_complete(task.name, task.result or "Completed")
            
            def on_task_fail(task: Task, error: Exception):
                logger.log_task_fail(task.name, str(error))
            
            def on_mission_complete(mission: Mission):
                logger.log_info(f"Mission completed successfully! Progress: {mission.get_progress():.1f}%")
                if console:
                    console.print(safe_print(f"\n[bold green]✅ Mission completed![/bold green]"))
                    console.print(f"[dim]Log saved to: {logger.get_log_file_path()}[/dim]")
            
            executor.on_task_started = on_task_start
            executor.on_task_completed = on_task_complete
            executor.on_task_failed = on_task_fail
            executor.on_mission_completed = on_mission_complete
            
            if effective_auto_run:
                logger.log_info("Mode auto-run activé : aucune confirmation ne sera demandée.")
            else:
                logger.log_info("Mode interactif : confirmation requise avant chaque tâche.")

            def confirm_task(task: Task) -> bool:
                prompt_text = f"Continuer avec '{task.name}' ? (o/n)"
                if console:
                    response = typer.prompt(prompt_text, default="o")
                else:
                    response = input(f"{prompt_text} ").strip() or "o"
                decision = str(response).strip().lower().startswith("o")
                logger.log_info(
                    f"Confirmation {'acceptée' if decision else 'refusée'} pour la tâche '{task.name}'"
                )
                if console and not decision:
                    console.print(safe_print(f"[yellow]⚠️  Tâche '{task.name}' annulée par l'utilisateur[/yellow]"))
                return decision

            # Simulation pour cette version
            # Dans une version complète, cela appellerait l'IA pour générer du code
            success = executor.execute_mission(
                mission,
                require_confirmation=True,
                confirmer=confirm_task,
            )
            
            if not success:
                logger.log_error("Mission failed")
                sys.exit(1)
            
            # Generate output files if specified
            if console:
                console.print(safe_print("\n[cyan]📄 Generating output files...[/cyan]"))
            
            outputs = mission.metadata.get("outputs", [])
            if outputs:
                logger.log_info(f"Found {len(outputs)} output(s) to generate")
                for output_config in outputs:
                    try:
                        file_path = output_handler.create_output_file(output_config, mission.name, mission=mission)
                        logger.log_info(f"Created: {file_path}")
                        if console:
                            console.print(safe_print(f"[green]  [OK] {file_path}[/green]"))
                    except OutputHandlerError as e:
                        error_msg = f"Failed to create output: {str(e)}"
                        logger.log_error(error_msg)
                        if console:
                            console.print(safe_print(f"[red]  [X] {error_msg}[/red]"))
            
            # Execute post-actions if specified
            post_actions = mission.metadata.get("post_actions", [])
            if post_actions:
                if console:
                    console.print(safe_print("\n[cyan]🔄 Executing post-actions...[/cyan]"))
                logger.log_info(f"Found {len(post_actions)} post-action(s)")
                try:
                    output_handler.execute_post_actions(post_actions, console, safe_print)
                    logger.log_info("All post-actions completed successfully")
                except OutputHandlerError as e:
                    error_msg = f"Post-actions failed: {str(e)}"
                    logger.log_error(error_msg)
                    if console:
                        console.print(safe_print(f"[red]❌ {error_msg}[/red]"))
        
        except YAMLParserError as e:
            error_msg = f"Failed to parse YAML: {str(e)}"
            logger.log_error(error_msg)
            if console:
                console.print(safe_print(f"[red]❌ {error_msg}[/red]"))
            sys.exit(1)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.log_error(error_msg)
            if console:
                console.print(safe_print(f"[red]❌ {error_msg}[/red]"))
            sys.exit(1)


    @app.command()
    def audit(
        target: str = typer.Argument(..., help="Cible à auditer (fichier ou répertoire)"),
        output: Optional[str] = typer.Option(None, "--output", "-o", help="Fichier de sortie pour l'audit")
    ):
        """
        Effectue un audit du code (mode analytique sans modifications)
        """
        init_app()
        console.print(safe_print("[yellow]⚠️  Audit mode not yet implemented[/yellow]"))


    @app.command()
    def diff(
        file1: str = typer.Argument(..., help="Premier fichier"),
        file2: str = typer.Argument(..., help="Deuxième fichier")
    ):
        """
        Affiche le diff entre deux fichiers
        """
        init_app()
        
        try:
            from core.file_manager import file_manager
            
            content1 = file_manager.read_file(file1)
            content2 = file_manager.read_file(file2)
            
            diff_result = diff_engine.compute_diff(content1, content2, file1)
            ui_diff_view.display_diff(diff_result)
        
        except FileManagerError as e:
            console.print(safe_print(f"[red]❌ Error reading files: {str(e)}[/red]"))
            sys.exit(1)


    @app.command()
    def version():
        """
        Affiche la version de AIHomeCoder
        """
        active_settings = settings_module.get_settings()
        version_info = f"""
AIHomeCoder v{active_settings.metadata.get('version', '1.0.0')}

Clean Architecture Python Application
Local code co-editing engine with AI integration
        """
        if console:
            console.print(Panel(version_info.strip(), border_style="cyan"))
        else:
            print(version_info)


def main():
    """Point d'entrée principal"""
    if app is None:
        print("Error: typer is not installed. Please run: pip install -r requirements.txt")
        sys.exit(1)
    app()


if __name__ == "__main__":
    main()
