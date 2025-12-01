# domain/services/handlers/tree_scan.py
from pathlib import Path
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

from core.file_manager import file_manager
from core.guardrail import guardrail

logger = logging.getLogger(__name__)


def _pick_string(*candidates: Optional[Any]) -> Optional[str]:
    for c in candidates:
        if isinstance(c, str) and c:
            return c
    return None


def should_skip(path: Path, ignore_names: List[str], ignore_patterns: List[str]) -> bool:
    name = path.name
    # skip by exact name
    if name in ignore_names:
        return True
    # simple suffix/prefix pattern matches
    for pat in ignore_patterns:
        if pat.startswith("*") and name.endswith(pat.lstrip("*")):
            return True
        if pat.endswith("*") and name.startswith(pat.rstrip("*")):
            return True
        if pat in name:
            return True
    return False


def _gather_paths(root: Path, max_depth: int, ignore_names: List[str], ignore_patterns: List[str]) -> List[str]:
    results = []
    root = root.resolve()
    base_depth = len(root.parts)
    for p in root.rglob("*"):
        try:
            rel = p.relative_to(root)
        except Exception:
            continue
        depth = len(rel.parts)
        if max_depth is not None and depth > max_depth:
            continue
        if should_skip(p, ignore_names, ignore_patterns):
            if p.is_dir():
                # skip walking into it by continuing
                continue
            else:
                continue
        # include both files and directories (string path)
        results.append(str(rel.as_posix()))
    return sorted(results)


def task_tree_scan(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Parcourt le workspace et renvoie une vue d'ensemble (liste de chemins).
    Params attendus (exemples) :
      - workspace_path / workspace : chemin racine
      - max_depth : int (optionnel)
      - ignore_names : list of names to skip (e.g., ['.git', '__pycache__'])
      - ignore_patterns : list of simple patterns ('*.pyc', 'node_modules', '.venv', etc.)
      - output : chemin du rapport JSON (optionnel)
      - dry_run : bool (optionnel)
    Retourne un statut string et écrit un rapport JSON (best-effort).
    """
    fm = context.get("file_manager") or file_manager
    guard = context.get("guardrail") or guardrail

    # workspace resolution
    ws_candidate = _pick_string(params.get("workspace_path"), params.get("workspace"), context.get("workspace"), ".")
    workspace_path = Path(ws_candidate).resolve()

    max_depth = None
    if isinstance(params.get("max_depth"), int):
        max_depth = params.get("max_depth")

    ignore_names = params.get("ignore_names") or []
    if not isinstance(ignore_names, list):
        ignore_names = []

    ignore_patterns = params.get("ignore_patterns") or []
    if not isinstance(ignore_patterns, list):
        ignore_patterns = []

    dry_run = bool(params.get("dry_run", False))

    # resolve output path for report
    out_path = _pick_string(params.get("output"), params.get("report_path"), context.get("output"))
    if not out_path:
        out_path = "reports/tree_scan.json"

    report = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "workspace": str(workspace_path),
        "max_depth": max_depth,
        "entries": [],
        "status": None,
    }

    try:
        # Best-effort: ensure workspace exists
        if not workspace_path.exists():
            report["status"] = "workspace_not_found"
            report["error"] = f"Workspace not found: {workspace_path}"
            try:
                fm.write_file(out_path, json.dumps(report, indent=2, ensure_ascii=False))
            except Exception as e:
                logger.error("Failed to write tree_scan report: %s", e)
            return "[ERROR] workspace not found"

        entries = _gather_paths(workspace_path, max_depth, ignore_names, ignore_patterns)
        report["entries"] = entries
        report["count"] = len(entries)
        report["status"] = "dry_run_ok" if dry_run else "ok"

        # write report (best-effort)
        try:
            fm.write_file(out_path, json.dumps(report, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error("Failed to write tree_scan report: %s", e)

        if dry_run:
            return f"[OK] Tree scan simulated: {len(entries)} entries"
        return f"[OK] Tree scan: {len(entries)} entries"
    except Exception as e:
        logger.exception("Unexpected error during tree_scan: %s", e)
        report["status"] = "error"
        report["error"] = str(e)
        try:
            fm.write_file(out_path, json.dumps(report, indent=2, ensure_ascii=False))
        except Exception as e2:
            logger.error("Failed to write tree_scan error report: %s", e2)
        return f"[ERROR] {str(e)}"
