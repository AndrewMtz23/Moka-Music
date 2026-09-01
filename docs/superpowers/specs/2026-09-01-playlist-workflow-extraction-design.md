# Playlist Workflow Extraction Design

## Status

Approved in chat on 2026-09-01. This document defines the next incremental slice of the MokaMusic UI workflow refactor.

## Context

`app/ui/metadata_workflow.py` contains 1,808 physical lines and 75 methods. It coordinates metadata editing, audio tools, backup history, cleanup, playlist ordering, and import/export through implicit `self` dependencies.

The playlist section contains two of the largest orchestration methods in the file: `_insert_selected_at_position` at 96 lines and `_prepare_active_playlist` at 75 lines. Both repeat plan preview, progress, execution, refresh, sort, preview, undo, and result-reporting behavior. `_insert_selected_at_position` also exceeds the configured complexity threshold.

The mutation engine is already isolated in `PlaylistWorkflowController`, with tests for building and executing playlist plans. The missing boundary is a UI workflow that coordinates that controller without depending on the complete `MokaMusicApp` object.

## Scope

This slice extracts playlist ordering orchestration into a composed `PlaylistWorkflow`. Existing behavior and visual appearance remain unchanged.

Included:

- Numbering tracks for the active library.
- Inserting selected tracks at a requested position.
- Preparing and reordering the active playlist.
- Resolving the active playlist target.
- Validating whether the current view can be reordered.
- Plan preview and confirmation.
- Progress, library refresh, preview refresh, sort synchronization, backup, undo, and result feedback.
- Characterization tests for the new coordinator.
- Compatibility wrappers for existing callbacks and export consumers.

Not included:

- Playlist, library-view, or report export.
- Metadata import or rename-from-metadata.
- `_active_library_view_target`, which belongs to the later export workflow.
- Changes to playlist numbering, filename formatting, plan semantics, or backup contents.
- Changes to layout, dialogs, translations, shortcuts, focus, colors, or other visible UI behavior.
- An event bus, dependency-injection framework, or external package.

## Approaches Considered

### Smaller playlist mixin

Moving the methods to `PlaylistWorkflowMixin` would reduce the source file but preserve an undocumented dependency on the full application through `self`. It moves the coupling instead of removing it.

### Composed workflow with explicit ports — selected

Create a `PlaylistWorkflow` object with small, typed UI and library ports. This follows the proven `CoverWorkflow` pattern, makes orchestration testable without Tkinter, and supports incremental migration with compatibility wrappers.

### Add UI orchestration to `PlaylistWorkflowController`

The existing controller could be expanded to open dialogs and refresh widgets. That would mix playlist mutation rules with Tkinter concerns and make both layers harder to test and reuse.

## Architecture

Add `app/ui/workflows/playlist_workflow.py` and export its public types from `app/ui/workflows/__init__.py`.

`PlaylistWorkflow` owns orchestration. `PlaylistWorkflowController` continues to build and execute mutation plans and remains unaware of Tkinter, translations, widgets, and application composition.

Dependencies are grouped into two frozen dataclasses containing typed callables. They must not expose `MokaMusicApp`, generic attribute lookup, or a dictionary-based service locator.

### `PlaylistUiPort`

Provides only playlist-related presentation operations:

- Translate a message key.
- Show warning, information, confirmation, and error dialogs.
- Request a target position.
- Request and rebuild a playlist preview.
- Begin progress and always provide a closable progress object.
- Show a toast.

### `PlaylistLibraryPort`

Provides only application and library integration:

- Return selected filenames grouped by controller and tree.
- Return the current preview controller and filename.
- Update the preview filename after rename.
- Resolve a tree for a controller and fallback library targets.
- Validate that the current view permits reordering.
- Refresh a complete tree or only changed controller/tree pairs.
- Synchronize the sort mode widget.
- Select and reload the active preview.
- Create metadata backups for track numbering.
- Record undo paths.

`MokaMusicApp` creates one `PlaylistWorkflow` after controllers and UI widgets are available. It supplies the existing `PlaylistWorkflowController`, ports, and song-information service.

`MetadataWorkflowMixin` retains four compatibility entry points whose bodies only delegate:

- `_number_tracks_for_active_library`
- `_insert_selected_at_position`
- `_prepare_active_playlist`
- `_active_playlist_target`

The fourth wrapper remains because existing export commands still use active-playlist target resolution. Direct callback rebinding and wrapper removal are deferred until the export workflow is extracted.

## Components and Responsibilities

### `PlaylistWorkflow`

- Resolve selection and active-library targets.
- Validate empty, multi-library, and filtered-view states.
- Request position and preview confirmation.
- Build plans through `PlaylistWorkflowController`.
- Execute confirmed plans through one shared private method.
- Open and close progress safely.
- Refresh affected views and synchronize track-number sorting.
- Restore preview selection after renamed files.
- Register undo only when the controller returns a backup path for a successful mutation.
- Present the same success, cancellation, no-change, and failure feedback as the current implementation.

### `PlaylistWorkflowController`

- Build insertion and final-order plans.
- Create the plan-execution backup.
- Reorder files, update track numbers, rename files, and invalidate affected song information.
- Return `PlaylistApplyResult` without presenting UI.

Its behavior and public API remain unchanged unless a small type-only adjustment is required for the workflow boundary.

### `MetadataWorkflowMixin`

- Delegate playlist entry points to `self.playlist_workflow`.
- Keep export/import and unrelated shared helpers in place.
- Contain no playlist plan execution or playlist-specific feedback logic after this slice.

### `MokaMusicApp`

- Act as the composition root.
- Construct ports from existing callbacks, controllers, widgets, and services.
- Avoid duplicating playlist orchestration.

## Data Flow

### Insert selected tracks

1. The existing callback calls the compatibility wrapper.
2. The workflow obtains grouped selections and rejects zero or multiple-library selection.
3. It validates that the library is loaded and the current view is reorderable.
4. It requests a zero-based display position and converts it to the controller's existing position convention.
5. It builds an insertion plan.
6. A no-change plan produces the existing information message and stops.
7. It requests preview confirmation and accepts a reordered plan from the preview.
8. The shared executor opens progress, invokes the controller, and closes progress in `finally`.
9. It updates the preview filename, refreshes changed pairs, switches to track-number sort, and restores preview selection.
10. It records undo and presents insert-specific feedback according to the result.

### Prepare active playlist

The workflow resolves the active playlist target, validates the view, builds a plan from the current order, and then follows steps 6–10 above. It uses prepare-specific success text while sharing all mutation and refresh behavior.

### Number tracks

The workflow resolves the current preview library or the existing principal/incoming fallback, validates the view, confirms the operation, and creates the existing metadata backup before mutation. It then calls `apply_track_numbers_from_order`, invalidates affected song information, refreshes the tree and preview, and presents the existing `ActionResult` feedback.

## Error Handling

- Missing selection, multiple-library selection, missing files, filtered views, declined dialogs, cancelled position, and cancelled preview terminate before mutation.
- Backup failure for track numbering terminates before mutation.
- Progress closes with `try/finally`, including when the controller raises unexpectedly.
- Controller-reported partial or total errors are displayed using the same existing message keys and details.
- Undo is recorded only when the successful result contains a backup path.
- Unexpected exceptions are not broadly swallowed inside the workflow. Existing UI event boundaries remain responsible for top-level logging where applicable.
- This slice does not add rollback semantics; it preserves the controller's current partial-result behavior.

## UI/UX Constraints

This is a structural refactor. Dialog order, labels, translations, default positions, sort changes, progress behavior, toast behavior, keyboard shortcuts, and widget layout must remain identical.

No frontend-design changes are included. The new workflow boundary only makes later UI changes safer by separating semantic playlist actions from their current widgets.

## Testing Strategy

Add `tests/test_playlist_workflow.py` with fakes for both ports, progress, controller, plans, and results. Tests run without constructing a Tk root.

Characterization cases:

- Numbering warns for an empty target and stops.
- Numbering rejects a filtered view.
- Declining numbering confirmation or failing backup prevents mutation.
- Successful numbering invalidates songs, refreshes the tree and preview, and reports the result.
- Insertion rejects no selection and selections spanning two libraries.
- Cancelling the position or plan preview prevents execution.
- A plan with no items reports no changes.
- Position conversion preserves the existing zero-based UI and one-based controller behavior.
- Preparation resolves the same active target precedence as today.
- Insert and prepare both use the shared executor while preserving distinct success messages.
- Progress closes after success and after an exception.
- Success updates preview filename, changed libraries, sort mode, selection, undo, toast, and information feedback.
- Failure does not record undo and reports controller errors.
- Compatibility wrappers delegate exact arguments and return the target result where applicable.

Existing `tests/test_playlist_workflow_controller.py` remains the domain-level safety net. Focused workflow tests, the full unit-test suite, Ruff check, Ruff formatting check, and module compilation are required before completion.

## Migration Sequence

1. Add failing tests for the workflow ports and public operations.
2. Add the typed ports and the smallest coordinator behavior that passes each test.
3. Consolidate insert and prepare execution into one private workflow method.
4. Compose `PlaylistWorkflow` in `MokaMusicApp` after controllers and UI widgets exist.
5. Replace the four mixin methods with compatibility delegation.
6. Remove playlist-only imports and unreachable helpers from `metadata_workflow.py`.
7. Run focused tests, the full suite, Ruff, formatting verification, compilation, and startup smoke checks.
8. Confirm the final diff contains no translation, layout, style, or unrelated workflow changes.

## Success Criteria

- Playlist orchestration is independently testable without constructing Tkinter or `MokaMusicApp`.
- `PlaylistWorkflow` depends only on its declared ports, `PlaylistWorkflowController`, and the song-information service.
- Insert and prepare share a single execution path.
- Existing callbacks and export target resolution remain compatible.
- `metadata_workflow.py` loses approximately 200–220 lines and retains only playlist delegation wrappers.
- No playlist behavior, user-facing text, or visual style changes.
- No new external dependency.
- Focused and full automated verification passes.

## Follow-up Slices

Export/import, audio tools, metadata editing, cleanup, and history extraction remain separate changes. This specification does not authorize them.
