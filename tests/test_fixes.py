"""test_fixes.py - Cobertura de los endurecimientos post-review.

Cubre:
  - Item.validate() valida el rango de los scores *_1a5
  - El import CSV rechaza scores fuera de rango (antes pasaban)
  - El handler global de errores ESCAPA el mensaje (anti-XSS) y los 4xx
    conservan su status (no los traga el catch-all de 500)
  - Las escrituras concurrentes al store JSONL se serializan (sin IDs
    duplicados ni items perdidos)
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ikigai import jsonl_store
from ikigai.models import Item
from ikigai.portability import CsvImportError, import_csv_text
from ikigai.server import create_app

# ─── Item.validate() ────────────────────────────────────────────────────

class TestItemValidate:
    def test_valid_scores_pass(self) -> None:
        Item(id="1.001", item="x", cuadrante="1", energia_1a5="5").validate()
        Item(id="1.002", item="x", cuadrante="1", energia_1a5="").validate()  # vacio OK

    @pytest.mark.parametrize("bad", ["9", "0", "6", "abc", "1.5", "-1"])
    def test_out_of_range_raises(self, bad: str) -> None:
        item = Item(id="1.003", item="x", cuadrante="1", dominio_1a5=bad)
        with pytest.raises(ValueError, match="dominio_1a5"):
            item.validate()

    def test_construction_itself_never_raises(self) -> None:
        """Cargar de disco NO debe validar: el store es resiliente a propósito."""
        # No lanza aunque el score sea basura — la validación es de borde.
        Item(id="1.004", item="x", cuadrante="1", impacto_1a5="999")


# ─── Import CSV valida scores ────────────────────────────────────────────

_HEADER = (
    "id,item,cuadrante,categoria,tipo,fuente,prioridad,notas,"
    "tag_amo,tag_bueno,tag_mundo,tag_pago,"
    "energia_1a5,dominio_1a5,impacto_1a5,viabilidad_1a5\n"
)


def test_csv_import_rejects_bad_score(tmp_path: Path) -> None:
    bad_csv = _HEADER + "1.001,Algo,1,,,,,,,,,,9,,,\n"  # energia_1a5 = 9
    with pytest.raises(CsvImportError, match="energia_1a5"):
        import_csv_text(tmp_path / "t.jsonl", bad_csv)


def test_csv_import_accepts_valid_score(tmp_path: Path) -> None:
    ok_csv = _HEADER + "1.001,Algo,1,,,,,,,,,,5,,,\n"
    n = import_csv_text(tmp_path / "t.jsonl", ok_csv)
    assert n == 1


# ─── Handler de errores: anti-XSS + passthrough de 4xx ───────────────────

def test_500_handler_escapes_html(tmp_path: Path) -> None:
    """Un mensaje de excepción con HTML debe salir ESCAPADO (no como tags)."""
    app = create_app(tmp_path)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("<script>alert('xss')</script>")

    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/boom")
    assert r.status_code == 500
    assert "<script>alert" not in r.text       # no inyecta tags crudos
    assert "&lt;script&gt;" in r.text           # el texto va escapado


def test_4xx_not_masked_as_500(tmp_path: Path) -> None:
    """Un 404 intencional conserva su status (no cae en el handler de 500)."""
    app = create_app(tmp_path)
    client = TestClient(app)
    r = client.get("/u/no-existe/inventario")
    assert r.status_code == 404


# ─── Concurrencia del store JSONL ────────────────────────────────────────

def test_concurrent_adds_no_dup_ids_no_loss(tmp_path: Path) -> None:
    """N writers en paralelo sobre el MISMO archivo no pierden ni duplican.

    Sin el keyed_lock, dos `add_with_generated_id` que leen el mismo max_seq
    generan el mismo id y un append pisa al otro -> items perdidos o ids
    duplicados. Con el lock, los N items quedan con ids únicos.
    """
    path = tmp_path / "tulipan.jsonl"
    n = 40
    barrier = threading.Barrier(n)  # maximiza el solapamiento real

    def worker(i: int) -> None:
        barrier.wait()
        jsonl_store.add_with_generated_id(path, "1", item=f"item-{i}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    items = jsonl_store.read_all(path)
    ids = [it.id for it in items]
    assert len(items) == n, f"se perdieron items: {len(items)} de {n}"
    assert len(set(ids)) == n, f"ids duplicados: {sorted(ids)}"
