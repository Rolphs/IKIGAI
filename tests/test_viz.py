"""Tests del feature de visualizacion dinamica (v0.3.0+ slim).

Tras el refactor "una fuente de verdad":
  - Visualization solo guarda framing (categories order + summary)
  - Concepts viven en intersection_concepts.yaml (compartido con /sintesis)
  - Evidence se DERIVA del CSV en runtime
  - Single-viz: no mas multi-viz CRUD ni rename/delete

Cobertura:
  - region_keys / region_to_csv_values (helpers puros)
  - Storage slim (formato YAML sin regions)
  - viz_lock concurrencia
  - Endpoints HTTP del visualizador
  - SINGLE SOURCE OF TRUTH cross-pantalla (el test mas importante)
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from ikigai import intersection_concepts
from ikigai.routers.visualizador import derive_region_views
from ikigai.viz_models import Visualization, region_keys, region_to_csv_values
from ikigai.viz_storage import load_visualization, save_visualization, viz_lock
from tests.conftest import make_client


# ─── viz_models: pure helpers ────────────────────────────────────────────
class TestRegionKeys:
    def test_n2(self) -> None:
        assert region_keys(2) == ["a", "b", "ab"]

    def test_n3(self) -> None:
        assert region_keys(3) == ["a", "b", "c", "ab", "ac", "bc", "abc"]

    def test_n4_count(self) -> None:
        # 2^4 - 1 = 15 regiones no vacias (Ikigai clasico completo)
        assert len(region_keys(4)) == 15

    def test_n4_keys(self) -> None:
        # primera region single y ultima full-intersection bien formadas
        assert region_keys(4)[0] == "a"
        assert region_keys(4)[-1] == "abcd"

    def test_n1(self) -> None:
        assert region_keys(1) == ["a"]

    def test_n0(self) -> None:
        # "solo universo": sin circulos, sin regiones internas
        assert region_keys(0) == []

    def test_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            region_keys(-1)
        with pytest.raises(ValueError):
            region_keys(5)


class TestRegionToCsvValues:
    """region_to_csv_values traduce letras Venn (a,b,c,d) a csv_values segun
    el orden de categories. Es el corazon del mapeo posicional<->semantico."""

    def test_single_letter(self) -> None:
        assert region_to_csv_values("a", ["1", "2", "3", "4"]) == ["1"]
        assert region_to_csv_values("c", ["1", "2", "3", "4"]) == ["3"]

    def test_intersection(self) -> None:
        assert region_to_csv_values("ab", ["1", "2", "3", "4"]) == ["1", "2"]
        assert region_to_csv_values("abcd", ["1", "2", "3", "4"]) == ["1", "2", "3", "4"]

    def test_respects_categories_order(self) -> None:
        # Si reordenas, las letras mapean distinto
        assert region_to_csv_values("a", ["3", "1", "2", "4"]) == ["3"]
        assert region_to_csv_values("ab", ["3", "1", "2", "4"]) == ["3", "1"]

    def test_out_returns_empty(self) -> None:
        # "out" es complemento, no mapea a csv_values
        assert region_to_csv_values("out", ["1", "2", "3", "4"]) == []

    def test_letters_beyond_categories_skipped(self) -> None:
        # Si pides region "abc" pero solo hay 2 categories, c se ignora
        assert region_to_csv_values("abc", ["1", "2"]) == ["1", "2"]


# ─── Storage slim ────────────────────────────────────────────────────────
class TestStorageSlim:
    def test_load_nonexistent_returns_defaults(self, tmp_path: Path) -> None:
        v = load_visualization(tmp_path, "default")
        assert v.name == "default"
        assert v.categories == ["1", "2", "3", "4"]
        assert v.summary == ""
        assert v.title  # algun titulo

    def test_save_and_reload_roundtrip(self, tmp_path: Path) -> None:
        v = Visualization(
            name="default",
            title="My Viz",
            categories=["3", "1", "2", "4"],
            summary="resumen macro",
        )
        save_visualization(tmp_path, v)
        v2 = load_visualization(tmp_path, "default")
        assert v2.categories == ["3", "1", "2", "4"]
        assert v2.title == "My Viz"
        assert v2.summary == "resumen macro"

    def test_save_does_not_persist_regions(self, tmp_path: Path) -> None:
        """Formato slim: el YAML NO debe contener 'regions'."""
        v = Visualization(name="default", title="X", categories=["1", "2"])
        path = save_visualization(tmp_path, v)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "regions" not in raw, "El formato slim NO guarda regions[]"
        assert set(raw.keys()) == {"name", "title", "categories", "summary"}

    def test_save_is_atomic_no_tmp_file_left(self, tmp_path: Path) -> None:
        v = Visualization(name="default", title="X", categories=["1"])
        save_visualization(tmp_path, v)
        leftover = list((tmp_path / "visualizations").glob("*.tmp"))
        assert leftover == []

    def test_viz_lock_serializes_concurrent_writes(self, tmp_path: Path) -> None:
        import threading

        save_visualization(tmp_path, Visualization(name="default", title="r"))
        results: list[Exception | None] = []

        def writer(idx: int) -> None:
            try:
                with viz_lock("default"):
                    v = load_visualization(tmp_path, "default")
                    v.summary = f"writer-{idx}"
                    save_visualization(tmp_path, v)
                results.append(None)
            except Exception as e:
                results.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert all(r is None for r in results)
        v_final = load_visualization(tmp_path, "default")
        assert v_final.summary.startswith("writer-")


# ─── derive_region_views: la funcion CENTRAL del refactor ────────────────
@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """Proyecto minimo con 4 items en distintos tags + concepts pre-cargados.

    Vive como subdir 'test' del workspace tmp para que la fixture `client`
    pueda usarlo bajo el prefix /u/test/* del refactor multi-ikigai.
    """
    from ikigai import jsonl_store
    from ikigai.models import Item
    pdir = tmp_path / "test"
    pdir.mkdir()
    p = pdir / "tulipan.jsonl"
    jsonl_store.append(p, Item(id="1.001", item="Item solo amo", cuadrante="1",
                               tag_amo="1"))
    jsonl_store.append(p, Item(id="2.001", item="Item solo bueno", cuadrante="2",
                               tag_bueno="1"))
    jsonl_store.append(p, Item(id="12.001", item="Item amo+bueno", cuadrante="1",
                               tag_amo="1", tag_bueno="1"))
    jsonl_store.append(p, Item(id="1b.001", item="Item negativo", cuadrante="1b"))
    # NOTA: la viz lee tags via items_by_tag(csv_value), que mira las columnas
    # tag_amo/bueno/mundo/pago (no 'cuadrante'). 'cuadrante' solo identifica
    # el origen del item; el bucket Venn lo determina el tag_*.
    return pdir


class TestDeriveRegionViews:
    def _items_path(self, project_dir: Path) -> Path:
        return project_dir / "tulipan.jsonl"

    def test_evidence_derives_items_with_matching_tag(self, project_dir: Path) -> None:
        v = Visualization(name="default", title="X", categories=["1", "2"])
        views = derive_region_views(v, self._items_path(project_dir))
        # Region 'a' (=csv "1") debe traer los items con cuadrante=1
        ids_a = views["a"]["evidence"]
        assert "1.001" in ids_a
        assert "12.001" in ids_a  # tambien va en a (es cuadrante=1)

    def test_out_contains_items_with_no_active_tag(self, project_dir: Path) -> None:
        """'out' debe contener items que NO tienen ninguno de los csv_values
        activos. Con categories=['1','2'], el item 1b.001 (cuadrante=1b) cae fuera."""
        v = Visualization(name="default", title="X", categories=["1", "2"])
        views = derive_region_views(v, self._items_path(project_dir))
        assert "1b.001" in views["out"]["evidence"]

    def test_concept_reads_from_intersection_concepts(self, project_dir: Path) -> None:
        # Pre-cargo un nombre personal en /sintesis
        yaml_path = intersection_concepts.yaml_path_for(project_dir)
        intersection_concepts.save_personal_name(yaml_path, "1", "Mi Pasion")
        v = Visualization(name="default", title="X", categories=["1", "2"])
        views = derive_region_views(v, self._items_path(project_dir))
        assert views["a"]["concept"] == "Mi Pasion"

    def test_concept_for_missing_key_is_empty(self, project_dir: Path) -> None:
        v = Visualization(name="default", title="X", categories=["1", "2"])
        views = derive_region_views(v, self._items_path(project_dir))
        assert views["ab"]["concept"] == ""

    def test_out_region_has_empty_concept(self, project_dir: Path) -> None:
        """'out' nunca tiene concept (no es una interseccion)."""
        v = Visualization(name="default", title="X", categories=["1", "2"])
        views = derive_region_views(v, self._items_path(project_dir))
        assert views["out"]["concept"] == ""


# ─── Server endpoints ──────────────────────────────────────────
@pytest.fixture()
def client(project_dir: Path):
    return make_client(project_dir)


class TestVisualizadorEndpoints:
    def test_get_renders(self, client: TestClient) -> None:
        r = client.get("/visualizador")
        assert r.status_code == 200
        assert "Visualizador" in r.text or "visualizador" in r.text

    def test_data_endpoint_returns_derived_regions(self, client: TestClient) -> None:
        r = client.get("/visualizador/data")
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data
        assert "regions" in data
        assert "out" in data["regions"]
        # Con default categories [1,2,3,4] hay 15 regiones internas + "out"
        assert len(data["regions"]) == 16

    def test_set_categories_persists_and_returns_them(
        self, client: TestClient, project_dir: Path
    ) -> None:
        r = client.post("/visualizador/categories", data={"categories": "3,1,2,4"})
        assert r.status_code == 200
        assert r.json()["categories"] == ["3", "1", "2", "4"]
        v = load_visualization(project_dir, "default")
        assert v.categories == ["3", "1", "2", "4"]

    def test_set_categories_rejects_too_many(self, client: TestClient) -> None:
        r = client.post(
            "/visualizador/categories", data={"categories": "1,2,3,4,1b"}
        )
        assert r.status_code == 400

    def test_set_categories_accepts_single(self, client: TestClient) -> None:
        r = client.post("/visualizador/categories", data={"categories": "1"})
        assert r.status_code == 200

    def test_set_categories_accepts_empty(self, client: TestClient) -> None:
        r = client.post("/visualizador/categories", data={"categories": ""})
        assert r.status_code == 200

    def test_set_categories_rejects_unknown_value(self, client: TestClient) -> None:
        r = client.post(
            "/visualizador/categories", data={"categories": "1,zzz"}
        )
        assert r.status_code == 400

    def test_set_region_concept_writes_to_shared_yaml(
        self, client: TestClient, project_dir: Path
    ) -> None:
        """El POST de concept escribe en intersection_concepts.yaml, NO en default.yaml."""
        client.post("/visualizador/categories", data={"categories": "1,2,3,4"})
        r = client.post(
            "/visualizador/region/ab/concept",
            data={"concept": "Mi Pasion personal"},
        )
        assert r.status_code == 200
        # Aparece en el yaml compartido
        names = intersection_concepts.load_personal_names(
            intersection_concepts.yaml_path_for(project_dir)
        )
        assert names["1,2"] == "Mi Pasion personal"
        # NO aparece en default.yaml (formato slim)
        raw = yaml.safe_load(
            (project_dir / "visualizations" / "default.yaml").read_text(encoding="utf-8")
        )
        assert "regions" not in raw

    def test_set_region_concept_rejects_out(self, client: TestClient) -> None:
        """'out' no es una interseccion, no debe aceptarse."""
        r = client.post(
            "/visualizador/region/out/concept", data={"concept": "x"}
        )
        assert r.status_code == 400

    def test_set_region_concept_rejects_invalid_key(self, client: TestClient) -> None:
        r = client.post(
            "/visualizador/region/zzz/concept", data={"concept": "x"}
        )
        assert r.status_code == 404


# ─── SINGLE SOURCE OF TRUTH (el test mas importante del refactor) ────────
class TestSingleSourceOfTruth:
    """Garantiza que /sintesis y /visualizador comparten state real, no copias.

    El sintoma original que motivo el refactor: 'llene cosas en /sintesis y
    /visualizador aparece vacio'. Estos tests aseguran que NUNCA vuelva.
    """

    def test_sintesis_concept_visible_in_visualizador(
        self, client: TestClient
    ) -> None:
        """Escribo en /sintesis, leo en /visualizador, debe estar."""
        client.post(
            "/sintesis/concept",
            data={"key": "1,2", "personal_name": "Pasion compartida"},
        )
        data = client.get("/visualizador/data").json()
        assert data["regions"]["ab"]["concept"] == "Pasion compartida"

    def test_visualizador_concept_visible_in_sintesis(
        self, client: TestClient
    ) -> None:
        """Escribo en /visualizador, /sintesis muestra el mismo nombre."""
        client.post(
            "/visualizador/region/ab/concept",
            data={"concept": "Sintesis viz"},
        )
        r = client.get("/sintesis")
        assert r.status_code == 200
        assert "Sintesis viz" in r.text

    def test_csv_items_appear_in_visualizador_evidence(
        self, client: TestClient, project_dir: Path
    ) -> None:
        """Items del CSV aparecen en la region correspondiente sin tener que
        arrastrarlos manualmente (auto-derivacion)."""
        data = client.get("/visualizador/data").json()
        # Item 1.001 (cuadrante=1) debe estar en region 'a'
        assert "1.001" in data["regions"]["a"]["evidence"]

    def test_categories_reorder_remaps_regions_but_preserves_concepts(
        self, client: TestClient
    ) -> None:
        """Si reordeno categories, la region 'a' apunta a otro csv_value PERO
        el concepto sigue ligado al csv_value original (no a la letra). Es decir:
        el nombre acuñado para "csv=1" sigue siendo el mismo, solo se renderiza
        en otra letra Venn."""
        # 1. Nombro la interseccion csv "1,2"
        client.post(
            "/sintesis/concept", data={"key": "1,2", "personal_name": "X12"}
        )
        # 2. Con categories=[1,2,3,4], region "ab" = csv "1,2" -> X12
        client.post("/visualizador/categories", data={"categories": "1,2,3,4"})
        data1 = client.get("/visualizador/data").json()
        assert data1["regions"]["ab"]["concept"] == "X12"
        # 3. Reordeno a [2,1,3,4]: ahora region "ab" sigue siendo csv "1,2"
        #    (porque concept_key ordena alfabeticamente; key del yaml="1,2"
        #    sigue siendo la misma).
        client.post("/visualizador/categories", data={"categories": "2,1,3,4"})
        data2 = client.get("/visualizador/data").json()
        assert data2["regions"]["ab"]["concept"] == "X12", \
            "El concept debe seguir siendo X12 (la interseccion semantica no cambio)"


# ─── Summary autosave ────────────────────────────────────────────────────
class TestVizSummary:
    def test_summary_starts_empty_and_persists(self, client: TestClient) -> None:
        d = client.get("/visualizador/data").json()
        assert d["summary"] == ""
        r = client.patch(
            "/visualizador/summary",
            data={"summary": "Mi insight macro: coherencia total."},
        )
        assert r.status_code == 200
        assert r.json()["summary"].startswith("Mi insight macro")
        d2 = client.get("/visualizador/data").json()
        assert d2["summary"].startswith("Mi insight macro")

    def test_summary_strips_whitespace(self, client: TestClient) -> None:
        client.patch("/visualizador/summary", data={"summary": "   hola   "})
        d = client.get("/visualizador/data").json()
        assert d["summary"] == "hola"

    def test_html_renders_summary_box(self, client: TestClient) -> None:
        r = client.get("/visualizador")
        assert r.status_code == 200
        assert 'id="viz-summary"' in r.text


# ─────────────────────────────────────────────────────────────────────
# Regresion del MOTOR GEOMETRICO (viz_geometry.js)
#
# El frontend JS no tiene runner (no Node en CI). Estos tests portan la
# geometria critica a Python para blindar un bug real: con step=3, las
# regiones-astilla podian captar UNA sola muestra -> hitbox de radio minimo
# en un punto -> fragil/inclickeable. El fix bajo SAMPLE_STEP a 2. Si
# alguien lo vuelve a subir, estos tests (y el tripwire del JS) lo atrapan.
#
# Las shapes de abajo ESPEJAN vennGeometry(n) en viz_geometry.js. Si cambian
# alla, cambian aca (estan documentadas como espejo, no es DRY-violation
# accidental: es un golden de geometria con su fuente anotada).
# ─────────────────────────────────────────────────────────────────────
import math  # noqa: E402
from itertools import combinations  # noqa: E402

_LETTERS = "abcd"


def _venn_shapes(n: int):
    """Espejo de vennGeometry(n).shapes + viewBox (viz_geometry.js)."""
    if n == 2:
        return [("c", 170, 100, 110), ("c", 310, 100, 110)], (-100, -120, 600, 380)
    if n == 3:
        return [
            ("c", 240, 120, 120), ("c", 160, 260, 120), ("c", 320, 260, 120),
        ], (-100, -50, 600, 480)
    if n == 4:
        cx, cy, rx, ry = 240, 240, 170, 90
        return [
            ("e", cx - 30, cy - 20, rx, ry, -45),
            ("e", cx + 30, cy + 20, rx, ry, -45),
            ("e", cx + 30, cy - 20, rx, ry, 45),
            ("e", cx - 30, cy + 20, rx, ry, 45),
        ], (-60, -20, 600, 540)
    raise ValueError(n)


def _point_in_shape(x: float, y: float, s) -> bool:
    """Espejo de pointInShape (viz_geometry.js)."""
    if s[0] == "c":
        _, cx, cy, r = s
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
    _, cx, cy, rx, ry, rot = s
    t = -rot * math.pi / 180.0
    dx, dy = x - cx, y - cy
    px = dx * math.cos(t) - dy * math.sin(t)
    py = dx * math.sin(t) + dy * math.cos(t)
    return (px * px) / (rx * rx) + (py * py) / (ry * ry) <= 1.0


def _region_key_at(x: float, y: float, shapes) -> str:
    return "".join(
        _LETTERS[i] for i, s in enumerate(shapes) if _point_in_shape(x, y, s)
    )


def _sample_counts(n: int, step: int) -> dict[str, int]:
    """Espejo de computeRegionGeometry: muestras por region."""
    shapes, (mnx, mny, w, h) = _venn_shapes(n)
    counts: dict[str, int] = {}
    y = mny
    while y <= mny + h:
        x = mnx
        while x <= mnx + w:
            k = _region_key_at(x, y, shapes)
            if k:
                counts[k] = counts.get(k, 0) + 1
            x += step
        y += step
    return counts


SAMPLE_STEP = 2  # DEBE coincidir con `const step` en viz_geometry.js


class TestVennGeometryRegression:
    @pytest.mark.parametrize("n", [2, 3, 4])
    def test_every_region_has_a_hitbox(self, n: int) -> None:
        """Toda region que el backend genera debe ser muestreada (clickeable)."""
        expected = {
            "".join(c)
            for size in range(1, n + 1)
            for c in combinations(_LETTERS[:n], size)
        }
        sampled = set(_sample_counts(n, SAMPLE_STEP))
        missing = expected - sampled
        assert not missing, f"N={n}: regiones sin hitbox (inclickeables): {missing}"

    def test_n4_thinnest_region_is_robust(self) -> None:
        """La region mas chica de N=4 no debe ser de 1-2 muestras.

        Umbral conservador (>=5) para detectar regresiones de robustez.
        """
        counts = _sample_counts(4, SAMPLE_STEP)
        expected = {
            "".join(c)
            for size in range(1, 5)
            for c in combinations(_LETTERS, size)
        }
        worst = min(counts[k] for k in expected)
        assert worst >= 5, f"region mas fragil de N=4 tiene {worst} muestras (<5)"

    def test_js_step_matches_expectation(self) -> None:
        """Tripwire: el SAMPLE_STEP real en viz_geometry.js sigue siendo 2.

        Si alguien lo sube "para optimizar", este test recuerda el porque.
        """
        js = (
            Path(__file__).resolve().parents[1]
            / "ikigai" / "static" / "viz" / "viz_geometry.js"
        ).read_text(encoding="utf-8")
        assert "const step = 2;" in js, (
            "viz_geometry.js cambio su sampling step; re-audita la robustez "
            "de las regiones chicas antes de actualizar SAMPLE_STEP aqui"
        )
