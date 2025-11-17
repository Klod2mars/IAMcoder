# Audit – Activation fiable de `task_tree_scan`

## Résumé exécutif
- La mission YAML `Audit Tree Permacalendar V2.yalm` encode l’intention `tree_scan` via la clé `id` sans expliciter `task_type`/`type`.
- `YAMLParser._build_mission` ignore `id`; les tâches héritent du type par défaut `generic`, ce qui déroute le dispatch du `TaskLogicHandler`.
- L’exécution produit le message générique « sans logique spécifique » et aucun rapport n’est généré, bien que toutes les autres données (paramètres, contexte, variables) soient correctement transportées.
- Le correctif minimal consiste à relier `id` → `task_type` (et idéalement `name`) lors du parsing, assorti d’une validation qui signale les tâches restées `generic`.

## Chaîne YAML → Mission → Task → Handler
| Étape | Entrée principale | Sortie obtenue | Observation |
| --- | --- | --- | --- |
| 1. Mission YAML | `tasks[0].id = "tree_scan"`<br>`goal`, `parameters`, `output` | Données brutes | L’intention métier est implicite, encapsulée dans `id`.
| 2. `YAMLParser._build_mission` | Dictionnaire de tâche | `Task(name="task_1", task_type="generic", parameters={...})` | `id` n’est pas consommé; `task_type` reste à la valeur par défaut.
| 3. `Mission` | Liste de `Task` | Mission en mémoire | La tâche est ajoutée avec `task_type="generic"`.
| 4. `ExecutorService._execute_task` | Mission & tâche | Delegation à `TaskLogicHandler.execute` | Aucun contrôle sur la cohérence du `task_type`.
| 5. `TaskLogicHandler.execute` | `task.task_type == "generic"` | Retour `[INFO] Tâche ... sans logique spécifique` | La branche `tree_scan` n’est jamais atteinte.

## Propagation de `task_type`
- Source attendue : `task_data.type` ou `task_data.task_type` (ou `id` dans le YAML étudié).
- Parsing : faute de champ explicite, `_build_mission` applique `task_type = "generic"`.
- Entité : `Task.task_type` conserve cette valeur jusqu’à l’exécution.
- Dispatch : `TaskLogicHandler.execute` compare `task.task_type.lower()` à `{"analysis", "report_generation", "tree_scan", "tree", "setup"}`.
- Impact : toute mission décrivant `tree_scan` via `id` est neutralisée; la logique dédiée n’est jamais déclenchée.

## Table de correspondance YAML → `Task`
| Champ YAML | Destination actuelle | Statut | Commentaire |
| --- | --- | --- | --- |
| `tasks[].name` | `Task.name` (fallback `task_{index}`) | OK | Absent dans la mission cible, le nom devient `task_1`.
| `tasks[].id` | **Non utilisé** | KO | Perdu lors du parsing; devrait alimenter `task_type` et/ou `name`.
| `tasks[].goal` | `Task.goal` | OK | But de la tâche correctement copié.
| `tasks[].type` / `task_type` | `Task.task_type` | OK quand présent | Défaut `generic` si absent.
| `tasks[].parameters` | `Task.parameters` | OK | Contient `destination`, `extensions`, `depth_limit`, etc.
| `tasks[].output` | **Ignoré** | KO | Non conservé dans `Task.parameters`; seul le contexte mission (`metadata["outputs"]`) persiste.
| `meta.context.workspace` | `Mission.metadata["context"]` → `_build_execution_context` | OK | Permet de résoudre le workspace dans `task_tree_scan`.
| `meta.context.variables` | Fusionné par `_collect_variables` | OK | `REPORT_PATH` est disponible pour les substitutions.

## Points de rupture identifiés
1. **Absence de mappage `id` → `task_type`** : la tâche est classée `generic`, bloquant le dispatch.
2. **Perte du champ `output` côté tâche** : même après correction du type, la configuration spécifique à la tâche ne rejoint jamais `task_tree_scan` (tout dépend d’un fallback mission ou de paramètres directs).
3. **Manque de garde-fou** : aucune validation (parser ou executor) ne signale qu’une tâche déclarée `tree_scan` reste `generic`.

## Recommandations prioritaires
1. **Parser** – Étendre `_build_mission` pour :
   - utiliser `task_data.get("id")` comme fallback pour `task_type` (et pour `name` si `name` manquant) ;
   - intégrer `task_data.get("output")` dans `parameters["output"]` pour la cohérence avec `_build_execution_context`.
2. **Validation** – Ajouter un contrôle léger (ex. `ExecutorService.validate_mission` ou parser) qui alerte lorsqu’une tâche reste `generic` alors qu’un identifiant connu (`id`, `output.destination`, etc.) est fourni.
3. **Observabilité** – Journaliser `task.name` et `task.task_type` avant dispatch pour détecter rapidement les types inattendus.
4. **Mission YAML (mesure immédiate)** – À court terme, documenter l’obligation d’ajouter `task_type: "tree_scan"` dans les missions existantes jusqu’au déploiement du fix parser.

## Fichiers à modifier (commentaire)
- `data/yaml_parser.py` – Injecter les fallbacks `id` → `task_type`/`name` et préserver `output` dans les paramètres de tâche.
- `domain/services/executor_service.py` – Compléter `validate_mission` pour signaler les tâches `generic` suspectes (optionnel mais recommandé pour détecter les régressions).
- `domain/services/task_logic_handler.py` – Ajouter un log/debug avant dispatch ou un fallback tempéré (`if task.task_type == "generic" and task.parameters.get("id") == "tree_scan"`).

## Risques & effets de bord
- **Compatibilité YAML** : mapper `id` → `task_type` peut modifier le comportement de missions qui utilisaient `id` pour un autre sens. Aucun YAML du dépôt ne déclare `id`, et la mission incriminée attend explicitement ce lien → risque faible.
- **Propagation de `output`** : intégrer `output` dans les paramètres pourrait impacter des tâches qui exploitent déjà `parameters["output"]`. Vérifier l’absence d’usage concurrent avant déploiement.
- **Validation supplémentaire** : un check trop strict pourrait bloquer des tâches légitimement `generic`. S’assurer qu’il reste informatif (warning) plutôt que bloquant.

## Observations complémentaires
- Le fichier de log mentionné dans le mandat (`logs/session_20251101_185154.md`) est absent du dépôt, rendant la reproduction exacte impossible.
- La mission `Audit Tree Permacalendar V2.yalm` est stockée hors du workspace (`../permacalendarv2/`), prévoir une synchronisation si l’outillage doit y accéder automatiquement.
- `task_tree_scan` lui-même est fonctionnel : une fois le `task_type` correct injecté, la génération de rapport utilise `parameters.destination`, `extensions` et résout `${REPORT_PATH}` grâce aux variables de contexte.

