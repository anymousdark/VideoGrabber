#!/usr/bin/env python3
"""
Módulo de gravação do VideoGrabber
Feito por anymousdark
"""

import os
import sys
import time
import threading
import queue
import wave
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Callable, Tuple
from enum import Enum

# Imports opcionais - verificados em runtime
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

from config import config, get_output_path


class RecordingState(Enum):
    """Estados da gravação"""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"


@dataclass
class RecordingStats:
    """Estatísticas da gravação atual"""
    start_time: float = 0
    pause_time: float = 0
    total_paused_duration: float = 0
    frames_recorded: int = 0
    audio_chunks_recorded: int = 0
    file_size_bytes: int = 0
    
    @property
    def duration(self) -> float:
        if self.start_time == 0:
            return 0
        if self.state == RecordingState.PAUSED:
            return self.pause_time - self.start_time - self.total_paused_duration
        return time.time() - self.start_time - self.total_paused_duration
    
    @property
    def state(self) -> RecordingState:
        return getattr(self, '_state', RecordingState.IDLE)
    
    @state.setter
    def state(self, value: RecordingState):
        self._state = value


class ScreenRecorder:
    """Gravador de tela usando mss + OpenCV"""
    
    def __init__(self, video_config, recording_config, webcam_config=None):
        self.video_config = video_config
        self.recording_config = recording_config
        self.webcam_config = webcam_config
        
        self.writer: Optional[cv2.VideoWriter] = None
        self.webcam_capture: Optional[cv2.VideoCapture] = None
        self.sct = None
        self.monitor = None
        
        self.stats = RecordingStats()
        self._frame_queue = queue.Queue(maxsize=60)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Callback para atualizar UI
        self.on_stats_update: Optional[Callable[[RecordingStats], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    def _init_mss(self):
        """Inicializa captura de tela com mss"""
        if not MSS_AVAILABLE:
            raise RuntimeError("mss não instalado. Execute: pip install mss")
        
        self.sct = mss.mss()
        
        # Define monitor a capturar
        if self.recording_config.region:
            x, y, w, h = self.recording_config.region
            self.monitor = {"left": x, "top": y, "width": w, "height": h}
        elif self.recording_config.target_window and PYGETWINDOW_AVAILABLE:
            windows = gw.getWindowsWithTitle(self.recording_config.target_window)
            if windows:
                win = windows[0]
                self.monitor = {
                    "left": win.left, "top": win.top,
                    "width": win.width, "height": win.height
                }
            else:
                self.monitor = self.sct.monitors[1]  # Monitor principal
        else:
            self.monitor = self.sct.monitors[1]  # Monitor principal
        
        # Ajusta resolução do vídeo se necessário
        self.video_config.width = self.monitor["width"]
        self.video_config.height = self.monitor["height"]
    
    def _init_webcam(self):
        """Inicializa webcam se configurada"""
        if not self.webcam_config or not CV2_AVAILABLE:
            return
        
        self.webcam_capture = cv2.VideoCapture(self.webcam_config.device_id)
        if not self.webcam_capture.isOpened():
            print("Aviso: Não foi possível abrir a webcam")
            self.webcam_capture = None
            return
        
        self.webcam_capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.webcam_config.width)
        self.webcam_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.webcam_config.height)
        self.webcam_capture.set(cv2.CAP_PROP_FPS, self.webcam_config.fps)
    
    def _init_video_writer(self, output_path: str):
        """Inicializa o escritor de vídeo"""
        if not CV2_AVAILABLE:
            raise RuntimeError("OpenCV não instalado. Execute: pip install opencv-python")
        
        fourcc_map = {
            'mp4': 'mp4v',
            'avi': 'XVID',
            'mkv': 'XVID',  # MKV com XVID (pode precisar de FFmpeg)
            'webm': 'VP80',
        }
        
        fourcc = cv2.VideoWriter_fourcc(*fourcc_map.get(
            self.video_config.output_format, 'mp4v'
        ))
        
        self.writer = cv2.VideoWriter(
            output_path,
            fourcc,
            self.video_config.fps,
            (self.video_config.width, self.video_config.height)
        )
        
        if not self.writer.isOpened():
            raise RuntimeError(f"Não foi possível criar arquivo de vídeo: {output_path}")
        
        # Qualidade (suportado por alguns backends/codecs)
        try:
            self.writer.set(cv2.VIDEOWRITER_PROP_QUALITY, self.video_config.quality)
        except Exception:
            pass
    
    def _overlay_webcam(self, screen_frame: np.ndarray) -> np.ndarray:
        """Sobrepõe webcam no frame da tela (Picture-in-Picture)"""
        if self.webcam_capture is None:
            return screen_frame
        
        ret, webcam_frame = self.webcam_capture.read()
        if not ret:
            return screen_frame
        
        # Redimensiona webcam
        h, w = screen_frame.shape[:2]
        webcam_w = int(w * self.webcam_config.size_percent)
        webcam_h = int(webcam_frame.shape[0] * webcam_w / webcam_frame.shape[1])
        
        webcam_resized = cv2.resize(webcam_frame, (webcam_w, webcam_h))
        
        # Posição
        x = int(w * self.webcam_config.position[0])
        y = int(h * self.webcam_config.position[1])
        
        # Garante que não saia da tela
        x = min(x, w - webcam_w)
        y = min(y, h - webcam_h)
        
        # Sobrepõe com transparência
        overlay = screen_frame.copy()
        overlay[y:y+webcam_h, x:x+webcam_w] = webcam_resized
        
        # Adiciona borda
        cv2.rectangle(overlay, (x, y), (x+webcam_w, y+webcam_h), (0, 255, 0), 2)
        
        return overlay
    
    def _draw_cursor(self, frame: np.ndarray):
        """Desenha cursor do mouse no frame"""
        if not self.video_config.show_cursor:
            return
        
        try:
            # Usa a API do Windows (sem dependência externa)
            import ctypes

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            point = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            x, y = point.x, point.y
            
            # Ajusta coordenadas relativas ao monitor capturado
            rel_x = x - self.monitor["left"]
            rel_y = y - self.monitor["top"]
            
            if 0 <= rel_x < frame.shape[1] and 0 <= rel_y < frame.shape[0]:
                cv2.circle(frame, (rel_x, rel_y), 10, (0, 0, 255), -1)
                cv2.circle(frame, (rel_x, rel_y), 12, (255, 255, 255), 2)
        except Exception:
            pass
    
    def _recording_loop(self):
        """Loop principal de gravação (roda em thread separada)"""
        frame_interval = 1.0 / self.video_config.fps
        next_frame_time = time.time()
        
        while self._running:
            current_time = time.time()
            
            # Controle de FPS
            if current_time < next_frame_time:
                time.sleep(next_frame_time - current_time)
            
            next_frame_time += frame_interval
            
            if self.stats.state == RecordingState.PAUSED:
                continue
            
            try:
                # Captura tela
                screenshot = self.sct.grab(self.monitor)
                frame = np.array(screenshot)
                
                # Converte BGRA para BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                
                # Sobrepõe webcam se configurado
                if self.recording_config.mode == 'both' and self.webcam_config.show_in_recording:
                    frame = self._overlay_webcam(frame)
                
                # Desenha cursor
                self._draw_cursor(frame)
                
                # Escreve frame
                if self.writer:
                    self.writer.write(frame)
                    self.stats.frames_recorded += 1
                
                # Atualiza stats
                if self.on_stats_update:
                    self.on_stats_update(self.stats)
                    
            except Exception as e:
                if self.on_error:
                    self.on_error(f"Erro na captura de tela: {e}")
                break
        
        # Finaliza
        self._cleanup()
    
    def _cleanup(self):
        """Limpa recursos"""
        if self.writer:
            self.writer.release()
            self.writer = None
        
        if self.webcam_capture:
            self.webcam_capture.release()
            self.webcam_capture = None
        
        if self.sct:
            self.sct.close()
            self.sct = None
    
    def start(self, output_path: str = None) -> bool:
        """Inicia gravação"""
        if self._running:
            return False
        
        if output_path is None:
            output_path = get_output_path()
        
        try:
            self._init_mss()
            self._init_webcam()
            self._init_video_writer(output_path)
            
            self.stats = RecordingStats()
            self.stats.start_time = time.time()
            self.stats.state = RecordingState.RECORDING
            
            self._running = True
            self._thread = threading.Thread(target=self._recording_loop, daemon=True)
            self._thread.start()
            
            return True
            
        except Exception as e:
            if self.on_error:
                self.on_error(f"Erro ao iniciar gravação: {e}")
            self._cleanup()
            return False
    
    def pause(self):
        """Pausa gravação"""
        if self.stats.state == RecordingState.RECORDING:
            self.stats.state = RecordingState.PAUSED
            self.stats.pause_time = time.time()
    
    def resume(self):
        """Retoma gravação"""
        if self.stats.state == RecordingState.PAUSED:
            self.stats.total_paused_duration += time.time() - self.stats.pause_time
            self.stats.state = RecordingState.RECORDING
    
    def stop(self) -> RecordingStats:
        """Para gravação e retorna estatísticas"""
        self._running = False
        self.stats.state = RecordingState.STOPPING
        
        if self._thread:
            self._thread.join(timeout=5)
        
        self._cleanup()
        self.stats.state = RecordingState.IDLE
        
        return self.stats


class AudioRecorder:
    """Gravador de áudio (sistema + microfone)"""
    
    def __init__(self, audio_config):
        self.audio_config = audio_config
        self.audio = None
        self.stream_system = None
        self.stream_mic = None
        self.wav_file = None
        
        self.stats = RecordingStats()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._system_queue = queue.Queue()
        self._mic_queue = queue.Queue()
        
        self.on_stats_update: Optional[Callable[[RecordingStats], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    def _init_audio(self):
        """Inicializa PyAudio"""
        if not PYAUDIO_AVAILABLE:
            raise RuntimeError("PyAudio não instalado. Execute: pip install pyaudio")
        
        self.audio = pyaudio.PyAudio()
    
    def _find_loopback_device(self):
        """Encontra dispositivo de loopback (áudio do sistema)"""
        if not self.audio:
            return None
        
        # Tenta encontrar dispositivo WASAPI loopback no Windows
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            name = info['name'].lower()
            if any(kw in name for kw in ['stereo mix', 'wave out', 'loopback', 'monitor']):
                if info['maxInputChannels'] > 0:
                    return i
        return None
    
    def _audio_callback_system(self, in_data, frame_count, time_info, status):
        """Callback para áudio do sistema"""
        if self._running and self.stats.state == RecordingState.RECORDING:
            self._system_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    def _audio_callback_mic(self, in_data, frame_count, time_info, status):
        """Callback para microfone"""
        if self._running and self.stats.state == RecordingState.RECORDING:
            # Aplica volume do microfone
            audio_data = np.frombuffer(in_data, dtype=np.int16)
            audio_data = (audio_data * self.audio_config.mic_volume).astype(np.int16)
            self._mic_queue.put(audio_data.tobytes())
        return (None, pyaudio.paContinue)
    
    def _mix_audio(self, system_data: bytes, mic_data: bytes) -> bytes:
        """Mistura áudio do sistema e microfone"""
        sys_arr = np.frombuffer(system_data, dtype=np.int16)
        mic_arr = np.frombuffer(mic_data, dtype=np.int16)
        
        # Garante mesmo tamanho
        min_len = min(len(sys_arr), len(mic_arr))
        sys_arr = sys_arr[:min_len]
        mic_arr = mic_arr[:min_len]
        
        # Aplica volumes
        sys_arr = (sys_arr * self.audio_config.system_volume).astype(np.int16)
        mic_arr = (mic_arr * self.audio_config.mic_volume).astype(np.int16)
        
        # Mistura (média ponderada para evitar clipping)
        mixed = (sys_arr.astype(np.float32) + mic_arr.astype(np.float32)) / 2
        mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
        
        return mixed.tobytes()
    
    def _recording_loop(self, output_path: str):
        """Loop de gravação de áudio"""
        # Abre arquivo WAV temporário
        self.wav_file = wave.open(output_path, 'wb')
        self.wav_file.setnchannels(self.audio_config.channels)
        self.wav_file.setsampwidth(2)  # 16-bit
        self.wav_file.setframerate(self.audio_config.sample_rate)
        
        self.stats.start_time = time.time()
        self.stats.state = RecordingState.RECORDING
        
        chunk_duration = self.audio_config.chunk_size / self.audio_config.sample_rate
        
        while self._running:
            if self.stats.state == RecordingState.PAUSED:
                time.sleep(0.1)
                continue
            
            try:
                mixed_data = None
                
                # Coleta áudio do sistema
                system_data = b''
                if self.audio_config.record_system_audio:
                    try:
                        system_data = self._system_queue.get(timeout=0.1)
                    except queue.Empty:
                        system_data = b'\x00' * (self.audio_config.chunk_size * 2 * self.audio_config.channels)
                
                # Coleta microfone
                mic_data = b''
                if self.audio_config.record_microphone:
                    try:
                        mic_data = self._mic_queue.get(timeout=0.1)
                    except queue.Empty:
                        mic_data = b'\x00' * (self.audio_config.chunk_size * 2 * self.audio_config.channels)
                
                # Mistura ou usa apenas um
                if system_data and mic_data:
                    mixed_data = self._mix_audio(system_data, mic_data)
                elif system_data:
                    mixed_data = system_data
                elif mic_data:
                    mixed_data = mic_data
                
                if mixed_data:
                    self.wav_file.writeframes(mixed_data)
                    self.stats.audio_chunks_recorded += 1
                    
            except Exception as e:
                if self.on_error:
                    self.on_error(f"Erro na gravação de áudio: {e}")
                break
        
        # Finaliza arquivo WAV
        if self.wav_file:
            self.wav_file.close()
            self.wav_file = None
    
    def start(self, output_path: str = None) -> bool:
        """Inicia gravação de áudio"""
        if self._running:
            return False
        
        if output_path is None:
            output_path = get_output_path().replace('.mp4', '_audio.wav')
        
        try:
            self._init_audio()
            
            # Stream do sistema (loopback)
            if self.audio_config.record_system_audio:
                loopback_idx = self._find_loopback_device()
                if loopback_idx is not None:
                    self.stream_system = self.audio.open(
                        format=pyaudio.paInt16,
                        channels=self.audio_config.channels,
                        rate=self.audio_config.sample_rate,
                        input=True,
                        input_device_index=loopback_idx,
                        frames_per_buffer=self.audio_config.chunk_size,
                        stream_callback=self._audio_callback_system
                    )
            
            # Stream do microfone
            if self.audio_config.record_microphone:
                self.stream_mic = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=self.audio_config.channels,
                    rate=self.audio_config.sample_rate,
                    input=True,
                    frames_per_buffer=self.audio_config.chunk_size,
                    stream_callback=self._audio_callback_mic
                )
            
            self._running = True
            self._thread = threading.Thread(
                target=self._recording_loop, 
                args=(output_path,), 
                daemon=True
            )
            self._thread.start()
            
            return True
            
        except Exception as e:
            if self.on_error:
                self.on_error(f"Erro ao iniciar áudio: {e}")
            self.stop()
            return False
    
    def pause(self):
        """Pausa gravação de áudio"""
        if self.stats.state == RecordingState.RECORDING:
            self.stats.state = RecordingState.PAUSED
            self.stats.pause_time = time.time()
    
    def resume(self):
        """Retoma gravação de áudio"""
        if self.stats.state == RecordingState.PAUSED:
            self.stats.total_paused_duration += time.time() - self.stats.pause_time
            self.stats.state = RecordingState.RECORDING
    
    def stop(self) -> RecordingStats:
        """Para gravação de áudio"""
        self._running = False
        self.stats.state = RecordingState.STOPPING
        
        if self.stream_system:
            self.stream_system.stop_stream()
            self.stream_system.close()
            self.stream_system = None
        
        if self.stream_mic:
            self.stream_mic.stop_stream()
            self.stream_mic.close()
            self.stream_mic = None
        
        if self.audio:
            self.audio.terminate()
            self.audio = None
        
        if self._thread:
            self._thread.join(timeout=3)
        
        self.stats.state = RecordingState.IDLE
        return self.stats


class WebcamRecorder:
    """Gravador de webcam usando OpenCV"""
    
    def __init__(self, webcam_config, video_config):
        self.webcam_config = webcam_config
        self.video_config = video_config
        
        self.capture: Optional[cv2.VideoCapture] = None
        self.writer: Optional[cv2.VideoWriter] = None
        
        self.stats = RecordingStats()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        self.on_stats_update: Optional[Callable[[RecordingStats], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    def _recording_loop(self):
        """Loop de captura da webcam"""
        if not CV2_AVAILABLE:
            if self.on_error:
                self.on_error("OpenCV não instalado. Execute: pip install opencv-python")
            return
        
        self.capture = cv2.VideoCapture(self.webcam_config.device_id)
        if not self.capture.isOpened():
            if self.on_error:
                self.on_error(f"Não foi possível abrir a webcam (ID {self.webcam_config.device_id})")
            return
        
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.webcam_config.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.webcam_config.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.webcam_config.fps)
        
        width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or self.webcam_config.width
        height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or self.webcam_config.height
        fps = self.webcam_config.fps
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.writer = cv2.VideoWriter(
            self.output_path, fourcc, fps, (width, height)
        )
        try:
            self.writer.set(cv2.VIDEOWRITER_PROP_QUALITY, self.video_config.quality)
        except Exception:
            pass
        
        self.stats.start_time = time.time()
        self.stats.state = RecordingState.RECORDING
        
        while self._running:
            if self.stats.state == RecordingState.PAUSED:
                time.sleep(0.05)
                continue
            
            ret, frame = self.capture.read()
            if not ret:
                time.sleep(0.01)
                continue
            
            if self.writer:
                self.writer.write(frame)
                self.stats.frames_recorded += 1
            
            if self.on_stats_update:
                self.on_stats_update(self.stats)
        
        if self.writer:
            self.writer.release()
            self.writer = None
        if self.capture:
            self.capture.release()
            self.capture = None
    
    def start(self, output_path: str) -> bool:
        """Inicia gravação da webcam"""
        if self._running:
            return False
        
        self.output_path = output_path
        self._running = True
        self.stats = RecordingStats()
        self.stats.state = RecordingState.RECORDING
        self._thread = threading.Thread(target=self._recording_loop, daemon=True)
        self._thread.start()
        return True
    
    def pause(self):
        if self.stats.state == RecordingState.RECORDING:
            self.stats.state = RecordingState.PAUSED
            self.stats.pause_time = time.time()
    
    def resume(self):
        if self.stats.state == RecordingState.PAUSED:
            self.stats.total_paused_duration += time.time() - self.stats.pause_time
            self.stats.state = RecordingState.RECORDING
    
    def stop(self) -> RecordingStats:
        self._running = False
        self.stats.state = RecordingState.STOPPING
        if self._thread:
            self._thread.join(timeout=5)
        self.stats.state = RecordingState.IDLE
        return self.stats


class VideoGrabberRecorder:
    """Classe principal que coordena vídeo + áudio"""
    
    def __init__(self):
        self.screen_recorder: Optional[ScreenRecorder] = None
        self.webcam_recorder: Optional[WebcamRecorder] = None
        self.audio_recorder: Optional[AudioRecorder] = None
        
        self.video_output_path: Optional[str] = None
        self.audio_output_path: Optional[str] = None
        self.final_output_path: Optional[str] = None
        
        self.on_state_change: Optional[Callable[[RecordingState], None]] = None
        self.on_stats_update: Optional[Callable[[dict], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_finished: Optional[Callable[[str], None]] = None
    
    def _merge_audio_video(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """Mescla áudio e vídeo usando FFmpeg"""
        try:
            import subprocess
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                print(f"FFmpeg erro: {result.stderr}")
                # Fallback: copia apenas vídeo se áudio falhar
                import shutil
                shutil.copy2(video_path, output_path)
                return False
            
            return True
            
        except FileNotFoundError:
            print("FFmpeg não encontrado. Instale FFmpeg para mesclar áudio/vídeo.")
            import shutil
            shutil.copy2(video_path, output_path)
            return False
        except Exception as e:
            print(f"Erro ao mesclar: {e}")
            import shutil
            shutil.copy2(video_path, output_path)
            return False
    
    def start(self, mode: str = 'screen', output_path: str = None) -> bool:
        """Inicia gravação completa"""
        if output_path is None:
            output_path = get_output_path()
        
        self.final_output_path = output_path
        base_name = os.path.splitext(output_path)[0]
        self.video_output_path = base_name + '_video.' + config.video.output_format
        self.audio_output_path = base_name + '_audio.wav'
        
        success = True
        
        # Inicia gravador de tela
        if mode in ['screen', 'both']:
            self.screen_recorder = ScreenRecorder(
                config.video, config.recording, config.webcam
            )
            self.screen_recorder.on_stats_update = self._on_screen_stats
            self.screen_recorder.on_error = self._on_error
            
            if not self.screen_recorder.start(self.video_output_path):
                success = False
        
        # Inicia gravador de webcam
        elif mode == 'webcam':
            self.webcam_recorder = WebcamRecorder(config.webcam, config.video)
            self.webcam_recorder.on_stats_update = self._on_screen_stats
            self.webcam_recorder.on_error = self._on_error
            
            if not self.webcam_recorder.start(self.video_output_path):
                success = False
        
        # Inicia gravador de áudio
        if mode in ['screen', 'both', 'webcam', 'audio_only'] and (config.audio.record_system_audio or config.audio.record_microphone):
            self.audio_recorder = AudioRecorder(config.audio)
            self.audio_recorder.on_stats_update = self._on_audio_stats
            self.audio_recorder.on_error = self._on_error
            
            if not self.audio_recorder.start(self.audio_output_path):
                # Falha de áudio é fatal apenas no modo somente-áudio
                if mode == 'audio_only':
                    success = False
        
        if not success:
            # Limpa gravações parciais para não deixar threads/arquivos órfãos
            if self.screen_recorder:
                self.screen_recorder.stop()
            if self.webcam_recorder:
                self.webcam_recorder.stop()
            if self.audio_recorder:
                self.audio_recorder.stop()
            return False
        
        if self.on_state_change:
            self.on_state_change(RecordingState.RECORDING)
        
        return True
    
    def pause(self):
        """Pausa todas as gravações"""
        if self.screen_recorder:
            self.screen_recorder.pause()
        if self.webcam_recorder:
            self.webcam_recorder.pause()
        if self.audio_recorder:
            self.audio_recorder.pause()
        
        if self.on_state_change:
            self.on_state_change(RecordingState.PAUSED)
    
    def resume(self):
        """Retoma todas as gravações"""
        if self.screen_recorder:
            self.screen_recorder.resume()
        if self.webcam_recorder:
            self.webcam_recorder.resume()
        if self.audio_recorder:
            self.audio_recorder.resume()
        
        if self.on_state_change:
            self.on_state_change(RecordingState.RECORDING)
    
    def stop(self) -> str:
        """Para gravação e mescla áudio/vídeo"""
        if self.screen_recorder:
            self.screen_recorder.stop()
        
        if self.webcam_recorder:
            self.webcam_recorder.stop()
        
        if self.audio_recorder:
            self.audio_recorder.stop()
        
        import shutil
        
        has_video = bool(self.video_output_path and os.path.exists(self.video_output_path))
        has_audio = bool(self.audio_output_path and os.path.exists(self.audio_output_path))
        
        # Mescla se tiver ambos
        if has_video and has_audio:
            merged = self._merge_audio_video(
                self.video_output_path,
                self.audio_output_path,
                self.final_output_path
            )
            
            # Remove temporários; se o merge falhou, preserva o WAV ao lado do vídeo
            try:
                os.remove(self.video_output_path)
            except OSError:
                pass
            
            if merged:
                try:
                    os.remove(self.audio_output_path)
                except OSError:
                    pass
            else:
                audio_keep = os.path.splitext(self.final_output_path)[0] + '_audio.wav'
                try:
                    shutil.move(self.audio_output_path, audio_keep)
                except OSError:
                    pass
        
        elif has_video:
            # Apenas vídeo - renomeia
            if os.path.abspath(self.video_output_path) != os.path.abspath(self.final_output_path):
                shutil.move(self.video_output_path, self.final_output_path)
        
        elif has_audio:
            # Áudio-only (ou fallback): move o WAV para o destino final
            if os.path.abspath(self.audio_output_path) != os.path.abspath(self.final_output_path):
                try:
                    shutil.move(self.audio_output_path, self.final_output_path)
                except OSError:
                    pass
        
        if self.on_state_change:
            self.on_state_change(RecordingState.IDLE)
        
        if self.on_finished and self.final_output_path:
            self.on_finished(self.final_output_path)
        
        return self.final_output_path
    
    def _on_screen_stats(self, stats: RecordingStats):
        if self.on_stats_update:
            self.on_stats_update({
                'video_frames': stats.frames_recorded,
                'duration': stats.duration,
                'state': stats.state.value
            })
    
    def _on_audio_stats(self, stats: RecordingStats):
        if self.on_stats_update:
            self.on_stats_update({
                'audio_chunks': stats.audio_chunks_recorded,
                'duration': stats.duration,
            })
    
    def _on_error(self, error: str):
        if self.on_error:
            self.on_error(error)
    
    def get_stats(self) -> dict:
        """Retorna estatísticas combinadas"""
        stats = {}
        if self.screen_recorder:
            stats.update({
                'video_frames': self.screen_recorder.stats.frames_recorded,
                'duration': self.screen_recorder.stats.duration,
                'state': self.screen_recorder.stats.state.value
            })
        if self.webcam_recorder:
            stats.update({
                'video_frames': self.webcam_recorder.stats.frames_recorded,
                'duration': self.webcam_recorder.stats.duration,
                'state': self.webcam_recorder.stats.state.value
            })
        if self.audio_recorder:
            stats.update({
                'audio_chunks': self.audio_recorder.stats.audio_chunks_recorded,
            })
        return stats
    
    def is_recording(self) -> bool:
        if self.screen_recorder:
            return self.screen_recorder.stats.state == RecordingState.RECORDING
        if self.webcam_recorder:
            return self.webcam_recorder.stats.state == RecordingState.RECORDING
        if self.audio_recorder:
            return self.audio_recorder.stats.state == RecordingState.RECORDING
        return False
    
    def is_paused(self) -> bool:
        if self.screen_recorder:
            return self.screen_recorder.stats.state == RecordingState.PAUSED
        if self.webcam_recorder:
            return self.webcam_recorder.stats.state == RecordingState.PAUSED
        if self.audio_recorder:
            return self.audio_recorder.stats.state == RecordingState.PAUSED
        return False
