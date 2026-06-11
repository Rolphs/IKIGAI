from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from ikigai import jsonl_store
from ikigai.cuadrantes import CUADRANTES, find_side
from ikigai.item_queries import items_by_evoking_cuadrante
from ikigai.navigation_context import resolve_master_from_request
from ikigai.render import get_paths, render
from ikigai.stats import (
    CIRCLE_BAR_BG,
    CIRCLE_EMOJIS,
    CIRCLE_LABELS,
    CIRCLES,
    section_fingerprint,
)

if TYPE_CHECKING:
    pass

router = APIRouter(prefix="/introspeccion", tags=["cuestionario"])

def _get_all_sides() -> list[dict[str, Any]]:
    """Aplana los 4 pares en una lista de 8 lados."""
    sides: list[dict[str, Any]] = []
    for pair in CUADRANTES:
        sides.append({"pair": pair, "side": pair.positivo, "type": "positivo"})
        sides.append({"pair": pair, "side": pair.negativo, "type": "negativo"})
    return sides

@router.get("", response_class=HTMLResponse)
def introspeccion_get(request: Request) -> Response:
    project_dir, items_path = get_paths(request)
    master_viz_name, master_title = resolve_master_from_request(request, project_dir)

    all_items = jsonl_store.read_all(items_path)
    sections = []
    for index, side_data in enumerate(_get_all_sides(), start=1):
        items = items_by_evoking_cuadrante(all_items, side_data["side"].csv_value)
        # Convertimos a dicts planos para que Jinja2 tojson no explote con CuadrantePair/Side
        pair = side_data["pair"]
        side = side_data["side"]

        # Items serializables para Jinja2 (frozen dataclass -> dict).
        # Solo exponemos lo que la pill necesita renderizar.
        items_payload = [
            {
                "id": it.id,
                "item": it.item,
                "tag_amo": it.tag_amo,
                "tag_bueno": it.tag_bueno,
                "tag_mundo": it.tag_mundo,
                "tag_pago": it.tag_pago,
                "is_aligned": it.is_aligned_with_evocation,
            }
            for it in items
        ]

        sections.append({
            "index": index,
            "type": side_data["type"],
            "pair": {
                "titulo": pair.titulo,
                "descripcion": pair.descripcion,
            },
            "side": {
                "csv_value": side.csv_value,
                "label": side.label,
                "emoji": side.emoji,
                "pregunta_evocativa": side.pregunta_evocativa,
            },
            "responses": items_payload,
            "fingerprint": section_fingerprint(items, side.csv_value),
        })

    # Todas las secciones se renderizan siempre, cada una con su form inline
    # para agregar reflexiones. Sin cursor: el usuario responde donde quiera.
    return render(request, "cuestionario.html.j2", {
        "sections": sections,
        "master_title": master_title,
        "master_viz_name": master_viz_name,
        "circles": CIRCLES,
        "circle_labels": CIRCLE_LABELS,
        "circle_emojis": CIRCLE_EMOJIS,
        "circle_bar_bg": CIRCLE_BAR_BG,
    })


@router.get("/section/{csv_value}/strip", response_class=HTMLResponse)
def introspeccion_section_strip(request: Request, csv_value: str) -> Response:
    """Fragment endpoint: HTML del strip de resultado real para una sección.

    Lo llama el JS del cuestionario después de cada submit para mantener
    la barra de distribución sincronizada con los pills (la propiedad
    'paralela' del diseño: pregunta y resultado real siempre cuadran).
    """
    found = find_side(csv_value)
    if found is None:
        raise HTTPException(status_code=404, detail=f"csv_value inválido: {csv_value!r}")
    _, side = found

    _, items_path = get_paths(request)
    items = items_by_evoking_cuadrante(jsonl_store.read_all(items_path), csv_value)

    return render(request, "_cuestionario_result_strip.html.j2", {
        "side": {
            "csv_value": side.csv_value,
            "emoji": side.emoji,
        },
        "fingerprint": section_fingerprint(items, csv_value),
        "circles": CIRCLES,
        "circle_labels": CIRCLE_LABELS,
        "circle_emojis": CIRCLE_EMOJIS,
        "circle_bar_bg": CIRCLE_BAR_BG,
    })

