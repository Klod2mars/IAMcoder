# domain/services/handlers/report_generation.py
from pathlib import Path
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

from core.file_manager import file_manager
from core.guardrail import guardrail

logger = logging.getLogger(__name__)


def _resolve_placeholders(value: Any, variables: Dict[str, str]) -> Any:
    """Replace ${VAR} placeholders in strings, lists or dicts (minimal)."""
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


def _pick_string(*candidates: Optional[Any]) -> Optional[str]:
    for candidate in candidates:
        resolved = candidate
        if isinstance(candidate, str):
            resolved = candidate.strip()
        # If candidate might be a placeholder or other type, return its string form if non-empty
        if isinstance(resolved, str) and resolved:
            return resolved
    return None


def task_generate_report(params: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Génère un rapport Markdown basé sur les données collectées par task_gather_overview.
    - params: dict
    - context: dict (workspace, workspace_path, variables, file_manager, guardrail, context_bridge, mission, task)
    Retourne une string de statut et écrit le rapport Markdown.
    """
    start_timestamp = datetime.datetime.now()

    fm = context.get("file_manager") or file_manager
    guard = context.get("guardrail") or guardrail
    context_bridge_ref = context.get("context_bridge")
    mission = context.get("mission")
    task_obj = context.get("task")

    variables = context.get("variables") or {}

    # Récupérer les données collectées
    gathered_data = None
    if mission and isinstance(getattr(mission, "metadata", None), dict) and "gathered_data" in mission.metadata:
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
    destination = None
    try:
        destination = _pick_string(
            params.get("destination"),
            params.get("report_path"),
            (params.get("output") or {}).get("destination") if isinstance(params.get("output"), dict) else None,
        )
    except Exception:
        destination = None

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
    report_lines: List[str] = [
        "# Rapport de Lecture AIHomeCoder",
        "",
        f"**Mission :** {getattr(mission, 'name', 'Unknown')}",
        f"**Workspace :** `{gathered_data.get('workspace', '?')}`",
        f"**Généré le :** {start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Vue d'ensemble",
        "",
        f"- **Répertoires trouvés :** {gathered_data.get('total_directories', 0)}",
        f"- **Fichiers trouvés :** {gathered_data.get('total_files', 0)}",
        f"- **Fichiers correspondant aux critères :** {gathered_data.get('matching_files_count', 0)}",
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
        # Sort by count descending
        try:
            items = sorted(gathered_data["file_stats"].items(), key=lambda x: -x[1])
        except Exception:
            items = list(gathered_data["file_stats"].items())
        for ext, count in items:
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
            report_lines.append(f"... et {len(gathered_data['matching_files']) - 100} fichier(s) supplémentaire(s)")
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
    try:
        guard.check_path(report_path_str, operation="write")
    except Exception:
        logger.debug("Guardrail check_path failed for %s", report_path_str, exc_info=True)

    try:
        if hasattr(fm, "write_file"):
            fm.write_file(report_path_str, report_content)
        else:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report_content, encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to write report: %s", exc)
        # best-effort: still return status with failure info

    # Enregistrer dans context_bridge
    if context_bridge_ref:
        try:
            summary = {
                "report_path": report_path_str,
                "workspace": gathered_data.get("workspace"),
                "directories": gathered_data.get("total_directories"),
                "files": gathered_data.get("total_files"),
                "matching_files": gathered_data.get("matching_files_count"),
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
        except Exception:
            logger.debug("Context bridge publish diagnostic failed at completion", exc_info=True)

    return (
        f"[OK] Rapport généré : {report_path_str} "
        f"({gathered_data.get('total_directories', 0)} dossier(s), {gathered_data.get('total_files', 0)} fichier(s))"
    )
