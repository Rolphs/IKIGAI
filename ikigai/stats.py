"""Agregaciones tipo chi-cuadrada sobre listas de Items.

Funciones puras sin I/O. Punto de extension natural para:
  - #3 fingerprint por pregunta (esta iteracion)
  - #5 heatmap de residuos (proxima)
  - #6 independencia entre tags / Cramer's V (eventualmente)

Vocabulario:
  - "Circulo" = uno de los 4 csv_values positivos: 1=Amo, 2=Bueno, 3=Mundo, 4=Pago.
  - "Pregunta evocadora" = la pregunta de introspeccion que evoco un item;
    tiene polaridad ('1' positivo, '1b' sombra).
  - "Tag asignado" = lo que el usuario explicitamente marco como pertenencia
    a un circulo. Es la celda *observada* de la tabla de contingencia.
"""
from __future__ import annotations

from ikigai.models import Item

# Los 4 circulos del Ikigai como csv_values positivos. Orden estable para UI.
CIRCLES: tuple[str, ...] = ("1", "2", "3", "4")

CIRCLE_LABELS: dict[str, str] = {
    "1": "Amo",
    "2": "Bueno",
    "3": "Mundo",
    "4": "Pago",
}
CIRCLE_EMOJIS: dict[str, str] = {
    "1": "❤️",
    "2": "💪",
    "3": "🌍",
    "4": "💵",
}

# Mapeo a clases Tailwind del proyecto (paleta del proyecto). Distintos por
# circulo para que el fingerprint sea legible de un vistazo.
CIRCLE_BAR_BG: dict[str, str] = {
    "1": "bg-danger-100",     # Amo (corazon rojo)
    "2": "bg-success-100",   # Bueno (musculo verde)
    "3": "bg-brand-100",    # Mundo (tierra azul)
    "4": "bg-accent-100",   # Pago (dinero spark)
}


def tag_distribution(items: list[Item]) -> dict[str, int]:
    """Cuenta cuantos items estan asignados a cada circulo positivo.

    Un item con N tags cuenta N veces (una por circulo asignado): la pregunta
    es "¿a cuales circulos pertenece este conjunto?", no "¿cuantos items hay?".
    """
    counts: dict[str, int] = {c: 0 for c in CIRCLES}
    for item in items:
        for circle in item.assigned_circles():
            if circle in counts:
                counts[circle] += 1
    return counts


def tag_distribution_pct(items: list[Item]) -> dict[str, float]:
    """tag_distribution normalizada a % sobre el total de assignments.

    Si la lista esta vacia o sin tags, devuelve ceros (no NaN, no error).
    El total puede exceder len(items) cuando hay items multi-tag — eso es
    intencional para que las barras sumen 100%.
    """
    raw = tag_distribution(items)
    total = sum(raw.values())
    if total == 0:
        return {c: 0.0 for c in CIRCLES}
    return {c: 100.0 * v / total for c, v in raw.items()}


def expected_circle_for_evoking_cuadrante(cuadrante_value: str) -> str | None:
    """Para preguntas positivas devuelve el circulo esperado; para sombra, None.

    Ejemplos:
      '1'  → '1'   (pregunta de Amo → circulo Amo esperado)
      '3'  → '3'   (pregunta de Mundo → circulo Mundo esperado)
      '1b' → None  (pregunta de sombra: no hay tag esperado)
      ''   → None
    """
    if not cuadrante_value or cuadrante_value.endswith("b"):
        return None
    return cuadrante_value if cuadrante_value in CIRCLES else None


def section_fingerprint(items: list[Item], evoking_cuadrante: str) -> dict[str, object]:
    """Empaqueta todo lo que el template del fingerprint necesita.

    Devuelve un dict con:
      - distribution_pct:   dict[circle → %] sobre 4 circulos
      - distribution_count: dict[circle → count]
      - total_assignments:  suma de tags activos en esta seccion
      - tagged_items_count: items con al menos 1 tag
      - expected_circle:    csv_value del circulo esperado o None (sombra)
      - has_divergence:     True si la pregunta espera un circulo y NINGUN
                            item de la seccion lo tagueo (señal chi² fuerte)
    """
    counts = tag_distribution(items)
    pct = tag_distribution_pct(items)
    total = sum(counts.values())
    expected = expected_circle_for_evoking_cuadrante(evoking_cuadrante)
    has_divergence = bool(
        expected
        and items
        and counts.get(expected, 0) == 0
    )
    tagged_items_count = sum(1 for it in items if it.assigned_circles())
    return {
        "distribution_pct": pct,
        "distribution_count": counts,
        "total_assignments": total,
        "tagged_items_count": tagged_items_count,
        "expected_circle": expected,
        "has_divergence": has_divergence,
    }
