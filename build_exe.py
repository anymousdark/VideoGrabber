#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o VideoGrabber.exe com PyInstaller, embutindo o FFmpeg.

feito por anymousdark
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(HERE, "video_grabber.py")
NAME = "VideoGrabber"
VERSION = "2.0.0"


def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=HERE)


def find_ffmpeg() -> str:
    env = (os.environ.get("FFMPEG_EXE") or "").strip('"')
    if env and os.path.isfile(env):
        return env

    which = shutil.which("ffmpeg")
    if which:
        return which

    try:
        import imageio_ffmpeg

        path = imageio_ffmpeg.get_ffmpeg_exe()
        if os.path.isfile(path):
            return path
    except Exception:
        pass

    raise SystemExit(
        "ffmpeg não encontrado. Instale com: pip install imageio-ffmpeg\n"
        "ou defina FFMPEG_EXE=C:\\caminho\\ffmpeg.exe"
    )


def main() -> int:
    print("=" * 64)
    print(f"  {NAME} v{VERSION} — build do executável")
    print("  feito por anymousdark")
    print("=" * 64)

    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    ffmpeg = find_ffmpeg()
    print(f"ffmpeg embutido: {ffmpeg}")

    sep = ";" if os.name == "nt" else ":"
    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", NAME,
        "--collect-submodules", "yt_dlp",
        "--collect-submodules", "imageio_ffmpeg",
        "--collect-all", "customtkinter",
        "--hidden-import", "imageio_ffmpeg",
        "--hidden-import", "app_ui",
        "--hidden-import", "PIL._tkinter_finder",
    ]

    icon = os.path.join(HERE, "assets", "icon.ico")
    if os.path.isfile(icon):
        args += ["--icon", icon, "--add-data", f"{icon}{sep}."]

    icon_png = os.path.join(HERE, "assets", "icon.png")
    if os.path.isfile(icon_png):
        args += ["--add-data", f"{icon_png}{sep}."]

    args.append(ENTRY)
    run(args)

    exe = os.path.join(HERE, "dist", f"{NAME}.exe")
    if os.path.isfile(exe):
        release_dir = os.path.join(HERE, "release")
        os.makedirs(release_dir, exist_ok=True)
        target = os.path.join(release_dir, f"{NAME}.exe")
        shutil.copy2(exe, target)
        size = os.path.getsize(target) / (1024 * 1024)
        print(f"\nOK: {target}  ({size:.1f} MB)")
        return 0

    print("\nFalhou: executável não gerado.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
