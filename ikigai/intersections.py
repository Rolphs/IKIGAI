"""
intersections.py — Nombres canonicos del modelo Ikigai clasico (4 primitivos).

El modelo clasico usa 4 dimensiones primitivas (los 4 circulos del Venn):
  1 = L (Love / Gusto)       — "what you love"
  2 = G (Good at / Habilidad) — "what you're good at"
  3 = W (World / Mundo)      — "what the world needs"
  4 = P (Paid / Mercado)     — "what you can be paid for"

Las INTERSECCIONES de 2 primitivos producen las palabras consagradas del
folclore: Pasion, Mision, Profesion, Vocacion. La interseccion total
(L ∩ G ∩ W ∩ P) es el Ikigai (el centro). Las intersecciones de 3 son
"Casi-Ikigai" con UN primitivo faltante — diagnostican que ingrediente
falta para llegar al centro.

Las 6 intersecciones de 2 incluyen 4 canonicas y 2 "diagonales" que el
diagrama-flor del folclore ignora (no aparecen en la imagen tipica del
Ikigai) pero que en un Venn matematico real SI existen.

Este modulo expone una tabla pura de lookup: frozenset({csv_values}) -> Intersection.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Intersection:
    """Un nombre canonico para una region del Venn."""

    name: str           # nombre corto consagrado (ej. "Pasion", "Ikigai")
    tagline: str        # frase corta descriptiva
    warning: str = ""   # si esta interseccion sola (sin las otras) genera un sintoma negativo


# Mapeo csv_value -> letra clasica para documentacion legible
# (NO se usa en el lookup, solo para que un humano lea esto y entienda).
#   1 = L (love)
#   2 = G (good at)
#   3 = W (world needs)
#   4 = P (paid for)
CANONICAL_INTERSECTIONS: dict[frozenset[str], Intersection] = {
    # ─── Intersecciones de 2 circulos (los "diamantes" clasicos) ──────────
    # ── 4 canonicas (las del diagrama-flor tipico del Ikigai) ──
    frozenset({"1", "2"}): Intersection(
        name="Pasion",
        tagline="Lo que amas Y haces bien",
        warning="Satisfecho pero la vida no tiene sentido (no aporta al mundo, no paga)",
    ),
    frozenset({"2", "4"}): Intersection(
        name="Profesion",
        tagline="Lo que haces bien Y te pagan",
        warning="Comodo y miserable (no amas lo que haces, no aporta al mundo)",
    ),
    frozenset({"3", "4"}): Intersection(
        name="Vocacion",
        tagline="Lo que el mundo necesita Y te pagan",
        warning="Contento con incertidumbre (no amas lo que haces, no eres bueno)",
    ),
    frozenset({"1", "3"}): Intersection(
        name="Mision",
        tagline="Lo que amas Y el mundo necesita",
        warning="Pleno pero sin dinero (no te pagan, no eres bueno)",
    ),
    # ── 2 diagonales (el folclore las omite, pero el Venn las tiene) ──
    frozenset({"1", "4"}): Intersection(
        name="Hobby remunerado",
        tagline="Lo que amas Y te pagan, pero no eres bueno ni el mundo lo necesita",
        warning="Suerte de mercado / capricho: insostenible cuando la novedad se acaba",
    ),
    frozenset({"2", "3"}): Intersection(
        name="Servicio voluntario",
        tagline="Lo que haces bien Y el mundo necesita, pero no amas ni te pagan",
        warning="Martirio competente: te quemas regalando algo que no te llena",
    ),
    # ─── El centro ────────────────────────────────────────────────────────
    frozenset({"1", "2", "3", "4"}): Intersection(
        name="Ikigai",
        tagline="El centro: amas, eres bueno, el mundo necesita Y te pagan",
        warning="",  # el centro NO tiene warning, es lo que se busca
    ),
    # ─── Intersecciones de 3 circulos (sin nombre clasico, pero diagnosticas) ─
    # Cada una = "casi Ikigai" con UN circulo faltante.
    frozenset({"2", "3", "4"}): Intersection(
        name="Casi-Ikigai",
        tagline="Bueno + necesario + paga... pero no lo amas",
        warning="Falta: Gusto. Riesgo de burnout aunque sea exitoso.",
    ),
    frozenset({"1", "3", "4"}): Intersection(
        name="Casi-Ikigai",
        tagline="Amas + necesario + paga... pero no eres bueno (aun)",
        warning="Falta: Habilidad. Frustracion por brecha entre ambicion y ejecucion.",
    ),
    frozenset({"1", "2", "4"}): Intersection(
        name="Casi-Ikigai",
        tagline="Amas + bueno + paga... pero al mundo no le importa",
        warning="Falta: Mundo. Exito vacio, sensacion de irrelevancia.",
    ),
    frozenset({"1", "2", "3"}): Intersection(
        name="Casi-Ikigai",
        tagline="Amas + bueno + necesario... pero nadie paga por eso",
        warning="Falta: Mercado. Vocacion sin sustento economico.",
    ),
}


def lookup(csv_values: Iterable[str]) -> Intersection | None:
    """Devuelve la interseccion canonica si los csv_values forman una conocida."""
    return CANONICAL_INTERSECTIONS.get(frozenset(csv_values))


def to_json_dict() -> dict[str, dict[str, str]]:
    """Serializa la tabla a un dict JSON-friendly indexado por csv_values ordenados.

    Las claves son strings "1,2" (ordenadas y joined por coma) para que el JS
    pueda hacer lookup directo despues de ordenar y serializar.
    """
    return {
        ",".join(sorted(keys)): asdict(inter)
        for keys, inter in CANONICAL_INTERSECTIONS.items()
    }
