"""
Tests del comando `ikigai export` y el modulo export.

Cubre:
  - Generacion correcta del HTML estatico
  - Self-containment: sin refs a archivos locales (solo CDNs HTTPS)
  - Manejo de proyectos incompletos (sin acuñar)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ikigai import jsonl_store
from ikigai.export import build_export_context, export_snapshot, render_export
from ikigai.models import Item

# ─── Fixtures locales (proyectos minimos en disco) ─────────────────────────


def _write_project(
    project_dir: Path,
    *,
    items: list[tuple[str, str, str]] | None = None,
    personal_names: dict[str, str] | None = None,
) -> None:
    """Construye un proyecto minimo: tulipan.jsonl + (opcional) intersection_concepts.yaml.

    `items` es lista de tuplas (id, texto, tag_csv_value). El tag determina
    en cual circulo positivo cae el item (1=amo, 2=bueno, 3=mundo, 4=pago).
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    items = items or [
        ("1.001", "amar el ajedrez", "1"),
        ("2.001", "soy bueno explicando", "2"),
        ("3.001", "el mundo necesita educacion", "3"),
        ("4.001", "me pagan por dar clases", "4"),
    ]

    item_objs = [
        Item(
            id=item_id,
            item=text,
            cuadrante=tag,
            fuente="test",
            tag_amo="1" if tag == "1" else "",
            tag_bueno="1" if tag == "2" else "",
            tag_mundo="1" if tag == "3" else "",
            tag_pago="1" if tag == "4" else "",
        )
        for item_id, text, tag in items
    ]
    jsonl_store.write_all(project_dir / "tulipan.jsonl", item_objs)

    if personal_names:
        # Formato de intersection_concepts.yaml es {concepts: {key: name}}
        lines = ["concepts:"]
        for key, name in personal_names.items():
            # Keys con coma necesitan quoting; keys de un solo digit tambien
            # por consistencia con como las escribe la app.
            lines.append(f"  '{key}': {name}")
        (project_dir / "intersection_concepts.yaml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8"
        )


@pytest.fixture()
def complete_project(tmp_path: Path) -> Path:
    """Proyecto con TODA la cadena causal acuñada (15 nombres personales).

    Esto refleja la regla de negocio del modulo intersection_concepts:
    una card solo es `is_secured` si su personal_name existe Y todos sus
    ingredientes (ancestros) tambien lo estan. Para que el centro Ikigai
    cuente como acuñado, hay que haber nombrado los 4 primitivos + 6 pares
    + 4 trios + el centro = 15 nombres.
    """
    project = tmp_path / "rolph_test"
    _write_project(
        project,
        personal_names={
            # Capa 0 (primitivos)
            "1": "Comprender",
            "2": "Transmitir",
            "3": "orden",
            "4": "Insights",
            # Capa 1 (pares: 4 canonicos + 2 diagonales)
            "1,2": "enseñar",
            "1,3": "mision1",
            "2,4": "profesion1",
            "3,4": "vocacion1",
            "1,4": "hobby_pagado",
            "2,3": "servicio_voluntario",
            # Capa 2 (trios: casi-Ikigai)
            "1,2,3": "sin_mercado",
            "1,2,4": "sin_mundo",
            "1,3,4": "sin_habilidad",
            "2,3,4": "sin_gusto",
            # Capa 3 (el centro)
            "1,2,3,4": "MAESTRO",
        },
    )
    return project


@pytest.fixture()
def empty_project(tmp_path: Path) -> Path:
    """Proyecto con items pero sin ningun nombre personal asignado."""
    project = tmp_path / "pristine"
    _write_project(project)  # sin personal_names
    return project


# ─── Tests ────────────────────────────────────────────────────────────────


class TestBuildExportContext:
    """La capa de logica pura: lee proyecto, devuelve dict para template."""

    def test_returns_4_layers_of_cards(self, complete_project: Path) -> None:
        ctx = build_export_context(complete_project)
        # Capa 0: 8 primitivos (4 positivos + 4 sombras) · 1: 6 pares · 2: 4 trios · 3: 1 centro = 19
        assert len(ctx["cards_by_layer"][0]) == 8
        assert len(ctx["cards_by_layer"][1]) == 6
        assert len(ctx["cards_by_layer"][2]) == 4
        assert len(ctx["cards_by_layer"][3]) == 1
        assert len(ctx["cards"]) == 19

    def test_ikigai_center_is_referenced(self, complete_project: Path) -> None:
        ctx = build_export_context(complete_project)
        assert ctx["ikigai"] is not None
        assert ctx["ikigai"]["personal_name"] == "MAESTRO"
        assert ctx["is_complete"] is True

    def test_empty_project_marks_as_incomplete(self, empty_project: Path) -> None:
        ctx = build_export_context(empty_project)
        assert ctx["is_complete"] is False
        assert ctx["total_secured"] == 0
        # Pero las cards si existen (sin personal_name) — 19 nodos del catalogo
        assert len(ctx["cards"]) == 19

    def test_items_per_positive_circle(self, complete_project: Path) -> None:
        ctx = build_export_context(complete_project)
        # 1 item por circulo en la fixture base
        assert len(ctx["items_per_positive"]["1"]) == 1
        assert ctx["items_per_positive"]["1"][0].item == "amar el ajedrez"

    def test_venn_regions_mapped_for_all_15_regions(self, complete_project: Path) -> None:
        """El hero del Venn necesita poder mirar cualquiera de las 15 regiones
        por su nombre topologico (a, ab, abcd...) y obtener la card."""
        ctx = build_export_context(complete_project)
        regions = ctx["venn_regions_by_key"]
        # 4 primitivos + 6 pares + 4 trios + 1 centro = 15
        assert len(regions) == 15
        # Spot-check del mapeo critico: el centro abcd debe ser el Ikigai
        assert regions["abcd"]["personal_name"] == "MAESTRO"
        # ab = Pasion = 1∩2 = "enseñar"
        assert regions["ab"]["personal_name"] == "enseñar"
        # Cada region apunta a una card real con su key
        for card in regions.values():
            assert "key" in card
            assert "personal_name" in card


class TestRenderExport:
    """La capa de template: dict → HTML string."""

    def test_html_contains_personal_names(self, complete_project: Path) -> None:
        ctx = build_export_context(complete_project)
        html = render_export(ctx)
        assert "MAESTRO" in html  # el centro
        assert "Comprender" in html
        assert "enseñar" in html  # la sintesis de capa 1

    def test_html_contains_items(self, complete_project: Path) -> None:
        ctx = build_export_context(complete_project)
        html = render_export(ctx)
        assert "amar el ajedrez" in html
        assert "soy bueno explicando" in html

    def test_html_is_self_contained(self, complete_project: Path) -> None:
        """Cero assets externos: el CSS va INLINE, no hay <script src>/<link href>.

        Garantiza que el HTML se ve bien en cualquier red (sin depender de
        cdn.tailwindcss.com) y que se puede mover a otro lado y seguir
        funcionando (precondicion para hosting estatico).
        """
        ctx = build_export_context(complete_project)
        html = render_export(ctx)

        # Regresion: NUNCA volver a un CDN externo en runtime.
        assert "cdn.tailwindcss" not in html
        assert "unpkg.com" not in html
        # El CSS de Tailwind debe estar INLINE (no por <link>/<script>).
        assert "<style>" in html
        assert ".text-brand-100" in html or "text-brand-100" in html

        # No debe quedar ningun asset por URL (src/href), salvo anclas internas.
        for match in re.finditer(r'(?:src|href)\s*=\s*"([^"]+)"', html):
            url = match.group(1)
            assert url.startswith("#"), (
                f"Asset no-self-contained: {url!r} — el snapshot debe ser 100% inline"
            )

    def test_incomplete_project_shows_warning_markers(self, empty_project: Path) -> None:
        ctx = build_export_context(empty_project)
        html = render_export(ctx)
        # Cards sin acuñar deben mostrarse con marcador explicito
        assert "sin acuñar" in html
        # Y el centro debe decir "en construcción"
        assert "construcción" in html

    def test_html_includes_venn4_svg_hero(self, complete_project: Path) -> None:
        """El hero principal es el diagrama de Venn de 4 elipses (Edwards 1989).
        Sin esto, el snapshot solo muestra cards — perdiendo la sintesis visual."""
        ctx = build_export_context(complete_project)
        html = render_export(ctx)
        # SVG presente y con las 4 elipses esperadas (4 <ellipse> tags)
        assert "<svg" in html
        assert html.count("<ellipse") == 4
        # El centro debe verse en el SVG, no solo abajo en la seccion capa 3
        # (verificamos que MAESTRO aparezca al menos 2 veces: en Venn + en card)
        assert html.count("MAESTRO") >= 2


class TestExportSnapshot:
    """La API publica end-to-end: lee proyecto → escribe HTML a disco."""

    def test_writes_html_file(self, complete_project: Path, tmp_path: Path) -> None:
        out = tmp_path / "out.html"
        written = export_snapshot(complete_project, out)

        assert written == out
        assert out.exists()
        assert out.stat().st_size > 1000  # algo razonable, no un .html vacio

    def test_creates_parent_dirs(self, complete_project: Path, tmp_path: Path) -> None:
        out = tmp_path / "deep" / "nested" / "dir" / "snapshot.html"
        export_snapshot(complete_project, out)
        assert out.exists()

    def test_html_opens_as_valid_html(
        self, complete_project: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "out.html"
        export_snapshot(complete_project, out)
        content = out.read_text(encoding="utf-8")
        assert content.startswith("<!doctype html>")
        assert "</html>" in content
        assert 'lang="es"' in content  # i18n esperado
