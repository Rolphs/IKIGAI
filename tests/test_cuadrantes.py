"""Tests de cuadrantes.py: la fuente de verdad de los primitivos del modelo.

Cubre D1 (anti-duplicacion): all_csv_values() / VALID_CUADRANTES son el
unico lugar que enumera cuadrantes validos. Otros modulos NO deben hardcodear
'1234'; deben re-exportar/usar estos.
"""
from __future__ import annotations

from ikigai import cuadrantes, jsonl_store, portability


def test_all_csv_values_order_and_content() -> None:
    # Orden esperado: (positivo, negativo) por cada par, en orden de CUADRANTES.
    assert cuadrantes.all_csv_values() == [
        "1", "1b", "2", "2b", "3", "3b", "4", "4b",
    ]


def test_valid_cuadrantes_matches_all_csv_values() -> None:
    assert frozenset(cuadrantes.all_csv_values()) == cuadrantes.VALID_CUADRANTES


def test_positive_csv_values_order_and_content() -> None:
    assert cuadrantes.positive_csv_values() == ["1", "2", "3", "4"]


def test_positive_csv_values_is_derived_subset_of_all() -> None:
    # D1: los positivos son la fuente de verdad para "los 4 circulos clasicos".
    # Deben ser EXACTAMENTE los positivos de cada par, sin sombras (no 'Nb').
    expected = [pair.positivo.csv_value for pair in cuadrantes.CUADRANTES]
    assert cuadrantes.positive_csv_values() == expected
    assert set(cuadrantes.positive_csv_values()) <= set(cuadrantes.all_csv_values())
    assert all(not cv.endswith("b") for cv in cuadrantes.positive_csv_values())


def test_valid_cuadrantes_is_derived_from_pairs() -> None:
    # Si alguien agrega/quita un primitivo en CUADRANTES, el set se mueve solo.
    expected = set()
    for pair in cuadrantes.CUADRANTES:
        expected.add(pair.positivo.csv_value)
        expected.add(pair.negativo.csv_value)
    assert expected == cuadrantes.VALID_CUADRANTES


def test_every_valid_cuadrante_resolves_with_find_side() -> None:
    # Coherencia: todo csv_value "valido" debe ser resoluble por find_side,
    # y nada fuera del set debe resolver.
    for cv in cuadrantes.VALID_CUADRANTES:
        assert cuadrantes.find_side(cv) is not None
    assert cuadrantes.find_side("99") is None
    assert cuadrantes.find_side("") is None


def test_consumers_use_the_canonical_set() -> None:
    # D1: jsonl_store y portability deben referenciar EL MISMO objeto canonico,
    # no una copia hardcodeada que pueda driftear.
    assert jsonl_store.VALID_CUADRANTES is cuadrantes.VALID_CUADRANTES
    assert portability.VALID_CUADRANTES is cuadrantes.VALID_CUADRANTES
