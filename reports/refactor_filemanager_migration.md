# Migration des écritures vers FileManager

## Objectif

Sécuriser toutes les écritures disque critiques en passant par `core.file_manager.file_manager` et le guardrail associé, conformément au plan `migrate_writes_to_filemanager`.

## Fichiers mis à jour

- `domain/services/task_logic_handler.py`
  - Les exports JSON et Markdown utilisent désormais `guardrail.check_path()` suivi de `file_manager.write_file()`.
  - Les données JSON sont sérialisées dans une structure prête à écrire avant de passer au gestionnaire de fichiers.

- `modules/output_handler.py`
  - Toutes les écritures d'outputs (y compris les modes « raw ») passent par `guardrail.check_path()` puis `file_manager.write_file()`.
  - Intégration avec `ContextBridge` pour enregistrer chaque output créé et produire un diagnostic correspondant.

- `presentation/logger.py`
  - La persistance Markdown s'appuie sur `file_manager.write_file(..., append=True)` avec vérification guardrail.

- `core/file_manager.py`
  - Ajout d'un paramètre `append` pour gérer les écritures cumulatives de manière sécurisée.

## Impacts

- La vérification des chemins sanctuarisés est systématique avant toute écriture disque.
- Les modules consommateurs n'ont plus besoin de gérer directement les ouvertures de fichiers.
- Le support de l'append permet de préserver les journaux Markdown existants.

## Tests

La suite de tests automatisés a été exécutée après migration :

```bash
venv\Scripts\python -m pytest tests
```

Résultat : **succès (10 tests)**.


