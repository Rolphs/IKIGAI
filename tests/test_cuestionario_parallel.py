"""Tests de la nueva logica 'pregunta paralela con resultado real' en /introspeccion.

Cubre:
  - GET /introspeccion: retro section blocks aparecen solo para secciones
    con items; first_unanswered_index correcto.
  - GET /introspeccion/section/{csv}/strip: fragmento de strip.
  - Detecta divergencia chi2 (pregunta espera Mundo, items taguean Pago).
  - 404 para csv_value invalido.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ikigai import jsonl_store
from ikigai.models import Item
from tests.conftest import TEST_IKIGAI_NAME, make_client


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    pdir = tmp_path / TEST_IKIGAI_NAME
    pdir.mkdir()
    (pdir / "tulipan.jsonl").write_text("", encoding="utf-8")
    return pdir


@pytest.fixture()
def client(project_dir: Path):
    return make_client(project_dir)


# ─── GET /introspeccion (pagina completa) ─────────────────────────


class TestIntrospeccionRetroBlocks:
    """La pagina renderiza SIEMPRE los 8 section-blocks (uno por pregunta).

    Nuevo diseno (form inline por pregunta): no hay cursor ni bloques
    condicionales. Cada pregunta trae su propio campo de reflexion.
    """

    def test_vacio_renderiza_los_8_bloques(self, client) -> None:
        """JSONL sin items -> igual aparecen los 8 bloques, cada uno con su form."""
        r = client.get("/introspeccion")
        assert r.status_code == 200
        assert r.text.count('<div class="cuestionario-section-block') == 8

    def test_cada_bloque_tiene_su_form_inline(self, client) -> None:
        """Cada pregunta trae su propio form para agregar reflexiones."""
        r = client.get("/introspeccion")
        assert r.text.count('class="section-answer-form') == 8

    def test_un_item_aparece_como_pill_en_su_bloque(self, project_dir: Path, client) -> None:
        """Item en cuadrante=3 -> su texto aparece en el bloque de pregunta 3."""
        items_path = project_dir / "tulipan.jsonl"
        jsonl_store.append(items_path, Item(
            id="3.001", item="salud mental accesible",
            cuadrante="3", tag_mundo="1",
        ))
        r = client.get("/introspeccion")
        assert 'data-section-csv="3"' in r.text
        assert "salud mental accesible" in r.text
        # Siguen siendo 8 bloques (uno por pregunta), con o sin items.
        assert r.text.count('<div class="cuestionario-section-block') == 8


# ─── GET /introspeccion/section/{csv}/strip ─────────────────────


class TestSectionStripEndpoint:
    """Fragmento HTML del strip de resultado real para una seccion."""

    def test_csv_invalido_404(self, client) -> None:
        r = client.get("/introspeccion/section/99/strip")
        assert r.status_code == 404

    def test_seccion_vacia_dice_invitacion_inventario(self, client) -> None:
        """Sin items: muestra hint para ir a clasificar a inventario."""
        r = client.get("/introspeccion/section/1/strip")
        assert r.status_code == 200
        assert "inventario" in r.text
        # No deberia mostrar barras de distribucion vacias.
        assert "0 · 0%" not in r.text

    def test_seccion_sombra_dice_que_no_espera_tag(self, client) -> None:
        """Preguntas con 'b' (sombras) renderizan mensaje distinto."""
        r = client.get("/introspeccion/section/3b/strip")
        assert r.status_code == 200
        assert "Sombra" in r.text

    def test_alineado_no_muestra_divergencia(self, project_dir: Path, client) -> None:
        """Item evocado por pregunta 1 + tagueado tag_amo -> sin warning."""
        items_path = project_dir / "tulipan.jsonl"
        jsonl_store.append(items_path, Item(
            id="1.001", item="construir marcos",
            cuadrante="1", tag_amo="1",
        ))
        r = client.get("/introspeccion/section/1/strip")
        assert r.status_code == 200
        assert "ningún item tagueó" not in r.text.lower()
        # El check del circulo esperado debe aparecer.
        assert "Círculo esperado" in r.text

    def test_divergencia_se_muestra(self, project_dir: Path, client) -> None:
        """Pregunta Mundo (3), pero todos los items taguearon Pago (4) -> warning."""
        items_path = project_dir / "tulipan.jsonl"
        # Item evocado por pregunta Mundo pero el usuario solo lo tageo como Pago.
        jsonl_store.append(items_path, Item(
            id="3.001", item="consultoria",
            cuadrante="3", tag_pago="1",  # tag_mundo INTENCIONALMENTE en blanco
        ))
        r = client.get("/introspeccion/section/3/strip")
        assert r.status_code == 200
        # Debe gritar la divergencia chi2.
        assert "ningún item tagueó" in r.text

    def test_distribucion_se_calcula_correctamente(
        self, project_dir: Path, client
    ) -> None:
        """4 items en pregunta 1: 2 tag_amo, 2 tag_bueno -> 50/50."""
        items_path = project_dir / "tulipan.jsonl"
        for i, tags in enumerate([
            {"tag_amo": "1"},
            {"tag_amo": "1"},
            {"tag_bueno": "1"},
            {"tag_bueno": "1"},
        ]):
            jsonl_store.append(items_path, Item(
                id=f"1.{i:03d}", item=f"item-{i}", cuadrante="1", **tags,
            ))
        r = client.get("/introspeccion/section/1/strip")
        assert r.status_code == 200
        # Deben aparecer "2 · 50%" para Amo y para Bueno.
        assert r.text.count("2 · 50%") == 2
