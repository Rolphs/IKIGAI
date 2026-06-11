"""
algebra.py — Algebra de conjuntos sobre los cuadrantes del inventario.

Como cada item vive en EXACTAMENTE UN cuadrante (campo `cuadrante` del
tulipan.jsonl), los 8 conjuntos
primitivos (1, 1b, 2, 2b, 3, 3b, 4, 4b) son disjuntos por construccion y
forman una particion del universo U.

Eso hace que las intersecciones primitivas (|Ci ∩ Cj|) sean siempre 0 para
i ≠ j. La riqueza algebraica vive en las EXPRESIONES DERIVADAS:

  Positivos       = 1 ∪ 2 ∪ 3 ∪ 4
  Pasion total    = 1 ∪ 1b
  Monetizable     = 4
  Pasion sin paga = (1 ∪ 2) \\ (3 ∪ 4)
  etc.

Y en las metricas de similitud (Jaccard, Dice, overlap) entre cualquier
par de subconjuntos de U.

Este modulo expone:
  - Operaciones puras: union, intersection, diff, sym_diff, complement
  - Metricas: jaccard
  - Parser/evaluador de expresiones tipo "1 ∪ (2 ∩ ¬3)"
  - Notacion dual (teoria de conjuntos + algebra de boole)
  - Presets de expresiones utiles

NO sabe nada de HTTP, FastAPI ni renderizado. Funciones puras y testeables.
"""
from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from dataclasses import dataclass

ItemId = str
ItemSet = frozenset[ItemId]


# ─── Operaciones puras ──────────────────────────────────────────────────────
# Wrappers tipados sobre las operaciones nativas de frozenset. No agregan nada
# funcional pero documentan la intencion y dan un punto de extension futuro
# (logging, telemetria, etc.) sin tocar callers.

def union(*sets: ItemSet) -> ItemSet:
    """A ∪ B ∪ ... — items en al menos uno de los conjuntos."""
    if not sets:
        return frozenset()
    result = set(sets[0])
    for s in sets[1:]:
        result |= s
    return frozenset(result)


def intersection(*sets: ItemSet) -> ItemSet:
    """A ∩ B ∩ ... — items en TODOS los conjuntos."""
    if not sets:
        return frozenset()
    result = set(sets[0])
    for s in sets[1:]:
        result &= s
    return frozenset(result)


def diff(a: ItemSet, b: ItemSet) -> ItemSet:
    """A \\ B — items en A pero NO en B."""
    return frozenset(a - b)


def sym_diff(a: ItemSet, b: ItemSet) -> ItemSet:
    """A △ B — items en exactamente uno (XOR)."""
    return frozenset(a ^ b)


def complement(a: ItemSet, universe: ItemSet) -> ItemSet:
    """¬A = U \\ A — items del universo que NO estan en A."""
    return frozenset(universe - a)


# ─── Metricas de similitud ──────────────────────────────────────────────────
# Devuelven 0.0 cuando no se puede dividir (ambos vacios) — convencion comun.

def jaccard(a: ItemSet, b: ItemSet) -> float:
    """|A ∩ B| / |A ∪ B| — similitud de Jaccard. Rango [0, 1]."""
    u = union(a, b)
    if not u:
        return 0.0
    return len(intersection(a, b)) / len(u)


# ─── Notacion dual ──────────────────────────────────────────────────────────
# Cada operador tiene un simbolo en teoria de conjuntos y otro en algebra de
# boole. Mostramos ambos para que el usuario aprenda la equivalencia.

@dataclass(frozen=True, slots=True)
class DualNotation:
    """Una expresion renderizada en ambas notaciones."""

    set_theory: str   # "A ∪ B"
    boolean: str      # "A + B"


_SET_OPS: dict[type[ast.operator] | type[ast.unaryop], str] = {
    ast.BitOr: "∪",
    ast.BitAnd: "∩",
    ast.Sub: "\\",
    ast.BitXor: "△",
    ast.Invert: "¬",
}

_BOOL_OPS: dict[type[ast.operator] | type[ast.unaryop], str] = {
    ast.BitOr: "+",
    ast.BitAnd: "·",
    ast.Sub: "-",       # A - B  (en boolean tambien se ve como A·¬B; preferimos A-B por brevedad)
    ast.BitXor: "⊕",
    ast.Invert: "¬",
}


def _render_node(node: ast.AST, ops: dict[type, str]) -> str:
    """Renderiza un ast.expr a string usando el mapeo de operadores dado."""
    if isinstance(node, ast.Name):
        # Quita el prefijo interno "_c_" si existe; "_universe" → "U"
        if node.id == "_universe":
            return "U"
        if node.id.startswith("_c_"):
            return node.id[3:]
        return node.id
    if isinstance(node, ast.BinOp):
        left = _render_node(node.left, ops)
        right = _render_node(node.right, ops)
        op = ops.get(type(node.op))
        if op is None:
            raise ExpressionError(f"Operador no soportado: {type(node.op).__name__}")
        # Agrega parentesis si los hijos son BinOp de menor precedencia.
        # Heuristica simple: si el hijo es BinOp envuelvo con ().
        if isinstance(node.left, ast.BinOp):
            left = f"({left})"
        if isinstance(node.right, ast.BinOp):
            right = f"({right})"
        return f"{left} {op} {right}"
    if isinstance(node, ast.UnaryOp):
        operand = _render_node(node.operand, ops)
        op = ops.get(type(node.op))
        if op is None:
            raise ExpressionError(f"Operador unario no soportado: {type(node.op).__name__}")
        if isinstance(node.operand, ast.BinOp):
            operand = f"({operand})"
        return f"{op}{operand}"
    raise ExpressionError(f"Nodo no soportado: {type(node).__name__}")


def render_dual(expr: str) -> DualNotation:
    """Renderiza una expresion en ambas notaciones."""
    tree = _parse_to_ast(expr)
    return DualNotation(
        set_theory=_render_node(tree.body, _SET_OPS),
        boolean=_render_node(tree.body, _BOOL_OPS),
    )


# ─── Parser / evaluador ─────────────────────────────────────────────────────
# Estrategia: normalizamos los simbolos unicode al equivalente Python, los
# operandos (cuadrantes "1", "1b", ..., "U") los prefijamos con "_c_" o
# "_universe" para que sean identificadores Python validos, y delegamos a
# ast.parse. Luego validamos que el AST solo contenga nodos permitidos antes
# de evaluar — asi NO hay riesgo de eval() malicioso.

class ExpressionError(ValueError):
    """Error parseando o evaluando una expresion de conjuntos."""


# Mapeo de simbolos unicode a operadores Python. El orden importa:
# "\\" antes de cualquier cosa que pueda chocar.
_SYMBOL_MAP = {
    "∪": "|",
    "∩": "&",
    "\\": "-",
    "△": "^",
    "⊕": "^",      # boolean XOR alias
    "¬": "~",
    "·": "&",      # boolean AND
    # "+" lo dejamos como esta: en Python set, "+" no es valido para sets,
    # pero el ast lo parsea como Add y nosotros lo rechazamos. Asi que para
    # union el usuario debe usar ∪ o |. (Si insistimos en aceptar +, hay que
    # convertirlo aqui — pero "+" es ambiguo con sumas; mejor explicito.)
}

# Match de cuadrante csv_value: digito 1-4 opcionalmente seguido de 'b'.
# (Modelo Ikigai clasico = 4 primitivos. Si en el futuro se agregan mas
# cuadrantes en cuadrantes.py, este regex tambien debe ampliarse.)
_CUADRANTE_RE = re.compile(r"(?<![A-Za-z0-9_])([1-4]b?)(?![A-Za-z0-9_])")
_UNIVERSE_RE = re.compile(r"(?<![A-Za-z0-9_])U(?![A-Za-z0-9_])")


def _normalize(expr: str) -> str:
    """Convierte una expresion en notacion humana a Python-set-compatible."""
    if not expr or not expr.strip():
        raise ExpressionError("Expresion vacia.")
    out = expr
    for sym, py in _SYMBOL_MAP.items():
        out = out.replace(sym, py)
    out = _CUADRANTE_RE.sub(r"_c_\1", out)
    out = _UNIVERSE_RE.sub("_universe", out)
    return out


def _parse_to_ast(expr: str) -> ast.Expression:
    """Parsea a un AST validado. Solo permite operaciones de conjunto."""
    normalized = _normalize(expr)
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as e:
        raise ExpressionError(f"Sintaxis invalida en '{expr}': {e.msg}") from e
    _validate_ast(tree.body)
    return tree


_ALLOWED_BINOPS: tuple[type[ast.operator], ...] = (ast.BitOr, ast.BitAnd, ast.Sub, ast.BitXor)
_ALLOWED_UNARYOPS: tuple[type[ast.unaryop], ...] = (ast.Invert,)


def _validate_ast(node: ast.AST) -> None:
    """Recorre el AST y rechaza cualquier nodo no permitido."""
    if isinstance(node, ast.Name):
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BINOPS):
            raise ExpressionError(
                f"Operador no permitido: {type(node.op).__name__}. "
                "Usa ∪/|, ∩/&, \\/-, △/^."
            )
        _validate_ast(node.left)
        _validate_ast(node.right)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARYOPS):
            raise ExpressionError(
                f"Operador unario no permitido: {type(node.op).__name__}. Usa ¬/~."
            )
        _validate_ast(node.operand)
        return
    raise ExpressionError(
        f"Construccion no permitida en una expresion de conjuntos: {type(node).__name__}"
    )


def evaluate(
    expr: str,
    cuadrantes: Mapping[str, ItemSet],
    universe: ItemSet | None = None,
) -> ItemSet:
    """Evalua una expresion de algebra de conjuntos.

    Args:
      expr: la expresion en notacion humana, ej. "1 ∪ (2 ∩ ¬3b)".
      cuadrantes: mapping csv_value → frozenset de item_ids. Ej. {"1": {...}, "1b": {...}}.
      universe: el conjunto U. Si no se da, se calcula como union(*cuadrantes.values()).

    Returns:
      frozenset[ItemId] con los items que satisfacen la expresion.

    Raises:
      ExpressionError: si la expresion no es valida o usa un operando inexistente.
    """
    tree = _parse_to_ast(expr)
    if universe is None:
        universe = union(*cuadrantes.values())
    namespace: dict[str, ItemSet] = {f"_c_{k}": v for k, v in cuadrantes.items()}
    namespace["_universe"] = universe
    return _eval_node(tree.body, namespace, universe)


def _eval_node(node: ast.AST, ns: dict[str, ItemSet], universe: ItemSet) -> ItemSet:
    """Evalua un nodo del AST. Asume que ya paso _validate_ast."""
    if isinstance(node, ast.Name):
        if node.id not in ns:
            # Limpia el nombre interno para el error
            human = node.id[3:] if node.id.startswith("_c_") else node.id
            raise ExpressionError(f"Operando desconocido: '{human}'.")
        return ns[node.id]
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, ns, universe)
        right = _eval_node(node.right, ns, universe)
        if isinstance(node.op, ast.BitOr):
            return union(left, right)
        if isinstance(node.op, ast.BitAnd):
            return intersection(left, right)
        if isinstance(node.op, ast.Sub):
            return diff(left, right)
        if isinstance(node.op, ast.BitXor):
            return sym_diff(left, right)
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, ns, universe)
        if isinstance(node.op, ast.Invert):
            return complement(operand, universe)
    # Cubierto por _validate_ast, pero por defense in depth:
    raise ExpressionError(f"Nodo no evaluable: {type(node).__name__}")


# ─── Presets de expresiones utiles ──────────────────────────────────────────
# Estos son los "diff cuts" mas comunes del modelo Ikigai extendido. Se
# muestran como cards en la pagina /sintesis para que el usuario tenga puntos
# de entrada interesantes sin tener que escribir expresiones desde cero.

@dataclass(frozen=True, slots=True)
class Preset:
    key: str            # slug estable
    label: str          # nombre para el usuario
    expression: str     # notacion de teoria de conjuntos (canonical)
    description: str    # tooltip / subtitulo


PRESETS: list[Preset] = [
    # ─── Particiones grandes ─────────────────────────────────────────────
    Preset(
        key="positivos",
        label="Todos los positivos",
        expression="1 ∪ 2 ∪ 3 ∪ 4",
        description="Lo que SI: amo, soy bueno, el mundo necesita, me pagarían.",
    ),
    Preset(
        key="negativos",
        label="Todos los negativos (la sombra)",
        expression="1b ∪ 2b ∪ 3b ∪ 4b",
        description="La sombra completa: lo que NO te gusta, NO puedes, NO importa, NO paga.",
    ),
    # ─── Pares por cuadrante ─────────────────────────────────────────────
    Preset(
        key="gusto_total",
        label="Gusto total (+ y −)",
        expression="1 ∪ 1b",
        description="Todo lo emocional: lo que enciende y lo que apaga.",
    ),
    Preset(
        key="habilidad_total",
        label="Habilidad total (+ y −)",
        expression="2 ∪ 2b",
        description="Lo que sabes hacer y lo que querrias pero no puedes.",
    ),
    # ─── Lecturas economicas ─────────────────────────────────────────────
    Preset(
        key="monetizable",
        label="Monetizable",
        expression="4",
        description="Lo que el mercado pagaría.",
    ),
    Preset(
        key="no_monetizable",
        label="No monetizable",
        expression="4b",
        description="Lo que no tiene mercado.",
    ),
    # ─── Diff cuts narrativos ────────────────────────────────────────────
    Preset(
        key="pasion_sin_paga",
        label="Pasion que no paga",
        expression="(1 ∩ 2) \\ 4",
        description="Lo que amas y haces bien, pero nadie te paga (aún). Misión sin mercado.",
    ),
    Preset(
        key="paga_sin_pasion",
        label="Te pagan sin amor",
        expression="4 \\ (1 ∪ 2)",
        description="Lo monetizado que NO esta en tu gusto/habilidad. Sintoma de comodidad miserable.",
    ),
    # ─── Ikigai clásico ─────────────────────────────────────────────
    Preset(
        key="ikigai_centro",
        label="✨ Ikigai (centro)",
        expression="1 ∩ 2 ∩ 3 ∩ 4",
        description="El centro: lo que amas, haces bien, el mundo necesita Y te pagan.",
    ),
]


