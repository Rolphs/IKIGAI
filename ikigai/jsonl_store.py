"""
jsonl_store.py — Persistencia de items en formato JSONL (NDJSON).

Cada línea del archivo es un objeto JSON completo correspondiente a un Item.
Vendría a ser el equivalente del CSV pero sin escape hell (comas, comillas,
saltos de línea, encoding) y con tipos reales en lugar de "todo es string".

Decisiones:
- update/delete: escritura atómica (tmp + os.replace via atomic_io) porque
  reescriben el archivo completo.
- append: append-only (open("a")) por eficiencia O(1). Un append NO es atómico
  ante un crash a mitad de línea, pero el daño está acotado (B3):
    * read_all es RESILIENTE: salta líneas ilegibles con un warning en vez de
      tumbar todo el store.
    * append se AUTO-PROTEGE: si el archivo no termina en '\n' (línea torn por
      un crash previo), inserta el separador antes de escribir, para que el
      item nuevo no se fusione con la línea rota.
    * el próximo update/delete reescribe desde read_all, purgando la línea
      rota — o sea el store se auto-sana en la siguiente edición.
- Omitimos campos vacíos al escribir para mantener el archivo legible.
  Al leer, los defaults del dataclass Item rellenan lo que falte.
- Encoding: UTF-8 SIEMPRE, sin BOM. JSON lo exige por contrato.
- Un mismo `id` solo aparece una vez (lo verificamos en update/delete).

API pública (drop-in mental para csv_writer, pero más simple):
- read_all(path) -> list[Item]
- append(path, item) -> Item
- update(path, item_id, **fields) -> Item | None
- delete(path, item_id) -> bool
- get(path, item_id) -> Item | None
- next_id_for_cuadrante(path, cuadrante) -> str
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

from ikigai import atomic_io
from ikigai.cuadrantes import VALID_CUADRANTES
from ikigai.locks import keyed_lock
from ikigai.models import Item

logger = logging.getLogger(__name__)

# Concurrencia: las mutaciones del store son read-modify-write (o append con
# chequeo de unicidad). FastAPI atiende requests en un thread pool, asi que dos
# requests al MISMO archivo pueden pisarse (IDs duplicados, escrituras perdidas).
# Serializamos por-path con keyed_lock (mismo patron que viz_storage). IMPORTANTE:
# threading.Lock NO es reentrante, asi que SOLO los entrypoints publicos toman el
# lock; los helpers internos (write_all, _append_line) quedan SIN lock para no
# anidar. Si llamas write_all directo desde fuera (p.ej. import CSV), tomalo vos.

# ─────────────────────────────────────────────────────────────
# Serialización
# ─────────────────────────────────────────────────────────────

def _item_to_json_obj(item: Item) -> dict[str, Any]:
    """Convierte Item → dict serializable, omitiendo campos vacíos.

    El JSONL queda compacto y legible. Al re-leer, los defaults del
    dataclass rellenan lo ausente, así que no hay pérdida semántica.
    """
    raw = asdict(item)
    # id e item son obligatorios siempre, aunque el item sea string vacío
    # (caso edge: querer guardar un item con texto vacío como placeholder).
    return {k: v for k, v in raw.items() if v != "" or k in ("id", "item")}


def _json_obj_to_item(obj: dict[str, Any]) -> Item:
    """Construye un Item desde un dict (típicamente venido de json.loads).

    Defensivo: ignora campos extra del JSON que no existen en el dataclass
    (forward-compat). Castea todo a str para mantener el contrato del Item.
    """
    valid_field_names = {f.name for f in fields(Item)}
    clean: dict[str, Any] = {}
    for key, value in obj.items():
        if key not in valid_field_names:
            continue
        # Item es 100% string fields hoy. Si el JSON trae int/bool/None,
        # lo normalizamos a str para no romper el contrato.
        clean[key] = "" if value is None else str(value)
    return Item(**clean)


# ─────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────

def _iter_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Itera (número_de_línea, contenido) de líneas no vacías.

    Tolera líneas en blanco y trailing newlines. El número de línea (1-based)
    permite reportar con precisión una línea corrupta en read_all.
    """
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            stripped = line.strip()
            if stripped:
                yield lineno, stripped


def read_all(path: Path) -> list[Item]:
    """Lee todos los items del archivo JSONL. Devuelve lista vacía si no existe.

    RESILIENTE (B3): si una línea no es JSON parseable o no es un objeto
    (típicamente la última, truncada por un crash a mitad de append), la salta
    con un warning en vez de tumbar TODO el store. Perder una línea es mucho
    mejor que dejar el archivo entero ilegible.
    """
    items: list[Item] = []
    for lineno, line in _iter_lines(path):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning(
                "jsonl_store: línea %d de %s ilegible, se omite (%s): %.80r",
                lineno, path, exc, line,
            )
            continue
        if not isinstance(obj, dict):
            logger.warning(
                "jsonl_store: línea %d de %s no es un objeto JSON, se omite: %.80r",
                lineno, path, line,
            )
            continue
        items.append(_json_obj_to_item(obj))
    return items


def get(path: Path, item_id: str) -> Item | None:
    """Devuelve el item con `id == item_id` o None si no existe.

    O(n) — para datasets de miles preferimos read_all + indexar en el caller.
    """
    for item in read_all(path):
        if item.id == item_id:
            return item
    return None


# ─────────────────────────────────────────────────────────────
# Escritura (atómica: tmp + replace)
# ─────────────────────────────────────────────────────────────

def write_all(path: Path, items: list[Item]) -> None:
    """Reescribe el archivo completo de forma atómica (reemplazo total).

    API pública de "replace all": usado por update/delete y por el import CSV
    de portability. Para append puro usar `append` (no relee todo).
    """
    lines = [
        json.dumps(_item_to_json_obj(item), ensure_ascii=False) + "\n"
        for item in items
    ]
    atomic_io.atomic_write_text(path, "".join(lines))


def _ends_with_newline(path: Path) -> bool:
    """True si el archivo termina en '\\n' (o si está vacío).

    Lo usa append para decidir si hace falta un separador antes de la nueva
    línea: si un crash dejó una línea truncada SIN newline final, escribir
    encima fusionaría el item nuevo con la línea rota (perdiendo ambos).
    """
    size = path.stat().st_size
    if size == 0:
        return True  # vacío: no hace falta separador
    with path.open("rb") as f:
        f.seek(-1, 2)  # último byte
        return f.read(1) == b"\n"


def _append_line(path: Path, item: Item) -> None:
    """Append O(1) — solo escribe una línea al final, sin releer.

    Auto-protección (B3): si el archivo existe y no termina en '\\n', inserta
    el separador primero para no fusionarse con una línea torn por un crash.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = path.exists() and not _ends_with_newline(path)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        if needs_separator:
            f.write("\n")
        f.write(json.dumps(_item_to_json_obj(item), ensure_ascii=False))
        f.write("\n")


def append(path: Path, item: Item) -> Item:
    """Agrega un item al final del JSONL. Devuelve el item agregado.

    Rechaza ids duplicados — la unicidad es invariante del store.
    """
    with keyed_lock(str(path)):
        if get(path, item.id) is not None:
            raise ValueError(f"id duplicado: '{item.id}' ya existe en {path}")
        _append_line(path, item)
    return item


def update(path: Path, item_id: str, **changed_fields: str) -> Item | None:
    """Actualiza campos de un item existente. Devuelve el item nuevo o None.

    Si el id no existe, devuelve None sin tocar el archivo.
    Si no hay cambios reales, igual reescribe (simple > clever).
    """
    with keyed_lock(str(path)):
        items = read_all(path)
        new_items: list[Item] = []
        updated: Item | None = None
        for it in items:
            if it.id == item_id and updated is None:
                updated = replace(it, **changed_fields)
                new_items.append(updated)
            else:
                new_items.append(it)
        if updated is None:
            return None
        write_all(path, new_items)
    return updated


def delete(path: Path, item_id: str) -> bool:
    """Elimina el item con `id == item_id`. Devuelve True si borró algo."""
    with keyed_lock(str(path)):
        items = read_all(path)
        new_items = [it for it in items if it.id != item_id]
        if len(new_items) == len(items):
            return False
        write_all(path, new_items)
    return True


# ─────────────────────────────────────────────────────────────
# Generación de IDs (compatibilidad con la lógica del csv_writer viejo)
# ─────────────────────────────────────────────────────────────

def _next_id_from_items(items: list[Item], cuadrante_value: str) -> str:
    """Pure: calcula el siguiente id para un cuadrante dada una lista ya leída.

    Separado de next_id_for_cuadrante para poder reusarlo sin re-leer el store
    (ver add_with_generated_id, que hace next_id + append en UNA lectura).
    """
    pattern = re.compile(rf"^{re.escape(cuadrante_value)}\.(\d+)$")
    max_seq = 0
    for item in items:
        m = pattern.match(item.id)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return f"{cuadrante_value}.{max_seq + 1:03d}"


def next_id_for_cuadrante(path: Path, cuadrante_value: str) -> str:
    """Devuelve el siguiente ID disponible para un cuadrante.

    Convención: '<cuadrante>.<NNN>' donde NNN es zero-padded a 3 dígitos
    y crece monotónicamente. Igual que csv_writer.next_id_for_cuadrante.
    """
    if cuadrante_value not in VALID_CUADRANTES:
        raise ValueError(
            f"cuadrante inválido '{cuadrante_value}'. "
            f"Válidos: {sorted(VALID_CUADRANTES)}"
        )
    return _next_id_from_items(read_all(path), cuadrante_value)


def add_with_generated_id(path: Path, cuadrante_value: str, **fields: str) -> Item:
    """Crea un item con id autogenerado y lo agrega, en UNA sola lectura.

    D4: antes el caller hacía next_id_for_cuadrante (read_all) + append (que
    re-leía para chequear duplicados) = 2 lecturas completas por item, O(n²)
    al cargar muchos. Aquí leemos una vez: el id generado es fresco por
    construcción (max_seq + 1), así que no hay que re-chequear unicidad.
    """
    if cuadrante_value not in VALID_CUADRANTES:
        raise ValueError(
            f"cuadrante inválido '{cuadrante_value}'. "
            f"Válidos: {sorted(VALID_CUADRANTES)}"
        )
    with keyed_lock(str(path)):
        items = read_all(path)
        new_id = _next_id_from_items(items, cuadrante_value)
        item = Item(id=new_id, cuadrante=cuadrante_value, **fields)
        _append_line(path, item)
    return item
