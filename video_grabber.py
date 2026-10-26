#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""VideoGrabber — baixador de vídeos e áudio com yt-dlp.

Front-end gráfico e CLI para o yt-dlp, feito por anymousdark.

Recursos liberados:
  - fila com vários links por vez
  - qualquer site suportado pelo yt-dlp
  - vídeo até a melhor resolução disponível (8K+)
  - formatos de vídeo MP4/MKV/WEBM e áudio MP3/M4A/OPUS/FLAC/WAV
  - playlists completas ou por intervalo
  - legendas em qualquer idioma
  - cookies do navegador (conteúdo que você já tem acesso)
  - SponsorBlock, thumbnail embutida, histórico opcional
  - limite de velocidade, proxy e fragmentos paralelos

Uso CLI:
    python video_grabber.py "https://youtu.be/XXXX" -o "D:\Videos" -q 2160
    python video_grabber.py URL1 URL2 --audio --audio-format mp3
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import queue
import re
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from email.message import Message
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

APP_NAME = "VideoGrabber"
APP_VERSION = "2.0.0"
APP_AUTHOR = "anymousdark"
APP_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME
)
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")
ARCHIVE_PATH = os.path.join(APP_DIR, "baixados.txt")

QUALITY_OPTIONS = {
    "Melhor disponível": None,
    "4320p (8K)": 4320,
    "2160p (4K)": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
    "240p": 240,
    "144p": 144,
}
VIDEO_FORMATS = ["mp4", "mkv", "webm"]
AUDIO_FORMATS = ["mp3", "m4a", "opus", "flac", "wav", "melhor"]
BROWSERS = ["Nenhum", "chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium"]
DIRECT_VIDEO_EXTENSIONS = {
    ".3gp", ".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg",
    ".ogv", ".ts", ".webm",
}
SUB_LANGS_DEFAULT = "pt,pt-BR,pt-PT,en"


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def is_direct_video_url(url: str) -> bool:
    return os.path.splitext(urlsplit(url).path.lower())[1] in DIRECT_VIDEO_EXTENSIONS


def normalize_host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ValueError("Informe um link.")
    parts = urlsplit(url)
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError("O link precisa começar com http:// ou https://")
    if not parts.hostname:
        raise ValueError("Informe um link HTTP(S) válido com nome de site.")
    return url


def sanitize_filename(name: str, fallback: str = "video.mp4") -> str:
    name = os.path.basename((name or "").replace("\\", "/"))
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).rstrip(". ")
    return name or fallback


def available_path(outdir: str, filename: str) -> str:
    path = os.path.join(outdir, filename)
    stem, ext = os.path.splitext(path)
    index = 2
    while os.path.exists(path):
        path = f"{stem} ({index}){ext}"
        index += 1
    return path


def human_speed(bps: float | None) -> str:
    if not bps:
        return "---"
    for unit in ("B", "KB", "MB", "GB"):
        if bps < 1024:
            return f"{bps:.0f} {unit}"
        bps /= 1024
    return f"{bps:.1f} TB"


def human_bytes(value: float | None) -> str:
    if not value:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def parse_languages(text: str) -> list[str]:
    parts = re.split(r"[,;\s]+", (text or "").strip())
    return [p for p in parts if p] or ["pt", "en"]


def ffmpeg_path() -> str | None:
    """Procura o ffmpeg: bundle do exe -> pasta do app -> PATH -> imageio-ffmpeg."""
    candidates = []
    base = getattr(sys, "_MEIPASS", None)
    if base:
        candidates.append(os.path.join(base, "ffmpeg.exe"))
    here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
    candidates.append(os.path.join(here, "ffmpeg.exe"))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    found = shutil.which("ffmpeg")
    if found:
        return found

    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def app_icon_path() -> str | None:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    for name in ("icon.ico", os.path.join("assets", "icon.ico")):
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    return None


def build_format(options: "DownloadOptions", has_ffmpeg: bool) -> str:
    """Monta o seletor de formato do yt-dlp."""
    if options.audio_only:
        return "bestaudio/best"

    cap = f"[height<={options.max_height}]" if options.max_height else ""
    if not has_ffmpeg:
        # Sem ffmpeg não dá para juntar vídeo+áudio: pega arquivo único.
        return f"b{cap}/b"

    if options.video_format == "mp4":
        return f"bv*{cap}[ext=mp4]+ba[ext=m4a]/bv*{cap}+ba/b{cap}/b"
    if options.video_format == "webm":
        return f"bv*{cap}[ext=webm]+ba[ext=webm]/bv*{cap}+ba/b{cap}/b"
    return f"bv*{cap}+ba/b{cap}/b"


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Opções de download
# ---------------------------------------------------------------------------
@dataclass
class DownloadOptions:
    outdir: str
    video_format: str = "mp4"
    audio_only: bool = False
    audio_format: str = "mp3"
    max_height: int | None = None
    playlist: bool = False
    playlist_items: str = ""
    subtitles: bool = True
    subtitle_langs: list[str] = field(default_factory=lambda: ["pt", "en"])
    cookies_browser: str = ""
    sponsorblock: bool = False
    embed_thumbnail: bool = True
    use_archive: bool = True
    speed_limit_kbps: int = 0
    concurrent_fragments: int = 4
    proxy: str = ""
    retries: int = 5
    organize_by_channel: bool = False


class _QueueLogger:
    """Repassa mensagens do yt-dlp para a fila da interface."""

    _NOISE = ("[download] Destination", "[download]   ", "[download]  ", "Deleting original")

    def __init__(self, events: queue.Queue):
        self.events = events

    def debug(self, msg: str) -> None:
        if msg.startswith("[debug]"):
            return
        if msg.startswith("[download]") and any(n in msg for n in ("ETA", "% of")):
            return
        self.info(msg)

    def info(self, msg: str) -> None:
        msg = (msg or "").strip()
        if msg:
            self.events.put(("log", msg))

    def warning(self, msg: str) -> None:
        self.events.put(("log", f"Aviso: {msg}"))

    def error(self, msg: str) -> None:
        self.events.put(("log", f"Erro: {msg}"))


# ---------------------------------------------------------------------------
# Motor de download
# ---------------------------------------------------------------------------
class DownloadJob:
    """Processa uma fila de links em thread separada, reportando por fila."""

    def __init__(self, events: queue.Queue):
        self.events = events
        self.cancel_flag = threading.Event()
        self.thread: threading.Thread | None = None
        self._total = 0
        self._index = 0

    # ---- controle --------------------------------------------------------
    def start(self, urls: list[str], options: DownloadOptions) -> bool:
        if self.running() or not urls:
            return False
        self.cancel_flag.clear()
        self._total = len(urls)
        self._index = 0
        self.thread = threading.Thread(
            target=self._run, args=(urls, options), daemon=True
        )
        self.thread.start()
        return True

    def cancel(self) -> None:
        self.cancel_flag.set()

    def running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    # ---- progresso -------------------------------------------------------
    def _emit_progress(self, item_pct: float, text: str) -> None:
        total = max(1, self._total)
        overall = ((self._index - 1) + max(0.0, min(1.0, item_pct))) / total
        self.events.put(("progress", overall, text))

    # ---- thread ----------------------------------------------------------
    def _run(self, urls: list[str], options: DownloadOptions) -> None:
        ok_count = 0
        os.makedirs(options.outdir, exist_ok=True)

        for index, url in enumerate(urls, 1):
            if self.cancel_flag.is_set():
                break
            self._index = index
            self.events.put(("item", index, self._total, url))
            self.events.put(("log", f"[{index}/{self._total}] {url}"))

            try:
                if not options.audio_only and is_direct_video_url(url):
                    if self._download_direct_file(url, options):
                        ok_count += 1
                        self._emit_progress(1.0, "Concluído")
                        self.events.put(("log", "Arquivo de vídeo baixado."))
                        continue

                if self._download_ytdlp(url, options):
                    ok_count += 1
            except Exception as exc:  # noqa: BLE001 - mostra qualquer falha ao usuário
                if self.cancel_flag.is_set():
                    break
                message = str(exc).strip() or exc.__class__.__name__
                self.events.put(("error", f"[{index}/{self._total}] {message}"))

        if self.cancel_flag.is_set():
            self.events.put(("log", "Download cancelado."))
        self.events.put(("done", ok_count, self._total))

    # ---- yt-dlp ----------------------------------------------------------
    def _download_ytdlp(self, url: str, options: DownloadOptions) -> bool:
        try:
            import yt_dlp
        except ImportError:
            self.events.put(("error", "yt-dlp não instalado. Rode: pip install yt-dlp"))
            return False

        ffmpeg = ffmpeg_path()
        if options.audio_only and not ffmpeg:
            self.events.put((
                "error",
                "Extrair áudio requer FFmpeg. Gere o exe com build_exe.py ou instale o FFmpeg.",
            ))
            return False
        if not ffmpeg:
            self.events.put((
                "log",
                "Aviso: FFmpeg não encontrado. A qualidade pode ficar limitada "
                "e não haverá conversão de legendas.",
            ))

        self.events.put(("log", f"Fonte: {normalize_host(url)}"))
        self.events.put(("log", f"Pasta: {options.outdir}"))
        self.events.put(("log", f"Modo: {'áudio ' + options.audio_format if options.audio_only else 'vídeo ' + options.video_format}"))
        if not options.audio_only:
            self.events.put(("log", f"Qualidade: {options.max_height or 'melhor disponível'}"))
        self._emit_progress(0.0, "Iniciando...")

        if options.organize_by_channel:
            template = (
                "%(uploader|Canal)s/%(playlist_title|)s/%(playlist_index&{:02d} - |)s%(title).120B [%(id)s].%(ext)s"
                if options.playlist
                else "%(uploader|Canal)s/%(title).120B [%(id)s].%(ext)s"
            )
        else:
            template = (
                "%(playlist_title|)s/%(playlist_index&{:02d} - |)s%(title).120B [%(id)s].%(ext)s"
                if options.playlist
                else "%(title).120B [%(id)s].%(ext)s"
            )

        opts: dict = {
            "format": build_format(options, bool(ffmpeg)),
            "outtmpl": os.path.join(options.outdir, template),
            "noplaylist": not options.playlist,
            "windowsfilenames": True,
            "retries": max(1, options.retries),
            "fragment_retries": max(1, options.retries),
            "socket_timeout": 30,
            "concurrent_fragment_downloads": max(1, options.concurrent_fragments),
            "quiet": True,
            "no_warnings": False,
            "noprogress": True,
            "logger": _QueueLogger(self.events),
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._pp_hook],
        }

        if options.playlist_items.strip():
            opts["playlist_items"] = options.playlist_items.strip()
        if options.use_archive:
            os.makedirs(APP_DIR, exist_ok=True)
            opts["download_archive"] = ARCHIVE_PATH
        if options.cookies_browser:
            opts["cookiesfrombrowser"] = (options.cookies_browser, None, None, None)
        if options.proxy.strip():
            opts["proxy"] = options.proxy.strip()
        if options.speed_limit_kbps > 0:
            opts["ratelimit"] = options.speed_limit_kbps * 1024

        postprocessors: list[dict] = []
        if options.sponsorblock:
            postprocessors.append({
                "key": "SponsorBlock",
                "categories": [
                    "sponsor", "selfpromo", "interaction", "intro",
                    "outro", "preview", "music_offtopic",
                ],
                "when": "after_filter",
            })
            self.events.put(("log", "SponsorBlock: marcando capítulos (quando disponível)."))

        if options.audio_only:
            if ffmpeg:
                opts["ffmpeg_location"] = ffmpeg
                codec = "best" if options.audio_format == "melhor" else options.audio_format
                postprocessors.extend([
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": codec,
                        "preferredquality": "0" if codec == "best" else "192",
                    },
                    {"key": "FFmpegMetadata"},
                ])
        else:
            opts["merge_output_format"] = options.video_format
            if ffmpeg:
                opts["ffmpeg_location"] = ffmpeg
                postprocessors.append({"key": "FFmpegMetadata"})
                if options.embed_thumbnail:
                    opts["writethumbnail"] = True
                    postprocessors.append({"key": "EmbedThumbnail"})

        if postprocessors:
            opts["postprocessors"] = postprocessors

        if options.subtitles and not options.audio_only:
            opts.update({
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": options.subtitle_langs or ["pt", "en"],
                "subtitlesformat": "srt/best",
            })

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as exc:  # noqa: BLE001
            if self.cancel_flag.is_set():
                return False
            message = str(exc).strip() or exc.__class__.__name__
            self.events.put(("error", message))
            return False

        self._emit_progress(1.0, "Concluído")
        self.events.put(("log", "Download finalizado com sucesso."))
        return True

    def _progress_hook(self, data: dict) -> None:
        if self.cancel_flag.is_set():
            raise KeyboardInterrupt("cancelado pelo usuário")
        status = data.get("status")
        if status == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes") or 0
            pct = (done / total) if total else 0.0
            text = f"{pct * 100:5.1f}%  {human_speed(data.get('speed'))}/s"
            if total:
                text += f"  {human_bytes(done)}/{human_bytes(total)}"
            eta = data.get("eta")
            if eta:
                text += f"  ETA {int(eta)}s"
            self._emit_progress(pct, text)
        elif status == "finished":
            self._emit_progress(1.0, "Processando...")

    def _pp_hook(self, data: dict) -> None:
        if data.get("status") == "started":
            self.events.put(("log", f"Pós-processando: {data.get('postprocessor', '')}"))

    # ---- links diretos ---------------------------------------------------
    def _download_direct_file(self, url: str, options: DownloadOptions) -> bool:
        """Baixa URL com extensão de vídeo diretamente, sem varrer páginas."""
        self.events.put(("log", "Link direto de vídeo detectado."))
        request = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VideoGrabber/2.0",
            "Accept": "*/*",
        })
        with urlopen(request, timeout=30) as response:
            content_type = response.headers.get_content_type().lower()
            if not content_type.startswith("video/") and content_type != "application/octet-stream":
                self.events.put(("log", "O link não respondeu como arquivo de vídeo; tentando yt-dlp."))
                return False

            filename = self._direct_filename(response.headers, response.geturl())
            final_path = available_path(options.outdir, filename)
            part_path = final_path + ".part"
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            started = time.monotonic()
            self.events.put(("log", f"Salvando arquivo: {os.path.basename(final_path)}"))

            try:
                with open(part_path, "wb") as output:
                    while True:
                        if self.cancel_flag.is_set():
                            raise InterruptedError("cancelado")
                        chunk = response.read(256 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        received += len(chunk)
                        elapsed = max(time.monotonic() - started, 0.001)
                        pct = min(received / total, 1.0) if total else 0.0
                        status = f"{pct * 100:5.1f}%  {human_speed(received / elapsed)}/s"
                        if total:
                            status += f"  {human_bytes(received)}/{human_bytes(total)}"
                        self._emit_progress(pct, status)
                os.replace(part_path, final_path)
            except Exception:
                try:
                    os.remove(part_path)
                except OSError:
                    pass
                raise

        return True

    @staticmethod
    def _direct_filename(headers, url: str) -> str:
        disposition = headers.get("Content-Disposition", "")
        message = Message()
        if disposition:
            message["content-disposition"] = disposition
        filename = message.get_filename() or os.path.basename(unquote(urlsplit(url).path))
        filename = sanitize_filename(filename, "video.mp4")
        if not os.path.splitext(filename)[1]:
            mime = headers.get_content_type()
            extension = mimetypes.guess_extension(mime) or ".mp4"
            filename += extension
        return filename


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _emit(text: str = "", *, err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    if stream is not None:
        try:
            stream.write(text + "\n")
            stream.flush()
            return
        except OSError:
            pass
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        with open(os.path.join(APP_DIR, "cli.log"), "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    except OSError:
        pass


def run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Baixa vídeos, playlists e áudio de sites suportados pelo yt-dlp.",
        epilog=f"feito por {APP_AUTHOR}",
    )
    parser.add_argument("urls", nargs="+", help="um ou mais links HTTP(S)")
    parser.add_argument("-o", "--out", default=os.path.join(os.path.expanduser("~"), "Videos"))
    parser.add_argument(
        "-q", "--quality", default="melhor",
        choices=["melhor", "4320", "2160", "1440", "1080", "720", "480", "360", "240", "144"],
    )
    parser.add_argument("--video-format", default="mp4", choices=VIDEO_FORMATS)
    parser.add_argument("--audio", action="store_true", help="extrair áudio")
    parser.add_argument("--audio-format", default="mp3", choices=AUDIO_FORMATS)
    parser.add_argument("--playlist", action="store_true", help="baixar playlist inteira")
    parser.add_argument("--playlist-items", default="", help="ex.: 1-10,15")
    parser.add_argument("--no-subs", action="store_true", help="não baixar legendas")
    parser.add_argument("--sub-langs", default=SUB_LANGS_DEFAULT, help="idiomas das legendas")
    parser.add_argument("--cookies", default="", choices=[""] + BROWSERS[1:], help="navegador para cookies")
    parser.add_argument("--sponsorblock", action="store_true", help="marcar capítulos do SponsorBlock")
    parser.add_argument("--no-thumbnail", action="store_true", help="não embutir thumbnail")
    parser.add_argument("--no-archive", action="store_true", help="não usar histórico")
    parser.add_argument("--speed-limit", type=int, default=0, help="limite em KB/s (0 = ilimitado)")
    parser.add_argument("--fragments", type=int, default=4, help="downloads paralelos por fragmento")
    parser.add_argument("--proxy", default="", help="ex.: http://127.0.0.1:8080")
    parser.add_argument("--organize", action="store_true", help="organizar por canal")
    args = parser.parse_args(argv)

    urls = []
    for raw in args.urls:
        try:
            urls.append(validate_url(raw))
        except ValueError as exc:
            _emit(f"ERRO: {exc}", err=True)
            return 2

    options = DownloadOptions(
        outdir=os.path.abspath(args.out),
        video_format=args.video_format,
        audio_only=args.audio,
        audio_format=args.audio_format,
        max_height=None if args.quality == "melhor" else int(args.quality),
        playlist=args.playlist,
        playlist_items=args.playlist_items,
        subtitles=not args.no_subs,
        subtitle_langs=parse_languages(args.sub_langs),
        cookies_browser=args.cookies,
        sponsorblock=args.sponsorblock,
        embed_thumbnail=not args.no_thumbnail,
        use_archive=not args.no_archive,
        speed_limit_kbps=max(0, args.speed_limit),
        concurrent_fragments=max(1, min(16, args.fragments)),
        proxy=args.proxy,
        organize_by_channel=args.organize,
    )

    events: queue.Queue = queue.Queue()
    job = DownloadJob(events)
    if not job.start(urls, options):
        _emit("ERRO: não foi possível iniciar o download.", err=True)
        return 2

    ok_count = 0
    total = len(urls)
    try:
        while True:
            kind, *payload = events.get()
            if kind == "log":
                _emit(str(payload[0]))
            elif kind == "progress":
                if sys.stdout is not None:
                    sys.stdout.write(f"\r{str(payload[1]):<60}")
                    sys.stdout.flush()
            elif kind == "error":
                _emit(f"\nERRO: {payload[0]}", err=True)
            elif kind == "done":
                ok_count, total = int(payload[0]), int(payload[1])
                break
    except KeyboardInterrupt:
        job.cancel()

    _emit("")
    _emit(f"Concluído: {ok_count}/{total}")
    return 0 if ok_count == total else 1


def main() -> int:
    args = sys.argv[1:]
    if args:
        return run_cli(args)

    from app_ui import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
