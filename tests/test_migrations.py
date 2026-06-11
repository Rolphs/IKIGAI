"""Tests de migraciones one-shot (CSV->JSONL, viz legacy->intersection_concepts)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ikigai import intersection_concepts, migrations

# ─── CSV -> JSONL ─────────────────────────────────────────────────────────


def _write_csv(path: Path, rows: list[str]) -> None:
    header = "id,item,cuadrante\n"
    path.write_text(header + "".join(r + "\n" for r in rows), encoding="utf-8")


class TestMigrateLegacyCsvToJsonl:
    def test_noop_when_jsonl_already_exists(self, tmp_path: Path) -> None:
        (tmp_path / "tulipan.jsonl").write_text("", encoding="utf-8")
        _write_csv(tmp_path / "tulipan.csv", ["1.001,algo,1"])
        msg = migrations.migrate_legacy_csv_to_jsonl(tmp_path)
        assert msg is None
        # El csv NO se debe haber renombrado (el jsonl manda).
        assert (tmp_path / "tulipan.csv").exists()
        assert not (tmp_path / "tulipan.csv.bak").exists()

    def test_noop_when_neither_file_exists(self, tmp_path: Path) -> None:
        msg = migrations.migrate_legacy_csv_to_jsonl(tmp_path)
        assert msg is None

    def test_migrates_csv_creates_jsonl_renames_backup(self, tmp_path: Path) -> None:
        _write_csv(
            tmp_path / "tulipan.csv",
            ["1.001,Caminar,1", "1.002,Pensar,1", "3.001,Solo mundo,3"],
        )
        msg = migrations.migrate_legacy_csv_to_jsonl(tmp_path)
        assert msg is not None
        assert "3 items" in msg
        # JSONL existe con 3 lineas.
        jsonl_lines = (tmp_path / "tulipan.jsonl").read_text(
            encoding="utf-8"
        ).strip().splitlines()
        assert len(jsonl_lines) == 3
        # Original respaldado, no eliminado.
        assert not (tmp_path / "tulipan.csv").exists()
        assert (tmp_path / "tulipan.csv.bak").exists()

    def test_is_idempotent_when_run_twice(self, tmp_path: Path) -> None:
        _write_csv(tmp_path / "tulipan.csv", ["1.001,X,1"])
        first = migrations.migrate_legacy_csv_to_jsonl(tmp_path)
        second = migrations.migrate_legacy_csv_to_jsonl(tmp_path)
        assert first is not None
        assert second is None  # segunda vez no hay nada que migrar

    def test_invalid_csv_propagates_error_without_touching_disk(
        self, tmp_path: Path
    ) -> None:
        # Cuadrante invalido: el import debe fallar y NO renombrar el csv.
        _write_csv(tmp_path / "tulipan.csv", ["1.001,X,99"])
        from ikigai.portability import CsvImportError
        with pytest.raises(CsvImportError):
            migrations.migrate_legacy_csv_to_jsonl(tmp_path)
        # Original intacto, sin backup.
        assert (tmp_path / "tulipan.csv").exists()
        assert not (tmp_path / "tulipan.csv.bak").exists()


# ─── viz legacy -> intersection_concepts.yaml ─────────────────────────────


def _write_legacy_viz(viz_dir: Path, name: str, payload: dict[str, object]) -> None:
    viz_dir.mkdir(parents=True, exist_ok=True)
    (viz_dir / f"{name}.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
    )


class TestMigrateLegacyVizConcepts:
    def test_noop_when_viz_dir_missing(self, tmp_path: Path) -> None:
        assert migrations.migrate_legacy_viz_concepts(tmp_path) is None

    def test_noop_when_no_yaml_has_regions(self, tmp_path: Path) -> None:
        _write_legacy_viz(
            tmp_path / "visualizations", "default",
            {"name": "default", "categories": ["1", "2", "3", "4"]},
        )
        assert migrations.migrate_legacy_viz_concepts(tmp_path) is None

    def test_extracts_concepts_from_list_format(self, tmp_path: Path) -> None:
        # Formato v0.2.x version-A: regions como lista de dicts con `key`.
        _write_legacy_viz(
            tmp_path / "visualizations", "default",
            {
                "name": "default",
                "regions": [
                    {"key": "1,2", "concept": "Pasion"},
                    {"key": "1,3", "concept": "Vocacion"},
                ],
            },
        )
        msg = migrations.migrate_legacy_viz_concepts(tmp_path)
        assert msg is not None
        assert "2 concepts" in msg
        names = intersection_concepts.load_personal_names(
            intersection_concepts.yaml_path_for(tmp_path)
        )
        assert names == {"1,2": "Pasion", "1,3": "Vocacion"}

    def test_extracts_concepts_from_dict_format(self, tmp_path: Path) -> None:
        # Formato v0.2.x version-B: regions como dict {key: {concept: ...}}.
        _write_legacy_viz(
            tmp_path / "visualizations", "default",
            {
                "name": "default",
                "regions": {
                    "1,2": {"concept": "Pasion"},
                    "1,2,3,4": {"concept": "Ikigai"},
                },
            },
        )
        msg = migrations.migrate_legacy_viz_concepts(tmp_path)
        assert msg is not None
        names = intersection_concepts.load_personal_names(
            intersection_concepts.yaml_path_for(tmp_path)
        )
        assert names == {"1,2": "Pasion", "1,2,3,4": "Ikigai"}

    def test_accepts_personal_name_field_as_alias_for_concept(
        self, tmp_path: Path
    ) -> None:
        # Algunos forks usaron personal_name en vez de concept.
        _write_legacy_viz(
            tmp_path / "visualizations", "default",
            {"regions": [{"key": "1,2", "personal_name": "Mi pasion"}]},
        )
        migrations.migrate_legacy_viz_concepts(tmp_path)
        names = intersection_concepts.load_personal_names(
            intersection_concepts.yaml_path_for(tmp_path)
        )
        assert names == {"1,2": "Mi pasion"}

    def test_does_not_overwrite_existing_concepts(self, tmp_path: Path) -> None:
        # Esta es la garantia de no-destructividad: si el usuario ya acuño
        # algo en v0.3+, la migracion de un YAML legacy no le pisa el cambio.
        ic_path = intersection_concepts.yaml_path_for(tmp_path)
        intersection_concepts.save_personal_name(ic_path, "1,2", "Pasion v0.3 (la buena)")
        _write_legacy_viz(
            tmp_path / "visualizations", "default",
            {"regions": [{"key": "1,2", "concept": "Pasion v0.2 (vieja)"}]},
        )
        msg = migrations.migrate_legacy_viz_concepts(tmp_path)
        assert msg is None  # 0 insertados, no devuelve mensaje
        names = intersection_concepts.load_personal_names(ic_path)
        assert names == {"1,2": "Pasion v0.3 (la buena)"}

    def test_does_not_modify_the_legacy_yaml(self, tmp_path: Path) -> None:
        # Leer no debe escribir. El YAML viejo queda intacto.
        viz_path = tmp_path / "visualizations" / "default.yaml"
        _write_legacy_viz(
            tmp_path / "visualizations", "default",
            {"regions": [{"key": "1,2", "concept": "X"}]},
        )
        original = viz_path.read_text(encoding="utf-8")
        migrations.migrate_legacy_viz_concepts(tmp_path)
        assert viz_path.read_text(encoding="utf-8") == original

    def test_ignores_corrupted_yaml_without_crashing(self, tmp_path: Path) -> None:
        viz_dir = tmp_path / "visualizations"
        viz_dir.mkdir()
        (viz_dir / "broken.yaml").write_text("{{{not yaml", encoding="utf-8")
        # No debe explotar. Otros YAMLs validos deberian seguir migrandose.
        _write_legacy_viz(viz_dir, "good", {"regions": [{"key": "1,2", "concept": "OK"}]})
        msg = migrations.migrate_legacy_viz_concepts(tmp_path)
        assert msg is not None
        names = intersection_concepts.load_personal_names(
            intersection_concepts.yaml_path_for(tmp_path)
        )
        assert names == {"1,2": "OK"}


# ─── Orquestador ──────────────────────────────────────────────────────────


class TestMigrateAllIfNeeded:
    def test_returns_empty_list_for_clean_project(self, tmp_path: Path) -> None:
        assert migrations.migrate_all_if_needed(tmp_path) == []

    def test_runs_both_migrations_when_applicable(self, tmp_path: Path) -> None:
        _write_csv(tmp_path / "tulipan.csv", ["1.001,X,1"])
        _write_legacy_viz(
            tmp_path / "visualizations", "default",
            {"regions": [{"key": "1,2", "concept": "Pasion"}]},
        )
        messages = migrations.migrate_all_if_needed(tmp_path)
        assert len(messages) == 2
        assert any("tulipan.csv" in m for m in messages)
        assert any("concepts" in m for m in messages)
