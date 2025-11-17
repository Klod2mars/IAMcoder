# AIHomeCoder V2 Mission Model

## Overview
- Purpose: capture the binary read/write mission model requested for AIHomeCoder V2.
- Scope: mission definitions, execution guardrails, and the dedicated write task implementation.
- Context: local workspace, strict validation mindset, outputs authored in Markdown.

## Read Mission Definition
- Location: `config/prompts/mission_read_context.yaml`.
- Mode: read_only; workspace resolved via `${WORKSPACE_ROOT}` placeholder.
- Core task: `task_gather_documents` collecting mission, plan, architecture, readme, and docs artefacts.
- Outputs: Markdown report registered through ContextBridge at `reports/${REPORT_NAME}`.
- Guardrails: sanctuary-aware directory exclusions, variable driven patterns, diagnostics published on start, document collection, and completion.

## Write Mission Definition
- Location: `config/prompts/mission_apply_changes.yaml`.
- Mode: write_enabled; workspace resolved via `${WORKSPACE_ROOT}` with guarded change policy.
- Plan specification: `changes` list supporting `overwrite`, `replace_block`, `insert_before`, `insert_after`, and `append` actions, optional external content sources, and dry-run toggle.
- Core task: `task_apply_writes` consuming `${WRITE_PLAN}`, emitting execution log to `${REPORT_LOG}`.
- Outputs: Markdown execution log declared and tracked via ContextBridge.

## task_apply_writes Implementation
- Location: `domain/services/task_logic_handler.py` (`task_apply_writes`).
- Plan ingestion: inline YAML or file path resolved against the workspace; guardrail read checks enforced.
- Safety: all write paths pass through `_safe_write_text` (guardrail write/append checks, directory creation with UTF-8 encoding); report logging also guarded.
- Supported actions: `overwrite`, `append`, `replace_block` (start/end markers or single marker), `insert_before`, `insert_after`.
- Diagnostics: per-change events (`change_error`, `change_processed`), aggregate start/completion events, ContextBridge output registration summarising applied, dry-run, and error counts.
- Reporting: Markdown log summarising mission/task metadata, guardrail policy, change statuses, and recorded errors.

## Validation Checklist
- ✅ Read mission YAML created with explicit variables, destinations, and post actions aligned to observation workflow.
- ✅ Write mission YAML documented with plan schema, guarded output handling, and post actions for traceability.
- ✅ `task_apply_writes` dispatch added to `TaskLogicHandler.execute`, fulfilling plan loading, guarded writes, diagnostics, and Markdown reporting responsibilities.
- ✅ Linter check executed for touched files; no issues reported.

## Recommendations
- Maintain sample write plans under `plans/` to illustrate supported selectors and action patterns.
- Extend automated tests to cover dry-run flows and marker edge cases for `task_apply_writes`.
- Integrate mission prompts into CI pipelines to validate new contributions against the mission model.

