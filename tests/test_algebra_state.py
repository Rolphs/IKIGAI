"""
Tests del modulo `algebra_state` — la carga compartida del store.

Este modulo es consumido tanto por el router /sintesis como por export.py.
Si rompe aqui, rompe en los dos. Por eso tests propios + tests de los
consumidores son complementarios.
"""
from __future__ import annotations

from pathlib import Path

from ikigai import jsonl_store
from ikigai.algebra_state import AlgebraState, load_algebra_state
from ikigai.models import Item


def _write_items(project_dir: Path, *rows: tuple[str, str, str]) -> Path:
    """Helper: escribe items directamente al JSONL. Cada row = (id, texto, tag).

    El tag es csv_value ('1'..'4' = positivos, '1b'..'4b' = sombras).
    Los positivos usan tag_amo/tag_bueno/tag_mundo/tag_pago para que
    items_by_tag los recoja. Los negativos solo usan cuadrante.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    items = [
        Item(
            id=item_id,
            item=text,
            cuadrante=tag,
            tag_amo="1" if tag == "1" else "",
            tag_bueno="1" if tag == "2" else "",
            tag_mundo="1" if tag == "3" else "",
            tag_pago="1" if tag == "4" else "",
        )
        for item_id, text, tag in rows
    ]
    jsonl_path = project_dir / "tulipan.jsonl"
    jsonl_store.write_all(jsonl_path, items)
    return jsonl_path


class TestLoadAlgebraState:
    """Cobertura directa del modulo. Los tests del router y export son
    indirectos; estos prueban el contrato publico de AlgebraState."""

    def test_returns_namedtuple_with_4_fields(self, tmp_path: Path) -> None:
        path = _write_items(tmp_path, ("1.001", "x", "1"))
        state = load_algebra_state(path)
        assert isinstance(state, AlgebraState)
        # Unpackable como tupla (asi lo usan los consumidores existentes).
        items_by_cuad, _primitive_sets, _items_by_id, universe = state
        assert items_by_cuad is state.items_by_cuad
        assert universe is state.universe

    def test_universe_is_union_of_all_primitive_sets(self, tmp_path: Path) -> None:
        path = _write_items(
            tmp_path,
            ("1.001", "amo", "1"),
            ("2.001", "bueno", "2"),
            ("3.001", "mundo", "3"),
            ("4.001", "pago", "4"),
        )
        state = load_algebra_state(path)
        assert state.universe == frozenset({"1.001", "2.001", "3.001", "4.001"})

    def test_primitive_sets_keyed_by_csv_value(self, tmp_path: Path) -> None:
        path = _write_items(tmp_path, ("1.001", "x", "1"), ("2.001", "y", "2"))
        state = load_algebra_state(path)
        assert state.primitive_sets["1"] == frozenset({"1.001"})
        assert state.primitive_sets["2"] == frozenset({"2.001"})
        # Cuadrantes vacios deben aparecer con frozenset vacio (no ausentes).
        assert state.primitive_sets["3"] == frozenset()
        assert state.primitive_sets["4"] == frozenset()

    def test_includes_all_8_cuadrantes_even_when_empty(self, tmp_path: Path) -> None:
        """Aunque el store este vacio, los 8 csv_values deben ser keys validas.
        Esto importa para callers que iteran sobre todos los cuadrantes
        sin tener que defenderse contra KeyError."""
        path = _write_items(tmp_path)  # JSONL vacio
        state = load_algebra_state(path)
        expected_keys = {"1", "1b", "2", "2b", "3", "3b", "4", "4b"}
        assert set(state.primitive_sets.keys()) == expected_keys
        assert set(state.items_by_cuad.keys()) == expected_keys

    def test_items_by_id_indexes_all_items(self, tmp_path: Path) -> None:
        path = _write_items(tmp_path, ("1.001", "amo", "1"), ("2.001", "bueno", "2"))
        state = load_algebra_state(path)
        assert len(state.items_by_id) == 2
        assert state.items_by_id["1.001"].item == "amo"
        assert state.items_by_id["2.001"].item == "bueno"
