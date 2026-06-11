/* ═══════════════════════════════════════════════════════════════════
 * viz_sidebar.js — Pills de categorías + reorder de pills/cajones
 *
 * El orden DOM de los pills activos determina el orden de viz.categories,
 * que a su vez determina las letras a,b,c,d del Venn. Reordenar pills =
 * cambiar qué cuadrante es 'a' (foco del set).
 *
 * Los pills/cajones inactivos bajan al final con animación FLIP, dando una
 * jerarquía visual clara entre lo elegido y lo no elegido.
 *
 * Dependencias externas:
 *   - window.VIZ, window.VIZ_NAME (estado)
 *   - fetchJSON, form (viz_helpers)
 *   - renderViz (viz_geometry)
 *   - closeEditor (viz_regions)
 * ═══════════════════════════════════════════════════════════════════ */

/* ─── Serial queue para updateCategories ───
 *
 * Race condition documentada (audit QA Kitten round 2):
 *   Clicks rapidos en cat-pills disparaban N requests POST en paralelo a
 *   /visualizador/{name}/categories. El backend (sin lock) escribia el YAML
 *   sin serializar, devolviendo a veces HTTP 500 y dejando UI en estado
 *   inconsistente con el server.
 *
 * Fix de dos lados:
 *   - backend: viz_lock(name) en server.py + atomic replace en save_visualization
 *   - frontend (este): solo UN request en vuelo a la vez; si el usuario
 *     hace mas clicks mientras corre, marcamos "pending" y al terminar
 *     ejecutamos UNA UNICA vez mas con el DOM actual. Asi 10 clicks rapidos
 *     = 2 requests (uno actual + uno final), no 10.
 */
let _updateInFlight = false;
let _updatePending = false;

async function updateCategories() {
  if (_updateInFlight) {
    // Otro request ya esta corriendo. Marcamos que hay que re-ejecutar al
    // terminar (coalescente: multiples marcas se colapsan en una sola run).
    _updatePending = true;
    return;
  }
  _updateInFlight = true;
  try {
    await _doUpdateCategories();
  } finally {
    _updateInFlight = false;
    if (_updatePending) {
      _updatePending = false;
      // Re-disparar con el estado actual del DOM (puede haber cambiado
      // mientras corria la run anterior). Sin await para no bloquear.
      updateCategories();
    }
  }
}

async function _doUpdateCategories() {
  // 1) Reorder pills INMEDIATAMENTE (FLIP) para feedback sin latencia.
  reorderPillsByActive();

  const selected = [...document.querySelectorAll(".cat-pill.active")]
    .map(el => el.dataset.csvValue);
  const status = document.getElementById("cat-warning");
  document.getElementById("cat-count").textContent = selected.length;

  if (selected.length > 4) {
    status.classList.remove("hidden");
    return;
  }
  status.classList.add("hidden");

  const resp = await fetch(`${window.IKIGAI_URL}/visualizador/categories`, {
    method: "POST",
    body: form({ categories: selected.join(",") }),
  });
  if (!resp.ok) {
    // Server rechazo: NO re-renderizamos con data stale. Mostramos el detalle
    // del backend para que el bug sea visible (no silencioso).
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    status.textContent = `⚠️ ${err.detail || resp.statusText}`;
    status.classList.remove("hidden");
    return;
  }
  // Reload viz state
  window.VIZ = await fetchJSON(`${window.IKIGAI_URL}/visualizador/data`);
  renderViz(window.VIZ);
  // Cerrar editor: las regiones pueden haber cambiado.
  closeEditor();
  // Update header counter (con pluralizacion: "1 circulo" vs "3 circulos")
  const countEl = document.getElementById("circle-count");
  if (countEl) {
    const n = selected.length;
    countEl.textContent = `(${n} círculo${n === 1 ? '' : 's'})`;
  }
  // Update cajones: marca activos/inactivos + reordena (FLIP)
  document.querySelectorAll(".cajon").forEach(d => {
    d.dataset.inactive = selected.includes(d.dataset.csvValue) ? "" : "1";
  });
  reorderCajonesByActive();
}

/**
 * Reordena pills: activos primero (orden DOM actual), inactivos al final.
 * Animación FLIP (First-Last-Invert-Play).
 */
function reorderPillsByActive() {
  const container = document.getElementById("cat-selector");
  if (!container) return;
  const pills = [...container.querySelectorAll(".cat-pill")];
  if (pills.length === 0) return;

  // FIRST: medir
  const before = new Map();
  pills.forEach(p => before.set(p, p.getBoundingClientRect()));

  // Particiona conservando orden interno de cada grupo (drag manual se respeta).
  const active   = pills.filter(p => p.classList.contains("active"));
  const inactive = pills.filter(p => !p.classList.contains("active"));
  [...active, ...inactive].forEach(p => container.appendChild(p));

  // LAST + INVERT + PLAY
  pills.forEach(p => {
    const after = p.getBoundingClientRect();
    const dx = before.get(p).left - after.left;
    const dy = before.get(p).top  - after.top;
    if (dx === 0 && dy === 0) return;
    p.style.transition = "none";
    p.style.transform  = `translate(${dx}px, ${dy}px)`;
    void p.offsetWidth;  // forzar reflow para que el snap aplique antes de animar
    p.classList.add("cat-pill-animating");
    p.style.transition = "";
    p.style.transform  = "";
  });
}

/**
 * Al cargar la página: pone activos al frente en el ORDEN exacto de
 * viz.categories (que viene del YAML). Sin animación.
 */
function reorderPillsByViz() {
  const container = document.getElementById("cat-selector");
  const cats = window.VIZ?.categories || [];
  cats.slice().reverse().forEach(csv => {
    const pill = container.querySelector(`.cat-pill[data-csv-value="${csv}"]`);
    if (pill) container.prepend(pill);
  });
  // Inactivos al final
  const pills = [...container.querySelectorAll(".cat-pill")];
  pills.filter(p => !p.classList.contains("active")).forEach(p => container.appendChild(p));
}

function setupCatPillDragReorder() {
  const container = document.getElementById("cat-selector");
  if (!container) return;
  let dragged = null;
  container.querySelectorAll(".cat-pill").forEach(pill => {
    pill.addEventListener("dragstart", ev => {
      dragged = pill;
      pill.classList.add("opacity-50");
      ev.dataTransfer.effectAllowed = "move";
      ev.dataTransfer.setData("text/plain", pill.dataset.csvValue);
    });
    pill.addEventListener("dragend", () => {
      pill.classList.remove("opacity-50");
      dragged = null;
    });
    pill.addEventListener("dragover", ev => {
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "move";
    });
    pill.addEventListener("drop", ev => {
      ev.preventDefault();
      if (!dragged || dragged === pill) return;
      const rect = pill.getBoundingClientRect();
      const after = (ev.clientX - rect.left) > rect.width / 2;
      pill.parentNode.insertBefore(dragged, after ? pill.nextSibling : pill);
      if (dragged.classList.contains("active")) updateCategories();
    });
  });
}

/**
 * Reordena cajones (sidebar derecho): activos arriba en el ORDEN de
 * viz.categories (= orden a,b,c,d del Venn), inactivos atenuados al final.
 * Animación FLIP. Idéntico patrón que reorderPillsByActive.
 */
function reorderCajonesByActive() {
  const container = document.querySelector("aside");
  if (!container) return;
  const cajones = [...container.querySelectorAll(".cajon")];
  if (cajones.length === 0) return;

  const before = new Map();
  cajones.forEach(c => before.set(c, c.getBoundingClientRect()));

  const cats = window.VIZ?.categories || [];
  const active = cajones
    .filter(c => !c.dataset.inactive)
    .sort((a, b) => {
      const ai = cats.indexOf(a.dataset.csvValue);
      const bi = cats.indexOf(b.dataset.csvValue);
      return (ai < 0 ? 999 : ai) - (bi < 0 ? 999 : bi);
    });
  const inactive = cajones.filter(c => c.dataset.inactive);
  [...active, ...inactive].forEach(c => container.appendChild(c));

  cajones.forEach(c => {
    const after = c.getBoundingClientRect();
    const dy = before.get(c).top - after.top;
    if (dy === 0) return;
    c.style.transition = "none";
    c.style.transform  = `translateY(${dy}px)`;
    void c.offsetWidth;
    c.classList.add("cajon-animating");
    c.style.transition = "";
    c.style.transform  = "";
  });
}

// Exponer para otros módulos.
window.updateCategories = updateCategories;
window.reorderPillsByActive = reorderPillsByActive;
window.reorderPillsByViz = reorderPillsByViz;
window.setupCatPillDragReorder = setupCatPillDragReorder;
window.reorderCajonesByActive = reorderCajonesByActive;
