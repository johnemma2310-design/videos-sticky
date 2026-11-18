"""Pipeline de videos stickman: guion -> escenas -> voz -> imágenes -> montaje -> verificación.

Cada video tiene su carpeta videos/<nombre>/ con guion.md; ahí quedan trabajo/, video.mp4,
video.srt (para subir como subtítulos a YouTube) y reporte.md.

Uso:
    python generar_video.py la-patasola                      # todo el pipeline
    python generar_video.py la-patasola --hasta voz          # se detiene después de un paso
    python generar_video.py la-patasola --desde imagenes     # retoma desde un paso
    python generar_video.py la-patasola --prueba             # la duración 10-15 min solo da aviso

Si un paso falla, el pipeline se detiene y muestra qué falló.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PASOS = ["escenas", "voz", "imagenes", "montaje", "verificar"]
RAIZ = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", help="nombre de la carpeta en videos/ (ej. la-patasola)")
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--prueba", action="store_true", help="no exige 10-15 min (solo avisa)")
    ap.add_argument("--desde", choices=PASOS, default="escenas")
    ap.add_argument("--hasta", choices=PASOS, default="verificar")
    args = ap.parse_args()

    # el nombre del video fija las rutas de pipeline/comun.py, así que va antes de importar el pipeline
    os.environ["VIDEO_STICK"] = args.video
    (RAIZ / "videos").mkdir(exist_ok=True)
    (RAIZ / "videos" / ".actual").write_text(args.video, encoding="utf-8")

    from pipeline import escenas, imagenes, montaje, verificar, voz
    from pipeline.comun import GUION, PipelineError, cargar_config, preparar_carpetas

    paso = "config"
    try:
        cfg = cargar_config(RAIZ / args.config)
        preparar_carpetas()
        for paso in PASOS[PASOS.index(args.desde):PASOS.index(args.hasta) + 1]:
            t0 = time.time()
            print(f"\n== {paso} ==")
            if paso == "escenas":
                d = escenas.generar(GUION, cfg)
                print(f"  {len(d['escenas'])} escenas ({d['imagenes_distintas']} imágenes distintas), "
                      f"duración estimada {d['duracion_estimada_total']:.1f}s")
            elif paso == "voz":
                d = voz.generar(cfg)
                print(f"  duración real con pausas: {d['duracion_total']:.1f}s")
            elif paso == "imagenes":
                imagenes.generar(cfg)
            elif paso == "montaje":
                d = montaje.generar(cfg)
                print(f"  videos/{args.video}/video.mp4: {d['duracion_video']:.2f}s")
            elif paso == "verificar":
                ok = verificar.generar(cfg, prueba=args.prueba)
                print(f"  reporte -> videos/{args.video}/reporte.md")
                if not ok:
                    raise PipelineError("La verificación encontró errores (ver reporte.md).")
            print(f"  ({time.time() - t0:.1f}s)")
    except PipelineError as e:
        print(f"\nPIPELINE DETENIDO en el paso '{paso}':\n{e}", file=sys.stderr)
        sys.exit(1)
    print(f"\nListo: videos/{args.video}/video.mp4" if args.hasta == "verificar"
          else f"\nListo hasta el paso '{args.hasta}'.")


if __name__ == "__main__":
    main()
