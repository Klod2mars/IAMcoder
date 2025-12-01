# domain/services/handlers/yaml_apply.py
from pathlib import Path
import json
import datetime
from typing import Any, Dict
import logging

from core.file_manager import file_manager
from core.guardrail import guardrail

logger = logging.getLogger(__name__)


def apply_yaml_replacements(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Minimal YAML-driven replacer used by TaskLogicHandler.
    - params: dict with keys instructions.replacements (list), dry_run (bool), create_backup (bool)
    - context: execution context (workspace_path, file_manager, guardrail, ...)
    Returns a status string.
    Writes a JSON report to output path (params.output or params.report_path or reports/last_report.json).
    """
    fm = context.get("file_manager") or file_manager
    guard = context.get("guardrail") or guardrail
    workspace_path = Path(context.get("workspace_path") or context.get("workspace") or ".").resolve()

    instructions = params.get("instructions") or {}
    replacements = instructions.get("replacements") or []
    dry_run = bool(params.get("dry_run", False))
    create_backup = bool(params.get("create_backup", False))

    # resolve output report path
    out_path = None
    if isinstance(params.get("output"), str):
        out_path = params.get("output")
    elif isinstance(params.get("report_path"), str):
        out_path = params.get("report_path")
    else:
        ctx_out = context.get("output")
        if isinstance(ctx_out, str):
            out_path = ctx_out
    if not out_path:
        out_path = "reports/last_report.json"

    report = {"status": None, "entries": []}
    errors = []

    for item in replacements:
        file_rel = item.get("file")
        anchor = item.get("anchor") or ""
        after = item.get("after") or ""
        include_anchor = bool(item.get("include_anchor", False))

        entry = {"file": file_rel, "anchor": anchor, "occurrences": 0, "found": False}
        if not file_rel:
            entry["error"] = "missing file"
            report["entries"].append(entry)
            continue

        target_path = Path(workspace_path).joinpath(file_rel)
        try:
            content = fm.read_file(str(target_path))
        except Exception as e:
            entry["error"] = f"read_error: {str(e)}"
            report["entries"].append(entry)
            errors.append(str(e))
            continue

        occ = content.count(anchor) if anchor else 0
        entry["occurrences"] = occ
        entry["found"] = occ > 0

        if occ and not dry_run:
            try:
                # create backup if requested
                if create_backup:
                    backup_dir = Path(workspace_path).joinpath("backups")
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    backup_name = f"{Path(file_rel).name}.bak_{ts}"
                    backup_path = backup_dir.joinpath(backup_name)
                    fm.write_file(str(backup_path), content)
                    entry["backup"] = str(backup_path)

                # apply replacement
                if include_anchor:
                    new_content = content.replace(anchor, anchor + after)
                else:
                    new_content = content.replace(anchor, after)

                fm.write_file(str(target_path), new_content)
                entry["applied"] = True
            except Exception as e:
                entry["error"] = f"apply_error: {str(e)}"
                errors.append(str(e))

        report["entries"].append(entry)

    # determine status
    if dry_run:
        report["status"] = "dry_run_ok" if any(e.get("found") for e in report["entries"]) else "dry_run_no_change"
    else:
        report["status"] = "applied" if any(e.get("applied") for e in report["entries"]) else "no_change"

    # write report (best-effort)
    try:
        fm.write_file(out_path, json.dumps(report, indent=2, ensure_ascii=False))
    except Exception as e:
        logger.error("Failed to write yaml_apply report: %s", e)

    if errors and dry_run:
        return f"[WARN] Dry-run completed with {len(errors)} error(s)"
    return f"[OK] Replacements {'simulated' if dry_run else 'applied'}: {len(replacements)}"
