from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import ttk
from typing import Callable

from ..models.audio_edit_project import AudioEditEffect, AudioEditEffectKind
from ..utils import themed_messagebox as messagebox


def edit_audio_effect_chain(
    parent: tk.Misc,
    effects: tuple[AudioEditEffect, ...],
    translate: Callable[..., str],
) -> tuple[AudioEditEffect, ...] | None:
    dialog = tk.Toplevel(parent)
    dialog.title(translate("audio_editor.fx_title"))
    dialog.transient(parent)
    dialog.resizable(False, False)
    dialog.grab_set()
    result: tuple[AudioEditEffect, ...] | None = None
    chain = list(effects)

    content = ttk.Frame(dialog, padding=14)
    content.pack(fill="both", expand=True)
    ttk.Label(
        content,
        text=translate("audio_editor.fx_order"),
        wraplength=500,
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

    chain_frame = ttk.LabelFrame(content, text=translate("audio_editor.fx_chain"), padding=8)
    chain_frame.grid(row=1, column=0, sticky="ns", padx=(0, 10))
    effect_list = tk.Listbox(chain_frame, width=29, height=8, exportselection=False)
    effect_list.grid(row=0, column=0, columnspan=2, sticky="ew")
    list_scroll = ttk.Scrollbar(chain_frame, orient="vertical", command=effect_list.yview)
    list_scroll.grid(row=0, column=2, sticky="ns")
    effect_list.configure(yscrollcommand=list_scroll.set)

    wet_var = tk.StringVar(value="25")
    delay_var = tk.StringVar(value="350")
    feedback_var = tk.StringVar(value="35")
    room_size_var = tk.StringVar(value="50")
    enabled_var = tk.BooleanVar(value=True)
    details = ttk.LabelFrame(content, text=translate("audio_editor.fx_settings"), padding=8)
    details.grid(row=1, column=1, sticky="nsew")
    detail_rows = (
        ("audio_editor.fx_wet", wet_var, 0, 100, 1),
        ("audio_editor.fx_delay", delay_var, 40, 1500, 10),
        ("audio_editor.fx_feedback", feedback_var, 0, 80, 1),
        ("audio_editor.fx_room_size", room_size_var, 10, 100, 1),
    )
    detail_widgets: dict[str, ttk.Widget] = {}
    ttk.Checkbutton(
        details,
        text=translate("audio_editor.fx_enabled"),
        variable=enabled_var,
    ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    for row, (key, variable, minimum, maximum, increment) in enumerate(detail_rows, start=1):
        label = ttk.Label(details, text=translate(key))
        label.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
        spinbox = ttk.Spinbox(
            details,
            from_=minimum,
            to=maximum,
            increment=increment,
            textvariable=variable,
            width=9,
        )
        spinbox.grid(row=row, column=1, sticky="ew", pady=2)
        detail_widgets[key] = label
        detail_widgets[f"{key}.input"] = spinbox
    ttk.Label(
        details,
        text=translate("audio_editor.fx_room_reverb_note"),
        wraplength=280,
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))

    commands = ttk.Frame(chain_frame)
    commands.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    ttk.Button(
        commands,
        text=translate("audio_editor.fx_add_reverb"),
        command=lambda: add_effect(AudioEditEffectKind.REVERB),
    ).grid(row=0, column=0, padx=(0, 3), pady=2)
    ttk.Button(
        commands,
        text=translate("audio_editor.fx_add_delay"),
        command=lambda: add_effect(AudioEditEffectKind.DELAY),
    ).grid(row=0, column=1, padx=3, pady=2)
    ttk.Button(
        commands,
        text=translate("audio_editor.fx_move_up"),
        command=lambda: move_effect(-1),
    ).grid(row=1, column=0, padx=(0, 3), pady=2)
    ttk.Button(
        commands,
        text=translate("audio_editor.fx_move_down"),
        command=lambda: move_effect(1),
    ).grid(row=1, column=1, padx=3, pady=2)
    ttk.Button(
        commands,
        text=translate("audio_editor.fx_remove"),
        command=lambda: remove_effect(),
    ).grid(row=1, column=2, padx=3, pady=2)
    ttk.Button(
        commands,
        text=translate("audio_editor.fx_reset"),
        command=lambda: reset_effect(),
    ).grid(row=2, column=0, columnspan=3, sticky="ew", pady=2)

    buttons = ttk.Frame(content)
    buttons.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(buttons, text=translate("audio_editor.cancel"), command=dialog.destroy).pack(side="right", padx=(6, 0))

    def selected_index() -> int | None:
        selection = effect_list.curselection()
        return int(selection[0]) if selection else None

    def effect_name(effect: AudioEditEffect) -> str:
        return translate(
            "audio_editor.fx_effect_row",
            name=translate(f"audio_editor.fx_kind_{effect.kind.value}"),
            state=translate("audio_editor.fx_on" if effect.enabled else "audio_editor.fx_off"),
            wet=round(effect.wet * 100),
        )

    def refresh_list(selection: int | None = None) -> None:
        effect_list.delete(0, tk.END)
        for effect in chain:
            effect_list.insert(tk.END, effect_name(effect))
        if selection is not None and 0 <= selection < len(chain):
            effect_list.selection_set(selection)
            effect_list.activate(selection)
            load_selected()

    def set_detail_visibility(effect: AudioEditEffect | None) -> None:
        delay_state = "normal" if effect and effect.kind == AudioEditEffectKind.DELAY else "disabled"
        room_state = "normal" if effect and effect.kind == AudioEditEffectKind.REVERB else "disabled"
        detail_widgets["audio_editor.fx_delay.input"].configure(state=delay_state)
        detail_widgets["audio_editor.fx_feedback.input"].configure(state="normal" if effect else "disabled")
        detail_widgets["audio_editor.fx_room_size.input"].configure(state=room_state)
        detail_widgets["audio_editor.fx_delay"].configure(state=delay_state)
        detail_widgets["audio_editor.fx_feedback"].configure(state="normal" if effect else "disabled")
        detail_widgets["audio_editor.fx_room_size"].configure(state=room_state)

    def load_selected(_event=None) -> None:
        index = selected_index()
        effect = chain[index] if index is not None and index < len(chain) else None
        enabled_var.set(effect.enabled if effect else False)
        wet_var.set(f"{effect.wet * 100:g}" if effect else "25")
        delay_var.set(f"{effect.delay_ms:g}" if effect else "350")
        feedback_var.set(f"{effect.feedback * 100:g}" if effect else "35")
        room_size_var.set(f"{effect.room_size * 100:g}" if effect else "50")
        set_detail_visibility(effect)

    def edited_effect(effect: AudioEditEffect) -> AudioEditEffect:
        return replace(
            effect,
            enabled=enabled_var.get(),
            wet=float(wet_var.get()) / 100,
            delay_ms=delay_var.get(),
            feedback=float(feedback_var.get()) / 100,
            room_size=float(room_size_var.get()) / 100,
        )

    def add_effect(kind: AudioEditEffectKind) -> None:
        if len(chain) >= 8:
            messagebox.showerror(
                translate("dialog.error"),
                translate("audio_editor.fx_limit"),
                parent=dialog,
            )
            return
        effect = (
            AudioEditEffect(kind, wet=0.2, feedback=0.55, room_size=0.5)
            if kind == AudioEditEffectKind.REVERB
            else AudioEditEffect(kind)
        )
        chain.append(effect)
        refresh_list(len(chain) - 1)

    def update_effect() -> None:
        index = selected_index()
        if index is None:
            messagebox.showerror(
                translate("dialog.error"),
                translate("audio_editor.fx_select_first"),
                parent=dialog,
            )
            return
        try:
            chain[index] = edited_effect(chain[index])
        except ValueError as exc:
            messagebox.showerror(
                translate("dialog.error"),
                translate("audio_editor.processing_invalid", error=exc),
                parent=dialog,
            )
            return
        refresh_list(index)

    def move_effect(offset: int) -> None:
        index = selected_index()
        if index is None:
            return
        destination = index + offset
        if not 0 <= destination < len(chain):
            return
        chain[index], chain[destination] = chain[destination], chain[index]
        refresh_list(destination)

    def remove_effect() -> None:
        index = selected_index()
        if index is None:
            return
        chain.pop(index)
        refresh_list(min(index, len(chain) - 1) if chain else None)
        if not chain:
            load_selected()

    def reset_effect() -> None:
        index = selected_index()
        if index is None:
            return
        current = chain[index]
        restored = (
            AudioEditEffect(current.kind, wet=0.2, feedback=0.55, room_size=0.5, id=current.id)
            if current.kind == AudioEditEffectKind.REVERB
            else AudioEditEffect(current.kind, id=current.id)
        )
        chain[index] = restored
        refresh_list(index)

    def apply() -> None:
        nonlocal result
        index = selected_index()
        if index is not None:
            try:
                chain[index] = edited_effect(chain[index])
            except ValueError as exc:
                messagebox.showerror(
                    translate("dialog.error"),
                    translate("audio_editor.processing_invalid", error=exc),
                    parent=dialog,
                )
                return
        result = tuple(chain)
        dialog.destroy()

    ttk.Button(
        details,
        text=translate("audio_editor.fx_update"),
        command=update_effect,
    ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    ttk.Button(
        buttons,
        text=translate("audio_editor.apply_processing"),
        command=apply,
    ).pack(side="right")
    effect_list.bind("<<ListboxSelect>>", load_selected)
    refresh_list(0 if chain else None)
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    if hasattr(parent, "_style_editor_dialog"):
        parent._style_editor_dialog(dialog)
    dialog.wait_window()
    return result
