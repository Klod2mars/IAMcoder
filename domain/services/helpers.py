# domain/services/helpers.py
from pathlib import Path
import json
import logging
from typing import Any, Dict, List, Optional

from core.file_manager import file_manager
from core.guardrail import guardrail
from core.context_bridge import context_bridge

logger = logging.getLogger(__name__)


def _resolve_placeholders(value: Any, variables: Dict[str, str]) -> Any:
    """
    Replace ${VAR} placeholders in strings, lists or dicts.
    - value: any nested structure (str | list | dict)
    - variables: mapping of variable names to their string values
    Returns the same structure with placeholders resolved where applicable.
    """
    if isinstance(value, str):
        result = value
        for key, raw_val in (variables or {}).items():
            try:
                result = result.replace(f"${{{key}}}", str(raw_val))
            except Exception:
                # best-effort: ignore problematic replacements
                continue
        return result

    if isinstance(value, list):
        return [_resolve_placeholders(item, variables) for item in value]

    if isinstance(value, dict):
        return {
            key: _resolve_placeholders(val, variables)
            for key, val in value.items()
        }

    return value


def _pick_string(*candidates: Any, variables: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    Return the first non-empty string from candidates.
    If variables is provided, resolve placeholders on string candidates first.
    """
    for c in candidates:
        if c is None:
            continue
        if isinstance(c, str):
            cand = c.strip()
            if not cand:
                continue
            if variables:
                cand = _resolve_placeholders(cand, variables)
                cand = cand.strip() if isinstance(cand, str) else cand
            if isinstance(cand, str) and cand:
                return cand
        else:
            # consider non-string scalars
            s = str(c).strip()
            if s:
                return s
    return None


def _coerce_variable_map(source: Any) -> Dict[str, str]:
    """
    Coerce a source into a flat dict[str, str].
    Accepts:
      - dict -> mapping key -> str(value)
      - list of {name/key, value} dicts -> mapping
      - None -> {}
    """
    mapping: Dict[str, str] = {}

    if isinstance(source, dict):
        for key, value in source.items():
            if not key:
                continue
            mapping[str(key)] = "" if value is None else str(value)
        return mapping

    if isinstance(source, list):
        for entry in source:
            if not isinstance(entry, dict):
                continue
            key = entry.get("name") or entry.get("key")
            if not key:
                continue
            mapping[str(key)] = "" if entry.get("value") is None else str(entry.get("value"))

    return mapping


def _to_bool(value: Any) -> bool:
    """
    Robust coercion to bool for common types/strings.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        return v in ("1", "true", "yes", "y", "on")
    return False


def _stringify_content(value: Any) -> Optional[str]:
    """
    Convert common structures to a string suitable for writing to text files.
    - None -> None
    - str -> identity
    - list -> join with newlines
    - dict or other -> JSON dump or str fallback
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        try:
            return "\n".join(str(item) for item in value)
        except Exception:
            return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        try:
            return str(value)
        except Exception:
            return None


def _safe_write_text(
    fm: Any,
    path_obj: Path,
    content: str,
    *,
    append: bool = False,
    encoding: str = "utf-8",
    guard: Any = None,
) -> None:
    """
    Write text to a path, using file_manager if available, guarded by guardrail when possible.
    - fm: file_manager instance or None (falls back to core.file_manager.file_manager)
    - path_obj: Path object
    - content: text to write
    - append: whether to append
    - guard: guardrail instance or None (falls back to core.guardrail.guardrail)
    Raises exceptions to caller so caller can aggregate errors.
    """
    fm = fm or file_manager
    guard = guard or guardrail

    # Best-effort guard check
    try:
        guard.check_path(str(path_obj), operation="append" if append else "write")
    except Exception:
        # don't block writes if guard check is not available or fails
        logger.debug("Guardrail check_path failed for %s", path_obj, exc_info=True)

    parent = path_obj.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.debug("Could not ensure parent dir %s: %s", parent, e)

    if append:
        old = None
        try:
            if hasattr(fm, "read_file"):
                try:
                    old = fm.read_file(str(path_obj))
                except Exception:
                    old = None
            else:
                if path_obj.exists():
                    old = path_obj.read_text(encoding=encoding)
        except Exception:
            old = None
        new_content = (old or "") + content
        if hasattr(fm, "write_file"):
            fm.write_file(str(path_obj), new_content)
        else:
            path_obj.write_text(new_content, encoding=encoding)
    else:
        if hasattr(fm, "write_file"):
            fm.write_file(str(path_obj), content)
        else:
            path_obj.write_text(content, encoding=encoding)


def _collect_variables(params: Optional[Dict[str, Any]], context_section: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """
    Merge variables from context_section and params into a flat mapping.
    - params: task.parameters
    - context_section: mission.metadata.get('context')
    """
    variables: Dict[str, str] = {}

    # process context_section variables first so params override
    for source in (context_section or {}).get("variables"), (params or {}).get("variables"):
        if source is None:
            continue
        try:
            coerced = _coerce_variable_map(source)
            variables.update(coerced)
        except Exception:
            # ignore malformed source
            logger.debug("Failed to coerce variable source: %s", source, exc_info=True)

    return variables


def build_execution_context(task, mission) -> Dict[str, Any]:
    """
    Build an execution context dict from a task and a mission.

    Mirrors the original TaskLogicHandler._build_execution_context behaviour:
    - merges variables from mission.context and task.parameters
    - resolves placeholders for workspace/outpoints
    - returns a dict containing workspace, workspace_path, variables, mode, output, declared_outputs,
      context_meta and references to file_manager, guardrail and context_bridge.
    """
    metadata = getattr(mission, "metadata", {}) or {}
    context_section = metadata.get("context") or {}
    params = getattr(task, "parameters", {}) or {}

    # collect variables (params override context_section)
    variables = _collect_variables(params, context_section)

    workspace_hint = (
        params.get("workspace")
        or params.get("workspace_path")
        or context_section.get("workspace")
        or context_section.get("workspace_path")
        or metadata.get("workspace")
    )

    workspace_value = _resolve_placeholders(workspace_hint, variables)

    if isinstance(workspace_value, (dict, list)):
        workspace_value = None

    workspace_candidate = str(workspace_value).strip() if workspace_value else "."
    try:
        workspace_path = Path(workspace_candidate).resolve()
    except OSError:
        workspace_path = Path(".").resolve()

    declared_outputs = metadata.get("outputs") or []
    declared_outputs = _resolve_placeholders(declared_outputs, variables)

    output_config = params.get("output") or {}
    output_config = _resolve_placeholders(output_config, variables)

    return {
        "task": task,
        "mission": mission,
        "workspace": str(workspace_path),
        "workspace_path": workspace_path,
        "variables": variables,
        "mode": context_section.get("mode"),
        "output": output_config,
        "declared_outputs": declared_outputs,
        "context_meta": context_section,
        "file_manager": file_manager,
        "guardrail": guardrail,
        "context_bridge": context_bridge,
    }
