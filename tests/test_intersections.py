"""Tests del modulo de nombres canonicos del Ikigai clasico."""
from __future__ import annotations

from ikigai.intersections import (
    lookup,
    to_json_dict,
)


class TestLookup:
    def test_finds_classic_pasion(self) -> None:
        i = lookup({"1", "2"})
        assert i is not None
        assert i.name == "Pasion"
        assert "amas" in i.tagline.lower()

    def test_finds_classic_mision(self) -> None:
        assert lookup({"1", "3"}).name == "Mision"

    def test_finds_classic_vocacion(self) -> None:
        assert lookup({"3", "4"}).name == "Vocacion"

    def test_finds_classic_profesion(self) -> None:
        assert lookup({"2", "4"}).name == "Profesion"

    def test_finds_ikigai_center(self) -> None:
        i = lookup({"1", "2", "3", "4"})
        assert i.name == "Ikigai"
        assert i.warning == ""  # el centro no tiene warning

    def test_order_independent(self) -> None:
        # Los lookups son por set, no por orden de los csv_values.
        assert lookup({"4", "2"}) == lookup({"2", "4"})
        assert lookup({"3", "1", "4", "2"}) == lookup({"1", "2", "3", "4"})

    def test_returns_none_for_unknown(self) -> None:
        # Combinaciones con primitivos inexistentes no estan en la tabla.
        assert lookup({"1", "5"}) is None
        assert lookup({"5"}) is None
        # Singletons tampoco son intersecciones
        assert lookup({"1"}) is None

    def test_finds_diagonal_hobby_remunerado(self) -> None:
        # 1 ∩ 4 (amas + pagan) es una de las 2 diagonales que el folclore omite.
        i = lookup({"1", "4"})
        assert i is not None and i.name == "Hobby remunerado"

    def test_finds_diagonal_servicio_voluntario(self) -> None:
        # 2 ∩ 3 (haces bien + mundo necesita) es la otra diagonal.
        i = lookup({"2", "3"})
        assert i is not None and i.name == "Servicio voluntario"

    def test_all_three_way_intersections_have_warning(self) -> None:
        # Las 4 intersecciones de 3 circulos son diagnosticas (falta uno).
        three_way = [
            {"2", "3", "4"}, {"1", "3", "4"},
            {"1", "2", "4"}, {"1", "2", "3"},
        ]
        for combo in three_way:
            i = lookup(combo)
            assert i is not None, f"falta naming para {combo}"
            assert i.warning, f"3-way {combo} debe tener warning diagnostico"
            assert "falta" in i.warning.lower()

    def test_all_two_way_intersections_have_warning(self) -> None:
        # Los 6 'diamantes' (4 canonicos + 2 diagonales) tienen warning.
        two_way = [
            {"1", "2"}, {"2", "4"}, {"3", "4"}, {"1", "3"},  # 4 canonicas
            {"1", "4"}, {"2", "3"},                          # 2 diagonales
        ]
        for combo in two_way:
            assert lookup(combo).warning, f"2-way {combo} debe advertir"


class TestToJsonDict:
    def test_keys_are_sorted_comma_strings(self) -> None:
        d = to_json_dict()
        assert "1,2" in d
        assert "1,2,3,4" in d
        # No deberia haber "2,1" (debe ir ordenado)
        for k in d:
            parts = k.split(",")
            assert parts == sorted(parts), f"clave {k!r} no esta ordenada"

    def test_values_are_dicts_with_canonical_fields(self) -> None:
        d = to_json_dict()
        for key, value in d.items():
            assert set(value.keys()) >= {"name", "tagline", "warning"}, key

    def test_covers_all_classic_combinations(self) -> None:
        d = to_json_dict()
        # 4 canonicas (Pasion, Mision, Profesion, Vocacion) +
        # 2 diagonales (Hobby remunerado, Servicio voluntario) +
        # 4 tres-vias (Casi-Ikigai) + 1 centro (Ikigai) = 11.
        assert len(d) == 11
