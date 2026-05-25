"""Application controllers that coordinate views, services, and state."""

from .add_music_controller import abrir_selector_archivo, agregar_a_lista
from .backup_controller import BackupController
from .cleanup_controller import CleanupController
from .cleanup_preset_controller import CleanupPresetController, PresetUpsertResult
from .config_controller import AppConfig, ConfigController
from .cover_controller import CoverApplyResult, CoverController, CoverPlan
from .drop_controller import DropAddResult, DropController, DropPayload
from .library_ui_controller import LibraryUiController
from .metadata_apply_controller import (
    BatchMetadataApplyResult,
    MetadataApplyController,
    PreviewMetadataTarget,
    SingleMetadataApplyResult,
)
from .metadata_controller import MetadataController
from .metadata_dialog_controller import METADATA_FIELDS, MetadataDialogController
from .menu_controller import MenuCallbacks, MenuController
from .playback_controller import PlaybackController
from .playback_selection_controller import PlaybackSelection, PlaybackSelectionController
from .rename_controller import RenameApplyResult, RenameController, RenamePlanItem
from .selection_controller import SelectionController
from .song_actions_controller import SongActions
from .ui_text_controller import TEXT_WIDGET_KEYS, UiTextController

__all__ = [
    "BackupController",
    "CleanupController",
    "CleanupPresetController",
    "AppConfig",
    "ConfigController",
    "CoverApplyResult",
    "CoverController",
    "CoverPlan",
    "DropAddResult",
    "DropController",
    "DropPayload",
    "LibraryUiController",
    "BatchMetadataApplyResult",
    "MetadataApplyController",
    "MetadataController",
    "MetadataDialogController",
    "METADATA_FIELDS",
    "MenuCallbacks",
    "MenuController",
    "PlaybackController",
    "PlaybackSelection",
    "PlaybackSelectionController",
    "PresetUpsertResult",
    "PreviewMetadataTarget",
    "RenameApplyResult",
    "RenameController",
    "RenamePlanItem",
    "SelectionController",
    "SingleMetadataApplyResult",
    "TEXT_WIDGET_KEYS",
    "UiTextController",
]
