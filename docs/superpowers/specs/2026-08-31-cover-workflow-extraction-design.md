# Cover Workflow Extraction Design

## Status

Approved direction in chat on 2026-08-31. This document defines the first implementation slice of the broader MokaMusic UI refactor.

## Context

`app/ui/metadata_workflow.py` contains 1,956 physical lines and coordinates unrelated metadata, cover, cleanup, audio, backup, playlist, and import/export operations. Its cover-art section currently depends on application state through implicit `self` members, including both library controllers, tree widgets, preview state, file dialogs, backup creation, progress UI, refresh behavior, undo recording, and notifications.

The domain operation is already better isolated in `CoverController` and `cover_service`, with unit tests for target selection, automatic-cover planning, image processing, applying a cover, cache invalidation, and preview impact. The missing boundary is the UI workflow that coordinates those operations.

## Scope

This slice extracts only the cover-art workflow from `MetadataWorkflowMixin` into a composed coordinator. It preserves existing behavior and visual appearance.

Included:

- Selecting a cover for the active preview.
- Handling an image dropped on the preview.
- Resolving selected or preview cover targets.
- Applying a manual cover to a folder or selected files.
- Finding and applying covers already present in music folders.
- Confirmation, backup, progress, result reporting, undo registration, preview reload, and library refresh.
- Characterization tests for the coordinator.
- Compatibility wrappers on `MokaMusicApp` while existing bindings are migrated.

Not included:

- Metadata editing, cleanup, audio tools, playlists, backup history, or import/export extraction.
- Changes to `CoverController` behavior or cover file formats.
- A visual redesign, new theme, or widget hierarchy changes.
- Renaming translation keys or changing user-facing messages.
- Introducing an event bus, dependency-injection framework, or new third-party package.

## Approaches Considered

### Smaller mixin

Moving cover methods into `CoverWorkflowMixin` would reduce the original file quickly, but the new mixin would retain the same undocumented `self` contract. It moves the coupling without fixing it.

### Composed coordinator with explicit ports — selected

Create a `CoverWorkflow` object whose domain services and application interactions are supplied explicitly. This makes the orchestration independently testable while allowing an incremental migration that preserves current callbacks.

### Full MVVM or application event bus

A new global state and event architecture could decouple all UI flows, but it would affect most of the application at once. That cost and migration risk are not justified for this slice.

## Architecture

Add `app/ui/workflows/cover_workflow.py` and `app/ui/workflows/__init__.py`.

`CoverWorkflow` owns orchestration only. It does not read audio metadata or modify image files directly; those responsibilities remain in `CoverController`, `SongInfo`, and `cover_service`.

Dependencies are grouped into two small, typed port objects to avoid a long constructor without recreating a generic application context:

### `CoverUiPort`

Provides only cover-related UI operations:

- Translation.
- Current preview access and preview-cover update.
- Image selection and validation.
- Warning, confirmation, information, and error dialogs.
- Progress creation.
- Toast display.
- Logging of unexpected drop-processing failures.

### `CoverLibraryPort`

Provides only library integration:

- Selected filenames grouped by controller and tree.
- Current preview controller and filename.
- Tree lookup for a controller.
- Metadata backup creation for target groups.
- Refresh of changed controller/tree pairs.
- Reload of the active preview.
- Undo registration.
- Conversion of raw drop data into a `DropPayload` through the existing `DropController`.

The ports are frozen dataclasses containing typed callables. They must not expose `MokaMusicApp` itself, arbitrary attribute lookup, or a generic `context` dictionary.

`MokaMusicApp` constructs one `CoverWorkflow` after its controllers and widgets are available. During this slice, existing methods such as `_select_preview_cover`, `_handle_cover_drop`, and `_apply_auto_cover_from_folder` remain as one-line compatibility wrappers. Existing menu commands and Tkinter bindings therefore remain stable. Direct binding to the coordinator and wrapper removal are explicitly deferred to a separately approved slice.

## Components and Responsibilities

### `CoverWorkflow`

- Resolve targets using `CoverController.cover_targets`.
- Validate prerequisites and request confirmation.
- Request backups before mutation.
- Open and close progress UI safely.
- Call `CoverController.apply_manual_cover` or `apply_cover_plan`.
- Ask the library port to refresh only changed controller/tree pairs.
- Reload or update the preview when affected.
- Register undo only after at least one successful mutation.
- Present success, partial-success, cancellation, and failure states.

### `CoverController`

No new UI knowledge. It continues to build plans, copy folder covers, apply metadata, invalidate song information, and return `CoverApplyResult`.

### `MetadataWorkflowMixin`

Delegates cover entry points to `self.cover_workflow`. Shared behavior such as `_refresh_changed_library_pairs` remains in place until another workflow needs a more general refresh coordinator.

### `MokaMusicApp`

Acts as composition root. It creates the ports from existing services, widgets, and callbacks. It must not duplicate cover orchestration.

## Data Flow

Manual cover flow:

1. An existing button or drop binding calls the compatibility wrapper.
2. `CoverWorkflow` obtains or validates an image path.
3. The workflow obtains explicit selection targets, falling back to the active preview.
4. It expands backup targets to the complete affected folders when folder-wide application is enabled.
5. It asks the user to confirm the affected count.
6. It creates backups; failure or cancellation stops the flow before mutation.
7. It opens progress UI and calls `CoverController`.
8. The progress object closes in `finally`.
9. Changed libraries and the preview are refreshed.
10. Undo and success/partial/failure feedback are emitted according to `CoverApplyResult`.

Automatic cover flow follows the same sequence after `CoverController.build_auto_cover_plan` groups tracks by discovered cover path.

## Error Handling

- Expected validation failures remain user-facing and do not raise.
- A missing active song, missing target, missing automatic cover, declined confirmation, or backup failure stops before mutation.
- Progress UI is always closed with `try/finally`.
- Partial success keeps successful changes, registers undo, refreshes affected views, and reports the number of errors.
- Total failure does not register undo and reports controller errors.
- Unexpected exceptions are caught only at the Tkinter drop-event boundary, logged, and shown as a localized error. Domain and testable coordinator methods do not broadly suppress unexpected exceptions.
- Cancellation returned through the existing progress callback is treated as a partial or failed result according to the number of completed mutations.

## UI/UX Constraints

This slice intentionally preserves layout, labels, colors, focus order, dialog sequence, and progress behavior. Refactoring must not turn a visual change into an unreviewed side effect.

The coordinator boundary prepares a later UI redesign by separating semantic actions from widgets. Future views will be able to expose the same actions through a `LibraryToolbar`, `MetadataInspector`, or context action without duplicating cover logic.

## Testing Strategy

Add `tests/test_cover_workflow.py` with fakes for both ports and existing domain objects where appropriate.

Characterization cases:

- Selecting a cover without an active preview warns and stops.
- Dropping a payload without an image warns and stops.
- Invalid image validation stops before confirmation and backup.
- No selection and no preview target warns and stops.
- Declining confirmation performs no backup or mutation.
- Backup failure performs no mutation.
- Manual application uses folder-wide targets by default.
- Selected-only application preserves the selected-only option.
- Progress closes after success and after an exception.
- Success refreshes changed libraries, reloads an affected preview, records undo, and shows success feedback.
- Partial success records undo and shows warning feedback.
- Total failure does not record undo and shows an error.
- Automatic cover with no discovered groups warns and stops.
- Automatic cover reports missing songs in its confirmation.
- Drop parsing exceptions are logged and shown to the user.

Existing `test_cover_controller.py` and `test_cover_service.py` remain unchanged and must continue to pass. The full unit-test suite, Ruff check, Ruff formatting check, and module compilation are required before completion.

## Migration Sequence

1. Write failing characterization tests against the proposed `CoverWorkflow` API.
2. Add typed port dataclasses and implement the smallest behavior that passes each test.
3. Instantiate the coordinator in `MokaMusicApp` after preview widgets and bindings are available.
4. Replace cover method bodies in `MetadataWorkflowMixin` with compatibility delegation.
5. Remove imports from `metadata_workflow.py` that are no longer used.
6. Run focused tests, full tests, Ruff, formatting verification, and compilation.
7. Confirm that startup and the existing cover interactions retain their visible behavior.

## Success Criteria

- Cover orchestration is independently testable without constructing a Tk root or `MokaMusicApp`.
- `CoverWorkflow` depends only on the two declared ports plus existing cover-domain services.
- Existing cover callbacks remain compatible.
- The cover-related orchestration is removed from `metadata_workflow.py`; wrappers contain no business logic.
- No existing feature, translation, or visible style changes.
- Focused and full automated verification passes.
- No new external dependency is introduced.

## Follow-up Slices

After this slice is verified, the same composition pattern can be evaluated separately for metadata editing, cleanup, playlists, import/export, application lifecycle, and player presentation. Those changes require their own scoped designs or bounded approvals and are not implicitly authorized by this document.
