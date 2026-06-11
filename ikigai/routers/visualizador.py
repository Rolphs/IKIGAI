"""routers/visualizador.py - Vista Venn del Ikigai (slim, single-viz).

Todo lo presentado se DERIVA en runtime de dos fuentes:
  - tulipan.jsonl (items con tags)
  - intersection_concepts.yaml (nombres acuñados por csv_value-set)

El default.yaml solo guarda framing posicional (categories order + summary).
Cambios al concepto de una region NO se guardan ahi: se guardan en
intersection_concepts.yaml (compartido con /sintesis), porque son SEMANTICOS
(invariantes al orden de circulos del Venn).

Endpoints:
  GET  /visualizador                      -> pagina HTML
  POST /visualizador/categories           -> cambia orden/seleccion de circulos
  POST /visualizador/region/{key}/concept -> guarda concept en intersection_concepts.yaml
  PATCH /visualizador/summary             -> guarda summary
  GET  /visualizador/data                 -> JSON derivado completo
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ikigai import export, intersection_concepts, jsonl_store
from ikigai.cuadrantes import CUADRANTES, all_csv_values, find_side, positive_csv_values
from ikigai.item_queries import items_by_tag
from ikigai.render import get_paths, render
from ikigai.viz_models import Visualization, region_to_csv_values
from ikigai.viz_storage import (
    load_visualization,
    save_visualization,
    viz_lock,
)

router = APIRouter(tags=["visualizador"])

_DEFAULT_VIZ = "default"


def derive_region_views(
    viz: Visualization, items_path: Path
) -> dict[str, dict[str, Any]]:
    """Para cada region del Venn (incluyendo 'out'), deriva concept + evidence.

    - concept: lo lee de intersection_concepts.yaml usando concept_key(csv_values).
    - evidence: items del store que tienen TODOS los tags csv_values de la region.
    - 'out': items que NO tienen ninguno de los csv_values positivos en categories.

    Esta es la FUNCION CRITICA del refactor "single source of truth": traduce
    el modelo posicional del Venn (letras a,b,c,d) al modelo semantico canonico
    (set de csv_values ordenados), aprovechando el algebra que ya existia.

    Returns:
      {region_key: {"concept": str, "evidence": [item_id, ...]}}
    """
    # Cache de items por csv_value (1 sola lectura del store)
    all_items = jsonl_store.read_all(items_path)
    items_for: dict[str, set[str]] = {}
    for csv_val in all_csv_values():
        items_for[csv_val] = {it.id for it in items_by_tag(all_items, csv_val)}

    # Cache de concepts (1 sola lectura del yaml)
    personal_names = intersection_concepts.load_personal_names_for(items_path.parent)

    out: dict[str, dict[str, Any]] = {}
    for region_key in viz.all_region_keys():
        if region_key == "out":
            # Exterior: items que NO tienen ninguno de los csv_values activos.
            all_active_ids: set[str] = set()
            for csv_val in viz.categories:
                all_active_ids |= items_for.get(csv_val, set())
            all_ids = {it.id for it in all_items}
            evidence = sorted(all_ids - all_active_ids)
            concept = ""  # "out" no tiene concept (no es interseccion)
        else:
            csv_values = region_to_csv_values(region_key, viz.categories)
            if not csv_values:
                evidence = []
                concept = ""
            else:
                evidence_set = items_for.get(csv_values[0], set()).copy()
                for csv_val in csv_values[1:]:
                    evidence_set &= items_for.get(csv_val, set())
                evidence = sorted(evidence_set)
                key = intersection_concepts.concept_key(csv_values)
                concept = personal_names.get(key, "")
        out[region_key] = {"concept": concept, "evidence": evidence}
    return out


def _error_page(title: str, detail: str, hint: str) -> str:
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Error</title>
<link rel="stylesheet" href="/static/tailwind.css"></head>
<body class="bg-ink-5 p-10 font-sans">
  <div class="max-w-2xl mx-auto bg-white border-l-4 border-danger-100 p-6 rounded shadow">
    <h1 class="text-2xl font-bold text-ink-160 mb-2">⚠️ {title}</h1>
    <pre class="text-sm text-danger-100 bg-danger-10 p-3 rounded whitespace-pre-wrap">{detail}</pre>
    <p class="mt-4 text-ink-120 text-sm">{hint}</p>
    <a href="/inventario" class="inline-block mt-4 text-brand-100 hover:underline">← Volver al inventario</a>
  </div>
</body></html>"""


@router.get("/visualizador", response_class=HTMLResponse)
def visualizador(request: Request) -> Response:
    """Renderiza la pagina del Venn. Single-viz: siempre 'default'."""
    project_dir, items_path = get_paths(request)
    try:
        viz = load_visualization(project_dir, _DEFAULT_VIZ)
        region_views = derive_region_views(viz, items_path)
        # Cacheamos los nombres personales una sola vez.
        personal_names = intersection_concepts.load_personal_names_for(project_dir)
    except Exception as exc:
        return HTMLResponse(
            content=_error_page(
                "Error cargando visualización",
                str(exc),
                "Revisa visualizations/default.yaml y tulipan.jsonl",
            ),
            status_code=500,
        )
    all_items = jsonl_store.read_all(items_path)
    return render(request, "visualizador.html.j2", {
        "viz": viz,
        "viz_name": _DEFAULT_VIZ,
        "master_title": viz.title,
        "master_viz_name": _DEFAULT_VIZ,
        "region_views": region_views,
        "cuadrantes": CUADRANTES,
        "items_by_cuad": {
            csv_val: items_by_tag(all_items, csv_val)
            for csv_val in all_csv_values()
        },
        "canonical_intersections": request.app.state.canonical_to_json_dict(),
        # Conceptos sinteticos por dominio (Amo/Bueno/Mundo/Pago). Se muestran
        # como label del circulo en el Venn y en el header de cada cajon.
        # Shared con /sintesis a traves de intersection_concepts.yaml.
        "primitive_concepts": {
            csv_val: personal_names.get(csv_val, "")
            for csv_val in positive_csv_values()
        },
    })


@router.post("/visualizador/categories")
def visualizador_set_categories(
    request: Request,
    categories: str = Form(""),
) -> JSONResponse:
    """Cambia el orden/seleccion de circulos del Venn. Max 4."""
    project_dir, _ = get_paths(request)
    cat_list = [c.strip() for c in categories.split(",") if c.strip()]
    if len(cat_list) > 4:
        raise HTTPException(
            status_code=400, detail=f"Máximo 4 categorías (mandaste {len(cat_list)})"
        )
    for c in cat_list:
        if find_side(c) is None:
            raise HTTPException(status_code=400, detail=f"Categoría inválida: {c!r}")
    with viz_lock(_DEFAULT_VIZ):
        v = load_visualization(project_dir, _DEFAULT_VIZ)
        v.categories = cat_list
        save_visualization(project_dir, v)
    return JSONResponse({"ok": True, "categories": v.categories})


@router.post("/visualizador/region/{region_key}/concept")
def visualizador_set_region_concept(
    request: Request,
    region_key: str,
    concept: str = Form(""),
) -> JSONResponse:
    """Guarda el concepto de una region.

    NO escribe a default.yaml. Escribe a intersection_concepts.yaml usando
    la concept_key derivada de region_key + categories actuales. Asi /sintesis
    ve el mismo dato y viceversa.

    Para 'out': no hay concept_key valido (es el complemento, no una
    interseccion). Se rechaza con 400 — el frontend NO debe permitir editar
    concept en la region exterior.
    """
    project_dir, _ = get_paths(request)
    if region_key == "out":
        raise HTTPException(
            status_code=400,
            detail="La region 'out' no almacena concepto (es el complemento del set)",
        )
    v = load_visualization(project_dir, _DEFAULT_VIZ)
    csv_values = region_to_csv_values(region_key, v.categories)
    if not csv_values:
        raise HTTPException(
            status_code=404,
            detail=f"Region {region_key!r} no valida para categories={v.categories}",
        )
    key = intersection_concepts.concept_key(csv_values)
    # Validar que el key es uno de los conocidos (defensa en profundidad)
    valid_keys = {
        intersection_concepts.concept_key(c)
        for c in intersection_concepts.ALL_CONCEPT_KEYS
    }
    if key not in valid_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Intersection key {key!r} no esta en el catalogo canonico",
        )
    yaml_path = intersection_concepts.yaml_path_for(project_dir)
    intersection_concepts.save_personal_name(yaml_path, key, concept)
    return JSONResponse({"ok": True, "concept": concept.strip(), "key": key})


@router.get("/visualizador/venn.svg")
def visualizador_venn_svg(request: Request) -> Response:
    """Devuelve el Venn-4 con callouts como SVG descargable (nombres completos).

    Reusa export.render_venn_svg -> misma plantilla que el snapshot HTML, asi
    el SVG que baja el usuario no trunca ni una palabra (a diferencia del Venn
    interactivo en pantalla, que si abrevia para caber en las regiones).
    """
    project_dir, _ = get_paths(request)
    svg = export.render_venn_svg(project_dir)
    slug = project_dir.name
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'attachment; filename="ikigai-{slug}.svg"'
        },
    )


@router.get("/visualizador/data")
def visualizador_data(request: Request) -> JSONResponse:
    """Devuelve el estado completo del visualizador como JSON (derivado).

    Usado por el frontend para refrescar la viz tras cambios en /inventario
    o /sintesis sin recargar pagina.
    """
    project_dir, items_path = get_paths(request)
    v = load_visualization(project_dir, _DEFAULT_VIZ)
    region_views = derive_region_views(v, items_path)
    return JSONResponse(
        {
            "name": v.name,
            "title": v.title,
            "categories": v.categories,
            "summary": v.summary,
            "regions": region_views,
        }
    )


@router.patch("/visualizador/summary")
def visualizador_set_summary(
    request: Request,
    summary: str = Form(""),
) -> JSONResponse:
    project_dir, _ = get_paths(request)
    with viz_lock(_DEFAULT_VIZ):
        v = load_visualization(project_dir, _DEFAULT_VIZ)
        v.summary = summary.strip()
        save_visualization(project_dir, v)
    return JSONResponse({"ok": True, "summary": v.summary})


