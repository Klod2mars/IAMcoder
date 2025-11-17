# Flex YALM Guardrails Checklist

| Domaine | Risque | Mesure de contrôle | Statut |
| --- | --- | --- | --- |
| Sanctuaires fichiers | Écriture hors périmètre | `file_manager.write_file` appelle `guardrail.check_path` avant toute écriture. | ✅ En place |
| Mode `read_only` | Génération d'instructions interdites | `guardrail.enforce_task_restrictions` reste exécuté sur le texte initial des tâches synthétisées. | ✅ Compatible |
| Métadonnées mission | Fuite d'informations | `FlexYALMParser` encapsule les diagnostics dans `metadata.flex_parser` sans exposer de chemins sensibles. | ✅ Conforme |
| Historique workspace | Corruption `workspace.json` | `ContextBridge.set_workspace` délègue à `WorkspaceStore.set_workspace` (idempotent, historique borné). | ✅ En place |
| Outputs déclarés | Écriture vers destinations non sûres | `OutputHandler` vérifie `guardrail.check_path` avant `file_manager.write_file` et journalise via ContextBridge. | ✅ En place |
| Post-actions | Exécution non sécurisée | Blocage des actions contenant `write/delete/move` en mode `read_only`, diagnostics ContextBridge. | ✅ Renforcé |
| Logs diagnostics | Explosion volumétrique | Rotation 2 Mo / 5 fichiers avec filtrage par niveau (`set_level`). | ✅ En place |

Légende : ✅ contrôle en place, 🔄 action requise avant déploiement.


