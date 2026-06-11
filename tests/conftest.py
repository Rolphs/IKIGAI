"""conftest.py - Fixtures compartidas y helpers para tests.

PROBLEMA: tras el refactor multi-ikigai, las rutas viven bajo /u/{name}/...
Reescribir las ~120+ URLs de los tests existentes seria muy invasivo.

SOLUCION: `PrefixedTestClient` envuelve un TestClient y prepende /u/{name}
automaticamente a cualquier path que parezca una ruta del ikigai. Asi los
tests existentes (que pasan `/inventario`, `/sintesis`, etc.) siguen
funcionando sin cambios.

Las rutas que NO se prefijan:
    - /static/*       (assets globales)
    - /_new           (workspace-level)
    - /u/...          (ya esta prefijado, no doble-prefijo)
    - /openapi.json, /docs, /redoc (FastAPI built-ins)
    - / (root)
"""
from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

# Slug del ikigai test que vive bajo el workspace temp. Coincide con
# el nombre del subdir que crean los fixtures de cada test_*.py.
TEST_IKIGAI_NAME = "test"

_PASSTHROUGH_PREFIXES = (
    "/static/",
    "/_new",
    "/u/",
    "/openapi.json",
    "/docs",
    "/redoc",
)


def _munge_url(path: str, prefix: str) -> str:
    """Prepende `prefix` a `path` salvo que ya sea workspace-level.

    Asume paths absolutos (que empiezan con /). Si no, devuelve sin tocar.
    """
    if not path.startswith("/"):
        return path
    if path == "/":
        return path
    for skip in _PASSTHROUGH_PREFIXES:
        if path.startswith(skip):
            return path
    return prefix + path


class PrefixedTestClient:
    """Wrapper de TestClient que prefija URLs con /u/{name} automaticamente.

    Permite que los tests legacy (escritos antes del refactor multi-ikigai)
    sigan funcionando sin cambios masivos. Forwarding via __getattr__ para
    cubrir cualquier metodo HTTP que se le agregue al TestClient.
    """

    def __init__(self, inner: TestClient, ikigai_name: str = TEST_IKIGAI_NAME) -> None:
        self._inner = inner
        self._prefix = f"/u/{ikigai_name}"

    # Metodos HTTP comunes — explicitos para autocomplete y type-checking.
    def get(self, url: str, **kw: Any) -> Any:
        return self._inner.get(_munge_url(url, self._prefix), **kw)

    def post(self, url: str, **kw: Any) -> Any:
        return self._inner.post(_munge_url(url, self._prefix), **kw)

    def patch(self, url: str, **kw: Any) -> Any:
        return self._inner.patch(_munge_url(url, self._prefix), **kw)

    def delete(self, url: str, **kw: Any) -> Any:
        return self._inner.delete(_munge_url(url, self._prefix), **kw)

    def put(self, url: str, **kw: Any) -> Any:
        return self._inner.put(_munge_url(url, self._prefix), **kw)

    def __getattr__(self, name: str) -> Any:
        # Fallback para otros attrs (e.g. app, base_url, headers).
        return getattr(self._inner, name)


def make_client(project_dir: Any) -> PrefixedTestClient:
    """Helper de DRY para tests: dado un project_dir directo, crea un workspace
    sintetico (project_dir.parent) y un PrefixedTestClient apuntando al subdir.

    Convencion: el fixture crea `project_dir = tmp_path / TEST_IKIGAI_NAME`.
    """
    from ikigai.server import create_app

    workspace = project_dir.parent
    name = project_dir.name
    inner = TestClient(create_app(workspace))
    return PrefixedTestClient(inner, ikigai_name=name)
