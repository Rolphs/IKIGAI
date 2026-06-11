"""
portability.py — CSV ↔ JSONL para portabilidad humana.

Storage interna del proyecto = JSONL (`jsonl_store`).
Pero un humano todavía quiere:
  - Exportar a CSV para mandarlo por correo / abrir en Excel.
  - Importar un CSV que él (o un colega) editó offline.
  - Recibir una plantilla CSV vacía para llenarla.

Este módulo es el puente. NO se usa internamente por la app después del
boot; solo es un I/O para humanos.

Si en el futuro se agrega export a otro formato (Parquet, Markdown, etc.),
va acá.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from ikigai import jsonl_store
from ikigai.cuadrantes import VALID_CUADRANTES
from ikigai.models import Item

# Schema canónico de columnas que escribimos/leemos en CSV.
# El JSONL es schema-flexible, pero el CSV necesita header fijo.
CANONICAL_COLUMNS: list[str] = [
    "id", "item", "cuadrante", "categoria", "tipo", "fuente", "prioridad", "notas",
    "tag_amo", "tag_bueno", "tag_mundo", "tag_pago",
    "energia_1a5", "dominio_1a5", "impacto_1a5", "viabilidad_1a5",
]

_REQUIRED_COLUMNS: frozenset[str] = frozenset({"id", "item", "cuadrante"})


class CsvImportError(ValueError):
    """Validación fallida al importar un CSV (formato, columnas, cuadrantes)."""


# ─────────────────────────────────────────────────────────────
# Export: JSONL → CSV
# ─────────────────────────────────────────────────────────────

def export_csv_from_items(items: list[Item]) -> str:
    """Genera CSV (schema canónico) desde items ya leídos. Pure, sin I/O.

    Si la lista está vacía, devuelve solo el header (CSV válido sin filas).
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CANONICAL_COLUMNS)
    writer.writeheader()
    for it in items:
        writer.writerow({col: getattr(it, col, "") for col in CANONICAL_COLUMNS})
    return buf.getvalue()


def build_csv_template_text() -> str:
    """CSV de plantilla con header + 2 filas de ejemplo (un positivo, un negativo).

    Útil cuando alguien quiere exportar un proyecto vacío y necesita el
    schema para llenarlo offline.
    """
    # Import local para evitar ciclos a nivel de módulo.
    from ikigai.cuadrantes import CUADRANTES

    pair = CUADRANTES[0]  # "Pasión" como demo
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CANONICAL_COLUMNS)
    writer.writeheader()
    writer.writerow({
        "id": f"{pair.positivo.csv_value}.001",
        "item": f"Ejemplo (BORRAME): {pair.positivo.placeholder}",
        "cuadrante": pair.positivo.csv_value,
        "fuente": "plantilla",
        "notas": f"Lado + ({pair.positivo.label}) del cuadrante '{pair.titulo}'",
    })
    writer.writerow({
        "id": f"{pair.negativo.csv_value}.001",
        "item": f"Ejemplo (BORRAME): {pair.negativo.placeholder}",
        "cuadrante": pair.negativo.csv_value,
        "fuente": "plantilla",
        "notas": (
            f"Lado - ({pair.negativo.label}) del cuadrante '{pair.titulo}'. "
            f"IDs validos: 1,1b,2,2b,3,3b,4,4b. Borra estos ejemplos y agrega los tuyos."
        ),
    })
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────
# Import: CSV → JSONL
# ─────────────────────────────────────────────────────────────

def parse_and_validate_csv_text(text: str) -> list[dict[str, str]]:
    """Parsea y valida texto CSV. Devuelve los rows como dicts.

    Validación:
      - tiene columnas requeridas (id, item, cuadrante)
      - todos los rows tienen cuadrante ∈ {1,1b,2,2b,3,3b,4,4b}
      - el id sigue la convención '<cuadrante>.<NNN>' (su prefijo == cuadrante)
      - sin ids duplicados, sin ids vacíos
    Lanza CsvImportError en cualquier fallo.
    """
    # Defense in depth: descartar BOM UTF-8 si Excel lo agregó.
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")

    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except csv.Error as e:
        raise CsvImportError(f"CSV malformado: {e}") from e

    if reader.fieldnames is None:
        raise CsvImportError("El archivo está vacío o no tiene header.")

    missing = _REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise CsvImportError(
            f"Faltan columnas obligatorias: {sorted(missing)}. "
            f"Schema esperado: {CANONICAL_COLUMNS}"
        )

    seen_ids: set[str] = set()
    for i, row in enumerate(rows, start=2):  # +2: header en línea 1
        cuad = (row.get("cuadrante") or "").strip()
        if cuad not in VALID_CUADRANTES:
            raise CsvImportError(
                f"Fila {i}: cuadrante '{cuad}' inválido. "
                f"Válidos: {sorted(VALID_CUADRANTES)}"
            )
        item_id = (row.get("id") or "").strip()
        if not item_id:
            raise CsvImportError(f"Fila {i}: 'id' vacío.")
        # M1: el id debe seguir la convención '<cuadrante>.<NNN>'. Si el prefijo
        # no concuerda con el cuadrante, next_id_for_cuadrante (que secuencia
        # por prefijo) generaría colisiones o saltos. Mejor rechazar al importar.
        prefix = item_id.split(".", 1)[0]
        if prefix != cuad:
            raise CsvImportError(
                f"Fila {i}: el id '{item_id}' no concuerda con el cuadrante "
                f"'{cuad}'. Convención: '<cuadrante>.<NNN>' (se esperaba que "
                f"empezara con '{cuad}.', ej. '{cuad}.001')."
            )
        if item_id in seen_ids:
            raise CsvImportError(f"Fila {i}: id '{item_id}' duplicado.")
        seen_ids.add(item_id)

        # Valida el rango de los scores (*_1a5) con la misma regla que el
        # endpoint HTTP. Sin esto, un CSV editado a mano podia meter scores
        # fuera de rango (ej. '9') que el endpoint si rechaza.
        try:
            _csv_row_to_item(row).validate()
        except ValueError as e:
            raise CsvImportError(f"Fila {i}: {e}") from e

    return rows


def import_csv_text(jsonl_path: Path, text: str) -> int:
    """Reemplaza completamente el JSONL con el contenido validado del CSV.

    Escritura atómica (delega en `jsonl_store.write_all`).
    Devuelve el número de items importados.
    """
    rows = parse_and_validate_csv_text(text)
    items = [_csv_row_to_item(row) for row in rows]
    jsonl_store.write_all(jsonl_path, items)
    return len(items)


# ─────────────────────────────────────────────────────────────
# Internals
# ─────────────────────────────────────────────────────────────

def _csv_row_to_item(row: dict[str, str]) -> Item:
    """Construye un Item desde un row del CSV (preserva schema canónico)."""
    return Item(
        id=row.get("id", ""),
        item=row.get("item", ""),
        cuadrante=row.get("cuadrante", ""),
        categoria=row.get("categoria", ""),
        tipo=row.get("tipo", ""),
        fuente=row.get("fuente", ""),
        prioridad=row.get("prioridad", ""),
        notas=row.get("notas", ""),
        tag_amo=row.get("tag_amo", ""),
        tag_bueno=row.get("tag_bueno", ""),
        tag_mundo=row.get("tag_mundo", ""),
        tag_pago=row.get("tag_pago", ""),
        energia_1a5=row.get("energia_1a5", ""),
        dominio_1a5=row.get("dominio_1a5", ""),
        impacto_1a5=row.get("impacto_1a5", ""),
        viabilidad_1a5=row.get("viabilidad_1a5", ""),
    )
