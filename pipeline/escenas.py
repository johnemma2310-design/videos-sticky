"""Paso 1: lee el guion, lo divide en frases y genera escenas.json.

Cada frase es una escena. Etiquetas opcionales dentro del guion (afectan a la frase en la que están):
    [[imagen=descripción de la ilustración; texto=Palabra clave; tarjeta=si]]
    [[escenario=bosque; accion=corre; rotulo=SCP-7741; criatura=si; movimiento=si]]  (dibujo de respaldo)

- imagen:  lo que debe mostrar la ilustración de Flow. Si el guion usa `imagen`, las frases sin
           `imagen` siguen mostrando la imagen anterior (otro encuadre), como un plano que continúa.
- texto:   palabra clave escrita a mano encima de la imagen (ej. "35 °C").
- tarjeta: ilustración sencilla sobre fondo blanco, con espacio para el texto.
- short:   `short=1` (o `short=1|Título`) donde empieza un Short vertical y `short=fin` donde termina.
- clip:    movimiento para animar esa ilustración en Flow (video de 3 s, cuesta puntos); el clip
           abre la escena y luego sigue la imagen fija.

Definiciones (no se narran): `@Nombre: descripción` y luego `{Nombre}` dentro de `imagen`,
para que un personaje se dibuje siempre igual. `{Sticky}` sale de config.json.
Escenarios: laboratorio, bosque, ciudad, casa, oscuridad, documento, vacio
Acciones:   de_pie, habla, senala, asustado, piensa, corre
"""
import re
from datetime import datetime
from pathlib import Path

from .comun import PipelineError, guardar_escenas, rel

ESCENARIOS = ["laboratorio", "bosque", "ciudad", "casa", "oscuridad", "documento", "vacio"]
ACCIONES = ["de_pie", "habla", "senala", "asustado", "piensa", "corre"]

PALABRAS_ESCENARIO = [
    ("documento", ["documento", "archivo", "informe", "registro", "expediente", "clasificad", "nota", "carta", "diario"]),
    ("laboratorio", ["laboratorio", "fundación", "celda", "contención", "instalación", "científic", "investigador", "sitio-"]),
    ("bosque", ["bosque", "árbol", "arbol", "selva", "montaña", "campo", "lago"]),
    ("ciudad", ["ciudad", "calle", "edificio", "oficina", "pueblo", "avenida", "barrio"]),
    ("casa", ["casa", "habitación", "cuarto", "sala", "puerta", "ventana", "cocina", "sótano", "ascensor", "pasillo"]),
    ("oscuridad", ["oscur", "noche", "sombra", "apag", "negro", "hueco", "abismo"]),
]
PALABRAS_ACCION = [
    ("corre", ["corr", "huy", "escap", "persig", "perseg"]),
    ("asustado", ["miedo", "grit", "terror", "horror", "pánico", "panico", "aterr", "temblab"]),
    ("senala", ["mira", "observ", "encontr", "descubr", "vieron", "muestra", "cámara"]),
    ("piensa", ["pregunt", "nadie sabe", "extraño", "misterio", "por qué", "quizá", "tal vez"]),
]
PALABRAS_CRIATURA = ["criatura", "entidad", "monstruo", "bestia", "figura", "silueta", "anomalía"]
ROTULO_ESCENARIO = {
    "laboratorio": "ZONA DE CONTENCIÓN", "bosque": "ZONA EXTERIOR", "ciudad": "ZONA URBANA",
    "casa": "INTERIOR", "oscuridad": "SIN LUZ", "documento": "EXPEDIENTE", "vacio": "REGISTRO",
}
ABREVIATURAS = ["Dr.", "Dra.", "Sr.", "Sra.", "Srta.", "etc.", "aprox.", "No.", "núm.", "pág.", "Ud.", "Uds."]
TAG_RE = re.compile(r"\[\[(.*?)\]\]", re.S)
SCP_RE = re.compile(r"\bSCP-\d{2,4}(?:-[A-Z]{1,4})?\b")


def limpiar_markdown(texto: str) -> list[str]:
    """Devuelve párrafos de texto plano (sin títulos, comentarios ni formato)."""
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
    parrafos, actual = [], []
    for linea in texto.splitlines():
        l = linea.strip()
        if not l or l.startswith("#") or re.fullmatch(r"[-*_]{3,}", l):
            if actual:
                parrafos.append(" ".join(actual))
                actual = []
            continue
        l = re.sub(r"^>\s*", "", l)
        l = re.sub(r"^([-*+]|\d+[.)])\s+", "", l)
        l = re.sub(r"!?\[([^\[\]]+)\]\([^)]*\)", r"\1", l)  # enlaces
        l = re.sub(r"(\*\*|__|\*|`)", "", l)
        actual.append(l)
    if actual:
        parrafos.append(" ".join(actual))
    return parrafos


def dividir_frases(parrafo: str) -> list[str]:
    tags = []

    def guardar_tag(m):
        tags.append(m.group(0))
        return f"\x00{len(tags) - 1}\x00"

    p = TAG_RE.sub(guardar_tag, parrafo)
    for ab in ABREVIATURAS:
        p = p.replace(ab, ab.replace(".", "\x01"))
    partes = re.split(r"(?<=[.!?…])[\"”»']?\s+(?=[\x00¿¡\"“«A-ZÁÉÍÓÚÑ0-9])", p)
    frases = []
    for parte in partes:
        parte = parte.replace("\x01", ".")
        parte = re.sub(r"\x00(\d+)\x00", lambda m: tags[int(m.group(1))], parte)
        if parte.strip():
            frases.append(parte.strip())
    return frases


def leer_tags(frase: str) -> tuple[str, dict]:
    opciones = {}
    for bloque in TAG_RE.findall(frase):
        for item in bloque.split(";"):
            if "=" in item:
                k, v = item.split("=", 1)
                opciones[k.strip().lower()] = v.strip()
    limpio = re.sub(r"\s{2,}", " ", TAG_RE.sub("", frase)).strip()
    return limpio, opciones


def _mejor(texto_min: str, tabla, defecto: str) -> str:
    mejor, puntos = defecto, 0
    for nombre, palabras in tabla:
        n = sum(texto_min.count(p) for p in palabras)
        if n > puntos:
            mejor, puntos = nombre, n
    return mejor


def inferir_visual(texto: str, opciones: dict) -> dict:
    t = texto.lower()
    escenario = opciones.get("escenario") or _mejor(t, PALABRAS_ESCENARIO, "vacio")
    accion = opciones.get("accion") or _mejor(t, PALABRAS_ACCION, "habla")
    if escenario not in ESCENARIOS:
        raise PipelineError(f"Escenario desconocido '{escenario}' en la frase: {texto[:60]}…  Válidos: {ESCENARIOS}")
    if accion not in ACCIONES:
        raise PipelineError(f"Acción desconocida '{accion}' en la frase: {texto[:60]}…  Válidas: {ACCIONES}")
    si = lambda v: str(v).lower() in ("si", "sí", "true", "1", "yes")
    criatura = si(opciones["criatura"]) if "criatura" in opciones else any(p in t for p in PALABRAS_CRIATURA)
    movimiento = si(opciones["movimiento"]) if "movimiento" in opciones else accion == "corre"
    scp = SCP_RE.search(texto)
    rotulo = opciones.get("rotulo") or (scp.group(0) if scp else ROTULO_ESCENARIO[escenario])
    descripcion = (f"Escenario '{escenario}', personaje en pose '{accion}'"
                   + (", aparece la criatura" if criatura else "")
                   + (", animación de movimiento por código" if movimiento else ", imagen fija con zoom suave")
                   + f". Rótulo: {rotulo}")
    return {"escenario": escenario, "accion": accion, "criatura": criatura,
            "movimiento": movimiento, "rotulo": rotulo[:28], "descripcion": descripcion,
            "imagen": opciones.get("imagen", ""), "texto": opciones.get("texto", ""),
            "clip": opciones.get("clip", ""), "short": opciones.get("short", ""),
            "tarjeta": si(opciones.get("tarjeta", "no"))}


LUGAR = {
    "laboratorio": "una instalación de contención secreta con puertas metálicas y luces de emergencia",
    "bosque": "un bosque oscuro de noche con niebla",
    "ciudad": "una ciudad de noche con edificios y ventanas iluminadas",
    "casa": "el interior de una casa vieja y silenciosa",
    "oscuridad": "un lugar casi totalmente oscuro, con poca luz",
    "documento": "un escritorio con un expediente clasificado con partes tachadas",
    "vacio": "un espacio neblinoso e inquietante",
}
POSE = {
    "de_pie": "de pie, observando", "habla": "explicando con un gesto de la mano",
    "senala": "señalando algo con el brazo", "asustado": "aterrado, con los brazos levantados",
    "piensa": "pensativo, con la mano en el mentón", "corre": "corriendo asustado",
}


DEF_RE = re.compile(r"^@([\wÁÉÍÓÚÑáéíóúñ ]+):\s*(.+)$", re.M)
REF_RE = re.compile(r"\{([\wÁÉÍÓÚÑáéíóúñ ]+)\}")


def expandir(texto: str, defs: dict) -> tuple[str, list[str]]:
    """Cambia {Nombre} por Nombre y devuelve las descripciones de los nombres usados."""
    usados = []

    def cambiar(m):
        if m.group(1) not in defs:
            raise PipelineError(f"'{{{m.group(1)}}}' no está definido; agrega una línea '@{m.group(1)}: ...' al guion.")
        if m.group(1) not in usados:
            usados.append(m.group(1))
        return m.group(1)
    limpio = REF_RE.sub(cambiar, texto)
    return limpio, [f"{n}: {defs[n]}." for n in usados]


def prompt_flow(e: dict, cfg: dict, titulo: str, defs: dict) -> str:
    """Prompt para generar la imagen de la escena en Google Flow."""
    f, v = cfg["flow"], e["visual"]
    nombre = cfg["personaje"]["nombre"]
    estilo = f["estilo_tarjeta"] if v["tarjeta"] else f["estilo"]
    if v["imagen"]:
        imagen, descripciones = expandir(v["imagen"], defs)
        partes = [estilo, f"Escena: {imagen[0].upper()}{imagen[1:]}."]
        if descripciones:
            partes.append("Cómo es cada uno: " + " ".join(descripciones))
    else:
        # guion sin etiquetas `imagen`: se describe la escena a partir de lo narrado
        partes = [estilo, f"El protagonista es {nombre}, {f['personaje']}.",
                  f"Escena: {LUGAR[v['escenario']]}. {nombre} está {POSE[v['accion']]}."]
        if v["criatura"]:
            partes.append("Al fondo se ve una figura alta y oscura con ojos brillantes, sin detalles gore.")
        historia = re.sub(r"\s*\(.*?\)", "", titulo)
        partes.append(f"La ilustración muestra lo que se narra: \"{e['texto']}\" (historia: {historia}).")
    partes.append(f["sin_texto"])
    return " ".join(partes)


def generar(ruta_guion: Path, cfg: dict) -> dict:
    if not ruta_guion.exists():
        raise PipelineError(f"No existe el guion: {ruta_guion}")
    bruto = ruta_guion.read_text(encoding="utf-8")
    titulo = next((l.lstrip("# ").strip() for l in bruto.splitlines() if l.startswith("#")), ruta_guion.stem)
    defs = {cfg["personaje"]["nombre"]: cfg["flow"]["personaje"]}
    defs.update({k.strip(): v.strip() for k, v in DEF_RE.findall(bruto)})
    bruto = DEF_RE.sub("", bruto)
    ppm = cfg["duracion"]["palabras_por_minuto"]
    pausa = cfg["video"]["pausa_entre_escenas"]

    escenas = []
    for parrafo in limpiar_markdown(bruto):
        for frase in dividir_frases(parrafo):
            texto, opciones = leer_tags(frase)
            if not re.search(r"\w", texto):
                continue
            palabras = len(texto.split())
            escenas.append({
                "id": len(escenas) + 1,
                "texto": texto,
                "palabras": palabras,
                "duracion_estimada": round(max(1.5, palabras / ppm * 60) + pausa, 2),
                "visual": inferir_visual(texto, opciones),
            })
    if not escenas:
        raise PipelineError(f"El guion {ruta_guion.name} no produjo ninguna escena (¿está vacío?).")

    con_planos = any(e["visual"]["imagen"] for e in escenas)
    duenio = None
    for e in escenas:
        if con_planos and not e["visual"]["imagen"] and duenio:
            e["imagen_de"] = duenio  # el plano continúa: misma ilustración, otro encuadre
            continue
        duenio = e["id"]
        e["prompt"] = prompt_flow(e, cfg, titulo, defs)
        if e["visual"]["clip"]:
            movimiento, _ = expandir(e["visual"]["clip"], defs)
            e["prompt_clip"] = f"{movimiento[0].upper()}{movimiento[1:]}. {cfg['flow']['estilo_clip']}"

    datos = {
        "titulo": titulo,
        "guion": rel(ruta_guion),
        "generado": datetime.now().isoformat(timespec="seconds"),
        "duracion_estimada_total": round(sum(e["duracion_estimada"] for e in escenas), 1),
        "imagenes_distintas": sum(1 for e in escenas if "prompt" in e),
        "escenas": escenas,
    }
    guardar_escenas(datos)
    return datos
