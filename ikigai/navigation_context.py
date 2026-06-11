"""navigation_context.py - Master viz resolver (slim, single-viz).

Tras el refactor a single-viz "default", esto es casi trivial: siempre
devuelve ("default", titulo). Se mantiene como funcion (no inline) para no
romper templates/routers que dependen de master_viz_name / master_title.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Request

from ikigai.viz_storage import load_visualization


def resolve_master_from_request(request: Request, project_dir: Path) -> tuple[str, str]:
    """Resuelve la viz pivote (name, title). Siempre ("default", titulo) en single-viz.

    `request` se mantiene en la firma (interfaz estable de los routers) aunque
    hoy no se use: cuando vuelva multi-viz, de aqui se leeria la viz preferida.
    """
    viz = load_visualization(project_dir, "default")
    title = (viz.title or "").strip() or "Default"
    return "default", title
