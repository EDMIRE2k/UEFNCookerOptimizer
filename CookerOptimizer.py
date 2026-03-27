import unreal
import tkinter as tk
from tkinter import messagebox
import math

_COOKER_OPTIMIZER_APP = None
_TK_MASTER = None


# ------------------------------------------------------------
# Tk root management
# ------------------------------------------------------------

def get_tk_master():
    global _TK_MASTER

    try:
        if _TK_MASTER is not None and _TK_MASTER.winfo_exists():
            return _TK_MASTER
    except Exception:
        _TK_MASTER = None

    _TK_MASTER = tk.Tk()
    _TK_MASTER.withdraw()
    return _TK_MASTER


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

def log(msg):
    unreal.log("[CookerOptimizer] " + str(msg))


def warn(msg):
    unreal.log_warning("[CookerOptimizer] " + str(msg))


def err(msg):
    unreal.log_error("[CookerOptimizer] " + str(msg))


# ------------------------------------------------------------
# Actor helpers
# ------------------------------------------------------------

def get_all_level_actors_safe():
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem:
            return list(subsystem.get_all_level_actors() or [])
    except Exception:
        pass

    try:
        return list(unreal.EditorLevelLibrary.get_all_level_actors() or [])
    except Exception as e:
        raise RuntimeError(f"Could not get level actors: {e}")


def get_selected_level_actors_safe():
    try:
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        if subsystem:
            return list(subsystem.get_selected_level_actors() or [])
    except Exception:
        pass

    try:
        return list(unreal.EditorLevelLibrary.get_selected_level_actors() or [])
    except Exception as e:
        raise RuntimeError(f"Could not get selected level actors: {e}")


def get_actor_label_safe(actor):
    try:
        return actor.get_actor_label()
    except Exception:
        try:
            return actor.get_name()
        except Exception:
            return "<Unknown Actor>"


def get_actor_class_name_safe(actor):
    try:
        return actor.get_class().get_name()
    except Exception:
        return "UnknownClass"


def is_blueprint_actor(actor):
    try:
        cls = actor.get_class()
        class_path = str(cls.get_path_name())
        return not class_path.startswith("/Script/")
    except Exception:
        return False


def is_static_mesh_actor(actor):
    try:
        return actor.get_class().get_name() == "StaticMeshActor"
    except Exception:
        return False


def is_landscape_actor(actor):
    try:
        return actor.get_class().get_name() in {"Landscape", "LandscapeProxy", "LandscapeStreamingProxy"}
    except Exception:
        return False


def get_editor_only_flag(actor):
    try:
        return bool(actor.get_editor_property("is_editor_only_actor"))
    except Exception:
        try:
            return bool(actor.is_editor_only_actor)
        except Exception:
            return False


def set_editor_only_flag(actor, enabled: bool):
    actor.set_editor_property("is_editor_only_actor", enabled)


def save_current_level():
    try:
        unreal.EditorLevelLibrary.save_current_level()
    except Exception as e:
        warn(f"Could not auto-save current level: {e}")


def build_eligible_actor_rows(include_blueprints, include_static_meshes, include_landscapes, exclude_already_editor_only):
    actors = get_all_level_actors_safe()
    rows = []

    for actor in actors:
        if actor is None:
            continue

        is_editor_only = get_editor_only_flag(actor)
        if exclude_already_editor_only and is_editor_only:
            continue

        matched = False
        actor_type = None

        if include_blueprints and is_blueprint_actor(actor):
            matched = True
            actor_type = "Blueprint Actor"
        elif include_static_meshes and is_static_mesh_actor(actor):
            matched = True
            actor_type = "Static Mesh Actor"
        elif include_landscapes and is_landscape_actor(actor):
            matched = True
            actor_type = "Landscape"

        if not matched:
            continue

        rows.append({
            "actor": actor,
            "label": get_actor_label_safe(actor),
            "class_name": get_actor_class_name_safe(actor),
            "actor_type": actor_type,
            "is_editor_only": is_editor_only,
        })

    rows.sort(key=lambda r: (r["actor_type"].lower(), r["class_name"].lower(), r["label"].lower()))
    return rows


class CookerOptimizerApp:
    def __init__(self):
        self.master = get_tk_master()
        self.root = tk.Toplevel(self.master)
        self.root.title("Cooker Optimizer")
        self.root.geometry("1180x760")
        self.root.configure(bg="#14171b")
        self.root.attributes("-topmost", True)

        self.tick_handle = None
        self.is_closing = False
        self.eligible_rows = []
        self.has_scanned = False

        self.current_preview_percent = 25.0
        self.current_preview_label = "25%"

        self.cook_feedback_history = []

        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.start_tick()

    def build_ui(self):
        bg = "#14171b"
        panel = "#1b2026"
        card = "#1f252d"
        panel2 = "#212730"
        fg = "#e7ecf2"
        muted = "#a8b1bd"
        accent = "#4f7cff"
        accent2 = "#5b6472"
        accent3 = "#3f556e"
        good = "#46b37b"
        bad = "#d96a6a"
        border = "#2a313b"
        warn_color = "#f0c674"

        outer = tk.Frame(self.root, bg=bg)
        outer.pack(fill="both", expand=True, padx=14, pady=14)

        left = tk.Frame(outer, bg=bg)
        left.pack(side="left", fill="both", expand=True)

        right = tk.Frame(outer, bg=bg, width=340)
        right.pack(side="right", fill="y", padx=(14, 0))
        right.pack_propagate(False)

        header = tk.Frame(left, bg=panel, highlightbackground=border, highlightthickness=1)
        header.pack(fill="x", pady=(0, 12))

        tk.Label(
            header,
            text="Cooker Optimizer",
            font=("Segoe UI", 16, "bold"),
            fg=fg,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(14, 2))

        tk.Label(
            header,
            text="Tool created by BiomeForge since epic won't fix it themselves",
            font=("Segoe UI", 8),
            fg="#8e99a8",
            bg=panel
        ).pack(anchor="w", padx=16, pady=(0, 2))

        tk.Label(
            header,
            text="Apply editor-only flags to selected batches of outliner actors.",
            font=("Segoe UI", 9),
            fg=muted,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(0, 14))

        filters = tk.Frame(left, bg=panel, highlightbackground=border, highlightthickness=1)
        filters.pack(fill="x", pady=(0, 12))

        tk.Label(
            filters,
            text="Actor Types",
            font=("Segoe UI", 10, "bold"),
            fg=fg,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(12, 8))

        self.include_blueprints_var = tk.BooleanVar(master=self.root, value=False)
        self.include_static_meshes_var = tk.BooleanVar(master=self.root, value=False)
        self.include_landscapes_var = tk.BooleanVar(master=self.root, value=False)
        self.exclude_already_editor_only_var = tk.BooleanVar(master=self.root, value=False)

        row1 = tk.Frame(filters, bg=panel)
        row1.pack(fill="x", padx=16, pady=(0, 6))

        tk.Checkbutton(
            row1,
            text="Blueprint Actors",
            variable=self.include_blueprints_var,
            fg=fg,
            bg=panel,
            activebackground=panel,
            activeforeground=fg,
            selectcolor=panel2,
            highlightthickness=0,
            bd=0
        ).pack(side="left", padx=(0, 16))

        tk.Checkbutton(
            row1,
            text="Static Mesh Actors",
            variable=self.include_static_meshes_var,
            fg=fg,
            bg=panel,
            activebackground=panel,
            activeforeground=fg,
            selectcolor=panel2,
            highlightthickness=0,
            bd=0
        ).pack(side="left", padx=(0, 16))

        tk.Checkbutton(
            row1,
            text="Landscapes",
            variable=self.include_landscapes_var,
            fg=fg,
            bg=panel,
            activebackground=panel,
            activeforeground=fg,
            selectcolor=panel2,
            highlightthickness=0,
            bd=0
        ).pack(side="left")

        row2 = tk.Frame(filters, bg=panel)
        row2.pack(fill="x", padx=16, pady=(0, 12))

        tk.Checkbutton(
            row2,
            text="Exclude actors already marked editor-only from the scan",
            variable=self.exclude_already_editor_only_var,
            fg=fg,
            bg=panel,
            activebackground=panel,
            activeforeground=fg,
            selectcolor=panel2,
            highlightthickness=0,
            bd=0
        ).pack(side="left")

        controls = tk.Frame(left, bg=panel, highlightbackground=border, highlightthickness=1)
        controls.pack(fill="x", pady=(0, 12))

        tk.Label(
            controls,
            text="Actions",
            font=("Segoe UI", 10, "bold"),
            fg=fg,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(12, 8))

        btn_row1 = tk.Frame(controls, bg=panel)
        btn_row1.pack(fill="x", padx=16, pady=(0, 8))

        tk.Button(
            btn_row1,
            text="Scan",
            command=self.scan,
            bg=accent,
            fg="white",
            activebackground=accent,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=16,
            pady=9
        ).pack(side="left")

        tk.Button(
            btn_row1,
            text="1/2",
            command=lambda: self.apply_fraction(2),
            bg=accent2,
            fg="white",
            activebackground=accent2,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=20,
            pady=9
        ).pack(side="left", padx=(10, 0))

        tk.Button(
            btn_row1,
            text="1/3",
            command=lambda: self.apply_fraction(3),
            bg=accent2,
            fg="white",
            activebackground=accent2,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=20,
            pady=9
        ).pack(side="left", padx=(10, 0))

        tk.Button(
            btn_row1,
            text="1/4",
            command=lambda: self.apply_fraction(4),
            bg=accent2,
            fg="white",
            activebackground=accent2,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=20,
            pady=9
        ).pack(side="left", padx=(10, 0))

        btn_row2 = tk.Frame(controls, bg=panel)
        btn_row2.pack(fill="x", padx=16, pady=(0, 14))

        tk.Label(
            btn_row2,
            text="Custom %",
            fg=fg,
            bg=panel,
            font=("Segoe UI", 9, "bold")
        ).pack(side="left")

        self.custom_percent_var = tk.StringVar(master=self.root, value="25")
        self.custom_percent_var.trace_add("write", self.on_custom_percent_changed)

        tk.Entry(
            btn_row2,
            textvariable=self.custom_percent_var,
            width=8,
            bg=panel2,
            fg=fg,
            insertbackground=fg,
            relief="flat",
            bd=0
        ).pack(side="left", padx=(8, 8), ipady=6)

        tk.Button(
            btn_row2,
            text="Custom",
            command=self.apply_custom_percentage,
            bg=accent2,
            fg="white",
            activebackground=accent2,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=18,
            pady=9
        ).pack(side="left", padx=(0, 10))

        tk.Button(
            btn_row2,
            text="Undo All",
            command=self.undo_all,
            bg=accent3,
            fg="white",
            activebackground=accent3,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=18,
            pady=9
        ).pack(side="left")

        tk.Button(
            btn_row2,
            text="Mark Selected",
            command=lambda: self.apply_to_selected(True),
            bg="#2f6f4f",
            fg="white",
            activebackground="#2f6f4f",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=18,
            pady=9
        ).pack(side="left", padx=(10, 0))

        tk.Button(
            btn_row2,
            text="Clear Selected",
            command=lambda: self.apply_to_selected(False),
            bg="#7a3f3f",
            fg="white",
            activebackground="#7a3f3f",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=18,
            pady=9
        ).pack(side="left", padx=(10, 0))

        metrics = tk.Frame(left, bg=panel, highlightbackground=border, highlightthickness=1)
        metrics.pack(fill="x", pady=(0, 12))

        tk.Label(
            metrics,
            text="Scan Metrics",
            font=("Segoe UI", 10, "bold"),
            fg=fg,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(12, 10))

        self.metric_total_var = tk.StringVar(master=self.root, value="0")
        self.metric_editor_only_var = tk.StringVar(master=self.root, value="0")
        self.metric_not_editor_only_var = tk.StringVar(master=self.root, value="0")
        self.metric_blueprints_var = tk.StringVar(master=self.root, value="0")
        self.metric_static_mesh_var = tk.StringVar(master=self.root, value="0")
        self.metric_landscape_var = tk.StringVar(master=self.root, value="0")

        grid = tk.Frame(metrics, bg=panel)
        grid.pack(fill="x", padx=16, pady=(0, 10))

        self._metric_card(grid, "Eligible Actors", self.metric_total_var, fg, 0, 0, card, border)
        self._metric_card(grid, "Already Editor-Only", self.metric_editor_only_var, good, 0, 1, card, border)
        self._metric_card(grid, "Not Editor-Only", self.metric_not_editor_only_var, bad, 0, 2, card, border)
        self._metric_card(grid, "Blueprint Actors", self.metric_blueprints_var, fg, 1, 0, card, border)
        self._metric_card(grid, "Static Mesh Actors", self.metric_static_mesh_var, fg, 1, 1, card, border)
        self._metric_card(grid, "Landscapes", self.metric_landscape_var, fg, 1, 2, card, border)

        preview = tk.Frame(left, bg=panel, highlightbackground=border, highlightthickness=1)
        preview.pack(fill="x", pady=(0, 12))

        tk.Label(
            preview,
            text="Preview Before Apply",
            font=("Segoe UI", 10, "bold"),
            fg=fg,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(12, 10))

        self.preview_mode_var = tk.StringVar(master=self.root, value="25%")
        self.preview_count_var = tk.StringVar(master=self.root, value="0")
        self.preview_total_var = tk.StringVar(master=self.root, value="0")

        preview_grid = tk.Frame(preview, bg=panel)
        preview_grid.pack(fill="x", padx=16, pady=(0, 14))

        self._metric_card(preview_grid, "Next Action", self.preview_mode_var, fg, 0, 0, card, border)
        self._metric_card(preview_grid, "Actors To Mark", self.preview_count_var, "#f0c674", 0, 1, card, border)
        self._metric_card(preview_grid, "Scanned Pool", self.preview_total_var, fg, 0, 2, card, border)

        cook_panel = tk.Frame(left, bg=panel, highlightbackground=border, highlightthickness=1)
        cook_panel.pack(fill="x", pady=(0, 12))

        tk.Label(
            cook_panel,
            text="Did project cook with current settings?",
            font=("Segoe UI", 10, "bold"),
            fg=fg,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(12, 6))

        tk.Label(
            cook_panel,
            text="Do not use these buttons until you successfully load into a session or you get a cooker out-of-memory error.",
            font=("Segoe UI", 8),
            fg=warn_color,
            bg=panel,
            wraplength=720,
            justify="left"
        ).pack(anchor="w", padx=16, pady=(0, 4))

        tk.Label(
            cook_panel,
            text="These buttons stay locked until you scan at least once.",
            font=("Segoe UI", 8),
            fg=muted,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(0, 10))

        cook_btn_row = tk.Frame(cook_panel, bg=panel)
        cook_btn_row.pack(fill="x", padx=16, pady=(0, 12))

        self.cook_yes_btn = tk.Button(
            cook_btn_row,
            text="Yes",
            command=lambda: self.report_cook_result(True),
            state="disabled",
            bg="#2f6f4f",
            fg="white",
            activebackground="#2f6f4f",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=20,
            pady=9
        )
        self.cook_yes_btn.pack(side="left")

        self.cook_no_btn = tk.Button(
            cook_btn_row,
            text="No",
            command=lambda: self.report_cook_result(False),
            state="disabled",
            bg="#7a3f3f",
            fg="white",
            activebackground="#7a3f3f",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=20,
            pady=9
        )
        self.cook_no_btn.pack(side="left", padx=(10, 0))

        self.cook_history_count_var = tk.StringVar(master=self.root, value="0")
        self.confidence_value_var = tk.StringVar(master=self.root, value="Hidden")
        self.confidence_basis_var = tk.StringVar(master=self.root, value="Awaiting first reported cook result")

        cook_grid = tk.Frame(cook_panel, bg=panel)
        cook_grid.pack(fill="x", padx=16, pady=(0, 14))

        self._metric_card(cook_grid, "Reported Results", self.cook_history_count_var, fg, 0, 0, card, border)
        self._metric_card(cook_grid, "Current Confidence", self.confidence_value_var, "#f0c674", 0, 1, card, border)

        basis_card = tk.Frame(cook_grid, bg=card, highlightbackground=border, highlightthickness=1)
        basis_card.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")
        cook_grid.grid_columnconfigure(2, weight=1)

        tk.Label(
            basis_card,
            text="Confidence Basis",
            fg="#a8b1bd",
            bg=card,
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=12, pady=(10, 2))

        tk.Label(
            basis_card,
            textvariable=self.confidence_basis_var,
            fg=fg,
            bg=card,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=240
        ).pack(anchor="w", padx=12, pady=(0, 10))

        self.summary_lbl = tk.Label(
            left,
            text="Ready.",
            fg=muted,
            bg=bg,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w"
        )
        self.summary_lbl.pack(fill="x", pady=(0, 8))

        self.status_lbl = tk.Label(
            left,
            text="Ready",
            fg=muted,
            bg=bg,
            font=("Segoe UI", 9)
        )
        self.status_lbl.pack(anchor="w")

        explainer = tk.Frame(right, bg=panel, highlightbackground=border, highlightthickness=1)
        explainer.pack(fill="both", expand=True)

        tk.Label(
            explainer,
            text="What this tool actually does",
            font=("Segoe UI", 11, "bold"),
            fg=fg,
            bg=panel
        ).pack(anchor="w", padx=16, pady=(14, 10))

        explanation_text = (
            "This tool does not magically fix cooker out of memory errors.\n\n"
            "It simply marks selected batches of actors as editor-only so they are excluded from cooked builds.\n\n"
            "That lets you test cooking the project in smaller batches instead of deleting actors from the map.\n\n"
            "Use it carefully:\n"
            "- editor-only actors will not exist in cooked output\n"
            "- references to them can become null in cooked builds\n"
            "- gameplay-critical actors should usually be avoided\n\n"
            "It is strongly advised that you check in your changes and back up the project before using this tool.\n\n"
            "This tool is not responsible for data loss caused by misuse. Use with caution.\n\n"
            "Suggested workflow:\n"
            "1. Scan\n"
            "2. Review preview count\n"
            "3. Mark a batch\n"
            "4. Attempt cook or session launch\n"
            "5. Report Yes/No in the cook section\n"
            "6. Adjust batch size based on confidence"
        )

        tk.Label(
            explainer,
            text=explanation_text,
            justify="left",
            wraplength=300,
            fg=muted,
            bg=panel,
            font=("Segoe UI", 9)
        ).pack(anchor="nw", padx=16, pady=(0, 16), fill="both")

    def _metric_card(self, parent, label, value_var, value_color, row, col, card_bg, border):
        card = tk.Frame(parent, bg=card_bg, highlightbackground=border, highlightthickness=1)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(
            card,
            text=label,
            fg="#a8b1bd",
            bg=card_bg,
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=12, pady=(10, 2))

        tk.Label(
            card,
            textvariable=value_var,
            fg=value_color,
            bg=card_bg,
            font=("Segoe UI", 16, "bold")
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def close(self):
        if self.is_closing:
            return

        self.is_closing = True

        try:
            if self.tick_handle:
                unreal.unregister_slate_post_tick_callback(self.tick_handle)
                self.tick_handle = None
        except Exception as e:
            warn(f"Close warning while unregistering tick: {e}")

        try:
            if self.root and self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass

        global _COOKER_OPTIMIZER_APP
        if _COOKER_OPTIMIZER_APP is self:
            _COOKER_OPTIMIZER_APP = None

        log("Cooker Optimizer closed.")

    def start_tick(self):
        def on_tick(dt):
            if self.is_closing:
                return
            try:
                if not self.root.winfo_exists():
                    self.close()
                    return
                self.root.update()
            except tk.TclError:
                self.close()
            except Exception as e:
                warn(f"Tick error: {e}")
                self.close()

        self.tick_handle = unreal.register_slate_post_tick_callback(on_tick)
        log("Cooker Optimizer opened.")

    def set_status(self, text):
        try:
            self.status_lbl.configure(text=text)
        except Exception:
            pass

    def set_feedback_buttons_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        try:
            self.cook_yes_btn.configure(state=state)
            self.cook_no_btn.configure(state=state)
        except Exception:
            pass

    def get_scan_options(self):
        try:
            self.root.update_idletasks()
        except Exception:
            pass

        return {
            "include_blueprints": bool(self.include_blueprints_var.get()),
            "include_static_meshes": bool(self.include_static_meshes_var.get()),
            "include_landscapes": bool(self.include_landscapes_var.get()),
            "exclude_already_editor_only": bool(self.exclude_already_editor_only_var.get()),
        }

    def update_metrics(self):
        total = len(self.eligible_rows)
        enabled_count = sum(1 for r in self.eligible_rows if r["is_editor_only"])
        disabled_count = total - enabled_count

        blueprint_count = sum(1 for r in self.eligible_rows if r["actor_type"] == "Blueprint Actor")
        static_mesh_count = sum(1 for r in self.eligible_rows if r["actor_type"] == "Static Mesh Actor")
        landscape_count = sum(1 for r in self.eligible_rows if r["actor_type"] == "Landscape")

        self.metric_total_var.set(str(total))
        self.metric_editor_only_var.set(str(enabled_count))
        self.metric_not_editor_only_var.set(str(disabled_count))
        self.metric_blueprints_var.set(str(blueprint_count))
        self.metric_static_mesh_var.set(str(static_mesh_count))
        self.metric_landscape_var.set(str(landscape_count))

        self.summary_lbl.configure(
            text=(
                f"Eligible actors: {total} | "
                f"Blueprints: {blueprint_count} | "
                f"Static Meshes: {static_mesh_count} | "
                f"Landscapes: {landscape_count}"
            )
        )

        self.update_preview_display()
        self.update_confidence_display()

    def get_preview_count(self, percent_value):
        total = len(self.eligible_rows)
        if total <= 0:
            return 0
        if percent_value <= 0:
            return 0
        if percent_value > 100:
            percent_value = 100.0

        return max(1, math.floor(total * (percent_value / 100.0)))

    def get_current_snapshot(self):
        total_pool = len(self.eligible_rows)
        percent_value = max(0.0, min(100.0, float(self.current_preview_percent)))
        target_count = self.get_preview_count(percent_value)
        ratio = (target_count / float(total_pool)) if total_pool > 0 else 0.0

        return {
            "percent": percent_value,
            "label": self.current_preview_label,
            "pool": total_pool,
            "count": target_count,
            "ratio": ratio,
        }

    def update_preview_display(self):
        snap = self.get_current_snapshot()
        self.preview_mode_var.set(self.current_preview_label)
        self.preview_count_var.set(str(snap["count"]))
        self.preview_total_var.set(str(snap["pool"]))

    def on_custom_percent_changed(self, *args):
        raw = self.custom_percent_var.get().strip()
        try:
            value = float(raw)
            self.current_preview_percent = value
            self.current_preview_label = f"{value:g}%"
        except Exception:
            self.current_preview_label = "Custom"
        self.update_preview_display()
        self.update_confidence_display()

    def estimate_confidence_for_current_settings(self):
        if not self.cook_feedback_history:
            return None, "Awaiting first reported cook result"

        snap = self.get_current_snapshot()
        current_percent = snap["percent"]
        current_pool = snap["pool"]

        if current_pool <= 0:
            return None, "No scanned pool"

        exact_matches = [
            h for h in self.cook_feedback_history
            if abs(h["percent"] - current_percent) < 0.0001 and h["pool"] == current_pool
        ]

        if exact_matches:
            exact_avg = sum(1.0 if h["success"] else 0.0 for h in exact_matches) / len(exact_matches)
            pct = int(round(exact_avg * 100.0))
            basis = f"Exact match from {len(exact_matches)} reported result(s) at {current_percent:g}% with pool {current_pool}"
            return pct, basis

        weighted_sum = 0.0
        total_weight = 0.0

        for h in self.cook_feedback_history:
            percent_distance = abs(h["percent"] - current_percent) / 100.0
            pool_distance = abs(h["pool"] - current_pool) / float(max(current_pool, 1))

            weight = 1.0 / (1.0 + (percent_distance * 6.0) + (pool_distance * 2.5))
            outcome = 1.0 if h["success"] else 0.0

            weighted_sum += outcome * weight
            total_weight += weight

        if total_weight <= 0:
            return None, "Insufficient history"

        pct = int(round((weighted_sum / total_weight) * 100.0))
        basis = f"Rough estimate from {len(self.cook_feedback_history)} prior reported result(s), weighted by setting similarity"
        return pct, basis

    def update_confidence_display(self):
        self.cook_history_count_var.set(str(len(self.cook_feedback_history)))

        pct, basis = self.estimate_confidence_for_current_settings()
        if pct is None:
            self.confidence_value_var.set("Hidden")
            self.confidence_basis_var.set(basis)
        else:
            self.confidence_value_var.set(f"{pct}%")
            self.confidence_basis_var.set(basis)

    def report_cook_result(self, success: bool):
        if not self.has_scanned or not self.eligible_rows:
            messagebox.showinfo("Scan Required", "Scan at least once before reporting a cook result.")
            return

        snap = self.get_current_snapshot()
        if snap["pool"] <= 0:
            messagebox.showinfo("Nothing Scanned", "No eligible actors are currently scanned.")
            return

        result_text = "SUCCESS" if success else "FAILED"
        msg = (
            f"Record cook result for current settings?\n\n"
            f"Result: {result_text}\n"
            f"Setting: {snap['label']}\n"
            f"Actors marked by current preview: {snap['count']}\n"
            f"Scanned pool: {snap['pool']}\n\n"
            f"Only use this after you either loaded into a session successfully or got a cooker out-of-memory error."
        )

        if not messagebox.askyesno("Record Cook Result", msg):
            return

        self.cook_feedback_history.append({
            "percent": snap["percent"],
            "pool": snap["pool"],
            "count": snap["count"],
            "success": success,
        })

        self.update_confidence_display()

        pct, basis = self.estimate_confidence_for_current_settings()
        if pct is None:
            summary = f"Recorded {result_text}.\n\nConfidence remains hidden."
        else:
            summary = (
                f"Recorded {result_text}.\n\n"
                f"Current rough cook probability for {self.current_preview_label}: {pct}%\n\n"
                f"{basis}"
            )

        messagebox.showinfo("Cook Result Recorded", summary)
        self.set_status(f"Recorded cook result: {result_text}")

    def scan(self):
        self.eligible_rows = []
        self.set_status("Scanning outliner actors ...")
        self.root.update_idletasks()

        try:
            opts = self.get_scan_options()

            if not (opts["include_blueprints"] or opts["include_static_meshes"] or opts["include_landscapes"]):
                messagebox.showwarning(
                    "No Actor Types Selected",
                    "Enable at least one actor type checkbox before scanning."
                )
                return

            self.eligible_rows = build_eligible_actor_rows(
                include_blueprints=opts["include_blueprints"],
                include_static_meshes=opts["include_static_meshes"],
                include_landscapes=opts["include_landscapes"],
                exclude_already_editor_only=opts["exclude_already_editor_only"]
            )

            self.has_scanned = True
            self.set_feedback_buttons_enabled(len(self.eligible_rows) > 0)

            self.update_metrics()
            self.set_status(f"Scan complete. Found {len(self.eligible_rows)} eligible actors.")
            log(f"Scan complete: {len(self.eligible_rows)} eligible actors.")

        except Exception as e:
            err(f"Scan failed: {e}")
            self.set_status(f"Scan failed: {e}")
            messagebox.showerror("Scan Failed", str(e))

    def _apply_percentage_internal(self, percent_value: float, label_text: str):
        if not self.eligible_rows:
            messagebox.showinfo("Nothing Scanned", "Run a scan first.")
            return

        if percent_value <= 0 or percent_value > 100:
            messagebox.showerror("Invalid Percentage", "Enter a percentage greater than 0 and up to 100.")
            return

        self.current_preview_percent = percent_value
        self.current_preview_label = label_text
        self.update_preview_display()
        self.update_confidence_display()

        total = len(self.eligible_rows)
        target_count = self.get_preview_count(percent_value)

        msg = (
            f"Preview before apply:\n\n"
            f"Scanned pool: {total}\n"
            f"Actors to mark editor-only: {target_count}\n"
            f"Selection mode: {label_text}\n\n"
            f"Continue?"
        )

        if not messagebox.askyesno("Preview Count Check", msg):
            return

        self.set_status(f"Applying editor-only to {label_text} ...")
        self.root.update_idletasks()

        changed = 0
        failed = []

        try:
            step = total / float(target_count)
            chosen_indices = set()

            for i in range(target_count):
                idx = int(round(i * step))
                if idx >= total:
                    idx = total - 1
                chosen_indices.add(idx)

            candidate = 0
            while len(chosen_indices) < target_count and candidate < total:
                chosen_indices.add(candidate)
                candidate += 1

            for index, row in enumerate(self.eligible_rows):
                if index not in chosen_indices:
                    continue

                actor = row["actor"]
                try:
                    set_editor_only_flag(actor, True)
                    row["is_editor_only"] = True
                    changed += 1
                except Exception as e:
                    failed.append((row["label"], str(e)))

            save_current_level()
            self.update_metrics()

            summary = f"Marked editor-only: {changed}\nFailed: {len(failed)}"
            if failed:
                summary += "\n\nFailures:\n" + "\n".join([f"{name} -> {reason}" for name, reason in failed[:20]])

            messagebox.showinfo("Cooker Optimizer Results", summary)
            self.set_status(f"Applied {label_text}. Changed={changed}, Failed={len(failed)}")

        except Exception as e:
            err(f"Apply percentage failed: {e}")
            self.set_status(f"Apply failed: {e}")
            messagebox.showerror("Apply Failed", str(e))

    def apply_fraction(self, divisor: int):
        if divisor <= 0:
            return
        percent_value = 100.0 / float(divisor)
        self._apply_percentage_internal(percent_value, f"1/{divisor}")

    def apply_custom_percentage(self):
        raw = self.custom_percent_var.get().strip()
        try:
            percent_value = float(raw)
        except Exception:
            messagebox.showerror("Invalid Percentage", "Enter a valid number, like 25 or 12.5.")
            return

        self._apply_percentage_internal(percent_value, f"{percent_value:g}%")

    def undo_all(self):
        if not self.eligible_rows:
            messagebox.showinfo("Nothing Scanned", "Run a scan first.")
            return

        msg = (
            f"This will clear the editor-only flag on all {len(self.eligible_rows)} scanned eligible actors.\n\n"
            f"Continue?"
        )

        if not messagebox.askyesno("Confirm Undo", msg):
            return

        self.set_status("Clearing editor-only on all scanned actors ...")
        self.root.update_idletasks()

        changed = 0
        failed = []

        try:
            for row in self.eligible_rows:
                actor = row["actor"]
                try:
                    if get_editor_only_flag(actor):
                        set_editor_only_flag(actor, False)
                        changed += 1
                    row["is_editor_only"] = False
                except Exception as e:
                    failed.append((row["label"], str(e)))

            save_current_level()
            self.update_metrics()

            summary = f"Cleared editor-only: {changed}\nFailed: {len(failed)}"
            if failed:
                summary += "\n\nFailures:\n" + "\n".join([f"{name} -> {reason}" for name, reason in failed[:20]])

            messagebox.showinfo("Undo Results", summary)
            self.set_status(f"Undo complete. Changed={changed}, Failed={len(failed)}")

        except Exception as e:
            err(f"Undo failed: {e}")
            self.set_status(f"Undo failed: {e}")
            messagebox.showerror("Undo Failed", str(e))

    def apply_to_selected(self, enabled: bool):
        action_text = "mark editor-only" if enabled else "clear editor-only"

        try:
            selected_actors = get_selected_level_actors_safe()
        except Exception as e:
            err(f"Failed to get selected actors: {e}")
            messagebox.showerror("Selection Error", str(e))
            return

        if not selected_actors:
            messagebox.showinfo("Nothing Selected", "Select one or more actors in the outliner first.")
            return

        msg = (
            f"This will {action_text} for {len(selected_actors)} currently selected actor(s) "
            f"in the outliner.\n\nContinue?"
        )

        if not messagebox.askyesno("Confirm Selected Actors Change", msg):
            return

        self.set_status(f"Applying selected actor change: {action_text} ...")
        self.root.update_idletasks()

        changed = 0
        failed = []

        for actor in selected_actors:
            try:
                set_editor_only_flag(actor, enabled)
                changed += 1
            except Exception as e:
                failed.append((get_actor_label_safe(actor), str(e)))

        try:
            save_current_level()
        except Exception:
            pass

        if self.eligible_rows:
            for row in self.eligible_rows:
                try:
                    row["is_editor_only"] = get_editor_only_flag(row["actor"])
                except Exception:
                    pass
            self.update_metrics()

        summary = f"Changed selected actors: {changed}\nFailed: {len(failed)}"
        if failed:
            summary += "\n\nFailures:\n" + "\n".join([f"{name} -> {reason}" for name, reason in failed[:20]])

        messagebox.showinfo("Selected Actors Updated", summary)
        self.set_status(f"Selected actor change complete. Changed={changed}, Failed={len(failed)}")


def launch_cooker_optimizer():
    global _COOKER_OPTIMIZER_APP

    try:
        if _COOKER_OPTIMIZER_APP is not None:
            _COOKER_OPTIMIZER_APP.close()
    except Exception:
        pass

    _COOKER_OPTIMIZER_APP = CookerOptimizerApp()
    return _COOKER_OPTIMIZER_APP


launch_cooker_optimizer()