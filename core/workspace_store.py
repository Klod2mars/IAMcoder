from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


STATE_DIR = Path("config") / "state"
STATE_FILE = STATE_DIR / "workspace.json"


class WorkspaceStore:
    """
    Stocke le dernier workspace sélectionné pour AIHomeCoder
    et conserve un petit historique.
    """

    def __init__(self, state_file: Path = STATE_FILE) -> None:
        self.state_file = state_file
        self.data: dict[str, Any] = {
            "last_workspace": None,
            "history": [],
            "auto_run": False,
        }
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            try:
                self.data = json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                # On ne casse pas le démarrage si le fichier est corrompu
                self.data = {
                    "last_workspace": None,
                    "history": [],
                    "auto_run": False,
                }

    def save(self) -> None:
        if not self.state_file.parent.exists():
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get_last_workspace(self) -> str | None:
        return self.data.get("last_workspace")

    def set_workspace(self, path: str, *, auto_run: bool | None = None) -> None:
        self.data["last_workspace"] = path
        now = datetime.utcnow().isoformat() + "Z"
        # mettre à jour l'historique (sans doublons)
        history = [h for h in self.data.get("history", []) if h.get("path") != path]
        history.insert(0, {"path": path, "last_used": now})
        # on limite l'historique à 10 entrées
        self.data["history"] = history[:10]
        if auto_run is not None:
            self.data["auto_run"] = auto_run
        self.save()

    def get_history(self) -> list[dict[str, Any]]:
        return self.data.get("history", [])

    def get_auto_run(self) -> bool:
        return bool(self.data.get("auto_run", False))


def get_workspace_store() -> WorkspaceStore:
    return WorkspaceStore()

