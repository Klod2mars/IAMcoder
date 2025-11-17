# Build Workspace And Flow From Audit

## Résumé
- Implémentation d'un store JSON persistant pour mémoriser le workspace actif, l'historique et l'état auto-run.
- Refactorisation de `core/settings` en fabrique paresseuse acceptant un workspace externe pour initialiser les chemins projet.
- Mise à jour des points d'entrée (`run_mission.py`, CLI, welcome screen) afin de sélectionner et afficher dynamiquement le workspace.
- Ajout d'une validation interactive entre les tâches avec lecture du mode auto-run ainsi qu'un registre minimal de handlers dans l'executor.

## Fichiers créés
- `core/workspace_store.py` : fournit `WorkspaceStore` pour persister le dernier workspace, l'historique (10 entrées) et le drapeau auto-run dans `config/state/workspace.json`.

## Fichiers modifiés
- `core/settings.py` : accepte un `project_root` externe et expose `get_settings()` avec cache par workspace.
- `run_mission.py` : propose la réutilisation du dernier workspace, permet la saisie d'un nouveau chemin et propage le workspace via `cwd`.
- `presentation/welcome_screen.py` : affiche le workspace actif, alerte en absence de sélection et oriente l'utilisateur vers la saisie d'un workspace.
- `domain/services/executor_service.py` : introduit la confirmation conditionnelle des tâches, la lecture du mode auto-run et un registre de handlers par `task_type`.
- `presentation/cli.py` : ouvre les options `--workspace` et `--auto-run`, synchronise le store, initialise les settings sur le workspace et transmet la confirmation au nouvel executor.

## Points d’entrée mis à jour
- `run_mission.py` interroge désormais le store pour rappeler ou enregistrer un workspace externe avant d'exécuter une mission.
- La CLI (`presentation/cli.py`) accepte les options `--workspace` et `--auto-run`, relaie ces informations vers l'executor et consigne le workspace utilisé.
- `presentation/welcome_screen.py` reflète l'état courant du workspace et encourage la saisie d'un nouveau chemin lorsqu'aucun historique n'est disponible.

## Scénarios d’usage
- Utiliser `python run_mission.py` pour sélectionner le dernier workspace, en saisir un nouveau ou revenir au dépôt courant si aucun n'est enregistré.
- Lancer `python main.py run mission.yalm --workspace C:/Projets/Client --auto-run` pour exécuter une mission sur un dépôt client en mode batch sans confirmations.
- Démarrer la CLI sans option pour bénéficier d'un mode interactif demandant la validation de chaque tâche et consignant les décisions dans les logs.

## Prochaines étapes (tests d’intégration, UI de sélection)
- Ajouter des tests d'intégration couvrant la persistance JSON du store et le basculement automatique du workspace dans `core/settings`.
- Tester le flux CLI complet avec différents réglages `--auto-run` afin de valider la confirmation conditionnelle et la gestion des annulations.
- Enrichir l'UI de sélection (welcome screen / CLI) avec un menu listant l'historique des workspaces et des validations de chemins avant exécution.

