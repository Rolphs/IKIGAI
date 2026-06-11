"""Tests puros de ikigai.intersection_concepts.

Cubre las unidades sin HTTP:
  1. Catalogo: las 11 intersecciones positivas en orden estable.
  2. concept_key: serializacion canonica.
  3. compute_intersection / compute_all_intersections: items con TODOS los tags.
  4. I/O YAML: load tolerante, save respeta empty=delete.

Los tests del endpoint HTTP /sintesis/concept viven en
test_intersection_endpoints.py.
"""
from __future__ import annotations

from pathlib import Path

from ikigai import intersection_concepts as ic
from ikigai.models import Item

# ─── Catalogo & key helpers (puro) ───────────────────────────────────────


class TestIntersectionKeys:
    def test_has_exactly_11_intersections(self) -> None:
        # 6 de 2 circulos + 4 de 3 + 1 de 4 = 11. Si esto cambia, hay un cambio
        # semantico mayor que merece su propio commit + revisar template.
        assert len(ic.INTERSECTION_KEYS) == 11

    def test_all_are_subsets_of_positive_circles(self) -> None:
        positives = frozenset({"1", "2", "3", "4"})
        for circles in ic.INTERSECTION_KEYS:
            assert circles <= positives, f"{circles} contiene un circulo no-positivo"
            assert len(circles) >= 2, f"{circles} no es una interseccion (necesita 2+)"

    def test_includes_ikigai_center(self) -> None:
        assert frozenset({"1", "2", "3", "4"}) in ic.INTERSECTION_KEYS

    def test_includes_all_4_canonical_2_circle(self) -> None:
        # Pasion, Mision, Profesion, Vocacion
        for pair in [{"1", "2"}, {"1", "3"}, {"2", "4"}, {"3", "4"}]:
            assert frozenset(pair) in ic.INTERSECTION_KEYS

    def test_no_duplicates(self) -> None:
        assert len(set(ic.INTERSECTION_KEYS)) == len(ic.INTERSECTION_KEYS)


class TestConceptKey:
    def test_orders_lexicographically(self) -> None:
        assert ic.concept_key(frozenset({"2", "1"})) == "1,2"
        assert ic.concept_key(frozenset({"4", "1", "2", "3"})) == "1,2,3,4"

    def test_empty_returns_empty_string(self) -> None:
        assert ic.concept_key(frozenset()) == ""

    def test_idempotent_with_list_or_set(self) -> None:
        assert ic.concept_key(["1", "2"]) == ic.concept_key({"1", "2"})


# ─── Computo puro ────────────────────────────────────────────────────────


def _mk(item_id: str, **kwargs) -> Item:
    return Item(id=item_id, item=f"item-{item_id}", **kwargs)


class TestComputeIntersection:
    def test_two_circles_returns_items_in_both(self) -> None:
        tag_sets = {
            "1": frozenset({"a", "b", "c"}),
            "2": frozenset({"b", "c", "d"}),
        }
        result = ic.compute_intersection({"1", "2"}, tag_sets)
        assert result == frozenset({"b", "c"})

    def test_three_circles_requires_all_three(self) -> None:
        tag_sets = {
            "1": frozenset({"a", "b", "c"}),
            "2": frozenset({"b", "c", "d"}),
            "3": frozenset({"c", "d", "e"}),
        }
        # Solo "c" esta en los 3.
        assert ic.compute_intersection({"1", "2", "3"}, tag_sets) == frozenset({"c"})

    def test_disjoint_circles_return_empty(self) -> None:
        tag_sets = {
            "1": frozenset({"a"}),
            "2": frozenset({"b"}),
        }
        assert ic.compute_intersection({"1", "2"}, tag_sets) == frozenset()

    def test_missing_circle_returns_empty(self) -> None:
        # Si pides un circulo que no esta en tag_sets, la interseccion es vacia
        # (no explota: fallback silencioso por UX en el router).
        tag_sets = {"1": frozenset({"a"})}
        assert ic.compute_intersection({"1", "9"}, tag_sets) == frozenset()

    def test_empty_circles_returns_empty(self) -> None:
        assert ic.compute_intersection([], {"1": frozenset({"a"})}) == frozenset()


class TestComputeAllIntersections:
    def test_returns_19_cards(self) -> None:
        # 8 primitivos (4 positivos + 4 sombras, capa 0) + 11 intersecciones
        # (capas 1-3) = 19 conceptos nombrables totales en el pipeline.
        cards = ic.compute_all_intersections({}, {}, {})
        assert len(cards) == 19

    def test_card_shape_has_expected_keys(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        sample = cards[0]
        expected_keys = {
            "key", "circles", "circles_sorted", "layer",
            "set_notation", "bool_notation", "label",
            "canonical_name", "canonical_tagline", "canonical_warning",
            "primary_question", "evocative_question",
            "members", "count", "individual_circles",
            "ingredients_by_layer", "personal_name",
            "prerequisites_met", "is_secured",
        }
        assert set(sample.keys()) == expected_keys

    def test_label_uses_emoji_and_human_name(self) -> None:
        # "❤️ Amo ∩ 💪 Bueno" en vez de "1 ∩ 2". Esa era la peticion explicita
        # de Rolph: las cards deben leerse en lenguaje humano, no en codigo CSV.
        cards = ic.compute_all_intersections({}, {}, {})
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert "Amo" in pasion["label"]
        assert "Bueno" in pasion["label"]
        assert "∩" in pasion["label"]
        # Los emojis estan ahi tambien.
        assert "❤️" in pasion["label"]
        assert "💪" in pasion["label"]

    def test_label_for_ikigai_center_includes_all_4_circles(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        ikigai = next(c for c in cards if c["key"] == "1,2,3,4")
        for name in ("Amo", "Bueno", "Mundo", "Pago"):
            assert name in ikigai["label"]
        # 4 circulos → 3 simbolos de interseccion.
        assert ikigai["label"].count("∩") == 3

    def test_canonical_name_populated_for_pasion(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert pasion["canonical_name"] == "Pasion"

    def test_members_include_only_items_with_all_tags(self) -> None:
        items = {
            "x": _mk("x", tag_amo="1", tag_bueno="1"),
            "y": _mk("y", tag_amo="1"),
            "z": _mk("z", tag_amo="1", tag_bueno="1", tag_mundo="1"),
        }
        tag_sets = {
            "1": frozenset({"x", "y", "z"}),
            "2": frozenset({"x", "z"}),
            "3": frozenset({"z"}),
            "4": frozenset(),
        }
        cards = ic.compute_all_intersections(tag_sets, items, {})
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert [m.id for m in pasion["members"]] == ["x", "z"]
        assert pasion["count"] == 2

    def test_personal_name_threaded_through(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {"1,2": "pensamiento activo"})
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert pasion["personal_name"] == "pensamiento activo"
        # Otros quedan vacios.
        ikigai_card = next(c for c in cards if c["key"] == "1,2,3,4")
        assert ikigai_card["personal_name"] == ""

    def test_set_and_bool_notation_use_C_prefix_sorted(self) -> None:
        # Cambio de v3: "C1 ∩ C2" en vez de "1 ∩ 2". Notacion humana de conjuntos.
        cards = ic.compute_all_intersections({}, {}, {})
        ikigai = next(c for c in cards if c["key"] == "1,2,3,4")
        assert ikigai["set_notation"] == "C1 ∩ C2 ∩ C3 ∩ C4"
        assert ikigai["bool_notation"] == "C1 · C2 · C3 · C4"

    def test_layer_assigned_correctly(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        by_key = {c["key"]: c for c in cards}
        # 2 circulos = capa 1
        assert by_key["1,2"]["layer"] == 1
        assert by_key["2,4"]["layer"] == 1
        # 3 circulos = capa 2
        assert by_key["1,2,3"]["layer"] == 2
        # 4 circulos = capa 3 (centro)
        assert by_key["1,2,3,4"]["layer"] == 3

    def test_individual_circles_present_for_each_participant(self) -> None:
        # Pasion = 1 ∩ 2 → individual_circles tiene 2 entradas (1 y 2)
        cards = ic.compute_all_intersections({}, {}, {})
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert [ic_["csv_value"] for ic_ in pasion["individual_circles"]] == ["1", "2"]
        # Ikigai = 1 ∩ 2 ∩ 3 ∩ 4 → 4 entradas en orden
        ikigai = next(c for c in cards if c["key"] == "1,2,3,4")
        assert [ic_["csv_value"] for ic_ in ikigai["individual_circles"]] == ["1", "2", "3", "4"]

    def test_individual_circles_show_full_circle_population(self) -> None:
        # La materia prima de cada circulo son TODOS sus items, no solo los que
        # estan en la interseccion. Esto es el punto: inspirar el naming aunque
        # la interseccion misma este vacia.
        items = {
            "a": _mk("a", tag_amo="1"),                      # solo Amo
            "b": _mk("b", tag_amo="1"),                      # solo Amo
            "c": _mk("c", tag_bueno="1"),                    # solo Bueno
            "d": _mk("d", tag_amo="1", tag_bueno="1"),       # cohabitante real
        }
        tag_sets = {
            "1": frozenset({"a", "b", "d"}),
            "2": frozenset({"c", "d"}),
            "3": frozenset(),
            "4": frozenset(),
        }
        cards = ic.compute_all_intersections(tag_sets, items, {})
        pasion = next(c for c in cards if c["key"] == "1,2")
        # Cohabitantes reales (interseccion): solo "d"
        assert [m.id for m in pasion["members"]] == ["d"]
        # Materia prima por circulo: cada lado completo (incluyendo cohabitantes)
        amo = pasion["individual_circles"][0]
        bueno = pasion["individual_circles"][1]
        assert amo["csv_value"] == "1"
        assert [m.id for m in amo["members"]] == ["a", "b", "d"]
        assert amo["count"] == 3
        assert bueno["csv_value"] == "2"
        assert [m.id for m in bueno["members"]] == ["c", "d"]
        assert bueno["count"] == 2
        assert bueno["label"] == "Bueno"
        assert bueno["emoji"] == "💪"

    def test_individual_circles_empty_when_no_data(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        pasion = next(c for c in cards if c["key"] == "1,2")
        # 2 circulos participantes, ambos vacios
        assert len(pasion["individual_circles"]) == 2
        for ic_ in pasion["individual_circles"]:
            assert ic_["members"] == []
            assert ic_["count"] == 0


class TestPrimitiveCards:
    """Capa 0: 8 primitivos nombrables. 4 esencias positivas + 4 sombras.
    Cada uno sintetiza los items que el usuario etiquetó/evocó para ese
    círculo en un nombre personal, que después propaga hacia capas 1-3."""

    def test_8_primitive_cards_in_output(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        primitive_keys = {c["key"] for c in cards if c["layer"] == 0}
        assert primitive_keys == {"1", "2", "3", "4", "1b", "2b", "3b", "4b"}

    def test_primitive_card_has_layer_0(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        amo = next(c for c in cards if c["key"] == "1")
        assert amo["layer"] == 0

    def test_primitive_card_uses_circle_label_as_canonical(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        amo = next(c for c in cards if c["key"] == "1")
        # Como intersections.py no tiene singleton lookups, usamos CIRCLE_LABELS.
        assert amo["canonical_name"] == "Amo"
        assert "Amo" in amo["canonical_tagline"]  # tagline auto-construido

    def test_primitive_card_notation_has_no_intersection_symbol(self) -> None:
        # Un primitivo no tiene operacion: notacion es solo "C1", no "C1 ∩ nada".
        cards = ic.compute_all_intersections({}, {}, {})
        amo = next(c for c in cards if c["key"] == "1")
        assert amo["set_notation"] == "C1"
        assert "∩" not in amo["set_notation"]

    def test_primitive_members_are_all_items_with_that_tag(self) -> None:
        items = {
            "a": _mk("a", tag_amo="1"),
            "b": _mk("b", tag_amo="1", tag_bueno="1"),
            "c": _mk("c", tag_bueno="1"),  # NO en Amo
        }
        tag_sets = {
            "1": frozenset({"a", "b"}),
            "2": frozenset({"b", "c"}),
            "3": frozenset(),
            "4": frozenset(),
        }
        cards = ic.compute_all_intersections(tag_sets, items, {})
        amo = next(c for c in cards if c["key"] == "1")
        assert [m.id for m in amo["members"]] == ["a", "b"]
        assert amo["count"] == 2

    def test_primitive_personal_name_persists_and_propagates(self) -> None:
        # Acuna C1 = "comer". El primitivo lo refleja Y propaga a capa 1+.
        cards = ic.compute_all_intersections({}, {}, {"1": "comer"})
        amo = next(c for c in cards if c["key"] == "1")
        assert amo["personal_name"] == "comer"
        # Pasion debe verlo como ingrediente de capa 0.
        pasion = next(c for c in cards if c["key"] == "1,2")
        layer_0 = {i["key"]: i for i in pasion["ingredients_by_layer"][0]}
        assert layer_0["1"]["personal_name"] == "comer"
        assert layer_0["1"]["has_personal"] is True

    def test_primitives_come_before_intersections_in_order(self) -> None:
        # ALL_CONCEPT_KEYS = PRIMITIVE_KEYS + INTERSECTION_KEYS, asi que las
        # 8 cards de capa 0 (4 positivas + 4 sombras) vienen primero.
        cards = ic.compute_all_intersections({}, {}, {})
        first_8 = [c["layer"] for c in cards[:8]]
        assert first_8 == [0] * 8
        rest_layers = {c["layer"] for c in cards[8:]}
        assert rest_layers == {1, 2, 3}

    def test_primitive_card_carries_primary_question(self) -> None:
        # La pregunta primaria del cuadrante ("¿Que amas?") aparece en la card
        # de capa 0 para que el usuario sepa de que se trata el circulo.
        # "Mundo" solo no es suficiente; necesita "¿Que necesita el mundo?".
        cards = ic.compute_all_intersections({}, {}, {})
        primitives = {c["key"]: c for c in cards if c["layer"] == 0}
        assert primitives["1"]["primary_question"] == "¿Qué amas?"
        assert primitives["2"]["primary_question"] == "¿Qué haces bien?"
        assert primitives["3"]["primary_question"] == "¿Qué necesita el mundo?"
        assert primitives["4"]["primary_question"] == "¿Por qué te pagarían?"

    def test_primitive_card_carries_evocative_question(self) -> None:
        # La pregunta evocativa (la rica, larga) tambien va a la card como
        # alternativa colapsable cuando la primaria no destraba al usuario.
        cards = ic.compute_all_intersections({}, {}, {})
        amo = next(c for c in cards if c["key"] == "1")
        assert amo["evocative_question"]  # no vacia
        assert "día libre" in amo["evocative_question"]  # texto del cuadrante

    def test_intersection_cards_dont_have_primitive_questions(self) -> None:
        # Las cards de capa 1-3 NO muestran pregunta primaria (no aplica:
        # una interseccion no es un cuadrante con pregunta evocativa propia).
        cards = ic.compute_all_intersections({}, {}, {})
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert pasion["primary_question"] == ""
        assert pasion["evocative_question"] == ""


class TestLayerAndSubIntersections:
    """Modelo constructivo por capas: cada capa N usa la N-1 como ingrediente."""

    def test_layer_of_counts_circles_minus_one(self) -> None:
        assert ic.layer_of(["1", "2"]) == 1
        assert ic.layer_of(["1", "2"]) == ic.layer_of(frozenset({"1", "2"}))
        assert ic.layer_of(["1", "2"]) == ic.layer_of(("1", "2"))
        assert ic.layer_of(["1", "2"]) == ic.layer_of("12")
        assert ic.layer_of(["1", "2", "3"]) == 2
        assert ic.layer_of(["1", "2", "3", "4"]) == 3

    def test_sub_intersections_empty_for_layer_0(self) -> None:
        # Primitivos (capa 0) no tienen sub-conceptos: sus ingredientes son los
        # items crudos del CSV, no otros conceptos.
        assert ic.sub_intersections({"1"}) == {}

    def test_sub_intersections_for_layer_1_returns_primitives(self) -> None:
        # Capa 1 propaga DESDE capa 0: C1∩C2 tiene como ingredientes a C1 y C2.
        # Ese es el cambio del fix-capa-0: antes era {} ahora propaga primitivos.
        result = ic.sub_intersections({"1", "2"})
        assert set(result.keys()) == {0}
        assert set(result[0]) == {frozenset({"1"}), frozenset({"2"})}

    def test_sub_intersections_for_layer_2(self) -> None:
        # C1∩C2∩C3 → sus 3 primitivos (capa 0) + sus 3 pares (capa 1)
        result = ic.sub_intersections({"1", "2", "3"})
        assert set(result.keys()) == {0, 1}
        assert len(result[0]) == 3  # C(3,1) primitivos
        assert len(result[1]) == 3  # C(3,2) pares
        assert set(result[1]) == {
            frozenset({"1", "2"}),
            frozenset({"1", "3"}),
            frozenset({"2", "3"}),
        }

    def test_sub_intersections_for_ikigai_center(self) -> None:
        # Ikigai → 4 primitivos + 6 pares + 4 trios (no se incluye a si mismo)
        result = ic.sub_intersections({"1", "2", "3", "4"})
        assert set(result.keys()) == {0, 1, 2}
        assert len(result[0]) == 4  # C(4,1)
        assert len(result[1]) == 6  # C(4,2)
        assert len(result[2]) == 4  # C(4,3)


class TestIngredientsPropagation:
    """Verifica que los nombres acunados en cards de arriba se propagan a las
    cards de capas inferiores que las contienen. Este es el corazon del modelo
    constructivo: el Ikigai se BUILDS, no se nombra de la nada."""

    def test_layer_0_cards_have_no_ingredients(self) -> None:
        # Los primitivos no tienen ingredientes: la card de Amo NO referencia
        # a otra card mas pequena (ya es el atomo del pipeline).
        cards = ic.compute_all_intersections({}, {}, {"1": "comer"})
        amo = next(c for c in cards if c["key"] == "1")
        assert amo["ingredients_by_layer"] == {}

    def test_layer_1_cards_now_have_layer_0_ingredients(self) -> None:
        # Cambio del fix-capa-0: Pasion (C1∩C2) ahora muestra C1 y C2 como
        # ingredientes de capa 0. Si los nombraste arriba, sus nombres personales
        # propagan hacia abajo.
        cards = ic.compute_all_intersections({}, {}, {
            "1": "comer", "2": "leer",
        })
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert set(pasion["ingredients_by_layer"].keys()) == {0}
        layer_0 = {i["key"]: i for i in pasion["ingredients_by_layer"][0]}
        assert layer_0["1"]["personal_name"] == "comer"
        assert layer_0["2"]["personal_name"] == "leer"
        assert layer_0["1"]["canonical_name"] == "Amo"
        assert layer_0["2"]["canonical_name"] == "Bueno"

    def test_layer_2_card_shows_both_layer_0_and_layer_1_subs(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        casi_sin_mercado = next(c for c in cards if c["key"] == "1,2,3")
        ing = casi_sin_mercado["ingredients_by_layer"]
        assert set(ing.keys()) == {0, 1}
        # Capa 0: los 3 primitivos
        keys_0 = {i["key"] for i in ing[0]}
        assert keys_0 == {"1", "2", "3"}
        # Capa 1: los 3 pares
        keys_1 = {i["key"] for i in ing[1]}
        assert keys_1 == {"1,2", "1,3", "2,3"}

    def test_personal_names_propagate_upward(self) -> None:
        # Acunamos en capa 1 → aparecen como ingredientes en capa 2 y 3.
        names = {
            "1,2": "customer journey",
            "1,3": "rituales que sanan",
        }
        cards = ic.compute_all_intersections({}, {}, names)
        ikigai = next(c for c in cards if c["key"] == "1,2,3,4")
        layer_1_ingredients = {i["key"]: i for i in ikigai["ingredients_by_layer"][1]}
        assert layer_1_ingredients["1,2"]["personal_name"] == "customer journey"
        assert layer_1_ingredients["1,2"]["has_personal"] is True
        assert layer_1_ingredients["1,3"]["personal_name"] == "rituales que sanan"
        assert layer_1_ingredients["1,3"]["has_personal"] is True
        # Las no acunadas se ven como canonico sin personal (template las muestra
        # tachadas en gris para invitar a llenarlas).
        assert layer_1_ingredients["2,4"]["has_personal"] is False
        assert layer_1_ingredients["2,4"]["canonical_name"] == "Profesion"
        assert layer_1_ingredients["2,4"]["personal_name"] == ""

    def test_ikigai_shows_all_3_lower_layers(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        ikigai = next(c for c in cards if c["key"] == "1,2,3,4")
        ing = ikigai["ingredients_by_layer"]
        assert set(ing.keys()) == {0, 1, 2}
        assert len(ing[0]) == 4  # 4 primitivos
        assert len(ing[1]) == 6  # 6 pares
        assert len(ing[2]) == 4  # 4 trios
        # Total: 14 ingredientes visibles en la card central (el Ikigai como
        # convergencia de TODO el trabajo previo del pipeline).
        layer_2_keys = {i["key"] for i in ing[2]}
        assert layer_2_keys == {"1,2,3", "1,2,4", "1,3,4", "2,3,4"}

    def test_ingredient_set_notation_uses_C_prefix(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        ikigai = next(c for c in cards if c["key"] == "1,2,3,4")
        notations = {i["set_notation"] for i in ikigai["ingredients_by_layer"][1]}
        # Las 6 de capa 1, con notacion C-prefix.
        assert "C1 ∩ C2" in notations
        assert "C3 ∩ C4" in notations


class TestSecuredStatus:
    """Estado del workflow visible: is_secured indica si la card esta "firme"
    (sintesis acunada Y todos los ingredientes previos acunados). Pendiente
    se pinta paja, asegurada blanca con boton metalico."""

    def test_layer_0_unnamed_is_not_secured(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {})
        amo = next(c for c in cards if c["key"] == "1")
        assert amo["personal_name"] == ""
        assert amo["prerequisites_met"] is True  # capa 0 no tiene prereqs
        assert amo["is_secured"] is False  # falta sintesis

    def test_layer_0_named_is_secured(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {"1": "comer"})
        amo = next(c for c in cards if c["key"] == "1")
        assert amo["is_secured"] is True

    def test_layer_1_named_but_missing_prereqs_is_not_secured(self) -> None:
        # Acunamos C1∩C2="libros de cocina" pero NO los primitivos C1, C2.
        # Pasion tiene sintesis pero su base sintetica esta floja — paja.
        cards = ic.compute_all_intersections({}, {}, {"1,2": "libros de cocina"})
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert pasion["personal_name"] == "libros de cocina"
        assert pasion["prerequisites_met"] is False
        assert pasion["is_secured"] is False

    def test_layer_1_fully_secured_when_self_and_prereqs_named(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {
            "1": "comer", "2": "leer", "1,2": "libros de cocina",
        })
        pasion = next(c for c in cards if c["key"] == "1,2")
        assert pasion["prerequisites_met"] is True
        assert pasion["is_secured"] is True

    def test_layer_2_requires_all_layer_0_and_layer_1_prereqs(self) -> None:
        # Llenamos primitivos y la sintesis de capa 2, PERO no los 3 pares
        # de capa 1 que componen 1,2,3. Resultado: pendiente.
        cards = ic.compute_all_intersections({}, {}, {
            "1": "comer", "2": "leer", "3": "sanar",
            "1,2,3": "sin sueldo pero pleno",
        })
        casi = next(c for c in cards if c["key"] == "1,2,3")
        assert casi["prerequisites_met"] is False
        assert casi["is_secured"] is False
        # Completando los 3 pares de capa 1 → asegurado.
        cards = ic.compute_all_intersections({}, {}, {
            "1": "comer", "2": "leer", "3": "sanar",
            "1,2": "libros de cocina", "1,3": "medicina narrativa", "2,3": "docencia ciudadana",
            "1,2,3": "sin sueldo pero pleno",
        })
        casi = next(c for c in cards if c["key"] == "1,2,3")
        assert casi["prerequisites_met"] is True
        assert casi["is_secured"] is True

    def test_ikigai_secured_requires_full_pipeline(self) -> None:
        # Centro asegurado = 4 primitivos + 6 pares + 4 casi-Ikigai + el centro.
        # 15 conceptos nombrables, todos con personal_name.
        all_keys = {
            "1": "a", "2": "b", "3": "c", "4": "d",
            "1,2": "e", "1,3": "f", "1,4": "g",
            "2,3": "h", "2,4": "i", "3,4": "j",
            "1,2,3": "k", "1,2,4": "l", "1,3,4": "m", "2,3,4": "n",
            "1,2,3,4": "IKIGAI",
        }
        cards = ic.compute_all_intersections({}, {}, all_keys)
        ikigai = next(c for c in cards if c["key"] == "1,2,3,4")
        assert ikigai["is_secured"] is True
        # Quitar un eslabon rompe la cadena hasta el centro.
        del all_keys["1,2"]
        cards = ic.compute_all_intersections({}, {}, all_keys)
        ikigai = next(c for c in cards if c["key"] == "1,2,3,4")
        assert ikigai["prerequisites_met"] is False
        assert ikigai["is_secured"] is False


class TestComputeIndividualCircles:
    def test_returns_sorted_by_csv_value(self) -> None:
        result = ic.compute_individual_circles(
            {"3", "1", "2"},
            {"1": frozenset(), "2": frozenset(), "3": frozenset()},
            {},
        )
        assert [r["csv_value"] for r in result] == ["1", "2", "3"]

    def test_unknown_circle_yields_empty_members(self) -> None:
        # Defensivo: si pides un circulo no presente en tag_sets, no explota,
        # solo aparece con count=0 (mismo trato que un circulo realmente vacio).
        result = ic.compute_individual_circles(
            ["1", "9"], {"1": frozenset({"a"})}, {"a": _mk("a")}
        )
        nine = next(r for r in result if r["csv_value"] == "9")
        assert nine["members"] == []
        assert nine["count"] == 0


# ─── I/O YAML ────────────────────────────────────────────────────────────


class TestLegacyConceptTolerance:
    """UNA sintesis por nodo (personal_name). El loader tolera YAML legacy
    (scalar string o lista de una version vieja multi-concepto); si encuentra
    una lista, toma el primero como principal."""

    def test_load_legacy_string_value(self, tmp_path: Path) -> None:
        path = tmp_path / "intersection_concepts.yaml"
        path.write_text("concepts:\n  '1': comer\n", encoding="utf-8")
        assert ic.load_personal_names(path) == {"1": "comer"}

    def test_load_legacy_list_takes_first_as_primary(self, tmp_path: Path) -> None:
        path = tmp_path / "intersection_concepts.yaml"
        path.write_text("concepts:\n  '1':\n    - comer\n    - leer\n", encoding="utf-8")
        assert ic.load_personal_names(path) == {"1": "comer"}

    def test_save_personal_name_single_scalar(self, tmp_path: Path) -> None:
        # Un solo concepto se guarda como scalar string (diff limpio, compat legacy).
        path = tmp_path / "intersection_concepts.yaml"
        ic.save_personal_name(path, "1", "comer")
        text = path.read_text(encoding="utf-8")
        assert "comer" in text
        assert "- comer" not in text  # no es lista YAML

    def test_save_personal_name_replaces_legacy_list(self, tmp_path: Path) -> None:
        path = tmp_path / "intersection_concepts.yaml"
        path.write_text("concepts:\n  '1':\n    - comer\n    - leer\n", encoding="utf-8")
        ic.save_personal_name(path, "1", "solo esto")
        assert ic.load_personal_names(path) == {"1": "solo esto"}

    def test_save_empty_removes_key(self, tmp_path: Path) -> None:
        path = tmp_path / "intersection_concepts.yaml"
        ic.save_personal_name(path, "1", "comer")
        ic.save_personal_name(path, "1", "")
        assert ic.load_personal_names(path) == {}

    def test_compute_uses_personal_name_as_primary(self) -> None:
        cards = ic.compute_all_intersections({}, {}, {"1": "comer"})
        amo = next(c for c in cards if c["key"] == "1")
        assert amo["personal_name"] == "comer"


class TestPersistence:
    def test_load_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert ic.load_personal_names(tmp_path / "nope.yaml") == {}

    def test_load_corrupted_yaml_returns_empty(self, tmp_path: Path) -> None:
        # Tolerancia: yaml roto → {} (no 500). Si quisieras strictness,
        # cambia load_personal_names para propagar el error.
        path = tmp_path / "corrupted.yaml"
        path.write_text("not: valid: yaml: [", encoding="utf-8")
        assert ic.load_personal_names(path) == {}

    def test_load_empty_yaml_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        assert ic.load_personal_names(path) == {}

    def test_load_unexpected_root_shape_returns_empty(self, tmp_path: Path) -> None:
        # Root debe ser dict con `concepts:`. Cualquier otra cosa → {}.
        path = tmp_path / "list.yaml"
        path.write_text("- just\n- a\n- list\n", encoding="utf-8")
        assert ic.load_personal_names(path) == {}

    def test_save_then_load_roundtrip(self, tmp_path: Path) -> None:
        path = tmp_path / "concepts.yaml"
        ic.save_personal_name(path, "1,2", "pensamiento activo")
        ic.save_personal_name(path, "1,2,3,4", "mi voz")
        loaded = ic.load_personal_names(path)
        assert loaded == {"1,2": "pensamiento activo", "1,2,3,4": "mi voz"}

    def test_save_empty_string_removes_entry(self, tmp_path: Path) -> None:
        # Politica: empty → delete (mantiene YAML limpio, evita "" en diffs).
        path = tmp_path / "concepts.yaml"
        ic.save_personal_name(path, "1,2", "primer nombre")
        ic.save_personal_name(path, "1,2", "")
        assert ic.load_personal_names(path) == {}

    def test_save_strips_whitespace(self, tmp_path: Path) -> None:
        path = tmp_path / "concepts.yaml"
        ic.save_personal_name(path, "1,2", "  con espacios  ")
        assert ic.load_personal_names(path) == {"1,2": "con espacios"}

    def test_save_only_whitespace_treated_as_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "concepts.yaml"
        ic.save_personal_name(path, "1,2", "nombre")
        ic.save_personal_name(path, "1,2", "   ")
        assert ic.load_personal_names(path) == {}

    def test_yaml_filename_is_canonical(self, tmp_path: Path) -> None:
        assert ic.yaml_path_for(tmp_path).name == "intersection_concepts.yaml"

    def test_load_personal_names_for_equals_explicit_path(self, tmp_path: Path) -> None:
        # El helper de conveniencia debe ser identico a resolver el path a mano.
        path = ic.yaml_path_for(tmp_path)
        ic.save_personal_name(path, "1,2", "pasion")
        assert ic.load_personal_names_for(tmp_path) == ic.load_personal_names(path)
        assert ic.load_personal_names_for(tmp_path) == {"1,2": "pasion"}

    def test_load_personal_names_for_missing_is_empty(self, tmp_path: Path) -> None:
        # Proyecto sin YAML aun -> dict vacio (tolerante, igual que load_personal_names).
        assert ic.load_personal_names_for(tmp_path) == {}


class TestConcurrentSaves:
    """D2: /sintesis y /visualizador escriben al MISMO YAML. save_personal_name
    debe serializar load->modify->save con un lock interno; sin el, writes
    concurrentes a keys distintos se pisan (lost update)."""

    def test_concurrent_saves_to_different_keys_dont_lose_writes(
        self, tmp_path: Path
    ) -> None:
        import threading

        path = tmp_path / "intersection_concepts.yaml"
        n = 40

        def worker(i: int) -> None:
            ic.save_personal_name(path, f"k{i}", f"name{i}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        loaded = ic.load_personal_names(path)
        # Sin lock, varios writes se perderian (el ultimo gana). Con lock, los 40.
        assert len(loaded) == n
        for i in range(n):
            assert loaded[f"k{i}"] == f"name{i}"

