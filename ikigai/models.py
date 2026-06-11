"""
Modelos del dominio. Dataclasses frozen para que el flujo de datos
sea explicito y type-checkable.

Vocabulario actual (single source of truth):
  - Item: una entrada del JSONL — un atributo de la persona.

NOTA HISTORICA: este modulo alguna vez tuvo `Region`, `Universo`, `Circle`,
`CurationEntry`, `AuditReport`, etc. — restos de cuando la app leia un
`universos.yaml` con multiples Venns y un `curation.yaml` con asignaciones
declarativas. Esa arquitectura fue reemplazada por:
  - Una sola visualizacion `default` (ver `viz_models.py`).
  - El "curation" se infiere de los `tag_*` del propio Item.
  - El auditor vive ahora como `ZenAuditReport` en `auditor.py`.
Los simbolos viejos se eliminaron en el refactor a single-viz.
"""
from __future__ import annotations

from dataclasses import dataclass

# Valores aceptados para los campos de score 1-5 (string, por el round-trip CSV).
# "" = sin puntuar. Fuente unica de verdad: la usan el endpoint HTTP y el
# import CSV para no duplicar la regla.
VALID_SCORES: frozenset[str] = frozenset({"", "1", "2", "3", "4", "5"})

# Nombres de los campos de score (terminan en _1a5).
SCORE_FIELDS: tuple[str, ...] = (
    "energia_1a5", "dominio_1a5", "impacto_1a5", "viabilidad_1a5",
)


@dataclass(frozen=True, slots=True)
class Item:
    """Un atributo de la persona, persistido como una linea del JSONL.

    `id` es la primary key (formato `<cuadrante>.<seq>`, ej. `1.001`).
    Todo lo demas es opcional para tolerar inputs minimos (solo id + texto).

    Vocabulario semantico (lente chi²):
      - `cuadrante` (alias semantico: `evoking_cuadrante`) representa
        la pregunta/caja que evoco este item. Incluye polaridad +/-
        (ej. '1' = lado positivo del circulo 1, '1b' = lado sombra).
        Es la columna ESPERADA de la tabla de contingencia 8x4.
      - `tag_amo/bueno/mundo/pago` representan los circulos a los que
        el usuario explicitamente asigno este item. Es la columna
        OBSERVADA. Un item puede pertenecer a 0..4 circulos.
      - La diagonal (esperado == observado) es la senal de alineacion;
        las celdas fuera de la diagonal son la senal de divergencia,
        que en este modelo NO es ruido sino informacion valiosa.
    """

    id: str
    item: str  # el texto que se muestra en el Venn
    cuadrante: str = ""
    categoria: str = ""
    tipo: str = ""
    fuente: str = ""
    prioridad: str = ""
    notas: str = ""

    # Introspeccion V2: tags positivos para ubicar automaticamente el item
    # en un Venn de 4 circulos. Se guardan como strings ("1" / "") por
    # compatibilidad con el round-trip CSV (donde todo es texto).
    tag_amo: str = ""
    tag_bueno: str = ""
    tag_mundo: str = ""
    tag_pago: str = ""
    energia_1a5: str = ""
    dominio_1a5: str = ""
    impacto_1a5: str = ""
    viabilidad_1a5: str = ""

    # ─── Helpers semanticos (lente chi²) ─────────────────────────────
    # Estos metodos NO mutan el item (es frozen). Solo exponen vocabulario.

    @property
    def evoking_cuadrante(self) -> str:
        """Cuadrante de la pregunta que evoco este item, con polaridad.

        Alias semantico de `cuadrante`. Usar este cuando el codigo razone
        sobre 'que pregunta genero este item' (vs. 'donde pertenece').
        """
        return self.cuadrante

    @property
    def evoking_circle(self) -> str:
        """Circulo evocador sin polaridad. Ej. '1b' → '1', '3' → '3'.

        Util para alinear la pregunta evocadora con un tag de los 4 circulos.
        """
        if self.cuadrante.endswith("b"):
            return self.cuadrante[:-1]
        return self.cuadrante

    @property
    def evoking_polarity(self) -> str:
        """'+' si pregunta afirmativa, '-' si pregunta de sombra, '' si desconocido."""
        if not self.cuadrante:
            return ""
        return "-" if self.cuadrante.endswith("b") else "+"

    def assigned_circles(self) -> frozenset[str]:
        """Conjunto de circulos donde el USUARIO asigno este item via tags.

        En vocabulario chi²: la celda 'observada' de la tabla de contingencia.
        Los circulos se devuelven como csv_values del lado positivo: subset
        de {'1', '2', '3', '4'}.
        """
        truthy = {"1", "true", "on", "yes", "si", "sí"}
        circles: set[str] = set()
        for tag_col, csv_val in (
            ("tag_amo", "1"),
            ("tag_bueno", "2"),
            ("tag_mundo", "3"),
            ("tag_pago", "4"),
        ):
            if str(getattr(self, tag_col, "")).strip().lower() in truthy:
                circles.add(csv_val)
        return frozenset(circles)

    @property
    def is_aligned_with_evocation(self) -> bool:
        """True si la pregunta evocadora coincide con algun circulo asignado.

        Es decir, este item cae sobre la 'diagonal' de la tabla 8x4.
        Para preguntas de sombra (polaridad '-') siempre devuelve False:
        no hay tag esperado, son items de complemento por definicion.
        """
        if self.evoking_polarity != "+":
            return False
        return self.evoking_circle in self.assigned_circles()

    # ─── Validacion de invariantes ──────────────────────────────────
    # NO se llama en __post_init__ a proposito: cargar el JSONL debe ser
    # resiliente (un valor raro en disco no debe tumbar todo el store). La
    # validacion se aplica en los BORDES de entrada (endpoint HTTP, import
    # CSV), donde si tiene sentido rechazar input malo con un error claro.

    def validate(self) -> None:
        """Verifica los invariantes del Item. Lanza ValueError si algo no cuadra.

        Hoy valida el rango de los 4 scores (`*_1a5`): cada uno debe ser ""
        (sin puntuar) o un digito '1'..'5'. Pensado para llamarse en los
        bordes de entrada, no al leer de disco.
        """
        for field_name in SCORE_FIELDS:
            value = getattr(self, field_name)
            if value not in VALID_SCORES:
                raise ValueError(
                    f"{field_name} debe estar entre 1 y 5 (o vacio), no {value!r}"
                )
