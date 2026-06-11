"""workspace.py - Registro de ikigais en una carpeta-raiz.

Convencion: un workspace es un directorio que contiene SUBDIRECTORIOS,
uno por ikigai. Cada subdir es un project_dir valido (tiene
`visualizations/default.yaml` o se asume vacio).

Layout tipico:
    ~/ikigai_workspace/
        mariana/
            tulipan.jsonl
            visualizations/default.yaml
            ...
        juan/
            tulipan.jsonl
            visualizations/default.yaml
            ...

Esta es la fuente de verdad para "que ikigais existen y cual estoy viendo".
Los routers consultan `list_ikigais(workspace)` para popular el dropdown
y `resolve_project_dir(workspace, name)` para servir requests.

CONVENCION DE NAMING:
    - El "name" es el nombre del subdirectorio (slug). Debe ser
      filesystem-safe: solo [a-z0-9_-], minusculas, sin espacios.
    - El "title" es el viz.title (libre, puede ser "Mariana Lopez 🌷").
    - El dropdown muestra el title; los URLs usan el name.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ikigai.viz_storage import load_visualization, viz_path

# Slug filesystem-safe: minusculas, numeros, guion, underscore. 1-50 chars.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,49}$")
_MAX_SLUG_LEN = 50

# Slugs que chocarian con rutas del server (o reservados por convencion).
# `_new` ya queda excluido por el regex (no se permite empezar con "_").
RESERVED_SLUGS: frozenset[str] = frozenset({"u", "static", "docs", "redoc"})


@dataclass(frozen=True)
class IkigaiInfo:
    """Resumen de un ikigai para popular dropdowns y listings."""

    name: str       # slug del subdirectorio, ej. "mariana"
    title: str      # viz.title libre, ej. "Mariana Lopez 🌷"
    project_dir: Path  # path absoluto al subdir


def is_valid_name(name: str) -> bool:
    """True si `name` es un slug filesystem-safe.

    Reglas: [a-z0-9_-]{1,50}, debe empezar con [a-zcon guion).
    Reservamos nombres que empiezan con "_" para uso interno del server.
    """
    return bool(_SLUG_RE.match(name))


def slugify(text: str) -> str:
    """Convierte un nombre libre en un slug filesystem/URL-safe.

    Pipeline: normaliza unicode (acentos -> ASCII), pasa a minusculas,
    reemplaza cualquier cosa que no sea [a-z0-9] por guion, colapsa guiones
    repetidos, recorta guiones de los bordes y trunca a 50 chars (sin dejar
    un guion colgando al final).

    Puede devolver "" si `text` no tiene ningun caracter slugificable
    (ej. solo emojis o simbolos). El caller decide el fallback; usa
    `derive_unique_slug` que ya lo maneja.

        slugify("Maria Lopez (Ingeniera)")  -> "maria-lopez-ingeniera"
        slugify("Maria Lopez")               -> "maria-lopez"  (acento->a)
        slugify("   ")                        -> ""
    """
    # NFKD separa los acentos en combining marks; los borramos (Mn).
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_text = ascii_text.lower()
    # Todo lo no-alfanumerico -> guion, luego colapsar y trim.
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    if len(slug) > _MAX_SLUG_LEN:
        slug = slug[:_MAX_SLUG_LEN].rstrip("-")
    return slug


def derive_unique_slug(workspace_root: Path, text: str) -> str:
    """Deriva un slug valido y UNICO para `text` dentro del workspace.

    - Slugifica `text`. Si queda vacio (solo emojis/simbolos), usa "ikigai".
    - Si choca con un slug reservado o con un ikigai existente, sufija
      `-2`, `-3`, ... hasta encontrar uno libre (respetando el largo max).

    Garantiza que el resultado pasa `is_valid_name` y no colisiona.
    """
    base = slugify(text) or "ikigai"
    existing = {info.name for info in list_ikigais(workspace_root)}
    taken = existing | RESERVED_SLUGS

    if base not in taken:
        return base

    # Sufijar -N hasta encontrar hueco. Recorta la base si el sufijo la
    # empujaria mas alla del largo maximo.
    n = 2
    while True:
        suffix = f"-{n}"
        trimmed = base[: _MAX_SLUG_LEN - len(suffix)].rstrip("-")
        candidate = f"{trimmed}{suffix}"
        if candidate not in taken:
            return candidate
        n += 1


def list_ikigais(workspace_root: Path) -> list[IkigaiInfo]:
    """Escanea workspace_root y devuelve los ikigais encontrados.

    Filtra: directorios cuyo nombre es slug-valido. NO requiere que tengan
    default.yaml todavia (un ikigai recien creado purlo). El
    title se infiere del viz si existe; si no, se cae al name capitalizado.

    Ordenado por title alfabetico para que el dropdown sea estable.
    """
    if not workspace_root.exists():
        return []

    out: list[IkigaiInfo] = []
    for entry in sorted(workspace_root.iterdir()):
        if not entry.is_dir():
            continue
        if not is_valid_name(entry.name):
            continue
        # Intenta leer el title del default.yaml. Si no existe, usa el name.
        if viz_path(entry).exists():
            viz = load_visualization(entry)
            title = viz.title or entry.name.title()
        else:
            title = entry.name.title()
        out.append(IkigaiInfo(name=entry.name, title=title, project_dir=entry))

    out.sort(key=lambda i: i.title.lower())
    return out


def resolve_project_dir(workspace_root: Path, name: str) -> Path:
    """Devuelve workspace_root/name si es valido y existe; else raises.

    No crea el directorio; solo resuelve. Usado por _get_deps en cada
    request HTTP.
    """
    if not is_valid_name(name):
        raise ValueError(f"Nombre de ikigai invalido: {name!r}")
    project_dir = workspace_root / name
    if not project_dir.exists():
        raise FileNotFoundError(f"Ikigai no encontrado: {name!r}")
    if not project_dir.is_dir():
        raise NotADirectoryError(f"{project_dir} no es un directorio")
    return project_dir


def create_ikigai(
    workspace_root: Path, title: str, slug: str | None = None
) -> Path:
    """Crea un nuevo ikigai a partir de un nombre amigable.

    - `title`: el nombre libre que ve el usuario (ej. "Maria Lopez ").
      Puede tener mayusculas, acentos, emojis. Requerido (no vacio).
    - `slug`: override opcional (modo avanzado). Si se omite, se DERIVA
      automaticamente del title via `derive_unique_slug` (slugify + manejo
      de colision/vacio/reservados). Si se da, debe ser un slug valido,
      no reservado y libre.

    Crea el subdir <workspace>/<slug>/ + tulipan.jsonl vacio +
    visualizations/default.yaml con el title. Devuelve el path al nuevo
    project_dir (su `.name` es el slug final).
    """
    title = title.strip()
    if not title:
        raise ValueError("El nombre del ikigai no puede estar vacio.")

    if slug is None:
        slug = derive_unique_slug(workspace_root, title)
    else:
        slug = slug.strip()
        if not is_valid_name(slug):
            raise ValueError(
                f"Slug invalido: {slug!r}. Usa minusculas, numeros, guion o "
                f"underscore (1-50 chars, no empieces con guion)."
            )
        if slug in RESERVED_SLUGS:
            raise ValueError(f"Slug reservado: {slug!r}. Elige otro.")

    project_dir = workspace_root / slug
    if project_dir.exists():
        raise FileExistsError(f"Ya existe un ikigai con slug {slug!r}")

    workspace_root.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir()
    # Seed: tulipan.jsonl vacio (los items se agregan via UI).
    (project_dir / "tulipan.jsonl").touch()
    # Seed: default.yaml con el title amigable.
    from ikigai.viz_models import Visualization
    from ikigai.viz_storage import save_visualization

    viz = Visualization(name="default", title=title)
    save_visualization(project_dir, viz)
    return project_dir
