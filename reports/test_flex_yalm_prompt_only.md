# Test FlexYALMParser – Prompt Only

## Objectif

Valider la prise en charge d'un YAML minimaliste contenant uniquement une mission implicite afin de garantir le fonctionnement du mode `prompt_only`.

## Scénario testé

```yaml
mission: "Audit rapide du projet actuel"
output: "reports/audit_auto.md"
mode: "read_only"
```

1. Chargement du contenu via `FlexYALMParser.parse_content(...)`.
2. Construction de la mission utilisant les nouvelles stratégies de fallback (`mission`, `prompt`, `description`, etc.).
3. Vérification des diagnostics fournis par `ContextBridge`.

## Résultats attendus

- `mission.name` conserve la valeur par défaut dérivée (`mission_YYYYMMDDHHMMSS`).
- `mission.tasks` contient une seule tâche :
  - `name`: `task_1`
  - `goal`: `Audit rapide du projet actuel`
- Diagnostics du parser :
  - `mode`: `prompt_only`
  - `fallback_chain`: `[{'source': 'root.mission', 'count': 1}]`
  - `provided_sections`: `['meta']` si des métadonnées minimales sont ajoutées ou `['<string>']` sinon.

## Vérifications automatisées

Un test dédié couvre ce scénario (`tests/test_flex_yalm_parser.py::test_parse_prompt_only_string`).

Commande d'exécution :

```bash
venv\Scripts\python -m pytest tests/test_flex_yalm_parser.py::test_parse_prompt_only_string
```

Résultat : **succès**.


