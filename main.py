#!/usr/bin/env python3
"""
VideoGrabber - Gravador de tela, webcam e áudio completo
Feito por anymousdark
Licença: MIT - Use, modifique e distribua livremente
"""

import sys
import os

# Adiciona o diretório do script ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui import VideoGrabberApp


def main():
    """Ponto de entrada principal"""
    app = VideoGrabberApp()
    app.run()


if __name__ == "__main__":
    main()