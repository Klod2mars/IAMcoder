# Context Audit - AIHomeCoder

> Audit structurel et environnemental realise le 2025-10-31.

## 1. Structure du referentiel (3 niveaux)
- Chemins racine actifs: `core/`, `domain/`, `data/`, `presentation/`, `modules/`, `config/`, `reports/`, `ARCHIVES/`

```
.
|-- ARCHIVES/
|   |-- aihomecoder.yalm
|   |-- audit.yaml
|   |-- Command Tree Simple.yalm.yaml
|   |-- Command Tree Simple.yaml
|   `-- test_aihomecoder_phase1.yalm.yaml
|-- config/
|   |-- profiles/
|   |   |-- deepseek_local.yaml
|   |   |-- default.yaml
|   |   `-- qwen_local.yaml
|   `-- settings.yaml
|-- core/
|   |-- file_manager.py
|   |-- guardrail.py
|   `-- settings.py
|-- data/
|   |-- ai_connector.py
|   |-- context_index.py
|   |-- diff_engine.py
|   `-- yaml_parser.py
|-- domain/
|   |-- entities/
|   |   |-- diff_result.py
|   |   |-- mission.py
|   |   `-- task.py
|   `-- services/
|       `-- executor_service.py
|-- modules/
|   `-- output_handler.py
|-- presentation/
|   |-- cli.py
|   |-- logger.py
|   `-- ui_diff_view.py
|-- reports/
|   |-- audit_structure_aihomecoder_cursor_2025-10-31.md
|   |-- mission_test_output.md
|   `-- structure_snapshot.md
`-- (autres dossiers: `tests/`, `logs/`, `exchange/`, `tools/`, `venv/` ...)
```

## 2. Configuration centrale (`config/settings.yaml`)
> Points clefs: moteur IA local Ollama, profil `qwen_local` par defaut, mode `read_only` actif, chemins sanctuarises charges depuis la configuration.
- IA: moteur `ollama`, modele par defaut `qwen2-coder:7b-instruct`, alternatif `deepseek-coder:6.7b`
- Securite: `rollback` active, sanctuaires (`data/hive_boxes/**`, `.env`, `private/**`, `.git/**`)
- Defauts: profil `qwen_local`, mode `read_only`, `log_level` INFO, `diff_context` 3, taille max fichiers 10 MB
- Chemins internes: journaux `logs/`, donnees `data/`, base `data/chroma_db`

```6:33:config/settings.yaml
ia:
  engine: "ollama"
  model_default: "qwen2-coder:7b-instruct"
  alt_model: "deepseek-coder:6.7b"
security:
  rollback: true
  sanctuary_paths:
    - "data/hive_boxes/**"
    - ".env"
    - "private/**"
    - ".git/**"
defaults:
  profile: "qwen_local"
  mode: "read_only"
  log_level: "INFO"
  diff_context: 3
  max_file_size_mb: 10
paths:
  logs: "logs"
  data: "data"
  chroma_db: "data/chroma_db"
```

## 3. Guardrail et mode operatoire
> `core/guardrail` applique les sanctuaires issus des settings et bloque les operations d'ecriture en mode `read_only`.
- Les inspections utilisent `Guardrail.is_sanctuary_path` avec les motifs charges dans `settings.sanctuary_paths`
- `_get_current_mode_from_config()` lit `config/settings.yaml` et renvoie `read_only`
- `enforce_task_restrictions` interdit les instructions contenant `write`, `delete`, `move` en mode lecture seule

```21:82:core/guardrail.py
    def __init__(self, sanctuary_paths: List[str] = None):
        self.sanctuary_paths = sanctuary_paths or settings.sanctuary_paths
...
        for pattern in self.sanctuary_paths:
            normalized_pattern = pattern.replace('\\', '/')
            if fnmatch.fnmatch(file_path_str, normalized_pattern):
                return True
```

```105:115:core/guardrail.py
def enforce_task_restrictions(task_text: str, mode: str | None = None) -> None:
    active_mode = mode or _get_current_mode_from_config()
    if str(active_mode).lower() == "read_only":
        lowered = (task_text or "").lower()
        for keyword in ("write", "delete", "move"):
            if keyword in lowered:
                raise GuardrailError("Forbidden in read_only mode")
```

## 4. Output handler - RAW OUTPUT MODE
> Le module detecte un mode brut lorsque la mission est en lecture seule, declare un format `raw` ou place `meta.raw_output=true`, et ecrit directement les donnees sans gabarit.

```51:88:modules/output_handler.py
        # Check for raw output mode
        if mission is not None:
            context = mission.metadata.get("context", {}) or {}
            meta = mission.metadata.get("meta", {}) or {}
            is_read_only = context.get("mode") == "read_only"
            is_raw_format = context.get("output_format") == "raw"
            has_raw_output_flag = meta.get("raw_output") is True
            if is_read_only or is_raw_format or has_raw_output_flag:
                raw_data = None
                raw_output_value = meta.get("raw_output")
                if isinstance(raw_output_value, str) and raw_output_value:
                    raw_data = raw_output_value
                elif mission.tasks:
                    task_results = []
                    for task in mission.tasks:
                        if task.result:
                            task_results.append(str(task.result))
                    if task_results:
                        raw_data = "\n".join(task_results)
                if raw_data:
                    file_manager.write_file(destination, raw_data)
                    self.created_files.append(destination)
                    return destination
```

## 5. Modules critiques (AI Connector & Executor Service)
> Pas de variable de version interne dediee; les deux modules s'appuient sur la version globale `settings.metadata['version'] = 1.0.0`. Les comportements clefs sont synthetises ci-dessous.
- `AIConnector` utilise par defaut Ollama avec le modele `qwen2-coder:7b-instruct` et verifie la disponibilite de l'outil via `ollama list`
- Le service peut basculer vers `deepseek-coder:6.7b` via `switch_model` apres validation
- `ExecutorService` orchestre les taches et positionne les statuts mission/tache (`RUNNING`, `COMPLETED`, `FAILED`), avec la logique par defaut retournant `Task 'name' executed successfully`

```22:114:data/ai_connector.py
    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.ia_model_default
        self.engine = settings.ia_engine
        self.ollama_available = self._check_ollama_availability()
...
        try:
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
```

```22:106:domain/services/executor_service.py
    def execute_mission(self, mission: Mission) -> bool:
        mission.status = MissionStatus.RUNNING
        try:
            for task in mission.tasks:
                if not self._execute_task(task, mission):
                    mission.status = MissionStatus.FAILED
                    if self.on_mission_failed:
                        self.on_mission_failed(mission)
                    return False
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

## 6. Environnement d'execution Python
- Environnement virtuel: `venv/`
- Python interprete: `Python 3.10.9` (sortie de `venv\Scripts\python.exe --version`)
- Configuration `pyvenv.cfg`: base `C:\\Program Files\\Python310`, `include-system-site-packages = false`

```1:3:venv/pyvenv.cfg
home = C:\\Program Files\\Python310
include-system-site-packages = false
version = 3.10.9
```

## 7. Inventaire YAML / YALM
- Fichiers `.yalm`: 6 principaux (`ARCHIVES/aihomecoder.yalm`, `deepseek_review_phase_03.yalm`, `example_mission.yalm`, `hello_aihomecoder.yalm`, `mission_output_phase_02.yalm`, `mission_standard.yalm`)
- Fichiers `.yaml`: 6 dans le projet actif (`ARCHIVES/audit.yaml`, `ARCHIVES/Command Tree Simple.yaml`, `config/settings.yaml`, `config/profiles/{deepseek_local,default,qwen_local}.yaml`) + 1 dependance (`venv/Lib/site-packages/markdown_it/port.yaml`)
- Fichiers hybrides `.yalm.yaml`: 5 (`ARCHIVES/Command Tree Simple.yalm.yaml`, `ARCHIVES/test_aihomecoder_phase1.yalm.yaml`, `Command Tree Simple.yalm.yaml`, `hello_claude_to_aihomecoder.yalm.yaml`, `install_claude_legacy.yalm.yaml`)
- Aucun `.env` present, mais sanctuarise; logs volumiques dans `logs/` (lecture seule)

> Fin du rapport - pre-brief pour mission constructive YALM.

