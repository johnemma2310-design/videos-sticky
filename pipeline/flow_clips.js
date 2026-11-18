// Ayudante para animar ilustraciones en Google Flow (Video → Fotogramas, 720p, 3 s, x1 = 9 puntos).
// Se inyecta con javascript_tool en la página del proyecto. Por cada clip (lista de `python -m pipeline.flow clips`):
//   1) clic real en el recuadro "Inicio" del cuadro de prompt → se abre "Selecciona una imagen de encuadre"
//   2) await flowClips.buscar('<huella>')  → {d, titulo, x, y}: d = diferencia (0-64, bien si <= 8); clic real en
//      (x, y). Si no trae x/y, la lista se pasó: volver a buscar la opción por su `titulo` y centrarla.
//   3) clic real en "Añadir a petición"
//   4) await flowClips.escribir('<prompt>') y clic real (ref) en "Iniciar generación"
//   5) await flowClips.esperar()  → 'LISTO <título>' cuando el video nuevo está primero en la cuadrícula (~40 s)
//   6) menú "Más opciones" de ese video → Descargar → 720p (tamaño original); luego `python -m pipeline.flow clip NNN`
// No usar "Subir archivo": pide aceptar un aviso de derechos que el usuario no aprobó.
(() => {
  const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
  const huellas = (window.__huellas = window.__huellas || {});
  const primera = () => document.querySelector('flow-grid-tile-container');
  let tituloAntes = '';

  async function huella(src) {
    if (huellas[src]) return huellas[src];
    const bm = await createImageBitmap(await (await fetch(src, { credentials: 'include' })).blob());
    const c = document.createElement('canvas');
    c.width = 9; c.height = 8;
    const x = c.getContext('2d');
    x.imageSmoothingQuality = 'high';
    x.drawImage(bm, 0, 0, 9, 8);
    const d = x.getImageData(0, 0, 9, 8).data;
    const g = [];
    for (let i = 0; i < d.length; i += 4) g.push(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]);
    let h = '';
    for (let r = 0; r < 8; r++) for (let k = 0; k < 8; k++) h += g[r * 9 + k] > g[r * 9 + k + 1] ? '1' : '0';
    return (huellas[src] = h);
  }

  window.flowClips = {
    async buscar(objetivo) {
      const lb = document.querySelector('[role=listbox][aria-label="Lista de recursos"]');
      if (!lb) return JSON.stringify({ error: 'no está abierto el selector de imagen de encuadre' });
      const dist = (a, b) => [...a].filter((ch, i) => ch !== b[i]).length;
      let mejor = { d: 99 };
      for (let y = 0; y <= lb.scrollHeight; y += 300) {
        lb.scrollTop = y;
        await dormir(400);
        for (const o of lb.querySelectorAll('[role=option]')) {
          const img = o.querySelector('img');
          if (!img || !img.src) continue;
          const d = dist(await huella(img.src), objetivo);
          if (d < mejor.d) mejor = { d, src: img.src, titulo: o.innerText.slice(0, 40) };
        }
        if (mejor.d <= 4) break;
      }
      const o = [...lb.querySelectorAll('[role=option]')].find((o) => (o.querySelector('img') || {}).src === mejor.src);
      if (o) {
        o.scrollIntoView({ block: 'center' });
        await dormir(300);
        const r = o.getBoundingClientRect();
        mejor.x = Math.round(r.left + r.width / 2);
        mejor.y = Math.round(r.top + r.height / 2);
      }
      delete mejor.src;
      return JSON.stringify(mejor);
    },
    async escribir(prompt) {
      const ed = document.querySelector('[role=textbox][contenteditable=true][aria-label="¿Qué quieres crear?"]');
      if (!ed) return 'ERROR: no encuentro el cuadro de prompt';
      if (!document.querySelector('[alt="Imagen del ingrediente"], [aria-label="Imagen del ingrediente"]'))
        return 'ERROR: falta la imagen de Inicio';
      tituloAntes = primera() ? primera().getAttribute('aria-label') : '';
      ed.focus();
      document.execCommand('selectAll');
      document.execCommand('insertText', false, prompt);
      await dormir(600);
      const b = document.querySelector('button[aria-label="Iniciar generación"]');
      return b && !b.disabled ? 'LISTO_PARA_CLIC' : 'ERROR: botón desactivado';
    },
    async esperar(maxMs = 40000) {
      const t0 = Date.now();
      while (Date.now() - t0 < maxMs) {
        await dormir(2000);
        if (/infringir nuestras pol/.test(document.body.innerText.slice(0, 4000))) return 'RECHAZADO';
        // el video nuevo queda primero en la cuadrícula; está listo cuando tiene miniatura y título propio
        const t = primera();
        if (t && t.querySelector('img[alt="Miniatura de vídeo generada"]') && t.getAttribute('aria-label') !== tituloAntes)
          return 'LISTO ' + t.getAttribute('aria-label');
      }
      return 'TARDA';
    },
  };
  return 'flowClips listo';
})();
