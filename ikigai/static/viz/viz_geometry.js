/* ═══════════════════════════════════════════════════════════════════
 * viz_geometry.js — Motor de geometría del diagrama de Venn (0–4 conjuntos)
 *
 * Función pura `vennGeometry(n)` → { viewBox, shapes, labelOffsets }
 * `computeRegionGeometry(shapes, viewBox)` → { key: {x,y,r,area} }  (DERIVADO)
 * `renderVenn(viz)` que inyecta el SVG en #venn-host.
 *
 * NOTA TOPOLÓGICA: no se puede dibujar un Venn de 4 con círculos manteniendo
 * las 15 regiones visibles (teorema clásico). N=4 usa elipses inclinadas
 * (configuración Edwards 1989). El tope del motor es N=4, igual que el
 * producto (el endpoint /categories valida máximo 4 categorías).
 *
 * MEJORAS v2 (motor genérico):
 *   1. Hitboxes DERIVADOS de la geometría (sampling + centroide + declutter),
 *      no más {x,y,r} a mano → cero tuning frágil, sirve para cualquier N.
 *   2. Highlight de REGIÓN REAL: cada región se ilumina con su forma exacta
 *      (intersección vía clip-paths encadenados − exclusión vía <mask>).
 *   3. Paleta GENERATIVA colorFor(i, n) (preserva los 4 colores base
 *      clásicos; genera más por golden-angle si hace falta).
 *   4. Hint de descubribilidad: pulso sutil en badges de regiones con concepto.
 *
 * Dependencias externas:
 *   - window.CSV_LABELS              (bootstrap inline desde Jinja)
 *   - window.VIZ                      (cargada por viz_main desde /data)
 *   - window.PRIMITIVE_CONCEPTS       (synth por dominio, inline desde Jinja)
 *   - activateRegion (viz_regions.js)
 *   - escapeXml      (viz_helpers.js)
 * ═══════════════════════════════════════════════════════════════════ */

const LETTERS = "abcd";

// ── Paleta GENERATIVA ──────────────────────────────────────────────
// Los primeros 4 son fijos (preservan la identidad visual del
// Ikigai clásico: brand/spark/green/red). Más allá de 4,
// se generan por golden-angle en HSL para no repetir matiz.
const BASE_FILL = [
  "rgba(216,27,118,0.30)",   // a · brand
  "rgba(245,158,11,0.40)", // b · accent
  "rgba(22,163,74,0.30)",   // c · success
  "rgba(220,38,38,0.28)",   // d · danger
];
const BASE_SOLID = ["#d81b76", "#f59e0b", "#16a34a", "#dc2626"];

function colorFor(i, _n, alpha = 0.30) {
  if (i < BASE_FILL.length) return BASE_FILL[i];
  const hue = (i * 137.508) % 360; // golden angle → matices bien espaciados
  return `hsla(${hue.toFixed(1)}, 70%, 50%, ${alpha})`;
}
function solidFor(i) {
  if (i < BASE_SOLID.length) return BASE_SOLID[i];
  const hue = (i * 137.508) % 360;
  return `hsl(${hue.toFixed(1)}, 70%, 45%)`;
}

// Color del HIGHLIGHT de región (spark gold: resalta sobre los fills multiply).
const HL_FILL = "rgba(245,158,11,0.50)";

// ── Layouts canónicos por N (solo viewBox + shapes + labelOffsets) ──
// Los hitboxes YA NO se hardcodean aquí: se derivan con computeRegionGeometry.
function vennGeometry(n) {
  if (n === 0) {
    return { viewBox: "-100 -80 600 380", shapes: [], labelOffsets: [] };
  }
  if (n === 1) {
    return {
      viewBox: "-100 -80 600 380",
      shapes: [{ kind: "circle", cx: 240, cy: 120, r: 130 }],
      labelOffsets: [{ x: 240, y: -45, anchor: "middle" }],
    };
  }
  if (n === 2) {
    return {
      viewBox: "-100 -120 600 380",
      shapes: [
        { kind: "circle", cx: 170, cy: 100, r: 110 },
        { kind: "circle", cx: 310, cy: 100, r: 110 },
      ],
      labelOffsets: [
        { x: 130, y: -45, anchor: "end" },
        { x: 350, y: -45, anchor: "start" },
      ],
    };
  }
  if (n === 3) {
    return {
      viewBox: "-100 -50 600 480",
      shapes: [
        { kind: "circle", cx: 240, cy: 120, r: 120 },
        { kind: "circle", cx: 160, cy: 260, r: 120 },
        { kind: "circle", cx: 320, cy: 260, r: 120 },
      ],
      labelOffsets: [
        { x: 240, y: -25, anchor: "middle" },
        { x: 30, y: 320, anchor: "start" },
        { x: 450, y: 320, anchor: "end" },
      ],
    };
  }
  if (n === 4) {
    // 4 elipses ±45° (Edwards 1989). 15 regiones visibles.
    const cx = 240, cy = 240, rx = 170, ry = 90;
    return {
      viewBox: "-60 -20 600 540",
      shapes: [
        { kind: "ellipse", cx: cx - 30, cy: cy - 20, rx, ry, rot: -45 }, // a
        { kind: "ellipse", cx: cx + 30, cy: cy + 20, rx, ry, rot: -45 }, // b
        { kind: "ellipse", cx: cx + 30, cy: cy - 20, rx, ry, rot: 45 },  // c
        { kind: "ellipse", cx: cx - 30, cy: cy + 20, rx, ry, rot: 45 },  // d
      ],
      labelOffsets: [
        { x: 60, y: 90, anchor: "start" },
        { x: 420, y: 400, anchor: "end" },
        { x: 420, y: 90, anchor: "end" },
        { x: 60, y: 400, anchor: "start" },
      ],
    };
  }
  return null;
}

// ── Geometría booleana: ¿el punto está dentro de la forma i? ─────────
function pointInShape(x, y, s) {
  if (s.kind === "circle") {
    const dx = x - s.cx, dy = y - s.cy;
    return dx * dx + dy * dy <= s.r * s.r;
  }
  // Elipse rotada: llevamos el punto al marco de la elipse (rotando −rot).
  const t = -(s.rot || 0) * Math.PI / 180;
  const dx = x - s.cx, dy = y - s.cy;
  const px = dx * Math.cos(t) - dy * Math.sin(t);
  const py = dx * Math.sin(t) + dy * Math.cos(t);
  return (px * px) / (s.rx * s.rx) + (py * py) / (s.ry * s.ry) <= 1;
}

// Key de la región que contiene el punto (concatena letras de las formas que
// lo cubren, en orden de índice → coincide con las keys del backend).
function regionKeyAt(x, y, shapes) {
  let k = "";
  for (let i = 0; i < shapes.length; i++) {
    if (pointInShape(x, y, shapes[i])) k += LETTERS[i];
  }
  return k;
}

// Busca en espiral el punto más cercano que SÍ pertenece a `key` (para cuando
// el centroide de una región no-convexa cae fuera de ella).
function nearestInRegion(cx, cy, key, shapes) {
  for (let rad = 4; rad <= 140; rad += 4) {
    for (let a = 0; a < 360; a += 18) {
      const x = cx + rad * Math.cos(a * Math.PI / 180);
      const y = cy + rad * Math.sin(a * Math.PI / 180);
      if (regionKeyAt(x, y, shapes) === key) return { x, y };
    }
  }
  return null;
}

// Empuja hits demasiado cercanos para que sus badges no se monten (declutter
// por repulsión, varias iteraciones). Reemplaza el "tuning" manual de N=4.
function declutter(hits, minSep = 34, iters = 90) {
  const keys = Object.keys(hits);
  for (let it = 0; it < iters; it++) {
    let moved = false;
    for (let i = 0; i < keys.length; i++) {
      for (let j = i + 1; j < keys.length; j++) {
        const a = hits[keys[i]], b = hits[keys[j]];
        let dx = b.x - a.x, dy = b.y - a.y;
        let d = Math.hypot(dx, dy) || 0.01;
        if (d < minSep) {
          const push = (minSep - d) / 2;
          const ux = dx / d, uy = dy / d;
          a.x -= ux * push; a.y -= uy * push;
          b.x += ux * push; b.y += uy * push;
          moved = true;
        }
      }
    }
    if (!moved) break;
  }
}

// ── MEJORA #1: hitboxes derivados de la geometría ───────────────────
// Muestrea el lienzo, clasifica cada punto a su región, acumula centroide y
// área, refina (centroide adentro) y descongestiona. Devuelve {key:{x,y,r}}.
function computeRegionGeometry(shapes, vb) {
  if (!shapes.length) return {};
  const [minX, minY, w, h] = vb;
  // step=2 (no 3): con step grande las regiones-astilla pueden captar muy
  // pocas muestras → hitbox de radio mínimo en un único punto, frágil ante
  // redondeo float y potencialmente inclickeable. El sampling corre una sola
  // vez por render (no por frame), así que el costo es imperceptible.
  // NO subir sin re-auditar la robustez de las regiones chicas de N=4.
  const step = 2;
  const acc = {};
  for (let y = minY; y <= minY + h; y += step) {
    for (let x = minX; x <= minX + w; x += step) {
      const k = regionKeyAt(x, y, shapes);
      if (!k) continue;
      let a = acc[k];
      if (!a) a = acc[k] = { sx: 0, sy: 0, n: 0 };
      a.sx += x; a.sy += y; a.n++;
    }
  }
  const hits = {};
  const cellArea = step * step;
  for (const k in acc) {
    const a = acc[k];
    let cx = a.sx / a.n, cy = a.sy / a.n;
    if (regionKeyAt(cx, cy, shapes) !== k) {
      const p = nearestInRegion(cx, cy, k, shapes);
      if (p) { cx = p.x; cy = p.y; }
    }
    const r = Math.max(8, Math.min(26, Math.sqrt((a.n * cellArea) / Math.PI) * 0.55));
    hits[k] = { x: cx, y: cy, r, area: a.n * cellArea };
  }
  declutter(hits);
  return hits;
}

// Serializa una forma a <circle>/<ellipse> (fill opcional, para clips/masks).
function shapeEl(s, fill) {
  const f = fill ? ` fill="${fill}"` : "";
  if (s.kind === "circle") {
    return `<circle cx="${s.cx}" cy="${s.cy}" r="${s.r}"${f}/>`;
  }
  return `<ellipse cx="${s.cx}" cy="${s.cy}" rx="${s.rx}" ry="${s.ry}"` +
         ` transform="rotate(${s.rot} ${s.cx} ${s.cy})"${f}/>`;
}

// ── MEJORA #2: highlight de región REAL ─────────────────────────────
// Para cada región construye su forma exacta:
//   inclusión  = intersección de las formas incluidas (clip-paths encadenados)
//   exclusión  = resta de las formas restantes (vía <mask> negro)
// Devuelve { defs, groups } como strings SVG (se inyectan en el render).
function buildHighlights(shapes, hits, vb) {
  const vbRect = `x="${vb[0]}" y="${vb[1]}" width="${vb[2]}" height="${vb[3]}"`;
  let clipDefs = shapes
    .map((s, i) => `<clipPath id="vclip-${i}">${shapeEl(s)}</clipPath>`)
    .join("");
  let maskDefs = "";
  let groups = "";
  for (const key in hits) {
    const inc = key.split("").map((l) => LETTERS.indexOf(l));
    const exc = shapes.map((_, i) => i).filter((i) => inc.indexOf(i) === -1);
    // Intersección: rect de highlight clipeado sucesivamente por cada incluida.
    let inner = `<rect ${vbRect} fill="${HL_FILL}"/>`;
    inc.forEach((i) => {
      inner = `<g clip-path="url(#vclip-${i})">${inner}</g>`;
    });
    if (exc.length) {
      const maskId = `vhlm-${key}`;
      maskDefs += `<mask id="${maskId}" maskUnits="userSpaceOnUse">` +
        `<rect ${vbRect} fill="white"/>` +
        exc.map((i) => shapeEl(shapes[i], "black")).join("") +
        `</mask>`;
      groups += `<g class="venn-hl" data-hl="${key}" mask="url(#${maskId})">${inner}</g>`;
    } else {
      groups += `<g class="venn-hl" data-hl="${key}">${inner}</g>`;
    }
  }
  return { defs: clipDefs + maskDefs, groups };
}

// Toggle de clase en el highlight de una región (usado por hover y por
// activateRegion en viz_regions.js).
function setRegionHl(key, cls, on) {
  const g = document.querySelector(`.venn-hl[data-hl="${key}"]`);
  if (g) g.classList.toggle(cls, on);
}

// ─── Dispatcher ───
function renderViz(viz) { return renderVenn(viz); }

function renderVenn(viz) {
  const host = document.getElementById("venn-host");
  const n = viz.categories.length;
  const g = vennGeometry(n);
  const vb = g.viewBox.split(" ").map(Number); // [minX, minY, w, h]

  // ─ Shapes (paleta generativa) ─
  const shapes = viz.categories.map((_csv, i) => {
    const s = g.shapes[i];
    const fill = colorFor(i, n);
    if (s.kind === "circle") {
      return `<circle cx="${s.cx}" cy="${s.cy}" r="${s.r}"` +
             ` fill="${fill}" style="mix-blend-mode:multiply" aria-hidden="true"/>`;
    }
    return `<ellipse cx="${s.cx}" cy="${s.cy}" rx="${s.rx}" ry="${s.ry}"` +
           ` transform="rotate(${s.rot} ${s.cx} ${s.cy})"` +
           ` fill="${fill}" style="mix-blend-mode:multiply" aria-hidden="true"/>`;
  }).join("");

  // ─ Hitboxes DERIVADOS + highlights de región real ─
  const regionHits = computeRegionGeometry(g.shapes, vb);
  const hl = buildHighlights(g.shapes, regionHits, vb);

  // ─ Labels (título + synth prominente + sublabel) ─
  const labels = viz.categories.map((csvVal, i) => {
    const lbl = window.CSV_LABELS[csvVal] || { titulo: csvVal, sublabel: "", emoji: "" };
    const o = g.labelOffsets[i];
    const synth = (window.PRIMITIVE_CONCEPTS || {})[csvVal] || "";
    const synthLine = synth
      ? `<tspan x="${o.x}" text-anchor="${o.anchor}" dy="1.4em"
               style="font-size:14px;font-weight:700;fill:#d81b76">“${escapeXml(synth)}”</tspan>`
      : "";
    return `<text x="${o.x}" y="${o.y}" text-anchor="${o.anchor}"
                   class="fill-ink-160" style="font-size:13px;font-weight:600">
      <tspan x="${o.x}" text-anchor="${o.anchor}">${lbl.emoji} ${lbl.titulo}</tspan>
      ${synthLine}
      <tspan x="${o.x}" text-anchor="${o.anchor}" dy="1.35em"
             style="font-size:11px;font-weight:400;fill:#74767c">${lbl.sublabel}</tspan>
    </text>`;
  }).join("");

  // ─ Hit-areas + badges con CONCEPTO (no count) ─
  const hits = Object.entries(regionHits).map(([key, hit]) => {
    const r = viz.regions[key] || { concept: "", evidence: [] };
    const concept = (r.concept || "").trim();
    const maxChars = hit.r >= 20 ? 14 : 8;
    const truncated = concept.length > maxChars
      ? concept.slice(0, maxChars - 1) + "…"
      : concept;
    const safeText = escapeXml(truncated);
    const textW = Math.max(20, truncated.length * 5.5 + 12);
    // MEJORA #5: badge de región CON concepto pulsa sutil (descubribilidad).
    const badge = concept
      ? `<g class="venn-badge has-concept" pointer-events="none">
          <rect x="${hit.x - textW / 2}" y="${hit.y - 9}" width="${textW}" height="18" rx="9"
                fill="#1d1d1d" opacity="0.92"/>
          <text x="${hit.x}" y="${hit.y + 4}" text-anchor="middle" fill="#ffffff"
                font-size="10" font-weight="600">${safeText}</text>
        </g>`
      : `<circle class="venn-badge" pointer-events="none"
                cx="${hit.x}" cy="${hit.y}" r="3"
                fill="rgba(116,118,124,0.4)"/>`;
    const ariaLabel = concept
      ? `Region ${key}: "${concept}"`
      : `Region ${key}: sin concepto definido. Click para acunar uno.`;
    return `${badge}<circle class="venn-region" data-region="${key}" cx="${hit.x}" cy="${hit.y}" r="${hit.r}"
                            tabindex="0" role="button"
                            aria-label="${escapeXml(ariaLabel)}">
              <title>${escapeXml(concept || "sin concepto - click para acunar")}</title>
            </circle>`;
  }).join("");

  // ─ Zona exterior "out" (rect envolvente) ─
  const outR = viz.regions["out"] || { concept: "", evidence: [] };
  const outConcept = (outR.concept || "").trim();
  const isUniverso = n === 0;
  const outFillStrong = isUniverso ? "#d81b76" : "#dc2626";
  const outFillSoft = isUniverso ? "rgba(216,27,118,0.6)" : "rgba(220,38,38,0.6)";
  const outBaseLabel = isUniverso ? "⋃ UNIVERSO" : "⊙ EXTERIOR";
  const outDisplay = outConcept
    ? (outConcept.length > 22 ? outConcept.slice(0, 21) + "…" : outConcept)
    : "";
  const outFullLabel = outConcept ? `${outBaseLabel} · ${outDisplay}` : outBaseLabel;
  const outBadgeW = Math.max(120, outFullLabel.length * 6.5 + 16);
  const outBadge = `<g class="venn-badge" pointer-events="none">
    <rect x="${vb[0] + 8}" y="${vb[1] + 8}" width="${outBadgeW}" height="22" rx="4"
          fill="${outConcept ? outFillStrong : outFillSoft}" opacity="0.95"/>
    <text x="${vb[0] + 14}" y="${vb[1] + 23}" fill="#ffffff" font-size="11" font-weight="700">
      ${escapeXml(outFullLabel)}
    </text>
  </g>`;
  const outAriaLabel = outConcept
    ? `Espacio exterior: "${outConcept}"`
    : `Espacio exterior (negativo). Click para acunar concepto.`;

  host.innerHTML = `<svg viewBox="${g.viewBox}" class="max-w-full max-h-full" style="overflow:visible"
                         role="img" aria-label="${isUniverso ? 'Universo (sin círculos)' : `Diagrama de Venn de ${n} círculo${n === 1 ? '' : 's'}`}">
    <defs>${hl.defs}</defs>
    <rect class="venn-out-zone" data-region="out"
          x="${vb[0] + 2}" y="${vb[1] + 2}" width="${vb[2] - 4}" height="${vb[3] - 4}"
          rx="8" tabindex="0" role="button"
          aria-label="${escapeXml(outAriaLabel)}">
      <title>${escapeXml(outConcept || "Espacio exterior - click para acunar concepto")}</title>
    </rect>
    <g>${shapes}</g>
    <g class="venn-hl-layer">${hl.groups}</g>
    <g>${labels}</g>
    <g>${hits}</g>
    ${outBadge}
  </svg>`;

  // ─ Wire-up: click activa región; hover ilumina la forma real ─
  host.querySelectorAll(".venn-region").forEach((el) => {
    const key = el.dataset.region;
    el.addEventListener("click", () => activateRegion(key));
    el.addEventListener("mouseenter", () => setRegionHl(key, "hover", true));
    el.addEventListener("mouseleave", () => setRegionHl(key, "hover", false));
    el.addEventListener("focus", () => setRegionHl(key, "hover", true));
    el.addEventListener("blur", () => setRegionHl(key, "hover", false));
  });
  const outZone = host.querySelector(".venn-out-zone");
  if (outZone) outZone.addEventListener("click", () => activateRegion("out"));
}

// Exponer en window para otros módulos.
window.colorFor = colorFor;
window.solidFor = solidFor;
window.vennGeometry = vennGeometry;
window.computeRegionGeometry = computeRegionGeometry;
window.setRegionHl = setRegionHl;
window.renderViz = renderViz;
window.renderVenn = renderVenn;
