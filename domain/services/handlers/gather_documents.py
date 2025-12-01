# domain/services/handlers/gather_documents.py
import os
from pathlib import Path
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

from core.file_manager import file_manager
from core.guardrail import guardrail

logger = logging.getLogger(__name__)


def _pick_string(*candidates: Optional[Any]) -> Optional[str]:
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _resolve_placeholders(value: Any, variables: Dict[str, str]) -> Any:
    # Minimal placeholder resolution (simple ${VAR} replacement for strings,
    # recursive for lists/dicts) — adapted from original task logic.
    if isinstance(value, str):
        result = value
        for key, raw_val in variables.items():
            result = result.replace(f"${{{key}}}", str(raw_val))
        return result
    if isinstance(value, list):
        return [_resolve_placeholders(item, variables) for item in value]
    if isinstance(value, dict):
        return {k: _resolve_placeholders(v, variables) for k, v in value.items()}
    return value


def _collect_terms(source, variables: Dict[str, str]) -> List[str]:
    resolved = _resolve_placeholders(source, variables)
    if not resolved:
        return []
    if isinstance(resolved, str):
        parts = [item.strip() for item in resolved.replace(";", ",").split(",") if item.strip()]
        return parts
    if isinstance(resolved, list):
        return [str(item).strip() for item in resolved if str(item).strip()]
    return [str(resolved).strip()]


def task_gather_documents(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Collecte des documents météo du workspace et génère un rapport Markdown.
    - params: dict (patterns/keywords/options)
    - context: dict (workspace, workspace_path, variables, file_manager, guardrail, context_bridge, mission, task, mode)
    Retourne un statut string et écrit un rapport Markdown (best-effort).
    """
    start_timestamp = datetime.datetime.now()

    file_manager_ref = context.get("file_manager") or file_manager
    guardrail_ref = context.get("guardrail") or guardrail
    context_bridge_ref = context.get("context_bridge")
    mission = context.get("mission")
    task_obj = context.get("task")

    variables = context.get("variables") or {}

    # Resolve workspace path
    workspace_path = context.get("workspace_path")
    if not isinstance(workspace_path, Path):
        workspace_candidate = _resolve_placeholders(context.get("workspace"), variables)
        if isinstance(workspace_candidate, str) and workspace_candidate.strip():
            try:
                workspace_path = Path(workspace_candidate.strip()).resolve()
            except OSError:
                workspace_path = Path(".").resolve()
        else:
            workspace_path = Path(".").resolve()

    if not workspace_path.exists():
        raise FileNotFoundError(f"Workspace path not found: {workspace_path}")

    mode = context.get("mode") or (context.get("context_meta") or {}).get("mode")

    # Build search terms
    default_terms = ["meteo", "weather", "climate", "soil_temp", "halo"]
    term_sources = [
        params.get("patterns"),
        params.get("keywords"),
        params.get("match"),
        params.get("match_keywords"),
        params.get("filters"),
        params.get("filter"),
        params.get("search"),
        variables.get("GATHER_PATTERNS"),
        variables.get("PATTERNS"),
    ]

    search_terms: List[str] = []
    for source in term_sources:
        search_terms.extend(_collect_terms(source, variables))

    if not search_terms:
        search_terms = default_terms.copy()

    search_terms_set = {term.lower() for term in search_terms if term}

    # Exclude directories
    exclude_sources = [
        params.get("exclude_dirs"),
        params.get("exclude"),
        params.get("skip_dirs"),
        variables.get("EXCLUDE_DIRS"),
    ]
    exclude_dirs = {"venv", "__pycache__", ".git", ".idea", ".mypy_cache", ".pytest_cache", "node_modules"}
    for source in exclude_sources:
        for entry in _collect_terms(source, variables):
            exclude_dirs.add(entry)

    gathered_docs: List[Dict[str, Any]] = []
    errors: List[str] = []

    workspace_display = str(workspace_path)

    if context_bridge_ref:
        try:
            context_bridge_ref.publish_diagnostic(
                "task_gather_documents",
                {
                    "event": "started",
                    "workspace": workspace_display,
                    "patterns": sorted(search_terms_set),
                    "task": getattr(task_obj, "name", None),
                    "mission": getattr(mission, "name", None),
                    "mode": mode or "unknown",
                },
            )
        except Exception:
            logger.debug("Context bridge publish diagnostic failed at start", exc_info=True)

    def should_skip(directory: Path) -> bool:
        name = directory.name
        if not name:
            return False
        if name in exclude_dirs:
            return True
        if name.startswith(".") and name not in {"."}:
            return True
        try:
            if guardrail_ref.is_sanctuary_path(str(directory)):
                return True
        except AttributeError:
            return False
        return False

    # Walk the workspace
    for root, dirs, files in os.walk(workspace_path):
        current_dir = Path(root)

        if current_dir != workspace_path and should_skip(current_dir):
            dirs[:] = []
            continue

        # Filter out directories to skip for next level
        dirs[:] = [d for d in dirs if not should_skip(current_dir / d)]

        for filename in files:
            file_path = current_dir / filename

            try:
                try:
                    if guardrail_ref.is_sanctuary_path(str(file_path)):
                        continue
                except AttributeError:
                    pass

                relative_path = file_path.relative_to(workspace_path).as_posix()
                haystack = f"{filename.lower()} {relative_path.lower()}"

                if not any(term in haystack for term in search_terms_set):
                    continue

                # Read file content via file_manager (best-effort)
                try:
                    content = file_manager_ref.read_file(str(file_path))
                except Exception:
                    # fallback: try simple read
                    try:
                        with open(file_path, "r", encoding="utf-8") as fh:
                            content = fh.read()
                    except Exception as exc_read:
                        errors.append(f"{relative_path}: {exc_read}")
                        if context_bridge_ref:
                            try:
                                context_bridge_ref.publish_diagnostic(
                                    "task_gather_documents",
                                    {
                                        "event": "read_failed",
                                        "document": relative_path,
                                        "error": str(exc_read),
                                    },
                                )
                            except Exception:
                                logger.debug("Failed to publish read_failed", exc_info=True)
                        continue

                gathered_docs.append({"path": relative_path, "content": content})
                if context_bridge_ref:
                    try:
                        context_bridge_ref.publish_diagnostic(
                            "task_gather_documents",
                            {
                                "event": "document_collected",
                                "document": relative_path,
                                "patterns": sorted(search_terms_set),
                                "count": len(gathered_docs),
                            },
                        )
                    except Exception:
                        logger.debug("Failed to publish document_collected", exc_info=True)

            except Exception as exc:  # pragma: no cover - instrumentation only
                message = f"{relative_path if 'relative_path' in locals() else file_path}: {exc}"
                errors.append(message)
                if context_bridge_ref:
                    try:
                        context_bridge_ref.publish_diagnostic(
                            "task_gather_documents",
                            {
                                "event": "read_failed",
                                "document": relative_path if 'relative_path' in locals() else str(file_path),
                                "error": str(exc),
                            },
                        )
                    except Exception:
                        logger.debug("Failed to publish read_failed (outer)", exc_info=True)
                continue

    duration_seconds = (datetime.datetime.now() - start_timestamp).total_seconds()

    # Build report content (Markdown)
    report_name = params.get("report_name") or params.get("destination") or params.get("report_path") or "gather_meteo_docs.md"
    try:
        if isinstance(report_name, str):
            report_name = Path(report_name).name
    except Exception:
        report_name = "gather_meteo_docs.md"
    if not report_name.lower().endswith(".md"):
        report_name = f"{report_name}.md"
    report_path = Path("reports") / report_name

    report_lines: List[str] = [
        "# 🌦️ Rapport de collecte météo",
        "",
        f"**Workspace :** `{workspace_display}`",
        f"**Mode :** {mode or 'write_enabled'}",
        f"**Généré le :** {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"**Motifs recherchés :** {', '.join(sorted(search_terms_set))}",
        f"**Documents collectés :** {len(gathered_docs)}",
        "",
    ]

    report_lines.append("## Documents")

    if gathered_docs:
        for doc in gathered_docs:
            report_lines.extend(
                [
                    f"### `{doc['path']}`",
                    "",
                    "```",
                    doc["content"],
                    "```",
                    "",
                ]
            )
    else:
        report_lines.append("_Aucun document correspondant aux motifs fournis._")
        report_lines.append("")

    if errors:
        report_lines.append("## Incidents")
        report_lines.extend(f"- WARNING: {msg}" for msg in errors)
        report_lines.append("")

    report_content = "\n".join(report_lines)

    report_path_str = str(report_path)
    try:
        guardrail_ref.check_path(report_path_str, operation="write")
    except Exception:
        # best-effort
        logger.debug("Guardrail check_path failed for %s", report_path_str, exc_info=True)

    try:
        if hasattr(file_manager_ref, "write_file"):
            file_manager_ref.write_file(report_path_str, report_content)
        else:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report_content, encoding="utf-8")
    except Exception as exc:
        errors.append(f"Failed to write report: {exc}")
        logger.error("Failed to write gather_documents report: %s", exc)

    summary = {
        "report_path": report_path_str,
        "documents": [doc["path"] for doc in gathered_docs],
        "patterns": sorted(search_terms_set),
        "duration_seconds": round(duration_seconds, 3),
        "errors": errors,
    }

    if context_bridge_ref:
        try:
            record = context_bridge_ref.register_output(
                report_path_str,
                format="markdown",
                mission=getattr(mission, "name", None),
                task=getattr(task_obj, "name", None),
                mode=mode,
                summary=summary,
            )
            final_event = "completed_with_warnings" if errors or not gathered_docs else "completed"
            context_bridge_ref.publish_diagnostic(
                "task_gather_documents",
                {
                    "event": final_event,
                    "summary": summary,
                    "record": record,
                },
            )
        except Exception:
            logger.debug("Context bridge publish diagnostic failed at completion", exc_info=True)

    status_prefix = "[WARN]" if errors or not gathered_docs else "[OK]"
    return (
        f"{status_prefix} Rapport météo collecté : {report_path_str} "
        f"({len(gathered_docs)} document(s), {duration_seconds:.2f} s)"
    )
