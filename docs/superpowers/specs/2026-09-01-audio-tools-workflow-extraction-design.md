# Audio Tools Workflow Extraction Design

## Status

Approved in chat on 2026-09-01. This document defines the next low-risk slice of the MokaMusic UI workflow refactor.

## Context

After extracting cover and playlist orchestration, `app/ui/metadata_workflow.py` contains 1,596 physical lines and still coordinates metadata editing, audio tools, file organization, cleanup, history, and import/export.

The audio-tools behavior is already supported by focused service modules:

- `audio_audit_service` builds quality, duplicate, and validation rows.
- `audio_conversion_service` builds conversion items and executes FFmpeg.

The remaining problem is UI orchestration. Target resolution, modal presentation, conversion options, progress, library refresh, and feedback still depend implicitly on the full `MokaMusicApp` object. `_convert_selected_audio` is 68 lines and exceeds the configured complexity threshold.

## Scope

This slice extracts only audio audit and conversion orchestration into a composed `AudioToolsWorkflow`.

Included:

- Resolving selected audio targets with fallback to the active library for read-only audits.
- Displaying audio-quality analysis.
- Detecting and displaying advanced duplicates.
- Validating audio files and displaying issues.
- Converting explicitly selected audio files.
- Preserving or flattening source folder structure according to existing options.
- Progress, destination-library refresh, and success, partial, or error feedback.
- Characterization tests for the composed workflow.
- Compatibility wrappers for the four existing action callbacks.

Not included:

- Rename-by-template, folder organization, file-plan application, playlist validation, or smart-playlist generation.
- Changes to audit algorithms, duplicate tolerances, validation rules, conversion presets, FFmpeg commands, destination naming, or overwrite behavior.
- Changes to translation resources, modal layout, table columns, column widths, message ordering, or other visible UI behavior.
- Changes to export/import, metadata editing, cleanup, backup, playlist, or cover workflows.
- An event bus, dependency-injection framework, or external package.

## Approaches Considered

### Smaller audio-tools mixin

Moving the methods to `AudioToolsWorkflowMixin` would reduce the source file but preserve the same undocumented `self` contract. It relocates coupling without making the orchestration independently testable.

### Composed workflow with explicit ports — selected

Create `AudioToolsWorkflow` with typed UI, library, and operation boundaries. This follows the established composed-workflow pattern, keeps Tkinter and FFmpeg outside unit tests, and permits an incremental migration through compatibility wrappers.

### Presentation inside the existing services

The service functions could open dialogs and progress UI directly. That would mix domain processing with Tkinter, reduce reuse, and make service tests dependent on presentation state.

## Architecture

Add `app/ui/workflows/audio_tools_workflow.py` and export its public types from `app/ui/workflows/__init__.py`.

`AudioToolsWorkflow` owns orchestration only. It does not implement audio-quality rules, duplicate matching, file validation, destination naming, or FFmpeg invocation.

Dependencies are grouped into three frozen dataclasses containing typed callables. They must not expose `MokaMusicApp`, generic attribute lookup, or a dictionary-based service locator.

### `AudioToolsUiPort`

Provides only audio-tools presentation operations:

- Translate a message key.
- Show warning, information, and error dialogs.
- Display the existing audio-audit table modal.
- Request existing audio-conversion options.
- Begin a closable progress operation.
- Show success or partial-result toasts.

The audit-modal adapter receives a localized title, rows, and the exact column tuples. The conversion-options adapter receives only the selected source count; `MokaMusicApp` supplies the Tk root and translator.

### `AudioToolsLibraryPort`

Provides only library integration:

- Return selected filenames grouped by controller and tree.
- Resolve the current active-library target through the existing playlist workflow.
- Return principal and incoming controller/tree pairs.
- Refresh a specific library tree.

The workflow itself resolves destination paths and refreshes only a loaded controller whose folder resolves to the selected destination.

### `AudioToolsOperations`

Provides the existing domain operations:

- Build audio-quality rows.
- Detect advanced duplicates.
- Validate audio files.
- Build conversion items.
- Convert audio files.

`MokaMusicApp` composes this dataclass from the current service functions. Tests replace these operations with recording fakes; production behavior remains in the existing services.

### Compatibility boundary

`MokaMusicApp` creates one `AudioToolsWorkflow` after controllers and UI widgets exist. `MetadataWorkflowMixin` retains four one-line entry points:

- `_analyze_audio_quality`
- `_detect_advanced_duplicates`
- `_validate_audio_files`
- `_convert_selected_audio`

The private `_audio_tool_targets` and `_refresh_libraries_after_conversion` methods move completely into the workflow because they have no consumers outside this slice.

## Components and Responsibilities

### `AudioToolsWorkflow`

- Resolve audit targets from selection or active-library fallback.
- Warn and stop when no audit target exists.
- Invoke the correct operation and present exact existing columns.
- Present empty duplicate and validation results without opening a table.
- Require explicit selection for conversion.
- Convert selected filenames into absolute source paths grouped by controller.
- Request conversion options and stop on cancellation.
- Build flat or structure-preserving conversion items.
- Open and close progress safely.
- Map FFmpeg absence and general exceptions to existing localized errors.
- Refresh matching destination libraries after a conversion result.
- Present success or partial results with existing message limits.

### Existing audio services

No behavior changes. They remain responsible for analysis rows, conversion-item planning, FFmpeg availability and commands, conversion execution, unique destinations, and `AudioConversionResult`.

### `MetadataWorkflowMixin`

Delegates the four audio-tool actions to `self.audio_tools_workflow`. It keeps selection helpers needed by unrelated workflows and retains all file-organization behavior.

### `MokaMusicApp`

Acts as the composition root. It adapts Tkinter modals and existing library callbacks to the declared ports without duplicating orchestration.

## Data Flow

### Audit operations

1. An existing menu callback reaches a compatibility wrapper.
2. The workflow obtains explicit selected groups.
3. If no selection exists, it asks the library port for the active target and expands that controller to all loaded filenames.
4. If no target exists, it shows the existing no-files warning and stops.
5. It invokes the selected audit operation.
6. Quality analysis always opens the table with current columns.
7. Duplicate and validation analysis show the existing empty-state information message when no rows exist; otherwise they open their current tables.

### Conversion

1. The workflow requires explicit selections and shows `audio_conversion.no_selection` when absent.
2. It creates absolute source paths grouped by their controller.
3. It requests existing conversion options using the total source count.
4. Cancellation stops before item construction or progress.
5. Flat conversion builds all sources together. Structure-preserving conversion builds each controller group with that controller folder as `source_root`.
6. Item-construction errors show `audio_conversion.failed` and stop before progress.
7. The workflow opens progress and invokes conversion with the existing overwrite option and callback.
8. Progress closes in `finally` on success, FFmpeg absence, and unexpected conversion exceptions.
9. `RuntimeError` maps to the existing `audio_conversion.ffmpeg_missing` message. Other exceptions map to `audio_conversion.failed`.
10. After a returned result, the workflow refreshes any loaded library whose resolved folder equals the resolved destination.
11. A result with errors shows a partial toast and warning, includes at most five error details, and appends the existing remaining-error count when required.
12. A result without errors shows the existing success toast and information dialog.

## Error Handling

- Missing audit targets and missing conversion selection are expected user-facing states and do not raise.
- Cancelled conversion options stop without mutation or feedback.
- Item-building failures are caught and shown before progress starts.
- Progress is always closed with `try/finally` after it opens.
- `RuntimeError` from conversion retains its existing FFmpeg-specific message.
- Other conversion exceptions retain their existing localized failure message.
- Audit-operation exceptions are not broadly suppressed; current menu event boundaries remain responsible for unexpected failures.
- Partial conversion results remain successful mutations and trigger destination refresh before partial feedback.
- This slice does not add rollback, retries, or FFmpeg installation behavior.

## UI/UX Constraints

This is a structural refactor. It preserves modal type, title, table column order, labels, widths, conversion option defaults, dialog sequence, progress behavior, toast type, and displayed error limits.

No frontend-design changes are included. The workflow boundary makes later presentation changes safer but does not authorize them.

## Testing Strategy

Add `tests/test_audio_tools_workflow.py` with recording fakes for the three ports and a fake progress object. Tests construct no Tk root and invoke no FFmpeg process.

Characterization cases:

- Explicit audit selection is preserved.
- Audit without selection falls back to the active controller and all its files.
- Missing audit target warns and stops before operations.
- Quality analysis opens the existing title and exact columns.
- Duplicate analysis with no rows shows the existing information message and does not open the table.
- Duplicate rows open the existing duplicate columns.
- Validation with no rows shows the existing information message and does not open the table.
- Validation rows open the existing validation columns.
- Conversion without selection warns and stops.
- Cancelled conversion options stop before item construction.
- Flat conversion passes all source paths once.
- Structure-preserving conversion builds items once per selected controller with the correct `source_root`.
- Item-building failure is shown before progress.
- FFmpeg absence closes progress and shows the existing specific error.
- Unexpected conversion failure closes progress and shows the generic localized error.
- Successful conversion closes progress, refreshes only a matching destination library, and shows success feedback.
- Partial conversion refreshes the destination, shows warning feedback, limits details to five errors, and reports the remaining count.
- All four compatibility wrappers delegate to the composed workflow.

Existing `test_audio_audit_service.py` and `test_audio_conversion_service.py` remain the domain-level safety net. Focused workflow tests, the full unit-test suite, Ruff check, Ruff formatting check, module compilation, and smoke tests are required before completion.

## Migration Sequence

1. Add failing tests for the ports, audit target resolution, and presentation behavior.
2. Add typed port dataclasses and implement audit operations incrementally.
3. Add failing tests for conversion validation, item planning, progress, errors, refresh, and feedback.
4. Implement conversion orchestration and destination refresh.
5. Compose `AudioToolsWorkflow` in `MokaMusicApp` after UI setup.
6. Replace four mixin methods with compatibility delegation.
7. Remove audio-tool-only imports and the two migrated private helpers from `metadata_workflow.py`.
8. Run focused tests, the full suite, Ruff, formatting verification, compilation, smoke tests, and a final scoped-diff review.

## Success Criteria

- Audio-tool orchestration is independently testable without Tkinter or FFmpeg.
- `AudioToolsWorkflow` depends only on its three declared boundaries.
- Existing audit and conversion callbacks remain compatible.
- `_convert_selected_audio` no longer contributes a C901 violation in `metadata_workflow.py`.
- `metadata_workflow.py` loses approximately 145–160 lines and retains only four audio-tool delegation wrappers.
- No service algorithm, translation, layout, visible behavior, or external dependency changes.
- Focused and full automated verification passes.

## Follow-up Slices

File organization is the next low-risk candidate. Export/import, metadata editing, cleanup, and history remain separate changes requiring their own approval. This specification does not authorize them.
