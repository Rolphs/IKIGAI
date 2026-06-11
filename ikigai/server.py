"""
server.py - FastAPI app multi-ikigai con workspace.

ARQUITECTURA:
    - `create_app(workspace_root)` recibe la CARPETA-RAIZ que contiene N
      subdirectorios (uno por ikigai). Ya NO recibe un project_dir.
    - Todos los routes de paginas viven bajo /u/{ikigai_name}/...
      (visualizador, inventario, sintesis, introspeccion).
    - Routes workspace-level (no /u/...) sirven el listing, creacion, etc.

URLS:
    GET  /                              -> redirige al primer ikigai disponible
                                           (o a /_new si el workspace esta vacio)
    GET  /_new                          -> form para crear un ikigai nuevo
    POST /_new                          -> crea el ikigai y redirige a su viz
    GET  /u/{name}/visualizador         -> viz de un ikigai especifico
    GET  /u/{name}/inventario           -> inventario
    ... (igual para los otros routers)
"""
from __future__ import annotations

import html
import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
)
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from ikigai.intersections import lookup as canonical_lookup
from ikigai.intersections import to_json_dict as canonical_to_json_dict
from ikigai.migrations import migrate_all_if_needed
from ikigai.render import render
from ikigai.routers import cuestionario, inventario, sintesis, visualizador
from ikigai.workspace import create_ikigai, derive_unique_slug, list_ikigais

logger = logging.getLogger(__name__)


def create_app(workspace_root: Path) -> FastAPI:
    """Factory de la aplicacion FastAPI multi-ikigai.

    workspace_root: directorio que contiene N subdirs ikigai (1 por persona).
    """
    workspace_root = workspace_root.resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)

    # Migraciones por-ikigai: corre migrations en CADA subdir existente.
    for info in list_ikigais(workspace_root):
        for msg in migrate_all_if_needed(info.project_dir):
            logger.info("[migration:%s] %s", info.name, msg)

    app = FastAPI(title="ikigai \U0001f337")

    # Dependencias globales del app.
    app.state.workspace_root = workspace_root
    app.state.templates = Jinja2Templates(
        directory=Path(__file__).parent / "templates" / "server"
    )
    app.state.canonical_to_json_dict = canonical_to_json_dict
    app.state.canonical_lookup = canonical_lookup

    # Static files (CSS, JS).
    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).parent / "static"),
        name="static",
    )

    # ════════ Per-ikigai routes (montadas bajo /u/{ikigai_name}/) ════════
    # APIRouter permite agrupar todos los routers de paginas bajo un prefix
    # comun. Cada handler accede al name via request.path_params["ikigai_name"].
    ikigai_router = APIRouter(prefix="/u/{ikigai_name}")
    ikigai_router.include_router(visualizador.router)
    ikigai_router.include_router(inventario.router)
    ikigai_router.include_router(cuestionario.router)
    ikigai_router.include_router(sintesis.router)
    app.include_router(ikigai_router)

    # ════════ Workspace-level routes (sin prefix /u/...) ════════
    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness/readiness probe para deploys (k8s, contenedores, etc.).

        Sin estado y sin I/O: responde 200 mientras el proceso este vivo.
        Deliberadamente NO toca el workspace ni el filesystem para que el
        probe no falle por un disco lento o un workspace vacio.
        """
        return {"status": "ok"}

    @app.get("/", response_class=RedirectResponse)
    def root() -> str:
        """Redirige al primer ikigai disponible o al wizard si no hay ninguno."""
        ikigais = list_ikigais(workspace_root)
        if not ikigais:
            return "/_new"
        # Primer ikigai por orden alfabetico de title. Lleva a su introspeccion.
        return f"/u/{ikigais[0].name}/introspeccion"

    @app.get("/_new", response_class=HTMLResponse)
    def new_form(request: Request) -> Response:
        """Formulario para crear un nuevo ikigai."""
        return render(request, "new_ikigai.html.j2", {})

    @app.get("/_new/slug-preview", response_class=HTMLResponse)
    def new_slug_preview(request: Request, name: str = "") -> Response:
        """Devuelve el slug que se derivaria del nombre tecleado (preview HTMX).

        Fuente unica de verdad: reusa `derive_unique_slug`, asi el preview
        nunca miente respecto a lo que `create_ikigai` hara de verdad.
        """
        name = name.strip()
        slug = derive_unique_slug(workspace_root, name) if name else ""
        return render(request, "_slug_preview.html.j2", {"slug": slug})

    @app.post("/_new")
    def new_create(
        request: Request,
        name: str = Form(...),
        slug: str = Form(""),
    ) -> Response:
        """Crea un nuevo ikigai y redirige a su introspeccion.

        `name` es el nombre amigable (libre). `slug` es el override opcional
        del modo avanzado; si viene vacio, se deriva del name.
        """
        try:
            created = create_ikigai(
                workspace_root, name.strip(), slug.strip() or None
            )
        except (ValueError, FileExistsError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(
            url=f"/u/{created.name}/introspeccion", status_code=303
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> Response:
        """Deja que los 4xx/HTTPException conserven su status y detalle.

        Explicito a proposito: sin este handler, un lector podria pensar que
        el catch-all de abajo (500) se traga los 404/400 intencionales. No lo
        hace —Starlette enruta por tipo— pero dejarlo escrito evita la duda.
        """
        return await default_http_exception_handler(request, exc)

    @app.exception_handler(Exception)
    def global_exception_handler(request: Request, exc: Exception) -> Response:
        """Catch-all SOLO para errores no manejados (500).

        Seguridad: el mensaje de la excepcion se escapa con `html.escape`
        antes de inyectarlo en el HTML. Sin esto, un texto controlable por
        input reflejado en el error permitiria inyeccion de HTML/JS (XSS).
        """
        logger.exception("Error no manejado en %s %s", request.method, request.url.path)
        safe_detail = html.escape(str(exc))
        return HTMLResponse(
            content=f"""
            <html><body style="font-family:sans-serif; padding:2rem;">
            <h1 style="color:#dc2626">🌷 Algo salió mal</h1>
            <p style="color:#74767c">Error: <code>{safe_detail}</code></p>
            <hr/>
            <p><a href="/">Volver al inicio</a></p>
            </body></html>
            """,
            status_code=500,
        )

    return app
