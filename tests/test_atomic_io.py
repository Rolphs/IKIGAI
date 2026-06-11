"""Tests del primitivo de I/O atomico (atomic_io)."""
from __future__ import annotations

from pathlib import Path

import pytest

from ikigai.atomic_io import atomic_write_text


class TestAtomicWriteText:
    def test_creates_file_when_missing(self, tmp_path: Path) -> None:
        target = tmp_path / "nuevo.yaml"
        atomic_write_text(target, "hola: mundo\n")
        assert target.read_text(encoding="utf-8") == "hola: mundo\n"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        target = tmp_path / "viejo.yaml"
        target.write_text("antes\n", encoding="utf-8")
        atomic_write_text(target, "despues\n")
        assert target.read_text(encoding="utf-8") == "despues\n"

    def test_creates_parent_directory_if_missing(self, tmp_path: Path) -> None:
        # Esto es defensa para llamadas tipo viz_path() que apuntan a
        # subdirs no creados (visualizations/ por ejemplo).
        target = tmp_path / "subdir" / "deeper" / "x.yaml"
        atomic_write_text(target, "x: 1\n")
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "x: 1\n"

    def test_does_not_leave_tmp_on_success(self, tmp_path: Path) -> None:
        # Higiene: el archivo .tmp se renombra, no debe quedar suelto.
        target = tmp_path / "limpio.yaml"
        atomic_write_text(target, "k: v\n")
        leftovers = list(tmp_path.glob("*.tmp"))
        assert leftovers == []

    def test_preserves_existing_on_simulated_crash_mid_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # El corazon de la garantia atomica: si la escritura al tmp falla
        # ANTES del replace, el archivo destino queda con su contenido
        # original intacto. Esto es lo que protege al usuario de perder
        # su arbol de sintesis cuando el proceso muere a mitad de write.
        target = tmp_path / "critico.yaml"
        target.write_text("ORIGINAL\n", encoding="utf-8")

        # Forzamos un crash en el fsync (justo antes del replace).
        import os as _os

        def fsync_crash(_fd: int) -> None:
            raise OSError("disco lleno simulado")

        monkeypatch.setattr(_os, "fsync", fsync_crash)
        with pytest.raises(OSError, match="disco lleno"):
            atomic_write_text(target, "NUEVO\n")

        # El destino sigue siendo el original.
        assert target.read_text(encoding="utf-8") == "ORIGINAL\n"
        # Y no quedo ningun .tmp huerfano tras el fallo.
        assert list(tmp_path.glob("*.tmp")) == []

    def test_fsync_is_called_for_durability(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # B2: la durabilidad depende de fsync ANTES del replace. Si alguien
        # lo borra "para acelerar", este test lo caza.
        import os as _os

        called: list[int] = []
        real_fsync = _os.fsync

        def spy_fsync(fd: int) -> None:
            called.append(fd)
            real_fsync(fd)

        monkeypatch.setattr(_os, "fsync", spy_fsync)
        atomic_write_text(tmp_path / "durable.yaml", "k: v\n")
        assert called, "atomic_write_text debe llamar os.fsync antes del replace"

    def test_unicode_roundtrip(self, tmp_path: Path) -> None:
        # YAML lleno de emoji/acentos es nuestro caso real (nombres
        # personales tipo "construyo ❤️ con orden"). No debe romper.
        target = tmp_path / "uni.yaml"
        content = "concepts:\n  '1,2': construyo ❤️ con órden 🌷\n"
        atomic_write_text(target, content)
        assert target.read_text(encoding="utf-8") == content
