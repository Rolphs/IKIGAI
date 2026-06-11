/* ══════════════════════════════════════════════════════════════════
 * viz_helpers.js — utilidades sin estado, reutilizadas por todos los módulos
 *
 * Globales expuestos:
 *   - fetchJSON(url, opts)  → wrapper de fetch + JSON + throw en !ok
 *   - form(obj)             → FormData desde un objeto plano
 *   - escapeXml(s)          → escape para inyectar texto en SVG/HTML
 * ══════════════════════════════════════════════════════════════════ */

async function fetchJSON(url, opts = {}) {
  const r = await fetch(url, opts);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function form(obj) {
  const fd = new FormData();
  Object.entries(obj).forEach(([k, v]) => fd.append(k, v));
  return fd;
}

function escapeXml(s) {
  return String(s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/** 
 * Toasts: Notificaciones sutiles y elegantes.
 * @param {string} msg 
 * @param {'success'|'error'|'info'|'warning'} type 
 */
function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const template = document.getElementById('toast-template');
  if (!container || !template) return;

  const clone = template.content.cloneNode(true);
  const item = clone.querySelector('.toast-item');
  const msgEl = clone.querySelector('.toast-msg');
  const iconEl = clone.querySelector('.toast-icon');
  const closeBtn = clone.querySelector('.toast-close');

  msgEl.textContent = msg;

  const configs = {
    success: { icon: '✅', border: 'border-success-100', bg: 'bg-white' },
    error:   { icon: '❌', border: 'border-danger-100',   bg: 'bg-white' },
    info:    { icon: 'ℹ️', border: 'border-brand-100',  bg: 'bg-white' },
    warning: { icon: '⚠️', border: 'border-accent-100', bg: 'bg-white' },
  };

  const conf = configs[type] || configs.info;
  item.classList.add(conf.border, conf.bg);
  iconEl.textContent = conf.icon;

  // Anti-pileup: al encadenar acciones rapidas (p.ej. varias reflexiones
  // seguidas en introspeccion), no apilamos toasts identicos. Quitamos el
  // anterior con el mismo mensaje para que cada accion *renueve* el toast
  // en vez de amontonar copias que tardan en irse.
  item.dataset.toastMsg = msg;
  container.querySelectorAll(`[data-toast-msg="${CSS.escape(msg)}"]`)
    .forEach((el) => el.remove());

  container.appendChild(item);

  // Animación entrada
  requestAnimationFrame(() => {
    item.classList.remove('translate-y-10', 'opacity-0');
  });

  const remove = () => {
    item.classList.add('opacity-0', 'translate-x-10');
    setTimeout(() => item.remove(), 300);
  };

  // Guard: el template puede no traer boton de cierre. Sin este guard,
  // `closeBtn.onclick` lanzaba TypeError y mataba la linea siguiente
  // (el setTimeout de auto-descarte) -> el toast se quedaba para siempre.
  if (closeBtn) closeBtn.onclick = remove;
  // Auto-remove en 4s
  setTimeout(remove, 4000);
}

// Exponer en window para uso desde otros módulos cargados como scripts clásicos.
window.fetchJSON = fetchJSON;
window.form = form;
window.escapeXml = escapeXml;
window.showToast = showToast;
