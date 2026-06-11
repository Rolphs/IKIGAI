from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from ikigai import algebra, auditor, intersection_concepts, jsonl_store
from ikigai.algebra_state import load_algebra_state
from ikigai.cuadrantes import CUADRANTES, all_csv_values, find_side
from ikigai.item_queries import tag_fields_for_cuadrante
from ikigai.models import Item
from ikigai.navigation_context import resolve_master_from_request
from ikigai.render import get_paths, render

router = APIRouter(prefix="/sintesis", tags=["sintesis"])

def _evaluate_expression(
    expr: str,
    primitive_sets: dict[str, frozenset[str]],
    items_by_id: dict[str, Item],
    universe: frozenset[str],
) -> dict[str, Any]:
    result_ids = algebra.evaluate(expr, primitive_sets, universe=universe)
    notation = algebra.render_dual(expr)
    result_items = sorted(
        (items_by_id[i] for i in result_ids if i in items_by_id),
        key=lambda it: it.id,
    )
    return {
        "expression": expr,
        "notation_set": notation.set_theory,
        "notation_bool": notation.boolean,
        "matched_items": result_items,
        "count": len(result_items),
    }

def _evaluate_all_presets(
    primitive_sets: dict[str, frozenset[str]],
    items_by_id: dict[str, Item],
    universe: frozenset[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for preset in algebra.PRESETS:
        evaluated = _evaluate_expression(preset.expression, primitive_sets, items_by_id, universe)
        evaluated["key"] = preset.key
        evaluated["label"] = preset.label
        evaluated["description"] = preset.description
        out.append(evaluated)
    return out

def _is_valid_key(key: str) -> bool:
    """True si key es un nodo nombrable del catalogo (primitivo o interseccion)."""
    valid = {intersection_concepts.concept_key(c) for c in intersection_concepts.ALL_CONCEPT_KEYS}
    return key in valid


def _unknown_key_response(key: str) -> Response:
    return HTMLResponse(
        f"<p class='text-danger-100 text-xs'>Interseccion desconocida: {key!r}</p>",
        status_code=400,
    )


def _compute_cards(project_dir: Any) -> list[dict[str, Any]]:
    """Carga estado + nombres y computa las cards. Fuente unica de verdad
    para los re-renders de /sintesis (save concepto, add item)."""
    _, primitive_sets, items_by_id, _ = load_algebra_state(project_dir)
    personal_names = intersection_concepts.load_personal_names_for(project_dir)
    return intersection_concepts.compute_all_intersections(
        primitive_sets, items_by_id, personal_names
    )


def _card_html(request: Request, card: dict[str, Any], *, oob: bool) -> str:
    """Renderiza UNA card a string. `oob=True` marca el <article> con
    hx-swap-oob para que HTMX la actualice por id sin ser el target principal."""
    resp = render(request, "_intersection_card.html.j2", {"c": card, "oob": oob})
    # resp.body puede ser bytes o memoryview segun la version de Starlette;
    # bytes(...) normaliza ambos antes de decodificar.
    return bytes(resp.body).decode("utf-8")


def _render_updated_card(request: Request, project_dir: Any, key: str) -> Response:
    """Re-computa SOLO la card de `key` y la devuelve como fragmento (HTMX swap).

    Usado por /item/add: agregar un item a un primitivo no cambia ninguna otra
    card (el item lleva un solo tag, no puede ser cohabitante de intersecciones),
    asi que no hace falta propagar.
    """
    card = next((c for c in _compute_cards(project_dir) if c["key"] == key), None)
    if card is None:  # pragma: no cover — guarded by _is_valid_key above
        return HTMLResponse("", status_code=500)
    return HTMLResponse(_card_html(request, card, oob=False))


def _render_card_and_dependents(request: Request, project_dir: Any, key: str) -> Response:
    """Devuelve la card guardada (swap normal) + las cards que la usan como
    ingrediente (OOB swap). Arregla la PROPAGACION: al bautizar una sintesis,
    todas las cards de capas superiores que la contienen reflejan el nombre
    nuevo al instante, sin refrescar la pagina.

    "Usa como ingrediente" = la interseccion guardada es un SUBCONJUNTO ESTRICTO
    de la otra (ej. guardar "1,2" actualiza "1,2,3", "1,2,4", "1,2,3,4";
    guardar el primitivo "1" actualiza toda card que contenga el circulo 1).
    """
    all_cards = _compute_cards(project_dir)
    saved = next((c for c in all_cards if c["key"] == key), None)
    if saved is None:  # pragma: no cover — guarded by _is_valid_key above
        return HTMLResponse("", status_code=500)
    saved_circles = saved["circles"]
    parts = [_card_html(request, saved, oob=False)]
    parts += [
        _card_html(request, c, oob=True)
        for c in all_cards
        if saved_circles < c["circles"]
    ]
    return HTMLResponse("".join(parts))


@router.get("", response_class=HTMLResponse)
def sintesis_get(request: Request) -> Response:
    project_dir, _ = get_paths(request)
    master_viz_name, master_title = resolve_master_from_request(request, project_dir)
    items_by_cuad, primitive_sets, items_by_id, universe = load_algebra_state(project_dir)
    evaluated_presets = _evaluate_all_presets(primitive_sets, items_by_id, universe)

    # Las 11 intersecciones positivas (la "carta" para acunar vocabulario personal).
    # Solo nos interesan los circulos positivos (1, 2, 3, 4) — la combinatoria con
    # sombra explota a 255 cards y rompe la UX. Si se necesita en V2, se agrega.
    personal_names = intersection_concepts.load_personal_names_for(project_dir)
    intersection_cards = intersection_concepts.compute_all_intersections(
        primitive_sets, items_by_id, personal_names
    )

    # Matriz de similitud (Jaccard) entre presets principales
    # Solo tomamos los presets para no saturar el heatmap (pueden ser muchos)
    matrix_labels = [e["label"] for e in evaluated_presets]
    matrix_data = []
    for p1 in evaluated_presets:
        row = []
        set1 = frozenset(it.id for it in p1["matched_items"])
        for p2 in evaluated_presets:
            set2 = frozenset(it.id for it in p2["matched_items"])
            score = algebra.jaccard(set1, set2)
            row.append(round(score, 3))
        matrix_data.append(row)

    # Auditoria de sentido
    audit_report = auditor.run_audit(project_dir)

    return render(request, "sintesis.html.j2", {
        "cuadrantes": CUADRANTES,
        "items_by_cuad": items_by_cuad,
        "cardinalities": {k: len(v) for k, v in primitive_sets.items()},
        "universe_size": len(universe),
        "intersection_cards": intersection_cards,
        "evaluated_presets": evaluated_presets,
        "similarity_matrix": {"labels": matrix_labels, "data": matrix_data},
        "master_title": master_title,
        "master_viz_name": master_viz_name,
        "audit": audit_report,
        # Conceptos sinteticos por dominio individual (key="1", "2", "3", "4"):
        # el input editable de cada set_card lee/escribe estos. Compartido
        # con /visualizador via el mismo intersection_concepts.yaml.
        "primitive_concepts": {
            csv_val: personal_names.get(csv_val, "")
            for csv_val in all_csv_values()
        },
    })


@router.post("/concept", response_class=HTMLResponse)
def sintesis_save_concept(
    request: Request,
    key: str = Form(...),
    personal_name: str = Form(""),
) -> Response:
    """Guarda (o borra, si viene vacio) el nombre UNICO de una interseccion.

    Usado por las cards de capa 1-3 (un solo concepto por nodo). Devuelve solo
    el fragmento de la card actualizada (HTMX swap por id).
    """
    project_dir, _ = get_paths(request)
    if not _is_valid_key(key):
        return _unknown_key_response(key)

    yaml_path = intersection_concepts.yaml_path_for(project_dir)
    intersection_concepts.save_personal_name(yaml_path, key, personal_name)
    return _render_card_and_dependents(request, project_dir, key)


@router.post("/item/add", response_class=HTMLResponse)
def sintesis_add_item(
    request: Request,
    key: str = Form(...),
    item_text: str = Form(""),
) -> Response:
    """Agrega un item nuevo al circulo primitivo `key` y re-renderiza la card.

    El item se crea en el inventario con cuadrante=key; para positivos (1-4)
    se auto-asigna el tag del circulo (asi cae en su set por tag), las sombras
    (1b-4b) se agrupan por `cuadrante`. Reusa jsonl_store + el mapeo unico
    circulo->tag (DRY con /inventario). Solo aplica a capa 0 (la UI solo pone
    el boton ahi); un key no-primitivo se rechaza.
    """
    project_dir, items_path = get_paths(request)
    if find_side(key) is None:
        return _unknown_key_response(key)

    text = item_text.strip()
    if text:
        jsonl_store.add_with_generated_id(
            items_path, key, item=text, fuente="sintesis",
            **tag_fields_for_cuadrante(key),
        )
    # Si vino vacio: no-op silencioso (re-render sin cambios, sin spamear error).
    return _render_updated_card(request, project_dir, key)


@router.post("/evaluate", response_class=HTMLResponse)
def sintesis_evaluate(request: Request, expr: str = Form(...)) -> Response:
    project_dir, _ = get_paths(request)
    _, primitive_sets, items_by_id, universe = load_algebra_state(project_dir)
    try:
        evaluated = _evaluate_expression(expr, primitive_sets, items_by_id, universe)
    except algebra.ExpressionError as e:
        return render(request, "_algebra_eval_error.html.j2", {"expr": expr, "error": str(e)})
    evaluated["key"] = "custom"
    evaluated["label"] = "Tu expresión"
    evaluated["description"] = ""
    return render(request, "_algebra_eval_card.html.j2", {"e": evaluated})
