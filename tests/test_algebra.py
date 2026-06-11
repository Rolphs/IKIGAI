"""Tests para ikigai.algebra — operaciones de conjuntos, metricas, parser, presets."""
from __future__ import annotations

import pytest

from ikigai import algebra
from ikigai.algebra import (
    PRESETS,
    DualNotation,
    ExpressionError,
    complement,
    diff,
    evaluate,
    intersection,
    jaccard,
    render_dual,
    sym_diff,
    union,
)

# ─── Fixtures ───────────────────────────────────────────────────────────────
# Universo chico pero suficiente para todos los casos. Cada item pertenece a
# UN cuadrante (modelo disjunto del CSV real).

@pytest.fixture
def cuadrantes() -> dict[str, frozenset[str]]:
    return {
        "1":  frozenset({"1.001", "1.002", "1.003"}),       # Gusto +
        "1b": frozenset({"1b.001", "1b.002"}),               # Gusto -
        "2":  frozenset({"2.001", "2.002"}),                 # Habilidad +
        "2b": frozenset(),                                    # vacio a proposito
        "3":  frozenset({"3.001"}),                          # Mundo +
        "3b": frozenset({"3b.001"}),                         # Mundo -
        "4":  frozenset({"4.001", "4.002"}),                 # Mercado +
        "4b": frozenset({"4b.001"}),                         # Mercado -
    }


@pytest.fixture
def universe(cuadrantes: dict[str, frozenset[str]]) -> frozenset[str]:
    return union(*cuadrantes.values())


# ─── Operaciones puras ──────────────────────────────────────────────────────

class TestUnion:
    def test_zero_args_returns_empty(self) -> None:
        assert union() == frozenset()

    def test_one_arg_returns_copy(self) -> None:
        a = frozenset({"x", "y"})
        assert union(a) == a

    def test_two_disjoint(self) -> None:
        a, b = frozenset({"x"}), frozenset({"y"})
        assert union(a, b) == frozenset({"x", "y"})

    def test_two_overlapping(self) -> None:
        a, b = frozenset({"x", "y"}), frozenset({"y", "z"})
        assert union(a, b) == frozenset({"x", "y", "z"})

    def test_many(self) -> None:
        sets = [frozenset({str(i)}) for i in range(5)]
        assert union(*sets) == frozenset({"0", "1", "2", "3", "4"})


class TestIntersection:
    def test_zero_args(self) -> None:
        assert intersection() == frozenset()

    def test_disjoint_returns_empty(self) -> None:
        a, b = frozenset({"x"}), frozenset({"y"})
        assert intersection(a, b) == frozenset()

    def test_overlapping(self) -> None:
        a, b = frozenset({"x", "y"}), frozenset({"y", "z"})
        assert intersection(a, b) == frozenset({"y"})

    def test_three_way(self) -> None:
        a, b, c = frozenset({"x", "y", "z"}), frozenset({"y", "z"}), frozenset({"z"})
        assert intersection(a, b, c) == frozenset({"z"})


class TestDiff:
    def test_basic(self) -> None:
        assert diff(frozenset({"x", "y"}), frozenset({"y"})) == frozenset({"x"})

    def test_no_overlap_keeps_all(self) -> None:
        assert diff(frozenset({"x"}), frozenset({"y"})) == frozenset({"x"})

    def test_subset_returns_empty(self) -> None:
        assert diff(frozenset({"x"}), frozenset({"x", "y"})) == frozenset()


class TestSymDiff:
    def test_basic(self) -> None:
        assert sym_diff(frozenset({"x", "y"}), frozenset({"y", "z"})) == frozenset({"x", "z"})

    def test_identical_returns_empty(self) -> None:
        a = frozenset({"x", "y"})
        assert sym_diff(a, a) == frozenset()

    def test_disjoint_returns_union(self) -> None:
        a, b = frozenset({"x"}), frozenset({"y"})
        assert sym_diff(a, b) == frozenset({"x", "y"})


class TestComplement:
    def test_basic(self, universe: frozenset[str]) -> None:
        a = frozenset({"1.001"})
        result = complement(a, universe)
        assert "1.001" not in result
        assert "2.001" in result

    def test_empty_complement_is_universe(self, universe: frozenset[str]) -> None:
        assert complement(frozenset(), universe) == universe

    def test_universe_complement_is_empty(self, universe: frozenset[str]) -> None:
        assert complement(universe, universe) == frozenset()


# ─── Metricas ───────────────────────────────────────────────────────────────

class TestJaccard:
    def test_identical_is_one(self) -> None:
        a = frozenset({"x", "y"})
        assert jaccard(a, a) == 1.0

    def test_disjoint_is_zero(self) -> None:
        assert jaccard(frozenset({"x"}), frozenset({"y"})) == 0.0

    def test_both_empty_is_zero(self) -> None:
        # Convencion: 0/0 → 0.0 (no NaN)
        assert jaccard(frozenset(), frozenset()) == 0.0

    def test_half_overlap(self) -> None:
        a, b = frozenset({"x", "y"}), frozenset({"y", "z"})
        # |a ∩ b| = 1, |a ∪ b| = 3
        assert jaccard(a, b) == pytest.approx(1 / 3)


# ─── Parser / evaluador ─────────────────────────────────────────────────────

class TestEvaluateBasic:
    def test_single_cuadrante(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        assert evaluate("1", cuadrantes) == cuadrantes["1"]

    def test_cuadrante_with_b_suffix(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        assert evaluate("1b", cuadrantes) == cuadrantes["1b"]

    def test_unicode_union(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        result = evaluate("1 ∪ 2", cuadrantes)
        assert result == cuadrantes["1"] | cuadrantes["2"]

    def test_python_union(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # Aceptamos | como alias de ∪
        assert evaluate("1 | 2", cuadrantes) == evaluate("1 ∪ 2", cuadrantes)

    def test_unicode_intersection(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # Entre cuadrantes disjuntos → vacio
        assert evaluate("1 ∩ 2", cuadrantes) == frozenset()

    def test_intersection_with_union(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # (1 ∪ 2) ∩ 1 = 1
        assert evaluate("(1 ∪ 2) ∩ 1", cuadrantes) == cuadrantes["1"]

    def test_difference(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # (1 ∪ 2) \ 1 = 2
        assert evaluate("(1 ∪ 2) \\ 1", cuadrantes) == cuadrantes["2"]

    def test_sym_diff(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # 1 △ 1 = vacio
        assert evaluate("1 △ 1", cuadrantes) == frozenset()
        # 1 △ 2 = 1 ∪ 2 (disjuntos)
        assert evaluate("1 △ 2", cuadrantes) == evaluate("1 ∪ 2", cuadrantes)

    def test_complement(
        self, cuadrantes: dict[str, frozenset[str]], universe: frozenset[str]
    ) -> None:
        # ¬1 = U \ 1
        result = evaluate("¬1", cuadrantes)
        assert result == universe - cuadrantes["1"]

    def test_universe_symbol(
        self, cuadrantes: dict[str, frozenset[str]], universe: frozenset[str]
    ) -> None:
        assert evaluate("U", cuadrantes) == universe

    def test_boolean_notation_dot(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # Notacion booleana: · es alias de ∩
        assert evaluate("1 · 2", cuadrantes) == evaluate("1 ∩ 2", cuadrantes)

    def test_complex_preset(
        self, cuadrantes: dict[str, frozenset[str]]
    ) -> None:
        # (1 ∩ 2) \ 4 — pasion sin paga (lo que amas Y haces bien, sin mercado)
        expected = (cuadrantes["1"] & cuadrantes["2"]) - cuadrantes["4"]
        assert evaluate("(1 ∩ 2) \\ 4", cuadrantes) == expected


class TestEvaluateErrors:
    def test_empty_expression(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        with pytest.raises(ExpressionError, match="vacia"):
            evaluate("", cuadrantes)

    def test_whitespace_only(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        with pytest.raises(ExpressionError, match="vacia"):
            evaluate("   ", cuadrantes)

    def test_unknown_operand(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # Como el regex solo matchea 1-5 y opcionalmente "b", "9" cae a un Name
        # crudo "9" en el AST que no esta en namespace.
        # Pero ojo: el ast.parse trata "9" como un Constant(int), no como Name.
        # Verificamos que efectivamente revienta de algun modo claro.
        with pytest.raises(ExpressionError):
            evaluate("9", cuadrantes)

    def test_syntax_error(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        with pytest.raises(ExpressionError, match="Sintaxis"):
            evaluate("1 ∪ ∪ 2", cuadrantes)

    def test_disallowed_operator(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # "+" se parsea como Add, que NO esta en _ALLOWED_BINOPS.
        with pytest.raises(ExpressionError, match=r"no permitido|Sintaxis"):
            evaluate("1 + 2", cuadrantes)

    def test_function_call_rejected(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # Defensa critica: no permitir invocacion de funciones.
        with pytest.raises(ExpressionError):
            evaluate("print(1)", cuadrantes)

    def test_attribute_access_rejected(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        with pytest.raises(ExpressionError):
            evaluate("1.__class__", cuadrantes)


class TestEvaluateUniverseOverride:
    def test_explicit_universe(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        # Si pasamos un universe explicito (subconjunto), el complemento se calcula contra el.
        u = frozenset({"1.001", "2.001"})
        result = evaluate("¬1", cuadrantes, universe=u)
        assert result == frozenset({"2.001"})


# ─── Notacion dual ──────────────────────────────────────────────────────────

class TestRenderDual:
    def test_simple_name(self) -> None:
        d = render_dual("1")
        assert isinstance(d, DualNotation)
        assert d.set_theory == "1"
        assert d.boolean == "1"

    def test_union(self) -> None:
        d = render_dual("1 ∪ 2")
        assert d.set_theory == "1 ∪ 2"
        assert d.boolean == "1 + 2"

    def test_intersection(self) -> None:
        d = render_dual("1 ∩ 2")
        assert d.set_theory == "1 ∩ 2"
        assert d.boolean == "1 · 2"

    def test_complement(self) -> None:
        d = render_dual("¬1")
        assert d.set_theory == "¬1"
        assert d.boolean == "¬1"

    def test_complex_with_parens(self) -> None:
        d = render_dual("(1 ∪ 2) ∩ 3")
        assert "(1 ∪ 2)" in d.set_theory
        assert "(1 + 2)" in d.boolean

    def test_universe_renders_as_U(self) -> None:
        d = render_dual("U")
        assert d.set_theory == "U"
        assert d.boolean == "U"


# ─── Presets ─────────────────────────────────────────────────────────────────

class TestPresets:
    def test_all_presets_parse(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        """Todos los presets deben evaluarse sin error contra cuadrantes vacios o no."""
        for preset in PRESETS:
            try:
                evaluate(preset.expression, cuadrantes)
            except ExpressionError as e:
                pytest.fail(f"Preset {preset.key!r} no parsea: {e}")

    def test_all_presets_render_dual(self) -> None:
        """Todos los presets deben renderizarse en ambas notaciones."""
        for preset in PRESETS:
            d = render_dual(preset.expression)
            assert d.set_theory
            assert d.boolean

    def test_positivos_is_union_of_4(
        self, cuadrantes: dict[str, frozenset[str]]
    ) -> None:
        p = next(p for p in PRESETS if p.key == "positivos")
        result = evaluate(p.expression, cuadrantes)
        expected = union(
            cuadrantes["1"], cuadrantes["2"], cuadrantes["3"], cuadrantes["4"],
        )
        assert result == expected

    def test_negativos_disjunto_de_positivos(
        self, cuadrantes: dict[str, frozenset[str]]
    ) -> None:
        # Sanity: por construccion del CSV los positivos y negativos son disjuntos.
        pos = evaluate("1 ∪ 2 ∪ 3 ∪ 4", cuadrantes)
        neg = evaluate("1b ∪ 2b ∪ 3b ∪ 4b", cuadrantes)
        assert pos & neg == frozenset()

    def test_presets_have_unique_keys(self) -> None:
        keys = [p.key for p in PRESETS]
        assert len(keys) == len(set(keys)), "Hay keys duplicadas en PRESETS"


# ─── Integracion: propiedades fundamentales ─────────────────────────────────

class TestSetAlgebraIdentities:
    """Verifica identidades clasicas del algebra de conjuntos.

    Sirven como sanity check de que nuestros wrappers no rompen propiedades
    matematicas que las usuarias esperan.
    """

    def test_de_morgan_union(
        self, cuadrantes: dict[str, frozenset[str]], universe: frozenset[str]
    ) -> None:
        # ¬(A ∪ B) = ¬A ∩ ¬B
        left = evaluate("¬(1 ∪ 2)", cuadrantes, universe=universe)
        right = evaluate("¬1 ∩ ¬2", cuadrantes, universe=universe)
        assert left == right

    def test_de_morgan_intersection(
        self, cuadrantes: dict[str, frozenset[str]], universe: frozenset[str]
    ) -> None:
        # ¬(A ∩ B) = ¬A ∪ ¬B
        left = evaluate("¬(1 ∩ 2)", cuadrantes, universe=universe)
        right = evaluate("¬1 ∪ ¬2", cuadrantes, universe=universe)
        assert left == right

    def test_double_complement(
        self, cuadrantes: dict[str, frozenset[str]], universe: frozenset[str]
    ) -> None:
        # ¬¬A = A
        assert evaluate("¬¬1", cuadrantes, universe=universe) == cuadrantes["1"]

    def test_distributivity(
        self, cuadrantes: dict[str, frozenset[str]]
    ) -> None:
        # A ∩ (B ∪ C) = (A ∩ B) ∪ (A ∩ C)
        left = evaluate("1 ∩ (2 ∪ 3)", cuadrantes)
        right = evaluate("(1 ∩ 2) ∪ (1 ∩ 3)", cuadrantes)
        assert left == right

    def test_idempotence(self, cuadrantes: dict[str, frozenset[str]]) -> None:
        assert evaluate("1 ∪ 1", cuadrantes) == cuadrantes["1"]
        assert evaluate("1 ∩ 1", cuadrantes) == cuadrantes["1"]


# ─── Smoke test del modulo completo ─────────────────────────────────────────

def test_module_exports_expected_api() -> None:
    """Sanity: el modulo expone los nombres documentados en el docstring."""
    expected = {
        "union", "intersection", "diff", "sym_diff", "complement",
        "jaccard",
        "evaluate", "render_dual", "DualNotation",
        "ExpressionError",
        "PRESETS", "Preset",
    }
    for name in expected:
        assert hasattr(algebra, name), f"Falta export: {name}"
