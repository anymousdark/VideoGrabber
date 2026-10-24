#!/usr/bin/env python3
"""
Gera o executável do VideoGrabber com PyInstaller.
Uso: python build_exe.py
Resultado: dist/VideoGrabber.exe
"""

import os
import shutil
import subprocess
import sys


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    icon = os.path.join(root, "assets", "icon.ico")
    icon_args = ["--icon", icon] if os.path.exists(icon) else []

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name", "VideoGrabber",
        "--collect-all", "mss",
        "--hidden-import", "pyaudio",
        "--hidden-import", "keyboard",
        "--hidden-import", "pygetwindow",
        "--hidden-import", "PIL._tkinter_finder",
        *icon_args,
        "main.py",
    ]

    print("=" * 60)
    print("  VideoGrabber — build do executável")
    print("  feito por anymousdark")
    print("=" * 60)
    print("Comando:", " ".join(cmd))
    print()

    subprocess.check_call(cmd)

    exe = os.path.join(root, "dist", "VideoGrabber.exe")
    release_dir = os.path.join(root, "release")
    os.makedirs(release_dir, exist_ok=True)

    if os.path.exists(exe):
        target = os.path.join(release_dir, "VideoGrabber.exe")
        shutil.copy2(exe, target)
        size_mb = os.path.getsize(target) / (1024 * 1024)
        print()
        print(f"OK! Executável gerado: {target} ({size_mb:.1f} MB)")
    else:
        print("ERRO: dist/VideoGrabber.exe não foi encontrado.")
        sys.exit(1)


if __name__ == "__main__":
    main()
