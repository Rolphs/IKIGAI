"""Tests del puente CSV ↔ JSONL (`ikigai.portability`).

El JSONL es el store canonico; el CSV es solo I/O para humanos (Excel,
correo, edicion offline). Estos tests blindan el puente — sobre todo el
round-trip JSONL→CSV→JSONL con caracteres que tipicamente rompen CSVs
naive (comas, comillas, newlines, emojis).

NOTA: `test_jsonl_store.py` cubre el store en si; aqui solo el bridge.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ikigai import jsonl_store
from ikigai.models import Item
from ikigai.portability import (
    CANONICAL_COLUMNS,
    CsvImportError,
    build_csv_template_text,
    export_csv_from_items,
    import_csv_text,
    parse_and_validate_csv_text,
)

# ─── Export: JSONL → CSV ────────────────────────────────────


class TestExportCsvFromItems:
    """Variante pura que recibe items ya leidos (evita doble lectura
    del store en GET /csv/export)."""

    def test_empty_list_returns_header_only(self) -> None:
        text = export_csv_from_items([])
        non_empty = [line for line in text.splitlines() if line.strip()]
        assert len(non_empty) == 1
        assert non_empty[0].split(",") == CANONICAL_COLUMNS

    def test_writes_canonical_columns_in_order(self) -> None:
        """El header debe coincidir EXACTO con CANONICAL_COLUMNS — Excel
        depende del orden para presentar las columnas predecibles."""
        text = export_csv_from_items([Item(id="1.001", item="x", cuadrante="1")])
        assert text.splitlines()[0].split(",") == CANONICAL_COLUMNS


# ─── Round-trip: el corazon del bridge ───────────────────────────────────


class TestRoundTripCsvKillers:
    """Los caracteres que clasicamente rompen CSVs naive deben sobrevivir
    JSONL → CSV → JSONL sin perdida ni corrupcion."""

    @pytest.mark.parametrize("text", [
        "Item con, comas, y mas, comas",
        'Item con "comillas dobles" en el medio',
        "Item con\nun salto de linea",
        "Item con \"todo\" mezclado, y\nnewline",
        "💪 emoji + acentos: cómo está el ñandú",
        ",,,puro,separador,por,delante",
        '"""triple-quoted al inicio"""',
    ])
    def test_text_survives_round_trip(self, tmp_path: Path, text: str) -> None:
        # Sembrar JSONL con un item peligroso.
        store = tmp_path / "tulipan.jsonl"
        original = Item(id="1.001", item=text, cuadrante="1", notas="bla bla")
        jsonl_store.append(store, original)

        # Export a CSV → import en un JSONL nuevo → comparar.
        csv_text = export_csv_from_items(jsonl_store.read_all(store))
        new_store = tmp_path / "after.jsonl"
        n = import_csv_text(new_store, csv_text)

        assert n == 1
        roundtripped = jsonl_store.read_all(new_store)[0]
        assert roundtripped == original  # frozen dataclass: igualdad estructural

    def test_multiple_items_preserve_order(self, tmp_path: Path) -> None:
        store = tmp_path / "tulipan.jsonl"
        for i in range(1, 4):
            jsonl_store.append(store, Item(id=f"1.00{i}", item=f"item {i}", cuadrante="1"))

        new_store = tmp_path / "after.jsonl"
        import_csv_text(new_store, export_csv_from_items(jsonl_store.read_all(store)))

        ids = [it.id for it in jsonl_store.read_all(new_store)]
        assert ids == ["1.001", "1.002", "1.003"]


# ─── Import: validacion ──────────────────────────────────────────────────


class TestParseAndValidate:
    def test_minimal_valid_csv_parses(self) -> None:
        text = "id,item,cuadrante\n1.001,Hola,1\n"
        rows = parse_and_validate_csv_text(text)
        assert len(rows) == 1
        assert rows[0]["item"] == "Hola"

    def test_strips_utf8_bom(self) -> None:
        """Excel/Numbers a menudo guardan con BOM. No es un error."""
        text = "\ufeffid,item,cuadrante\n1.001,Hola,1\n"
        rows = parse_and_validate_csv_text(text)
        assert rows[0]["id"] == "1.001"

    def test_missing_required_column_raises(self) -> None:
        text = "id,item\n1.001,Sin cuadrante\n"
        with pytest.raises(CsvImportError, match="cuadrante"):
            parse_and_validate_csv_text(text)

    def test_invalid_cuadrante_raises_with_line_number(self) -> None:
        text = "id,item,cuadrante\n1.001,Hola,1\nbad.001,Mal,99\n"
        with pytest.raises(CsvImportError, match="Fila 3"):
            parse_and_validate_csv_text(text)

    @pytest.mark.parametrize("cuad", ["1", "1b", "2", "2b", "3", "3b", "4", "4b"])
    def test_all_8_cuadrantes_accepted(self, cuad: str) -> None:
        text = f"id,item,cuadrante\n{cuad}.001,x,{cuad}\n"
        rows = parse_and_validate_csv_text(text)
        assert rows[0]["cuadrante"] == cuad

    def test_empty_id_raises(self) -> None:
        text = "id,item,cuadrante\n,Hola,1\n"
        with pytest.raises(CsvImportError, match="vac"):
            parse_and_validate_csv_text(text)

    def test_duplicate_ids_raise(self) -> None:
        text = "id,item,cuadrante\n1.001,A,1\n1.001,B,1\n"
        with pytest.raises(CsvImportError, match="duplicado"):
            parse_and_validate_csv_text(text)

    def test_id_prefix_must_match_cuadrante(self) -> None:
        # M1: id '1.001' con cuadrante '3' es incoherente y romperia el
        # secuenciado de next_id_for_cuadrante. Debe rechazarse con la fila.
        text = "id,item,cuadrante\n1.001,Hola,1\n1.002,Mal,3\n"
        with pytest.raises(CsvImportError, match="Fila 3"):
            parse_and_validate_csv_text(text)

    def test_id_without_dot_is_rejected(self) -> None:
        # Un id sin la forma '<cuad>.<NNN>' tampoco cumple la convencion.
        text = "id,item,cuadrante\nfoo,Hola,1\n"
        with pytest.raises(CsvImportError, match="no concuerda"):
            parse_and_validate_csv_text(text)

    def test_shadow_cuadrante_prefix_matches(self) -> None:
        # Los cuadrantes sombra ('1b', etc.) tambien validan por prefijo exacto.
        text = "id,item,cuadrante\n1b.001,Hola,1b\n"
        rows = parse_and_validate_csv_text(text)
        assert rows[0]["id"] == "1b.001"

    def test_shadow_prefix_mismatch_rejected(self) -> None:
        # '1.001' con cuadrante '1b' NO concuerda (prefijo '1' != '1b').
        text = "id,item,cuadrante\n1.001,Hola,1b\n"
        with pytest.raises(CsvImportError, match="no concuerda"):
            parse_and_validate_csv_text(text)

    def test_empty_file_raises(self) -> None:
        with pytest.raises(CsvImportError, match=r"vac|header"):
            parse_and_validate_csv_text("")


# ─── Import: efectos sobre el store ──────────────────────────────────────


class TestImportCsvText:
    def test_replaces_existing_items_completely(self, tmp_path: Path) -> None:
        """Importar es REEMPLAZO, no merge. El historico se descarta."""
        store = tmp_path / "tulipan.jsonl"
        jsonl_store.append(store, Item(id="1.001", item="viejo", cuadrante="1"))

        new_text = "id,item,cuadrante\n3.001,nuevo,3\n"
        n = import_csv_text(store, new_text)

        assert n == 1
        items = jsonl_store.read_all(store)
        assert [it.id for it in items] == ["3.001"]
        assert items[0].item == "nuevo"

    def test_failure_leaves_store_untouched(self, tmp_path: Path) -> None:
        """Si la validacion falla, el JSONL existente NO se toca."""
        store = tmp_path / "tulipan.jsonl"
        jsonl_store.append(store, Item(id="1.001", item="sagrado", cuadrante="1"))
        snapshot = store.read_text(encoding="utf-8")

        with pytest.raises(CsvImportError):
            import_csv_text(store, "id,item,cuadrante\nx,Algo,99\n")

        assert store.read_text(encoding="utf-8") == snapshot


# ─── Plantilla CSV ───────────────────────────────────────────────────────


class TestBuildCsvTemplate:
    def test_template_has_both_polarities(self) -> None:
        """Plantilla didactica: muestra un ejemplo positivo Y uno de sombra,
        para que el usuario vea que la columna `cuadrante` acepta ambas."""
        text = build_csv_template_text()
        # Hay al menos una fila con cuadrante positivo y una con sombra.
        assert ",1," in text
        assert ",1b," in text

    def test_template_is_reimportable(self, tmp_path: Path) -> None:
        """Lo que generamos como plantilla debe pasar nuestra propia validacion."""
        text = build_csv_template_text()
        store = tmp_path / "tulipan.jsonl"
        n = import_csv_text(store, text)
        assert n == 2  # 2 filas de ejemplo
