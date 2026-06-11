"""
ikigai — Tulipan de Ikigai como reporte HTML interactivo y app local.

Pipeline actual (single source of truth):
  1. tulipan.jsonl              — items crudos (un Item por linea, append-only).
  2. visualizations/default.yaml — los 4 circulos del Venn de Ikigai.
  3. intersection_concepts.yaml  — nombres personales acuñados por el usuario
                                   para cada interseccion (la "salida creativa").

Filosofia: separation of concerns. Cada archivo cambia a un ritmo distinto.
El JSONL crece muy seguido; el yaml de viz casi nunca; los concepts a un
ritmo intermedio (a medida que el usuario nombra cosas).
"""
from importlib.metadata import PackageNotFoundError, version

# El distribution name (en pyproject.toml) es "ikigai-tulipan" para evitar
# colision con otro paquete homonimo en PyPI.
# El Python module sigue siendo `ikigai` (zero impact en imports).
# Version cerrada del proyecto (single source of truth a nivel codigo). Debe
# coincidir con la de pyproject.toml. Se usa como fallback si la metadata del
# paquete no esta disponible (checkout sin instalar, o editable installs que
# no exponen la version via importlib.metadata).
_FALLBACK_VERSION = "3.1.0"

try:
    __version__ = version("ikigai-tulipan") or _FALLBACK_VERSION
except PackageNotFoundError:
    __version__ = _FALLBACK_VERSION
