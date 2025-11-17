# Guardrail Reinforcement Report

## Contexte

Dans le cadre du projet `flex_yalm_refactor`, nous avons renforcé l'application des guardrails afin d'empêcher toute action non autorisée lorsque le système fonctionne en mode `read_only` et, de manière plus générale, de tracer les diagnostics liés aux restrictions de sécurité.

## Modifications principales

- **Exécution des missions** (`domain/services/executor_service.py`)
  - Intégration du nouveau `ContextBridge` pour suivre le mode d'exécution et exposer un instantané complet dans les métadonnées de la mission.
  - Appel systématique de `enforce_task_restrictions()` avant chaque tâche. En cas de violation, la tâche est immédiatement bloquée, journalisée dans les diagnostics et signalée via les callbacks.
  - Publication de diagnostics détaillés (`mission` et `task`) pour chaque évènement clé : démarrage, réussite, annulation, échec ou blocage par guardrail.

- **Post-actions** (`modules/output_handler.py`)
  - Détection proactive des actions contenant les mots-clés sensibles (`write`, `delete`, `remove`, `move`, `touch`, `rm`, `mv`) lorsque le mode `read_only` est actif.
  - Blocage explicite avec une `OutputHandlerError` et journalisation via `ContextBridge` lorsque l'une de ces actions est détectée.
  - Les post-actions sûres continuent d'être exécutées et enregistrées dans les diagnostics.

- **ContextBridge** (`core/context_bridge.py`)
  - Ajout d'accesseurs dédiés (`get_auto_run()`, `get_mode()`) pour faciliter l'application des guardrails dans l'executor et les modules de sortie.

## Diagnostics et traçabilité

Les diagnostics publiés par `ContextBridge` permettent désormais de suivre :

- Chaque transition de statut des tâches et de la mission.
- Les blocages provoqués par les guardrails avec le mode actif et le mot-clé incriminé.
- L'exécution ou le blocage des post-actions.

Ces informations sont disponibles via `mission.metadata["context_bridge"]` et peuvent être exportées pour audit.

## Vérifications

- Suite au renforcement des guardrails, la suite de tests automatisés a été exécutée :

  ```bash
  venv\Scripts\python -m pytest tests
  ```

- Résultat : **10 tests passés avec succès**.

## Points d'attention

- Les missions ou post-actions exécutées en mode `read_only` doivent être formulées de façon à éviter toute consigne de modification (écriture, déplacement ou suppression de fichiers).
- Les diagnostics additionnels augmentent légèrement le volume des métadonnées mission. Les consommateurs en aval doivent s'assurer de gérer ces structures JSON.


