## AIHomeCoder Read-Only Mode Upgrade

- Profiles updated: `config/profiles/qwen_local.yaml`, `config/profiles/deepseek_local.yaml`, `config/profiles/default.yaml`
- Added `modes` block with `read_only` and `write_enabled` definitions
- Settings updated: `config/settings.yaml` → defaults: `profile: qwen_local`, `mode: read_only`
- Guardrail updated: `core/guardrail.py` → added `enforce_task_restrictions`

**Confirmation**: ✅ Profiles and guardrail updated for READ ONLY compliance.

