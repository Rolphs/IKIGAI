"""Tests para los helpers semanticos del lente chi²:
- Item.evoking_circle / evoking_polarity / assigned_circles / is_aligned_with_evocation
- item_queries.items_by_tag (lo OBSERVADO vs lo EVOCADO)

Estos tests existen para hacer explicita la separacion entre 'la pregunta
que evoco el item' (esperado) y 'los circulos a los que el usuario lo
asigno' (observado). Esa separacion antes vivia implicita en el codigo
y producia un bug latente en el visualizador (mostraba lo evocado en
lugar de lo asignado).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ikigai import jsonl_store
from ikigai.item_queries import items_by_evoking_cuadrante, items_by_tag
from ikigai.models import Item

# ─── Item helpers (sin I/O) ──────────────────────────────────────────────


class TestItemEvocationHelpers:
    def test_evoking_circle_strips_polarity(self) -> None:
        assert Item(id="1.1", item="x", cuadrante="1").evoking_circle == "1"
        assert Item(id="1b.1", item="x", cuadrante="1b").evoking_circle == "1"
        assert Item(id="4b.1", item="x", cuadrante="4b").evoking_circle == "4"

    def test_evoking_polarity(self) -> None:
        assert Item(id="x", item="x", cuadrante="1").evoking_polarity == "+"
        assert Item(id="x", item="x", cuadrante="3").evoking_polarity == "+"
        assert Item(id="x", item="x", cuadrante="1b").evoking_polarity == "-"
        assert Item(id="x", item="x", cuadrante="").evoking_polarity == ""

    def test_evoking_cuadrante_alias_returns_raw_value(self) -> None:
        it = Item(id="x", item="x", cuadrante="2b")
        assert it.evoking_cuadrante == "2b"
        assert it.evoking_cuadrante == it.cuadrante


class TestAssignedCircles:
    def test_no_tags_returns_empty(self) -> None:
        it = Item(id="x", item="x")
        assert it.assigned_circles() == frozenset()

    def test_single_tag(self) -> None:
        it = Item(id="x", item="x", tag_amo="1")
        assert it.assigned_circles() == frozenset({"1"})

    def test_multiple_tags(self) -> None:
        it = Item(id="x", item="x", tag_amo="1", tag_mundo="1", tag_pago="1")
        assert it.assigned_circles() == frozenset({"1", "3", "4"})

    @pytest.mark.parametrize("truthy", ["1", "true", "on", "yes", "si", "sí", "TRUE", "Yes"])
    def test_accepts_various_truthy_values(self, truthy: str) -> None:
        it = Item(id="x", item="x", tag_bueno=truthy)
        assert "2" in it.assigned_circles()

    @pytest.mark.parametrize("falsy", ["", "0", "false", "no", "off", "   "])
    def test_rejects_falsy_values(self, falsy: str) -> None:
        it = Item(id="x", item="x", tag_bueno=falsy)
        assert "2" not in it.assigned_circles()


class TestAlignmentWithEvocation:
    def test_aligned_when_positive_evocation_matches_tag(self) -> None:
        it = Item(id="x", item="x", cuadrante="1", tag_amo="1")
        assert it.is_aligned_with_evocation is True

    def test_not_aligned_when_tag_differs_from_evocation(self) -> None:
        it = Item(id="x", item="x", cuadrante="1", tag_pago="1")
        assert it.is_aligned_with_evocation is False

    def test_negative_evocation_never_aligned(self) -> None:
        it = Item(id="x", item="x", cuadrante="1b", tag_amo="1")
        assert it.is_aligned_with_evocation is False

    def test_no_tags_not_aligned(self) -> None:
        it = Item(id="x", item="x", cuadrante="1")
        assert it.is_aligned_with_evocation is False


# ─── items_by_tag (con I/O) ──────────────────────────────────────────────


def _seed_jsonl(tmp_path: Path, items: list[Item]) -> Path:
    """Helper: crea un tulipan.jsonl con los items dados y devuelve el path."""
    p = tmp_path / "tulipan.jsonl"
    for it in items:
        jsonl_store.append(p, it)
    return p


def _read(path: Path) -> list[Item]:
    return jsonl_store.read_all(path)


class TestItemsByTag:
    def test_filters_by_tag_amo_for_circle_1(self, tmp_path: Path) -> None:
        path = _seed_jsonl(tmp_path, [
            Item(id="1.001", item="Si tageado", cuadrante="1", tag_amo="1"),
            Item(id="1.002", item="No tageado", cuadrante="1"),
            Item(id="3.001", item="Otro circulo", cuadrante="3", tag_mundo="1"),
        ])
        ids = sorted(i.id for i in items_by_tag(_read(path), "1"))
        assert ids == ["1.001"]

    def test_picks_up_items_tagged_across_evoking_questions(self, tmp_path: Path) -> None:
        path = _seed_jsonl(tmp_path, [
            Item(id="4.001", item="Cruzado", cuadrante="4",
                 tag_amo="1", tag_pago="1"),
        ])
        ids = sorted(i.id for i in items_by_tag(_read(path), "1"))
        assert ids == ["4.001"]

    def test_circle_2_uses_tag_bueno(self, tmp_path: Path) -> None:
        path = _seed_jsonl(tmp_path, [
            Item(id="2.001", item="Bueno solo", cuadrante="2", tag_bueno="1"),
            Item(id="1.001", item="Amo solo", cuadrante="1", tag_amo="1"),
        ])
        ids = sorted(i.id for i in items_by_tag(_read(path), "2"))
        assert ids == ["2.001"]

    def test_negative_csv_value_falls_back_to_evoking_cuadrante(self, tmp_path: Path) -> None:
        path = _seed_jsonl(tmp_path, [
            Item(id="1b.001", item="Sombra Amo", cuadrante="1b"),
            Item(id="2b.001", item="Sombra Bueno", cuadrante="2b"),
        ])
        items = _read(path)
        assert sorted(i.id for i in items_by_tag(items, "1b")) == ["1b.001"]
        assert sorted(i.id for i in items_by_tag(items, "2b")) == ["2b.001"]

    def test_unknown_csv_value_returns_empty(self, tmp_path: Path) -> None:
        path = _seed_jsonl(tmp_path, [
            Item(id="1.001", item="X", cuadrante="1", tag_amo="1"),
        ])
        assert items_by_tag(_read(path), "zzz") == []


class TestEvokingVsTaggingDivergence:
    """Verifica explicitamente la separacion esperado/observado (chi²)."""

    def test_evoking_groups_by_question_tagging_groups_by_circle(
        self, tmp_path: Path
    ) -> None:
        # 3 items evocados por distintas preguntas, todos tageados Amo.
        path = _seed_jsonl(tmp_path, [
            Item(id="1.001", item="Item de Amo", cuadrante="1",
                 tag_amo="1"),
            Item(id="2.001", item="Item de Bueno tageado Amo", cuadrante="2",
                 tag_amo="1"),
            Item(id="4.001", item="Item de Pago tageado Amo", cuadrante="4",
                 tag_amo="1"),
        ])
        items = _read(path)
        # ESPERADO: agrupados por pregunta evocadora → 1 en cada caja.
        assert [i.id for i in items_by_evoking_cuadrante(items, "1")] == ["1.001"]
        # OBSERVADO: agrupados por circulo asignado → los 3 en Amo.
        assert sorted(i.id for i in items_by_tag(items, "1")) == ["1.001", "2.001", "4.001"]
