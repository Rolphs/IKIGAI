"""
Carga del estado algebraico desde el JSONL del proyecto.

Regla simple:
- Existe `tulipan.jsonl` → lo usamos.
- Nada existe → estado vacio (universo vacio, buckets vacios).

Ademas:
- Circulos positivos (1,2,3,4) se construyen por TAG asignado.
- Sombras (1b,2b,3b,4b) se construyen por `cuadrante` evocador.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from ikigai import jsonl_store
from ikigai.item_queries import classify_items_by_circle
from ikigai.models import Item

JSONL_NAME = "tulipan.jsonl"


class AlgebraState(NamedTuple):
    items_by_cuad: dict[str, list[Item]]
    primitive_sets: dict[str, frozenset[str]]
    items_by_id: dict[str, Item]
    universe: frozenset[str]


def resolve_items_path(project_dir: Path) -> Path:
    """Devuelve el path del JSONL del proyecto."""
    return project_dir / JSONL_NAME


def load_algebra_state(project_dir_or_path: Path) -> AlgebraState:
    """Carga el estado algebraico desde el JSONL del proyecto.

    Acepta tanto un `project_dir` (resuelve `tulipan.jsonl` adentro) como
    un path directo al archivo JSONL — util para tests que pasan el path
    explicitamente.
    """
    if project_dir_or_path.is_file() or project_dir_or_path.suffix == ".jsonl":
        items_path = project_dir_or_path
    else:
        items_path = resolve_items_path(project_dir_or_path)

    all_items = jsonl_store.read_all(items_path)
    items_by_id = {it.id: it for it in all_items}
    universe = frozenset(items_by_id.keys())
    items_by_cuad = classify_items_by_circle(all_items)
    primitive_sets = {
        csv_val: frozenset(it.id for it in lst)
        for csv_val, lst in items_by_cuad.items()
    }
    return AlgebraState(
        items_by_cuad=items_by_cuad,
        primitive_sets=primitive_sets,
        items_by_id=items_by_id,
        universe=universe,
    )
