# Audit Flex YALM Parser – 2025-11-01

## Résumé exécutif
- La chaîne actuelle repose sur `data/yaml_parser.py` qui exige les sections `meta` et `tasks`, puis construit des entités `Mission`/`Task` strictes avant exécution par `ExecutorService`.
- Cette rigidité empêche l'interprétation de prompts courts ou de YAML partiels, alors que les utilisateurs réclament des instructions plus naturelles.
- Le nouveau module `data/flex_yalm_parser.py` introduit un parsing tolérant, capable de synthétiser des tâches à partir d'un simple prompt, tout en produisant une analyse diagnostique de la structure reçue.
- Un plan de ContextBridge harmonise parser, stockage workspace et gestion des outputs pour conserver le contexte sans manipulations manuelles.
- Une checklist de guardrails garantit que ces assouplissements respectent les politiques read-only et la protection des sanctuaires.

## Chaîne de parsing actuelle
```91:138:data/yaml_parser.py
        meta = data.get("meta", {})
        mission_name = meta.get("project_name") or meta.get("mission_id") or "Unnamed Mission"
        # ... existing code ...
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

| Section YAML | Champ | Mission/Task cible | Rigidité observée |
| --- | --- | --- | --- |
| `meta` | `project_name` ou `mission_id` | `Mission.name` (obligatoire) | `Mission` lève `ValueError` si vide ; fallback « Unnamed Mission » empêche validation métier cohérente. |
| `meta` | `description` | `Mission.description` | Vide si absent, ce qui réduit la traçabilité lors de l'exécution. |
| `meta.*` | `version`, `author`, `architecture`, `language` | `Mission.metadata` | Copiés tels quels sans contrôle de cohérence. |
| `tasks[]` | `name` | `Task.name` | `Task` exige un nom non vide ; généré sinon, mais impose présence du tableau `tasks`. |
| `tasks[]` | `goal` | `Task.goal` | Champ requis : absence → exception en `Task.__post_init__`. |
| `tasks[]` | `type`/`task_type` | `Task.task_type` | Facultatif, mais la logique attend un libellé. |
| `tasks[]` | `parameters` | `Task.parameters` | Dictionnaire libre ; aucune normalisation. |

Les validations additionnelles (`YAMLParser.validate_yaml_structure`) rejettent tout fichier sans `meta` + `tasks`, et `ExecutorService.validate_mission` refuse les missions sans tâches ni noms.

## Points de rigidité identifiés
- **Couplage dur meta/tasks** : absence d'une section invalide entièrement la mission, empêchant l'usage d'un simple prompt.
- **Validation double** : parser + `ExecutorService` imposent les mêmes contraintes, ce qui multiplie les rejets au lieu de proposer des corrections.
- **Absence de diagnostic** : aucun retour détaillé sur les champs manquants, rendant l'expérience utilisateur opaque.
- **Pas de mode entrée libre** : impossible d'encoder « audit prompt-only » sans créer de tâches artificielles à la main.

## Modèle adaptatif proposé (`data/flex_yalm_parser.py`)
- Synthèse automatique de tâches depuis `prompt`, `instructions`, listes ou simples chaînes.
- Génération d'un `meta.project_name` propre via slug et timestamp de secours.
- Injection d'un bloc `metadata.flex_parser` avec mode détecté, sections fournies, warnings et source.
- Conservation des sections optionnelles (`context`, `outputs`, `post_actions`) pour un chaînage inchangé avec OutputHandler.
- Méthode `get_last_diagnostics()` pour exposer les warnings à la couche présentation.

Modes de parsing pris en charge :
- `strict` : YAML complet `meta + tasks` (identique à l'existant).
- `meta_plus_prompt` : `meta` + `prompt` → une tâche synthétique.
- `flex_meta` : `meta` + instructions implicites (`instructions`, `steps`).
- `prompt_list` : racine liste de chaînes → séquence de tâches générées.
- `prompt_only` : chaîne ou clé `prompt` seule.

## Prototype YAML ultra-simplifié (3 lignes)
Fichier `flex_prompt_ultra_simple.yalm` :

```yaml
meta: { project_name: "audit_flex_prompt" }
prompt: "Examiner la robustesse du parser et proposer un mode prompt-only."
mode: prompt_only
```

Ce format minimal est accepté par `FlexYALMParser` et produit une mission d'une tâche avec diagnostics `prompt_only`.

## ContextBridge (plan d'intégration)
- **Entrée** : `FlexYALMParser` fournit `mission.metadata.flex_parser` (mode, warnings, source).
- **Pivot** : nouveau composant `ContextBridge` (à créer) orchestre :
  - stockage auto dans `WorkspaceStore` (`last_workspace`, `auto_run`),
  - synchronisation des outputs déclarés avec `OutputHandler`,
  - publication des diagnostics au front (CLI / UI Diff).
- **Sortie** : normalise les chemins et rattache les fichiers générés à `mission.metadata` pour export JSON.

Étapes recommandées :
1. Ajouter `ContextBridge` dans `domain/services` avec interfaces vers `workspace_store`, `output_handler` et parser.
2. Étendre l'UI (`presentation/welcome_screen` ou CLI) pour afficher warnings du parser.
3. Prévoir un cache JSON (ex. `config/state/mission_snapshot.json`) pour réimporter le contexte.

## Sécurité et guardrails
- Voir `reports/flex_yalm_guardrails_checklist.md` pour la matrice complète.
- Les opérations d'écriture passent toujours par `file_manager.write_file`, donc `Guardrail.check_path` reste appliqué.
- Le mode `read_only` existant (`guardrail.enforce_task_restrictions`) n'est pas contourné : les instructions synthétiques conservent le texte d'origine.

## Recommandations finales
- Intégrer `FlexYALMParser` derrière une feature flag dans `main.py`/`run_mission.py`.
- Ajouter des tests unitaires ciblés (`tests/test_flex_yalm_parser.py`) couvrant les cinq modes ci-dessus.
- Documenter dans `docs/AIHomeCoder_FormatNotice.md` la nouvelle mini-syntaxe.
- Implémenter `ContextBridge` avant d'automatiser l'import/export de missions.


