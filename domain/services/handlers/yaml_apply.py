# domain/services/handlers/yaml_apply.py
from pathlib import Path
import json
import datetime
from typing import Any, Dict
import logging
import re

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

        # parameters
        anchor_pattern = item.get("anchor_pattern") or anchor
        use_regex = bool(item.get("anchor_regex")) or bool(item.get("anchor_pattern"))
        case_insensitive = bool(item.get("case_insensitive", False))
        ignore_indent = bool(item.get("ignore_indent", False))
        replace_all = bool(item.get("replace_all", True))
        occurrence = item.get("occurrence")  # optional: 1-based occurrence index
        flags = 0
        if case_insensitive:
            flags |= re.IGNORECASE
        if item.get("multiline", False):
            flags |= re.MULTILINE
        if item.get("dotall", False):
            flags |= re.DOTALL

        matches = []
        # Find matches according to mode
        try:
            if use_regex and anchor_pattern:
                pattern = re.compile(anchor_pattern, flags)
                for m in pattern.finditer(content):
                    matches.append((m.start(), m.end(), m.group(0)))
            elif anchor:
                if ignore_indent:
                    # match anchor ignoring leading indentation
                    pattern = re.compile(r'^[ \t]*' + re.escape(anchor), re.MULTILINE)
                    for m in pattern.finditer(content):
                        matches.append((m.start(), m.end(), m.group(0)))
                else:
                    # simple substring search (all occurrences)
                    start_idx = 0
                    while True:
                        idx = content.find(anchor, start_idx)
                        if idx == -1:
                            break
                        matches.append((idx, idx + len(anchor), content[idx:idx + len(anchor)]))
                        start_idx = idx + len(anchor)
        except re.error as e:
            entry["error"] = f"anchor_pattern_error: {str(e)}"
            report["entries"].append(entry)
            continue

        entry["occurrences"] = len(matches)
        entry["found"] = len(matches) > 0
        # include small diagnostics about matches (first 5)
        entry["matches"] = []
        for s, e, sn in matches[:5]:
            ctx_s = max(0, s - 30)
            ctx_e = min(len(content), e + 30)
            snippet = content[ctx_s:ctx_e].replace("\n", "\\n")
            entry["matches"].append({"start": s, "end": e, "snippet": snippet})

        if matches and not dry_run:
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

                new_content = content

                if use_regex and anchor_pattern:
                    # regex replacement
                    if include_anchor:
                        repl = lambda m: m.group(0) + after
                    else:
                        repl = after
                    if replace_all:
                        new_content, n = pattern.subn(repl, new_content)
                    else:
                        # replace only the specified occurrence or the first one
                        count = 1
                        if occurrence:
                            # perform replacement of the specific occurrence
                            occ_index = int(occurrence) - 1
                            # iterate matches to reconstruct result
                            parts = []
                            last = 0
                            replaced = 0
                            for i, m in enumerate(pattern.finditer(new_content)):
                                if i == occ_index:
                                    parts.append(new_content[last:m.start()])
                                    if include_anchor:
                                        parts.append(m.group(0) + after)
                                    else:
                                        parts.append(after)
                                    last = m.end()
                                    replaced = 1
                                    break
                            if replaced:
                                parts.append(new_content[last:])
                                new_content = "".join(parts)
                                n = replaced
                            else:
                                n = 0
                        else:
                            new_content, n = pattern.subn(repl, new_content, count=1)
                else:
                    # simple substring replacement
                    if include_anchor:
                        if replace_all:
                            new_content = new_content.replace(anchor, anchor + after)
                            n = entry["occurrences"]
                        else:
                            if occurrence:
                                new_content = new_content.replace(anchor, anchor + after, 1)  # simplest: replace first occurrence only
                                n = 1
                            else:
                                new_content = new_content.replace(anchor, anchor + after, 1)
                                n = 1
                    else:
                        if replace_all:
                            new_content = new_content.replace(anchor, after)
                            n = entry["occurrences"]
                        else:
                            new_content = new_content.replace(anchor, after, 1)
                            n = 1

                fm.write_file(str(target_path), new_content)
                entry["applied"] = True
                entry["applied_matches"] = n
            except Exception as e:
                entry["error"] = f"apply_error: {str(e)}"
                errors.append(str(e))

        # if no matches, optionally add a suggestion
        if not matches:
            # simple suggestion: try ignore_indent or case_insensitive or regex
            sug = []
            if not ignore_indent:
                sug.append("try 'ignore_indent: true'")
            if not case_insensitive:
                sug.append("try 'case_insensitive: true'")
            if not use_regex:
                sug.append("or use 'anchor_pattern' (regex) to match variants)")
            if sug:
                entry.setdefault("suggestions", []).append(", ".join(sug))

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
