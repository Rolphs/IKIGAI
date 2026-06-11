/**
 * algebra_crud.js — Pega los partials de algebra (cards de cuadrante primitivo)
 * con el modulo compartido EditItems (definido en edit_items.js).
 *
 * Responsabilidades:
 *   - Doble-click en .alg-item-text  -> editInline (PATCH /inventario/item/{id})
 *   - Click en .alg-item-del         -> deleteItem (DELETE + push undo)
 *   - Submit en .alg-add-form        -> addItem    (POST) + reinjectar <li>
 *   - registerOnRestore              -> reinjectar el <li> en su lista original
 *                                       cuando el usuario hace Ctrl+Z
 *   - Mantener .alg-card-count y el sanity-check sumatorio en sincronia.
 *
 * Por que NO reusamos el HTML del backend tal cual:
 *   POST /inventario/item devuelve un <li> con CLASES del inventario (chips,
 *   .htmx-added, etc.) que no encajan visualmente en algebra (que usa .set-item).
 *   Como ya tenemos el id que devuelve el server, re-renderizamos localmente
 *   con un <li> que matchea las clases visuales de la pagina /sintesis.
 *
 *   Esto mantiene UN solo backend (DRY) y dos presentaciones front
 *   (inventario vs sintesis), cada una con sus estilos propios.
 */
(function () {
  "use strict";

  if (!window.EditItems) {
    console.warn("[algebra_crud] EditItems no esta cargado; CRUD inline deshabilitado.");
    return;
  }

  // ───────────────────────────────────────────────────────────────
  // Renderer del <li> en formato sintesis (clases .set-item / .alg-item)
  // ───────────────────────────────────────────────────────────────
  function renderAlgebraRow({ id, item, cuadrante }) {
    const li = document.createElement("li");
    li.className = "set-item alg-item group cursor-grab active:cursor-grabbing";
    li.id = `alg-item-${id}`;
    li.dataset.itemId = id;
    li.dataset.cuadrante = cuadrante;
    li.dataset.itemText = item;
    li.draggable = true;
    li.innerHTML = `
      <span class="item-id">${escapeHtml(id)}</span>
      <span class="item-text alg-item-text cursor-text"
            title="Doble-click para editar">${escapeHtml(item)}</span>
      <button type="button"
              class="alg-item-del opacity-0 group-hover:opacity-100 focus-visible:opacity-100
                     transition shrink-0 text-ink-120 hover:text-danger-100
                     w-6 h-6 inline-flex items-center justify-center rounded
                     focus:outline-none focus:ring-2 focus:ring-danger-100"
              aria-label="Borrar item (Ctrl+Z para deshacer)"
              title="Borrar (Ctrl+Z deshace)">✕</button>
    `;
    return li;
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  // ───────────────────────────────────────────────────────────────
  // Sincronia de contadores: card individual + sumatorio global
  // ───────────────────────────────────────────────────────────────
  function updateCardCount(cardEl) {
    const ul = cardEl.querySelector(".alg-items");
    const countEl = cardEl.querySelector(".alg-card-count");
    if (!ul || !countEl) return;
    const n = ul.querySelectorAll(".alg-item").length;
    countEl.textContent = n;
    // Si quedo vacia y no hay msg ∅, lo agregamos; si tiene items y hay msg, lo quitamos.
    const emptyMsg = cardEl.querySelector(".alg-empty-msg");
    if (n === 0 && !emptyMsg) {
      const p = document.createElement("p");
      p.className = "alg-empty-msg text-[11px] italic text-ink-120 py-1";
      p.textContent = "∅ vacío";
      ul.insertAdjacentElement("afterend", p);
    } else if (n > 0 && emptyMsg) {
      emptyMsg.remove();
    }
  }

  function updateGlobalSum() {
    const sum = [...document.querySelectorAll(".alg-card-count")]
      .reduce((acc, el) => acc + (parseInt(el.textContent, 10) || 0), 0);
    // No volvemos a calcular si != |U| (eso requiere logica de auditor server-side
    // mas pesada). Simplemente actualizamos el numero crudo si el span existe.
    const sumSpan = document.querySelector("[data-alg-global-sum]");
    if (sumSpan) sumSpan.textContent = sum;
  }

  // ───────────────────────────────────────────────────────────────
  // Wiring de eventos (delegacion global para sobrevivir re-renders)
  // ───────────────────────────────────────────────────────────────
  document.addEventListener("dblclick", (e) => {
    const span = e.target.closest(".alg-item-text");
    if (!span) return;
    const li = span.closest(".alg-item");
    if (!li) return;
    window.EditItems.editInline(span, li, {
      onSaved: (newText) => { li.dataset.itemText = newText; },
    });
  });

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".alg-item-del");
    if (!btn) return;
    const li = btn.closest(".alg-item");
    if (!li) return;
    const card = li.closest(".set-card");
    window.EditItems.deleteItem(li, {
      onDeleted: () => {
        li.remove();
        if (card) updateCardCount(card);
        updateGlobalSum();
      },
    });
  });

  document.addEventListener("submit", async (e) => {
    const form = e.target.closest(".alg-add-form");
    if (!form) return;
    e.preventDefault();
    const input = form.querySelector(".alg-add-input");
    const text = (input.value || "").trim();
    if (!text) return;
    const cuadrante = form.dataset.cuadrante;
    const btn = form.querySelector(".alg-add-btn");
    btn.disabled = true;
    try {
      // El server devuelve HTML del inventario; lo descartamos y reusamos solo
      // el id generado parseandolo del fragmento. Si quisieramos evitar la
      // dependencia del HTML, conviene en el futuro agregar un endpoint JSON,
      // pero hoy reusar el endpoint existente es DRY-friendly.
      const html = await window.EditItems.addItem(cuadrante, text);
      const tmp = document.createElement("div");
      tmp.innerHTML = html;
      const newId = tmp.firstElementChild?.dataset.itemId;
      if (!newId) throw new Error("Server no devolvio item_id en el fragmento");
      const card = form.closest(".set-card");
      const ul = card.querySelector(".alg-items");
      ul.appendChild(renderAlgebraRow({ id: newId, item: text, cuadrante }));
      ul.scrollTop = ul.scrollHeight;  // auto-scroll al nuevo item
      input.value = "";
      input.focus();
      updateCardCount(card);
      updateGlobalSum();
    } catch (err) {
      window.EditItems.showToast?.(`Error al agregar: ${err.message}`);
    } finally {
      btn.disabled = false;
    }
  });

  // ───────────────────────────────────────────────────────────────
  // Undo: cuando EditItems restaura un <li>, reinjectarlo en SU lista
  // ───────────────────────────────────────────────────────────────
  window.EditItems.registerOnRestore((entry, _serverHtml) => {
    // entry.listId puede ser "alg-ul-1" (nuestro id) o "inventario-..." (otra pagina).
    // Solo procesamos las listas de sintesis.
    const ul = document.getElementById(entry.listId);
    if (!ul || !ul.classList.contains("alg-items")) return;
    ul.appendChild(renderAlgebraRow({
      id: entry.id, item: entry.text, cuadrante: entry.cuadrante,
    }));
    const card = ul.closest(".set-card");
    if (card) updateCardCount(card);
    updateGlobalSum();
  });

  // ───────────────────────────────────────────────────────────────
  // Drag and Drop: Reclasificación entre cards
  // ───────────────────────────────────────────────────────────────
  document.addEventListener("dragstart", (e) => {
    const li = e.target.closest(".alg-item");
    if (!li) return;
    e.dataTransfer.setData("text/plain", li.dataset.itemId);
    e.dataTransfer.setData("orig-cuadrante", li.dataset.cuadrante);
    e.dataTransfer.effectAllowed = "move";
    li.classList.add("opacity-40");
  });

  document.addEventListener("dragend", (e) => {
    const li = e.target.closest(".alg-item");
    if (li) li.classList.remove("opacity-40");
  });

  document.addEventListener("dragover", (e) => {
    const card = e.target.closest(".set-card");
    if (card) {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
    }
  });

  document.addEventListener("drop", async (e) => {
    const card = e.target.closest(".set-card");
    if (!card) return;
    e.preventDefault();
    
    const itemId = e.dataTransfer.getData("text/plain");
    const origCuad = e.dataTransfer.getData("orig-cuadrante");
    const targetCuad = card.dataset.csvValue;
    
    if (origCuad === targetCuad) return;

    const li = document.getElementById(`alg-item-${itemId}`);
    if (!li) return;

    try {
      // PATCH /inventario/item/{id} acepta tanto item_text como cuadrante,
      // asi que el move es una sola llamada atomica.
      const r = await fetch(`${window.IKIGAI_URL}/inventario/item/${encodeURIComponent(itemId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ cuadrante: targetCuad, item_text: li.dataset.itemText }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      
      // Update DOM
      const targetUl = card.querySelector(".alg-items");
      li.dataset.cuadrante = targetCuad;
      targetUl.appendChild(li);
      
      const origCard = document.querySelector(`.set-card[data-csv-value="${origCuad}"]`);
      if (origCard) updateCardCount(origCard);
      updateCardCount(card);
      updateGlobalSum();
      window.EditItems.showToast?.(`Movido ${itemId} a C${targetCuad}`);
    } catch (err) {
      window.EditItems.showToast?.(`Error al mover: ${err.message}`);
    }
  });

  // Ctrl+Z global (compartido con inventario; idempotente si ambas paginas lo llaman).
  window.EditItems.bindGlobalShortcuts?.();
})();
