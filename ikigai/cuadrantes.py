"""
Definicion de los 4 primitivos del Ikigai clasico.

Cada primitivo es un "circulo" del Venn y tiene un par (+/-): el positivo es
el peetalo clasico del modelo, el negativo es su sombra/inverso (igual de
informativo y a menudo mas honesto).

IMPORTANTE — naming correcto:
  Los 4 primitivos son DATOS CRUDOS que tu capturas (Gusto, Habilidad,
  Mundo, Mercado). Las palabras "Pasion / Mision / Vocacion / Profesion"
  NO son primitivos: son los nombres de las INTERSECCIONES de 2 primitivos
  (ver intersections.py). Esa colision conceptual era la causa de que
  llenar "Mision" como cuadrante crudo se sintiera ambiguo.

IDs:
  Positivos: "1.NNN", "2.NNN", "3.NNN", "4.NNN"
  Negativos: "1b.NNN", "2b.NNN", "3b.NNN", "4b.NNN"

Mapeo a la literatura clasica:
  1 = L (Love / Gusto)        — "what you love"
  2 = G (Good at / Habilidad) — "what you're good at"
  3 = W (World / Mundo)       — "what the world needs"
  4 = P (Paid / Mercado)      — "what you can be paid for"
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CuadranteSide:
    """Un lado (+ o -) de un primitivo en el inventario."""

    csv_value: str  # id del cuadrante: se guarda en el campo `cuadrante` del tulipan.jsonl (ej. "1" o "1b"). El nombre `csv_value` es un artefacto historico (pre-v0.4 era una columna CSV); NO implica CSV hoy.
    label: str  # texto coloquial al frente del usuario
    emoji: str
    placeholder: str  # ejemplo dentro del input
    color_class: str  # Tailwind class del border / accento
    pregunta_evocativa: str  # para el modo cuestionario / introspección


@dataclass(frozen=True, slots=True)
class CuadrantePair:
    """Una caja del inventario con sus 2 lados."""

    key: str  # slug para URLs (ej. "gusto")
    titulo: str  # encabezado de la caja
    descripcion: str  # subtitulo / ayuda
    pregunta: str  # la pregunta que el cuadrante hace al usuario; items son respuestas
    positivo: CuadranteSide
    negativo: CuadranteSide


# Convenciones:
#   Verde success-100 = positivo, rojo danger-100 = negativo.
#   Si mas adelante quieres agregar/quitar primitivos, edita SOLO este archivo.
CUADRANTES: list[CuadrantePair] = [
    CuadrantePair(
        key="gusto",
        titulo="Gusto",
        descripcion="Lo que enciende o apaga tu energia cuando lo haces (Love).",
        pregunta="¿Qué amas?",
        positivo=CuadranteSide(
            csv_value="1",
            label="Me gusta",
            emoji="❤️",
            placeholder="Ej. construir marcos conceptuales, cocinar tecnica",
            color_class="success-100",
            pregunta_evocativa="Si hoy tuvieras el día libre y todo el dinero del mundo, ¿en qué actividad se te pasarían las horas sin darte cuenta?",
        ),
        negativo=CuadranteSide(
            csv_value="1b",
            label="No me gusta",
            emoji="💔",
            placeholder="Ej. cajas negras, burocracia sin sentido",
            color_class="danger-100",
            pregunta_evocativa="¿Qué es aquello que, aunque te pagaran el triple, te genera una pesadez inmediata solo de pensar en hacerlo?",
        ),
    ),
    CuadrantePair(
        key="habilidad",
        titulo="Habilidad",
        descripcion="Lo que sabes hacer bien vs. lo que querrias y aun no puedes (Good at).",
        pregunta="¿Qué haces bien?",
        positivo=CuadranteSide(
            csv_value="2",
            label="Soy bueno",
            emoji="💪",
            placeholder="Ej. sintetizar dominios, leer patrones invisibles",
            color_class="success-100",
            pregunta_evocativa="¿Qué es eso que para otros es un 'trabajo duro' pero para ti fluye de manera natural, casi sin esfuerzo?",
        ),
        negativo=CuadranteSide(
            csv_value="2b",
            label="Quisiera, pero no puedo",
            emoji="😖",
            placeholder="Ej. ejercer psicologia clinica con titulo",
            color_class="danger-100",
            pregunta_evocativa="¿Qué habilidad ves en otros y sientes una envidia sana (o no tan sana), algo que te encantaría dominar pero sientes que aún no muerdes el anzuelo?",
        ),
    ),
    CuadrantePair(
        key="mundo",
        titulo="Mundo",
        descripcion="Lo que el mundo necesita vs. lo que el mundo NO necesita mas (World needs).",
        pregunta="¿Qué necesita el mundo?",
        positivo=CuadranteSide(
            csv_value="3",
            label="El mundo lo necesita",
            emoji="🌍",
            placeholder="Ej. traductores de complejidad entre silos",
            color_class="success-100",
            pregunta_evocativa="Si pudieras chasquear los dedos y resolver un solo problema del mundo (o de tu comunidad), ¿cuál sería?",
        ),
        negativo=CuadranteSide(
            csv_value="3b",
            label="Al mundo NO le importa",
            emoji="🚫",
            placeholder="Ej. otra consultora boutique igual a las demas",
            color_class="danger-100",
            pregunta_evocativa="¿Qué ruido o tendencia ves en la sociedad actual que te parece una pérdida de tiempo total para la humanidad?",
        ),
    ),
    CuadrantePair(
        key="mercado",
        titulo="Mercado",
        descripcion="Lo que el mercado pagaria vs. lo que no tiene mercado real (Paid for).",
        pregunta="¿Por qué te pagarían?",
        positivo=CuadranteSide(
            csv_value="4",
            label="Me podrian pagar",
            emoji="💵",
            placeholder="Ej. consultoria estrategica con metodologia seria",
            color_class="success-100",
            pregunta_evocativa="¿Por qué tipo de consejo o ayuda la gente suele buscarte y estaría dispuesta a invitarte un café o pagarte una consultoría?",
        ),
        negativo=CuadranteSide(
            csv_value="4b",
            label="No tiene mercado",
            emoji="📉",
            placeholder="Ej. filosofia pura como producto",
            color_class="danger-100",
            pregunta_evocativa="¿Qué talento tuyo es 'puro arte' o hobby personal porque, honestamente, nadie en su sano juicio pagaría por ello hoy?",
        ),
    ),
]


# Lookup auxiliar: csv_value → (pair, side)
def find_side(csv_value: str) -> tuple[CuadrantePair, CuadranteSide] | None:
    """Resuelve un csv_value ('1', '1b', etc.) al par y lado correspondiente."""
    for pair in CUADRANTES:
        if pair.positivo.csv_value == csv_value:
            return pair, pair.positivo
        if pair.negativo.csv_value == csv_value:
            return pair, pair.negativo
    return None


def all_csv_values() -> list[str]:
    """Todos los csv_values válidos, en orden (positivo, negativo) por par.

    Ej. ['1', '1b', '2', '2b', '3', '3b', '4', '4b'].

    FUENTE DE VERDAD: cualquier validación de "¿es un cuadrante válido?" debe
    derivar de aquí, no hardcodear '1234'. Así agregar/quitar un primitivo en
    CUADRANTES se propaga solo (jsonl_store, portability, visualizador, etc.).
    """
    out: list[str] = []
    for pair in CUADRANTES:
        out.extend((pair.positivo.csv_value, pair.negativo.csv_value))
    return out


def positive_csv_values() -> list[str]:
    """Solo los csv_values POSITIVOS, en orden. Ej. ['1', '2', '3', '4'].

    FUENTE DE VERDAD para "los 4 circulos clasicos del Venn". El pipeline de
    naming e intersecciones solo opera sobre positivos (la combinatoria con
    sombras explota la UX). No hardcodear {'1','2','3','4'} en otros modulos:
    derivar de aqui para que agregar/quitar un primitivo se propague solo.
    """
    return [pair.positivo.csv_value for pair in CUADRANTES]


# Set inmutable derivado para validación O(1). NO hardcodear en otros módulos.
VALID_CUADRANTES: frozenset[str] = frozenset(all_csv_values())
