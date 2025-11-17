"""Core ContextBridge module.

Provides a single place to coordinate workspace selection, declared outputs,
and diagnostics exchanged between application layers during a mission run.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .workspace_store import WorkspaceStore, get_workspace_store

if TYPE_CHECKING:  # pragma: no cover - import for type hints only
    from domain.entities import Mission


class ContextBridge:
    """Central coordination hub for mission context."""

    def __init__(
        self,
        *,
        workspace_store: Optional[WorkspaceStore] = None,
    ) -> None:
        self._workspace_store = workspace_store or get_workspace_store()
        self._current_workspace: Optional[str] = self._workspace_store.get_last_workspace()
        self._outputs: List[Dict[str, Any]] = []
        self._diagnostics: List[Dict[str, Any]] = []
        self._mission_meta: Dict[str, Any] = {}
        self._mission_context: Dict[str, Any] = {}
        self._mission_name: Optional[str] = None

    # ------------------------------------------------------------------
    # Workspace management
    # ------------------------------------------------------------------
    def set_workspace(self, path: str, *, auto_run: Optional[bool] = None) -> None:
        """Record the active workspace path and persist it via the store."""

        if not path:
            return

        normalized = str(Path(path).resolve())
        self._current_workspace = normalized
        self._workspace_store.set_workspace(normalized, auto_run=auto_run)

    def get_workspace(self) -> Optional[str]:
        """Return the active workspace path, if any."""

        return self._current_workspace

    def get_auto_run(self) -> bool:
        """Expose the persisted auto-run flag from the workspace store."""

        return bool(self._workspace_store.get_auto_run())

    def get_mode(self) -> Optional[str]:
        """Return the mission execution mode if provided."""

        mode = None
        if isinstance(self._mission_context, dict):
            mode = self._mission_context.get("mode")
        if not mode and isinstance(self._mission_meta, dict):
            mode = self._mission_meta.get("mode")
        return mode

    # ------------------------------------------------------------------
    # Mission attachment and output synchronisation
    # ------------------------------------------------------------------
    def attach_mission(self, mission: "Mission") -> None:
        """Capture mission metadata and synchronise declared outputs."""

        self._mission_name = mission.name
        self._mission_meta = mission.metadata.get("meta", {}) or {}
        self._mission_context = mission.metadata.get("context", {}) or {}

        workspace_hint = (
            self._mission_context.get("workspace")
            or self._mission_context.get("workspace_path")
        )
        auto_run = self._mission_context.get("auto_run")
        if workspace_hint:
            self.set_workspace(str(workspace_hint), auto_run=auto_run)

        parser_diag = mission.metadata.get("flex_parser")
        if parser_diag:
            self.publish_diagnostic("flex_parser", parser_diag)

        self.sync_outputs(mission.metadata.get("outputs"))

    def sync_outputs(self, outputs_config: Any) -> List[Dict[str, Any]]:
        """Normalise declared outputs for later tracking."""

        self._outputs = []

        for entry in self._ensure_iterable(outputs_config):
            normalised = self._normalise_output_entry(entry)
            if normalised:
                self._outputs.append(normalised)

        return self._outputs

    def register_output(self, destination: str, **metadata: Any) -> Dict[str, Any]:
        """Mark an output as materialised and capture related metadata."""

        normalized_destination = str(destination)
        record = None
        for item in self._outputs:
            if item.get("destination") == normalized_destination:
                record = item
                break

        status = metadata.pop("status", "created")
        if record is None:
            record = {"destination": normalized_destination, "status": status}
            self._outputs.append(record)
        else:
            record["status"] = status

        record.update(metadata)
        record.setdefault("updated_at", self._utc_timestamp())
        return record

    def get_outputs(self) -> List[Dict[str, Any]]:
        """Return a copy of the tracked outputs."""

        return [dict(item) for item in self._outputs]

    # ------------------------------------------------------------------
    # Diagnostics handling
    # ------------------------------------------------------------------
    def publish_diagnostic(self, source: str, payload: Any) -> Dict[str, Any]:
        """Record a diagnostic entry tagged with its source."""

        entry = {
            "source": source,
            "timestamp": self._utc_timestamp(),
            "payload": payload,
        }
        self._diagnostics.append(entry)
        return entry

    def get_diagnostics(self) -> List[Dict[str, Any]]:
        """Return collected diagnostics."""

        return [dict(item) for item in self._diagnostics]

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------
    def export_snapshot(self) -> Dict[str, Any]:
        """Return a consolidated view of the bridge state."""

        return {
            "mission": {
                "name": self._mission_name,
                "meta": self._mission_meta,
                "context": self._mission_context,
            },
            "workspace": self._current_workspace,
            "outputs": self.get_outputs(),
            "diagnostics": self.get_diagnostics(),
        }

    def reset(self) -> None:
        """Forget mission-specific data while preserving workspace knowledge."""

        self._outputs = []
        self._diagnostics = []
        self._mission_meta = {}
        self._mission_context = {}
        self._mission_name = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _normalise_output_entry(self, entry: Any) -> Dict[str, Any]:
        if entry is None:
            return {}

        if isinstance(entry, dict):
            result = dict(entry)
            result.setdefault("status", "declared")
            if "destination" in result:
                result["destination"] = str(result["destination"])
            return result

        if isinstance(entry, str):
            return {"destination": entry, "status": "declared"}

        return {"destination": str(entry), "status": "declared"}

    def _ensure_iterable(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple) or isinstance(value, set):
            return list(value)
        return [value]

    def _utc_timestamp(self) -> str:
        return datetime.utcnow().isoformat() + "Z"


# Shared instance for convenience
context_bridge = ContextBridge()


