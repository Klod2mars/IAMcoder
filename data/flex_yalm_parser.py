"""
Data Layer: Flex YALM Parser
Parser tolérant pour missions YAML ou prompt-only.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from core.file_manager import FileManagerError, file_manager
from domain.entities import Mission, Task
from .yaml_parser import YAMLParser, YAMLParserError


class FlexYALMParserError(YAMLParserError):
    """Exception levée lors d'une erreur de parsing flexible."""


class FlexYALMParser:
    """Parser souple capable d'interpréter des missions partielles ou prompt-only."""

    def __init__(self, *, strict_parser: Optional[YAMLParser] = None) -> None:
        self.strict_parser = strict_parser or YAMLParser()
        self.last_diagnostics: Optional[Dict[str, Any]] = None

    def parse_file(self, file_path: str, *, fallback_name: Optional[str] = None) -> Mission:
        """Lit un fichier .yalm ou .yaml et construit une mission flexible."""

        try:
            content = file_manager.read_file(file_path)
        except FileManagerError as exc:
            raise FlexYALMParserError(f"Failed to read YAML file '{file_path}': {exc}") from exc

        mission = self.parse_content(
            content,
            source=file_path,
            fallback_name=fallback_name or Path(file_path).stem,
        )

        return mission

    def parse_content(
        self,
        content: str,
        *,
        source: Optional[str] = None,
        fallback_name: Optional[str] = None,
    ) -> Mission:
        """Parse une chaîne YAML ou un prompt brut et renvoie une mission."""

        if not content or not content.strip():
            raise FlexYALMParserError("Empty YAML content.")

        data = self._safe_load(content)
        normalized, diagnostics = self._normalize(
            data,
            source=source,
            fallback_name=fallback_name,
        )

        mission = self._build_mission(normalized, diagnostics)
        self.last_diagnostics = diagnostics
        return mission

    def get_last_diagnostics(self) -> Dict[str, Any]:
        """Retourne la dernière analyse effectuée par le parser."""

        return self.last_diagnostics or {}

    # ---------------------------------------------------------------------
    # Étapes internes
    # ---------------------------------------------------------------------

    def _safe_load(self, content: str) -> Any:
        try:
            return yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise FlexYALMParserError(f"Invalid YAML syntax: {exc}") from exc

    def _normalize(
        self,
        raw: Any,
        *,
        source: Optional[str],
        fallback_name: Optional[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        warnings: List[str] = []
        provided_sections: List[str]
        context: Any = {}
        outputs: Any = None
        post_actions: Any = []
        description_hint = ""

        if isinstance(raw, dict):
            provided_sections = sorted(raw.keys())
            raw_meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
            explicit_tasks = self._coerce_task_container(raw.get("tasks"))

            if "meta" not in raw:
                warnings.append("Missing 'meta' section; generated fallback metadata.")
            if not raw.get("tasks"):
                warnings.append("Missing 'tasks' section; synthesizing tasks from prompts.")

            if explicit_tasks:
                task_candidates = explicit_tasks
                fallback_trace = [
                    {
                        "source": "tasks",
                        "count": len(explicit_tasks),
                    }
                ]
            else:
                task_candidates, fallback_trace = self._collect_implicit_tasks(raw)

            tasks, task_warnings = self._build_task_blueprints(task_candidates)
            warnings.extend(task_warnings)

            meta = self._build_meta(
                raw_meta,
                fallback_name=fallback_name,
                source=source,
                root=raw,
            )

            context = raw.get("context") or {}
            outputs = raw.get("outputs")
            post_actions = raw.get("post_actions") or []
            description_hint = (
                raw.get("description")
                or raw_meta.get("description")
                or (tasks[0]["goal"] if tasks else "")
            )

            if raw.get("prompt") and not explicit_tasks:
                mode = "meta_plus_prompt"
            elif "meta" in raw and raw.get("tasks"):
                mode = "strict"
            elif "meta" in raw:
                mode = "flex_meta"
            elif raw.get("tasks"):
                mode = "tasks_only"
            else:
                mode = "prompt_only"

        elif isinstance(raw, list):
            provided_sections = ["<list>"]
            fallback_trace = [
                {
                    "source": "root_list",
                    "count": len(raw),
                }
            ]
            tasks, task_warnings = self._build_task_blueprints(raw)
            warnings.append("Root YAML list interpreted as sequential instructions.")
            warnings.extend(task_warnings)
            meta = self._build_meta({}, fallback_name=fallback_name, source=source)
            description_hint = tasks[0]["goal"] if tasks else ""
            mode = "prompt_list"

        elif isinstance(raw, str):
            provided_sections = ["<string>"]
            fallback_trace = [
                {
                    "source": "root_string",
                    "count": 1,
                }
            ]
            tasks, task_warnings = self._build_task_blueprints([raw])
            warnings.append("Root YAML string interpreted as single instruction.")
            warnings.extend(task_warnings)
            meta = self._build_meta({}, fallback_name=fallback_name, source=source)
            description_hint = tasks[0]["goal"] if tasks else ""
            mode = "prompt_only"

        elif raw is None:
            raise FlexYALMParserError("Empty YAML content.")

        else:
            raise FlexYALMParserError(
                f"Unsupported YAML root type: {type(raw).__name__}."
            )

        if not tasks:
            raise FlexYALMParserError("Unable to synthesize at least one task from YAML content.")

        normalized = {
            "meta": meta,
            "tasks": tasks,
            "context": context,
            "outputs": outputs,
            "post_actions": post_actions,
            "description_hint": description_hint,
        }

        diagnostics = {
            "source": source,
            "mode": mode,
            "warnings": warnings,
            "task_count": len(tasks),
            "provided_sections": provided_sections,
            "primary_prompt": tasks[0]["goal"] if tasks else "",
            "fallback_chain": fallback_trace,
        }

        return normalized, diagnostics

    def _build_mission(
        self,
        normalized: Dict[str, Any],
        diagnostics: Dict[str, Any],
    ) -> Mission:
        meta = normalized["meta"]
        description = normalized.get("description_hint") or meta.get("description", "")

        mission = Mission(
            name=meta["project_name"],
            description=description or "",
            metadata={
                "version": meta.get("version", "1.0.0"),
                "author": meta.get("author", ""),
                "architecture": meta.get("architecture", ""),
                "language": meta.get("language", ""),
                "meta": meta,
                "context": normalized.get("context"),
                "outputs": normalized.get("outputs"),
                "post_actions": normalized.get("post_actions"),
                "flex_parser": diagnostics,
            },
        )

        for blueprint in normalized["tasks"]:
            task = Task(
                name=blueprint["name"],
                goal=blueprint["goal"],
                task_type=blueprint.get("task_type", "instruction"),
                parameters=blueprint.get("parameters", {}),
            )
            mission.add_task(task)

        return mission

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _coerce_task_container(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [
                {"name": str(key), "goal": val}
                for key, val in value.items()
            ]
        return [value]

    def _collect_implicit_tasks(self, raw: Dict[str, Any]) -> Tuple[List[Any], List[Dict[str, Any]]]:
        candidates: List[Any] = []
        fallback_trace: List[Dict[str, Any]] = []

        def extend_from(value: Any, source: str) -> None:
            items = self._ensure_iterable(value)
            if not items:
                return
            fallback_trace.append({"source": source, "count": len(items)})
            candidates.extend(items)

        meta = raw.get("meta")
        if isinstance(meta, dict):
            extend_from(meta.get("task"), "meta.task")
            extend_from(meta.get("tasks"), "meta.tasks")
            extend_from(meta.get("mission"), "meta.mission")
            extend_from(meta.get("mission_prompt"), "meta.mission_prompt")
            extend_from(meta.get("goal"), "meta.goal")
            extend_from(meta.get("prompt"), "meta.prompt")

        extend_from(raw.get("mission"), "root.mission")
        extend_from(raw.get("task"), "root.task")
        extend_from(raw.get("prompt"), "root.prompt")
        extend_from(raw.get("prompts"), "root.prompts")
        extend_from(raw.get("instructions"), "root.instructions")
        extend_from(raw.get("instruction"), "root.instruction")
        extend_from(raw.get("steps"), "root.steps")

        if not candidates and raw.get("description"):
            extend_from(raw.get("description"), "root.description")

        return candidates, fallback_trace

    def _ensure_iterable(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple) or isinstance(value, set):
            return list(value)
        return [value]

    def _build_task_blueprints(self, raw_tasks: List[Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
        blueprints: List[Dict[str, Any]] = []
        warnings: List[str] = []

        for index, raw_task in enumerate(raw_tasks, start=1):
            try:
                blueprints.append(self._coerce_task_blueprint(index, raw_task))
            except FlexYALMParserError as exc:
                warnings.append(str(exc))

        return blueprints, warnings

    def _coerce_task_blueprint(self, index: int, raw_task: Any) -> Dict[str, Any]:
        if isinstance(raw_task, Task):
            return {
                "name": raw_task.name,
                "goal": raw_task.goal,
                "task_type": raw_task.task_type,
                "parameters": raw_task.parameters,
            }

        if isinstance(raw_task, dict):
            name = self._pick_first(
                raw_task,
                ["name", "title", "id"],
                default=f"task_{index}",
            )
            goal_value = self._pick_first(
                raw_task,
                ["goal", "prompt", "description", "summary"],
            )

            if isinstance(goal_value, list):
                goal = " ".join(str(item).strip() for item in goal_value if str(item).strip())
            else:
                goal = str(goal_value).strip() if goal_value else ""

            if not goal:
                raise FlexYALMParserError(
                    f"Task {index}: missing goal/description in provided mapping."
                )

            task_type = str(
                self._pick_first(raw_task, ["task_type", "type"], default="instruction")
            )

            parameters = raw_task.get("parameters")
            if isinstance(parameters, dict):
                params = dict(parameters)
            elif parameters is None:
                params = {}
            else:
                params = {"value": parameters}

            for key, value in raw_task.items():
                if key in {"name", "title", "id", "goal", "prompt", "description", "summary", "task_type", "type", "parameters"}:
                    continue
                params[key] = value

            return {
                "name": name,
                "goal": goal,
                "task_type": task_type,
                "parameters": params,
            }

        if isinstance(raw_task, str):
            goal = raw_task.strip()
            if not goal:
                raise FlexYALMParserError(f"Task {index}: empty instruction string.")
            return {
                "name": f"task_{index}",
                "goal": goal,
                "task_type": "instruction",
                "parameters": {},
            }

        raise FlexYALMParserError(
            f"Task {index}: unsupported structure '{type(raw_task).__name__}'."
        )

    def _build_meta(
        self,
        meta: Optional[Dict[str, Any]],
        *,
        fallback_name: Optional[str],
        source: Optional[str],
        root: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta = dict(meta or {})

        candidates: List[str] = []
        for key in ("project_name", "mission_id", "name", "title"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        if root:
            for key in ("project_name", "mission", "mission_name", "name", "title"):
                value = root.get(key)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())

        if fallback_name and isinstance(fallback_name, str):
            candidates.append(fallback_name)

        if source:
            candidates.append(Path(source).stem)

        project_name = self._slugify(next((c for c in candidates if c), None))
        if not project_name:
            project_name = f"mission_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        meta.setdefault("project_name", project_name)
        meta.setdefault("mission_id", project_name)
        meta.setdefault("version", meta.get("version", "1.0.0"))

        return meta

    def _pick_first(
        self,
        mapping: Dict[str, Any],
        keys: List[str],
        *,
        default: Optional[str] = None,
    ) -> Optional[Any]:
        for key in keys:
            value = mapping.get(key)
            if value is not None:
                return value
        return default

    def _slugify(self, value: Optional[str]) -> str:
        if not value:
            return ""
        value = value.strip().lower()
        value = re.sub(r"[^a-z0-9]+", "_", value)
        value = re.sub(r"_+", "_", value).strip("_")
        return value or ""


# Instance utilitaire optionnelle
flex_yaml_parser = FlexYALMParser()


