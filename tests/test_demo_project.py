"""Tests E2E del proyecto demo Mariana (ikigai init --demo).

El demo se ship como package data en ikigai/_demo_data/. Se materializa
en un proyecto-usuario via `ikigai init <dir> --demo`. Si un refactor
rompe el formato (JSONL, YAML, viz schema), o el bootstrap, estos tests
saltan antes de que un usuario pip-install vea pantalla rota.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from ikigai.cli import main as cli_main
from tests.conftest import PrefixedTestClient, make_client


@pytest.fixture(scope="module")
def demo_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Bootstrapea un workspace demo via `ikigai init --demo` y devuelve
    el path al SUBDIR del ikigai mariana adentro del workspace.

    Tras el refactor multi-ikigai, `init --demo` crea un workspace y planta
    el demo como subdir 'mariana'. Asi que demo_project = workspace/mariana.
    """
    workspace = tmp_path_factory.mktemp("demo_workspace")
    runner = CliRunner()
    result = runner.invoke(cli_main, ["init", str(workspace), "--demo"])
    assert result.exit_code == 0, f"init --demo fallo:\n{result.output}"
    return workspace / "mariana"


@pytest.fixture(scope="module")
def demo_client(demo_project: Path) -> PrefixedTestClient:
    # make_client(project_dir) toma project_dir.parent como workspace y
    # project_dir.name (= 'mariana') como ikigai_name del prefix.
    return make_client(demo_project)


class TestInitDemoBootstrap:
    def test_init_demo_creates_jsonl(self, demo_project: Path) -> None:
        assert (demo_project / "tulipan.jsonl").exists()
        assert (demo_project / "tulipan.jsonl").stat().st_size > 1_000

    def test_init_demo_creates_concepts(self, demo_project: Path) -> None:
        concepts = demo_project / "intersection_concepts.yaml"
        assert concepts.exists()
        body = concepts.read_text(encoding="utf-8")
        assert "lo-que-me-llena" in body
        assert "diseñar-claridad-para-otros" in body

    def test_init_demo_creates_visualization(self, demo_project: Path) -> None:
        viz = demo_project / "visualizations" / "default.yaml"
        assert viz.exists()

    def test_init_demo_aborts_if_nonempty(self, tmp_path: Path) -> None:
        existing = tmp_path / "squatted"
        existing.mkdir()
        (existing / "something.txt").write_text("hi")
        runner = CliRunner()
        result = runner.invoke(cli_main, ["init", str(existing), "--demo"])
        assert result.exit_code != 0
        assert "no esta vacio" in result.output


class TestDemoProjectBoots:
    @pytest.mark.parametrize(
        "path",
        ["/introspeccion", "/inventario", "/sintesis", "/visualizador"],
    )
    def test_page_renders(self, demo_client: TestClient, path: str) -> None:
        r = demo_client.get(path)
        assert r.status_code == 200, f"{path} fallo con {r.status_code}"

    def test_root_redirects(self, demo_client: TestClient) -> None:
        r = demo_client.get("/", follow_redirects=False)
        assert r.status_code in (301, 302, 307, 308)


class TestDemoHasCompleteIkigai:
    """El valor pedagogico demo es mostrar un Ikigai COMPLETO."""

    def test_sintesis_renders_all_acunados(self, demo_client: TestClient) -> None:
        r = demo_client.get("/sintesis")
        body = r.text
        for personal_name in [
            "lo-que-me-llena",                # primitivo (capa 0)
            "pasion-domesticada",           # par canonico (capa 1)
            "hobby-rentable",                  # diagonal (capa 1)
            "vocacion-sin-pago",               # casi-ikigai (capa 2)
            "diseñar-claridad-para-otros",    # centro (capa 3)
        ]:
            assert personal_name in body, f"demo perdio el concept '{personal_name}'"

    def test_visualizador_shows_princepts(self, demo_client: TestClient) -> None:
        r = demo_client.get("/visualizador")
        body = r.text
        for primitive in (
            "lo-que-me-llena",
            "lo-que-fluye",
            "lo-que-falta-al-mundo",
            "lo-que-paga-cuentas",
        ):
            assert primitive in body, f"demo perdio el primitive '{primitive}'"


class TestDemoExportSnapshot:
    def test_export_generates_snapshot(self, demo_project: Path, tmp_path: Path) -> None:
        from ikigai.export import export_snapshot

        out = tmp_path / "demo-snapshot.html"
        written = export_snapshot(demo_project, out)
        assert written.exists()
        assert written.stat().st_size > 10_000
        body = written.read_text(encoding="utf-8")
        assert "diseñar-claridad-para-otros" in body
