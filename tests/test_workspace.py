"""Tests del workspace: slugify, derive_unique_slug, create_ikigai y los
endpoints del wizard /_new (incluido el preview en vivo del slug).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ikigai.server import create_app
from ikigai.viz_storage import load_visualization
from ikigai.workspace import (
    RESERVED_SLUGS,
    create_ikigai,
    derive_unique_slug,
    is_valid_name,
    list_ikigais,
    slugify,
)

# Emoji tulipan via escape (el hook del workspace filtra emojis literales).
TULIP = "\U0001F337"


# ───────────────────────── slugify ─────────────────────────


class TestSlugify:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("Maria Lopez", "maria-lopez"),
            ("  Maria   Lopez  ", "maria-lopez"),  # colapsa espacios
            ("Maria Lopez (Ingeniera)", "maria-lopez-ingeniera"),
            ("MAYUSCULAS", "mayusculas"),
            ("guion-ya-puesto", "guion-ya-puesto"),
            ("multiples---guiones", "multiples-guiones"),  # colapsa
            ("---bordes---", "bordes"),  # trim de bordes
            ("under_score", "under-score"),  # normaliza separador a guion
            ("123 numeros", "123-numeros"),
        ],
    )
    def test_basic(self, text: str, expected: str) -> None:
        assert slugify(text) == expected

    def test_acentos_a_ascii(self) -> None:
        # Maria con acento, Lopez con acento -> ASCII.
        assert slugify("Mar\u00eda L\u00f3pez") == "maria-lopez"
        assert slugify("ni\u00f1o a\u00f1ejo") == "nino-anejo"  # enie -> n

    def test_solo_emojis_da_vacio(self) -> None:
        assert slugify(TULIP + TULIP) == ""

    def test_solo_simbolos_da_vacio(self) -> None:
        assert slugify("!!! @#$ ...") == ""

    def test_string_vacio(self) -> None:
        assert slugify("") == ""

    def test_trunca_a_50_sin_guion_colgando(self) -> None:
        # 60 chars 'a' separadas para forzar truncado en un borde.
        text = "a" * 48 + " bcdef"
        slug = slugify(text)
        assert len(slug) <= 50
        assert not slug.endswith("-")

    def test_output_siempre_es_slug_valido_o_vacio(self) -> None:
        for text in ["Hola Mundo", "X", "a-b-c", "café con leche"]:
            slug = slugify(text)
            assert slug == "" or is_valid_name(slug)


# ─────────────────── derive_unique_slug ───────────────────


class TestDeriveUniqueSlug:
    def test_sin_colision_devuelve_base(self, tmp_path: Path) -> None:
        assert derive_unique_slug(tmp_path, "Maria Lopez") == "maria-lopez"

    def test_vacio_usa_fallback_ikigai(self, tmp_path: Path) -> None:
        assert derive_unique_slug(tmp_path, TULIP + TULIP) == "ikigai"

    def test_colision_sufija_numero(self, tmp_path: Path) -> None:
        create_ikigai(tmp_path, "Maria Lopez")  # -> maria-lopez
        assert derive_unique_slug(tmp_path, "Maria Lopez") == "maria-lopez-2"

    def test_colision_multiple_incrementa(self, tmp_path: Path) -> None:
        create_ikigai(tmp_path, "Ana")  # ana
        create_ikigai(tmp_path, "Ana")  # ana-2 (slug derivado)
        assert derive_unique_slug(tmp_path, "Ana") == "ana-3"

    def test_reservado_se_sufija(self, tmp_path: Path) -> None:
        # "static" es reservado -> no se puede usar tal cual.
        slug = derive_unique_slug(tmp_path, "static")
        assert slug not in RESERVED_SLUGS
        assert slug == "static-2"

    def test_resultado_siempre_valido(self, tmp_path: Path) -> None:
        create_ikigai(tmp_path, "Test")
        for text in ["Test", "static", TULIP, "Maria Lopez"]:
            assert is_valid_name(derive_unique_slug(tmp_path, text))


# ───────────────────── create_ikigai ─────────────────────


class TestCreateIkigai:
    def test_auto_slug_desde_title(self, tmp_path: Path) -> None:
        pd = create_ikigai(tmp_path, "Maria Lopez")
        assert pd.name == "maria-lopez"
        assert pd.is_dir()
        assert (pd / "tulipan.jsonl").exists()
        # El title amigable se guarda tal cual en el viz.
        assert load_visualization(pd).title == "Maria Lopez"

    def test_title_con_emoji_preservado(self, tmp_path: Path) -> None:
        pd = create_ikigai(tmp_path, "Maria " + TULIP)
        assert pd.name == "maria"  # emoji no entra al slug
        assert load_visualization(pd).title == "Maria " + TULIP

    def test_slug_explicito_avanzado(self, tmp_path: Path) -> None:
        pd = create_ikigai(tmp_path, "Maria Lopez", slug="ml")
        assert pd.name == "ml"
        assert load_visualization(pd).title == "Maria Lopez"

    def test_title_vacio_rechaza(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            create_ikigai(tmp_path, "   ")

    def test_slug_explicito_invalido_rechaza(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            create_ikigai(tmp_path, "Maria", slug="MAYUS")

    def test_slug_explicito_reservado_rechaza(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            create_ikigai(tmp_path, "Maria", slug="static")

    def test_slug_existente_rechaza(self, tmp_path: Path) -> None:
        create_ikigai(tmp_path, "Maria", slug="ml")
        with pytest.raises(FileExistsError):
            create_ikigai(tmp_path, "Otra", slug="ml")

    def test_aparece_en_listing(self, tmp_path: Path) -> None:
        create_ikigai(tmp_path, "Maria Lopez")
        names = {i.name for i in list_ikigais(tmp_path)}
        assert "maria-lopez" in names


# ───────────────── endpoints del wizard ─────────────────


class TestWizardEndpoints:
    def _client(self, tmp_path: Path) -> TestClient:
        return TestClient(create_app(tmp_path))

    def test_get_form(self, tmp_path: Path) -> None:
        r = self._client(tmp_path).get("/_new")
        assert r.status_code == 200
        assert "Nombre del ikigai" in r.text
        assert 'name="name"' in r.text
        assert 'name="slug"' in r.text  # campo avanzado

    def test_health_endpoint(self, tmp_path: Path) -> None:
        # Probe de liveness/readiness para deploys: 200 + {"status": "ok"},
        # sin tocar el workspace (responde aunque no haya ningun ikigai).
        r = self._client(tmp_path).get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_slug_preview(self, tmp_path: Path) -> None:
        r = self._client(tmp_path).get("/_new/slug-preview", params={"name": "Maria Lopez"})
        assert r.status_code == 200
        assert "/u/maria-lopez" in r.text

    def test_slug_preview_vacio(self, tmp_path: Path) -> None:
        r = self._client(tmp_path).get("/_new/slug-preview", params={"name": "  "})
        assert r.status_code == 200
        assert "/u/" not in r.text  # no muestra URL si no hay nombre

    def test_slug_preview_refleja_colision(self, tmp_path: Path) -> None:
        create_ikigai(tmp_path, "Maria Lopez")
        r = self._client(tmp_path).get("/_new/slug-preview", params={"name": "Maria Lopez"})
        assert "/u/maria-lopez-2" in r.text

    def test_post_crea_con_auto_slug(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        r = client.post("/_new", data={"name": "Maria Lopez"}, follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/u/maria-lopez/introspeccion"
        assert (tmp_path / "maria-lopez").is_dir()

    def test_post_con_slug_explicito(self, tmp_path: Path) -> None:
        client = self._client(tmp_path)
        r = client.post(
            "/_new", data={"name": "Maria Lopez", "slug": "ml"}, follow_redirects=False
        )
        assert r.status_code == 303
        assert r.headers["location"] == "/u/ml/introspeccion"

    def test_post_title_vacio_da_400(self, tmp_path: Path) -> None:
        r = self._client(tmp_path).post("/_new", data={"name": "   "})
        assert r.status_code == 400

    def test_post_slug_reservado_da_400(self, tmp_path: Path) -> None:
        r = self._client(tmp_path).post("/_new", data={"name": "X", "slug": "static"})
        assert r.status_code == 400
