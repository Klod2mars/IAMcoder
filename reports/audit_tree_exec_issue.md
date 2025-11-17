# Audit – Activation de `task_tree_scan`

## Synthèse rapide
- Le YAML `Audit Tree Permacalendar V2.yaml` décrit la tâche via `id: "tree_scan"` sans champ `task_type`/`type`, laissant le type implicite.
- `YAMLParser._build_mission` ne mappe pas `id` vers `task_type`, d’où la création d’une `Task` de type `generic`.
- `TaskLogicHandler.execute` n’atteint jamais la branche `tree_scan` et renvoie le message informatif par défaut, aucune génération de rapport.
- Le log indiqué dans le mandat (`session_20251101_185154.md`) est absent du dépôt, ce qui complique la vérification post-exécution.

## Chaîne d’appel YAML → mission → `TaskLogicHandler`

| Étape | Composant | Observation | Résultat |
| --- | --- | --- | --- |
| 1 | Mission YAML externe | La tâche est identifiée par `id` et aucun champ `task_type` n’est fourni. | Intention `tree_scan` implicite seulement. |
| 2 | `presentation/cli.run` | Charge le YAML via `yaml_parser.create_mission_from_yaml`. | Passe le contenu au parser strict. |
| 3 | `data.yaml_parser._build_mission` | Construit la `Task` en ne regardant que `type` / `task_type`; valeur par défaut `generic`. | `Task.task_type == "generic"`. |
| 4 | `domain.services.task_logic_handler.execute` | Dispatch basé sur `task_type.lower()`; `tree_scan` jamais détecté. | Branche « sans logique spécifique » exécutée. |

```18:31:../permacalendarv2/Audit Tree Permacalendar V2.yaml
tasks:
  - id: "tree_scan"
    goal: "Parcourir le workspace et générer un rapport Markdown d'arborescence."
    parameters:
      destination: "${REPORT_PATH}"
      extensions:
        - ".dart"
        - ".yaml"
      include_hidden: false
      depth_limit: 5
    output:
      destination: "${REPORT_PATH}"
      format: "markdown"
```

```101:137:data/yaml_parser.py
        mission = Mission(
            name=mission_name,
            description=description,
            metadata={
                "version": meta.get("version", "1.0.0"),
                "author": meta.get("author", ""),
                "architecture": meta.get("architecture", ""),
                "language": meta.get("language", ""),
                "meta": meta,
                "context": data.get("context"),
                "outputs": data.get("outputs"),
                "post_actions": data.get("post_actions")
            }
        )
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
```

```19:46:domain/entities/task.py
@dataclass
class Task:
    name: str
    goal: str
    task_type: str = "generic"
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
```

```41:55:domain/services/task_logic_handler.py
    def execute(self, task, mission):
        ttype = task.task_type.lower()
        params = task.parameters or {}

        if ttype == "analysis":
            return self._analyze_workspace(params)
        elif ttype == "report_generation":
            return self._generate_markdown(params)
        elif ttype in {"tree_scan", "tree"}:
            context = self._build_execution_context(task, mission)
            return task_tree_scan(params, context)
        elif ttype == "setup":
            return f"[OK] Préparation du workspace : {params.get('variable_path', 'N/A')}"
        else:
            return f"[INFO] Tâche '{task.name}' exécutée sans logique spécifique."
```

## Checklist des paramètres transmis

| Paramètre | Source YAML | Après parsing | Remarques |
| --- | --- | --- | --- |
| `destination` | `tasks[0].parameters.destination` | Présent dans `Task.parameters` (atteignable par `task_tree_scan`). | Utilisable seulement si la branche `tree_scan` est atteinte. |
| `extensions` | `tasks[0].parameters.extensions` | Conservé dans `Task.parameters`. | Sert à filtrer les fichiers dans `task_tree_scan`. |
| `workspace` | `context.workspace` | Copié dans `Mission.metadata['context']` puis résolu via `_build_execution_context`. | Fournit le workspace réel à scanner. |
| `variables.REPORT_PATH` | `context.variables` | Agrégé dans le contexte d’exécution via `_collect_variables`. | Permet de résoudre `${REPORT_PATH}` si la logique est déclenchée. |
| `tasks[0].output` | Section `output` à l’intérieur de la tâche | Non recopié dans `Task.parameters`; `declared_outputs` reste vide. | La fonction lit `params.get("output")`, donc cette config est perdue. |
| `task_type` attendu | `${task_data.type}` ou `${task_data.task_type}` | Non défini → valeur par défaut `generic`. | Point de rupture : aucune correspondance `tree_scan`. |

```130:174:domain/services/task_logic_handler.py
    def _build_execution_context(self, task, mission):
        metadata = mission.metadata or {}
        context_section = metadata.get("context") or {}
        params = task.parameters or {}

        variables = self._collect_variables(params, context_section)

        workspace_hint = (
            params.get("workspace")
            or params.get("workspace_path")
            or context_section.get("workspace")
            or context_section.get("workspace_path")
        )
        workspace_value = _resolve_placeholders(workspace_hint, variables)
        if isinstance(workspace_value, (dict, list)):
            workspace_value = None
        workspace_candidate = str(workspace_value).strip() if workspace_value else "."
        try:
            workspace_path = Path(workspace_candidate).resolve()
        except OSError:
            workspace_path = Path(".").resolve()

        declared_outputs = metadata.get("outputs") or []
        declared_outputs = _resolve_placeholders(declared_outputs, variables)

        output_config = params.get("output") or {}
        output_config = _resolve_placeholders(output_config, variables)

        return {
            "task": task,
            "mission": mission,
            "workspace": str(workspace_path),
            "workspace_path": workspace_path,
            "variables": variables,
            "mode": context_section.get("mode"),
            "output": output_config,
            "declared_outputs": declared_outputs,
            "context_meta": context_section,
            "file_manager": file_manager,
            "guardrail": guardrail,
            "context_bridge": context_bridge,
        }
```

## Diagnostic
- La clé `id` du YAML n’est jamais traduite en `task_type`; la tâche est créée avec le type par défaut `generic` et le dispatcher ne peut pas reconnaître `tree_scan`.
- La configuration `output` spécifique à la tâche n’est plus accessible après parsing, ce qui limiterait la résolution automatique du chemin même si la branche était atteinte.
- `ExecutorService._execute_task` relaie la demande au handler sans instrumentation supplémentaire, ce qui masque le mauvais mapping tant que l’on ne trace pas `task.task_type`.
- Les journaux de session attendus ne sont pas présents, rendant la détection de ce scénario uniquement possible par inspection du code.

## Pistes de correction
- Étendre `YAMLParser` pour considérer `task_data.get("id")` comme candidat au `task_type` lorsque `type`/`task_type` sont absents, ou copier la valeur dans `task_parameters["task_type"]`.
- Minimalement, mettre à jour les missions existantes pour expliciter `task_type: "tree_scan"` jusqu’à ce que le parser soit corrigé.
- Ajouter une validation (ex. dans `ExecutorService.validate_mission`) qui signale les tâches dont le `task_type` est `generic` alors qu’un champ `id` connu est présent.
- Restituer la sous-clé `output` dans `Task.parameters` (ou dans `Mission.metadata['outputs']`) afin que `task_tree_scan` dispose d’un fallback cohérent.
- Consigner dans le log le couple (`task.name`, `task.task_type`) avant dispatch pour faciliter les audits futurs.

## Notes complémentaires
- `Audit Tree Permacalendar V2.yaml` est stocké dans `../permacalendarv2` et non dans le dépôt `aihomecoder`; prévoir une copie locale ou une synchronisation si l’outil doit y accéder automatiquement.
- Le log mentionné dans le mandat (`session_20251101_185154.md`) n’existe pas dans `logs/`; le dernier fichier voisin est `session_20251101_185144.md` mais vide.


