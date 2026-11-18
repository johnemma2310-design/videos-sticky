// Ayudante que corre DENTRO de la página de un proyecto de Google Flow (flow.google.com/project/...).
// Flow solo acepta un clic REAL en "Iniciar generación" (ignora clics simulados por código), así que:
//   1) flowRunner.preparar()  -> escribe el prompt de la siguiente escena (devuelve el archivo o "FIN")
//   2) clic real en el botón "Iniciar generación" (herramienta computer de Claude in Chrome)
//   3) await flowRunner.esperar() -> espera la imagen nueva, la descarga con su nombre y avanza
// La lista se carga subiendo videos/<video>/trabajo/flow_pendientes.json al <input id="flowRunnerArchivo">.
// El clic debe ir al ref del botón (find), nunca a coordenadas: un clic en la cuadrícula abre una imagen.
// Requisitos en Flow: modo Imagen, Nano Banana, 16:9, x1, "Agente" desactivado.
(() => {
  const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
  const editor = () => document.querySelector('[role=textbox][contenteditable=true][aria-label="¿Qué quieres crear?"]');
  const boton = () => document.querySelector('button[aria-label="Iniciar generación"]');
  const imagenes = () => [...document.querySelectorAll('img')].filter((i) => i.complete && i.naturalWidth >= 1000);
  const vistas = new Set();
  // marca TODAS las imágenes de la página, aunque no hayan terminado de cargar: si no, una imagen
  // vieja que carga tarde (lazy) parecería nueva y se descargaría con el nombre equivocado
  const marcarVistas = () => document.querySelectorAll('img').forEach((i) => i.src && vistas.add(i.src));
  const anterior = window.flowRunner;

  const E = (window.flowRunner = {
    lote: null, lista: [], indice: 0, hechos: [], fallos: [], log: [],
    resumen() {
      return { lote: this.lote, hechos: this.hechos.length, total: this.lista.length, siguiente: this.indice + 1,
               fallos: this.fallos, ultimo: this.log.slice(-2) };
    },
  });
  if (anterior && anterior.lista && anterior.lista.length) Object.assign(E, {
    lote: anterior.lote, lista: anterior.lista, indice: anterior.indice, hechos: anterior.hechos, fallos: anterior.fallos,
  });
  const anotar = (m) => { E.log.push(new Date().toLocaleTimeString() + ' ' + m); if (E.log.length > 100) E.log.shift(); };

  async function descargar(img, nombre) {
    const blob = await (await fetch(img.src, { credentials: 'include' })).blob();
    if (blob.size < 20000) throw new Error('imagen demasiado pequeña');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
    return blob.size;
  }

  // si se abre una imagen (vista /edit/), su imagen grande parecería nueva y se guardaría mal
  const enEdicion = () => location.pathname.includes('/edit/');
  // Flow muestra una tarjeta "podría infringir nuestras políticas" cuando rechaza un prompt
  const rechazos = () => (document.body.innerText.match(/infringir nuestras pol/g) || []).length;
  let rechazosAntes = 0;

  E.preparar = async () => {
    if (E.indice >= E.lista.length) return 'FIN';
    if (enEdicion()) return 'ERROR: hay una imagen abierta; vuelve a la cuadrícula del proyecto';
    let ed = null;
    for (let k = 0; k < 60 && !(ed = editor()); k++) await dormir(500);
    if (!ed) return 'ERROR: no encuentro el cuadro de prompt';
    marcarVistas();
    rechazosAntes = rechazos();
    ed.focus();
    document.execCommand('selectAll');
    document.execCommand('insertText', false, E.lista[E.indice].prompt);
    for (let k = 0; k < 40 && (!boton() || boton().disabled); k++) await dormir(250);
    return boton() && !boton().disabled ? E.lista[E.indice].archivo : 'ERROR: botón desactivado';
  };

  // Espera hasta maxMs la imagen nueva; si no llega, deja la escena para reintentar.
  E.esperar = async (maxMs = 100000) => {
    const item = E.lista[E.indice];
    if (!item) return 'FIN';
    // Flow a veces deja el prompt en el cuadro después de enviar, así que no sirve para saber si se envió:
    // si el clic no llegó, esperar() devuelve TARDA y hay que repetir el clic.
    const t0 = Date.now();
    while (Date.now() - t0 < maxMs) {
      await dormir(2000);
      if (enEdicion()) return 'ERROR: se abrió una imagen; vuelve a la cuadrícula y repite la escena';
      if (rechazos() > rechazosAntes) {
        // a veces el aviso es de otra tarjeta y la imagen llega igual: esperar y descartarla, para que
        // no la tome la escena siguiente (eso corrió una posición varias imágenes)
        await dormir(20000);
        marcarVistas();
        E.fallos.push(item.archivo);
        E.indice++;
        anotar('rechazada ' + item.archivo);
        return 'RECHAZADA por Flow: ' + item.archivo + ' (se salta; cambia su imagen en el guion)';
      }
      const nuevas = imagenes().filter((i) => !vistas.has(i.src));
      if (nuevas.length) {
        nuevas.sort((a, b) => {
          const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
          return ra.top - rb.top || ra.left - rb.left;
        });
        await dormir(1500);
        try {
          const tam = await descargar(nuevas[0], item.archivo);
          nuevas.forEach((i) => vistas.add(i.src));
          E.hechos.push(item.archivo);
          E.indice++;
          anotar('ok ' + item.archivo);
          return 'OK ' + item.archivo + ' (' + Math.round(tam / 1024) + ' KB) ' + E.hechos.length + '/' + E.lista.length;
        } catch (e) {
          anotar('error descarga ' + item.archivo + ': ' + e.message);
          return 'ERROR descarga: ' + e.message;
        }
      }
    }
    return 'TARDA: ' + item.archivo + ' aún no aparece; llama esperar() otra vez o salta()';
  };

  E.saltar = () => { const it = E.lista[E.indice]; if (it) { E.fallos.push(it.archivo); E.indice++; } return E.resumen(); };

  let input = document.getElementById('flowRunnerArchivo');
  if (!input) {
    input = document.createElement('input');
    input.type = 'file';
    input.id = 'flowRunnerArchivo';
    input.accept = '.json';
    input.setAttribute('aria-label', 'Lista de prompts flowRunner');
    input.style.cssText = 'position:fixed;top:4px;left:50%;z-index:99999;width:220px;opacity:.9';
    document.body.appendChild(input);
  }
  input.onchange = async () => {
    const datos = JSON.parse(await input.files[0].text());
    Object.assign(E, { lote: datos.lote, lista: datos.escenas, indice: 0, hechos: [], fallos: [] });
    anotar('lista cargada: ' + datos.escenas.length + ' (lote ' + datos.lote + ')');
    input.remove();
  };
  return 'flowRunner listo';
})();
