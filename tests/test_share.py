"""
Tests del feature de shareability del export.

Cubre:
  - El flag `redact` de build_export_context / export_snapshot oculta items
  - El modo redacted muestra badge visual y mantiene el resto del snapshot

Por que archivo separado de test_export.py:
  Estos tests tocan el CONTRATO de privacidad/compartir, no la generacion
  del snapshot per se. Mantenerlos separados:
   - Hace explicito el feature (mira el nombre del archivo y sabes que hay)
   - Permite cambiar la politica de redact sin tocar tests de export base
   - Sigue SRP a nivel de modulo de tests
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from ikigai import jsonl_store
from ikigai.export import build_export_context, export_snapshot, render_export
from ikigai.models import Item

# ─── Fixture reutilizada (mismo patron que test_export.py) ──────────────────


def _write_minimal_project(project_dir: Path) -> Path:
    """Proyecto minimo: 1 item por circulo, sin nombres personales.

    Suficiente para verificar que el flag redact se propaga, sin requerir
    la fixture grande de 15 nombres del modulo test_export.py.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    items = [
        Item(id="1.001", item="SECRETO_AMO",   cuadrante="1", fuente="test", tag_amo="1"),
        Item(id="2.001", item="SECRETO_BUENO", cuadrante="2", fuente="test", tag_bueno="1"),
        Item(id="3.001", item="SECRETO_MUNDO", cuadrante="3", fuente="test", tag_mundo="1"),
        Item(id="4.001", item="SECRETO_PAGO",  cuadrante="4", fuente="test", tag_pago="1"),
    ]
    jsonl_store.write_all(project_dir / "tulipan.jsonl", items)
    return project_dir


@pytest.fixture()
def minimal_project(tmp_path: Path) -> Path:
    return _write_minimal_project(tmp_path / "shareable")


# ─── Tests de la opcion `redact` en la API Python ───────────────────────


class TestRedactFlag:
    """El flag redact debe propagarse desde la API publica hasta el HTML."""

    def test_context_marks_redacted_field(self, minimal_project: Path) -> None:
        ctx_full = build_export_context(minimal_project, redact=False)
        ctx_red = build_export_context(minimal_project, redact=True)
        assert ctx_full["redacted"] is False
        assert ctx_red["redacted"] is True

    def test_redacted_html_hides_item_texts(self, minimal_project: Path) -> None:
        """El proposito de redact: NO debe aparecer ningun texto de item."""
        ctx = build_export_context(minimal_project, redact=True)
        html = render_export(ctx)
        # Los 4 textos sentinela NO deben estar
        assert "SECRETO_AMO" not in html
        assert "SECRETO_BUENO" not in html
        assert "SECRETO_MUNDO" not in html
        assert "SECRETO_PAGO" not in html

    def test_non_redacted_html_includes_item_texts(self, minimal_project: Path) -> None:
        """Sanity check inverso: sin redact, los textos SI aparecen."""
        ctx = build_export_context(minimal_project, redact=False)
        html = render_export(ctx)
        assert "SECRETO_AMO" in html
        assert "SECRETO_PAGO" in html

    def test_redacted_html_shows_share_badge(self, minimal_project: Path) -> None:
        """El usuario debe ver claramente que esta viendo una version redacted."""
        ctx = build_export_context(minimal_project, redact=True)
        html = render_export(ctx)
        assert "versión compartible" in html
        assert "🔒" in html

    def test_redacted_html_still_shows_counts(self, minimal_project: Path) -> None:
        """Redact oculta TEXTO pero conserva CONTEOS — necesarios para contexto."""
        ctx = build_export_context(minimal_project, redact=True)
        html = render_export(ctx)
        # Con 1 item por circulo, el conteo "(1)" debe aparecer al menos 4 veces
        # (uno por circulo positivo en la seccion "Lo que sembraste")
        assert html.count("(1)") >= 4

    def test_redacted_html_is_still_self_contained(self, minimal_project: Path) -> None:
        """Redact no debe romper la propiedad de self-containment."""
        ctx = build_export_context(minimal_project, redact=True)
        html = render_export(ctx)
        for match in re.finditer(r'(?:src|href)\s*=\s*"([^"]+)"', html):
            url = match.group(1)
            assert url.startswith("https://") or url.startswith("#"), (
                f"Asset no-self-contained tras redact: {url!r}"
            )

    def test_export_snapshot_propagates_redact_to_disk(
        self, minimal_project: Path, tmp_path: Path
    ) -> None:
        """End-to-end: pasar redact al export_snapshot escribe HTML redacted."""
        out = tmp_path / "shared.html"
        export_snapshot(minimal_project, out, redact=True)
        content = out.read_text(encoding="utf-8")
        assert "SECRETO_AMO" not in content
        assert "versión compartible" in content

