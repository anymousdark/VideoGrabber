#!/usr/bin/env python3
"""
Configurações do VideoGrabber
Feito por anymousdark
"""

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class VideoConfig:
    """Configurações de vídeo"""
    # Resolução
    width: int = 1920
    height: int = 1080
    
    # FPS
    fps: int = 30
    
    # Codec de vídeo
    # Opções: 'mp4v', 'XVID', 'MJPG', 'H264', 'VP8', 'VP9'
    video_codec: str = 'mp4v'
    
    # Formato de saída
    # Opções: 'mp4', 'avi', 'mkv', 'webm'
    output_format: Literal['mp4', 'avi', 'mkv', 'webm'] = 'mp4'
    
    # Qualidade (0-100, para codecs que suportam)
    quality: int = 90
    
    # Mostrar cursor do mouse na gravação
    show_cursor: bool = True
    
    # Destacar cliques do mouse
    highlight_clicks: bool = True


@dataclass
class AudioConfig:
    """Configurações de áudio"""
    # Taxa de amostragem
    sample_rate: int = 44100
    
    # Canais (1=mono, 2=estéreo)
    channels: int = 2
    
    # Tamanho do buffer
    chunk_size: int = 1024
    
    # Formato de áudio
    audio_format: str = 'pyaudio.paInt16'
    
    # Gravar áudio do sistema (loopback)
    record_system_audio: bool = True
    
    # Gravar microfone
    record_microphone: bool = True
    
    # Volume do microfone (0.0 - 1.0)
    mic_volume: float = 1.0
    
    # Volume do áudio do sistema (0.0 - 1.0)
    system_volume: float = 1.0


@dataclass
class WebcamConfig:
    """Configurações de webcam"""
    # ID do dispositivo (0 = padrão)
    device_id: int = 0
    
    # Resolução da webcam
    width: int = 1280
    height: int = 720
    
    # FPS da webcam
    fps: int = 30
    
    # Mostrar preview da webcam na gravação de tela
    show_in_recording: bool = True
    
    # Posição do preview da webcam (x, y) em porcentagem da tela
    position: tuple = (0.02, 0.02)  # Canto superior esquerdo
    
    # Tamanho do preview (porcentagem da largura da tela)
    size_percent: float = 0.25


@dataclass
class RecordingConfig:
    """Configurações gerais de gravação"""
    # Diretório de saída
    output_dir: str = field(default_factory=lambda: os.path.join(
        os.path.expanduser("~"), "Videos", "VideoGrabber"
    ))
    
    # Prefixo do nome do arquivo
    filename_prefix: str = "VideoGrabber_"
    
    # Modo de gravação
    # 'screen' = apenas tela
    # 'webcam' = apenas webcam
    # 'both' = tela + webcam (picture in picture)
    # 'audio_only' = apenas áudio
    mode: Literal['screen', 'webcam', 'both', 'audio_only'] = 'screen'
    
    # Gravar região específica (None = tela inteira)
    # Formato: (x, y, width, height)
    region: tuple = None
    
    # Janela específica para gravar (título da janela)
    target_window: str = None
    
    # Limite de tempo em segundos (0 = sem limite)
    time_limit: int = 0
    
    # Limite de tamanho em MB (0 = sem limite)
    size_limit_mb: int = 0
    
    # Auto-iniciar gravação ao abrir
    auto_start: bool = False
    
    # Minimizar para bandeja ao gravar
    minimize_to_tray: bool = True


@dataclass
class HotkeyConfig:
    """Configurações de atalhos globais"""
    # Iniciar/Parar gravação
    start_stop: str = 'f9'
    
    # Pausar/Retomar
    pause_resume: str = 'f10'
    
    # Capturar screenshot
    screenshot: str = 'f11'
    
    # Mostrar/Ocultar janela
    toggle_window: str = 'f12'


@dataclass
class AppConfig:
    """Configuração principal da aplicação"""
    video: VideoConfig = field(default_factory=VideoConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    webcam: WebcamConfig = field(default_factory=WebcamConfig)
    recording: RecordingConfig = field(default_factory=RecordingConfig)
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    
    # Tema da interface
    theme: Literal['light', 'dark', 'system'] = 'dark'
    
    # Idioma
    language: str = 'pt_BR'
    
    # Verificar atualizações ao iniciar
    check_updates: bool = True
    
    # Salvar configurações ao fechar
    save_on_exit: bool = True


# Instância global de configuração
config = AppConfig()


def get_output_path(filename: str = None) -> str:
    """Gera caminho completo para arquivo de saída"""
    os.makedirs(config.recording.output_dir, exist_ok=True)
    
    if filename is None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = config.video.output_format
        filename = f"{config.recording.filename_prefix}{timestamp}.{ext}"
    
    return os.path.join(config.recording.output_dir, filename)


def load_config_from_file(config_path: str = None):
    """Carrega configurações de arquivo JSON"""
    import json
    
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'settings.json'
        )
    
    if not os.path.exists(config_path):
        return
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Atualiza configurações (implementação simplificada)
        # Em produção, usar biblioteca como pydantic para validação
        for section, values in data.items():
            if hasattr(config, section):
                section_obj = getattr(config, section)
                for key, value in values.items():
                    if hasattr(section_obj, key):
                        setattr(section_obj, key, value)
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")


def save_config_to_file(config_path: str = None):
    """Salva configurações em arquivo JSON"""
    import json
    from dataclasses import asdict
    
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'settings.json'
        )
    
    try:
        data = {
            'video': asdict(config.video),
            'audio': asdict(config.audio),
            'webcam': asdict(config.webcam),
            'recording': asdict(config.recording),
            'hotkeys': asdict(config.hotkeys),
            'theme': config.theme,
            'language': config.language,
            'check_updates': config.check_updates,
            'save_on_exit': config.save_on_exit,
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar configurações: {e}")