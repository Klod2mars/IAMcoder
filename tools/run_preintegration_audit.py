from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

import yaml


ROOT = Path(__file__).resolve().parents[1]


def check_knowledge_folder() -> Dict[str, Any]:
    target = ROOT / "core" / "knowledge"
    required = [
        "CLAUDE.md",
        "claude-commands-guide.md",
        "settings.local.json",
    ]
    optional = ["claude_legacy.yaml"]

    exists = target.exists() and target.is_dir()
    files_present: List[str] = []
    missing_required: List[str] = []
    present_optional: List[str] = []

    if exists:
        for name in required:
            if (target / name).exists():
                files_present.append(name)
            else:
                missing_required.append(name)
        for name in optional:
            if (target / name).exists():
                present_optional.append(name)

    status = "OK" if exists and not missing_required else ("MISSING" if not exists else "INCOMPLETE")
    details = {
        "path": str(target.relative_to(ROOT)),
        "exists": exists,
        "required_present": files_present,
        "required_missing": missing_required,
        "optional_present": present_optional,
    }
    return {"status": status, "details": details}


def check_profiles() -> Dict[str, Any]:
    profiles = [
        ROOT / "config" / "profiles" / "default.yaml",
        ROOT / "config" / "profiles" / "qwen_local.yaml",
        ROOT / "config" / "profiles" / "deepseek_local.yaml",
    ]
    results: List[Dict[str, Any]] = []
    ok = True
    for p in profiles:
        item: Dict[str, Any] = {"file": str(p.relative_to(ROOT))}
        if not p.exists():
            item["exists"] = False
            item["valid_yaml"] = False
            ok = False
        else:
            item["exists"] = True
            try:
                with p.open("r", encoding="utf-8") as f:
                    yaml.safe_load(f)
                item["valid_yaml"] = True
            except Exception as e:
                item["valid_yaml"] = False
                item["error"] = str(e)
                ok = False
        results.append(item)
    status = "OK" if ok else "ISSUES"
    return {"status": status, "list": results}


def check_guardrail_settings() -> Dict[str, Any]:
    settings_path = ROOT / "config" / "settings.yaml"
    guardrail_path = ROOT / "core" / "guardrail.py"
    status = "OK"
    details: Dict[str, Any] = {"settings": None, "notes": []}

    mode = None
    try:
        if settings_path.exists():
            with settings_path.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            mode = ((cfg.get("defaults") or {}).get("mode") or "").lower()
            details["settings"] = {
                "path": str(settings_path.relative_to(ROOT)),
                "mode": mode or "(unset)",
            }
        else:
            status = "ISSUES"
            details["notes"].append("config/settings.yaml missing")
    except Exception as e:
        status = "ISSUES"
        details["notes"].append(f"Failed to read settings.yaml: {e}")

    if mode != "read_only":
        status = "ISSUES"
        details["notes"].append("defaults.mode is not 'read_only'")

    if not guardrail_path.exists():
        status = "ISSUES"
        details["notes"].append("core/guardrail.py missing")

    return {"status": status, "details": details}


def render_report(knowledge: Dict[str, Any], profiles: Dict[str, Any], guardrail: Dict[str, Any]) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    knowledge_status = knowledge["status"]
    profiles_status = profiles["status"]
    guardrail_status = guardrail["status"]

    knowledge_details = (
        f"exists={knowledge['details']['exists']}, "
        f"required_present={knowledge['details']['required_present']}, "
        f"required_missing={knowledge['details']['required_missing']}"
    )

    profiles_list_lines = []
    for item in profiles["list"]:
        line = f"- {item['file']}: {'OK' if item.get('exists') and item.get('valid_yaml') else 'ISSUE'}"
        profiles_list_lines.append(line)
    profiles_list = "\n".join(profiles_list_lines)

    settings_mode = (guardrail.get("details") or {}).get("settings", {}).get("mode", "(unknown)")

    diag_parts = []
    if knowledge_status != "OK":
        diag_parts.append("Knowledge folder incomplete or missing.")
    if profiles_status != "OK":
        diag_parts.append("One or more profiles missing or invalid.")
    if guardrail_status != "OK":
        diag_parts.append("Guardrail/settings coherence issue (mode should be read_only).")
    diagnostic_summary = "\n".join([f"- {p}" for p in diag_parts]) or "- All checks passed."

    status_summary = (
        "READY for Claude integration"
        if knowledge_status == profiles_status == guardrail_status == "OK"
        else "ACTION REQUIRED before integration"
    )

    return f"""# 🧩 Audit Pré-Intégration – AIHomeCoder & Claude

**Date :** {date_str}  
**Mode :** Read-Only  
**Analyste :** Qwen Local  

## Résumé
- Dossier mémoire : {knowledge_status}
- Profils : {profiles_status}
- Guardrail cohérent : {guardrail_status}

## Détails
- `core/knowledge/` : {knowledge_details}
- Profils YAML :
{profiles_list}
- Paramètres par défaut : {settings_mode}

## Diagnostic
{diagnostic_summary}

## Recommandations
- Si le dossier `core/knowledge/` est vide, exécuter `install_claude_legacy.yalm`.
- Si des fichiers sont manquants, les copier manuellement avant intégration.
- Rejouer `hello_claude_to_aihomecoder.yalm` après installation complète.

## Statut final
{status_summary}
"""


def main() -> int:
    knowledge = check_knowledge_folder()
    profiles = check_profiles()
    guardrail = check_guardrail_settings()

    report = render_report(knowledge, profiles, guardrail)
    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"audit_pre_integration_claude_{datetime.now().strftime('%Y-%m-%d')}.md"
    out_path.write_text(report, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


