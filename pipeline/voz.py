"""Paso 2: narración con edge-tts, un audio por escena, con el tiempo de cada palabra.

Las palabras sirven para los subtítulos palabra por palabra y para recortar el silencio que
edge-tts deja al principio y al final de cada audio (así no hay huecos entre frases).
"""
import asyncio
import json
import time

import edge_tts

from .comun import DIR_AUDIO, PipelineError, cargar_escenas, duracion_media, guardar_escenas, rel


async def _sintetizar(texto, cfg_voz, destino):
    com = edge_tts.Communicate(texto, cfg_voz["nombre"], rate=cfg_voz["velocidad"], pitch=cfg_voz["tono"],
                               volume=cfg_voz["volumen"], boundary="WordBoundary")
    palabras = []
    with open(destino, "wb") as f:
        async for trozo in com.stream():
            if trozo["type"] == "audio":
                f.write(trozo["data"])
            elif trozo["type"] == "WordBoundary":
                ini = trozo["offset"] / 1e7  # unidades de 100 ns
                palabras.append({"p": trozo["text"], "ini": round(ini, 3),
                                 "fin": round(ini + trozo["duration"] / 1e7, 3)})
    return palabras


def generar(cfg: dict, log=print) -> dict:
    datos = cargar_escenas()
    cv = cfg["voz"]
    fps = cfg["video"]["fps"]
    pausa = cfg["video"]["pausa_entre_escenas"]
    margen = cfg["voz"].get("margen_s", 0.06)
    for e in datos["escenas"]:
        destino = DIR_AUDIO / f"escena_{e['id']:03d}.mp3"
        firma = DIR_AUDIO / f"escena_{e['id']:03d}.txt"
        ruta_palabras = DIR_AUDIO / f"escena_{e['id']:03d}_palabras.json"
        clave = f"{cv['nombre']}|{cv['velocidad']}|{cv['tono']}|{cv['volumen']}|{e['texto']}"
        reutilizar = (destino.exists() and ruta_palabras.exists() and firma.exists()
                      and firma.read_text(encoding="utf-8") == clave)
        if not reutilizar:
            ultimo_error = None
            for intento in range(1, cv.get("reintentos", 3) + 1):
                try:
                    palabras = asyncio.run(_sintetizar(e["texto"], cv, destino))
                    if destino.exists() and destino.stat().st_size > 1000 and palabras:
                        break
                    ultimo_error = "audio vacío o sin palabras"
                except Exception as ex:  # red, voz inválida, etc.
                    ultimo_error = f"{type(ex).__name__}: {ex}"
                time.sleep(2 * intento)
            else:
                raise PipelineError(f"edge-tts no pudo generar el audio de la escena {e['id']}: {ultimo_error}")
            ruta_palabras.write_text(json.dumps(palabras, ensure_ascii=False), encoding="utf-8")
            firma.write_text(clave, encoding="utf-8")
        palabras = json.loads(ruta_palabras.read_text(encoding="utf-8"))
        dur_archivo = duracion_media(destino)
        if dur_archivo < 0.2:
            raise PipelineError(f"El audio de la escena {e['id']} dura {dur_archivo:.2f}s; parece vacío.")
        # se usa solo el tramo hablado: del inicio de la primera palabra al final de la última
        recorte = max(0.0, palabras[0]["ini"] - margen)
        dur = min(dur_archivo, palabras[-1]["fin"] + margen + 0.1) - recorte
        e["palabras"] = [{"p": w["p"], "ini": round(w["ini"] - recorte, 3), "fin": round(w["fin"] - recorte, 3)}
                         for w in palabras]
        extra = cfg.get("quiz", {}).get("cuenta_s", 3.6) if e["visual"].get("anim", "").startswith("quiz") else 0.0
        frames = max(1, round((dur + pausa + extra) * fps))
        e["audio"] = rel(destino)
        e["recorte_audio"] = round(recorte, 3)
        e["duracion_audio"] = round(dur, 3)
        e["frames"] = frames
        e["duracion"] = round(frames / fps, 4)
        log(f"  voz {e['id']:03d}: {dur:5.2f}s {'(reutilizado)' if reutilizar else ''}")
    datos["duracion_total"] = round(sum(e["duracion"] for e in datos["escenas"]), 2)
    guardar_escenas(datos)
    return datos
