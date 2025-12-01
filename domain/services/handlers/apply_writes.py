# domain/services/handlers/apply_writes.py
from pathlib import Path
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

from core.file_manager import file_manager
from core.guardrail import guardrail
from domain.services.helpers import (
    _pick_string,
    _stringify_content,
    _to_bool,
    _safe_write_text,
)

logger = logging.getLogger(__name__)


def _resolve_workspace_path(candidate: Optional[str], context: Dict[str, Any]) -> Path:
    ws_candidate = _pick_string(candidate, context.get("workspace_path"), context.get("workspace"), ".")
    return Path(ws_candidate).expanduser().resolve()


def _read_text(fm, path_obj: Path, encoding: str = "utf-8") -> Optional[str]:
    try:
        # Prefer file_manager API if present
        if hasattr(fm, "read_file"):
            return fm.read_file(str(path_obj))
        # fallback to Path
        return path_obj.read_text(encoding=encoding)
    except Exception:
        return None


def task_apply_writes(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Handler minimaliste pour appliquer des écritures sur le workspace.
    - params: dict, attend instructions.writes: list[ {file, content, append, create_backup, encoding} ]
    - context: dict, peut contenir 'workspace'|'workspace_path', 'file_manager', 'guardrail', 'output'
    Retourne un status string et écrit un rapport JSON (best-effort).
    """
    fm = context.get("file_manager") or file_manager
    guard = context.get("guardrail") or guardrail
    workspace_path = _resolve_workspace_path(params.get("workspace_path") or params.get("workspace"), context)

    instructions = params.get("instructions") or {}
    writes = instructions.get("writes") or []
    dry_run = bool(params.get("dry_run", False))

    # resolve output path for report
    out_path = _pick_string(params.get("output"), params.get("report_path"), context.get("output"))
    if not out_path:
        out_path = "reports/apply_writes.json"

    report = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "workspace": str(workspace_path),
        "entries": [],
        "status": None,
    }

    errors: List[str] = []
    applied_count = 0
    simulated_count = 0

    for item in writes:
        file_rel = item.get("file")
        entry: Dict[str, Any] = {"file": file_rel}
        if not file_rel:
            entry["error"] = "missing file"
            report["entries"].append(entry)
            continue

        # Resolve target path
        try:
            target_path = Path(file_rel)
            if not target_path.is_absolute():
                target_path = workspace_path.joinpath(target_path)
            target_path = target_path.resolve()
            entry["target"] = str(target_path)
        except Exception as e:
            entry["error"] = f"path_resolve_error: {str(e)}"
            report["entries"].append(entry)
            errors.append(str(e))
            continue

        content_raw = item.get("content")
        content = _stringify_content(content_raw)
        if content is None:
            entry["error"] = "no_content"
            report["entries"].append(entry)
            continue

        append = _to_bool(item.get("append", False))
        create_backup = _to_bool(item.get("create_backup", False))
        encoding = item.get("encoding") or "utf-8"

        # Read existing content (best-effort)
        old_content = _read_text(fm, target_path, encoding=encoding)

        # Dry-run: only check that a change would happen
        if dry_run:
            would_change = (old_content is None) or (("" if append else "") + content) != (old_content or "")
            entry["would_change"] = bool(would_change)
            simulated_count += 1 if would_change else 0
            report["entries"].append(entry)
            continue

        # Real write
        try:
            # create backup if requested
            if create_backup and old_content is not None:
                try:
                    backup_dir = workspace_path.joinpath("backups")
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    backup_name = f"{target_path.name}.bak_{ts}"
                    backup_path = backup_dir.joinpath(backup_name)
                    if hasattr(fm, "write_file"):
                        fm.write_file(str(backup_path), old_content)
                    else:
                        backup_path.write_text(old_content, encoding=encoding)
                    entry["backup"] = str(backup_path)
                except Exception as be:
                    logger.warning("Failed to create backup for %s: %s", target_path, be)
                    entry.setdefault("warnings", []).append(f"backup_failed:{str(be)}")

            # Perform write/append
            try:
                _safe_write_text(fm, target_path, content, append=append, encoding=encoding)
                entry["applied"] = True
                applied_count += 1
            except Exception as we:
                entry["error"] = f"write_error: {str(we)}"
                errors.append(str(we))
        except Exception as e:
            entry["error"] = f"unexpected_error: {str(e)}"
            errors.append(str(e))

        report["entries"].append(entry)

    # determine status
    if dry_run:
        report["status"] = "dry_run_ok" if simulated_count > 0 else "dry_run_no_change"
    else:
        report["status"] = "applied" if applied_count > 0 else "no_change"

    # write report best-effort
    try:
        if hasattr(fm, "write_file"):
            fm.write_file(out_path, json.dumps(report, indent=2, ensure_ascii=False))
        else:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write apply_writes report: %s", e)

    if errors and dry_run:
        return f"[WARN] Dry-run completed with {len(errors)} error(s)"
    return f"[OK] Writes {'simulated' if dry_run else 'applied'}: {applied_count if not dry_run else simulated_count}"
