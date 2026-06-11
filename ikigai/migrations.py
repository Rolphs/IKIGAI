"""Migraciones one-shot de formatos viejos.

Toda BREAKING change de formato deja un usuario potencialmente con data
vieja. Este modulo es donde viven esas migraciones — UNA sola pasada al
abrir el proyecto, idempotente, no destructiva, con backup del original.

Las migraciones activas hoy:

  v0.4: tulipan.csv -> tulipan.jsonl
    Disparador: existe tulipan.csv pero no tulipan.jsonl.
    Accion: import via portability.import_csv_text, rename csv -> csv.bak.

  v0.3: viz YAML con `regions[].concept` -> intersection_concepts.yaml
    Disparador: visualizations/*.yaml contiene un campo `regions:` con
    sub-campos `concept:` o `personal_name:` (formato pre-v0.3).
    Accion: extrae los concepts y los inyecta en intersection_concepts.yaml,
    SOLO si la key no esta ya presente (no destructivo). El viz YAML queda
    intacto — los campos `regions:` los ignora silenciosamente
    load_visualization, asi que no estorban. Asi evitamos modificar data
    del usuario solo por leerla.

Las llamadas viven en create_app() (web app) y cli.export() (snapshot).
Cero costo cuando no hay nada que migrar (un solo Path.exists()).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ikigai import intersection_concepts, portability
from ikigai.algebra_state import JSONL_NAME


def migrate_legacy_csv_to_jsonl(project_dir: Path) -> str | None:
    """Convierte tulipan.csv a tulipan.jsonl si aplica. Idempotente.

    Devuelve un mensaje describiendo la accion, o None si no hizo nada.
    Si el CSV existe pero es invalido (cuadrantes raros, ids duplicados),
    propaga CsvImportError sin tocar el disco — mejor fallar ruidosamente
    que dejar al usuario con un JSONL vacio sin saberlo.
    """
    jsonl_path = project_dir / JSONL_NAME
    csv_path = project_dir / "tulipan.csv"

    if jsonl_path.exists():
        return None  # ya migrado, o nunca fue legacy
    if not csv_path.exists():
        return None  # proyecto nuevo, sin nada que migrar

    text = csv_path.read_text(encoding="utf-8")
    n = portability.import_csv_text(jsonl_path, text)
    backup_path = csv_path.with_suffix(".csv.bak")
    csv_path.rename(backup_path)
    return (
        f"Migrado: {csv_path.name} ({n} items) -> {jsonl_path.name}. "
        f"Original respaldado como {backup_path.name}."
    )


def migrate_legacy_viz_concepts(project_dir: Path) -> str | None:
    """Extrae concepts viejos de visualizations/*.yaml a intersection_concepts.yaml.

    Pre-v0.3, los nombres acuñados por region vivian dentro del YAML de
    cada visualizacion como `regions: [..., {key: '1,2', concept: 'Pasion'}]`
    o `regions: {'1,2': {concept: 'Pasion'}}`. v0.3 los movio a un
    archivo compartido (intersection_concepts.yaml).

    Esta funcion escanea visualizations/*.yaml, extrae los `concept:` (o
    `personal_name:`) encontrados, y los inserta en intersection_concepts.yaml
    SOLO para keys que aun no existan ahi. No modifica los YAML viejos —
    sus campos `regions:` son inofensivos para el codigo actual.

    Devuelve mensaje describiendo cuantos concepts migro, o None si no hubo
    nada que migrar.
    """
    viz_dir = project_dir / "visualizations"
    if not viz_dir.is_dir():
        return None

    legacy_pairs = _collect_legacy_concept_pairs(viz_dir)
    if not legacy_pairs:
        return None

    yaml_path = intersection_concepts.yaml_path_for(project_dir)
    existing = intersection_concepts.load_personal_names(yaml_path)
    inserted = 0
    for key, name in legacy_pairs.items():
        if key in existing:
            continue  # no destructivo: el usuario ya acuño algo, lo respetamos
        intersection_concepts.save_personal_name(yaml_path, key, name)
        inserted += 1

    if inserted == 0:
        return None
    return (
        f"Migrado: {inserted} concepts desde visualizations/*.yaml legacy "
        f"-> {yaml_path.name}."
    )


def _collect_legacy_concept_pairs(viz_dir: Path) -> dict[str, str]:
    """Lee todos los YAML del directorio y devuelve {key: concept_text}.

    Tolerante a dos formatos historicos:
      regions: [{key: '1,2', concept: 'X'}, ...]   # lista de dicts
      regions: {'1,2': {concept: 'X'}, ...}        # dict de dicts
    Y a dos nombres de campo equivalentes: `concept` y `personal_name`.
    """
    pairs: dict[str, str] = {}
    for path in sorted(viz_dir.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue  # YAML corrupto: skip silencioso (no es nuestro trabajo arreglarlo aqui)
        regions = raw.get("regions")
        if isinstance(regions, list):
            for entry in regions:
                _maybe_collect(entry, key_field="key", into=pairs)
        elif isinstance(regions, dict):
            for k, entry in regions.items():
                _maybe_collect(entry, key_field=None, default_key=str(k), into=pairs)
    return pairs


def _maybe_collect(
    entry: Any,
    *,
    key_field: str | None,
    into: dict[str, str],
    default_key: str | None = None,
) -> None:
    if not isinstance(entry, dict):
        return
    key = entry.get(key_field) if key_field else default_key
    if not isinstance(key, str) or not key:
        return
    # `concept` es el nombre v0.2; `personal_name` lo usaron algunos forks.
    concept = entry.get("concept") or entry.get("personal_name")
    if not isinstance(concept, str):
        return
    stripped = concept.strip()
    if not stripped:
        return
    # Primer hit gana: si dos viz tienen el mismo key con concepts distintos,
    # ganarse el orden alfabetico de los YAML es predecible y suficiente.
    into.setdefault(key, stripped)


def migrate_all_if_needed(project_dir: Path) -> list[str]:
    """Corre todas las migraciones aplicables. Devuelve log de acciones.

    Esta es la API publica del modulo — los callers (create_app, cli.export)
    solo necesitan invocarla y opcionalmente loguear las strings devueltas.
    """
    messages: list[str] = []
    for migrator in (migrate_legacy_csv_to_jsonl, migrate_legacy_viz_concepts):
        msg = migrator(project_dir)
        if msg:
            messages.append(msg)
    return messages
