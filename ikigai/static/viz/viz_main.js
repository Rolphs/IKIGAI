/* viz_main.js - Entry point del visualizador (slim v0.3.0+)
 *
 * Funciones varias (export SVG, autosave del resumen) + el handler de
 * DOMContentLoaded que arma todo el wire-up inicial. Este archivo DEBE
 * cargarse al final (despues de los demas modulos viz_*.js).
 *
 * Refactor v0.3.0:
 *   - Eliminado: setupItemEditing (chips read-only en la viz; editar en /inventario)
 *   - Eliminado: setupVizPickerAutoClose (no mas multi-viz tabs)
 *   - Eliminado: drag handlers de item-chips (items son derivados, no asignables)
 *   - Eliminado: btn-auto (sin sentido cuando los items son auto-derivados)
 *   - URLs simplificadas: sin segmento /viz_name (siempre "default" implicito)
 */

// --- Exportar Venn como SVG (claro, con callouts) ---
// Baja el SVG del endpoint /visualizador/venn.svg, que reusa la MISMA
// plantilla que el snapshot HTML (_venn4_svg.html.j2). Asi el archivo no
// trunca ni una palabra: cada region apunta a su nombre completo afuera.
// (El Venn EN PANTALLA si abrevia, porque debe caber en las regiones
//  diminutas; el export es la version imprimible/clara.)
async function exportSvg() {
  const btn = document.getElementById("btn-export-svg");
  if (btn) btn.disabled = true;
  try {
    const r = await fetch(`${window.IKIGAI_URL}/visualizador/venn.svg`);
    if (!r.ok) throw new Error("HTTP " + r.status);
    const svgText = await r.text();
    const blob = new Blob([svgText], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const ts = new Date().toISOString().slice(0, 10);
    const titleSlug = ((window.VIZ && window.VIZ.title) || "venn").toLowerCase().replace(/\s+/g, "-");
    a.download = "ikigai-" + titleSlug + "-" + ts + ".svg";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    if (typeof showToast === "function") showToast("SVG exportado (nombres completos)", "success");
  } catch (e) {
    if (typeof showToast === "function") showToast("Error exportando SVG: " + e.message, "error");
    else alert("Error exportando SVG: " + e.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

// --- Resumen ejecutivo: autosave debounced ---
let _summaryTimer = null;
function setupSummaryAutosave() {
  const ta = document.getElementById("viz-summary");
  const status = document.getElementById("viz-summary-status");
  if (!ta) return;
  ta.addEventListener("input", function () {
    status.textContent = "escribiendo...";
    clearTimeout(_summaryTimer);
    _summaryTimer = setTimeout(async function () {
      status.textContent = "guardando...";
      try {
        const r = await fetch(`${window.IKIGAI_URL}/visualizador/summary`, {
          method: "PATCH",
          body: form({ summary: ta.value }),
        });
        if (!r.ok) throw new Error("HTTP " + r.status);
        status.textContent = "guardado";
        showToast("Resumen actualizado", "success");
        setTimeout(function () { status.textContent = ""; }, 1500);
      } catch (e) {
        status.textContent = "error: " + e.message;
        showToast("Error guardando resumen", "error");
      }
    }, 500);
  });
}

// --- Barra de progreso de síntesis ---
function updateSynthesisProgress() {
  const regions = window.VIZ.regions || {};
  const keys = Object.keys(regions).filter(k => k !== 'out');
  const total = keys.length;
  const named = keys.filter(k => regions[k].concept && regions[k].concept.trim()).length;
  
  const pct = total > 0 ? (named / total) * 100 : 0;
  const bar = document.getElementById('synthesis-progress-bar');
  const text = document.getElementById('synthesis-progress-text');
  
  if (bar) bar.style.width = `${pct}%`;
  if (text) text.textContent = `${named}/${total}`;
}

// --- Wire-up inicial ---
document.addEventListener("DOMContentLoaded", async function () {
  window.VIZ = await fetchJSON(`${window.IKIGAI_URL}/visualizador/data`);
  renderViz(window.VIZ);
  updateSynthesisProgress();

  // Marca inactivos y reordena cajones (activos arriba). Sin animacion inicial.
  const cats = window.VIZ.categories || [];
  document.querySelectorAll(".cajon").forEach(function (d) {
    d.dataset.inactive = cats.includes(d.dataset.csvValue) ? "" : "1";
  });
  reorderCajonesByActive();

  // Reordenar pills activos al frente segun viz.categories + wire-up de drag-reorder
  reorderPillsByViz();
  setupCatPillDragReorder();
  setupSummaryAutosave();

  // Botones del header
  const expBtn = document.getElementById("btn-export-svg");
  if (expBtn) expBtn.addEventListener("click", exportSvg);

  // Pills: click toggla activo + actualiza aria-pressed + dispara updateCategories.
  document.querySelectorAll(".cat-pill").forEach(function (p) {
    p.addEventListener("click", function () {
      p.classList.toggle("active");
      p.setAttribute("aria-pressed", p.classList.contains("active") ? "true" : "false");
      updateCategories();
    });
  });

  // Region editor: concept input -> save on blur/enter
  const conceptInput = document.getElementById("region-concept");
  if (conceptInput) {
    conceptInput.addEventListener("blur", function () {
      saveConcept();
      // Refresh data + render para que el badge de "concepto definido" actualice.
      refreshAndRender();
    });
    conceptInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); conceptInput.blur(); }
    });
  }

  // Close editor
  const closeBtn = document.getElementById("region-close");
  if (closeBtn) closeBtn.addEventListener("click", closeEditor);

  // Outside-click & ESC: cerrar el drawer cuando el usuario clickea fuera.
  setupOutsideClickToCloseEditor();
});

/** Cierra el #region-editor cuando el usuario clickea fuera de el (y de la
 * Venn, que ya tiene su propio handler para SWITCH-de-region). Tambien ESC.
 *
 * Se llama una sola vez en wire-up. El handler vive en document para que
 * funcione sin importar donde clickee el usuario, y se hace no-op cuando
 * el drawer esta cerrado para evitar trabajo inutil.
 */
function setupOutsideClickToCloseEditor() {
  const editor = document.getElementById("region-editor");
  if (!editor) return;

  // Click anywhere outside the editor closes it (UX expectation comun).
  document.addEventListener("click", function (e) {
    // No-op si el drawer esta cerrado.
    if (editor.classList.contains("translate-y-full")) return;
    // Click dentro del drawer: dejar pasar.
    if (editor.contains(e.target)) return;
    // Click en una region de la Venn: dejar pasar para que activateRegion
    // cambie de region sin flicker (cerrar -> reabrir en otra region).
    if (e.target.closest && e.target.closest(".venn-region, .venn-out-zone")) return;
    closeEditor();
  });

  // ESC tambien cierra (estandar de UI).
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (editor.classList.contains("translate-y-full")) return;
    // Si el foco esta en un input editable, primero quitar foco; un
    // segundo ESC cerrara. Asi no perdemos texto a medio escribir.
    const active = document.activeElement;
    if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA")) {
      active.blur();
      return;
    }
    closeEditor();
  });
}

/** Recarga window.VIZ desde /data y re-renderiza. Util tras guardar concept. */
async function refreshAndRender() {
  try {
    window.VIZ = await fetchJSON(`${window.IKIGAI_URL}/visualizador/data`);
    renderViz(window.VIZ);
    updateSynthesisProgress();
    if (window.ACTIVE_REGION) activateRegion(window.ACTIVE_REGION);
  } catch (e) { /* silencio: no critico */ }
}

window.exportSvg = exportSvg;
window.refreshAndRender = refreshAndRender;
