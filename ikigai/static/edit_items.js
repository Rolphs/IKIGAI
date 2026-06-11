/**
 * edit_items.js — Modulo compartido entre /inventario y /visualizador.
 *
 * Expone window.EditItems con:
 *   - showToast(msg)              feedback flotante (auto-hide 5s)
 *   - pushUndo(entry)             agrega al stack LIFO (max 5)
 *   - undo()                      pop + fetch restore + re-render via callback
 *   - registerOnRestore(fn)       fn(entry, htmlFragment) tras restore exitoso
 *   - editInline(span, li, opts)  doble-click inline edit. opts.onSaved(newText)
 *   - deleteItem(li, opts)        DELETE + push al undo. opts.onDeleted()
 *   - addItem(cuadrante, text)    POST y devuelve {id, html} promise
 *   - bindGlobalShortcuts()       Ctrl+Z global (ignora inputs/textareas)
 *
 * Endpoints que consume (ya existen en server.py):
 *   POST   /inventario/item          (cuadrante, item_text) -> HTML fragmento
 *   PATCH  /inventario/item/{id}     (item_text)            -> JSON {id, item}
 *   DELETE /inventario/item/{id}                            -> 200
 *   POST   /inventario/item/restore  (item_id, cuadrante, item_text) -> HTML fragmento
 */
(function () {
  "use strict";

  const MAX_UNDO = 5;
  const stack = []; // [{id, cuadrante, text, listId}, ...] LIFO
  const onRestoreCallbacks = [];

  // ──────────────────────────────────────────────────────────────────────
  // Toast (singleton, lazy-created la primera vez que se llama showToast)
  // ──────────────────────────────────────────────────────────────────────
  let toastEl, toastText, toastBtn, toastTimer;

  function ensureToast() {
    if (toastEl) return;
    toastEl = document.getElementById("undo-toast");
    if (!toastEl) {
      // Auto-create si la página no lo trae
      toastEl = document.createElement("div");
      toastEl.id = "undo-toast";
      toastEl.setAttribute("role", "status");
      toastEl.setAttribute("aria-live", "polite");
      toastEl.className =
        "fixed bottom-6 left-1/2 -translate-x-1/2 bg-ink-160 text-white " +
        "px-4 py-3 rounded-lg shadow-lg text-sm flex items-center gap-3 " +
        "opacity-0 pointer-events-none transition-opacity duration-200 z-50";
      toastEl.innerHTML = `
        <span id="undo-toast-text">—</span>
        <button type="button" id="undo-toast-btn"
                class="px-2 py-1 bg-white text-ink-160 rounded text-xs font-semibold hover:bg-accent-100">
          Deshacer (Ctrl+Z)
        </button>`;
      document.body.appendChild(toastEl);
    }
    toastText = toastEl.querySelector("#undo-toast-text");
    toastBtn = toastEl.querySelector("#undo-toast-btn");
    toastBtn.addEventListener("click", undo);
  }

  function showToast(msg) {
    ensureToast();
    toastText.textContent = msg;
    toastEl.classList.remove("opacity-0", "pointer-events-none");
    toastEl.classList.add("opacity-100");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, 5000);
  }

  function hideToast() {
    if (!toastEl) return;
    toastEl.classList.add("opacity-0", "pointer-events-none");
    toastEl.classList.remove("opacity-100");
  }

  // ──────────────────────────────────────────────────────────────────────
  // Undo stack
  // ──────────────────────────────────────────────────────────────────────
  function pushUndo(entry) {
    stack.push(entry);
    if (stack.length > MAX_UNDO) stack.shift();
    showToast(`Borrado: “${truncate(entry.text, 40)}” · ${stack.length}/${MAX_UNDO} en pila`);
  }

  function registerOnRestore(fn) {
    onRestoreCallbacks.push(fn);
  }

  async function undo() {
    const entry = stack.pop();
    if (!entry) {
      showToast("Nada que deshacer");
      return;
    }
    const form = new FormData();
    form.append("item_id", entry.id);
    form.append("cuadrante", entry.cuadrante);
    form.append("item_text", entry.text);
    try {
      const r = await fetch(`${window.IKIGAI_URL}/inventario/item/restore`, { method: "POST", body: form });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const html = await r.text();
      // Notifica a todos los listeners (cada página decide cómo reinsertar)
      for (const cb of onRestoreCallbacks) cb(entry, html);
      showToast(`Restaurado: “${truncate(entry.text, 40)}”`);
    } catch (err) {
      stack.push(entry); // devolver a la pila si falló
      showToast(`Error al restaurar: ${err.message}`);
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // Inline edit (doble-click sobre un <span>)
  // ──────────────────────────────────────────────────────────────────────
  function editInline(span, li, opts = {}) {
    if (span.dataset.editing === "1") return;
    const original = span.textContent;
    const itemId = li.dataset.itemId;
    const spanClone = span.cloneNode(false); // misma class/title sin texto
    span.dataset.editing = "1";

    const input = document.createElement("input");
    input.type = "text";
    input.value = original;
    input.maxLength = 280;
    input.className =
      "flex-1 px-2 py-1 -my-1 border border-brand-100 rounded text-sm " +
      "focus:outline-none focus:ring-2 focus:ring-brand-100 focus:ring-opacity-30";
    span.replaceWith(input);
    input.focus();
    input.select();

    const restoreSpanWith = (text) => {
      spanClone.textContent = text;
      input.replaceWith(spanClone);
    };

    let settled = false;
    const finish = async (commit) => {
      if (settled) return;
      settled = true;
      const newText = input.value.trim();
      const restoredText = commit && newText ? newText : original;
      if (commit && newText && newText !== original) {
        try {
          const r = await fetch(`${window.IKIGAI_URL}/inventario/item/${encodeURIComponent(itemId)}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: new URLSearchParams({ item_text: newText }),
          });
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          li.dataset.itemText = newText;
          showToast(`Editado “${truncate(newText, 40)}”`);
          if (opts.onSaved) opts.onSaved(newText);
        } catch (err) {
          showToast(`Error al guardar: ${err.message}`);
          restoreSpanWith(original);
          return;
        }
      }
      restoreSpanWith(restoredText);
    };

    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter") { ev.preventDefault(); finish(true); }
      else if (ev.key === "Escape") { ev.preventDefault(); finish(false); }
    });
    input.addEventListener("blur", () => finish(true));
  }

  // ──────────────────────────────────────────────────────────────────────
  // Delete (con push al undo stack)
  // ──────────────────────────────────────────────────────────────────────
  async function deleteItem(li, opts = {}) {
    const entry = {
      id: li.dataset.itemId,
      cuadrante: li.dataset.cuadrante,
      text: li.dataset.itemText,
      listId: li.parentElement?.id,
    };
    try {
      const r = await fetch(`${window.IKIGAI_URL}/inventario/item/${encodeURIComponent(entry.id)}`, { method: "DELETE" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      pushUndo(entry);
      if (opts.onDeleted) opts.onDeleted(entry);
      else li.remove(); // default: quitar del DOM
    } catch (err) {
      showToast(`Error al borrar: ${err.message}`);
    }
  }

  // ──────────────────────────────────────────────────────────────────────
  // Add (POST y devuelve el fragmento HTML del row creado)
  // ──────────────────────────────────────────────────────────────────────
  async function addItem(cuadrante, itemText) {
    const text = (itemText || "").trim();
    if (!text) throw new Error("Texto vacío");
    const r = await fetch(`${window.IKIGAI_URL}/inventario/item`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ cuadrante, item_text: text }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.text(); // HTML del <li>
  }

  // ──────────────────────────────────────────────────────────────────────
  // Ctrl+Z global (no interfiere con inputs/textareas)
  // ──────────────────────────────────────────────────────────────────────
  function bindGlobalShortcuts() {
    document.addEventListener("keydown", (e) => {
      const isUndo = (e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === "z";
      if (!isUndo) return;
      const tag = (document.activeElement?.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea") return;
      e.preventDefault();
      undo();
    });
  }

  // ──────────────────────────────────────────────────────────────────────
  // Utilidades
  // ──────────────────────────────────────────────────────────────────────
  function truncate(s, n) {
    return s && s.length > n ? s.slice(0, n - 1) + "…" : s;
  }

  // ────────────────────────────────────────────────────────────
  // Nav toggle slide: anima la pastilla blanca antes de navegar.
  // Hace que el cambio entre /visualizador y /inventario se sienta continuo
  // en vez de un swap duro. Sin JS, el pill no se ve (width=0) pero el
  // color/peso de aria-selected sigue marcando la seccion activa.
  //
  // El pill se POSICIONA midiendo el <a> activo en tiempo real (offsetLeft,
  // offsetWidth) y exponiendolos como CSS vars --pill-x y --pill-w. Asi:
  //   - Cada segmento puede tener ancho propio segun su texto ("Visualizador"
  //     vs "Algebra"), y el pill encaja perfecto sin recortes ni desbordes.
  //   - Si la ventana cambia de tamaño, re-medimos.
  //   - Si se cambia data-active, re-medimos y el CSS anima width+transform.
  // ────────────────────────────────────────────────────────────
  const SLIDE_MS = 220;

  function updateNavPill(nav) {
    const active = nav.querySelector(`a[data-section="${nav.dataset.active}"]`);
    if (!active) return;
    // offsetLeft es relativo al wrapper posicionado (.nav-toggle), perfecto.
    // Añadimos un pequeño check de seguridad para asegurar que el pill exista
    const pill = nav.querySelector(".nav-toggle-pill");
    if (pill) {
      nav.style.setProperty("--pill-x", `${active.offsetLeft}px`);
      nav.style.setProperty("--pill-w", `${active.offsetWidth}px`);
    }
  }

  function bindNavToggleSlide() {
    const navs = document.querySelectorAll(".nav-toggle");
    navs.forEach(updateNavPill);
    // Re-medir al cambiar viewport (fonts cargadas, zoom, rotate, etc).
    window.addEventListener("resize", () => navs.forEach(updateNavPill));
    // Tambien cuando las fonts se cargan tarde (cambian metrics del texto).
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => navs.forEach(updateNavPill));
    }

    document.body.addEventListener("click", (e) => {
      const link = e.target.closest(".nav-toggle a[data-section]");
      if (!link) return;
      const nav = link.closest(".nav-toggle");
      const target = link.dataset.section;
      if (!nav || nav.dataset.active === target) {
        e.preventDefault();   // ya estamos aqui, no hace nada
        return;
      }
      e.preventDefault();
      nav.dataset.active = target;
      updateNavPill(nav);                            // dispara CSS transition
      // Esperamos a que la animacion termine antes de navegar.
      setTimeout(() => { window.location.href = link.href; }, SLIDE_MS);
    });
  }
  // Auto-bind al cargar (sin esperar a que cada pagina lo pida)
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindNavToggleSlide);
  } else {
    bindNavToggleSlide();
  }

  // ─────────────────────────────────────────────────────────────
  // API publica
  // ─────────────────────────────────────────────────────────────
  window.EditItems = {
    showToast,
    pushUndo,
    undo,
    registerOnRestore,
    editInline,
    deleteItem,
    addItem,
    bindGlobalShortcuts,
  };
})();
