# Audit preparatoire – Lecture contextuelle selective

**Date :** 2025-11-01  
**Mission :** aihomecoder_selective_context_audit  
**Mode :** READ_ONLY_ANALYSIS  
**Cadre :** Lecture du codebase sans modification, preparation a une fonction de lecture contextuelle selective.

## Resume executif
- La pile `FileManager` → `YAMLParser` → `TaskLogicHandler` offre deja une separation claire entre lecture disque, parsing et orchestration, ce qui limite les impacts d'une extension orientee lecture contextuelle.
- Le flot mission s'appuie sur `ExecutorService` et `ContextBridge` pour propager mode d'execution, diagnostics et outputs; toute nouvelle logique doit s'y inscrire pour conserver la tracabilite.
- Une nouvelle tache `task_gather_documents` collecte les fichiers meteo (motifs `meteo/weather/climate/soil_temp/halo`), assemble un rapport Markdown dedie et publie diagnostics + outputs via `ContextBridge`.
- La posture de securite repose sur un mode par defaut `read_only` et sur un guardrail qui filtre les chemins sanctuaires et detecte les mots-cles interdits; aucun sandbox supplementaire n'est defini.
- Les points d'injection favorables se situent dans `TaskLogicHandler.execute`, la configuration YAML (`parameters` et `context.variables`) et `ContextBridge.register_output`, tremplins naturels pour une logique `task_gather_documents` ou `contextual_reader`.

## 📂 Modules de lecture et de parsing

### Synthese executive
- La couche `core` encapsule les acces fichiers via `FileManager`, avec verification systematique par `Guardrail`.
- Le parsing YAML produit des entites `Mission` et `Task` en preservant `metadata`, `context`, `outputs` et `post_actions` pour la couche service.
- Les services de domaine orchestrent la logique metier et les outputs sans manipuler directement le systeme de fichiers.

### Details techniques
| Module | Role principal | Structures clefs | Imports clefs |
| --- | --- | --- | --- |
| `core/file_manager.py` | IO securises et filtrage des chemins | `FileManager` (`read_file`, `write_file`, `file_exists`, `list_files`), singleton `file_manager` | `pathlib.Path`, `typing.List`, `core.guardrail.guardrail` |
| `core/guardrail.py` | Protection des sanctuaires et enforcement du mode | `Guardrail` (`is_sanctuary_path`, `check_path`, `filter_allowed_paths`), `_get_current_mode_from_config`, `enforce_task_restrictions`, singleton `guardrail` | `fnmatch`, `pathlib.Path`, `core.settings.settings`, `yaml` (lazy) |
| `data/yaml_parser.py` | Parser strict `*.yalm` et constructeur de missions | `YAMLParser` (`parse_file`, `parse_content`, `create_mission_from_yaml`, `_build_mission`, `validate_yaml_structure`), exception `YAMLParserError` | `yaml.safe_load`, `pathlib.Path`, `domain.entities.Mission/Task`, `core.file_manager` |
| `domain/entities/task.py` | Representation d'une tache et etats | `TaskStatus` (`Enum`), dataclass `Task` (`to_dict`, `from_dict`, validations) | `dataclasses`, `enum.Enum`, `typing.Dict` |
| `domain/services/task_logic_handler.py` | Dispatch logique des taches et generation de rapports | `TaskLogicHandler.execute`, `_build_execution_context`, `_collect_variables`, fonction libre `task_tree_scan` (arborescence + rapports JSON/Markdown) | `pathlib.Path`, `collections.Counter`, `json`, `datetime`, `logging`, `core.file_manager`, `core.guardrail`, `core.context_bridge` |
| `domain/services/executor_service.py` | Orchestration mission/tache et suivi `ContextBridge` | `ExecutorService.execute_mission`, `_execute_task`, `_execute_task_logic`, `validate_mission`, `_update_mission_snapshot`, callbacks de diagnostic | `logging`, `typing.Callable`, `core.context_bridge.ContextBridge`, `core.guardrail.GuardrailError`, `domain.entities`, `TaskLogicHandler` |
| `main.py` | Point d'entree CLI | Ajoute le depot au `sys.path` puis invoque `presentation.cli.main()` | `sys`, `pathlib.Path`, `presentation.cli` |
| `run_mission.py` | Lanceur interactif pour missions locales | `list_yalm_files`, `main` (selection workspace, execution via `subprocess`), archive optionnelle | `os`, `subprocess`, `pathlib.Path`, `core.workspace_store.get_workspace_store` |

## ⚙️ Mecanismes d'execution des taches

### Chaine YAML → Mission → Execution
1. `FileManager.read_file` ouvre le fichier cible en UTF-8 et leve `FileManagerError` si le chemin est absent ou inacessible.
2. `YAMLParser.parse_file` recupere le contenu via `file_manager`, puis `parse_content` (basee sur `yaml.safe_load`) renvoie un dictionnaire ou `{}` selon la charge.
3. `_build_mission` construit une `Mission` : meta enrichie, description fallback, liste de `Task` conservee avec `parameters`, `outputs` et `post_actions`.
4. `ExecutorService.execute_mission` reinitialise le `ContextBridge`, attache la mission, publie un diagnostic de demarrage et gere la confirmation utilisateur (`auto_run`).
5. Pour chaque tache, `_execute_task` applique `enforce_task_restrictions`, publie diagnostics, met a jour les statuts (`IN_PROGRESS`, `COMPLETED`, `FAILED`, `CANCELLED`) et capture les erreurs.
6. `_execute_task_logic` delegue a `TaskLogicHandler.execute`, qui branche vers `_analyze_workspace`, `_generate_markdown`, `task_tree_scan` ou renvoie un message informatif pour les types inconnus.
7. Les outputs de tache sont ecrits via `file_manager.write_file`, verifies par `guardrail.check_path`, puis declares via `ContextBridge.register_output` afin de suivre les artefacts generes.

### Points focaux par fonction ciblee
- **`FileManager.read_file` / `list_files`** : normalise les chemins `Path`, encapsule les erreurs `PermissionError`, applique `guardrail.filter_allowed_paths` pour exclure les sanctuaires de tout listing.
- **`YAMLParser.parse_content`** : parser minimaliste `yaml.safe_load` (default `{}`) qui separe les exceptions syntactiques (`YAMLError`) des violations d'IO.
- **`YAMLParser.validate_yaml_structure`** : verifie sections obligatoires, type liste des taches, contenu non vide des instructions textuelles et signale les anomalies par index.
- **`ExecutorService._execute_task_logic`** : delegue a `TaskLogicHandler` et encapsule les exceptions en message `[ERROR]`, evitant un crash et conservant la progression mission.
- **`TaskLogicHandler`** : `execute` mappe `task_type` vers les implementions dediees, `_build_execution_context` fusionne `mission.metadata["context"]`, variables et outputs declares, `task_tree_scan` realise le parcours de workspace avec filtrage guardrail, generation Markdown et enregistrement dans `ContextBridge`.
- **`ContextBridge.register_output`** : normalise les destinations declarees, met a jour le statut (`created` par defaut) et fusionne les metadonnees (mission, task, format) avant de les exposer via `export_snapshot` pour maintenir une traque des artefacts.
- **`task_gather_documents`** : reutilise la meme fabrique de contexte pour rechercher les fichiers meteo (patterns configurables), lire leur contenu via `FileManager` et produire `reports/gather_meteo_docs.md` avec diagnostics `started/document_collected/completed` et enregistrement guardrailise.

## 🔒 Securite et modes d'acces

### Observations principales
- `config/settings.yaml` fixe `defaults.mode = read_only` et declare des `sanctuary_paths` (dossiers/projets sensibles) charges par `core.settings.Settings`.
- `Guardrail` combine filtrage de patterns (`fnmatch`) et detection de mots-cles (`write/delete/move`) via `enforce_task_restrictions` pour bloquer les consignes dangereuses en mode `read_only`.
- `FileManager.write_file` et `modules.output_handler` passent systematiquement par `guardrail.check_path` avant toute ecriture disque.
- Aucun mecanisme de sandbox OS n'est implemente; la protection repose sur les patterns de fichiers et le respect des mots-cles.

### Detail des protections
- `core/guardrail.Guardrail` charge la liste des sanctuaires depuis `settings`, expose `filter_allowed_paths` et enregistre les motifs responsables via `_find_matching_pattern` pour diagnostiquer les blocages.
- `_get_current_mode_from_config` lit `config/settings.yaml` pour determiner le mode actif si non fourni par `ContextBridge`; fallback `write_enabled` assure resilence.
- `ExecutorService._execute_task` publie un diagnostic `executor.task` `blocked` lorsque `GuardrailError` est leve, ce qui facilite les audits et retours utilisateur.
- `modules/output_handler` detecte le mode `read_only` dans `mission.metadata["context"]`, tente d'ecrire des outputs "raw" si fournis, sinon applique le pipeline standard avec guardrail pre-ecriture.
- `core.workspace_store` journalise le workspace actif et l'option `auto_run`, elements relies par `ContextBridge` pour maintenir la coherence du mode exec/securite.
- `OutputHandler.execute_post_actions` bloque toute action contenant des mots-clés destructifs (`write`, `delete`, `move`, ...) en mode `read_only`, publie des diagnostics `post_action_blocked` et garantit ainsi que les post-actions declaratives restent passives.

## 🧩 Points d'integration possibles

### Domain / Application
- La branche `task_gather_documents` est active dans `TaskLogicHandler.execute` et reutilise `_build_execution_context` pour resoudre workspace, variables et destinations.
- Ajouter un enregistrement structure (ex: JSON, Markdown) via `ContextBridge.register_output` et diagnostics dedies, assurant la coherence avec les autres taches.
- Exploiter les variables resolues (`_collect_variables`) pour piloter des filtres (patterns, profondeur, extensions) de lecture selective et nourrir une future memoire tampon contextualisee.

### Core / Infrastructure
- Capitaliser sur `FileManager` pour toute lecture selective (filtres, listage, lecture partielle) et conserver `guardrail.check_path` pour les nouveaux rapports ou caches.
- Exploiter `ContextBridge.export_snapshot` pour stocker l'etat de lecture (fichiers consultes, heuristiques), accessible a d'autres couches sans IO supplementaire.

### Presentation
- `presentation.cli.run` peut exposer une option `--contextual-reader` ou des indicateurs verbose relies aux diagnostics `ContextBridge`, sans modifier la logique de base.
- `run_mission.py` pourrait proposer la mission enrichie avec la nouvelle tache (auto-selection) ou pre-remplir un workspace cible en reutilisant `workspace_store`.

### Donnees & configuration
- `YAMLParser._build_mission` accepte deja `parameters` et `output` par tache; documenter un schema `task_type: contextual_reader` avec `parameters.sources` et `parameters.filters` suffira pour alimenter la nouvelle logique.
- `FlexYALMParser` peut fournir des diagnostics additionnels (section `diagnostics["tasks"]`) indiquant les inputs attends par la nouvelle tache, sans briser la compatibilite existante.

---

_Pre-Humain — Audit preparatoire a la fonction de lecture contextuelle selective._

