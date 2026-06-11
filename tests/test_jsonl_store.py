"""Tests del jsonl_store.

Cubre:
  1. Round-trip básico (append → read_all)
  2. Update / delete / get
  3. Generación de IDs por cuadrante
  4. Casos que matan al CSV: comas, comillas, saltos de línea, unicode
  5. Idempotencia y atomicidad de escritura
  6. Errores claros (id duplicado, cuadrante inválido)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ikigai import jsonl_store as js
from ikigai.models import Item

# ─── Round-trip básico ──────────────────────────────────────────────


class TestReadAll:
    def test_returns_empty_list_when_file_missing(self, tmp_path: Path) -> None:
        assert js.read_all(tmp_path / "no_existe.jsonl") == []

    def test_round_trip_preserves_fields(self, tmp_path: Path) -> None:
        path = tmp_path / "items.jsonl"
        original = Item(
            id="1.001", item="Diseñar productos bellos",
            cuadrante="1", tag_amo="1", notas="con énfasis ácido",
        )
        js.append(path, original)
        loaded = js.read_all(path)
        assert loaded == [original]

    def test_multiple_appends_preserve_order(self, tmp_path: Path) -> None:
        path = tmp_path / "items.jsonl"
        js.append(path, Item(id="1.001", item="primero"))
        js.append(path, Item(id="2.001", item="segundo"))
        js.append(path, Item(id="3.001", item="tercero"))
        loaded = js.read_all(path)
        assert [it.id for it in loaded] == ["1.001", "2.001", "3.001"]

    def test_ignores_blank_lines(self, tmp_path: Path) -> None:
        # Si alguien edita el archivo a mano y deja líneas en blanco,
        # no debe explotar el reader.
        path = tmp_path / "items.jsonl"
        path.write_text(
            '{"id": "1.001", "item": "uno"}\n'
            '\n'
            '   \n'
            '{"id": "2.001", "item": "dos"}\n',
            encoding="utf-8",
        )
        assert [it.id for it in js.read_all(path)] == ["1.001", "2.001"]


# ─── Get / Update / Delete ──────────────────────────────────────────


class TestGet:
    def test_returns_item_by_id(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        assert js.get(path, "x") == Item(id="x", item="hola")

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        assert js.get(path, "no_existe") is None


class TestUpdate:
    def test_updates_field_in_place(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="texto viejo", cuadrante="1"))
        updated = js.update(path, "x", item="texto nuevo")
        assert updated is not None
        assert updated.item == "texto nuevo"
        # Persistió
        assert js.get(path, "x").item == "texto nuevo"
        # Otros campos siguen intactos
        assert js.get(path, "x").cuadrante == "1"

    def test_returns_none_when_id_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        assert js.update(path, "no_existe", item="nada") is None
        # El archivo no se tocó (el otro item sigue ahí)
        assert js.get(path, "x").item == "hola"

    def test_updates_only_first_match_idempotent(self, tmp_path: Path) -> None:
        # Aunque la API rechaza duplicados en append, defensivamente verificamos
        # que update afecta solo al primero si por alguna razón los hubiera.
        path = tmp_path / "i.jsonl"
        path.write_text(
            '{"id": "x", "item": "a"}\n'
            '{"id": "x", "item": "b"}\n',
            encoding="utf-8",
        )
        js.update(path, "x", item="z")
        items = js.read_all(path)
        assert items[0].item == "z"
        assert items[1].item == "b"


class TestDelete:
    def test_deletes_existing_item(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        js.append(path, Item(id="y", item="adios"))
        assert js.delete(path, "x") is True
        assert [it.id for it in js.read_all(path)] == ["y"]

    def test_returns_false_when_id_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        assert js.delete(path, "no_existe") is False
        assert [it.id for it in js.read_all(path)] == ["x"]


# ─── Append: validación ─────────────────────────────────────────────


class TestAppendValidation:
    def test_rejects_duplicate_id(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="primero"))
        with pytest.raises(ValueError, match="duplicado"):
            js.append(path, Item(id="x", item="segundo"))

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        assert path.exists()


# ─── add_with_generated_id: id + append en una lectura (D4) ──────────


class TestAddWithGeneratedId:
    def test_generates_first_id_and_appends(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        it = js.add_with_generated_id(path, "1", item="hola")
        assert it.id == "1.001"
        assert it.cuadrante == "1"
        assert it.item == "hola"
        assert [x.id for x in js.read_all(path)] == ["1.001"]

    def test_increments_across_calls(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        a = js.add_with_generated_id(path, "1", item="a")
        b = js.add_with_generated_id(path, "1", item="b")
        assert [a.id, b.id] == ["1.001", "1.002"]
        assert [x.id for x in js.read_all(path)] == ["1.001", "1.002"]

    def test_independent_sequences_per_cuadrante(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.add_with_generated_id(path, "1", item="a")
        b = js.add_with_generated_id(path, "2", item="b")
        assert b.id == "2.001"

    def test_passes_extra_fields_to_item(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        it = js.add_with_generated_id(
            path, "1", item="hola", tag_amo="1", notas="con nota"
        )
        assert it.tag_amo == "1"
        assert it.notas == "con nota"
        assert js.get(path, it.id).notas == "con nota"

    def test_rejects_invalid_cuadrante(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        with pytest.raises(ValueError, match="cuadrante inválido"):
            js.add_with_generated_id(path, "9", item="x")


# ─── Casos que matan al CSV (¡el motivo de existir!) ────────────────


class TestCsvKillers:
    """Estos casos hacen llorar al CSV. JSONL los maneja sin parpadear."""

    def test_item_text_with_commas(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        texto = "Diseñar, prototipar, validar, iterar"
        js.append(path, Item(id="x", item=texto))
        assert js.get(path, "x").item == texto

    def test_item_text_with_double_quotes(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        texto = 'Sentir que soy "el experto" sin pretenderlo'
        js.append(path, Item(id="x", item=texto))
        assert js.get(path, "x").item == texto

    def test_item_text_with_newlines(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        texto = "Línea 1\nLínea 2\nLínea 3"
        js.append(path, Item(id="x", item=texto))
        assert js.get(path, "x").item == texto

    def test_unicode_emojis_and_accents(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        texto = "Innovación de Diseño 🌷 ❤️ — ñoño"
        js.append(path, Item(id="x", item=texto))
        # Round-trip exacto, byte por byte, sin mojibake.
        assert js.get(path, "x").item == texto

    def test_notas_with_mixed_payload(self, tmp_path: Path) -> None:
        # Combinación letal para CSV: comillas, comas, newlines, tabs, unicode.
        path = tmp_path / "i.jsonl"
        notas = 'Tabla:\t"col1","col2"\nFila:\t"a,b","c"\n— fin —'
        js.append(path, Item(id="x", item="t", notas=notas))
        assert js.get(path, "x").notas == notas


# ─── Atomicidad ──────────────────────────────────────────────────────


class TestAtomicity:
    def test_no_tmp_file_left_behind_after_update(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        js.update(path, "x", item="adios")
        tmp = path.with_suffix(path.suffix + ".tmp")
        assert not tmp.exists()

    def test_no_tmp_file_left_behind_after_delete(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        js.append(path, Item(id="y", item="adios"))
        js.delete(path, "x")
        tmp = path.with_suffix(path.suffix + ".tmp")
        assert not tmp.exists()


# ─── Empty-field omission (JSONL legible) ───────────────────────────


class TestEmptyFieldOmission:
    def test_written_json_omits_empty_strings(self, tmp_path: Path) -> None:
        # Un item con solo id+item no debe escribir 14 campos vacíos
        # — eso hace el JSONL ilegible y pierde la ventaja de inspección.
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="solo lo esencial"))
        raw = path.read_text(encoding="utf-8")
        # Solo deberían aparecer las claves "id" e "item".
        assert '"id"' in raw and '"item"' in raw
        assert '"cuadrante"' not in raw  # default "" omitido
        assert '"tag_amo"' not in raw

    def test_round_trip_restores_default_empty_strings(self, tmp_path: Path) -> None:
        # Aunque el JSON no tenga las claves, al leer el Item las rellena
        # con el default "" del dataclass.
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="x", item="hola"))
        loaded = js.get(path, "x")
        assert loaded.cuadrante == ""
        assert loaded.tag_amo == ""


# ─── ID generation ──────────────────────────────────────────────────


class TestNextIdForCuadrante:
    def test_first_id_for_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        assert js.next_id_for_cuadrante(path, "1") == "1.001"

    def test_increments_past_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="1.001", item="a"))
        js.append(path, Item(id="1.002", item="b"))
        js.append(path, Item(id="1.005", item="c"))  # gap intencional
        assert js.next_id_for_cuadrante(path, "1") == "1.006"

    def test_independent_sequences_per_cuadrante(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="1.001", item="a"))
        js.append(path, Item(id="2.001", item="b"))
        js.append(path, Item(id="2.002", item="c"))
        assert js.next_id_for_cuadrante(path, "1") == "1.002"
        assert js.next_id_for_cuadrante(path, "2") == "2.003"
        assert js.next_id_for_cuadrante(path, "1b") == "1b.001"

    def test_shadow_cuadrantes_supported(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="3b.001", item="sombra"))
        assert js.next_id_for_cuadrante(path, "3b") == "3b.002"

    def test_rejects_invalid_cuadrante(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        with pytest.raises(ValueError, match="cuadrante inválido"):
            js.next_id_for_cuadrante(path, "X")
        with pytest.raises(ValueError, match="cuadrante inválido"):
            js.next_id_for_cuadrante(path, "5")


# ─── Forward-compat: campos extra del JSON se ignoran ───────────────


class TestForwardCompat:
    def test_unknown_json_fields_ignored_on_read(self, tmp_path: Path) -> None:
        # Si el JSONL trae un campo `future_field` que el dataclass no conoce,
        # el reader debe ignorarlo en vez de explotar.
        path = tmp_path / "i.jsonl"
        path.write_text(
            '{"id": "x", "item": "hola", "future_field": "desde 2099"}\n',
            encoding="utf-8",
        )
        loaded = js.read_all(path)
        assert loaded == [Item(id="x", item="hola")]

    def test_null_values_coerced_to_empty_string(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        path.write_text(
            '{"id": "x", "item": "hola", "notas": null}\n',
            encoding="utf-8",
        )
        assert js.get(path, "x").notas == ""


# ─── Resiliencia ante líneas corruptas (B3) ─────────────────────────


class TestResilientRead:
    """Un crash a mitad de append deja una línea truncada. read_all NO debe
    tumbar todo el store por eso: salta la línea rota con warning y sigue."""

    def test_skips_truncated_trailing_line(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = tmp_path / "i.jsonl"
        # Dos items buenos + una última línea truncada (crash a mitad de write).
        path.write_text(
            '{"id": "1.001", "item": "uno"}\n'
            '{"id": "2.001", "item": "dos"}\n'
            '{"id": "3.001", "it',  # <- torn, sin cerrar
            encoding="utf-8",
        )
        with caplog.at_level("WARNING"):
            loaded = js.read_all(path)
        assert [it.id for it in loaded] == ["1.001", "2.001"]
        assert any("ilegible" in r.message for r in caplog.records)

    def test_skips_broken_line_in_the_middle(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        path.write_text(
            '{"id": "1.001", "item": "uno"}\n'
            '{ESTO NO ES JSON}\n'
            '{"id": "3.001", "item": "tres"}\n',
            encoding="utf-8",
        )
        assert [it.id for it in js.read_all(path)] == ["1.001", "3.001"]

    def test_skips_non_object_json_line(self, tmp_path: Path) -> None:
        # Una línea que ES JSON válido pero no un objeto (array, número).
        path = tmp_path / "i.jsonl"
        path.write_text(
            '{"id": "1.001", "item": "uno"}\n'
            '[1, 2, 3]\n'
            '42\n'
            '{"id": "2.001", "item": "dos"}\n',
            encoding="utf-8",
        )
        assert [it.id for it in js.read_all(path)] == ["1.001", "2.001"]


class TestAppendSelfHealing:
    """append se auto-protege: si el archivo quedó con una línea sin '\\n'
    final (crash previo), el nuevo item NO debe fusionarse con ella."""

    def test_append_after_torn_line_does_not_merge(self, tmp_path: Path) -> None:
        path = tmp_path / "i.jsonl"
        # Item bueno con newline + línea torn SIN newline final.
        path.write_text(
            '{"id": "1.001", "item": "uno"}\n'
            '{"id": "2.001", "it',  # torn, sin '\n'
            encoding="utf-8",
        )
        # Append de un item nuevo: debe insertar separador antes de escribir.
        js.append(path, Item(id="3.001", item="tres"))

        # El item nuevo se lee bien (no se fusionó con la línea rota).
        loaded = js.read_all(path)
        assert "3.001" in [it.id for it in loaded]
        assert any(it.item == "tres" for it in loaded)
        # La línea torn sigue su propia línea (se descarta al leer, no contamina).
        assert "1.001" in [it.id for it in loaded]

    def test_append_to_clean_file_adds_no_extra_blank_line(
        self, tmp_path: Path
    ) -> None:
        # Si el archivo ya termina en '\n', NO insertamos separador extra
        # (no queremos líneas en blanco gratis).
        path = tmp_path / "i.jsonl"
        js.append(path, Item(id="1.001", item="uno"))
        js.append(path, Item(id="2.001", item="dos"))
        raw = path.read_text(encoding="utf-8")
        assert "\n\n" not in raw

    def test_self_heals_on_next_rewrite(self, tmp_path: Path) -> None:
        # Tras una edición completa (update/delete), la línea rota se purga.
        path = tmp_path / "i.jsonl"
        path.write_text(
            '{"id": "1.001", "item": "uno"}\n'
            '{"id": "2.001", "item": "dos"}\n'
            '{"id": "3.001", "it',  # torn
            encoding="utf-8",
        )
        js.update(path, "1.001", item="uno-editado")
        raw = path.read_text(encoding="utf-8")
        # Ya no queda rastro de la línea truncada.
        assert '"it' not in raw or raw.count("\n") == 2
        assert [it.id for it in js.read_all(path)] == ["1.001", "2.001"]
