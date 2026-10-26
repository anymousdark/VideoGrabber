#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interface moderna do VideoGrabber (CustomTkinter).

feito por anymousdark
"""

from __future__ import annotations

import os
import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from video_grabber import (
    APP_AUTHOR,
    APP_NAME,
    APP_VERSION,
    AUDIO_FORMATS,
    BROWSERS,
    QUALITY_OPTIONS,
    SUB_LANGS_DEFAULT,
    VIDEO_FORMATS,
    DownloadJob,
    DownloadOptions,
    app_icon_path,
    ffmpeg_path,
    load_settings,
    parse_languages,
    save_settings,
    validate_url,
)

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------
BG = "#0b0d13"
SIDEBAR = "#10131c"
CARD = "#161a25"
CARD2 = "#1e2331"
CARD3 = "#262c3d"
FG = "#f2f4f8"
MUTED = "#8b93a8"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#9277ff"
GREEN = "#22c55e"
GREEN_HOVER = "#34d970"
RED = "#ef4444"
RED_HOVER = "#f87171"
YELLOW = "#f59e0b"
BORDER = "#2a3040"
FONT = "Segoe UI"
MONO = "Consolas"


def _logo_png_path() -> str | None:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for path in (os.path.join(base, "icon.png"), os.path.join(base, "assets", "icon.png")):
        if os.path.isfile(path):
            return path
    return None


class App:
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.events: queue.Queue = queue.Queue()
        self.job = DownloadJob(self.events)
        self.settings = load_settings()
        self.last_dir = self.settings.get("outdir") or os.path.join(os.path.expanduser("~"), "Videos")
        self._logo_img = None

        self._build_vars()
        self._build_ui()
        self._load_settings_into_ui()
        self._toggle_mode()
        self._toggle_playlist()
        self._toggle_subs()
        self._update_link_count()
        self._log(f"{APP_NAME} pronto. Cole um ou mais links e clique em Baixar.")
        self._log("Links diretos de vídeo também são aceitos (MP4, WebM, MKV, MOV, etc.).")
        self.root.after(100, self._poll)

    # ------------------------------------------------------------------ vars
    def _build_vars(self) -> None:
        self.dir_var = tk.StringVar(value=self.last_dir)
        self.mode_var = tk.StringVar(value="Vídeo")
        self.quality_var = tk.StringVar(value="Melhor disponível")
        self.video_format_var = tk.StringVar(value="mp4")
        self.audio_format_var = tk.StringVar(value="mp3")
        self.playlist_var = tk.BooleanVar(value=False)
        self.playlist_items_var = tk.StringVar(value="")
        self.subs_var = tk.BooleanVar(value=True)
        self.subs_langs_var = tk.StringVar(value=SUB_LANGS_DEFAULT)
        self.cookies_var = tk.StringVar(value="Nenhum")
        self.sponsor_var = tk.BooleanVar(value=False)
        self.thumb_var = tk.BooleanVar(value=True)
        self.archive_var = tk.BooleanVar(value=True)
        self.speed_var = tk.StringVar(value="0")
        self.fragments_var = tk.StringVar(value="4")
        self.proxy_var = tk.StringVar(value="")
        self.organize_var = tk.BooleanVar(value=False)

    # --------------------------------------------------------------- widgets
    def _label(self, parent, text, size=11, color=MUTED, bold=False, anchor="w", **kwargs):
        return ctk.CTkLabel(
            parent, text=text, text_color=color, anchor=anchor,
            font=(FONT, size, "bold" if bold else "normal"), **kwargs,
        )

    def _entry(self, parent, variable, width=220, placeholder=""):
        return ctk.CTkEntry(
            parent, textvariable=variable, width=width, height=32,
            corner_radius=8, fg_color=CARD2, border_color=BORDER, border_width=1,
            text_color=FG, placeholder_text=placeholder, placeholder_text_color=MUTED,
            font=(FONT, 11),
        )

    def _option(self, parent, variable, values, width=150):
        return ctk.CTkOptionMenu(
            parent, values=values, variable=variable, width=width, height=32,
            corner_radius=8, fg_color=CARD2, button_color=CARD3,
            button_hover_color=ACCENT, text_color=FG,
            dropdown_fg_color=CARD2, dropdown_hover_color=ACCENT,
            dropdown_text_color=FG, font=(FONT, 11), dropdown_font=(FONT, 11),
            dynamic_resizing=False,
        )

    def _switch(self, parent, text, variable, command=None):
        return ctk.CTkSwitch(
            parent, text=text, variable=variable, onvalue=True, offvalue=False,
            command=command, progress_color=ACCENT, button_color=FG,
            button_hover_color="#ffffff", text_color=FG, font=(FONT, 11),
            switch_width=34, switch_height=17,
        )

    def _button(self, parent, text, command, kind="secondary", width=130, height=32):
        if kind == "primary":
            return ctk.CTkButton(
                parent, text=text, command=command, width=width, height=height,
                corner_radius=10, fg_color=GREEN, hover_color=GREEN_HOVER,
                text_color="#07110a", font=(FONT, 13, "bold"),
            )
        if kind == "accent":
            return ctk.CTkButton(
                parent, text=text, command=command, width=width, height=height,
                corner_radius=9, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                text_color="#ffffff", font=(FONT, 11, "bold"),
            )
        if kind == "danger":
            return ctk.CTkButton(
                parent, text=text, command=command, width=width, height=height,
                corner_radius=10, fg_color=CARD2, hover_color=CARD3,
                border_width=1, border_color=RED, text_color=RED,
                font=(FONT, 12, "bold"),
            )
        return ctk.CTkButton(
            parent, text=text, command=command, width=width, height=height,
            corner_radius=8, fg_color=CARD2, hover_color=CARD3,
            border_width=1, border_color=BORDER, text_color=FG,
            font=(FONT, 11),
        )

    def _card(self, parent):
        return ctk.CTkFrame(
            parent, fg_color=CARD, corner_radius=14,
            border_width=1, border_color=BORDER,
        )

    # ------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self.root.title(f"{APP_NAME} {APP_VERSION} — feito por {APP_AUTHOR}")
        self.root.configure(fg_color=BG)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1120, screen_w - 40)
        height = min(820, screen_h - 80)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 20)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(980, 660)

        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

    # --------------------------------------------------------------- sidebar
    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self.root, width=250, corner_radius=0, fg_color=SIDEBAR)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(8, weight=1)

        # Logo
        logo_row = ctk.CTkFrame(side, fg_color="transparent")
        logo_row.grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 2))
        logo_path = _logo_png_path()
        if logo_path:
            try:
                image = Image.open(logo_path)
                self._logo_img = ctk.CTkImage(light_image=image, dark_image=image, size=(36, 36))
                ctk.CTkLabel(logo_row, image=self._logo_img, text="").pack(side="left")
            except Exception:
                self._label(logo_row, "▶", size=24, color=ACCENT_HOVER).pack(side="left")
        else:
            self._label(logo_row, "▶", size=24, color=ACCENT_HOVER).pack(side="left")
        self._label(logo_row, APP_NAME, size=19, color=FG, bold=True).pack(side="left", padx=(8, 0))

        self._label(
            side, "baixador de vídeos e áudio", size=10, color=MUTED,
        ).grid(row=1, column=0, sticky="w", padx=20)

        # Badge
        badge = ctk.CTkLabel(
            side, text=f"feito por {APP_AUTHOR}", fg_color=ACCENT,
            text_color="#ffffff", corner_radius=7, height=26,
            font=(FONT, 10, "bold"),
        )
        badge.grid(row=2, column=0, sticky="w", padx=18, pady=(12, 14))

        divider = ctk.CTkFrame(side, height=1, fg_color=BORDER, corner_radius=0)
        divider.grid(row=3, column=0, sticky="ew", padx=18)

        # Status
        status_card = ctk.CTkFrame(
            side, fg_color=CARD, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        status_card.grid(row=4, column=0, sticky="ew", padx=14, pady=(16, 12))
        self._label(status_card, "STATUS", size=9, color=MUTED, bold=True).pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        status_row = ctk.CTkFrame(status_card, fg_color="transparent")
        status_row.pack(anchor="w", padx=14)
        self.side_dot = ctk.CTkLabel(status_row, text="●", text_color=GREEN, font=(FONT, 15))
        self.side_dot.pack(side="left")
        self.side_status = self._label(status_row, "Pronto", size=13, color=FG, bold=True)
        self.side_status.pack(side="left", padx=(6, 0))
        self.side_item = self._label(
            status_card, "Nenhum download em andamento", size=10, color=MUTED,
        )
        self.side_item.pack(anchor="w", padx=14, pady=(3, 12))

        # Ações
        self._label(side, "AÇÕES", size=9, color=MUTED, bold=True).grid(
            row=5, column=0, sticky="w", padx=20, pady=(8, 6)
        )
        self._button(
            side, "▣  Abrir pasta", self._open_dir, width=210, height=34
        ).grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 6))
        self._button(
            side, "⌫  Limpar log", self._clear_log, width=210, height=34
        ).grid(row=7, column=0, sticky="ew", padx=14)

        # Rodapé
        footer = ctk.CTkFrame(side, fg_color="transparent")
        footer.grid(row=9, column=0, sticky="ew", padx=18, pady=(0, 18))
        self._label(
            footer, f"© 2026 {APP_AUTHOR}  •  MIT", size=10, color=ACCENT_HOVER, bold=True,
        ).pack(anchor="w")
        self._label(footer, f"v{APP_VERSION}  •  powered by yt-dlp", size=9, color=MUTED).pack(
            anchor="w", pady=(2, 6)
        )
        self._label(
            footer, "Baixe apenas conteúdo\nque você tem direito.", size=9, color=MUTED,
        ).pack(anchor="w")

    # ------------------------------------------------------------------ main
    def _build_main(self) -> None:
        main = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(5, weight=1)

        # Cabeçalho
        head = ctk.CTkFrame(main, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(12, 6))
        head.grid_columnconfigure(0, weight=1)
        title_box = ctk.CTkFrame(head, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")
        self._label(title_box, "Baixar vídeos e áudio", size=24, color=FG, bold=True).pack(anchor="w")
        self._label(
            title_box, "Cole os links, escolha o formato e baixe. Sem limites artificiais.",
            size=11, color=MUTED,
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            head, text="  SEM LIMITES  ", fg_color="#12351f", text_color=GREEN,
            corner_radius=6, height=24, font=(FONT, 9, "bold"),
        ).grid(row=0, column=1, sticky="e")

        # Links
        url_card = self._card(main)
        url_card.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 6))
        url_card.grid_columnconfigure(0, weight=1)

        url_head = ctk.CTkFrame(url_card, fg_color="transparent")
        url_head.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 4))
        self._label(url_head, "LINKS", size=10, color=FG, bold=True).pack(side="left")
        self._label(url_head, "um por linha", size=10, color=MUTED).pack(side="left", padx=(8, 0))
        self.link_count = self._label(url_head, "0 links", size=10, color=MUTED)
        self.link_count.pack(side="right")

        self.url_text = ctk.CTkTextbox(
            url_card, height=52, corner_radius=8, fg_color=CARD2,
            border_width=1, border_color=BORDER, text_color=FG,
            font=(MONO, 11), wrap="none",
        )
        self.url_text.grid(row=1, column=0, sticky="ew", padx=14)
        self.url_placeholder = ctk.CTkLabel(
            self.url_text, text="Cole um ou mais links aqui…",
            text_color=MUTED, fg_color="transparent", font=(FONT, 11),
        )
        self.url_placeholder.place(x=12, y=8)
        self.url_placeholder.bind("<Button-1>", lambda _e: self.url_text.focus_set())
        self.url_text.bind("<Control-Return>", lambda _e: self._start())
        self.url_text.bind("<KeyRelease>", lambda _e: self._update_link_count())
        self.url_text.bind("<<Paste>>", lambda _e: self.root.after(20, self._update_link_count))

        toolbar = ctk.CTkFrame(url_card, fg_color="transparent")
        toolbar.grid(row=2, column=0, sticky="ew", padx=14, pady=(6, 8))
        self._button(toolbar, "Colar", self._paste, width=80, height=30).pack(side="left")
        self._button(toolbar, "Limpar", self._clear_links, width=80, height=30).pack(
            side="left", padx=(6, 0)
        )
        self._label(
            toolbar, "Ctrl+Enter para baixar", size=9, color=MUTED,
        ).pack(side="right")

        # Abas de opções
        self.tabs = ctk.CTkTabview(
            main, height=204, corner_radius=14, fg_color=CARD,
            border_width=1, border_color=BORDER,
            segmented_button_fg_color=CARD2,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
            segmented_button_unselected_color=CARD2,
            segmented_button_unselected_hover_color=CARD3,
            text_color=FG,
        )
        self.tabs.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 6))
        tab_format = self.tabs.add("Formato")
        tab_playlist = self.tabs.add("Playlist")
        tab_net = self.tabs.add("Rede")

        self._build_tab_format(tab_format)
        self._build_tab_playlist(tab_playlist)
        self._build_tab_net(tab_net)

        # Ações
        actions = ctk.CTkFrame(main, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 6))
        self.start_btn = ctk.CTkButton(
            actions, text="↓   Baixar agora", command=self._start,
            height=42, corner_radius=12, fg_color=GREEN, hover_color=GREEN_HOVER,
            text_color="#07110a", font=(FONT, 15, "bold"),
        )
        self.start_btn.pack(side="left", fill="x", expand=True)
        self.cancel_btn = ctk.CTkButton(
            actions, text="■  Cancelar", command=self._cancel, width=150, height=42,
            corner_radius=12, fg_color=CARD2, hover_color=CARD3,
            border_width=1, border_color=BORDER, text_color=MUTED,
            text_color_disabled=MUTED, font=(FONT, 12, "bold"), state="disabled",
        )
        self.cancel_btn.pack(side="left", padx=(10, 0))

        # Progresso
        progress_card = self._card(main)
        progress_card.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 6))
        self.progress = ctk.CTkProgressBar(
            progress_card, height=8, corner_radius=4,
            fg_color=CARD2, progress_color=ACCENT,
        )
        self.progress.pack(fill="x", padx=14, pady=(8, 4))
        self.progress.set(0)
        info = ctk.CTkFrame(progress_card, fg_color="transparent")
        info.pack(fill="x", padx=14, pady=(0, 8))
        self.main_status = self._label(info, "Pronto para baixar.", size=11, color=FG, bold=True)
        self.main_status.pack(side="left")
        self.percent_label = self._label(info, "0%", size=11, color=MUTED, bold=True)
        self.percent_label.pack(side="right")

        # Log
        log_card = self._card(main)
        log_card.grid(row=5, column=0, sticky="nsew", padx=24, pady=(0, 12))
        log_card.grid_columnconfigure(0, weight=1)
        log_card.grid_rowconfigure(1, weight=1)
        log_head = ctk.CTkFrame(log_card, fg_color="transparent")
        log_head.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        self._label(log_head, "LOG", size=10, color=FG, bold=True).pack(side="left")
        self._label(log_head, "detalhes do download", size=9, color=MUTED).pack(
            side="left", padx=(8, 0)
        )
        self.log_box = ctk.CTkTextbox(
            log_card, height=90, corner_radius=8, fg_color="#0d1119", text_color="#c9d3e3",
            font=(MONO, 10), wrap="word", activate_scrollbars=True,
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    # -------------------------------------------------------------- abas
    def _build_tab_format(self, tab) -> None:
        tab.grid_columnconfigure(1, weight=1)

        self._label(tab, "Pasta de saída").grid(row=0, column=0, sticky="w", pady=(6, 0))
        self._entry(tab, self.dir_var, width=420).grid(
            row=0, column=1, sticky="ew", padx=(10, 8), pady=(6, 0)
        )
        self._button(tab, "…", self._choose_dir, width=38, height=32).grid(
            row=0, column=2, sticky="w", pady=(6, 0)
        )

        mode_row = ctk.CTkFrame(tab, fg_color="transparent")
        mode_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._label(mode_row, "Modo").pack(side="left")
        self.mode_seg = ctk.CTkSegmentedButton(
            mode_row, values=["Vídeo", "Áudio"], variable=self.mode_var,
            command=lambda _v: self._toggle_mode(), height=32, corner_radius=8,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
            unselected_color=CARD2, unselected_hover_color=CARD3,
            text_color=FG, font=(FONT, 11, "bold"),
        )
        self.mode_seg.pack(side="left", padx=(8, 18))
        self._label(mode_row, "Qualidade").pack(side="left")
        self.quality_menu = self._option(mode_row, self.quality_var, list(QUALITY_OPTIONS), width=170)
        self.quality_menu.pack(side="left", padx=(8, 0))

        fmt_row = ctk.CTkFrame(tab, fg_color="transparent")
        fmt_row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._label(fmt_row, "Vídeo").pack(side="left")
        self.video_format_menu = self._option(fmt_row, self.video_format_var, VIDEO_FORMATS, width=90)
        self.video_format_menu.pack(side="left", padx=(8, 18))
        self._label(fmt_row, "Áudio").pack(side="left")
        self.audio_format_menu = self._option(fmt_row, self.audio_format_var, AUDIO_FORMATS, width=100)
        self.audio_format_menu.pack(side="left", padx=(8, 0))
        self._switch(fmt_row, "Organizar por canal", self.organize_var).pack(side="right")

    def _build_tab_playlist(self, tab) -> None:
        tab.grid_columnconfigure(1, weight=1)

        playlist_row = ctk.CTkFrame(tab, fg_color="transparent")
        playlist_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._switch(
            playlist_row, "Playlist inteira", self.playlist_var,
            command=self._toggle_playlist,
        ).pack(side="left")
        self._label(playlist_row, "Itens").pack(side="left", padx=(18, 6))
        self.playlist_items_entry = self._entry(
            playlist_row, self.playlist_items_var, width=170, placeholder="1-10,15"
        )
        self.playlist_items_entry.pack(side="left")
        self._label(
            playlist_row, "ex.: 1-10,15", size=9, color=MUTED,
        ).pack(side="left", padx=(8, 0))

        subs_row = ctk.CTkFrame(tab, fg_color="transparent")
        subs_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self._switch(
            subs_row, "Legendas", self.subs_var, command=self._toggle_subs
        ).pack(side="left")
        self._label(subs_row, "Idiomas").pack(side="left", padx=(18, 6))
        self.subs_langs_entry = self._entry(subs_row, self.subs_langs_var, width=210)
        self.subs_langs_entry.pack(side="left")
        self._label(
            subs_row, "pt,en,es…", size=9, color=MUTED,
        ).pack(side="left", padx=(8, 0))

        cookies_row = ctk.CTkFrame(tab, fg_color="transparent")
        cookies_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self._label(cookies_row, "Cookies do navegador").pack(side="left")
        self._option(cookies_row, self.cookies_var, BROWSERS, width=140).pack(
            side="left", padx=(10, 0)
        )
        self._label(
            cookies_row, "para conteúdo que você já acessa", size=9, color=MUTED,
        ).pack(side="left", padx=(12, 0))

    def _build_tab_net(self, tab) -> None:
        tab.grid_columnconfigure(3, weight=1)

        self._label(tab, "Velocidade KB/s").grid(row=0, column=0, sticky="w", pady=(8, 0))
        self._entry(tab, self.speed_var, width=90).grid(
            row=0, column=1, sticky="w", padx=(8, 16), pady=(8, 0)
        )
        self._label(tab, "Fragmentos").grid(row=0, column=2, sticky="w", pady=(8, 0))
        self._entry(tab, self.fragments_var, width=60).grid(
            row=0, column=3, sticky="w", padx=(8, 0), pady=(8, 0)
        )
        self._switch(tab, "SponsorBlock", self.sponsor_var).grid(
            row=0, column=4, sticky="e", padx=(18, 0), pady=(8, 0)
        )

        self._label(tab, "Proxy").grid(row=1, column=0, sticky="w", pady=(12, 0))
        self._entry(tab, self.proxy_var, width=380, placeholder="http://127.0.0.1:8080").grid(
            row=1, column=1, columnspan=3, sticky="ew", padx=(8, 0), pady=(12, 0)
        )

        checks = ctk.CTkFrame(tab, fg_color="transparent")
        checks.grid(row=2, column=0, columnspan=5, sticky="w", pady=(12, 0))
        self._switch(checks, "Thumbnail embutida", self.thumb_var).pack(side="left")
        self._switch(checks, "Histórico (evitar repetir)", self.archive_var).pack(
            side="left", padx=(22, 0)
        )
        self._label(
            checks, "SponsorBlock marca capítulos, não remove o vídeo.", size=9, color=MUTED,
        ).pack(side="left", padx=(22, 0))

    # ------------------------------------------------------------ configurações
    def _load_settings_into_ui(self) -> None:
        s = self.settings
        if s.get("outdir"):
            self.dir_var.set(s["outdir"])
            self.last_dir = s["outdir"]
        self.mode_var.set(s.get("mode", "Vídeo"))
        self.quality_var.set(s.get("quality", "Melhor disponível"))
        self.video_format_var.set(s.get("video_format", "mp4"))
        self.audio_format_var.set(s.get("audio_format", "mp3"))
        self.playlist_var.set(bool(s.get("playlist", False)))
        self.playlist_items_var.set(s.get("playlist_items", ""))
        self.subs_var.set(bool(s.get("subtitles", True)))
        self.subs_langs_var.set(s.get("subtitle_langs", SUB_LANGS_DEFAULT))
        self.cookies_var.set(s.get("cookies", "Nenhum"))
        self.sponsor_var.set(bool(s.get("sponsorblock", False)))
        self.thumb_var.set(bool(s.get("thumbnail", True)))
        self.archive_var.set(bool(s.get("archive", True)))
        self.speed_var.set(str(s.get("speed_limit", "0")))
        self.fragments_var.set(str(s.get("fragments", "4")))
        self.proxy_var.set(s.get("proxy", ""))
        self.organize_var.set(bool(s.get("organize", False)))

    def _collect_settings(self) -> dict:
        return {
            "outdir": self.dir_var.get().strip(),
            "mode": self.mode_var.get(),
            "quality": self.quality_var.get(),
            "video_format": self.video_format_var.get(),
            "audio_format": self.audio_format_var.get(),
            "playlist": self.playlist_var.get(),
            "playlist_items": self.playlist_items_var.get().strip(),
            "subtitles": self.subs_var.get(),
            "subtitle_langs": self.subs_langs_var.get().strip(),
            "cookies": self.cookies_var.get(),
            "sponsorblock": self.sponsor_var.get(),
            "thumbnail": self.thumb_var.get(),
            "archive": self.archive_var.get(),
            "speed_limit": self.speed_var.get().strip(),
            "fragments": self.fragments_var.get().strip(),
            "proxy": self.proxy_var.get().strip(),
            "organize": self.organize_var.get(),
        }

    def _save_settings(self) -> None:
        save_settings(self._collect_settings())

    # -------------------------------------------------------------- ações
    def _toggle_mode(self) -> None:
        audio = self.mode_var.get() == "Áudio"
        self.quality_menu.configure(state="disabled" if audio else "normal")
        self.video_format_menu.configure(state="disabled" if audio else "normal")
        self.audio_format_menu.configure(state="normal" if audio else "disabled")

    def _toggle_playlist(self) -> None:
        self.playlist_items_entry.configure(
            state="normal" if self.playlist_var.get() else "disabled"
        )

    def _toggle_subs(self) -> None:
        self.subs_langs_entry.configure(
            state="normal" if self.subs_var.get() else "disabled"
        )

    def _update_link_count(self) -> None:
        text = self.url_text.get("1.0", "end")
        count = len([line for line in text.splitlines() if line.strip()])
        self.link_count.configure(text=f"{count} link" + ("s" if count != 1 else ""))
        if hasattr(self, "url_placeholder"):
            if count:
                self.url_placeholder.place_forget()
            else:
                self.url_placeholder.place(x=12, y=8)

    def _paste(self) -> None:
        try:
            text = self.root.clipboard_get().strip()
        except tk.TclError:
            return
        if not text:
            return
        current = self.url_text.get("1.0", "end").strip()
        prefix = "\n" if current else ""
        self.url_text.insert("end", prefix + text)
        self._update_link_count()

    def _clear_links(self) -> None:
        self.url_text.delete("1.0", "end")
        self._update_link_count()

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.dir_var.get() or self.last_dir)
        if chosen:
            self.dir_var.set(chosen)
            self.last_dir = chosen

    def _open_dir(self) -> None:
        path = self.dir_var.get().strip()
        if os.path.isdir(path):
            try:
                if hasattr(os, "startfile"):
                    os.startfile(path)  # type: ignore[attr-defined]
                else:
                    import subprocess

                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.Popen([opener, path])
            except OSError as exc:
                messagebox.showerror(APP_NAME, f"Não foi possível abrir a pasta:\n{exc}")
        else:
            messagebox.showwarning(APP_NAME, "A pasta ainda não existe.")

    def _clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _log(self, text: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    @staticmethod
    def _int(value: str, default: int = 0) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    def _set_status(self, text: str, color: str = FG) -> None:
        self.side_status.configure(text=text, text_color=color)
        self.side_dot.configure(text_color=color)

    def _start(self) -> None:
        if self.job.running():
            return

        raw_urls = [line.strip() for line in self.url_text.get("1.0", "end").splitlines() if line.strip()]
        if not raw_urls:
            messagebox.showwarning(APP_NAME, "Cole pelo menos um link.")
            return

        urls: list[str] = []
        invalid: list[str] = []
        for line in raw_urls:
            try:
                urls.append(validate_url(line))
            except ValueError:
                invalid.append(line)
        if invalid:
            preview = "\n".join(invalid[:5])
            messagebox.showerror(
                APP_NAME,
                "Estes links são inválidos (precisam começar com http/https):\n\n" + preview,
            )
            return

        outdir = self.dir_var.get().strip()
        if not outdir:
            messagebox.showwarning(APP_NAME, "Escolha uma pasta de destino.")
            return
        try:
            os.makedirs(outdir, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível criar a pasta:\n{exc}")
            return

        audio_only = self.mode_var.get() == "Áudio"
        if audio_only and not ffmpeg_path():
            messagebox.showerror(
                APP_NAME,
                "Extrair áudio requer FFmpeg. Gere o exe com build_exe.py ou instale o FFmpeg.",
            )
            return

        options = DownloadOptions(
            outdir=outdir,
            video_format=self.video_format_var.get(),
            audio_only=audio_only,
            audio_format=self.audio_format_var.get(),
            max_height=QUALITY_OPTIONS.get(self.quality_var.get()),
            playlist=self.playlist_var.get(),
            playlist_items=self.playlist_items_var.get().strip(),
            subtitles=self.subs_var.get(),
            subtitle_langs=parse_languages(self.subs_langs_var.get()),
            cookies_browser="" if self.cookies_var.get() == "Nenhum" else self.cookies_var.get(),
            sponsorblock=self.sponsor_var.get(),
            embed_thumbnail=self.thumb_var.get(),
            use_archive=self.archive_var.get(),
            speed_limit_kbps=max(0, self._int(self.speed_var.get(), 0)),
            concurrent_fragments=max(1, min(16, self._int(self.fragments_var.get(), 4))),
            proxy=self.proxy_var.get().strip(),
            organize_by_channel=self.organize_var.get(),
        )

        self.last_dir = outdir
        self._save_settings()
        self.progress.set(0)
        self.percent_label.configure(text="0%")
        self.main_status.configure(text="Iniciando…", text_color=FG)
        self._set_status("Iniciando…", ACCENT)
        self.side_item.configure(text="Preparando fila…")
        self.start_btn.configure(state="disabled", fg_color=CARD3)
        self.cancel_btn.configure(state="normal", border_color=RED, text_color=RED)
        self._log("")
        self._log(f">>> {len(urls)} link(s) na fila")

        if not self.job.start(urls, options):
            self.start_btn.configure(state="normal", fg_color=GREEN)
            self.cancel_btn.configure(state="disabled", border_color=BORDER, text_color=MUTED)
            self._set_status("Não iniciou", RED)

    def _cancel(self) -> None:
        if self.job.running():
            self.job.cancel()
            self._set_status("Cancelando…", YELLOW)
            self.main_status.configure(text="Cancelando…")
            self._log("Cancelamento solicitado…")

    # ---------------------------------------------------------- fila de eventos
    def _poll(self) -> None:
        try:
            while True:
                kind, *payload = self.events.get_nowait()
                if kind == "log":
                    self._log(str(payload[0]))
                elif kind == "progress":
                    value = float(payload[0])
                    self.progress.set(value)
                    self.percent_label.configure(text=f"{value * 100:.0f}%")
                    self.main_status.configure(text=str(payload[1]), text_color=FG)
                    self._set_status("Baixando…", ACCENT)
                elif kind == "item":
                    index, total, _url = payload
                    self.side_item.configure(text=f"Item {index} de {total}")
                elif kind == "error":
                    self._log(f"ERRO: {payload[0]}")
                    self.main_status.configure(text="Falhou", text_color=RED)
                    self._set_status("Erro", RED)
                elif kind == "done":
                    ok_count, total = int(payload[0]), int(payload[1])
                    self.start_btn.configure(state="normal", fg_color=GREEN)
                    self.cancel_btn.configure(state="disabled", border_color=BORDER, text_color=MUTED)
                    self.side_item.configure(text="Nenhum download em andamento")
                    if total and ok_count == total:
                        self.progress.set(1)
                        self.percent_label.configure(text="100%")
                        self.main_status.configure(text=f"Concluído: {ok_count}/{total}", text_color=GREEN)
                        self._set_status("Concluído", GREEN)
                    elif ok_count:
                        self.main_status.configure(text=f"Parcial: {ok_count}/{total}", text_color=YELLOW)
                        self._set_status("Parcial", YELLOW)
                    else:
                        self.main_status.configure(text="Nada foi baixado", text_color=RED)
                        self._set_status("Falhou", RED)
                        messagebox.showwarning(
                            APP_NAME,
                            "Nenhum download foi concluído. Veja o log para detalhes.",
                        )
        except queue.Empty:
            pass
        self.root.after(100, self._poll)

    # ---------------------------------------------------------------- fechar
    def on_close(self) -> None:
        if self.job.running():
            if not messagebox.askyesno(APP_NAME, "Há um download em andamento. Cancelar e sair?"):
                return
            self.job.cancel()
        self._save_settings()
        self.root.destroy()


def run_gui() -> int:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")
    root = ctk.CTk()
    icon = app_icon_path()
    if icon:
        try:
            root.iconbitmap(icon)
        except tk.TclError:
            pass
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gui())
