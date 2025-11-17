from pathlib import Path
from collections import Counter
import os
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

import yaml

from core.context_bridge import context_bridge
from core.file_manager import file_manager
from core.guardrail import guardrail


logger = logging.getLogger(__name__)


def _resolve_placeholders(value: Any, variables: Dict[str, str]) -> Any:
    """Replace ${VAR} placeholders in strings, lists or dicts."""

    if isinstance(value, str):
        result = value
        for key, raw_val in variables.items():
            result = result.replace(f"${{{key}}}", str(raw_val))
        return result

    if isinstance(value, list):
        return [_resolve_placeholders(item, variables) for item in value]

    if isinstance(value, dict):
        return {
            key: _resolve_placeholders(val, variables)
            for key, val in value.items()
        }

    return value


class TaskLogicHandler:
    """
    Orchestrateur logique des tâches.
    Fournit les comportements concrets selon le type de tâche :
    - analysis : lecture du workspace et collecte des fichiers
    - report_generation : création du rapport Markdown
    """

    def execute(self, task, mission):
        ttype = (task.task_type or "generic").lower()
        task_name = (task.name or "").lower()
        logger.debug("Dispatching task '%s' with type '%s'", getattr(task, "name", "<unnamed>"), task.task_type)
        params = task.parameters or {}

        # Dispatch par nom de tâche (prioritaire pour les tâches spécifiques)
        if task_name == "task_gather_overview" or ttype in {"read", "gather_overview"}:
            context = self._build_execution_context(task, mission)
            return task_gather_overview(params, context)
        elif task_name == "task_generate_report" or ttype in {"report", "generate_report"}:
            context = self._build_execution_context(task, mission)
            return task_generate_report(params, context)
        # Dispatch par type de tâche (pour compatibilité)
        elif ttype == "analysis":
            return self._analyze_workspace(params)
        elif ttype == "report_generation":
            return self._generate_markdown(params)
        elif ttype in {"tree_scan", "tree"}:
            context = self._build_execution_context(task, mission)
            return task_tree_scan(params, context)
        elif ttype in {"task_gather_documents", "gather_documents"}:
            context = self._build_execution_context(task, mission)
            return task_gather_documents(params, context)
        elif task_name == "task_apply_writes" or ttype in {"task_apply_writes", "apply_writes"}:
            context = self._build_execution_context(task, mission)
            return task_apply_writes(params, context)
        elif ttype == "setup":
            return f"[OK] Préparation du workspace : {params.get('variable_path', 'N/A')}"
        else:
            return f"[INFO] Tâche '{task.name}' exécutée sans logique spécifique."

    def _analyze_workspace(self, params):
        workspace = Path(params.get("workspace_path", ".")).resolve()
        depth = int(params.get("depth", 3))
        stats = Counter()
        lines = []

        def explore(path: Path, level=0):
            if level > depth:
                return
            indent = "│   " * level
            lines.append(f"{indent}├── {path.name}/")
            for item in sorted(path.iterdir()):
                if item.is_dir():
                    explore(item, level + 1)
                else:
                    stats[item.suffix or "[none]"] += 1
                    lines.append(f"{indent}│   {item.name}")

        explore(workspace)

        output_json = params.get("output_data")
        if output_json:
            out_path = Path(output_json)
            payload = {
                "workspace": str(workspace),
                "tree": lines,
                "extensions": stats,
            }
            guardrail.check_path(str(out_path), operation="write")
            file_manager.write_file(
                str(out_path),
                json.dumps(payload, indent=2, ensure_ascii=False),
            )

        return f"[OK] Structure analysée : {workspace} ({len(lines)} entrées)"

    def _generate_markdown(self, params):
        report_path = Path(params.get("destination", "reports/tree_readonly.md"))
        report_path.parent.mkdir(parents=True, exist_ok=True)

        data_path = Path("data/tree_" + report_path.stem + ".json")
        data = {}
        if data_path.exists():
            data = json.loads(data_path.read_text(encoding="utf-8"))

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        workspace = data.get("workspace", "?")
        lines = data.get("tree", [])
        stats = data.get("extensions", {})

        md = [
            f"# 🌳 Rapport de Lecture — {Path(workspace).name}",
            f"**Date :** {now}",
            f"**Workspace :** {workspace}",
            "",
            "## Arborescence (3 niveaux)",
            "```",
            *lines,
            "```",
            "",
            "## Extensions détectées",
        ]
        for ext, count in stats.items():
            md.append(f"- **{ext}** : {count} fichier(s)")
        md.append("\n---\n_Rapport généré par AIHomeCoder v1.0.0_")

        guardrail.check_path(str(report_path), operation="write")
        file_manager.write_file(str(report_path), "\n".join(md))
        return f"[OK] Rapport Markdown généré : {report_path}"

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------
    def _build_execution_context(self, task, mission):
        metadata = mission.metadata or {}
        context_section = metadata.get("context") or {}
        params = task.parameters or {}

        variables = self._collect_variables(params, context_section)

        workspace_hint = (
            params.get("workspace")
            or params.get("workspace_path")
            or context_section.get("workspace")
            or context_section.get("workspace_path")
            or metadata.get("workspace")  # Workspace peut être défini directement dans mission.metadata
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

    def _collect_variables(self, params, context_section):
        variables: Dict[str, str] = {}

        for source in (context_section.get("variables"), params.get("variables")):
            variables.update(self._coerce_variable_map(source))

        return variables

    @staticmethod
    def _coerce_variable_map(source):
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


def task_tree_scan(params, context):
    """
    Parcourt le workspace actif et génère un rapport Markdown listant
    les répertoires et fichiers ciblés (par défaut .dart).
    Compatible avec le mode read_only via FileManager + Guardrail.
    """

    start_timestamp = datetime.datetime.now()

    file_manager_ref = context.get("file_manager") or file_manager
    guardrail_ref = context.get("guardrail") or guardrail
    context_bridge_ref = context.get("context_bridge")

    variables = context.get("variables") or {}

    workspace_path = context.get("workspace_path")
    if not isinstance(workspace_path, Path):
        workspace_candidate = _resolve_placeholders(context.get("workspace"), variables)
        if isinstance(workspace_candidate, str) and workspace_candidate.strip():
            workspace_path = Path(workspace_candidate.strip()).resolve()
        else:
            workspace_path = Path(".").resolve()

    if not workspace_path.exists():
        raise FileNotFoundError(f"Workspace path not found: {workspace_path}")

    def _pick_string(*candidates):
        for candidate in candidates:
            resolved = _resolve_placeholders(candidate, variables)
            if isinstance(resolved, str) and resolved.strip():
                return resolved.strip()
        return None

    output_config = context.get("output") if isinstance(context.get("output"), dict) else {}
    declared_outputs = context.get("declared_outputs") or []

    destination = _pick_string(
        params.get("destination"),
        params.get("report_path"),
        (params.get("output") or {}).get("destination") if isinstance(params.get("output"), dict) else None,
        output_config.get("destination") if isinstance(output_config, dict) else None,
    )

    if not destination:
        if isinstance(declared_outputs, dict):
            destination = _pick_string(declared_outputs.get("destination"))
        elif isinstance(declared_outputs, list):
            for entry in declared_outputs:
                if isinstance(entry, dict):
                    destination = _pick_string(entry.get("destination"))
                elif isinstance(entry, str):
                    destination = _pick_string(entry)
                if destination:
                    break

    report_path = Path(destination or "reports/audit_tree.md")

    extension_sources = [
        params.get("extensions"),
        params.get("extension"),
        params.get("scan_ext"),
        params.get("scan_extensions"),
        variables.get("SCAN_EXT"),
    ]

    target_extensions: List[str] = []
    for source in extension_sources:
        resolved = _resolve_placeholders(source, variables)
        if not resolved:
            continue
        if isinstance(resolved, str):
            chunks = [item.strip() for item in resolved.split(",") if item.strip()]
            target_extensions.extend(chunks)
        elif isinstance(resolved, list):
            target_extensions.extend(str(item).strip() for item in resolved if str(item).strip())

    if not target_extensions:
        target_extensions = [".dart"]

    clean_extensions = {
        ext if ext.startswith(".") else f".{ext}"
        for ext in (ext.lower() for ext in target_extensions)
    }

    depth_candidate = _pick_string(
        params.get("max_depth"),
        params.get("depth"),
        variables.get("MAX_DEPTH"),
    )
    try:
        max_depth = max(0, int(depth_candidate)) if depth_candidate is not None else 6
    except ValueError:
        max_depth = 6

    exclude_sources = [
        params.get("exclude_dirs"),
        params.get("exclude"),
        params.get("skip_dirs"),
        variables.get("EXCLUDE_DIRS"),
    ]

    exclude_dirs = {"venv", "__pycache__", ".git", ".idea", ".mypy_cache", ".pytest_cache", "node_modules"}

    for source in exclude_sources:
        resolved = _resolve_placeholders(source, variables)
        if not resolved:
            continue
        if isinstance(resolved, str):
            exclude_dirs.update(
                item.strip() for item in resolved.split(",") if item.strip()
            )
        elif isinstance(resolved, list):
            exclude_dirs.update(str(item).strip() for item in resolved if str(item).strip())

    tree_lines: List[str] = ["./"]
    matching_files: List[str] = []
    errors: List[str] = []
    total_dirs = 1
    total_files = 0
    max_depth_reached = 0

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

    def walk(directory: Path, depth: int, prefix: str) -> None:
        nonlocal total_dirs, total_files, max_depth_reached

        max_depth_reached = max(max_depth_reached, depth)

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
            next_prefix = prefix + ("    " if is_last else "│   ")

            if entry.is_dir():
                tree_lines.append(f"{prefix}{connector} 📁 {entry.name}/")
                if depth + 1 <= max_depth:
                    walk(entry, depth + 1, next_prefix)
            else:
                suffix = entry.suffix.lower()
                if suffix in clean_extensions:
                    rel_path = entry.relative_to(workspace_path).as_posix()
                    matching_files.append(rel_path)
                    tree_lines.append(f"{prefix}{connector} 📄 {entry.name}")

    walk(workspace_path, 0, "")

    matching_files.sort()

    duration_seconds = (datetime.datetime.now() - start_timestamp).total_seconds()

    extensions_display = ", ".join(sorted(clean_extensions))
    workspace_display = str(workspace_path)

    report_lines = [
        "# 🌳 Structure du projet",
        "",
        f"**Workspace :** `{workspace_display}`",
        f"**Généré le :** {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Mode :** {context.get('mode') or 'write_enabled'}",
        "",
        "## Arborescence scannée",
        "```",
        *tree_lines,
        "```",
        "",
        "## Statistiques",
        f"- Répertoires parcourus : {total_dirs}",
        f"- Fichiers inspectés : {total_files}",
        f"- Fichiers ciblés ({extensions_display}) : {len(matching_files)}",
        f"- Profondeur analysée : {max_depth_reached} / limite {max_depth}",
        f"- Durée du scan : {duration_seconds:.2f} s",
    ]

    if matching_files:
        report_lines.append("")
        report_lines.append("## Fichiers ciblés")
        report_lines.extend(f"- `{path}`" for path in matching_files)

        distribution: Dict[str, int] = {}
        for path in matching_files:
            root_name = path.split("/", 1)[0]
            distribution[root_name] = distribution.get(root_name, 0) + 1

        report_lines.append("")
        report_lines.append("## Répartition par dossier racine")
        for root_name, count in sorted(distribution.items()):
            report_lines.append(f"- `{root_name}` : {count} fichier(s)")
    else:
        report_lines.append("")
        report_lines.append("## Fichiers ciblés")
        report_lines.append("_Aucun fichier correspondant._")

    if errors:
        report_lines.append("")
        report_lines.append("## Incidents")
        report_lines.extend(f"- WARNING: {message}" for message in errors)

    report_content = "\n".join(report_lines)

    report_path_str = str(report_path)
    guardrail_ref.check_path(report_path_str, operation="write")
    file_manager_ref.write_file(report_path_str, report_content)

    mission = context.get("mission")
    task_obj = context.get("task")

    summary = {
        "report_path": report_path_str,
        "workspace": workspace_display,
        "total_directories": total_dirs,
        "total_files": total_files,
        "matching_files": matching_files,
        "extensions": sorted(clean_extensions),
        "max_depth_limit": max_depth,
        "max_depth_reached": max_depth_reached,
        "duration_seconds": round(duration_seconds, 3),
        "errors": errors,
    }

    if context_bridge_ref:
        metadata = {
            "format": "markdown",
            "mission": mission.name if mission else None,
            "task": task_obj.name if task_obj else None,
            "summary": summary,
        }
        metadata = {key: value for key, value in metadata.items() if value is not None}
        record = context_bridge_ref.register_output(report_path_str, **metadata)
        context_bridge_ref.publish_diagnostic(
            "task_tree_scan",
            {
                "event": "completed_with_warnings" if errors else "completed",
                "summary": summary,
                "record": record,
            },
        )

    status_prefix = "[WARN]" if errors else "[OK]"
    return (
        f"{status_prefix} Rapport arborescent généré : {report_path_str} "
        f"({len(matching_files)} fichier(s) ciblé(s), {total_dirs} dossier(s) parcourus)"
    )


def task_gather_documents(params, context):
    """Collecte les documents météo du workspace et génère un rapport Markdown."""

    start_timestamp = datetime.datetime.now()

    file_manager_ref = context.get("file_manager") or file_manager
    guardrail_ref = context.get("guardrail") or guardrail
    context_bridge_ref = context.get("context_bridge")
    mission = context.get("mission")
    task_obj = context.get("task")

    variables = context.get("variables") or {}

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

    def _pick_string(*candidates):
        for candidate in candidates:
            resolved = _resolve_placeholders(candidate, variables)
            if isinstance(resolved, str) and resolved.strip():
                return resolved.strip()
        return None

    output_config = context.get("output") if isinstance(context.get("output"), dict) else {}
    declared_outputs = context.get("declared_outputs") or []

    destination = _pick_string(
        params.get("destination"),
        params.get("report_path"),
        (params.get("output") or {}).get("destination") if isinstance(params.get("output"), dict) else None,
        output_config.get("destination") if isinstance(output_config, dict) else None,
    )

    if not destination:
        if isinstance(declared_outputs, dict):
            destination = _pick_string(declared_outputs.get("destination"))
        elif isinstance(declared_outputs, list):
            for entry in declared_outputs:
                if isinstance(entry, dict):
                    destination = _pick_string(entry.get("destination"))
                elif isinstance(entry, str):
                    destination = _pick_string(entry)
                if destination:
                    break

    report_name = Path(destination).name if destination else "gather_meteo_docs.md"
    if not report_name.lower().endswith(".md"):
        report_name = f"{report_name}.md"

    report_path = Path("reports") / report_name

    def _collect_terms(source) -> List[str]:
        resolved = _resolve_placeholders(source, variables)
        if not resolved:
            return []
        if isinstance(resolved, str):
            parts = [item.strip() for item in resolved.replace(";", ",").split(",") if item.strip()]
            return parts
        if isinstance(resolved, list):
            return [str(item).strip() for item in resolved if str(item).strip()]
        return [str(resolved).strip()]

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
        search_terms.extend(_collect_terms(source))

    if not search_terms:
        search_terms = default_terms.copy()

    search_terms_set = {term.lower() for term in search_terms if term}

    exclude_sources = [
        params.get("exclude_dirs"),
        params.get("exclude"),
        params.get("skip_dirs"),
        variables.get("EXCLUDE_DIRS"),
    ]

    exclude_dirs = {"venv", "__pycache__", ".git", ".idea", ".mypy_cache", ".pytest_cache", "node_modules"}
    for source in exclude_sources:
        for entry in _collect_terms(source):
            exclude_dirs.add(entry)

    gathered_docs: List[Dict[str, Any]] = []
    errors: List[str] = []

    workspace_display = str(workspace_path)

    if context_bridge_ref:
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

    for root, dirs, files in os.walk(workspace_path):
        current_dir = Path(root)

        if current_dir != workspace_path and should_skip(current_dir):
            dirs[:] = []
            continue

        dirs[:] = [d for d in dirs if not should_skip(current_dir / d)]

        for filename in files:
            file_path = current_dir / filename

            try:
                if guardrail_ref.is_sanctuary_path(str(file_path)):
                    continue
            except AttributeError:
                pass

            relative_path = file_path.relative_to(workspace_path).as_posix()
            haystack = f"{filename.lower()} {relative_path.lower()}"
            if not any(term in haystack for term in search_terms_set):
                continue

            try:
                content = file_manager_ref.read_file(str(file_path))
                gathered_docs.append({
                    "path": relative_path,
                    "content": content,
                })
                if context_bridge_ref:
                    context_bridge_ref.publish_diagnostic(
                        "task_gather_documents",
                        {
                            "event": "document_collected",
                            "document": relative_path,
                            "patterns": sorted(search_terms_set),
                            "count": len(gathered_docs),
                        },
                    )
            except Exception as exc:  # pragma: no cover - instrumentation only
                message = f"{relative_path}: {exc}"
                errors.append(message)
                if context_bridge_ref:
                    context_bridge_ref.publish_diagnostic(
                        "task_gather_documents",
                        {
                            "event": "read_failed",
                            "document": relative_path,
                            "error": str(exc),
                        },
                    )

    duration_seconds = (datetime.datetime.now() - start_timestamp).total_seconds()

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
            report_lines.extend([
                f"### `{doc['path']}`",
                "",
                "```",
                doc["content"],
                "```",
                "",
            ])
    else:
        report_lines.append("_Aucun document correspondant aux motifs fournis._")
        report_lines.append("")

    if errors:
        report_lines.append("## Incidents")
        report_lines.extend(f"- WARNING: {msg}" for msg in errors)

    report_content = "\n".join(report_lines)

    report_path_str = str(report_path)
    guardrail_ref.check_path(report_path_str, operation="write")
    file_manager_ref.write_file(report_path_str, report_content)

    summary = {
        "report_path": report_path_str,
        "documents": [doc["path"] for doc in gathered_docs],
        "patterns": sorted(search_terms_set),
        "duration_seconds": round(duration_seconds, 3),
        "errors": errors,
    }

    record = None
    if context_bridge_ref:
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

    status_prefix = "[WARN]" if errors or not gathered_docs else "[OK]"
    return (
        f"{status_prefix} Rapport météo collecté : {report_path_str} "
        f"({len(gathered_docs)} document(s), {duration_seconds:.2f} s)"
    )


def task_apply_writes(params: Dict[str, Any], context: Dict[str, Any]):
    """Apply file modifications described in a YAML plan."""

    start_timestamp = datetime.datetime.now()

    file_manager_ref = context.get("file_manager") or file_manager
    guardrail_ref = context.get("guardrail") or guardrail
    context_bridge_ref = context.get("context_bridge")
    mission = context.get("mission")
    task_obj = context.get("task")

    variables = context.get("variables") or {}

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

    def _pick_string(*candidates: Optional[Any]) -> Optional[str]:
        for candidate in candidates:
            resolved = _resolve_placeholders(candidate, variables)
            if isinstance(resolved, str) and resolved.strip():
                return resolved.strip()
        return None

    def _resolve_workspace_path(candidate: str) -> Path:
        resolved = _resolve_placeholders(candidate, variables)
        if not resolved:
            raise ValueError("Empty path candidate")
        path_obj = Path(resolved)
        if not path_obj.is_absolute():
            path_obj = workspace_path / path_obj
        return path_obj.resolve()

    def _read_text(path_obj: Path, encoding: str) -> str:
        guardrail_ref.check_path(str(path_obj), operation="read")
        with open(path_obj, "r", encoding=encoding) as handle:
            return handle.read()

    def _safe_write_text(path_obj: Path, content: str, *, append: bool, encoding: str) -> None:
        guardrail_ref.check_path(str(path_obj), operation="append" if append else "write")
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(path_obj, mode, encoding=encoding) as handle:
            handle.write(content)

    def _stringify_content(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        return str(value)

    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            return lowered in {"1", "true", "yes", "on"}
        if isinstance(value, (int, float)):
            return bool(value)
        return False

    plan_data: Optional[Dict[str, Any]] = None
    plan_origin: Optional[str] = None
    inline_plan = params.get("plan")
    plan_path_hint = _pick_string(params.get("plan_path"), variables.get("WRITE_PLAN"))

    if isinstance(inline_plan, dict):
        plan_data = inline_plan
        plan_origin = "inline"
    elif isinstance(inline_plan, str) and inline_plan.strip():
        try:
            plan_data = yaml.safe_load(inline_plan) or {}
            plan_origin = "inline"
        except yaml.YAMLError:
            plan_path_hint = plan_path_hint or inline_plan
            plan_data = None

    plan_path_obj: Optional[Path] = None

    if plan_data is None:
        if not plan_path_hint:
            message = "[ERROR] task_apply_writes: missing plan_path or inline plan."
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "failed",
                        "reason": "missing_plan",
                        "task": getattr(task_obj, "name", None),
                        "mission": getattr(mission, "name", None),
                    },
                )
            return message
        try:
            plan_path_obj = _resolve_workspace_path(plan_path_hint)
        except Exception as exc:  # pragma: no cover - defensive
            message = f"[ERROR] Invalid plan path '{plan_path_hint}': {exc}"
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "failed",
                        "reason": "invalid_plan_path",
                        "details": str(exc),
                        "task": getattr(task_obj, "name", None),
                        "mission": getattr(mission, "name", None),
                    },
                )
            return message

        try:
            guardrail_ref.check_path(str(plan_path_obj), operation="read")
            plan_text = file_manager_ref.read_file(str(plan_path_obj))
        except Exception as exc:  # pragma: no cover - forwarding error context
            message = f"[ERROR] Failed to read plan '{plan_path_obj}': {exc}"
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "failed",
                        "reason": "plan_read_error",
                        "details": str(exc),
                        "task": getattr(task_obj, "name", None),
                        "mission": getattr(mission, "name", None),
                    },
                )
            return message

        try:
            plan_data = yaml.safe_load(plan_text) or {}
        except yaml.YAMLError as exc:
            message = f"[ERROR] Invalid YAML plan '{plan_path_obj}': {exc}"
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "failed",
                        "reason": "plan_parse_error",
                        "details": str(exc),
                        "task": getattr(task_obj, "name", None),
                        "mission": getattr(mission, "name", None),
                    },
                )
            return message

        plan_origin = str(plan_path_obj)
    else:
        if plan_path_hint:
            try:
                plan_path_obj = _resolve_workspace_path(plan_path_hint)
                plan_origin = str(plan_path_obj)
            except Exception:  # pragma: no cover - fallback to inline origin
                plan_origin = plan_origin or "inline"
        else:
            plan_origin = plan_origin or "inline"

    if not isinstance(plan_data, dict):
        message = "[ERROR] task_apply_writes: plan payload is not a mapping."
        if context_bridge_ref:
            context_bridge_ref.publish_diagnostic(
                "task_apply_writes",
                {
                    "event": "failed",
                    "reason": "plan_not_mapping",
                    "task": getattr(task_obj, "name", None),
                    "mission": getattr(mission, "name", None),
                },
            )
        return message

    changes = plan_data.get("changes") or []
    if not isinstance(changes, list):
        message = "[ERROR] task_apply_writes: plan.changes must be a list."
        if context_bridge_ref:
            context_bridge_ref.publish_diagnostic(
                "task_apply_writes",
                {
                    "event": "failed",
                    "reason": "changes_not_list",
                    "task": getattr(task_obj, "name", None),
                    "mission": getattr(mission, "name", None),
                },
            )
        return message

    dry_run = _to_bool(params.get("dry_run")) or _to_bool(plan_data.get("dry_run"))
    default_encoding = _pick_string(
        params.get("default_encoding"),
        plan_data.get("default_encoding"),
        variables.get("DEFAULT_ENCODING"),
    ) or "utf-8"
    guardrail_policy = _pick_string(
        params.get("guardrail_policy"),
        plan_data.get("guardrail_policy"),
        variables.get("CHANGE_POLICY"),
    ) or "guarded"

    output_config = context.get("output") if isinstance(context.get("output"), dict) else {}
    declared_outputs = context.get("declared_outputs") or []

    destination = _pick_string(
        params.get("report_path"),
        params.get("destination"),
        (params.get("output") or {}).get("destination") if isinstance(params.get("output"), dict) else None,
        output_config.get("destination") if isinstance(output_config, dict) else None,
    )

    if not destination:
        if isinstance(declared_outputs, dict):
            destination = _pick_string(declared_outputs.get("destination"))
        elif isinstance(declared_outputs, list):
            for entry in declared_outputs:
                if isinstance(entry, dict):
                    destination = _pick_string(entry.get("destination"))
                elif isinstance(entry, str):
                    destination = _pick_string(entry)
                if destination:
                    break

    if destination:
        report_path = Path(destination)
        if not report_path.is_absolute() and report_path.parent == Path("."):
            report_path = Path("reports") / report_path.name
    else:
        report_path = Path("reports") / "apply_writes_report.md"

    change_results: List[Dict[str, Any]] = []
    applied_changes = 0
    dry_run_changes = 0
    error_messages: List[str] = []

    if context_bridge_ref:
        context_bridge_ref.publish_diagnostic(
            "task_apply_writes",
            {
                "event": "started",
                "plan_origin": plan_origin,
                "dry_run": dry_run,
                "changes": len(changes),
                "workspace": str(workspace_path),
                "task": getattr(task_obj, "name", None),
                "mission": getattr(mission, "name", None),
                "guardrail_policy": guardrail_policy,
            },
        )

    for index, change in enumerate(changes, start=1):
        result_entry: Dict[str, Any] = {
            "index": index,
            "status": "pending",
            "file": None,
            "action": None,
            "message": "",
        }
        change_results.append(result_entry)

        if not isinstance(change, dict):
            result_entry.update({"status": "error", "message": "Change entry must be a mapping."})
            error_messages.append(f"#{index}: change entry is not a mapping")
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "change_error",
                        "index": index,
                        "reason": "invalid_entry",
                        "message": "Change entry must be a mapping.",
                    },
                )
            continue

        action_value = change.get("action") or change.get("operation")
        action = str(action_value).strip().lower() if action_value else ""
        if not action:
            result_entry.update({"status": "error", "message": "Missing action."})
            error_messages.append(f"#{index}: missing action")
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "change_error",
                        "index": index,
                        "reason": "missing_action",
                    },
                )
            continue

        file_value = change.get("file") or change.get("path") or change.get("target")
        if not file_value:
            result_entry.update({"status": "error", "message": "Missing file path."})
            error_messages.append(f"#{index}: missing file path")
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "change_error",
                        "index": index,
                        "reason": "missing_file",
                        "action": action,
                    },
                )
            continue

        try:
            target_path = _resolve_workspace_path(file_value)
        except Exception as exc:
            result_entry.update({"status": "error", "message": str(exc)})
            error_messages.append(f"#{index}: invalid target path - {exc}")
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "change_error",
                        "index": index,
                        "reason": "invalid_target_path",
                        "details": str(exc),
                        "action": action,
                    },
                )
            continue

        try:
            rel_path = target_path.relative_to(workspace_path)
            display_path = rel_path.as_posix()
        except ValueError:
            display_path = str(target_path)

        result_entry["file"] = display_path
        result_entry["action"] = action

        encoding = _pick_string(
            change.get("encoding"),
            plan_data.get("default_encoding"),
            params.get("encoding"),
            params.get("default_encoding"),
            variables.get("DEFAULT_ENCODING"),
        ) or default_encoding

        content_text = _stringify_content(change.get("content"))
        source_ref = change.get("source") or change.get("content_from")
        if source_ref:
            try:
                source_path = _resolve_workspace_path(source_ref)
                source_text = _read_text(source_path, encoding)
            except Exception as exc:
                result_entry.update({"status": "error", "message": f"Source read failed: {exc}"})
                error_messages.append(f"{display_path}: source read failed ({exc})")
                if context_bridge_ref:
                    context_bridge_ref.publish_diagnostic(
                        "task_apply_writes",
                        {
                            "event": "change_error",
                            "index": index,
                            "reason": "source_read_failed",
                            "details": str(exc),
                            "action": action,
                            "file": display_path,
                        },
                    )
                continue
            if content_text is None:
                content_text = source_text

        try:
            if action == "overwrite":
                if content_text is None:
                    raise ValueError("Missing content for overwrite.")
                if dry_run:
                    result_entry.update({"status": "dry_run", "message": "Dry-run: overwrite skipped."})
                    dry_run_changes += 1
                else:
                    _safe_write_text(target_path, content_text, append=False, encoding=encoding)
                    result_entry.update({"status": "applied", "message": "Overwrite completed."})
                    applied_changes += 1

            elif action == "append":
                if content_text is None:
                    raise ValueError("Missing content for append.")
                if dry_run:
                    result_entry.update({"status": "dry_run", "message": "Dry-run: append skipped."})
                    dry_run_changes += 1
                else:
                    _safe_write_text(target_path, content_text, append=True, encoding=encoding)
                    result_entry.update({"status": "applied", "message": "Append completed."})
                    applied_changes += 1

            elif action in {"insert_before", "insert_after", "replace_block"}:
                try:
                    existing_text = _read_text(target_path, encoding)
                except FileNotFoundError:
                    raise FileNotFoundError("Target file does not exist.")

                selectors = change.get("selectors") or {}
                if not isinstance(selectors, dict):
                    selectors = {}

                marker_value = _pick_string(
                    selectors.get("before") if action == "insert_before" else None,
                    selectors.get("after") if action == "insert_after" else None,
                    selectors.get("marker"),
                    selectors.get("target"),
                )
                start_marker = _pick_string(selectors.get("start"))
                end_marker = _pick_string(selectors.get("end"))

                if action == "replace_block":
                    if content_text is None:
                        raise ValueError("Missing content for replace_block.")
                    if start_marker and end_marker:
                        start_index = existing_text.find(start_marker)
                        if start_index == -1:
                            raise ValueError(f"Start marker '{start_marker}' not found.")
                        content_start = start_index + len(start_marker)
                        end_index = existing_text.find(end_marker, content_start)
                        if end_index == -1:
                            raise ValueError(f"End marker '{end_marker}' not found.")
                        new_text = existing_text[:content_start] + content_text + existing_text[end_index:]
                    elif marker_value:
                        if marker_value not in existing_text:
                            raise ValueError(f"Marker '{marker_value}' not found.")
                        new_text = existing_text.replace(marker_value, content_text, 1)
                    else:
                        raise ValueError("Selectors must define start/end or marker for replace_block.")

                    if dry_run:
                        result_entry.update({"status": "dry_run", "message": "Dry-run: replace_block skipped."})
                        dry_run_changes += 1
                    else:
                        _safe_write_text(target_path, new_text, append=False, encoding=encoding)
                        result_entry.update({"status": "applied", "message": "replace_block completed."})
                        applied_changes += 1

                else:
                    if content_text is None:
                        raise ValueError("Missing content for insertion.")
                    if not marker_value:
                        raise ValueError("Selectors must provide a marker for insertion.")
                    marker_index = existing_text.find(marker_value)
                    if marker_index == -1:
                        raise ValueError(f"Marker '{marker_value}' not found.")
                    if action == "insert_before":
                        new_text = existing_text[:marker_index] + content_text + existing_text[marker_index:]
                    else:
                        insert_position = marker_index + len(marker_value)
                        new_text = existing_text[:insert_position] + content_text + existing_text[insert_position:]

                    if dry_run:
                        result_entry.update({"status": "dry_run", "message": f"Dry-run: {action} skipped."})
                        dry_run_changes += 1
                    else:
                        _safe_write_text(target_path, new_text, append=False, encoding=encoding)
                        result_entry.update({"status": "applied", "message": f"{action} completed."})
                        applied_changes += 1

            else:
                raise ValueError(f"Unsupported action '{action}'.")

        except Exception as exc:  # pragma: no cover - aggregates errors for diagnostics
            result_entry.update({"status": "error", "message": str(exc)})
            error_messages.append(f"{display_path}: {exc}")
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "change_error",
                        "index": index,
                        "reason": "exception",
                        "details": str(exc),
                        "action": action,
                        "file": display_path,
                    },
                )
        else:
            if context_bridge_ref:
                context_bridge_ref.publish_diagnostic(
                    "task_apply_writes",
                    {
                        "event": "change_processed",
                        "index": index,
                        "status": result_entry["status"],
                        "action": action,
                        "file": display_path,
                    },
                )

    duration_seconds = (datetime.datetime.now() - start_timestamp).total_seconds()

    report_lines = [
        "# Apply Writes Execution Log",
        "",
        f"- Mission: {getattr(mission, 'name', 'unknown')}",
        f"- Task: {getattr(task_obj, 'name', 'unknown')}",
        f"- Plan origin: {plan_origin or 'unknown'}",
        f"- Guardrail policy: {guardrail_policy}",
        f"- Dry run: {'yes' if dry_run else 'no'}",
        f"- Started at: {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Duration (s): {duration_seconds:.2f}",
        "",
        "## Changes",
    ]

    if change_results:
        for entry in change_results:
            report_lines.append(
                f"- [{entry['status'].upper()}] {entry.get('action', '?')} :: {entry.get('file', '?')} - {entry.get('message', '')}"
            )
    else:
        report_lines.append("- No changes declared in plan.")

    if error_messages:
        report_lines.extend(["", "## Errors", *[f"- {msg}" for msg in error_messages]])

    report_lines.append("")

    report_path_str = str(report_path)
    try:
        _safe_write_text(report_path, "\n".join(report_lines), append=False, encoding="utf-8")
    except Exception as exc:  # pragma: no cover - writing log should rarely fail
        error_messages.append(f"Failed to write report: {exc}")
        if context_bridge_ref:
            context_bridge_ref.publish_diagnostic(
                "task_apply_writes",
                {
                    "event": "report_write_failed",
                    "details": str(exc),
                    "destination": report_path_str,
                },
            )

    summary = {
        "plan_origin": plan_origin,
        "report_path": report_path_str,
        "dry_run": dry_run,
        "applied": applied_changes,
        "dry_run_changes": dry_run_changes,
        "errors": error_messages,
        "duration_seconds": round(duration_seconds, 3),
    }

    record = None
    if context_bridge_ref:
        status_flag = "created_with_warnings" if error_messages else "created"
        record = context_bridge_ref.register_output(
            report_path_str,
            format="markdown",
            mission=getattr(mission, "name", None),
            task=getattr(task_obj, "name", None),
            status=status_flag,
            summary=summary,
        )

        final_event = "completed_with_warnings" if error_messages else "completed"
        if dry_run and not error_messages:
            final_event = "completed_dry_run"

        context_bridge_ref.publish_diagnostic(
            "task_apply_writes",
            {
                "event": final_event,
                "summary": summary,
                "record": record,
            },
        )

    status_prefix = "[WARN]" if error_messages else ("[DRY]" if dry_run else "[OK]")
    return (
        f"{status_prefix} Plan applique : {applied_changes} change(s), "
        f"{dry_run_changes} en simulation, rapport {report_path_str}"
    )


def task_gather_overview(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Collecte une vue d'ensemble du workspace : structure, fichiers, dossiers.
    Stocke les données dans mission.metadata pour utilisation par task_generate_report.
    """
    start_timestamp = datetime.datetime.now()

    file_manager_ref = context.get("file_manager") or file_manager
    guardrail_ref = context.get("guardrail") or guardrail
    context_bridge_ref = context.get("context_bridge")
    mission = context.get("mission")
    task_obj = context.get("task")

    variables = context.get("variables") or {}

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

    # Paramètres de scan
    scan_depth = int(params.get("scan_depth") or params.get("depth") or 3)
    include_extensions = params.get("include_extensions") or params.get("include") or [".py", ".md", ".yaml", ".yalm", ".txt"]
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
            if guardrail_ref.is_sanctuary_path(str(directory)):
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
    if mission:
        if "gathered_data" not in mission.metadata:
            mission.metadata["gathered_data"] = {}
        mission.metadata["gathered_data"].update(gathered_data)

    if context_bridge_ref:
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

    status_prefix = "[WARN]" if errors else "[OK]"
    return (
        f"{status_prefix} Vue d'ensemble collectée : {total_dirs} dossier(s), "
        f"{total_files} fichier(s) ({len(matching_files)} correspondant aux extensions)"
    )


def task_generate_report(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Génère un rapport Markdown basé sur les données collectées par task_gather_overview.
    """
    start_timestamp = datetime.datetime.now()

    file_manager_ref = context.get("file_manager") or file_manager
    guardrail_ref = context.get("guardrail") or guardrail
    context_bridge_ref = context.get("context_bridge")
    mission = context.get("mission")
    task_obj = context.get("task")

    variables = context.get("variables") or {}

    # Récupérer les données collectées
    gathered_data = None
    if mission and "gathered_data" in mission.metadata:
        gathered_data = mission.metadata["gathered_data"]

    if not gathered_data:
        # Fallback : scanner rapidement si aucune donnée n'a été collectée
        logger.warning("Aucune donnée collectée trouvée, génération d'un rapport minimal")
        gathered_data = {
            "workspace": str(context.get("workspace_path") or "."),
            "directories": [],
            "files": [],
            "matching_files": [],
            "file_stats": {},
            "tree_lines": ["./"],
            "total_directories": 0,
            "total_files": 0,
            "matching_files_count": 0,
            "errors": [],
        }

    # Destination du rapport
    def _pick_string(*candidates):
        for candidate in candidates:
            resolved = _resolve_placeholders(candidate, variables)
            if isinstance(resolved, str) and resolved.strip():
                return resolved.strip()
        return None

    destination = _pick_string(
        params.get("destination"),
        params.get("report_path"),
        (params.get("output") or {}).get("destination") if isinstance(params.get("output"), dict) else None,
    )

    if not destination:
        declared_outputs = context.get("declared_outputs") or []
        if isinstance(declared_outputs, dict):
            destination = _pick_string(declared_outputs.get("destination"))
        elif isinstance(declared_outputs, list):
            for entry in declared_outputs:
                if isinstance(entry, dict):
                    destination = _pick_string(entry.get("destination"))
                elif isinstance(entry, str):
                    destination = _pick_string(entry)
                if destination:
                    break

    report_path = Path(destination or "reports/context_report.md")
    if not report_path.is_absolute() and report_path.parent == Path("."):
        report_path = Path("reports") / report_path.name

    # Générer le contenu Markdown
    report_lines = [
        "# Rapport de Lecture AIHomeCoder",
        "",
        f"**Mission :** {getattr(mission, 'name', 'Unknown')}",
        f"**Workspace :** `{gathered_data['workspace']}`",
        f"**Généré le :** {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Vue d'ensemble",
        "",
        f"- **Répertoires trouvés :** {gathered_data['total_directories']}",
        f"- **Fichiers trouvés :** {gathered_data['total_files']}",
        f"- **Fichiers correspondant aux critères :** {gathered_data['matching_files_count']}",
        "",
    ]

    if gathered_data.get("extensions"):
        report_lines.extend([
            "## Extensions ciblées",
            "",
        ])
        for ext in gathered_data["extensions"]:
            count = sum(1 for f in gathered_data.get("files", []) if f.endswith(ext))
            report_lines.append(f"- **{ext}** : {count} fichier(s)")

        report_lines.append("")

    # Statistiques par extension
    if gathered_data.get("file_stats"):
        report_lines.extend([
            "## Statistiques par extension",
            "",
        ])
        for ext, count in sorted(gathered_data["file_stats"].items(), key=lambda x: -x[1]):
            report_lines.append(f"- **{ext}** : {count} fichier(s)")

        report_lines.append("")

    # Arborescence
    if gathered_data.get("tree_lines"):
        max_tree_lines = 200  # Limiter pour éviter des rapports trop longs
        tree_display = gathered_data["tree_lines"][:max_tree_lines]
        if len(gathered_data["tree_lines"]) > max_tree_lines:
            tree_display.append(f"... ({len(gathered_data['tree_lines']) - max_tree_lines} lignes supplémentaires)")

        report_lines.extend([
            "## Arborescence du projet",
            "",
            "```",
            *tree_display,
            "```",
            "",
        ])

    # Fichiers correspondant aux critères
    if gathered_data.get("matching_files"):
        report_lines.extend([
            "## Fichiers correspondant aux critères",
            "",
        ])
        for file_path in gathered_data["matching_files"][:100]:  # Limiter à 100 fichiers
            report_lines.append(f"- `{file_path}`")

        if len(gathered_data["matching_files"]) > 100:
            report_lines.append(f"\n... et {len(gathered_data['matching_files']) - 100} fichier(s) supplémentaire(s)")

        report_lines.append("")

    # Erreurs
    if gathered_data.get("errors"):
        report_lines.extend([
            "## Incidents",
            "",
        ])
        for error in gathered_data["errors"]:
            report_lines.append(f"- ⚠️ WARNING: {error}")
        report_lines.append("")

    report_lines.append("---")
    report_lines.append(f"*Rapport généré par AIHomeCoder v1.0.0*")

    report_content = "\n".join(report_lines)

    # Écrire le rapport
    report_path_str = str(report_path)
    guardrail_ref.check_path(report_path_str, operation="write")
    file_manager_ref.write_file(report_path_str, report_content)

    # Enregistrer dans context_bridge
    if context_bridge_ref:
        summary = {
            "report_path": report_path_str,
            "workspace": gathered_data["workspace"],
            "directories": gathered_data["total_directories"],
            "files": gathered_data["total_files"],
            "matching_files": gathered_data["matching_files_count"],
        }
        record = context_bridge_ref.register_output(
            report_path_str,
            format="markdown",
            mission=getattr(mission, "name", None),
            task=getattr(task_obj, "name", None),
            summary=summary,
        )
        context_bridge_ref.publish_diagnostic(
            "task_generate_report",
            {
                "event": "completed",
                "summary": summary,
                "record": record,
            },
        )

    return (
        f"[OK] Rapport généré : {report_path_str} "
        f"({gathered_data['total_directories']} dossier(s), {gathered_data['total_files']} fichier(s))"
    )