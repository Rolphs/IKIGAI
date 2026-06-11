"""
tests/test_auditor.py — Pruebas para el linter de sentido (Zen Auditor).
"""
from pathlib import Path

from ikigai import jsonl_store
from ikigai.auditor import run_audit
from ikigai.models import Item


def _write_items(project_dir: Path, items: list[Item], yaml_content: str = "concepts: {}") -> None:
    """Helper: escribe directamente al JSONL (sin pasar por la migracion CSV).

    Usar `write_all` para sembrar batch — los tests no estan
    probando el append incremental.
    """
    jsonl_store.write_all(project_dir / "tulipan.jsonl", items)
    (project_dir / "intersection_concepts.yaml").write_text(yaml_content, encoding="utf-8")


def test_audit_empty_project(tmp_path: Path) -> None:
    _write_items(tmp_path, [])

    report = run_audit(tmp_path)
    assert report.total_items == 0
    assert report.untagged_items_count == 0
    assert report.coverage_pct == 0
    assert report.synthesis_pct == 0
    assert len(report.gaps) == 0


def test_audit_perfect_synthesis(tmp_path: Path) -> None:
    # Un item en C1 (Amo) y esa region nombrada.
    items = [Item(id="1.001", item="Cocinar", cuadrante="1", tag_amo="1")]
    yaml = "concepts:\n  '1': Mi pasion base\n"
    _write_items(tmp_path, items, yaml)

    report = run_audit(tmp_path)
    assert report.total_items == 1
    assert report.untagged_items_count == 0
    assert report.coverage_pct == 100.0
    assert report.synthesis_pct == 100.0
    assert len(report.gaps) == 0


def test_audit_unnamed_gap(tmp_path: Path) -> None:
    # Item en C1, pero sin nombre en el YAML (concepts vacio por default).
    items = [Item(id="1.001", item="Cocinar", cuadrante="1", tag_amo="1")]
    _write_items(tmp_path, items)

    report = run_audit(tmp_path)
    assert report.synthesis_pct == 0.0
    assert len(report.gaps) == 1
    gap = report.gaps[0]
    assert gap.key == "1"
    assert gap.type == "unnamed"
    assert gap.items_count == 1


def test_audit_ghost_concept(tmp_path: Path) -> None:
    # Nombre en YAML para C1, pero C1 esta vacio en el JSONL.
    yaml = "concepts:\n  '1': Fantasma\n"
    _write_items(tmp_path, [], yaml)

    report = run_audit(tmp_path)
    assert len(report.gaps) == 1
    gap = report.gaps[0]
    assert gap.key == "1"
    assert gap.type == "ghost"
    assert gap.items_count == 0


def test_audit_untagged_items(tmp_path: Path) -> None:
    # Item sin tags.
    items = [Item(id="1.001", item="Algo raro", cuadrante="1")]
    _write_items(tmp_path, items)

    report = run_audit(tmp_path)
    assert report.total_items == 1
    assert report.untagged_items_count == 1
    assert report.coverage_pct == 0.0


def test_audit_complex_intersections(tmp_path: Path) -> None:
    # Item en interseccion 1,2 (Pasion).
    items = [Item(id="12.001", item="Disenar", cuadrante="1", tag_amo="1", tag_bueno="1")]
    # Nombramos los primitivos pero NO la interseccion.
    yaml = "concepts:\n  '1': Gusto\n  '2': Habilidad\n"
    _write_items(tmp_path, items, yaml)

    report = run_audit(tmp_path)
    # 3 regiones relevantes: "1", "2" y "1,2". De esas, "1" y "2" estan
    # nombradas, "1,2" no → synthesis_pct = 2/3.
    assert report.synthesis_pct == (2 / 3 * 100)

    unnamed_gaps = [g for g in report.gaps if g.type == "unnamed"]
    assert len(unnamed_gaps) == 1
    assert unnamed_gaps[0].key == "1,2"
