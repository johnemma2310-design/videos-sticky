"""Conexión con Google Flow (las imágenes se generan en el navegador con pipeline/flow_runner.js).

Trabaja sobre el último video usado con generar_video.py (videos/.actual) o el que se indique:
    python -m pipeline.flow exportar [video]   # crea trabajo/flow_pendientes.json con los planos sin imagen
    python -m pipeline.flow progreso [video]   # cuántas imágenes del lote ya están en Descargas
    python -m pipeline.flow importar [video]   # mueve las descargas del lote a trabajo/flow/escena_NNN.jpg
    python -m pipeline.flow clips [video]      # clips pendientes: escena, huella de su imagen y prompt
    python -m pipeline.flow clip NNN           # mueve el último .mp4 de Descargas a trabajo/flow/clip_NNN.mp4

Cada lote tiene un id; las descargas se llaman <lote>_escena_NNN.jpg, así nunca se mezclan
con archivos viejos de la carpeta Descargas.
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

if __name__ == "__main__" and len(sys.argv) > 2 and not sys.argv[2].isdigit():
    os.environ["VIDEO_STICK"] = sys.argv[2]

from .comun import DIR_FLOW, RAIZ, TRABAJO, VIDEO, PipelineError, cargar_config, cargar_escenas, rel
from .imagenes import buscar_flow

PENDIENTES = TRABAJO / "flow_pendientes.json"


def _descargas(cfg) -> Path:
    return Path(cfg["flow"].get("descargas") or Path.home() / "Downloads")


def exportar(cfg) -> dict:
    planos = [e for e in cargar_escenas()["escenas"] if "prompt" in e]
    if not planos:
        raise PipelineError("escenas.json no tiene prompts; ejecuta primero el paso 'escenas'.")
    lote = "flow" + datetime.now().strftime("%m%d%H%M")
    lista = [{"archivo": f"{lote}_escena_{e['id']:03d}.jpg", "prompt": e["prompt"]}
             for e in planos if not buscar_flow(e["id"])]
    datos = {"lote": lote, "video": VIDEO, "escenas": lista}
    PENDIENTES.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return datos


def _del_lote(cfg, lote):
    patron = re.compile(rf"^{lote}_escena_(\d{{3}})(?: \(\d+\))?\.(jpg|jpeg|png|webp)$")
    por_escena = {}
    for p in _descargas(cfg).iterdir():
        m = patron.match(p.name)
        if m:
            por_escena.setdefault(int(m.group(1)), []).append(p)
    return por_escena


def progreso(cfg):
    datos = json.loads(PENDIENTES.read_text(encoding="utf-8"))
    return len(_del_lote(cfg, datos["lote"])), len(datos["escenas"])


def importar(cfg) -> tuple[list, list]:
    if not PENDIENTES.exists():
        raise PipelineError(f"No existe {rel(PENDIENTES)}; ejecuta 'exportar' primero.")
    datos = json.loads(PENDIENTES.read_text(encoding="utf-8"))
    DIR_FLOW.mkdir(parents=True, exist_ok=True)
    encontradas = _del_lote(cfg, datos["lote"])
    movidas, faltan = [], []
    for item in datos["escenas"]:
        n = int(re.search(r"escena_(\d{3})", item["archivo"]).group(1))
        copias = sorted(encontradas.get(n, []), key=lambda p: p.stat().st_mtime)
        if not copias:
            faltan.append(n)
            continue
        final = copias[-1]
        final.replace(DIR_FLOW / f"escena_{n:03d}{final.suffix.lower()}")
        for extra in copias[:-1]:  # copias duplicadas del mismo lote
            extra.unlink()
        movidas.append(n)
    return movidas, faltan


def huella(ruta) -> str:
    """dHash de 64 bits; flow_clips.js calcula la misma huella para hallar la imagen en Flow."""
    from PIL import Image
    with Image.open(ruta) as im:
        g = list(im.convert("L").resize((9, 8), Image.BILINEAR).get_flattened_data())
    return "".join("1" if g[r * 9 + c] > g[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))


def clips_pendientes(cfg) -> list[dict]:
    pend = []
    for e in cargar_escenas()["escenas"]:
        if "prompt_clip" not in e or (DIR_FLOW / f"clip_{e['id']:03d}.mp4").exists():
            continue
        imagen = buscar_flow(e["id"])
        if not imagen:
            raise PipelineError(f"La escena {e['id']} tiene clip pero aún no tiene imagen de Flow.")
        pend.append({"escena": e["id"], "huella": huella(imagen), "prompt": e["prompt_clip"]})
    return pend


def importar_clip(cfg, escena: int) -> Path:
    """Mueve el .mp4 más reciente de Descargas (Flow lo nombra a su manera) a trabajo/flow/clip_NNN.mp4."""
    videos = sorted(_descargas(cfg).glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not videos or datetime.now().timestamp() - videos[-1].stat().st_mtime > 600:
        raise PipelineError("No hay un .mp4 descargado en los últimos 10 minutos.")
    destino = DIR_FLOW / f"clip_{escena:03d}.mp4"
    videos[-1].replace(destino)
    return destino


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = cargar_config(RAIZ / "config.json")
    accion = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if not VIDEO:
            raise PipelineError("No hay video actual; indica el nombre: python -m pipeline.flow exportar <video>")
        if accion == "exportar":
            d = exportar(cfg)
            print(f"video {VIDEO}, lote {d['lote']}: {len(d['escenas'])} imágenes pendientes -> {rel(PENDIENTES)}")
        elif accion == "progreso":
            hechas, total = progreso(cfg)
            print(f"{hechas}/{total}")
        elif accion == "importar":
            movidas, faltan = importar(cfg)
            print(f"video {VIDEO}: importadas {len(movidas)}; faltan: {faltan if faltan else 'ninguna'}")
        elif accion == "clips":
            pend = clips_pendientes(cfg)
            print(json.dumps(pend, ensure_ascii=False, indent=1))
            print(f"video {VIDEO}: {len(pend)} clips pendientes")
        elif accion == "clip":
            print(f"video {VIDEO}: {rel(importar_clip(cfg, int(sys.argv[2])))}")
        else:
            print(__doc__)
            sys.exit(2)
    except PipelineError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
