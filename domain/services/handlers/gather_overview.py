# domain/services/handlers/gather_overview.py
from pathlib import Path
from collections import Counter
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

from core.file_manager import file_manager
from core.guardrail import guardrail

logger = logging.getLogger(__name__)


def _pick_string(*candidates: Optional[Any]) -> Optional[str]:
    for candidate in candidates:
        if isinstance(candidate, str):
            cand = candidate.strip()
            if cand:
                return cand
    return None


def task_gather_overview(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Collecte une vue d'ensemble du workspace : structure, fichiers, dossiers.
    Stocke les données dans mission.metadata pour utilisation par task_generate_report.
    - params: dict (scan_depth/include_extensions/exclude_dirs/options)
    - context: dict (workspace, workspace_path, variables, file_manager, guardrail, context_bridge, mission, task, mode)
    Retourne une string de statut et stocke les résultats dans mission.metadata['gathered_data'].
    """
    start_timestamp = datetime.datetime.now()

    fm = context.get("file_manager") or file_manager
    guard = context.get("guardrail") or guardrail
    context_bridge_ref = context.get("context_bridge")
    mission = context.get("mission")
    task_obj = context.get("task")

    variables = context.get("variables") or {}

    # Resolve workspace path
    workspace_path = context.get("workspace_path")
    if not isinstance(workspace_path, Path):
        workspace_candidate = context.get("workspace")
        if isinstance(workspace_candidate, str) and workspace_candidate.strip():
            try:
                workspace_path = Path(workspace_candidate.strip()).resolve()
            except OSError:
                workspace_path = Path(".").resolve()
        else:
            workspace_path = Path(".").resolve()

    if not workspace_path.exists():
        raise FileNotFoundError(f"Workspace path not found: {workspace_path}")

    # Paramètres de scan
    scan_depth = int(params.get("scan_depth") or params.get("depth") or 3)
    include_extensions = params.get("include_extensions") or params.get("include") or [".py", ".md", ".yaml", ".yml", ".txt"]
    if isinstance(include_extensions, str):
        include_extensions = [ext.strip() for ext in include_extensions.split(",") if ext.strip()]

    # Normaliser les extensions
    clean_extensions = {
        ext if ext.startswith(".") else f".{ext}"
        for ext in (ext.lower() for ext in include_extensions)
    }

    exclude_dirs = {"venv", "__pycache__", ".git", ".idea", ".mypy_cache", ".pytest_cache", "node_modules", ".dart_tool", "build"}

    def should_skip(directory: Path) -> bool:
        name = directory.name
        if not name:
            return False
        if name in exclude_dirs:
            return True
        if name.startswith(".") and name not in {"."}:
            return True
        try:
            if guard.is_sanctuary_path(str(directory)):
                return True
        except AttributeError:
            return False
        return False

    gathered_data = {
        "workspace": str(workspace_path),
        "scan_depth": scan_depth,
        "extensions": sorted(clean_extensions),
        "directories": [],
        "files": [],
        "file_stats": Counter(),
        "scan_timestamp": start_timestamp.isoformat(),
    }

    tree_lines: List[str] = ["./"]
    matching_files: List[str] = []
    errors: List[str] = []
    total_dirs = 1
    total_files = 0

    def walk(directory: Path, depth: int, prefix: str) -> None:
        nonlocal total_dirs, total_files

        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda entry: (not entry.is_dir(), entry.name.lower()),
            )
        except OSError as exc:
            errors.append(f"{directory}: {exc}")
            return

        directories: List[Path] = []
        files: List[Path] = []

        for entry in entries:
            if entry.is_dir():
                if should_skip(entry):
                    continue
                directories.append(entry)
            else:
                total_files += 1
                files.append(entry)

        total_dirs += len(directories)

        ordered_entries = directories + files
        for index, entry in enumerate(ordered_entries):
            is_last = index == len(ordered_entries) - 1
            connector = "└──" if is_last else "├──"

            if entry.is_dir():
                rel_path = entry.relative_to(workspace_path).as_posix()
                tree_lines.append(f"{prefix}{connector} 📁 {entry.name}/")
                gathered_data["directories"].append(rel_path)
                if depth + 1 <= scan_depth:
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    walk(entry, depth + 1, next_prefix)
            else:
                suffix = entry.suffix.lower()
                rel_path = entry.relative_to(workspace_path).as_posix()
                gathered_data["file_stats"][suffix or "[none]"] += 1
                if suffix in clean_extensions or not clean_extensions:
                    matching_files.append(rel_path)
                    tree_lines.append(f"{prefix}{connector} 📄 {entry.name}")
                gathered_data["files"].append(rel_path)

    walk(workspace_path, 0, "")

    gathered_data["tree_lines"] = tree_lines
    gathered_data["matching_files"] = sorted(matching_files)
    gathered_data["total_directories"] = total_dirs
    gathered_data["total_files"] = total_files
    gathered_data["matching_files_count"] = len(matching_files)
    gathered_data["errors"] = errors

    # Stocker dans mission.metadata pour usage ultérieur
    if mission is not None:
        if not hasattr(mission, "metadata") or mission.metadata is None:
            try:
                mission.metadata = {}
            except Exception:
                # best-effort, ne pas faire échouer la collecte
                pass
        if isinstance(getattr(mission, "metadata", None), dict):
            if "gathered_data" not in mission.metadata:
                mission.metadata["gathered_data"] = {}
            mission.metadata["gathered_data"].update(gathered_data)

    # Publier diagnostic via context_bridge si disponible
    if context_bridge_ref:
        try:
            context_bridge_ref.publish_diagnostic(
                "task_gather_overview",
                {
                    "event": "completed" if not errors else "completed_with_warnings",
                    "workspace": str(workspace_path),
                    "directories": total_dirs,
                    "files": total_files,
                    "matching_files": len(matching_files),
                    "task": getattr(task_obj, "name", None),
                    "mission": getattr(mission, "name", None),
                },
            )
        except Exception:
            logger.debug("Context bridge publish diagnostic failed", exc_info=True)

    status_prefix = "[WARN]" if errors else "[OK]"
    return (
        f"{status_prefix} Vue d'ensemble collectée : {total_dirs} dossier(s), "
        f"{total_files} fichier(s) ({len(matching_files)} correspondant aux extensions)"
    )
