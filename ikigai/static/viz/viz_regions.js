/* viz_regions.js - Editor de region (panel inferior) + AI suggest
 *
 * Refactor v0.3.0 (single source of truth):
 *   - Ya no se manipula evidence aqui (toggle/remove eliminados): los items
 *     mostrados son DERIVADOS del CSV en runtime por el backend. Para
 *     cambiar de que region es un item, edita su tag en /inventario.
 *   - Solo se guarda CONCEPT, y se escribe al yaml compartido con /sintesis
 *     via /visualizador/region/{key}/concept.
 */

function activateRegion(key) {
  window.ACTIVE_REGION = key;
  const r = window.VIZ.regions[key] || { concept: "", evidence: [] };

  document.querySelectorAll(".venn-region, .venn-out-zone").forEach(function (el) {
    el.classList.toggle("active", el.dataset.region === key);
  });

  // MEJORA #2: iluminar la FORMA REAL de la region activa (no solo el hitbox).
  // Apaga todos los highlights y prende el de la region activa con .active.
  document.querySelectorAll(".venn-hl").forEach(function (g) {
    g.classList.toggle("active", g.dataset.hl === key);
  });

  const badge = document.getElementById("region-badge");
  badge.textContent =
    key === "out" ? "exterior" : (isCenter(key) ? "centro" : key);
  if (key === "out") {
    badge.classList.remove("bg-brand-100");
    badge.classList.add("bg-danger-100");
  } else {
    badge.classList.remove("bg-danger-100");
    badge.classList.add("bg-brand-100");
  }
  document.getElementById("region-label").textContent = describeRegion(key);

  // Concept: editable salvo "out" (exterior no tiene concept_key valido).
  const conceptInput = document.getElementById("region-concept");
  const isOut = key === "out";
  conceptInput.value = r.concept;
  conceptInput.disabled = isOut;
  conceptInput.placeholder = isOut
    ? "El exterior no almacena concepto (es el complemento del set)"
    : "Ej. 'Mentoria que transforma vidas'";

  renderEvidence(r.evidence);
  renderCanonicalBlurb(key);

  document.getElementById("region-editor").classList.remove("translate-y-full");

  // Highlight de los chips que estan en la region (read-only ahora).
  document.querySelectorAll(".item-chip").forEach(function (chip) {
    chip.classList.toggle("in-region", r.evidence.includes(chip.dataset.itemId));
  });
}

function closeEditor() {
  document.getElementById("region-editor").classList.add("translate-y-full");
  document.querySelectorAll(".venn-region, .venn-out-zone").forEach(function (el) {
    el.classList.remove("active");
  });
  document.querySelectorAll(".venn-hl").forEach(function (g) {
    g.classList.remove("active");
  });
  document.querySelectorAll(".item-chip").forEach(function (c) {
    c.classList.remove("in-region");
  });
  window.ACTIVE_REGION = null;
}

function isCenter(key) {
  const n = (window.VIZ && window.VIZ.categories) ? window.VIZ.categories.length : 0;
  return key !== "out" && key.length === n;
}

function renderCanonicalBlurb(key) {
  const box = document.getElementById("region-canonical");
  const tagline = document.getElementById("region-tagline");
  const warningRow = document.getElementById("region-warning");
  const warningText = document.getElementById("region-warning-text");
  const c = canonicalForRegion(key);
  if (!c) { box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  tagline.textContent = c.tagline;
  const isIkigai = c.name === "Ikigai";
  box.className = isIkigai
    ? "mb-3 -mt-1 p-3 rounded border-l-4 border-success-100 bg-success-10"
    : "mb-3 -mt-1 p-3 rounded border-l-4 border-accent-100 bg-accent-10";
  if (c.warning) {
    warningText.textContent = c.warning;
    warningRow.classList.remove("hidden");
  } else {
    warningRow.classList.add("hidden");
  }
}

function describeRegion(key) {
  if (key === "out") return "Espacio exterior - items que no caen en ningun circulo activo";
  const letters = key.split("");
  const csvVals = letters.map(function (L) {
    const idx = "abcde".indexOf(L);
    return window.VIZ.categories[idx];
  });
  const parts = csvVals.map(function (v) {
    return (window.CSV_LABELS[v] && window.CSV_LABELS[v].label) || v;
  });
  const composition = parts.length === 1 ? ("Solo " + parts[0]) : parts.join(" n ");
  const lookupKey = csvVals.slice().sort().join(",");
  const canonical = window.CANONICAL_INTERSECTIONS && window.CANONICAL_INTERSECTIONS[lookupKey];
  if (canonical) return canonical.name + " - " + composition;
  return composition;
}

function canonicalForRegion(key) {
  if (key === "out") return null;
  const csvVals = key.split("").map(function (L) {
    const idx = "abcde".indexOf(L);
    return window.VIZ.categories[idx];
  });
  const lookupKey = csvVals.slice().sort().join(",");
  return (window.CANONICAL_INTERSECTIONS && window.CANONICAL_INTERSECTIONS[lookupKey]) || null;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function renderEvidence(evidence) {
  const host = document.getElementById("region-evidence");
  if (!evidence.length) {
    host.innerHTML =
      '<span class="text-xs italic text-ink-120">' +
      'No hay items aqui. Edita los tags en ' +
            '<a href="' + window.IKIGAI_URL + '/inventario" class="text-brand-100 hover:underline">Inventario</a>' +
      ' para que aparezcan en esta region.</span>';
    return;
  }
  // READ-ONLY: items derivados; sin boton de quitar.
  host.innerHTML = evidence.map(function (id) {
    const chip = document.querySelector('.item-chip[data-item-id="' + id + '"]');
    const text = chip ? chip.dataset.itemText : "(no encontrado)";
    return '<span class="inline-flex items-center gap-1 bg-success-100 text-white text-xs px-2 py-1 rounded">' +
      '<span class="font-mono opacity-70">' + escapeHtml(id) + '</span>' +
      '<span>' + escapeHtml(text) + '</span></span>';
  }).join("");
}

/** Guarda el concepto al yaml compartido (intersection_concepts.yaml). */
async function saveConcept() {
  const key = window.ACTIVE_REGION;
  if (!key || key === "out") return;  // "out" no tiene concept_key
  const concept = document.getElementById("region-concept").value.trim();
  window.VIZ.regions[key].concept = concept;  // sync local
  try {
    const r = await fetch(
            window.IKIGAI_URL + "/visualizador/region/" + encodeURIComponent(key) + "/concept",
      { method: "POST", body: form({ concept: concept }) }
    );
    if (!r.ok) {
      const err = await r.json().catch(function () { return { detail: r.statusText }; });
      console.warn("saveConcept fallo:", err);
      showToast("Error al guardar concepto", "error");
    } else {
      showToast("Concepto guardado", "success");
    }
  } catch (e) {
    console.warn("saveConcept network error:", e);
    showToast("Error de conexión", "error");
  }
}

window.activateRegion = activateRegion;
window.closeEditor = closeEditor;
window.saveConcept = saveConcept;
