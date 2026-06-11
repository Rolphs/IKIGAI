"""Tests del SVG descargable con callouts (export.render_venn_svg) y del
endpoint GET /visualizador/venn.svg.

El SVG del visualizador EN PANTALLA trunca nombres para caber en las regiones;
el export debe NO truncar (callouts hacia los margenes). Estos tests blindan
esa promesa de claridad y que el .svg sea standalone valido.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ikigai.export import render_venn_svg
from ikigai.server import create_app
from tests.test_export import _write_project  # reusa el helper de proyecto

_NAMES = {
    "1": "Comprender", "2": "Transmitir", "3": "orden", "4": "Insights",
    "1,2": "ensenar", "1,3": "mision1", "2,4": "profesion1", "3,4": "vocacion1",
    "1,4": "hobby_pagado", "2,3": "servicio_voluntario",
    "1,2,3": "sin_mercado", "1,2,4": "sin_mundo", "1,3,4": "sin_habilidad",
    "2,3,4": "sin_gusto", "1,2,3,4": "MAESTRO",
}


def _complete(tmp_path: Path) -> Path:
    project = tmp_path / "raul-test"
    _write_project(project, personal_names=_NAMES)
    return project


class TestRenderVennSvg:
    def test_standalone_svg_full_names_no_truncation(self, tmp_path: Path) -> None:
        svg = render_venn_svg(_complete(tmp_path))
        assert svg.startswith("<?xml")
        assert "<svg" in svg and "http://www.w3.org/2000/svg" in svg
        assert "MAESTRO" in svg          # centro Ikigai completo
        assert "\u2026" not in svg       # CERO elipsis (sin truncar)
        assert "callout-line" in svg     # lineas guia
        assert "∩" in svg           # subtitulo de cruce (interseccion)

    def test_no_relative_dy_em_cross_renderer(self, tmp_path: Path) -> None:
        # Guard: 'dy' con unidades em NO lo soportan Inkscape/Office/Illustrator
        # (colapsan los tspans a una linea). Posicionamos con y absoluto.
        svg = render_venn_svg(_complete(tmp_path))
        assert 'dy=' not in svg

    def test_pending_project_renders(self, tmp_path: Path) -> None:
        project = tmp_path / "pristine"
        _write_project(project)  # sin nombres
        svg = render_venn_svg(project)
        assert svg.startswith("<?xml")
        assert "IKIGAI" in svg


class TestVennSvgEndpoint:
    def _client(self, tmp_path: Path) -> tuple[TestClient, str]:
        workspace = tmp_path / "ws"
        project = workspace / "raul-test"
        _write_project(project, personal_names=_NAMES)
        return TestClient(create_app(workspace)), "raul-test"

    def test_endpoint_serves_downloadable_svg(self, tmp_path: Path) -> None:
        client, slug = self._client(tmp_path)
        r = client.get(f"/u/{slug}/visualizador/venn.svg")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/svg+xml")
        assert "attachment" in r.headers.get("content-disposition", "")
        assert "MAESTRO" in r.text
        assert "\u2026" not in r.text
