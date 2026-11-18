"""Utilidades compartidas: rutas, configuración, ffmpeg/ffprobe y escenas.json."""
import json
import os
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VIDEOS = RAIZ / "videos"
ACTUAL = VIDEOS / ".actual"  # último video usado con generar_video.py

# Cada video vive en videos/<nombre>/ (guion.md, trabajo/, video.mp4, video.srt, reporte.md).
VIDEO = os.environ.get("VIDEO_STICK") or (ACTUAL.read_text(encoding="utf-8").strip() if ACTUAL.exists() else "")
PROYECTO = VIDEOS / (VIDEO or "_sin_video")
GUION = PROYECTO / "guion.md"
TRABAJO = PROYECTO / "trabajo"
DIR_AUDIO = TRABAJO / "audio"
DIR_IMG = TRABAJO / "imagenes"
DIR_SUBS = TRABAJO / "subtitulos"
DIR_CLIPS = TRABAJO / "clips"
DIR_FLOW = TRABAJO / "flow"
SALIDA = PROYECTO
DIR_SHORTS = PROYECTO / "shorts"  # short_1.mp4, short_2.mp4 de este video
ESCENAS_JSON = TRABAJO / "escenas.json"

ANCHO, ALTO = 1920, 1080


class PipelineError(Exception):
    """Error que detiene el pipeline con un mensaje claro."""


def cargar_config(ruta: Path) -> dict:
    if not ruta.exists():
        raise PipelineError(f"No existe el archivo de configuración: {ruta}")
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PipelineError(f"config.json no es JSON válido: {e}")


def preparar_carpetas():
    if not VIDEO:
        raise PipelineError("No se indicó el video. Uso: python generar_video.py <nombre>  (carpeta videos/<nombre>/)")
    for d in (TRABAJO, DIR_AUDIO, DIR_IMG, DIR_SUBS, DIR_CLIPS, DIR_FLOW, SALIDA, DIR_SHORTS):
        d.mkdir(parents=True, exist_ok=True)


def ejecutar(cmd, descripcion: str, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
    if r.returncode != 0:
        cola = "\n".join(r.stderr.strip().splitlines()[-15:])
        raise PipelineError(f"{descripcion} falló (código {r.returncode}):\n{cola}")
    return r


def duracion_media(ruta: Path) -> float:
    r = ejecutar(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(ruta)],
        f"ffprobe de {ruta.name}",
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise PipelineError(f"ffprobe no devolvió una duración válida para {ruta}")


def guardar_escenas(datos: dict):
    ESCENAS_JSON.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def cargar_escenas() -> dict:
    if not ESCENAS_JSON.exists():
        raise PipelineError(f"No existe {rel(ESCENAS_JSON)}; ejecuta primero el paso 'escenas'.")
    return json.loads(ESCENAS_JSON.read_text(encoding="utf-8"))


def rel(ruta: Path) -> str:
    """Ruta relativa a la raíz del proyecto, con barras normales."""
    return Path(ruta).resolve().relative_to(RAIZ).as_posix()
