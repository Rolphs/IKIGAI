"""Tests HTTP del endpoint /sintesis/concept y de la pagina /sintesis.

Cubre el comportamiento HTTP/HTMX:
  - GET /sintesis renderiza las 11 cards de interseccion con etiquetas humanas.
  - POST /sintesis/concept persiste / borra nombres personales y devuelve el
    fragmento HTMX correcto (con id DOM normalizado: comas -> guiones).

Las unidades puras del modulo `intersection_concepts` viven en
test_intersection_concepts.py (sin HTTP). Aqui solo lo que requiere TestClient.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from ikigai import intersection_concepts as ic
from ikigai import jsonl_store
from ikigai.models import Item
from tests.conftest import TEST_IKIGAI_NAME, make_client


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    pdir = tmp_path / TEST_IKIGAI_NAME
    pdir.mkdir()
    items = [
        Item(id="1.001", item="Caminar", cuadrante="1",
             tag_amo="1", tag_bueno="1"),
        Item(id="1.002", item="Pensar", cuadrante="1",
             tag_amo="1", tag_bueno="1"),
        Item(id="3.001", item="Solo mundo", cuadrante="3",
             tag_mundo="1"),
    ]
    jsonl_store.write_all(pdir / "tulipan.jsonl", items)
    return pdir


@pytest.fixture()
def client(project_dir: Path):
    return make_client(project_dir)


class TestSintesisIntersectionsPage:
    def test_get_renders_all_11_cards(self, client: TestClient) -> None:
        r = client.get("/sintesis")
        assert r.status_code == 200
        # Cada interseccion tiene un id "card-{key}". Verifico las 11.
        expected_keys = [
            "1,2", "1,3", "2,4", "3,4",          # canonicas de 2
            "1,4", "2,3",                         # diagonales
            "1,2,3", "1,2,4", "1,3,4", "2,3,4",  # casi-ikigai
            "1,2,3,4",                            # centro
        ]
        for key in expected_keys:
            # IDs DOM usan '-' en vez de ',' porque CSS interpreta la coma
            # como separador de selectores. La key canonica del backend
            # sigue siendo "1,2" — solo el atributo id visual cambia.
            dom_id = key.replace(",", "-")
            assert f'id="card-{dom_id}"' in r.text, f"falta card {key}"

    def test_pasion_shows_members_from_csv(self, client: TestClient) -> None:
        # En el CSV: caminar (amo+bueno) y pensar (amo+bueno) → 1∩2 = {caminar, pensar}
        r = client.get("/sintesis")
        # El fragmento de pasion contiene ambos items.
        # Para no acoplar al HTML exacto, verifico que ambos textos aparezcan.
        assert "Caminar" in r.text
        assert "Pensar" in r.text

    def test_canonical_name_visible_in_card(self, client: TestClient) -> None:
        r = client.get("/sintesis")
        # Pasion debe aparecer como nombre canonico de 1∩2.
        assert "Pasion" in r.text

    def test_cards_show_human_labels_not_csv_codes(self, client: TestClient) -> None:
        # Petition de Rolph: el header de cada card debe mostrar 'Amo ∩ Bueno'
        # no '1 ∩ 2'. La notacion cruda sigue ahi como referencia (en gris).
        # Verificamos pieza por pieza porque el render incluye emojis intermedios
        # ("❤️ Amo ∩ 💪 Bueno") y matchear el string exacto seria fragil.
        r = client.get("/sintesis")
        for name in ("Amo", "Bueno", "Mundo", "Pago"):
            assert name in r.text, f"falta circulo '{name}' en alguna card"
        # Por lo menos un simbolo de interseccion humano (no solo el set_notation
        # crudo que tambien usa ∩). Como la notacion cruda usa solo digitos, basta
        # verificar que "Amo ∩" aparece en algun lado — eso implica que el header
        # del card lo renderizo en formato humano.
        assert "Amo ∩" in r.text.replace("❤️ ", "")  # ignorando emoji prefix

    def test_layer_1_2_cards_have_raw_materials_in_disclosure(self, client: TestClient) -> None:
        # Despues del rediseno-capa-0: el modelo constructivo es estricto.
        # Capa N usa SOLO sintesis de capa N-1 como inspiracion principal.
        # Los items crudos se mueven a un disclosure colapsado (escape hatch).
        # Asi la card de capa 1 se enfoca en: ingredientes de capa 0 + input.
        r = client.get("/sintesis")
        # Existe el disclosure para capas 1-3 (con texto generico que cubre
        # 2, 3 o 4 circulos segun la capa).
        assert "Ver materia prima cruda — items de los" in r.text

    def test_layer_3_keeps_raw_materials_in_disclosure(self, client: TestClient) -> None:
        # En Ikigai (capa 3) el disclosure tiene 4 circulos. Verificamos
        # explicitamente que el texto plural funciona y aparece.
        r = client.get("/sintesis")
        assert "items de los 4 círculos" in r.text


class TestSaveConceptEndpoint:
    def test_post_saves_personal_name_and_returns_card(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.post(
            "/sintesis/concept",
            data={"key": "1,2", "personal_name": "pensamiento activo"},
        )
        assert r.status_code == 200
        # Devuelve solo la card actualizada (HTMX swap). El id DOM reemplaza
        # las comas con guiones porque CSS interpreta ',' como separador de
        # selectores (rompia HTMX para todas las intersecciones). La key del
        # backend sigue siendo "1,2" (canonical), solo el id visual cambia.
        assert 'id="card-1-2"' in r.text
        assert 'hx-target="#card-1-2"' in r.text
        assert "pensamiento activo" in r.text
        # Persiste en YAML.
        yaml_path = project_dir / "intersection_concepts.yaml"
        assert yaml_path.exists()
        names = ic.load_personal_names(yaml_path)
        assert names == {"1,2": "pensamiento activo"}

    def test_post_empty_name_removes_entry(
        self, client: TestClient, project_dir: Path
    ) -> None:
        # Primero crea, luego borra.
        client.post("/sintesis/concept", data={"key": "1,2", "personal_name": "X"})
        r = client.post("/sintesis/concept", data={"key": "1,2", "personal_name": ""})
        assert r.status_code == 200
        names = ic.load_personal_names(project_dir / "intersection_concepts.yaml")
        assert names == {}

    def test_post_rejects_unknown_key(self, client: TestClient) -> None:
        # Defensa basica contra YAML pollution via keys arbitrarias.
        r = client.post(
            "/sintesis/concept",
            data={"key": "9,99", "personal_name": "x"},
        )
        assert r.status_code == 400

    def test_save_propagates_to_dependent_cards_oob(
        self, client: TestClient
    ) -> None:
        # Al bautizar "1,2", las cards que la contienen (1,2,3 / 1,2,4 / 1,2,3,4)
        # se devuelven como OOB swaps para que reflejen el nombre sin refrescar.
        r = client.post(
            "/sintesis/concept",
            data={"key": "1,2", "personal_name": "puente activo"},
        )
        assert r.status_code == 200
        # La card guardada es el target normal (sin oob).
        assert 'id="card-1-2"' in r.text
        # Una dependiente (superset estricto) viene marcada como OOB.
        assert 'id="card-1-2-3"' in r.text
        assert "hx-swap-oob" in r.text
        # El nombre nuevo aparece tambien dentro de la dependiente (propagado).
        assert r.text.count("puente activo") >= 2

    def test_save_primitive_propagates_to_supersets(
        self, client: TestClient
    ) -> None:
        # Guardar el primitivo "1" actualiza toda card que contenga el circulo 1.
        r = client.post(
            "/sintesis/concept", data={"key": "1", "personal_name": "comer"}
        )
        assert r.status_code == 200
        assert 'id="card-1"' in r.text  # target principal
        assert 'id="card-1-2"' in r.text  # dependiente OOB
        assert "hx-swap-oob" in r.text

    def test_get_after_save_shows_saved_name(
        self, client: TestClient, project_dir: Path
    ) -> None:
        client.post("/sintesis/concept", data={"key": "1,3", "personal_name": "vocacion personal"})
        r = client.get("/sintesis")
        assert r.status_code == 200
        assert "vocacion personal" in r.text


class TestAddItemEndpoint:
    """POST /sintesis/item/add agrega materia prima a un primitivo de capa 0
    sin salir de la pagina, y re-renderiza la card (lista + contadores)."""

    def test_add_item_to_positive_autotags_and_persists(
        self, client: TestClient, project_dir: Path
    ) -> None:
        items_path = project_dir / "tulipan.jsonl"
        before = len(jsonl_store.read_all(items_path))
        r = client.post(
            "/sintesis/item/add", data={"key": "1", "item_text": "Nadar al amanecer"}
        )
        assert r.status_code == 200
        # Re-renderiza la card del primitivo "1" con el item nuevo dentro.
        assert 'id="card-1"' in r.text
        assert "Nadar al amanecer" in r.text
        # Persiste con cuadrante=1 y auto-tag tag_amo=1 (cae en el set por tag).
        items = jsonl_store.read_all(items_path)
        assert len(items) == before + 1
        nuevo = next(it for it in items if it.item == "Nadar al amanecer")
        assert nuevo.cuadrante == "1"
        assert nuevo.tag_amo == "1"
        assert nuevo.fuente == "sintesis"

    def test_add_item_to_shadow_has_no_tags(
        self, client: TestClient, project_dir: Path
    ) -> None:
        items_path = project_dir / "tulipan.jsonl"
        r = client.post(
            "/sintesis/item/add", data={"key": "1b", "item_text": "Scrollear sin parar"}
        )
        assert r.status_code == 200
        nuevo = next(
            it for it in jsonl_store.read_all(items_path)
            if it.item == "Scrollear sin parar"
        )
        assert nuevo.cuadrante == "1b"
        # Sombras se agrupan por `cuadrante`, sin tags positivos.
        assert (nuevo.tag_amo, nuevo.tag_bueno, nuevo.tag_mundo, nuevo.tag_pago) == (
            "", "", "", "",
        )

    def test_add_empty_item_is_noop(
        self, client: TestClient, project_dir: Path
    ) -> None:
        items_path = project_dir / "tulipan.jsonl"
        before = len(jsonl_store.read_all(items_path))
        r = client.post("/sintesis/item/add", data={"key": "1", "item_text": "   "})
        assert r.status_code == 200  # no spamea error
        assert len(jsonl_store.read_all(items_path)) == before  # nada creado

    def test_add_item_rejects_non_primitive_key(self, client: TestClient) -> None:
        # El "+ Item" solo aplica a capa 0; una interseccion no es un cuadrante.
        r = client.post(
            "/sintesis/item/add", data={"key": "1,2", "item_text": "x"}
        )
        assert r.status_code == 400
