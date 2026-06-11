"""
item_queries.py — Filtros y agrupaciones puras sobre listas de Items.

SRP: este módulo NO toca el filesystem. Recibe `list[Item]` y devuelve
sublistas/dicts. La persistencia vive en `jsonl_store.py`; la portabilidad
(CSV import/export) vive en `portability.py`.

Vocabulario chi²:
  - `items_by_evoking_cuadrante`: agrupa por la PREGUNTA que evocó el item
    (columna `cuadrante`). Útil para Inventario (cajas por pregunta) e
    Introspección. Es la columna "esperada" de la tabla de contingencia.
  - `items_by_tag`: agrupa por el CÍRCULO al que el usuario asignó el item
    vía tags (tag_amo/bueno/mundo/pago). Útil para el Venn / álgebra. Es
    la columna "observada" de la tabla de contingencia.
  - `classify_items_by_circle`: una sola pasada → los 8 buckets de
    círculos (4 positivos + 4 sombras). 8x más rápido que llamar
    `items_by_tag` 8 veces.
"""
from __future__ import annotations

from ikigai.models import Item

# Convención: tags positivos. Sombras (1b..4b) no tienen columna de tag;
# se infieren por la columna `cuadrante`.
_CIRCLE_TO_TAG_COLUMN: dict[str, str] = {
    "1": "tag_amo",
    "2": "tag_bueno",
    "3": "tag_mundo",
    "4": "tag_pago",
}
_SHADOW_CSV_VALUES: frozenset[str] = frozenset({"1b", "2b", "3b", "4b"})
_TAG_TRUTHY_VALUES: frozenset[str] = frozenset(
    {"1", "true", "on", "yes", "si", "sí"}
)


def _is_tag_truthy(value: str) -> bool:
    return str(value).strip().lower() in _TAG_TRUTHY_VALUES


def tag_fields_for_cuadrante(cuadrante: str) -> dict[str, str]:
    """Tags a asignar al CREAR un item en `cuadrante`.

    - Positivos (1-4) -> {su tag_col: "1"} (asi cae en el set por tag).
    - Sombras (1b-4b) -> todos los tags vacios (se agrupan por la columna
      `cuadrante`, no por tag).

    Util para crear items fuera del flujo de /inventario (ej. el boton "+"
    de /sintesis). Mantiene el mapeo circulo->tag en UN solo lugar.
    """
    fields = {col: "" for col in _CIRCLE_TO_TAG_COLUMN.values()}
    col = _CIRCLE_TO_TAG_COLUMN.get(cuadrante)
    if col:
        fields[col] = "1"
    return fields


# ─────────────────────────────────────────────────────────────
# Filtros
# ─────────────────────────────────────────────────────────────

def items_by_evoking_cuadrante(items: list[Item], cuadrante_value: str) -> list[Item]:
    """Items cuya columna `cuadrante` coincide. Preserva orden de entrada."""
    return [it for it in items if it.cuadrante == cuadrante_value]


def items_by_tag(items: list[Item], csv_value: str) -> list[Item]:
    """Items filtrados por el CÍRCULO asignado vía tag.

    - '1','2','3','4'      → filtra por tag_amo/bueno/mundo/pago.
    - '1b','2b','3b','4b'  → fallback a `cuadrante` (no hay tags negativos;
                            los items de sombra se agrupan por la pregunta
                            evocadora).
    - cualquier otro       → lista vacía.
    """
    if csv_value in _CIRCLE_TO_TAG_COLUMN:
        column = _CIRCLE_TO_TAG_COLUMN[csv_value]
        return [it for it in items if _is_tag_truthy(getattr(it, column, ""))]
    if csv_value.endswith("b"):
        return items_by_evoking_cuadrante(items, csv_value)
    return []


def classify_items_by_circle(items: list[Item]) -> dict[str, list[Item]]:
    """Una sola pasada → los 8 buckets (4 positivos + 4 sombras).

    Equivale a 8 llamadas a `items_by_tag` pero recorre la lista una vez.

    - Positivos (1,2,3,4): un item entra si su tag_X correspondiente es
      truthy. Un mismo item PUEDE caer en más de un círculo positivo
      (los tags no son exclusivos — algo puede ser 'amo' y 'bueno').
    - Sombras (1b,2b,3b,4b): un item entra si su columna `cuadrante`
      coincide. Las sombras SÍ son exclusivas (un item evoca a una sola
      pregunta).
    """
    buckets: dict[str, list[Item]] = {
        "1": [], "2": [], "3": [], "4": [],
        "1b": [], "2b": [], "3b": [], "4b": [],
    }
    for it in items:
        # Positivos
        for circle_value, tag_column in _CIRCLE_TO_TAG_COLUMN.items():
            if _is_tag_truthy(getattr(it, tag_column, "")):
                buckets[circle_value].append(it)
        # Sombras
        if it.cuadrante in _SHADOW_CSV_VALUES:
            buckets[it.cuadrante].append(it)
    return buckets
