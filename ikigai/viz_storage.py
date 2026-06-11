"""viz_storage.py - Persistencia slim de Visualization (v0.3.0+).

Refactor "una fuente de verdad": single viz "default" por proyecto. NO mas
multi-viz (rename/delete/create), NO mas regions[].concept en YAML.

Path convention:
  <project_dir>/visualizations/default.yaml

Formato del YAML:
  name: default
  title: "Default"
  categories: ["1", "2", "3", "4"]   # 0-4 csv_values (orden define a,b,c,d)
  summary: "resumen ejecutivo libre"

Los conceptos por region viven en intersection_concepts.yaml (compartido con
/sintesis). Los items por region se derivan del CSV.
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

from ikigai import atomic_io
from ikigai.locks import keyed_lock
from ikigai.viz_models import Visualization

# ─── Lock por viz_name ───
#
# Race documentada: clicks rapidos en cat-pills disparan POSTs concurrentes
# a /visualizador/categories. Sin lock, dos requests pueden cargar el mismo
# estado A, modificarlo a su antojo y escribirlo (ultimo gana, perdiendo
# cambios del primero). Solucion: serializar load+modify+save con un lock
# por viz_name. El registro de locks vive ahora en locks.py (compartido).


@contextmanager
def viz_lock(name: str) -> Iterator[None]:
    """Context manager para serializar load+modify+save de una viz.

    Uso tipico:
        with viz_lock(viz_name):
            v = load_visualization(project_dir, viz_name)
            v.categories = nuevas_cats
            save_visualization(project_dir, v)

    Mantener el bloque corto. NO hacer I/O lento ni llamadas al LLM adentro.
    """
    with keyed_lock(f"viz:{name}"):
        yield


def visualizations_dir(project_dir: Path) -> Path:
    return project_dir / "visualizations"


def viz_path(project_dir: Path, name: str = "default") -> Path:
    return visualizations_dir(project_dir) / f"{name}.yaml"


def load_visualization(project_dir: Path, name: str = "default") -> Visualization:
    """Carga la viz. Si no existe, devuelve una nueva con defaults sanos."""
    path = viz_path(project_dir, name)
    if not path.exists():
        return Visualization(name=name, title=name.title())

    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Visualization(
        name=str(raw.get("name", name)),
        title=str(raw.get("title", name.title())),
        categories=list(raw.get("categories", ["1", "2", "3", "4"]) or []),
        summary=str(raw.get("summary", "")),
    )


def save_visualization(project_dir: Path, viz: Visualization) -> Path:
    """Persiste viz a YAML con atomic replace.

    NOTA: no escribe `regions` (legacy). Solo {name, title, categories, summary}.
    Si necesitas el concepto de una region, lee intersection_concepts.yaml.
    """
    visualizations_dir(project_dir).mkdir(parents=True, exist_ok=True)
    path = viz_path(project_dir, viz.name)
    payload: dict[str, Any] = {
        "name": viz.name,
        "title": viz.title,
        "categories": viz.categories,
        "summary": viz.summary,
    }
    serialized = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    atomic_io.atomic_write_text(path, serialized)
    return path
