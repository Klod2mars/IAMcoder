# Audit Cursor - Workspace & Flow

**Mission:** audit_cursor_aihomecoder_workspace_and_flow  
**Date:** 2025-11-01  
**Mode:** read_only_audit  

## 1. Entrées pour la sélection du workspace

| Module | Détermination du chemin | Observations | Opportunité pour `select_workspace()` |
| --- | --- | --- | --- |
| `core/settings.Settings` | `Path.cwd()` fixé dès l'instanciation | L'instance globale `settings` est créée à l'import et propage le `cwd` courant vers `guardrail`, `logger`, `ai_connector`… | Introduire une fabrique acceptant un `workspace_path` et initialiser avant toute importation dépendante. |
| `presentation/cli.run` | `init_app()` appelle `settings.ensure_directories()` | Comme `settings` est déjà figé, la CLI ne peut pas changer de workspace une fois chargée. | Injecter le workspace sélectionné via un paramètre ou une fonction `configure_settings()` avant d'initialiser la CLI. |
| `run_mission.py` | `ROOT_DIR = os.path.dirname(os.path.abspath(__file__))` | Les missions listées et exécutées sont cantonnées au dépôt courant; pas de multi-workspace. | Brancher la sélection dynamique et propager le chemin choisi au sous-processus (`cwd=workspace_path`). |
| `presentation/welcome_screen.py` | `ROOT_DIR = Path(__file__).resolve().parent.parent` | L'écran d'accueil affiche et scanne uniquement le dépôt d'origine. | Lire le workspace persistant et offrir un picklist comme point d'entrée. |
| `data.diff_engine.DiffEngine` | `project_root or Path.cwd()` | Les opérations Git/rollback dépendent du workspace actif. | Passer explicitement le workspace pour aligner Git et guardrails. |

```16:33:core/settings.py
        self.project_root = Path.cwd()
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
```

```41:44:presentation/cli.py
def init_app():
    """Initialise l'application avec les ressources nécessaires"""
    settings.ensure_directories()
```

```5:16:run_mission.py
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def list_yalm_files():
    """
    List all mission files (.yalm, .yaml, .yalm.yaml) in the root directory.
    Added multi-extension support on 2025-10-30 for better compatibility.
    """
    valid_exts = (".yalm", ".yaml", ".yalm.yaml")
    files = [
        f for f in os.listdir(ROOT_DIR)
        if f.lower().endswith(valid_exts)
    ]
    return sorted(files)
```

```52:62:run_mission.py
    cmd = [
        os.path.join(ROOT_DIR, "venv", "Scripts", "python.exe"),
        os.path.join(ROOT_DIR, "main.py"),
        "run",
        selected,
        "--verbose"
    ]

    try:
        subprocess.run(cmd, cwd=ROOT_DIR)
```

```10:24:presentation/welcome_screen.py
ROOT_DIR = Path(__file__).resolve().parent.parent

def collect_missions() -> list[str]:
    """Return sorted mission filenames available at repository root."""

    patterns = ("*.yalm", "*.yalm.yaml")
    result: set[str] = set()

    for pattern in patterns:
        for candidate in ROOT_DIR.glob(pattern):
            if candidate.parent == ROOT_DIR:
                result.add(candidate.name)

    return sorted(result)
```

```27:33:presentation/welcome_screen.py
def render_header() -> None:
    print("=" * 70)
    print(" AIHomeCoder :: Terminal Welcome Screen")
    print("=" * 70)
    print("Workspace:", ROOT_DIR)
    print()
```

```26:28:data/diff_engine.py
        self.project_root = Path(project_root) if project_root else Path.cwd()
```

## 2. Pipeline d'exécution des tasks

- `ExecutorService.execute_mission` positionne la mission en `RUNNING`, parcourt `mission.tasks` et délègue à `_execute_task`. Les callbacks (`on_task_started`, `on_task_completed`…) ne gèrent qu'une instrumentation.
- `_execute_task` marque la tâche `IN_PROGRESS`, appelle `_execute_task_logic`, puis la marque `COMPLETED` en l'absence d'exception.
- `_execute_task_logic` renvoie une chaîne statique; aucune logique n'est attachée au `task_type` ou aux paramètres. Ainsi, même si plusieurs tâches sont déclarées, aucune exécution métier ne se produit après la première réussite apparente.

```22:45:domain/services/executor_service.py
    def execute_mission(self, mission: Mission) -> bool:
        """
        Exécute une mission complète.
        
        Args:
            mission: La mission à exécuter
            
        Returns:
            True si la mission a réussi, False sinon
        """
        mission.status = MissionStatus.RUNNING
        
        try:
            for task in mission.tasks:
                if not self._execute_task(task, mission):
                    mission.status = MissionStatus.FAILED
                    if self.on_mission_failed:
                        self.on_mission_failed(mission)
                    return False
```

```46:88:domain/services/executor_service.py
            mission.status = MissionStatus.COMPLETED
            if self.on_mission_completed:
                self.on_mission_completed(mission)
            return True
            
        except Exception as e:
            mission.status = MissionStatus.FAILED
            if self.on_mission_failed:
                self.on_mission_failed(mission)
            return False
```

```91:105:domain/services/executor_service.py
    def _execute_task_logic(self, task: Task, mission: Mission) -> str:
        """
        Logique d'exécution d'une tâche.
        Cette méthode doit être surchargée ou injectée avec de la logique concrète.
        
        Args:
            task: La tâche à exécuter
            mission: La mission parente
            
        Returns:
            Le résultat de l'exécution
        """
        return f"Task '{task.name}' executed successfully"
```

```118:137:data/yaml_parser.py
        tasks_data = data.get("tasks", [])
        for index, task_data in enumerate(tasks_data, start=1):
            if isinstance(task_data, dict):
                task = Task(
                    name=task_data.get("name", f"task_{index}"),
                    goal=task_data.get("goal", ""),
                    task_type=task_data.get("type", task_data.get("task_type", "generic")),
                    parameters=task_data.get("parameters", {})
                )
                mission.add_task(task)
            elif isinstance(task_data, str):
                task = Task(
                    name=f"task_{index}",
                    goal=task_data.strip(),
                    task_type="instruction",
                    parameters={}
                )
                mission.add_task(task)
```

> **Constat :** la mission semble "s'arrêter" après la première tâche car aucune implémentation concrète n'existe pour la suite. Le pipeline signale un succès immédiat sans interpréter le `task_type`. La prochaine itération doit donc injecter une couche applicative (ex. mapping `task_type → handler`).

## 3. Validation utilisateur entre tasks

- Introduire un mode interactif avec confirmation explicite avant chaque tâche.
- Étendre la CLI (`typer`) avec une option `--auto-run/--no-auto-run` (défaut: interactif).
- Propager le paramètre jusqu'à `ExecutorService` via une fonction de confirmation.

```python
def execute_mission(
    self,
    mission: Mission,
    *,
    require_confirmation: bool = False,
    confirmer: Callable[[Task], bool] | None = None
) -> bool:
    for task in mission.tasks:
        if require_confirmation:
            check = confirmer or (
                lambda t: input(f"Continuer avec '{t.name}' ? (o/n) ").strip().lower().startswith("o")
            )
            if not check(task):
                task.status = TaskStatus.CANCELLED
                mission.status = MissionStatus.CANCELLED
                return False
        if not self._execute_task(task, mission):
            return False
    mission.status = MissionStatus.COMPLETED
    return True
```

- Implémenter `confirmer` côté CLI pour gérer Rich/console, respecter `--auto-run`, et journaliser la décision utilisateur.

## 4. Persistance du workspace sélectionné

- Créer `core/workspace_store.py` chargé de lire/écrire `config/state/workspace.json`.
- Structure minimale proposée :

```json
{
  "last_workspace": "C:/Projets/ClientA",
  "history": [
    {"path": "C:/Projets/ClientA", "last_used": "2025-11-01T10:15:00Z"},
    {"path": "D:/Clients/Beta", "last_used": "2025-10-28T18:42:00Z"}
  ],
  "auto_run": false
}
```

- Lors de l'initialisation :
  1. Charger l'état si disponible.
  2. Proposer la dernière sélection en valeur par défaut.
  3. Après validation, mettre à jour `last_used` et purger les chemins inexistants.
  4. Exposer `get_active_workspace()` utilisé par `Settings`, `run_mission.py`, `welcome_screen`.

## 5. Recommandations immédiates

- Refactoriser `core/settings` en fabrique paresseuse (`get_settings(workspace: Path)`), puis remplacer les importations directes par une initialisation orchestrée dans `main.py`.
- Introduire un `WorkspaceManager` (sélection interactive + persistance) et l'invoquer avant l'import de modules dépendants.
- Cartographier les `task_type` actuels et définir un registre de handlers pour donner un comportement concret aux missions.
- Ajouter des tests d'intégration couvrant la sélection de workspace, la validation utilisateur et la persistance JSON afin de sécuriser ces évolutions.


