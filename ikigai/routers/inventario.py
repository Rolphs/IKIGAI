from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ikigai import jsonl_store
from ikigai.cuadrantes import CUADRANTES, find_side
from ikigai.item_queries import items_by_evoking_cuadrante
from ikigai.models import VALID_SCORES, Item
from ikigai.navigation_context import resolve_master_from_request
from ikigai.portability import (
    CsvImportError,
    build_csv_template_text,
    export_csv_from_items,
    import_csv_text,
)
from ikigai.render import get_paths, render

router = APIRouter(prefix="/inventario", tags=["inventario"])


@router.get("", response_class=HTMLResponse)
def inventario_get(request: Request) -> Response:
    project_dir, items_path = get_paths(request)
    master_viz_name, master_title = resolve_master_from_request(request, project_dir)
    all_items = jsonl_store.read_all(items_path)
    cuadrantes_data = []
    for pair in CUADRANTES:
        cuadrantes_data.append({
            "pair": pair,
            "positivos": items_by_evoking_cuadrante(all_items, pair.positivo.csv_value),
            "negativos": items_by_evoking_cuadrante(all_items, pair.negativo.csv_value),
        })
    return render(request, "inventario.html.j2", {
        "cuadrantes_data": cuadrantes_data,
        "items_path": str(items_path),
        "master_title": master_title,
        "master_viz_name": master_viz_name,
    })


@router.post("/item", response_class=HTMLResponse)
def inventario_post_item(
    request: Request,
    cuadrante: str = Form(...),
    item_text: str = Form(...),
    response_fragment: str = Form("inventario"),
    source: str = Form("inventario"),
    tag_amo: str = Form(""),
    tag_bueno: str = Form(""),
    tag_mundo: str = Form(""),
    tag_pago: str = Form(""),
    energia_1a5: str = Form(""),
    dominio_1a5: str = Form(""),
    impacto_1a5: str = Form(""),
    viabilidad_1a5: str = Form(""),
) -> Response:
    """Agrega un item nuevo y devuelve el partial apropiado.

    DRY: el guardado vive en un solo endpoint. La diferencia entre Inventario
    e Introspección es de presentación, así que el caller pide el fragmento.
    """
    _, items_path = get_paths(request)
    item_text = item_text.strip()
    if not item_text:
        raise HTTPException(status_code=400, detail="Item vacío")
    if find_side(cuadrante) is None:
        raise HTTPException(status_code=400, detail=f"Cuadrante inválido: {cuadrante!r}")

    scores = {
        "energia_1a5": energia_1a5.strip(),
        "dominio_1a5": dominio_1a5.strip(),
        "impacto_1a5": impacto_1a5.strip(),
        "viabilidad_1a5": viabilidad_1a5.strip(),
    }
    for field_name, value in scores.items():
        if value not in VALID_SCORES:
            raise HTTPException(status_code=400, detail=f"{field_name} debe estar entre 1 y 5")

    tag_values = {
        "tag_amo": "1" if tag_amo else "",
        "tag_bueno": "1" if tag_bueno else "",
        "tag_mundo": "1" if tag_mundo else "",
        "tag_pago": "1" if tag_pago else "",
    }

    # Modo zen-discovery: si no se mandó ningún tag y la pregunta es positiva
    # (1-4), auto-asignamos el tag del círculo evocador. Mantiene la
    # introspección en flow puro. Las sombras (1b-4b) no llevan tag por def.
    if not any(tag_values.values()) and cuadrante in {"1", "2", "3", "4"}:
        _cuadrante_to_tag_col = {
            "1": "tag_amo",
            "2": "tag_bueno",
            "3": "tag_mundo",
            "4": "tag_pago",
        }
        tag_values[_cuadrante_to_tag_col[cuadrante]] = "1"

    # D4: una sola lectura del store (genera id + append juntos).
    item = jsonl_store.add_with_generated_id(
        items_path,
        cuadrante,
        item=item_text,
        fuente=source,
        tag_amo=tag_values["tag_amo"],
        tag_bueno=tag_values["tag_bueno"],
        tag_mundo=tag_values["tag_mundo"],
        tag_pago=tag_values["tag_pago"],
        energia_1a5=scores["energia_1a5"],
        dominio_1a5=scores["dominio_1a5"],
        impacto_1a5=scores["impacto_1a5"],
        viabilidad_1a5=scores["viabilidad_1a5"],
    )

    template_name = (
        "_cuestionario_answer_pill.html.j2"
        if response_fragment == "introspeccion"
        else "_item_row.html.j2"
    )
    return render(request, template_name, {"item": item})


@router.delete("/item/{item_id}")
def inventario_delete_item(request: Request, item_id: str) -> Response:
    _, items_path = get_paths(request)
    ok = jsonl_store.delete(items_path, item_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Item {item_id!r} no existe")
    return Response(status_code=200, content="")


@router.patch("/item/{item_id}")
def inventario_update_item(
    request: Request,
    item_id: str,
    item_text: str = Form(None),
    cuadrante: str = Form(None),
) -> JSONResponse:
    _, items_path = get_paths(request)

    current = jsonl_store.get(items_path, item_id)
    if current is None:
        raise HTTPException(status_code=404, detail=f"Item {item_id!r} no existe")

    new_text = item_text.strip() if item_text is not None else current.item
    new_cuad = cuadrante.strip() if cuadrante is not None else current.cuadrante

    if not new_text:
        raise HTTPException(status_code=400, detail="Item vacío")
    if find_side(new_cuad) is None:
        raise HTTPException(status_code=400, detail=f"Cuadrante inválido: {new_cuad!r}")

    jsonl_store.update(items_path, item_id, item=new_text, cuadrante=new_cuad)
    return JSONResponse({"ok": True, "id": item_id, "item": new_text, "cuadrante": new_cuad})


@router.post("/item/restore", response_class=HTMLResponse)
def inventario_restore_item(
    request: Request,
    item_id: str = Form(...),
    cuadrante: str = Form(...),
    item_text: str = Form(...),
) -> Response:
    _, items_path = get_paths(request)
    item_text = item_text.strip()
    if not item_text:
        raise HTTPException(status_code=400, detail="Item vacío")
    if find_side(cuadrante) is None:
        raise HTTPException(status_code=400, detail=f"Cuadrante inválido: {cuadrante!r}")

    # Si el id original ya existe (rara vez en restore), generamos uno nuevo.
    final_id = item_id
    if jsonl_store.get(items_path, item_id) is not None:
        final_id = jsonl_store.next_id_for_cuadrante(items_path, cuadrante)

    item = Item(id=final_id, item=item_text, cuadrante=cuadrante, fuente="inventario-undo")
    jsonl_store.append(items_path, item)
    return render(request, "_item_row.html.j2", {"item": item})


@router.get("/csv/export")
def inventario_export_csv(request: Request) -> Response:
    """Export CSV para portabilidad humana (mail, Excel, otro proyecto).

    Si el JSONL existe con items, exportamos sus rows en formato CSV
    canónico (con BOM UTF-8 para que Excel lo abra bien). Si no hay items,
    devolvemos la plantilla con 2 filas de ejemplo.
    """
    _, items_path = get_paths(request)
    items = jsonl_store.read_all(items_path)
    if items:
        text = export_csv_from_items(items)
        filename = "tulipan.csv"
    else:
        text = build_csv_template_text()
        filename = "tulipan-plantilla.csv"
    body = b"\xef\xbb\xbf" + text.encode("utf-8")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/csv/import")
async def inventario_import_csv(request: Request, file: UploadFile = File(...)) -> JSONResponse:  # noqa: B008
    """Import CSV reemplaza completamente el JSONL del proyecto."""
    _, items_path = get_paths(request)
    try:
        raw = await file.read()
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Archivo no es UTF-8: {e}") from e
    try:
        n = import_csv_text(items_path, text)
    except CsvImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return JSONResponse({"ok": True, "n_rows": n, "filename": file.filename})
