"""Tests del FastAPI server. Usamos un project_dir temporal por test."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ikigai import jsonl_store
from ikigai.models import Item
from tests.conftest import TEST_IKIGAI_NAME, make_client


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """Project dir minimo valido. Vive como subdir 'test' del workspace tmp."""
    pdir = tmp_path / TEST_IKIGAI_NAME
    pdir.mkdir()
    jsonl_store.append(
        pdir / "tulipan.jsonl",
        Item(
            id="1.001", item="Item preexistente", cuadrante="1",
            tag_amo="1",
        ),
    )
    return pdir


@pytest.fixture()
def client(project_dir: Path):
    return make_client(project_dir)


def _items(project_dir: Path) -> list[Item]:
    """Lee los items del JSONL del proyecto."""
    return jsonl_store.read_all(project_dir / "tulipan.jsonl")


class TestRoutes:
    def test_root_redirects(self, client: TestClient) -> None:
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 307
        # Tras el refactor multi-ikigai, root redirige al primer ikigai del
        # workspace (alfabeticamente). En tests, solo existe "test".
        assert r.headers["location"] == "/u/test/introspeccion"

    def test_inventario_get_loads(self, client: TestClient) -> None:
        r = client.get("/inventario")
        assert r.status_code == 200
        assert "Gusto" in r.text
        assert "❤️" in r.text
        assert "💵" in r.text
        assert "Item preexistente" in r.text

    def test_nav_toggle_visualizador_first_in_both_pages(
        self, client: TestClient
    ) -> None:
        """Regression: el journey actual prioriza introspección al entrar,
        pero el nav global debe mantener un orden estable en todas las páginas.

        Tras el refactor multi-ikigai los URLs son /u/{name}/{seccion} pero
        el ORDEN visual del nav-toggle se mantiene (introspeccion < sintesis
        < visualizador). El active_href se contrasta contra la URL absoluta
        con prefijo del ikigai actual.
        """
        import re
        prefix = "/u/test"
        for path, active_href in [
            ("/visualizador", f"{prefix}/visualizador"),
            ("/introspeccion", f"{prefix}/introspeccion"),
            ("/inventario", f"{prefix}/introspeccion"),
            ("/sintesis", f"{prefix}/sintesis"),
        ]:
            r = client.get(path)
            assert r.status_code == 200, f"GET {path} failed: {r.status_code}"
            viz_idx = r.text.find(f'href="{prefix}/visualizador"')
            intro_idx = r.text.find(f'href="{prefix}/introspeccion"')
            sint_idx = r.text.find(f'href="{prefix}/sintesis"')
            assert viz_idx != -1 and intro_idx != -1 and sint_idx != -1
            assert intro_idx < sint_idx < viz_idx
            tag_pattern = re.compile(
                rf'<a\b[^>]*\bhref="{re.escape(active_href)}"[^>]*\baria-selected="true"',
                re.DOTALL,
            )
            assert tag_pattern.search(r.text)

    def test_sintesis_get_loads(self, client: TestClient) -> None:
        r = client.get("/sintesis")
        assert r.status_code == 200
        assert "Laboratorio de Alquimia" in r.text
        assert "Fundamentos" in r.text
        for csv_val in ["1", "1b", "2", "2b", "3", "3b", "4", "4b"]:
            assert f'data-csv-value="{csv_val}"' in r.text
        assert "Item preexistente" in r.text
        assert 'data-item-id="1.001"' in r.text

    def test_sintesis_renders_all_presets(self, client: TestClient) -> None:
        from ikigai.algebra import PRESETS
        r = client.get("/sintesis")
        assert r.status_code == 200
        for preset in PRESETS:
            assert preset.label in r.text

    def test_sintesis_evaluate_valid_expression(self, client: TestClient) -> None:
        r = client.post("/sintesis/evaluate", data={"expr": "1 \u222a 2"})
        assert r.status_code == 200
        assert 'data-expr-key="custom"' in r.text
        assert "1 \u222a 2" in r.text
        assert "|\u00b7| =" in r.text

    def test_sintesis_evaluate_invalid_expression(self, client: TestClient) -> None:
        r = client.post("/sintesis/evaluate", data={"expr": "foo bar baz"})
        assert r.status_code == 200
        assert 'data-expr-key="error"' in r.text
        assert "inv\u00e1lida" in r.text

    def test_sintesis_evaluate_unknown_operand(self, client: TestClient) -> None:
        r = client.post("/sintesis/evaluate", data={"expr": "9"})
        assert r.status_code == 200
        assert 'data-expr-key="error"' in r.text

    def test_sintesis_evaluate_empty_expr_rejected_by_form(
        self, client: TestClient
    ) -> None:
        r = client.post("/sintesis/evaluate", data={})
        assert r.status_code == 422


class TestAddItem:
    def test_adds_to_store_and_returns_fragment(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.post(
            "/inventario/item",
            data={"cuadrante": "1", "item_text": "Nuevo item"},
        )
        assert r.status_code == 200
        assert "Nuevo item" in r.text
        assert 'id="item-1.002"' in r.text

        items = _items(project_dir)
        assert len(items) == 2
        assert items[1].item == "Nuevo item"
        assert items[1].fuente == "inventario"

    def test_fragment_uses_closest_selector_not_id_with_dots(
        self, client: TestClient
    ) -> None:
        r = client.post(
            "/inventario/item",
            data={"cuadrante": "1", "item_text": "Test"},
        )
        assert 'hx-target="closest li"' in r.text
        assert "#item-" not in r.text

    def test_rejects_empty_text(self, client: TestClient) -> None:
        r = client.post(
            "/inventario/item", data={"cuadrante": "1", "item_text": "   "}
        )
        assert r.status_code == 400

    def test_rejects_invalid_cuadrante(self, client: TestClient) -> None:
        r = client.post(
            "/inventario/item",
            data={"cuadrante": "zzz", "item_text": "Algo"},
        )
        assert r.status_code == 400

    def test_negative_cuadrante_works(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.post(
            "/inventario/item",
            data={"cuadrante": "1b", "item_text": "Algo que odio"},
        )
        assert r.status_code == 200
        items = _items(project_dir)
        assert any(it.cuadrante == "1b" for it in items)

    def test_intro_v2_saves_tags_scores_and_returns_pill(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.post(
            "/inventario/item",
            data={
                "cuadrante": "1",
                "item_text": "Diseñar sistemas visuales",
                "response_fragment": "introspeccion",
                "source": "introspeccion-v2",
                "tag_amo": "1",
                "tag_bueno": "1",
                "tag_pago": "1",
                "energia_1a5": "5",
                "dominio_1a5": "4",
                "viabilidad_1a5": "3",
            },
        )
        assert r.status_code == 200
        assert "Diseñar sistemas visuales" in r.text
        assert "❤️ Amo" in r.text
        assert "💪 Bueno" in r.text
        assert "💵 Pago" in r.text
        assert "intro-answer-pill" in r.text

        items = _items(project_dir)
        it = items[-1]
        assert it.fuente == "introspeccion-v2"
        assert it.tag_amo == "1"
        assert it.tag_bueno == "1"
        assert it.tag_mundo == ""
        assert it.tag_pago == "1"
        assert it.energia_1a5 == "5"
        assert it.dominio_1a5 == "4"
        assert it.viabilidad_1a5 == "3"

    def test_intro_v2_rejects_invalid_score(self, client: TestClient) -> None:
        r = client.post(
            "/inventario/item",
            data={
                "cuadrante": "1",
                "item_text": "Algo",
                "response_fragment": "introspeccion",
                "energia_1a5": "9",
            },
        )
        assert r.status_code == 400
        assert "energia_1a5" in r.json()["detail"]


class TestDeleteItem:
    def test_deletes_existing(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.delete("/inventario/item/1.001")
        assert r.status_code == 200
        assert len(_items(project_dir)) == 0

    def test_404_on_missing(self, client: TestClient) -> None:
        r = client.delete("/inventario/item/9.999")
        assert r.status_code == 404

    def test_fragment_has_no_hx_confirm(self, client: TestClient) -> None:
        r = client.post(
            "/inventario/item",
            data={"cuadrante": "1", "item_text": "Test"},
        )
        assert "hx-confirm" not in r.text

    def test_fragment_has_data_attrs_for_undo(self, client: TestClient) -> None:
        r = client.post(
            "/inventario/item",
            data={"cuadrante": "1", "item_text": "Foo bar"},
        )
        assert 'data-item-id="1.002"' in r.text
        assert 'data-cuadrante="1"' in r.text
        assert 'data-item-text="Foo bar"' in r.text


class TestUpdateItem:
    def test_updates_text_only(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.patch(
            "/inventario/item/1.001",
            data={"item_text": "  Texto editado  "},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "1.001"
        assert body["item"] == "Texto editado"
        items = _items(project_dir)
        assert items[0].item == "Texto editado"
        assert items[0].cuadrante == "1"

    def test_rejects_empty(self, client: TestClient) -> None:
        r = client.patch(
            "/inventario/item/1.001",
            data={"item_text": "   "},
        )
        assert r.status_code == 400

    def test_404_on_missing(self, client: TestClient) -> None:
        r = client.patch(
            "/inventario/item/9.999",
            data={"item_text": "x"},
        )
        assert r.status_code == 404

    def test_rejects_invalid_cuadrante(
        self, client: TestClient, project_dir: Path
    ) -> None:
        # B1: editar el cuadrante a un valor inexistente debe rechazarse
        # (igual que POST), no corromper el item dejandolo sin clasificacion.
        r = client.patch(
            "/inventario/item/1.001",
            data={"cuadrante": "99"},
        )
        assert r.status_code == 400
        # El item conserva su cuadrante original; no se toco el store.
        items = _items(project_dir)
        assert items[0].cuadrante == "1"

    def test_fragment_marks_text_as_editable(self, client: TestClient) -> None:
        r = client.post(
            "/inventario/item",
            data={"cuadrante": "1", "item_text": "X"},
        )
        assert 'class="item-text' in r.text


class TestRestoreItem:
    def test_restore_reinserts_with_same_id(
        self, client: TestClient, project_dir: Path
    ) -> None:
        client.delete("/inventario/item/1.001")
        assert len(_items(project_dir)) == 0
        r = client.post(
            "/inventario/item/restore",
            data={"item_id": "1.001", "cuadrante": "1", "item_text": "Item preexistente"},
        )
        assert r.status_code == 200
        items = _items(project_dir)
        assert len(items) == 1
        assert items[0].id == "1.001"
        assert items[0].fuente == "inventario-undo"

    def test_restore_rejects_empty_text(self, client: TestClient) -> None:
        r = client.post(
            "/inventario/item/restore",
            data={"item_id": "1.001", "cuadrante": "1", "item_text": "   "},
        )
        assert r.status_code == 400

    def test_restore_rejects_invalid_cuadrante(self, client: TestClient) -> None:
        r = client.post(
            "/inventario/item/restore",
            data={"item_id": "x.001", "cuadrante": "zzz", "item_text": "x"},
        )
        assert r.status_code == 400

    def test_restore_assigns_new_id_on_collision(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.post(
            "/inventario/item/restore",
            data={"item_id": "1.001", "cuadrante": "1", "item_text": "Duplicado"},
        )
        assert r.status_code == 200
        ids = [it.id for it in _items(project_dir)]
        assert ids == ["1.001", "1.002"]


class TestCsvExport:
    """CSV export sigue existiendo como puente de portabilidad humana."""

    def test_returns_csv_when_populated(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.get("/inventario/csv/export")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert 'filename="tulipan.csv"' in r.headers["content-disposition"]
        assert "Item preexistente" in r.text
        assert "BORRAME" not in r.text

    def test_export_includes_utf8_bom_for_excel_compatibility(
        self, client: TestClient, project_dir: Path
    ) -> None:
        """Sin BOM, Excel/Numbers asumen cp1252 y rompen acentos."""
        r = client.get("/inventario/csv/export")
        assert r.content[:3] == b"\xef\xbb\xbf"

    def test_export_then_import_roundtrip_with_bom(
        self, client: TestClient, project_dir: Path
    ) -> None:
        """Round-trip: lo exportado (con BOM) debe re-importarse sin error."""
        # Pre-poblar con items con acentos para verificar encoding round-trip
        items_path = project_dir / "tulipan.jsonl"
        items_path.unlink()
        jsonl_store.append(items_path, Item(
            id="1.001", item="Construcción de marcos conceptuales", cuadrante="1",
        ))
        jsonl_store.append(items_path, Item(
            id="3.001", item="Traducción entre silos", cuadrante="3",
        ))

        exported_bytes = client.get("/inventario/csv/export").content
        assert exported_bytes[:3] == b"\xef\xbb\xbf"

        r = client.post(
            "/inventario/csv/import",
            files={"file": ("reimport.csv", exported_bytes, "text/csv")},
        )
        assert r.status_code == 200, r.json()
        assert r.json()["n_rows"] == 2

        items = _items(project_dir)
        textos = {it.item for it in items}
        assert "Construcción de marcos conceptuales" in textos
        assert "Traducción entre silos" in textos

    def test_returns_template_when_empty(
        self, client: TestClient, project_dir: Path
    ) -> None:
        # Vaciamos el JSONL
        (project_dir / "tulipan.jsonl").write_text("", encoding="utf-8")
        r = client.get("/inventario/csv/export")
        assert r.status_code == 200
        assert 'filename="tulipan-plantilla.csv"' in r.headers["content-disposition"]
        assert "BORRAME" in r.text
        assert ",1," in r.text
        assert ",1b," in r.text

    def test_returns_template_when_file_does_not_exist(
        self, client: TestClient, project_dir: Path
    ) -> None:
        (project_dir / "tulipan.jsonl").unlink()
        r = client.get("/inventario/csv/export")
        assert r.status_code == 200
        assert "BORRAME" in r.text


class TestCsvImport:
    def test_imports_valid_csv_replaces_existing(
        self, client: TestClient, project_dir: Path
    ) -> None:
        new_csv = b"id,item,cuadrante\n3.001,Nuevo A,3\n3b.001,Nuevo B,3b\n"
        r = client.post(
            "/inventario/csv/import",
            files={"file": ("upload.csv", new_csv, "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["n_rows"] == 2
        items = _items(project_dir)
        assert {it.id for it in items} == {"3.001", "3b.001"}
        assert all(it.item != "Item preexistente" for it in items)

    def test_rejects_invalid_cuadrante(
        self, client: TestClient, project_dir: Path
    ) -> None:
        bad = b"id,item,cuadrante\nx.001,Algo,99\n"
        r = client.post(
            "/inventario/csv/import",
            files={"file": ("bad.csv", bad, "text/csv")},
        )
        assert r.status_code == 400
        assert "inv\u00e1lido" in r.json()["detail"]
        # El original sigue intacto
        items = _items(project_dir)
        assert any(it.item == "Item preexistente" for it in items)

    def test_rejects_missing_columns(self, client: TestClient) -> None:
        bad = b"id,item\n1.001,Sin cuadrante\n"
        r = client.post(
            "/inventario/csv/import",
            files={"file": ("bad.csv", bad, "text/csv")},
        )
        assert r.status_code == 400
        assert "cuadrante" in r.json()["detail"]

    def test_accepts_utf8_bom(self, client: TestClient) -> None:
        content = "\ufeffid,item,cuadrante\n1.001,Hola,1\n".encode("utf-8")
        r = client.post(
            "/inventario/csv/import",
            files={"file": ("excel.csv", content, "text/csv")},
        )
        assert r.status_code == 200

    def test_export_import_round_trip_of_template(
        self, client: TestClient, project_dir: Path
    ) -> None:
        """La plantilla exportada vacía debe ser reimportable sin modificación."""
        (project_dir / "tulipan.jsonl").unlink()
        exported = client.get("/inventario/csv/export").text
        r = client.post(
            "/inventario/csv/import",
            files={"file": ("template.csv", exported.encode("utf-8"), "text/csv")},
        )
        assert r.status_code == 200, r.json()
        assert r.json()["n_rows"] == 2


class TestInventarioUiHasExportImportButtons:
    def test_inventario_renders_export_and_import_controls(
        self, client: TestClient
    ) -> None:
        r = client.get("/inventario")
        assert r.status_code == 200
        assert 'href="/u/test/inventario/csv/export"' in r.text
        assert 'id="csv-import-input"' in r.text
        assert 'accept=".csv,text/csv"' in r.text
