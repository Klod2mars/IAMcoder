# Rapport Cursor - Structure AIHomeCoder

**Date:** 2025-10-31  
**Objectif:** Extraction des informations sur la structure interne d'AIHomeCoder pour génération de missions YAML compatibles

---

## 1. Structure YAML attendue

### Schéma minimal requis

Une mission YAML (`*.yalm`, `*.yaml`, ou `*.yalm.yaml`) doit respecter la structure suivante :

```yaml
meta:
  project_name: "nom_mission"  # OU mission_id (l'un ou l'autre requis)
  version: "1.0.0"              # Optionnel, défaut: "1.0.0"
  description: "Description de la mission"
  author: "Auteur"              # Optionnel
  architecture: "Architecture"   # Optionnel
  language: "Python 3.10+"      # Optionnel
  model: "qwen2.5-coder:7b"     # Optionnel (pour mémoire IA)
  memory: "config/profiles/qwen_local.yaml"  # Optionnel (fichier mémoire)

tasks:                          # OBLIGATOIRE - Liste des tâches
  - name: "Nom de la tâche"     # Requis si dict
    goal: "Objectif de la tâche"
    task_type: "generic"        # Optionnel, défaut: "generic"
    parameters:                  # Optionnel, dict vide par défaut
      key: value

  # OU format simplifié (chaîne de caractères)
  - "Instruction textuelle simple de la tâche"

# Sections optionnelles
context:                        # Contexte d'exécution
  environment: "ollama"
  language: "English"
  mode: "local_test"
  output_format: "markdown"

outputs:                        # Fichiers de sortie à générer
  - format: "markdown"
    destination: "reports/mission_report.md"
  - format: "lialm"
    destination: "exchange/exchange_file.lialm"
  - format: "text"              # OU simplement log: "logs/mission.log"
    destination: "logs/mission.log"

post_actions:                   # Actions post-exécution
  - "Validate that both output files exist."
  - "Display the first 10 lines of the Markdown report in console."
  - "Print confirmation message: '✅ Mission complete.'"

stack:                          # Stack technique (optionnel)
  frameworks:
    - "pytest"
    - "typer"
  environment:
    min_python: "3.10"

intent:                         # Intentions (optionnel)
  - "Première intention"
  - "Deuxième intention"
```

### Validation structurelle

**Validations effectuées dans `data/yaml_parser.py` (méthode `validate_yaml_structure`) :**

1. **Section `meta` obligatoire**
   - Doit contenir `project_name` OU `mission_id` (au moins l'un)
   
2. **Section `tasks` obligatoire**
   - Doit être une liste
   - Chaque tâche peut être :
     - Un dictionnaire avec au moins `goal` OU `name`
     - Une chaîne de caractères non vide

**Erreurs retournées :**
- `"Missing 'meta' section"`
- `"Missing 'meta.project_name' or 'meta.mission_id'"`
- `"Missing 'tasks' section"`
- `"'tasks' must be a list"`
- `"Task {i+1} must have at least 'goal' or 'name'"`
- `"Task {i+1} string is empty"`
- `"Task {i+1} must be a dictionary or a string"`

---

## 2. Types de tâches disponibles

### Types supportés

Le système est flexible sur les types de tâches. La clé `task_type` accepte n'importe quelle valeur, mais les exemples observés incluent :

- `"generic"` - Type par défaut (défini dans `domain/entities/task.py:27`)
- `"instruction"` - Tâche textuelle simple (mappée depuis une chaîne)
- `"code_generation"` - Génération de code
- `"test_generation"` - Génération de tests
- `"documentation"` - Génération de documentation

**Note importante :** Le type de tâche n'est pas validé strictement. Le système accepte tout type personnalisé, mais l'exécution réelle dépend de la logique injectée dans `ExecutorService._execute_task_logic()`.

### Structure d'une Task (entité)

```python
Task(
    name: str                    # OBLIGATOIRE (validation dans __post_init__)
    goal: str                    # OBLIGATOIRE (validation dans __post_init__)
    task_type: str = "generic"   # Optionnel
    parameters: Dict[str, Any]   # Optionnel, dict vide par défaut
    status: TaskStatus           # Géré par le système
    result: Optional[str]        # Résultat de l'exécution
    error: Optional[str]         # Message d'erreur si échec
)
```

---

## 3. Validation interne

### Où sont levées les erreurs

#### A. Validation YAML structure (`data/yaml_parser.py:139`)

**Méthode :** `YAMLParser.validate_yaml_structure(data: Dict[str, Any]) -> List[str]`

Vérifie :
- Présence de `meta` et `project_name`/`mission_id`
- Présence de `tasks` comme liste
- Format valide de chaque tâche

#### B. Validation Mission (`domain/services/executor_service.py:107`)

**Méthode :** `ExecutorService.validate_mission(mission: Mission) -> List[str]`

**Emplacement exact de l'erreur "Mission must contain at least one task" :**
- **Fichier :** `domain/services/executor_service.py`
- **Ligne :** 122-123
- **Code :**
  ```python
  if not mission.tasks:
      errors.append("Mission must contain at least one task")
  ```

**Validations complètes dans `validate_mission()` :**
1. ✅ Mission doit avoir un `name` non vide
2. ✅ Mission doit contenir **au moins une tâche** (`mission.tasks` non vide)
3. ✅ Chaque tâche doit avoir un `name` non vide
4. ✅ Chaque tâche doit avoir un `goal` non vide

#### C. Validation Entity Mission (`domain/entities/mission.py:32`)

**Méthode :** `Mission.__post_init__()`

Vérifie que `name` n'est pas vide, lève `ValueError("Mission name cannot be empty")`.

#### D. Validation Entity Task (`domain/entities/task.py:33`)

**Méthode :** `Task.__post_init__()`

Lève `ValueError` si :
- `name` est vide : `"Task name cannot be empty"`
- `goal` est vide : `"Task goal cannot be empty"`

### Ordre de validation lors de l'exécution

1. **Parsing YAML** (`yaml_parser.parse_file()`)
   - Syntaxe YAML valide
   
2. **Construction Mission** (`yaml_parser.create_mission_from_yaml()`)
   - Appelle `_build_mission()` qui crée les entités
   - Les `__post_init__()` valident `name` et `goal`
   
3. **Validation finale** (`ExecutorService.validate_mission()`)
   - Vérifie nom de mission
   - **Vérifie présence d'au moins une tâche** ← ICI l'erreur principale
   - Vérifie nom et goal de chaque tâche

**Point d'entrée CLI :** `presentation/cli.py:103`
```python
errors = ExecutorService().validate_mission(mission)
if errors:
    for error in errors:
        logger.log_error(error)
        console.print(safe_print(f"[red]❌ Validation error:[/red] {error}"))
    sys.exit(1)
```

---

## 4. Flux d'exécution général

### Diagramme de flux

```
main.py
  └─> presentation/cli.py::run()
      ├─> yaml_parser.create_mission_from_yaml(file_path)
      │   ├─> parse_file() → Dict[str, Any]
      │   └─> _build_mission() → Mission
      │       ├─> Mission.__init__() (valide name)
      │       └─> Pour chaque task_data:
      │           └─> Task.__init__() (valide name + goal)
      │
      ├─> ExecutorService().validate_mission(mission)
      │   └─> Vérifie: name, tasks non vide, chaque task.name/goal
      │
      ├─> ExecutorService().execute_mission(mission)
      │   ├─> mission.status = RUNNING
      │   ├─> Pour chaque task:
      │   │   ├─> _execute_task(task, mission)
      │   │   │   ├─> task.status = IN_PROGRESS
      │   │   │   ├─> on_task_started(task) [callback]
      │   │   │   ├─> _execute_task_logic(task, mission) → result
      │   │   │   │   └─> [Par défaut: retourne "Task '{name}' executed successfully"]
      │   │   │   ├─> task.status = COMPLETED
      │   │   │   └─> on_task_completed(task) [callback]
      │   │   └─> Si échec: task.status = FAILED, mission.status = FAILED
      │   └─> mission.status = COMPLETED
      │
      ├─> Génération des outputs (si définis dans mission.metadata["outputs"])
      │   └─> output_handler.create_output_file(output_config, mission_name)
      │
      └─> Exécution des post_actions (si définis)
          └─> output_handler.execute_post_actions(post_actions)
```

### Transmission des paramètres

**Paramètres de tâche :**
- Les `parameters` de chaque tâche sont stockés dans `Task.parameters` (Dict[str, Any])
- Accessibles dans `_execute_task_logic()` via `task.parameters`
- Les métadonnées de mission sont dans `mission.metadata` (contient aussi `context`, `outputs`, `post_actions`)

**Exemple d'accès :**
```python
def _execute_task_logic(self, task: Task, mission: Mission) -> str:
    params = task.parameters  # Dict des paramètres de la tâche
    context = mission.metadata.get("context", {})  # Contexte global
    # Logique d'exécution...
```

### Système d'archivage

**Archivage manuel via `run_mission.py` :**

L'archivage n'est **pas automatique** par défaut. Le script `run_mission.py` propose un archivage interactif après l'exécution :

```python
# Archive option (run_mission.py:67-76)
archive_dir = os.path.join(ROOT_DIR, "ARCHIVES")
move = input("\nArchive this file? (y/n): ").strip().lower()
if move == "y":
    src = os.path.join(ROOT_DIR, selected)
    dst = os.path.join(archive_dir, selected)
    os.replace(src, dst)
```

**Dossier d'archives :** `ARCHIVES/` (à la racine du projet)

**Note :** L'exécution via `main.py run <file>` ne déclenche **pas** d'archivage automatique.

---

## 5. Règles de configuration

### Extensions de fichier reconnues

**Extensions supportées :**
- `.yalm` (format principal)
- `.yaml` (format standard YAML)
- `.yalm.yaml` (format hybride)

**Source :** `run_mission.py:12`
```python
valid_exts = (".yalm", ".yaml", ".yalm.yaml")
```

**Note :** Le parsing utilise `yaml.safe_load()` qui accepte n'importe quelle extension, mais la recherche de fichiers dans `run_mission.py` filtre sur ces extensions.

### Chemins protégés (Sanctuary Paths)

**Configuration dans `config/settings.yaml` :**
```yaml
security:
  sanctuary_paths:
    - "data/hive_boxes/**"
    - ".env"
    - "private/**"
    - ".git/**"
```

**Valeurs par défaut** (`core/settings.py:22-27`) :
- `"data/hive_boxes/**"`
- `".env"`
- `"private/**"`
- `".git/**"`

**Protection :**
- Vérifiée dans `core/file_manager.py::write_file()` via `guardrail.check_path()`
- Lève `GuardrailError` si tentative d'écriture sur un chemin protégé
- Utilise `fnmatch` pour matching de patterns (support de `**`)

### Modes d'exécution

**Modes disponibles** (`core/guardrail.py:89-115`) :

1. **`read_only`** : Interdit les actions `write`, `delete`, `move` dans le texte des tâches
   - Vérifié via `enforce_task_restrictions(task_text, mode)`
   
2. **`write_enabled`** : Autorise toutes les opérations

**Lecture du mode :**
- Depuis `config/settings.yaml` → `defaults.mode`
- Fonction : `_get_current_mode_from_config()` (`core/guardrail.py:89`)

### Emplacements des dossiers

**Dossiers principaux** (`core/settings.py:17-19`) :

- **Logs :** `logs/` (relatif à la racine)
- **Data :** `data/` (relatif à la racine)
- **Config :** `config/` (relatif à la racine)
- **Reports :** `reports/` (convention, non configuré)
- **Exchange :** `exchange/` (convention, non configuré)
- **Archives :** `ARCHIVES/` (convention, non configuré)

**Chroma DB :** `data/chroma_db` (défini dans `config/settings.yaml:paths.chroma_db`)

### Configuration IA

**Fichier :** `config/settings.yaml`
```yaml
ia:
  engine: "ollama"
  model_default: "qwen2-coder:7b-instruct"
  alt_model: "deepseek-coder:6.7b"
```

**Changement de modèle :** `data/ai_connector.py::switch_model(model_name)`

**Profils disponibles :** `config/profiles/`
- `default.yaml`
- `qwen_local.yaml`
- `deepseek_local.yaml`

---

## 6. Types de sorties supportés

**Module :** `modules/output_handler.py`

**Formats de sortie :**

1. **`markdown`** : Génère un rapport Markdown avec timestamps et sections structurées
2. **`lialm`** : Génère un fichier d'échange LIALM (format YAML pour transfert entre modèles IA)
3. **`text`** : Génère un fichier texte simple
4. **`.log`** : Si destination se termine par `.log`, génère un format de log structuré

**Configuration dans mission YAML :**
```yaml
outputs:
  - format: "markdown"
    destination: "reports/mission_report.md"
  - format: "lialm"
    destination: "exchange/exchange_file.lialm"
  - log: "logs/mission.log"  # Format alternatif
```

**Post-actions supportées :**
- `"Validate that both output files exist."` → Vérifie l'existence des fichiers créés
- `"Display the first 10 lines of the Markdown report in console."` → Aperçu du rapport
- `"Print confirmation message: '...'"` → Affiche un message de confirmation

---

## 7. Points d'attention pour génération YAML

### ✅ À respecter absolument

1. **Section `meta` obligatoire** avec `project_name` OU `mission_id`
2. **Section `tasks` obligatoire** avec au moins **une tâche**
3. **Chaque tâche** doit avoir :
   - Un `name` non vide (si dict)
   - Un `goal` non vide (si dict)
   - OU être une chaîne non vide

### ⚠️ Bonnes pratiques

1. **Nommer les tâches explicitement** : `name` + `goal` pour clarté
2. **Utiliser `parameters`** pour passer des données structurées
3. **Inclure `outputs` et `post_actions`** pour automatisation complète
4. **Respecter les sanctuary_paths** : ne pas tenter d'écrire sur `.git/**`, `.env`, etc.

### 🔒 Sécurité

- Le système vérifie automatiquement les chemins protégés
- En mode `read_only`, les tâches contenant `write`, `delete`, `move` sont bloquées
- Les fichiers sont créés avec gestion d'erreurs appropriée

---

## Résumé rapide

1. **Structure minimale** : `meta` (avec `project_name` ou `mission_id`) + `tasks` (liste non vide)
2. **Validation critique** : `ExecutorService.validate_mission()` vérifie qu'il y a **au moins une tâche** (ligne 122-123 de `executor_service.py`)
3. **Extensions acceptées** : `.yalm`, `.yaml`, `.yalm.yaml` - Le parsing utilise `yaml.safe_load()` qui est flexible sur le format YAML

**Fichiers clés à consulter pour détails :**
- `data/yaml_parser.py` : Parsing et validation YAML
- `domain/services/executor_service.py` : Validation mission et exécution
- `domain/entities/mission.py` : Structure Mission
- `domain/entities/task.py` : Structure Task
- `core/guardrail.py` : Protection des chemins
- `config/settings.yaml` : Configuration globale

---

*Rapport généré le 2025-10-31 pour le Pré-Humain - Compatibilité missions YAML*

