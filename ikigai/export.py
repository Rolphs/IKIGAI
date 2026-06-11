"""
Snapshot estatico del Ikigai personal de un usuario.

Genera un HTML autocontenido (sin servidor, sin assets locales) listo para
abrir en cualquier browser o subir a cualquier hosting estatico.

La app interactiva (FastAPI + HTMX) NO puede vivir en un hosting estatico
porque necesita backend. Pero un *snapshot del resultado* si — y eso es lo
que construye este modulo.

Diseño:
    - Sin dependencias de FastAPI / Request / TemplateResponse.
    - Jinja2 standalone con FileSystemLoader propio (templates/export/).
    - Toda la matematica y datos vienen del modulo `intersection_concepts`,
      que es donde vive la verdad sobre cuales cards existen y como se
      computan.
    - Tailwind VENDORIZADO: el CSS buildeado (ikigai/static/tailwind.css) se
      inyecta inline en el HTML. Asi el snapshot se ve bien en CUALQUIER red
      (sin depender de cdn.tailwindcss.com) y sigue siendo autocontenido.
      El CSS purgado pesa ~31KB, no megabytes.
"""
from __future__ import annotations

import datetime as _dt
from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ikigai import intersection_concepts
from ikigai.algebra_state import load_algebra_state, resolve_items_path
from ikigai.cuadrantes import CUADRANTES, positive_csv_values

# Templates separados de los de FastAPI: la card del server tiene <form>,
# HTMX, botones interactivos. La del export es estatica pura, sin acciones.
_TEMPLATES_DIR = Path(__file__).parent / "templates" / "export"
_SNAPSHOT_TEMPLATE = "snapshot.html.j2"
_VENN_SVG_TEMPLATE = "_venn4_svg.html.j2"

# CSS vendorizado (mismo que sirve el server desde /static/). Se inyecta
# inline en el snapshot para que sea autocontenido y se vea bien sin CDN.
_STATIC_CSS = Path(__file__).parent / "static" / "tailwind.css"

# Solo los 4 circulos positivos entran al pipeline de naming (igual que
# en /sintesis). La combinatoria con sombra rompe la UX. Derivado de la
# fuente de verdad (cuadrantes) para que agregar/quitar un primitivo se
# propague solo, en vez de hardcodear {"1","2","3","4"}.
_POSITIVE_CIRCLES = frozenset(positive_csv_values())

# Mapeo region_key (Venn topology) -> concept_key (Ikigai algebra).
#
# Las regiones del Venn de 4 elipses (Edwards 1989) se etiquetan con letras:
# a (Gusto, top-left), b (Habilidad, bottom-right), c (Mundo, top-right),
# d (Mercado, bottom-left), mas todas las 11 intersecciones (ab, ac, ad, bc,
# bd, cd, abc, abd, acd, bcd, abcd). El modulo intersection_concepts las
# nombra con csv_values numericos ("1", "2", "1,2", "1,2,3,4", etc.).
# Esta tabla es el unico lugar donde ambas convenciones se reconcilian.
_REGION_TO_CONCEPT_KEY: dict[str, str] = {
    "a":    "1",
    "b":    "2",
    "c":    "3",
    "d":    "4",
    "ab":   "1,2",       # Pasion
    "ac":   "1,3",       # Mision
    "ad":   "1,4",       # Hobby remunerado (diagonal)
    "bc":   "2,3",       # Servicio voluntario (diagonal)
    "bd":   "2,4",       # Profesion
    "cd":   "3,4",       # Vocacion
    "abc":  "1,2,3",     # Casi-Ikigai sin Mercado
    "abd":  "1,2,4",     # Casi-Ikigai sin Mundo
    "acd":  "1,3,4",     # Casi-Ikigai sin Habilidad
    "bcd":  "2,3,4",     # Casi-Ikigai sin Gusto
    "abcd": "1,2,3,4",   # ⭐ IKIGAI
}


def build_export_context(project_dir: Path, *, redact: bool = False) -> dict[str, Any]:
    """Recolecta todo lo que el template necesita en un solo dict.

    Esta funcion es pura logica de dominio: lee archivos, computa cards,
    y devuelve datos. No toca Jinja ni filesystem de salida. Asi se
    puede testear sin generar HTML.

    Args:
      project_dir: directorio con tulipan.jsonl + intersection_concepts.yaml.
      redact: si True, oculta los textos de items en "Lo que sembraste"
        — solo se reportan conteos. Util para compartir publicamente sin
        exponer contenido personal sensible. Los nombres personales (las
        sintesis acuñadas) siempre se muestran porque son el punto.
    """
    items_path = resolve_items_path(project_dir)

    # Toda la carga del estado vive en `algebra_state` (compartido con el
    # router /sintesis). Aqui solo derivamos lo especifico del export.
    state = load_algebra_state(items_path)
    positive_tag_sets = {
        k: v for k, v in state.primitive_sets.items() if k in _POSITIVE_CIRCLES
    }
    universe_size = len(state.universe)

    personal_names = intersection_concepts.load_personal_names_for(project_dir)
    cards = intersection_concepts.compute_all_intersections(
        positive_tag_sets, state.items_by_id, personal_names
    )

    # Agrupar por capa para que el template no tenga que hacer logica de loop.
    cards_by_layer: dict[int, list[dict[str, Any]]] = {0: [], 1: [], 2: [], 3: []}
    for c in cards:
        cards_by_layer[c["layer"]].append(c)

    # Lookup por concept_key, para que el hero del Venn pueda mapear region
    # -> card sin tener que iterar las 15 cards por cada region.
    cards_by_concept_key: dict[str, dict[str, Any]] = {
        c["key"]: c for c in cards
    }
    venn_regions_by_key: dict[str, dict[str, Any]] = {
        region: cards_by_concept_key[concept_key]
        for region, concept_key in _REGION_TO_CONCEPT_KEY.items()
        if concept_key in cards_by_concept_key
    }

    # El centro Ikigai (capa 3) merece referencia directa — es el remate.
    ikigai = cards_by_layer[3][0] if cards_by_layer[3] else None

    # Items por circulo positivo, para la seccion "lo que sembraste".
    items_per_positive = {
        csv_val: state.items_by_cuad[csv_val] for csv_val in sorted(_POSITIVE_CIRCLES)
    }

    # Metricas de completitud para mostrar el "estado" del export.
    total_secured = sum(1 for c in cards if c["is_secured"])
    total_concepts = len(cards)
    is_complete = ikigai is not None and ikigai["is_secured"]

    return {
        "project_name": project_dir.name,
        "exported_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "redacted": redact,
        "cards": cards,
        "cards_by_layer": cards_by_layer,
        "venn_regions_by_key": venn_regions_by_key,
        "ikigai": ikigai,
        "items_per_positive": items_per_positive,
        "universe_size": universe_size,
        "total_secured": total_secured,
        "total_concepts": total_concepts,
        "is_complete": is_complete,
        "cuadrantes": CUADRANTES,
    }


def export_snapshot(
    project_dir: Path, out_path: Path, *, redact: bool = False
) -> Path:
    """API publica: lee el proyecto, genera HTML, escribe al path indicado.

    Devuelve el path escrito (util para CLI y tests).
    """
    context = build_export_context(project_dir, redact=redact)
    html = render_export(context)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_export(context: dict[str, Any]) -> str:
    """Renderiza el HTML standalone. Devuelve string (no escribe a disco).

    Separar render de write permite testear el HTML en memoria.
    Jinja2 cachea templates parseados a nivel de Environment, asi que
    re-renders son ~80x mas rapidos que el primero (de ~24ms a <1ms).
    """
    template = _get_jinja_env().get_template(_SNAPSHOT_TEMPLATE)
    return template.render(tailwind_css=_read_vendored_css(), **context)


def render_venn_svg(project_dir: Path) -> str:
    """Renderiza SOLO el Venn-4 con callouts como SVG standalone descargable.

    Reusa la misma plantilla (_venn4_svg.html.j2) y el mismo builder de
    regiones que el snapshot HTML (DRY): asi el .svg que baja el usuario y el
    hero del snapshot son identicos pixel a pixel. Devuelve un documento XML
    completo (con prolog) listo para servir/descargar.
    """
    context = build_export_context(project_dir)
    template = _get_jinja_env().get_template(_VENN_SVG_TEMPLATE)
    svg = template.render(**context)
    return '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n' + svg


@lru_cache(maxsize=1)
def _read_vendored_css() -> str:
    """Lee el CSS buildeado una sola vez (cacheado).

    Es el mismo `ikigai/static/tailwind.css` que sirve el server; aqui se
    inyecta inline en el snapshot para hacerlo autocontenido sin CDN.
    """
    return _STATIC_CSS.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _get_jinja_env() -> Environment:
    """Singleton del Environment de Jinja2.

    Por que cachear: Environment.get_template() **parsea y compila** el
    template la primera vez, y cachea el resultado dentro del Environment.
    Si creamos un Environment nuevo en cada render, perdemos ese cache y
    pagamos el parsing (~20ms por export con nuestros 3 templates anidados
    de snapshot + venn4_hero + card_static).

    `lru_cache(maxsize=1)` nos da un singleton lazy thread-safe sin tener
    que escribir nuestro propio patron de inicializacion. El env se
    construye en la primera llamada y se reusa.

    Si en algun momento necesitaramos invalidar (ej. para hot-reload de
    templates en tests), basta con `_get_jinja_env.cache_clear()`.
    """
    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )



