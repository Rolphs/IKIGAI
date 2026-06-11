"""Tests del modo zen-discovery en /inventario/item.

La introspeccion (discovery) NO envia checkboxes de tags: el backend
auto-asigna el tag del circulo evocador para preguntas positivas, y
deja sin tags las preguntas de sombra (complemento por definicion).

Esto separa modos cognitivos:
  - Discovery (introspeccion) = generativo, flow, cero clasificacion meta.
  - Curation (inventario) = analitico, multi-tag, deliberado.

La separacion ademas hace mas honesta la señal chi²: cualquier
divergencia entre cuadrante evocador y tag asignado pasa a ser
intencional (curacion deliberada), no ruido de UI.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ikigai import jsonl_store
from ikigai.models import Item
from tests.conftest import TEST_IKIGAI_NAME, make_client


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    pdir = tmp_path / TEST_IKIGAI_NAME
    pdir.mkdir()
    # JSONL vacío (archivo creado, sin items).
    (pdir / "tulipan.jsonl").write_text("", encoding="utf-8")
    return pdir


@pytest.fixture()
def client(project_dir: Path):
    return make_client(project_dir)


def _items(project_dir: Path) -> list[Item]:
    return jsonl_store.read_all(project_dir / "tulipan.jsonl")


class TestZenDiscoveryAutoTag:
    @pytest.mark.parametrize("cuadrante,expected_tag_attr", [
        ("1", "tag_amo"),
        ("2", "tag_bueno"),
        ("3", "tag_mundo"),
        ("4", "tag_pago"),
    ])
    def test_positive_cuadrante_auto_tags_its_circle(
        self,
        client: TestClient,
        project_dir: Path,
        cuadrante: str,
        expected_tag_attr: str,
    ) -> None:
        """POST desde introspeccion sin tags → auto-asigna el tag del circulo."""
        r = client.post(
            "/inventario/item",
            data={
                "cuadrante": cuadrante,
                "item_text": "Item zen",
                "response_fragment": "introspeccion",
                "source": "introspeccion-v2",
            },
        )
        assert r.status_code == 200

        it = _items(project_dir)[-1]
        assert getattr(it, expected_tag_attr) == "1"
        other_tags = {"tag_amo", "tag_bueno", "tag_mundo", "tag_pago"} - {expected_tag_attr}
        for col in other_tags:
            assert getattr(it, col) == "", f"{col} deberia estar vacio"

    @pytest.mark.parametrize("cuadrante", ["1b", "2b", "3b", "4b"])
    def test_shadow_cuadrante_leaves_item_untagged(
        self,
        client: TestClient,
        project_dir: Path,
        cuadrante: str,
    ) -> None:
        """Preguntas de sombra son complemento por definicion: sin tags."""
        r = client.post(
            "/inventario/item",
            data={
                "cuadrante": cuadrante,
                "item_text": "Item sombra",
                "response_fragment": "introspeccion",
                "source": "introspeccion-v2",
            },
        )
        assert r.status_code == 200

        it = _items(project_dir)[-1]
        for col in ("tag_amo", "tag_bueno", "tag_mundo", "tag_pago"):
            assert getattr(it, col) == "", (
                f"sombra ({cuadrante}) NO debe asignar tags pero {col}={getattr(it, col)!r}"
            )


class TestZenDiscoveryRespectsExplicitTags:
    """Si el cliente SI manda tags (inventario, edicion, etc.) los respetamos."""

    def test_explicit_tags_not_overwritten_by_auto_assignment(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.post(
            "/inventario/item",
            data={
                "cuadrante": "1",
                "item_text": "Cruzado",
                "tag_pago": "1",
            },
        )
        assert r.status_code == 200

        it = _items(project_dir)[-1]
        assert it.tag_pago == "1"
        assert it.tag_amo == ""

    def test_multi_tag_intent_preserved(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.post(
            "/inventario/item",
            data={
                "cuadrante": "1",
                "item_text": "Multi",
                "tag_amo": "1",
                "tag_bueno": "1",
                "tag_mundo": "1",
            },
        )
        assert r.status_code == 200

        it = _items(project_dir)[-1]
        assert it.tag_amo == "1"
        assert it.tag_bueno == "1"
        assert it.tag_mundo == "1"
        assert it.tag_pago == ""


class TestIntrospectionTemplateIsZen:
    """El template de introspeccion ya no expone los 4 checkboxes de circulos."""

    def test_no_circle_checkboxes_in_intro_form(self, client: TestClient) -> None:
        r = client.get("/introspeccion")
        assert r.status_code == 200
        for tag in ("tag_amo", "tag_bueno", "tag_mundo", "tag_pago"):
            assert f'name="{tag}"' not in r.text, (
                f"el form de introspeccion no debe exponer checkbox {tag}"
            )

    def test_reclassify_hint_points_to_inventario(self, client: TestClient) -> None:
        r = client.get("/introspeccion")
        assert "/inventario" in r.text
