"""render.py - Helper unificado para renderizar templates.

PROBLEMA QUE RESUELVE: Todos los templates necesitan saber el URL prefix
del ikigai actual (`/u/{name}/...`) para construir links y formularios
correctamente. Sin esta abstraccion, cada handler tendria que recordar
inyectar `ikigai_name` y `ikigai_url` en el contexto del template, y
olvidarse de uno rompe la navegacion.

USO:
    return render(request, "inventario.html.j2", {
        "cuadrantes_data": cuadrantes_data,
        ...
    })

Los siguientes vars siempre estan disponibles en TODOS los templates:
    - ikigai_name:  slug del ikigai actual (str, "" si no hay)
    - ikigai_url:   prefix completo para URLs (/u/{name} o "" si no hay)
    - all_ikigais:  list[IkigaiInfo] para poblar el dropdown del chrome
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import Response

from ikigai.algebra_state import resolve_items_path
from ikigai.workspace import list_ikigais, resolve_project_dir


def get_paths(request: Request) -> tuple[Path, Path]:
    """Resuelve (project_dir, items_path) del ikigai actual.

    Lee `ikigai_name` de los path_params (la URL fue /u/{name}/...).
    Si el name no existe o es invalido, lanza HTTPException(404).
    """
    name = request.path_params.get("ikigai_name", "")
    if not name:
        raise HTTPException(status_code=404, detail="Falta el nombre del ikigai en la URL")
    workspace_root = request.app.state.workspace_root
    try:
        project_dir = resolve_project_dir(workspace_root, name)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    items_path = resolve_items_path(project_dir)
    return project_dir, items_path


def render(
    request: Request,
    template_name: str,
    context: dict[str, Any] | None = None,
) -> Response:
    """Renderiza template inyectando vars globales (ikigai_url, etc.).

    Acepta `context` opcional para vars page-specific. Los vars globales
    SIEMPRE se aniaden (no se pueden override desde el handler para evitar
    bugs sutiles de navegacion).
    """
    ctx: dict[str, Any] = dict(context or {})

    # Resolve current ikigai from path param (si la URL es /u/{name}/...).
    name = request.path_params.get("ikigai_name", "") or ""
    ctx["ikigai_name"] = name
    ctx["ikigai_url"] = f"/u/{name}" if name else ""

    # Lista de todos los ikigais para popular el dropdown del chrome.
    # Es barato: solo lee directorios (no JSONs pesados).
    workspace_root = request.app.state.workspace_root
    ctx["all_ikigais"] = list_ikigais(workspace_root)

    templates = request.app.state.templates
    return templates.TemplateResponse(request, template_name, ctx)
