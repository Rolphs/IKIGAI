"""Tests para ikigai.stats — agregaciones tipo chi-cuadrada sobre Items.

Estos helpers son puros (sin I/O) y la base para todas las
visualizaciones tipo "tabla de contingencia" del proyecto.
"""
from __future__ import annotations

import pytest

from ikigai.models import Item
from ikigai.stats import (
    CIRCLES,
    expected_circle_for_evoking_cuadrante,
    section_fingerprint,
    tag_distribution,
    tag_distribution_pct,
)


def _mk(item_id: str, **tags: str) -> Item:
    """Helper para construir Items rapidos en tests."""
    return Item(id=item_id, item=f"item-{item_id}", **tags)


class TestTagDistribution:
    def test_empty_list_returns_zero_for_each_circle(self) -> None:
        assert tag_distribution([]) == {"1": 0, "2": 0, "3": 0, "4": 0}

    def test_single_taggear_item_counts_once(self) -> None:
        items = [_mk("a", tag_amo="1")]
        assert tag_distribution(items) == {"1": 1, "2": 0, "3": 0, "4": 0}

    def test_multi_tag_item_counts_in_each_circle(self) -> None:
        # Item con 3 tags suma 1 en cada uno (no se "divide entre 3").
        # La pregunta es "a cuales circulos pertenece", no "que tan fuerte".
        items = [_mk("a", tag_amo="1", tag_bueno="1", tag_pago="1")]
        assert tag_distribution(items) == {"1": 1, "2": 1, "3": 0, "4": 1}

    def test_multiple_items_aggregate(self) -> None:
        items = [
            _mk("a", tag_amo="1"),
            _mk("b", tag_amo="1", tag_bueno="1"),
            _mk("c", tag_mundo="1"),
        ]
        assert tag_distribution(items) == {"1": 2, "2": 1, "3": 1, "4": 0}

    def test_untagged_items_ignored(self) -> None:
        # Items sin tags no contribuyen a la distribucion.
        items = [_mk("a"), _mk("b", tag_amo="1"), _mk("c", cuadrante="3")]
        assert tag_distribution(items) == {"1": 1, "2": 0, "3": 0, "4": 0}


class TestTagDistributionPct:
    def test_empty_returns_all_zero_no_nan(self) -> None:
        # Importante: NO debe producir division por cero ni NaN.
        result = tag_distribution_pct([])
        assert result == {"1": 0.0, "2": 0.0, "3": 0.0, "4": 0.0}

    def test_single_tag_is_100pct(self) -> None:
        items = [_mk("a", tag_amo="1")]
        result = tag_distribution_pct(items)
        assert result["1"] == 100.0
        assert result["2"] == result["3"] == result["4"] == 0.0

    def test_multi_tag_normalizes_over_total_assignments(self) -> None:
        # 1 item con 2 tags → cada cinado tiene 50%.
        items = [_mk("a", tag_amo="1", tag_pago="1")]
        result = tag_distribution_pct(items)
        assert result["1"] == 50.0
        assert result["4"] == 50.0

    def test_pcts_sum_to_100_when_any_tags_exist(self) -> None:
        items = [
            _mk("a", tag_amo="1"),
            _mk("b", tag_bueno="1", tag_mundo="1"),
            _mk("c", tag_pago="1"),
        ]
        result = tag_distribution_pct(items)
        assert sum(result.values()) == pytest.approx(100.0)


class TestExpectedCircleForEvokingCuadrante:
    @pytest.mark.parametrize("cuadrante,expected", [
        ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"),
    ])
    def test_positive_cuadrantes_map_to_their_circle(
        self, cuadrante: str, expected: str
    ) -> None:
        assert expected_circle_for_evoking_cuadrante(cuadrante) == expected

    @pytest.mark.parametrize("cuadrante", ["1b", "2b", "3b", "4b"])
    def test_shadow_cuadrantes_have_no_expected_circle(self, cuadrante: str) -> None:
        # Las preguntas de sombra no esperan que el usuario taggee un circulo
        # particular: por definicion son items de complemento.
        assert expected_circle_for_evoking_cuadrante(cuadrante) is None

    @pytest.mark.parametrize("garbage", ["", "zzz", "9", "x1"])
    def test_unknown_inputs_return_none(self, garbage: str) -> None:
        assert expected_circle_for_evoking_cuadrante(garbage) is None


class TestSectionFingerprint:
    def test_empty_section_has_zero_assignments_and_no_divergence(self) -> None:
        fp = section_fingerprint([], "1")
        assert fp["total_assignments"] == 0
        assert fp["tagged_items_count"] == 0
        assert fp["expected_circle"] == "1"
        # Sin items: no hay divergencia, hay AUSENCIA de informacion.
        assert fp["has_divergence"] is False
        assert fp["distribution_pct"] == {c: 0.0 for c in CIRCLES}

    def test_aligned_section_no_divergence(self) -> None:
        # Pregunta de Amo (cuadrante=1) e items tagueados como Amo → alineado.
        items = [_mk("a", tag_amo="1"), _mk("b", tag_amo="1", tag_bueno="1")]
        fp = section_fingerprint(items, "1")
        assert fp["expected_circle"] == "1"
        assert fp["distribution_count"]["1"] == 2
        assert fp["has_divergence"] is False
        assert fp["tagged_items_count"] == 2

    def test_divergent_section_flags_when_expected_circle_unused(self) -> None:
        # Pregunta de Amo (esperado=1) pero NINGUN item taguea Amo →
        # divergencia explicita. Esto es la señal chi² fuerte.
        items = [_mk("a", tag_pago="1"), _mk("b", tag_bueno="1")]
        fp = section_fingerprint(items, "1")
        assert fp["expected_circle"] == "1"
        assert fp["distribution_count"]["1"] == 0
        assert fp["distribution_count"]["2"] == 1
        assert fp["distribution_count"]["4"] == 1
        assert fp["has_divergence"] is True

    def test_shadow_section_never_diverges(self) -> None:
        # Preguntas de sombra no tienen expected_circle, asi que tampoco
        # tienen has_divergence (no hay baseline contra que comparar).
        items = [_mk("a", tag_amo="1"), _mk("b")]
        fp = section_fingerprint(items, "1b")
        assert fp["expected_circle"] is None
        assert fp["has_divergence"] is False

    def test_partial_alignment_still_no_divergence(self) -> None:
        # Si AL MENOS UN item taguea el circulo esperado, no marcamos
        # divergencia: la señal exige ausencia total.
        items = [_mk("a", tag_amo="1"), _mk("b", tag_pago="1")]
        fp = section_fingerprint(items, "1")
        assert fp["distribution_count"]["1"] == 1
        assert fp["has_divergence"] is False
