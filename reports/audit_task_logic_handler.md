# 🔍 Audit Task Logic Handler — Plan d’Insertion
**Date :** 2025-11-01

## Emplacement des points d’injection
- `ExecutorService._execute_task_logic` est le point de contrôle central pour détourner l’exécution réelle des tâches ; il suffit d’y déléguer vers un `TaskLogicHandler` externe.
- Le registre `_handler_registry` peut être remplacé par un registre fourni par le handler (pattern stratégie), idéalement injecté via le constructeur de `ExecutorService` ou par une méthode `register_handler`.
- Les hooks `on_task_started`, `on_task_completed`, `on_task_failed`, `on_mission_completed`, `on_mission_failed` permettent de relayer l’état vers la présentation ; le handler peut les consommer pour enrichir les métadonnées.
- `Mission.metadata` et `Task.parameters` offrent un espace pour transmettre des informations supplémentaires (modèle IA, chemins de fichiers) sans casser les entités.
- `WorkspaceStore` fournit l’état `auto_run` : si le handler déclenche des confirmations spécifiques, il faut veiller à l’utiliser plutôt que d’introduire un nouveau mécanisme parallèle.

## Dépendances nécessaires
- Couche domaine : `Mission`, `Task`, `MissionStatus`, `TaskStatus` pour créer/mettre à jour les états.
- Couche core : `core.workspace_store.WorkspaceStore` pour respecter les règles d’exécution interactive vs automatique.
- Couche data : `data.ai_connector.AIConnector` comme passerelle IA réutilisable par le handler pour traiter les tâches d’analyse ou de génération.
- Couche modules : `modules.output_handler.OutputHandler` si le handler doit orchestrer la production d’artefacts intermédiaires.
- Gestion des exceptions personnalisées (`AIConnectorError`, `OutputHandlerError`) afin de remonter des erreurs métiers cohérentes jusqu’au `ExecutorService`.

## Méthodes à surcharger
- Introduire `ExecutorService.set_handler(handler: TaskLogicHandler)` pour enregistrer un orchestrateur externe tout en conservant la logique actuelle comme fallback.
- Déplacer les implémentations `_handle_*` vers le `TaskLogicHandler` et ne conserver que la délégation dans `_execute_task_logic`.
- Étendre `validate_mission` pour déléguer au handler la validation de nouveaux `task_type` ou de paramètres obligatoires.
- Ajouter une méthode `TaskLogicHandler.before_task(task, mission)` / `after_task` pour intégrer des effets de bord contrôlés (journalisation, stockage de contexte) tout en s’appuyant sur les hooks existants.

## Risques d’effets de bord
- Rupture de compatibilité : remplacer `_handler_registry` sans fournir de handlers par défaut pourrait faire échouer les tests (`tests/test_executor_service.py`).
- Gestion des exceptions : un handler qui laisse passer des exceptions non capturées transformera brutalement la tâche en `FAILED`; il faut définir une politique de gestion et de journalisation claire.
- Performance : l’ajout d’appels réseau (Ollama, API externes) dans la boucle séquentielle peut rallonger considérablement l’exécution sans mécanisme de timeout personnalisé.
- Cohérence des états : toute mise à jour directe des entités en dehors de l’API `ExecutorService` doit respecter les transitions (`PENDING` → `IN_PROGRESS` → `COMPLETED/FAILED`) pour ne pas corrompre les rapports.
- Tests : introduire un handler configurable nécessite des doubles de test (mocks/stubs) pour conserver la couverture actuelle et garantir un comportement déterministe.


