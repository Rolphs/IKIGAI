"""
ikigai.auditor — El linter de sentido.
Analiza la brecha entre la materia prima (tulipan.jsonl) y la síntesis (YAML).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ikigai import intersection_concepts
from ikigai.algebra_state import load_algebra_state
from ikigai.cuadrantes import positive_csv_values


@dataclass
class AuditGap:
    key: str           # e.g. "1,2"
    label: str         # e.g. "Gusto ∩ Habilidad"
    items_count: int
    has_concept: bool
    type: str          # "unnamed" (tiene items, no nombre) | "ghost" (tiene nombre, no items)


@dataclass
class ZenAuditReport:
    total_items: int
    untagged_items_count: int
    coverage_pct: float
    gaps: list[AuditGap]
    synthesis_pct: float  # % de intersecciones con items que ya tienen nombre


def run_audit(project_dir: Path) -> ZenAuditReport:
    # items_by_cuad no se usa aqui; el audit razona sobre primitive_sets
    # (8 cuadrantes como conjuntos de IDs) e items_by_id (lookup por ID).
    _items_by_cuad, primitive_sets, items_by_id, universe = load_algebra_state(project_dir)

    personal_names = intersection_concepts.load_personal_names_for(project_dir)

    # 1. Items sin tags (en el aire)
    untagged = [it for it in items_by_id.values() if not it.assigned_circles()]

    # 2. Analizar las 15 regiones posibles (4 primitivas + 11 intersecciones)
    positives = set(positive_csv_values())
    positive_tag_sets = {k: v for k, v in primitive_sets.items() if k in positives}
    all_intersections = intersection_concepts.compute_all_intersections(
        positive_tag_sets, items_by_id, personal_names
    )

    gaps = []
    named_count = 0
    relevant_regions = 0

    for card in all_intersections:
        key = str(card["key"])
        count = int(card["count"])
        has_name = bool(card["personal_name"])

        if count > 0:
            relevant_regions += 1
            if has_name:
                named_count += 1
            else:
                gaps.append(AuditGap(
                    key=key,
                    label=str(card["label"]),
                    items_count=count,
                    has_concept=False,
                    type="unnamed"
                ))
        elif has_name:
            # Concepto acuñado pero ya no hay items que lo respalden
            gaps.append(AuditGap(
                key=key,
                label=str(card["label"]),
                items_count=0,
                has_concept=True,
                type="ghost"
            ))

    coverage = ((len(universe) - len(untagged)) / len(universe) * 100) if universe else 0
    synthesis = (named_count / relevant_regions * 100) if relevant_regions else 0

    return ZenAuditReport(
        total_items=len(universe),
        untagged_items_count=len(untagged),
        coverage_pct=coverage,
        gaps=gaps,
        synthesis_pct=synthesis
    )
