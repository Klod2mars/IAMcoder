# domain/services/handlers/analysis.py
from pathlib import Path
from collections import Counter
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

from core.file_manager import file_manager
from core.guardrail import guardrail

logger = logging.getLogger(__name__)


def analyze_workspace(params: Dict[str, Any]) -> str:
    """
    Equivalent minimal de TaskLogicHandler._analyze_workspace.
    - params: dict with keys workspace_path (or 'workspace'), depth (int), output_data (optional path)
    Returns a status string and writes JSON payload to output_data if provided.
    """
    workspace = Path(params.get("workspace_path", params.get("workspace", "."))).resolve()
    depth = int(params.get("depth", 3))
    stats = Counter()
    lines: List[str] = []

    def explore(path: Path, level=0):
        if level > depth:
            return
        indent = "│   " * level
        lines.append(f"{indent}├── {path.name}/")
        try:
            for item in sorted(path.iterdir()):
                if item.is_dir():
                    explore(item, level + 1)
                else:
                    stats[item.suffix or "[none]"] += 1
                    lines.append(f"{indent}│   {item.name}")
        except Exception as exc:
            logger.debug("explore(): cannot list %s: %s", path, exc, exc_info=True)

    explore(workspace)

    output_json = params.get("output_data")
    if output_json:
        out_path = Path(output_json)
        payload = {
            "workspace": str(workspace),
            "tree": lines,
            "extensions": dict(stats),
        }
        try:
            guardrail.check_path(str(out_path), operation="write")
        except Exception:
            logger.debug("Guardrail check_path failed for %s", out_path, exc_info=True)
        try:
            if hasattr(file_manager, "write_file"):
                file_manager.write_file(str(out_path), json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to write analyze_workspace output: %s", exc)

    return f"[OK] Structure analysée : {workspace} ({len(lines)} entrées)"


def generate_markdown(params: Dict[str, Any]) -> str:
    """
    Equivalent minimal de TaskLogicHandler._generate_markdown.
    - params: dict with optional 'destination' (report path)
    Returns a status string and writes a markdown report to destination (reports/...).
    """
    report_path = Path(params.get("destination", "reports/tree_readonly.md"))
    report_path.parent.mkdir(parents=True, exist_ok=True)

    data_path = Path("data/tree_" + report_path.stem + ".json")
    data: Dict[str, Any] = {}
    # Prefer to read via filesystem; try file_manager if useful
    try:
        if data_path.exists():
            try:
                # Try reading via file_manager if available
                if hasattr(file_manager, "read_file"):
                    raw = file_manager.read_file(str(data_path))
                    data = json.loads(raw) if raw else {}
                else:
                    data = json.loads(data_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.debug("Failed to load data_path %s via file_manager/filesystem: %s", data_path, exc)
                data = {}
    except Exception:
        data = {}

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    workspace = data.get("workspace", "?")
    lines = data.get("tree", [])
    stats = data.get("extensions", {})

    md = [
        f"# 🌳 Rapport de Lecture — {Path(workspace).name if workspace else Path('.').name}",
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
    for ext, count in (stats.items() if isinstance(stats, dict) else []):
        md.append(f"- **{ext}** : {count} fichier(s)")
    md.append("\n---\n_Rapport généré par AIHomeCoder v1.0.0_")

    try:
        guardrail.check_path(str(report_path), operation="write")
    except Exception:
        logger.debug("Guardrail check_path failed for %s", report_path, exc_info=True)
    try:
        if hasattr(file_manager, "write_file"):
            file_manager.write_file(str(report_path), "\n".join(md))
        else:
            report_path.write_text("\n".join(md), encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to write generate_markdown report: %s", exc)

    return f"[OK] Rapport Markdown généré : {report_path}"
