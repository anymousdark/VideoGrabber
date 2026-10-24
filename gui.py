#!/usr/bin/env python3
"""
Interface gráfica do VideoGrabber
Tema escuro moderno, feito por anymousdark
"""

import os
import time
import subprocess
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from config import (
    config,
    load_config_from_file,
    save_config_to_file,
)
import recorder as rec

try:
    import keyboard
except ImportError:
    keyboard = None

try:
    import mss
    import mss.tools
except ImportError:
    mss = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    import cv2
except ImportError:
    cv2 = None


# ---------------------------------------------------------------------------
# Paleta / tema
# ---------------------------------------------------------------------------
BG = "#0e1016"
CARD = "#161a24"
CARD2 = "#1e2331"
CARD3 = "#252b3b"
FG = "#e8ebf3"
MUTED = "#8a93a8"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#957dff"
GREEN = "#22c55e"
GREEN_HOVER = "#34d970"
YELLOW = "#f59e0b"
YELLOW_HOVER = "#fbbf24"
RED = "#ef4444"
RED_HOVER = "#f87171"
BORDER = "#2a3142"

FONT = "Segoe UI"
MONO = "Consolas"

MODES = [
    ("Tela", "screen", "🖥"),
    ("Webcam", "webcam", "🎥"),
    ("Tela + Cam", "both", "🖥🎥"),
    ("Áudio", "audio_only", "🎙"),
]

FORMATS = ["mp4", "avi", "mkv", "webm"]


class VideoGrabberApp:
    def __init__(self):
        load_config_from_file()

        self.root = tk.Tk()
        self.root.title("VideoGrabber — feito por anymousdark")
        self.root.configure(bg=BG)
        self.root.minsize(560, 760)

        width, height = 600, 820
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 20)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.recorder = None
        self.mode = config.recording.mode if config.recording.mode in [m[1] for m in MODES] else "screen"
        self.region = config.recording.region
        self._record_start = 0.0
        self._paused_total = 0.0
        self._pause_start = None
        self._tick_job = None
        self._blink_job = None
        self._blink_on = False
        self._stopping = False
        self._last_output = None
        self._hotkeys_registered = False

        self._build_style()
        self._build_ui()
        self._apply_config_to_ui()
        self._select_mode(self.mode, silent=True)
        self._register_hotkeys()
        self._update_region_label()
        self._set_ui_state("idle")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ tema
    def _build_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Dark.TCombobox",
            fieldbackground=CARD2,
            background=CARD2,
            foreground=FG,
            arrowcolor=FG,
            bordercolor=BORDER,
            lightcolor=CARD2,
            darkcolor=CARD2,
            padding=6,
        )
        style.map(
            "Dark.TCombobox",
            fieldbackground=[("readonly", CARD2)],
            foreground=[("readonly", FG)],
            bordercolor=[("focus", ACCENT)],
        )

        self.root.option_add("*TCombobox*Listbox.background", CARD2)
        self.root.option_add("*TCombobox*Listbox.foreground", FG)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    # ------------------------------------------------------------------- UI
    def _card(self, parent):
        outer = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill="both", expand=True, padx=16, pady=14)
        return outer, inner

    def _label(self, parent, text, size=10, color=FG, bold=False, bg=CARD):
        return tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=color,
            font=(FONT, size, "bold" if bold else "normal"),
            anchor="w",
        )

    def _build_ui(self):
        root = self.root

        # ---------------- Cabeçalho ----------------
        header = tk.Frame(root, bg=BG)
        header.pack(fill="x", padx=22, pady=(18, 10))

        left = tk.Frame(header, bg=BG)
        left.pack(side="left", fill="x", expand=True)

        tk.Label(
            left,
            text="🎥  VideoGrabber",
            bg=BG,
            fg=FG,
            font=(FONT, 21, "bold"),
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            left,
            text="Grave tela, webcam e áudio — sem limites",
            bg=BG,
            fg=MUTED,
            font=(FONT, 10),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        badge = tk.Label(
            header,
            text="feito por anymousdark",
            bg=CARD2,
            fg=ACCENT_HOVER,
            font=(FONT, 9, "bold"),
            padx=12,
            pady=6,
        )
        badge.pack(side="right", anchor="n")

        # ---------------- Seletor de modo ----------------
        mode_wrap, mode_inner = self._card(root)
        mode_wrap.pack(fill="x", padx=22, pady=(6, 10))

        self._label(mode_inner, "MODO DE GRAVAÇÃO", size=8, color=MUTED, bold=True).pack(anchor="w", pady=(0, 8))

        mode_row = tk.Frame(mode_inner, bg=CARD)
        mode_row.pack(fill="x")

        self.mode_buttons = {}
        for idx, (label, value, icon) in enumerate(MODES):
            btn = tk.Button(
                mode_row,
                text=f"{icon}\n{label}",
                bg=CARD2,
                fg=MUTED,
                activebackground=CARD3,
                activeforeground=FG,
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=BORDER,
                highlightcolor=ACCENT,
                font=(FONT, 9, "bold"),
                cursor="hand2",
                padx=4,
                pady=8,
                command=lambda v=value: self._select_mode(v),
            )
            btn.grid(row=0, column=idx, sticky="nsew", padx=(0 if idx == 0 else 6, 0))
            mode_row.grid_columnconfigure(idx, weight=1)
            self.mode_buttons[value] = btn

        # ---------------- Configurações ----------------
        settings_wrap, s = self._card(root)
        settings_wrap.pack(fill="x", padx=22, pady=(0, 10))

        self._label(s, "CONFIGURAÇÕES", size=8, color=MUTED, bold=True).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10)
        )

        # Pasta de saída
        self._label(s, "Pasta de saída", size=9, color=MUTED).grid(row=1, column=0, sticky="w", pady=4)
        self.folder_var = tk.StringVar()
        folder_entry = tk.Entry(
            s,
            textvariable=self.folder_var,
            bg=CARD2,
            fg=FG,
            insertbackground=FG,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=(FONT, 9),
        )
        folder_entry.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(8, 6), pady=4, ipady=5)

        browse_btn = tk.Button(
            s,
            text="…",
            bg=CARD3,
            fg=FG,
            activebackground=ACCENT,
            activeforeground="#fff",
            relief="flat",
            bd=0,
            font=(FONT, 10, "bold"),
            cursor="hand2",
            width=3,
            command=self._browse_folder,
        )
        browse_btn.grid(row=1, column=3, sticky="ew", pady=4)

        # Formato / FPS / Qualidade
        self._label(s, "Formato", size=9, color=MUTED).grid(row=2, column=0, sticky="w", pady=4)
        self.format_var = tk.StringVar(value=config.video.output_format)
        fmt = ttk.Combobox(
            s,
            textvariable=self.format_var,
            values=FORMATS,
            state="readonly",
            style="Dark.TCombobox",
            width=8,
            font=(FONT, 9),
        )
        fmt.grid(row=2, column=1, sticky="ew", padx=(8, 6), pady=4)

        fps_wrap = tk.Frame(s, bg=CARD)
        fps_wrap.grid(row=2, column=2, columnspan=2, sticky="ew", padx=(8, 0), pady=4)
        self._label(fps_wrap, "FPS", size=9, color=MUTED).pack(side="left")
        self.fps_var = tk.StringVar(value=str(config.video.fps))
        fps = tk.Spinbox(
            fps_wrap,
            from_=1,
            to=120,
            textvariable=self.fps_var,
            width=5,
            bg=CARD2,
            fg=FG,
            buttonbackground=CARD3,
            insertbackground=FG,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=(FONT, 9),
            justify="center",
        )
        fps.pack(side="left", padx=(8, 10), ipady=3)

        self._label(fps_wrap, "Câmera", size=9, color=MUTED).pack(side="left")
        self.cam_var = tk.StringVar(value=str(config.webcam.device_id))
        cam = tk.Spinbox(
            fps_wrap,
            from_=0,
            to=9,
            textvariable=self.cam_var,
            width=4,
            bg=CARD2,
            fg=FG,
            buttonbackground=CARD3,
            insertbackground=FG,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=(FONT, 9),
            justify="center",
        )
        cam.pack(side="left", padx=(8, 0), ipady=3)

        # Qualidade
        self._label(s, "Qualidade", size=9, color=MUTED).grid(row=3, column=0, sticky="w", pady=4)
        self.quality_var = tk.IntVar(value=config.video.quality)
        quality = tk.Scale(
            s,
            from_=10,
            to=100,
            orient="horizontal",
            variable=self.quality_var,
            bg=CARD,
            fg=FG,
            troughcolor=CARD2,
            highlightthickness=0,
            sliderrelief="flat",
            activebackground=ACCENT,
            font=(FONT, 8),
            showvalue=True,
            bd=0,
        )
        quality.grid(row=3, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=2)

        # Limites
        limits = tk.Frame(s, bg=CARD)
        limits.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(6, 2))

        self._label(limits, "Limite (min)", size=9, color=MUTED).pack(side="left")
        self.limit_var = tk.StringVar(value=str(max(0, config.recording.time_limit // 60)))
        limit = tk.Spinbox(
            limits,
            from_=0,
            to=999,
            textvariable=self.limit_var,
            width=5,
            bg=CARD2,
            fg=FG,
            buttonbackground=CARD3,
            insertbackground=FG,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=(FONT, 9),
            justify="center",
        )
        limit.pack(side="left", padx=(8, 16), ipady=3)

        self._label(limits, "Limite (MB)", size=9, color=MUTED).pack(side="left")
        self.sizelimit_var = tk.StringVar(value=str(max(0, config.recording.size_limit_mb)))
        sizelimit = tk.Spinbox(
            limits,
            from_=0,
            to=99999,
            textvariable=self.sizelimit_var,
            width=7,
            bg=CARD2,
            fg=FG,
            buttonbackground=CARD3,
            insertbackground=FG,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            font=(FONT, 9),
            justify="center",
        )
        sizelimit.pack(side="left", padx=(8, 0), ipady=3)

        # Checkboxes
        checks = tk.Frame(s, bg=CARD)
        checks.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(8, 2))

        self.mic_var = tk.BooleanVar(value=config.audio.record_microphone)
        self.sys_var = tk.BooleanVar(value=config.audio.record_system_audio)
        self.cursor_var = tk.BooleanVar(value=config.video.show_cursor)
        self.pip_var = tk.BooleanVar(value=config.webcam.show_in_recording)

        for text, var in [
            ("Microfone", self.mic_var),
            ("Áudio do sistema", self.sys_var),
            ("Mostrar cursor", self.cursor_var),
            ("Webcam PiP", self.pip_var),
        ]:
            cb = tk.Checkbutton(
                checks,
                text=text,
                variable=var,
                bg=CARD,
                fg=FG,
                activebackground=CARD,
                activeforeground=FG,
                selectcolor=CARD2,
                highlightthickness=0,
                bd=0,
                font=(FONT, 9),
                cursor="hand2",
            )
            cb.pack(side="left", padx=(0, 14))

        # Região
        region_row = tk.Frame(s, bg=CARD)
        region_row.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(8, 0))

        self.region_var = tk.StringVar(value="Tela inteira")
        self._label(region_row, "Região:", size=9, color=MUTED).pack(side="left")
        tk.Label(
            region_row,
            textvariable=self.region_var,
            bg=CARD,
            fg=FG,
            font=(FONT, 9),
        ).pack(side="left", padx=(6, 10))

        self._ghost_button(region_row, "Selecionar", self._select_region, width=10).pack(side="left")
        self._ghost_button(region_row, "Limpar", self._clear_region, width=8).pack(side="left", padx=(6, 0))
        self._ghost_button(region_row, "Prévia webcam", self._preview_webcam, width=14).pack(side="right")

        s.grid_columnconfigure(1, weight=1)
        s.grid_columnconfigure(2, weight=1)
        s.grid_columnconfigure(3, weight=0)

        # ---------------- Status ----------------
        status_wrap, st = self._card(root)
        status_wrap.pack(fill="x", padx=22, pady=(0, 10))

        status_top = tk.Frame(st, bg=CARD)
        status_top.pack(fill="x")

        self.dot = tk.Canvas(status_top, width=14, height=14, bg=CARD, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 10))
        self._dot_id = self.dot.create_oval(2, 2, 12, 12, fill=MUTED, outline="")

        self.state_label = tk.Label(
            status_top,
            text="Pronto para gravar",
            bg=CARD,
            fg=FG,
            font=(FONT, 10, "bold"),
            anchor="w",
        )
        self.state_label.pack(side="left")

        self.timer_label = tk.Label(
            st,
            text="00:00:00",
            bg=CARD,
            fg=FG,
            font=(MONO, 34, "bold"),
            anchor="w",
        )
        self.timer_label.pack(anchor="w", pady=(6, 0))

        self.detail_label = tk.Label(
            st,
            text="Nenhuma gravação em andamento",
            bg=CARD,
            fg=MUTED,
            font=(FONT, 9),
            anchor="w",
        )
        self.detail_label.pack(anchor="w", pady=(2, 0))

        # ---------------- Botões ----------------
        actions = tk.Frame(root, bg=BG)
        actions.pack(fill="x", padx=22, pady=(0, 8))

        self.start_btn = self._solid_button(
            actions, "●  Iniciar gravação", GREEN, GREEN_HOVER,
            self._start_recording, height=2, font_size=11
        )
        self.start_btn.pack(side="left", fill="x", expand=True)

        self.pause_btn = self._solid_button(
            actions, "⏸  Pausar", YELLOW, YELLOW_HOVER,
            self._toggle_pause, height=2, font_size=10
        )
        self.pause_btn.pack(side="left", fill="x", expand=True, padx=(8, 0))

        self.stop_btn = self._solid_button(
            actions, "■  Parar", RED, RED_HOVER,
            self._stop_recording, height=2, font_size=10
        )
        self.stop_btn.pack(side="left", fill="x", expand=True, padx=(8, 0))

        secondary = tk.Frame(root, bg=BG)
        secondary.pack(fill="x", padx=22, pady=(0, 8))

        self._ghost_button(secondary, "📁  Abrir pasta", self._open_folder).pack(side="left")
        self._ghost_button(secondary, "📸  Screenshot", self._screenshot).pack(side="left", padx=(8, 0))
        self._ghost_button(secondary, "🗑  Limpar status", self._clear_status).pack(side="right")

        # ---------------- Rodapé ----------------
        footer = tk.Frame(root, bg=BG)
        footer.pack(side="bottom", fill="x", padx=22, pady=(0, 14))

        tk.Label(
            footer,
            text="F9 iniciar/parar  •  F10 pausar  •  F11 screenshot  •  F12 ocultar",
            bg=BG,
            fg=MUTED,
            font=(FONT, 8),
            anchor="w",
        ).pack(side="left")

        tk.Label(
            footer,
            text="v1.0",
            bg=BG,
            fg=MUTED,
            font=(FONT, 8),
        ).pack(side="right")

    # ------------------------------------------------------------- widgets
    def _solid_button(self, parent, text, color, hover, command, height=1, font_size=10):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="#08110a" if color == GREEN else "#111111",
            activebackground=hover,
            activeforeground="#111111",
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(FONT, font_size, "bold"),
            cursor="hand2",
            pady=6 if height == 1 else 10,
        )
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover) if btn["state"] != "disabled" else None)
        btn.bind("<Leave>", lambda e: btn.configure(bg=color) if btn["state"] != "disabled" else None)
        btn._normal_bg = color
        btn._hover_bg = hover
        return btn

    def _ghost_button(self, parent, text, command, width=None):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=CARD2,
            fg=FG,
            activebackground=CARD3,
            activeforeground=FG,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=BORDER,
            font=(FONT, 9, "bold"),
            cursor="hand2",
            padx=10,
            pady=6,
            width=width,
        )
        btn.bind("<Enter>", lambda e: btn.configure(bg=CARD3))
        btn.bind("<Leave>", lambda e: btn.configure(bg=CARD2))
        return btn

    # ------------------------------------------------------------ config
    def _apply_config_to_ui(self):
        self.folder_var.set(config.recording.output_dir)
        self.format_var.set(config.video.output_format)
        self.fps_var.set(str(config.video.fps))
        self.cam_var.set(str(config.webcam.device_id))
        self.quality_var.set(config.video.quality)
        self.limit_var.set(str(max(0, config.recording.time_limit // 60)))
        self.sizelimit_var.set(str(max(0, config.recording.size_limit_mb)))

    def _sync_config_from_ui(self):
        config.recording.output_dir = self.folder_var.get().strip() or config.recording.output_dir
        config.recording.mode = self.mode
        config.video.output_format = self.format_var.get()
        config.video.fps = max(1, int(self._safe_int(self.fps_var.get(), 30)))
        config.video.quality = int(self.quality_var.get())
        config.webcam.device_id = max(0, int(self._safe_int(self.cam_var.get(), 0)))
        config.audio.record_microphone = bool(self.mic_var.get())
        config.audio.record_system_audio = bool(self.sys_var.get())
        config.video.show_cursor = bool(self.cursor_var.get())
        config.webcam.show_in_recording = bool(self.pip_var.get())
        config.recording.time_limit = max(0, self._safe_int(self.limit_var.get(), 0)) * 60
        config.recording.size_limit_mb = max(0, self._safe_int(self.sizelimit_var.get(), 0))
        config.recording.region = self.region

    @staticmethod
    def _safe_int(value, default=0):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    # ------------------------------------------------------------- modos
    def _select_mode(self, mode, silent=False):
        self.mode = mode
        for value, btn in self.mode_buttons.items():
            if value == mode:
                btn.configure(bg=ACCENT, fg="#ffffff", highlightbackground=ACCENT)
            else:
                btn.configure(bg=CARD2, fg=MUTED, highlightbackground=BORDER)

        # Ajustes visuais por modo
        if mode == "audio_only":
            self.pip_var.set(False)
        elif mode in ("screen", "both"):
            self.pip_var.set(config.webcam.show_in_recording)

        if not silent:
            labels = {
                "screen": "Pronto para gravar a tela",
                "webcam": "Pronto para gravar a webcam",
                "both": "Pronto para gravar tela + webcam",
                "audio_only": "Pronto para gravar áudio",
            }
            self.state_label.configure(text="Pronto para gravar")
            self.detail_label.configure(text=labels.get(mode, "Pronto para gravar"))

    # ------------------------------------------------------------ pasta
    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.folder_var.get() or os.path.expanduser("~"))
        if folder:
            self.folder_var.set(folder)

    def _open_folder(self):
        folder = self.folder_var.get().strip()
        if not os.path.isdir(folder):
            messagebox.showwarning("Pasta inválida", "A pasta de saída não existe.")
            return
        try:
            os.startfile(folder)
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível abrir a pasta:\n{e}")

    # ------------------------------------------------------------ região
    def _update_region_label(self):
        if self.region:
            x, y, w, h = self.region
            self.region_var.set(f"{w}x{h} em ({x}, {y})")
        else:
            self.region_var.set("Tela inteira")

    def _clear_region(self):
        self.region = None
        config.recording.region = None
        self._update_region_label()

    def _select_region(self):
        top = tk.Toplevel(self.root)
        top.attributes("-fullscreen", True)
        top.attributes("-alpha", 0.35)
        top.attributes("-topmost", True)
        top.configure(bg="#000000")
        top.title("Selecione a região")

        canvas = tk.Canvas(top, bg="#000000", cursor="cross", highlightthickness=0)
        canvas.pack(fill="both", expand=True)

        hint = tk.Label(
            top,
            text="Arraste para selecionar a região  •  ESC para cancelar",
            bg="#000000",
            fg="#ffffff",
            font=(FONT, 14, "bold"),
        )
        hint.place(relx=0.5, y=30, anchor="n")

        start = {"x": 0, "y": 0}
        rect_id = {"id": None}

        def on_press(event):
            start["x"], start["y"] = event.x_root, event.y_root
            if rect_id["id"]:
                canvas.delete(rect_id["id"])
            rect_id["id"] = canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline=ACCENT_HOVER, width=3, fill=ACCENT
            )

        def on_drag(event):
            if rect_id["id"]:
                canvas.coords(rect_id["id"], start["x"], start["y"], event.x_root, event.y_root)

        def on_release(event):
            x1, y1 = start["x"], start["y"]
            x2, y2 = event.x_root, event.y_root
            x, y = min(x1, x2), min(y1, y2)
            w, h = abs(x2 - x1), abs(y2 - y1)
            top.destroy()
            if w >= 16 and h >= 16:
                self.region = (x, y, w, h)
                config.recording.region = self.region
                self._update_region_label()
                self.detail_label.configure(text=f"Região definida: {w}x{h} em ({x}, {y})")

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)
        top.bind("<Escape>", lambda e: top.destroy())

    # ----------------------------------------------------------- webcam
    def _preview_webcam(self):
        if cv2 is None or Image is None:
            messagebox.showerror(
                "Dependência ausente",
                "Instale opencv-python e pillow para ver a prévia da webcam.",
            )
            return

        device = max(0, self._safe_int(self.cam_var.get(), 0))
        cap = cv2.VideoCapture(device)
        if not cap.isOpened():
            cap.release()
            messagebox.showerror("Webcam", f"Não foi possível abrir a câmera {device}.")
            return

        win = tk.Toplevel(self.root)
        win.title("Prévia da webcam")
        win.configure(bg=BG)
        win.attributes("-topmost", True)

        header = tk.Frame(win, bg=BG)
        header.pack(fill="x", padx=12, pady=(10, 4))
        tk.Label(
            header, text=f"🎥  Câmera {device}", bg=BG, fg=FG,
            font=(FONT, 11, "bold")
        ).pack(side="left")

        video_label = tk.Label(win, bg="#000000", width=520, height=300)
        video_label.pack(padx=12, pady=(4, 12))

        running = {"value": True}

        def update_frame():
            if not running["value"]:
                return
            ok, frame = cap.read()
            if ok:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img.thumbnail((520, 300))
                photo = ImageTk.PhotoImage(img)
                video_label.configure(image=photo)
                video_label.image = photo
            win.after(33, update_frame)

        def close():
            running["value"] = False
            cap.release()
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close)
        win.after(0, update_frame)

    # ------------------------------------------------------- gravação
    def _validate(self):
        if self.mode in ("screen", "both") and mss is None:
            messagebox.showerror("Dependência ausente", "Instale a biblioteca 'mss'.")
            return False
        if self.mode in ("webcam", "both") and cv2 is None:
            messagebox.showerror("Dependência ausente", "Instale a biblioteca 'opencv-python'.")
            return False
        if self.mode == "audio_only" and not (self.mic_var.get() or self.sys_var.get()):
            messagebox.showwarning("Áudio", "Selecione microfone e/ou áudio do sistema.")
            return False
        if (self.mic_var.get() or self.sys_var.get()) and rec.PYAUDIO_AVAILABLE is False:
            messagebox.showerror("Dependência ausente", "Instale a biblioteca 'pyaudio' para gravar áudio.")
            return False
        folder = self.folder_var.get().strip()
        if not folder:
            messagebox.showwarning("Pasta", "Escolha uma pasta de saída.")
            return False
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Pasta", f"Não foi possível criar a pasta:\n{e}")
            return False
        return True

    def _build_output_path(self):
        folder = self.folder_var.get().strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = "wav" if self.mode == "audio_only" else self.format_var.get()
        name = f"VideoGrabber_{timestamp}.{ext}"
        return os.path.join(folder, name)

    def _start_recording(self):
        if self.recorder is not None:
            return
        if not self._validate():
            return

        self._sync_config_from_ui()
        output_path = self._build_output_path()

        self.recorder = rec.VideoGrabberRecorder()
        self.recorder.on_state_change = self._on_state_change
        self.recorder.on_error = self._on_error
        self.recorder.on_finished = self._on_finished

        ok = self.recorder.start(self.mode, output_path)
        if not ok:
            self.recorder = None
            messagebox.showerror("Erro", "Não foi possível iniciar a gravação. Verifique as dependências.")
            return

        self._record_start = time.time()
        self._paused_total = 0.0
        self._pause_start = None
        self._stopping = False
        self._last_output = output_path

        self._set_ui_state("recording")
        self.state_label.configure(text="Gravando…")
        self.detail_label.configure(text="Salvando em: " + os.path.basename(output_path))
        self._start_timer()
        self._start_blink()
        self._beep(880, 120)

    def _toggle_pause(self):
        if self.recorder is None:
            return
        if self.recorder.is_paused():
            self.recorder.resume()
            if self._pause_start is not None:
                self._paused_total += time.time() - self._pause_start
                self._pause_start = None
            self._set_ui_state("recording")
            self.state_label.configure(text="Gravando…")
        else:
            self.recorder.pause()
            self._pause_start = time.time()
            self._set_ui_state("paused")
            self.state_label.configure(text="Pausado")
        self._update_timer()

    def _stop_recording(self):
        if self.recorder is None or self._stopping:
            return
        self._stopping = True
        self.state_label.configure(text="Finalizando…")
        self.detail_label.configure(text="Salvando arquivo, aguarde…")
        self.root.update_idletasks()

        output = self.recorder.stop()
        self.recorder = None
        self._stopping = False
        self._stop_timer()
        self._stop_blink()
        self._set_ui_state("idle")
        self._beep(440, 140)

        if output and os.path.exists(output):
            size_mb = os.path.getsize(output) / (1024 * 1024)
            self.state_label.configure(text="Gravação concluída")
            self.detail_label.configure(text=f"{os.path.basename(output)}  •  {size_mb:.1f} MB  •  salvo em {os.path.dirname(output)}")
            self._last_output = output
        else:
            self.state_label.configure(text="Nada foi salvo")
            self.detail_label.configure(text="A gravação não gerou um arquivo válido.")

    def _on_state_change(self, state):
        self.root.after(0, lambda: self._sync_state(state))

    def _sync_state(self, state):
        if state == rec.RecordingState.PAUSED:
            self._set_ui_state("paused")
        elif state == rec.RecordingState.IDLE:
            self._set_ui_state("idle")
        elif state == rec.RecordingState.RECORDING:
            self._set_ui_state("recording")

    def _on_error(self, message):
        self.root.after(0, lambda: self._show_error(message))

    def _show_error(self, message):
        self.detail_label.configure(text=message)
        # Se a gravação continua (ex.: falha só do áudio), não derruba a UI
        if self.recorder is not None and self.recorder.is_recording():
            return
        self.state_label.configure(text="Erro")
        self._set_ui_state("idle")
        self._stop_timer()
        self._stop_blink()

    def _on_finished(self, path):
        self._last_output = path

    # ------------------------------------------------------------- timer
    def _elapsed(self):
        if not self._record_start:
            return 0.0
        elapsed = time.time() - self._record_start - self._paused_total
        if self._pause_start is not None:
            elapsed -= time.time() - self._pause_start
        return max(0.0, elapsed)

    def _start_timer(self):
        self._stop_timer()
        self.timer_label.configure(text="00:00:00")
        self._tick()

    def _stop_timer(self):
        if self._tick_job:
            try:
                self.root.after_cancel(self._tick_job)
            except tk.TclError:
                pass
            self._tick_job = None

    def _tick(self):
        if self.recorder is None:
            return
        self._update_timer()
        self._check_limits()
        self._tick_job = self.root.after(250, self._tick)

    def _update_timer(self):
        elapsed = int(self._elapsed())
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.timer_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

        frames = 0
        try:
            stats = self.recorder.get_stats() if self.recorder else {}
            frames = stats.get("video_frames", 0)
        except Exception:
            pass

        size_mb = 0.0
        try:
            if self.recorder and self.recorder.video_output_path and os.path.exists(self.recorder.video_output_path):
                size_mb = os.path.getsize(self.recorder.video_output_path) / (1024 * 1024)
        except OSError:
            pass

        self.detail_label.configure(text=f"{frames} frames  •  {size_mb:.1f} MB  •  {self.mode}")

    def _check_limits(self):
        limit_s = config.recording.time_limit
        if limit_s and self._elapsed() >= limit_s:
            self._stop_recording()
            return

        limit_mb = config.recording.size_limit_mb
        if limit_mb and self.recorder and self.recorder.video_output_path:
            try:
                if os.path.exists(self.recorder.video_output_path):
                    size_mb = os.path.getsize(self.recorder.video_output_path) / (1024 * 1024)
                    if size_mb >= limit_mb:
                        self._stop_recording()
            except OSError:
                pass

    # ---------------------------------------------------------- blink
    def _start_blink(self):
        self._stop_blink()
        self._blink()

    def _stop_blink(self):
        if self._blink_job:
            try:
                self.root.after_cancel(self._blink_job)
            except tk.TclError:
                pass
            self._blink_job = None
        self._set_dot(MUTED)

    def _blink(self):
        if self.recorder is None:
            return
        if self.recorder.is_paused():
            self._set_dot(YELLOW)
            self._blink_job = self.root.after(500, self._blink)
            return
        self._blink_on = not self._blink_on
        self._set_dot(RED if self._blink_on else "#5a1b1b")
        self._blink_job = self.root.after(500, self._blink)

    def _set_dot(self, color):
        try:
            self.dot.itemconfigure(self._dot_id, fill=color)
        except tk.TclError:
            pass

    # ------------------------------------------------------ estado da UI
    def _set_ui_state(self, state):
        if state == "recording":
            self.start_btn.configure(state="disabled", bg=CARD3, text="●  Gravando…")
            self.pause_btn.configure(state="normal", bg=YELLOW, text="⏸  Pausar")
            self.stop_btn.configure(state="normal", bg=RED)
            self._set_dot(GREEN)
        elif state == "paused":
            self.start_btn.configure(state="disabled", bg=CARD3, text="●  Gravando…")
            self.pause_btn.configure(state="normal", bg=GREEN, text="▶  Retomar")
            self.stop_btn.configure(state="normal", bg=RED)
            self._set_dot(YELLOW)
        else:
            self.start_btn.configure(state="normal", bg=GREEN, text="●  Iniciar gravação")
            self.pause_btn.configure(state="disabled", bg=CARD3, text="⏸  Pausar")
            self.stop_btn.configure(state="disabled", bg=CARD3)
            self._set_dot(MUTED)
            if self.timer_label.cget("text") == "":
                self.timer_label.configure(text="00:00:00")

    def _clear_status(self):
        if self.recorder is not None:
            return
        self.timer_label.configure(text="00:00:00")
        self.state_label.configure(text="Pronto para gravar")
        self.detail_label.configure(text="Nenhuma gravação em andamento")

    # -------------------------------------------------------- screenshot
    def _screenshot(self):
        if mss is None:
            messagebox.showerror("Dependência ausente", "Instale a biblioteca 'mss'.")
            return
        folder = self.folder_var.get().strip() or config.recording.output_dir
        os.makedirs(folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"VideoGrabber_screenshot_{timestamp}.png")
        try:
            with mss.mss() as sct:
                monitor = self.region if self.region else sct.monitors[1]
                if isinstance(monitor, tuple):
                    x, y, w, h = monitor
                    monitor = {"left": x, "top": y, "width": w, "height": h}
                shot = sct.grab(monitor)
                mss.tools.to_png(shot.rgb, shot.size, output=path)
            self.detail_label.configure(text=f"Screenshot salvo: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Screenshot", f"Erro ao capturar:\n{e}")

    # ------------------------------------------------------------ beep
    @staticmethod
    def _beep(freq, duration):
        try:
            import winsound
            winsound.Beep(freq, duration)
        except Exception:
            pass

    # ---------------------------------------------------------- hotkeys
    def _register_hotkeys(self):
        if keyboard is None:
            return
        try:
            keyboard.add_hotkey("f9", lambda: self.root.after(0, self._hotkey_toggle))
            keyboard.add_hotkey("f10", lambda: self.root.after(0, self._toggle_pause))
            keyboard.add_hotkey("f11", lambda: self.root.after(0, self._screenshot))
            keyboard.add_hotkey("f12", lambda: self.root.after(0, self._toggle_window))
            self._hotkeys_registered = True
        except Exception:
            self._hotkeys_registered = False

    def _hotkey_toggle(self):
        if self.recorder is None:
            self._start_recording()
        else:
            self._stop_recording()

    def _toggle_window(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.root.lift()
        else:
            self.root.withdraw()

    # ----------------------------------------------------------- fechar
    def _on_close(self):
        if self.recorder is not None:
            if not messagebox.askyesno("Gravação em andamento", "Parar a gravação e sair?"):
                return
            self._stop_recording()

        try:
            self._sync_config_from_ui()
            save_config_to_file()
        except Exception:
            pass

        if keyboard is not None and self._hotkeys_registered:
            try:
                keyboard.unhook_all_hotkeys()
            except Exception:
                pass

        self.root.destroy()

    # -------------------------------------------------------------- run
    def run(self):
        self.root.mainloop()
