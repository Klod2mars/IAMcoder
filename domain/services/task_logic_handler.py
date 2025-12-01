$root = Get-Location
$src = Join-Path $root "domain\services\task_logic_handler.py"
$bak_ts = Get-Date -Format "yyyyMMddHHmmss"
$bak = Join-Path (Split-Path $src) ("task_logic_handler.py.bak_" + $bak_ts)

# Backup (obligatoire)
Write-Host "Backup: $src -> $bak"
Copy-Item -Path $src -Destination $bak -Force

# Write fixed file (UTF8)
$fixed = @'
# domain/services/task_logic_handler.py
from pathlib import Path
import os
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

from core.context_bridge import context_bridge
from core.file_manager import file_manager
from core.guardrail import guardrail

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Helpers (thin wrappers that delegate to domain.services.helpers)
# ---------------------------------------------------------------------
def _resolve_placeholders(value: Any, variables: Dict[str, str]) -> Any:
    """
    Wrapper vers domain.services.helpers._resolve_placeholders.
    """
    from domain.services.helpers import _resolve_placeholders as _hp
    return _hp(value, variables)


# ---------------------------------------------------------------------
# Task handlers (top-level wrappers delegating to domain.services.handlers/*)
# ---------------------------------------------------------------------
def apply_yaml_replacements(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.yaml_apply.apply_yaml_replacements.
    """
    from domain.services.handlers.yaml_apply import apply_yaml_replacements as _external_apply_yaml_replacements
    return _external_apply_yaml_replacements(params, context)


def task_tree_scan(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.tree_scan.task_tree_scan.
    """
    from domain.services.handlers.tree_scan import task_tree_scan as _external_task_tree_scan
    return _external_task_tree_scan(params, context)


def task_gather_documents(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.gather_documents.task_gather_documents.
    """
    from domain.services.handlers.gather_documents import task_gather_documents as _external_task_gather_documents
    return _external_task_gather_documents(params, context)


def task_apply_writes(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.apply_writes.task_apply_writes.
    """
    from domain.services.handlers.apply_writes import task_apply_writes as _external_task_apply_writes
    return _external_task_apply_writes(params, context)


def task_gather_overview(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.gather_overview.task_gather_overview.
    """
    from domain.services.handlers.gather_overview import task_gather_overview as _external_task_gather_overview
    return _external_task_gather_overview(params, context)


def task_generate_report(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.report_generation.task_generate_report.
    """
    from domain.services.handlers.report_generation import task_generate_report as _external_task_generate_report
    return _external_task_generate_report(params, context)


# ---------------------------------------------------------------------
# Orchestrator class (single point of entry)
# ---------------------------------------------------------------------
class TaskLogicHandler:
    """
    Orchestrateur léger : conserve TaskLogicHandler.execute(...) comme point d'entrée.
    Toute la logique lourde est déléguée aux handlers sous domain.services.handlers
    et aux utilitaires dans domain.services.helpers.
    """

    def execute(self, task, mission):
        """
        Unique point d'entrée : dispatch des tâches selon task.task_type ou task.name.
        Conserve l'API observable (retours texte, logs).
        """
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
            # analysis handlers are pure functions that accept params only.
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

        # YAML-driven deterministic replacer
        elif ttype in {"yaml_replace", "yaml_apply", "yaml_apply_replacements"}:
            context = self._build_execution_context(task, mission)
            return apply_yaml_replacements(params, context)

        elif ttype == "setup":
            return f"[OK] Préparation du workspace : {params.get('variable_path', 'N/A')}"
        else:
            return f"[INFO] Tâche '{task.name}' exécutée sans logique spécifique."

    # ------------------------------------------------------------------
    # Context & variable helpers (delegation to domain.services.helpers)
    # ------------------------------------------------------------------
    def _build_execution_context(self, task, mission):
        """
        Wrapper léger : délègue la construction du contexte à helpers.build_execution_context.
        """
        from domain.services.helpers import build_execution_context as _external_build_execution_context
        return _external_build_execution_context(task, mission)

    def _collect_variables(self, params, context_section):
        """
        Wrapper vers domain.services.helpers._collect_variables.
        """
        from domain.services.helpers import _collect_variables as _external_collect
        return _external_collect(params, context_section)

    @staticmethod
    def _coerce_variable_map(source):
        """
        Wrapper statique vers domain.services.helpers._coerce_variable_map.
        """
        from domain.services.helpers import _coerce_variable_map as _external_coerce
        return _external_coerce(source)

    # ------------------------------------------------------------------
    # Analysis / report generators (delegation)
    # ------------------------------------------------------------------
    def _analyze_workspace(self, params):
        """
        Wrapper : délègue à domain.services.handlers.analysis.analyze_workspace.
        """
        from domain.services.handlers.analysis import analyze_workspace as _external_analyze
        return _external_analyze(params)

    def _generate_markdown(self, params):
        """
        Wrapper : délègue à domain.services.handlers.analysis.generate_markdown.
        """
        from domain.services.handlers.analysis import generate_markdown as _external_generate
        return _external_generate(params)


# End of task_logic_handler.py
'@

Set-Content -Path $src -Value $fixed -Encoding UTF8

# 3) Quick syntax check
Write-Host "Running python -m py_compile domain/services/task_logic_handler.py"
python -m py_compile domain/services/task_logic_handler.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "py_compile failed. Inspect domain/services/task_logic_handler.py and restore backup if needed:"
    Write-Host "Copy-Item -Path '$bak' -Destination '$src' -Force"
    exit 1
} else {
    Write-Host "py_compile OK."
}

# 4) Quick import smoke-test
Write-Host "Running import test..."
python - <<'PY'
try:
    import importlib
    m = importlib.import_module("domain.services.task_logic_handler")
    print("import OK")
except Exception as e:
    import traceback
    traceback.print_exc()
    raise
PY

Write-Host "Backup kept at: $bak"
$root = Get-Location
$src = Join-Path $root "domain\services\task_logic_handler.py"
$bak_ts = Get-Date -Format "yyyyMMddHHmmss"
$bak = Join-Path (Split-Path $src) ("task_logic_handler.py.bak_" + $bak_ts)

# Backup (obligatoire)
Write-Host "Backup: $src -> $bak"
Copy-Item -Path $src -Destination $bak -Force

# Write fixed file (UTF8)
$fixed = @'
# domain/services/task_logic_handler.py
from pathlib import Path
import os
import json
import datetime
import logging
from typing import Any, Dict, List, Optional

from core.context_bridge import context_bridge
from core.file_manager import file_manager
from core.guardrail import guardrail

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Helpers (thin wrappers that delegate to domain.services.helpers)
# ---------------------------------------------------------------------
def _resolve_placeholders(value: Any, variables: Dict[str, str]) -> Any:
    """
    Wrapper vers domain.services.helpers._resolve_placeholders.
    """
    from domain.services.helpers import _resolve_placeholders as _hp
    return _hp(value, variables)


# ---------------------------------------------------------------------
# Task handlers (top-level wrappers delegating to domain.services.handlers/*)
# ---------------------------------------------------------------------
def apply_yaml_replacements(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.yaml_apply.apply_yaml_replacements.
    """
    from domain.services.handlers.yaml_apply import apply_yaml_replacements as _external_apply_yaml_replacements
    return _external_apply_yaml_replacements(params, context)


def task_tree_scan(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.tree_scan.task_tree_scan.
    """
    from domain.services.handlers.tree_scan import task_tree_scan as _external_task_tree_scan
    return _external_task_tree_scan(params, context)


def task_gather_documents(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.gather_documents.task_gather_documents.
    """
    from domain.services.handlers.gather_documents import task_gather_documents as _external_task_gather_documents
    return _external_task_gather_documents(params, context)


def task_apply_writes(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.apply_writes.task_apply_writes.
    """
    from domain.services.handlers.apply_writes import task_apply_writes as _external_task_apply_writes
    return _external_task_apply_writes(params, context)


def task_gather_overview(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.gather_overview.task_gather_overview.
    """
    from domain.services.handlers.gather_overview import task_gather_overview as _external_task_gather_overview
    return _external_task_gather_overview(params, context)


def task_generate_report(params: Dict[str, Any], context: Dict[str, Any]):
    """
    Wrapper léger : délègue à domain.services.handlers.report_generation.task_generate_report.
    """
    from domain.services.handlers.report_generation import task_generate_report as _external_task_generate_report
    return _external_task_generate_report(params, context)


# ---------------------------------------------------------------------
# Orchestrator class (single point of entry)
# ---------------------------------------------------------------------
class TaskLogicHandler:
    """
    Orchestrateur léger : conserve TaskLogicHandler.execute(...) comme point d'entrée.
    Toute la logique lourde est déléguée aux handlers sous domain.services.handlers
    et aux utilitaires dans domain.services.helpers.
    """

    def execute(self, task, mission):
        """
        Unique point d'entrée : dispatch des tâches selon task.task_type ou task.name.
        Conserve l'API observable (retours texte, logs).
        """
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
            # analysis handlers are pure functions that accept params only.
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

        # YAML-driven deterministic replacer
        elif ttype in {"yaml_replace", "yaml_apply", "yaml_apply_replacements"}:
            context = self._build_execution_context(task, mission)
            return apply_yaml_replacements(params, context)

        elif ttype == "setup":
            return f"[OK] Préparation du workspace : {params.get('variable_path', 'N/A')}"
        else:
            return f"[INFO] Tâche '{task.name}' exécutée sans logique spécifique."

    # ------------------------------------------------------------------
    # Context & variable helpers (delegation to domain.services.helpers)
    # ------------------------------------------------------------------
    def _build_execution_context(self, task, mission):
        """
        Wrapper léger : délègue la construction du contexte à helpers.build_execution_context.
        """
        from domain.services.helpers import build_execution_context as _external_build_execution_context
        return _external_build_execution_context(task, mission)

    def _collect_variables(self, params, context_section):
        """
        Wrapper vers domain.services.helpers._collect_variables.
        """
        from domain.services.helpers import _collect_variables as _external_collect
        return _external_collect(params, context_section)

    @staticmethod
    def _coerce_variable_map(source):
        """
        Wrapper statique vers domain.services.helpers._coerce_variable_map.
        """
        from domain.services.helpers import _coerce_variable_map as _external_coerce
        return _external_coerce(source)

    # ------------------------------------------------------------------
    # Analysis / report generators (delegation)
    # ------------------------------------------------------------------
    def _analyze_workspace(self, params):
        """
        Wrapper : délègue à domain.services.handlers.analysis.analyze_workspace.
        """
        from domain.services.handlers.analysis import analyze_workspace as _external_analyze
        return _external_analyze(params)

    def _generate_markdown(self, params):
        """
        Wrapper : délègue à domain.services.handlers.analysis.generate_markdown.
        """
        from domain.services.handlers.analysis import generate_markdown as _external_generate
        return _external_generate(params)


# End of task_logic_handler.py
'@

Set-Content -Path $src -Value $fixed -Encoding UTF8

# 3) Quick syntax check
Write-Host "Running python -m py_compile domain/services/task_logic_handler.py"
python -m py_compile domain/services/task_logic_handler.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "py_compile failed. Inspect domain/services/task_logic_handler.py and restore backup if needed:"
    Write-Host "Copy-Item -Path '$bak' -Destination '$src' -Force"
    exit 1
} else {
    Write-Host "py_compile OK."
}

# 4) Quick import smoke-test
Write-Host "Running import test..."
python - <<'PY'
try:
    import importlib
    m = importlib.import_module("domain.services.task_logic_handler")
    print("import OK")
except Exception as e:
    import traceback
    traceback.print_exc()
    raise
PY

Write-Host "Backup kept at: $bak"
