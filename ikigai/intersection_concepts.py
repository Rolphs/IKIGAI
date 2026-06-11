"""intersection_concepts.py — La tercera capa de naming del Ikigai algebraico.

Hay tres capas de "nombre" en este sistema:

  1. CANONICA (universal): "Pasion", "Mision", "Profesion", "Vocacion", "Ikigai".
     Vive en `intersections.py`. Mismo nombre para todos los humanos.
  2. POR-VENN (por visualizacion): "Mi mentoria que transforma", "Trabajo
     que no me llena". Vive en `Region.concept` por cada Universo del visualizador.
  3. PERSONAL GLOBAL (este modulo, NUEVO): el nombre que TU acunas para la
     interseccion `1 ∩ 2` mirando los items concretos que cohabitan ahi. Ej.
     "caminar ∩ pensar = pensamiento activo". No es un sustantivo abstracto
     del folclore (capa 1), ni narrativa de un Venn (capa 2): es VOCABULARIO
     PROPIO emergente al ver las intersecciones algebraicas con tus items reales.

Este modulo expone:
  - INTERSECTION_KEYS: las 11 intersecciones positivas en orden estable para UI.
  - concept_key(): serializa una frozenset[str] a string canonico "1,2,3".
  - compute_intersection(): items con TODOS los tags de la interseccion.
  - compute_all_intersections(): empaqueta las 11 con metadata para el template.
  - load_personal_names() / save_personal_name(): persistencia YAML.

NO conoce HTTP, FastAPI, ni renderizado. Funciones puras + I/O minimal.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations
from pathlib import Path
from typing import Any

import yaml

from ikigai import atomic_io, intersections
from ikigai.cuadrantes import CUADRANTES, find_side
from ikigai.locks import keyed_lock
from ikigai.models import Item
from ikigai.stats import CIRCLE_EMOJIS, CIRCLE_LABELS

# Mapa csv_value ("1", "2", "3", "4") → (pregunta primaria, pregunta evocativa).
# La pregunta primaria es el "¿Qué amas?" — fundamento del circulo, lo que
# define operativamente que items pertenecen ahi. La evocativa es la version
# rica usada en /inventario para destrabar respuestas. Las cards de capa 0
# las muestran al usuario para que "mundo" o "amo" no sean cascarones vacios.
PRIMITIVE_QUESTIONS: dict[str, dict[str, str]] = {
    pair.positivo.csv_value: {
        "primary": pair.pregunta,
        "evocative": pair.positivo.pregunta_evocativa,
    }
    for pair in CUADRANTES
}

# ─── Catálogo de claves nombrables (orden estable UI) ──────────────
# 19 "conceptos nombrables" en total = 8 primitivos (capa 0) + 11 intersecciones.
# Los 8 primitivos son las 4 esencias + sus 4 sombras (1b, 2b, 3b, 4b).
# El pipeline constructivo completo va de capa 0 → 1 → 2 → 3.
# Cada capa propaga sus nombres personales hacia las siguientes como ingredientes.
PRIMITIVE_KEYS: tuple[frozenset[str], ...] = (
    frozenset({"1"}),  # ❤️ Amo
    frozenset({"1b"}), # 🌑 Sombra C1
    frozenset({"2"}),  # 💪 Bueno
    frozenset({"2b"}), # 🌑 Sombra C2
    frozenset({"3"}),  # 🌍 Mundo
    frozenset({"3b"}), # 🌑 Sombra C3
    frozenset({"4"}),  # 💰 Pago
    frozenset({"4b"}), # 🌑 Sombra C4
)

# ─── Las 11 intersecciones positivas del modelo Ikigai ───────────────────
INTERSECTION_KEYS: tuple[frozenset[str], ...] = (
    frozenset({"1", "2"}),
    frozenset({"1", "3"}),
    frozenset({"2", "4"}),
    frozenset({"3", "4"}),
    frozenset({"1", "4"}),
    frozenset({"2", "3"}),
    frozenset({"1", "2", "3"}),
    frozenset({"1", "2", "4"}),
    frozenset({"1", "3", "4"}),
    frozenset({"2", "3", "4"}),
    frozenset({"1", "2", "3", "4"}),
)

# Catálogo completo del pipeline constructivo (19 nodos nombrables).
# Capa 0 primero (los 8 primitivos), luego capa 1, 2, 3. El UI lo renderiza
# en este mismo orden, segmentado visualmente por capa.
ALL_CONCEPT_KEYS: tuple[frozenset[str], ...] = PRIMITIVE_KEYS + INTERSECTION_KEYS


def concept_key(circles: Iterable[str]) -> str:
    """Serializa una frozenset de csv_values a una key canonica para YAML/dict.

    Ej. frozenset({"2", "1"}) → "1,2". Orden lexicografico ascendente para
    que sea estable independientemente del orden de insercion.
    """
    return ",".join(sorted(circles))


# ─── Calculo puro de items en cada interseccion ─────────────────────────


def compute_intersection(
    circles: Iterable[str],
    tag_sets: Mapping[str, frozenset[str]],
) -> frozenset[str]:
    """Item IDs que tienen TODOS los tags de los circulos pedidos.

    Args:
      circles: csv_values positivos, ej. ("1", "2", "3").
      tag_sets: mapping csv_value → frozenset[item_id]. Se asume que solo
        circulos positivos (1-4) tienen sentido aqui; los negativos seran
        ignorados silenciosamente (sus items NO entran a la interseccion).

    Returns:
      Items que estan en TODAS las celdas pedidas. Frozenset vacio si alguno
      de los circulos no esta en tag_sets o si la interseccion es vacia.
    """
    circle_list = list(circles)
    if not circle_list:
        return frozenset()
    try:
        sets_to_intersect = [tag_sets[c] for c in circle_list]
    except KeyError:
        return frozenset()
    result = sets_to_intersect[0]
    for s in sets_to_intersect[1:]:
        result = result & s
    return frozenset(result)


def _primitive_display_name(csv_value: str) -> str:
    """Nombre humano para un primitivo positivo o de sombra."""
    if csv_value in CIRCLE_LABELS:
        return CIRCLE_LABELS[csv_value]
    found = find_side(csv_value)
    if found:
        _, side = found
        return side.label
    return csv_value


def _primitive_display_emoji(csv_value: str) -> str:
    """Emoji humano para un primitivo positivo o de sombra."""
    if csv_value in CIRCLE_EMOJIS:
        return CIRCLE_EMOJIS[csv_value]
    found = find_side(csv_value)
    if found:
        _, side = found
        return side.emoji
    return ""


def _label_for(circle: str) -> str:
    """'❤️ Amo' / '💔 No me gusta' para circulos conocidos; raw como fallback."""
    emoji = _primitive_display_emoji(circle)
    label = _primitive_display_name(circle)
    return f"{emoji} {label}".strip()


def layer_of(circles: Iterable[str]) -> int:
    """Capa del concepto = numero de circulos involucrados - 1.

    - Capa 0: 1 circulo  (los 4 primitivos: Amo, Bueno, Mundo, Pago)
    - Capa 1: 2 circulos (Pasion, Mision, Profesion, Vocacion, Hobby, Servicio)
    - Capa 2: 3 circulos (los 4 casi-Ikigai)
    - Capa 3: 4 circulos (Ikigai centro)

    Modelo constructivo: cada capa USA la anterior como ingrediente.
    Capa 0 son los primitivos — su sintesis personal nace de mirar TODOS los
    items que el usuario etiqueto en ese circulo. Las capas 1-3 son las
    intersecciones tradicionales.
    """
    return len(list(circles)) - 1


def sub_intersections(circles: Iterable[str]) -> dict[int, list[frozenset[str]]]:
    """Sub-conceptos de un concepto, agrupados por capa.

    Para C1 ∩ C2 (capa 1) → {0: [{C1}, {C2}]} (sus 2 primitivos componentes).
    Para C1 ∩ C2 ∩ C3 (capa 2) → {0: [3 primitivos], 1: [3 pares]}.
    Para Ikigai (capa 3) → {0: [4 primitivos], 1: [6 pares], 2: [4 trios]}.
    Para un primitivo (capa 0) → {} (no tiene sub-conceptos; sus ingredientes
    son los items crudos del CSV, no otros conceptos).

    Base de la PROPAGACION: cada card de capa N muestra los nombres personales
    acunados en las cards de capas < N que la componen. Despues del fix-capa-0,
    los primitivos tambien propagan: si nombras C1="comer" y C2="leer", la
    card de Pasion (C1∩C2) mostrara ambos como ingredientes de capa 0.
    """
    circle_list = sorted(circles)
    n = len(circle_list)
    if n < 2:
        return {}
    out: dict[int, list[frozenset[str]]] = {}
    # Tamanos validos: 1 (primitivos, capa 0) hasta n-1 (capa n-2). Excluye
    # el set entero (no se incluye a si mismo).
    for size in range(1, n):
        out[size - 1] = [frozenset(combo) for combo in combinations(circle_list, size)]
    return out


def compute_individual_circles(
    circles: Iterable[str],
    tag_sets: Mapping[str, frozenset[str]],
    items_by_id: Mapping[str, Item],
) -> list[dict[str, object]]:
    """Materia prima por circulo de una interseccion.

    Para cada circulo participante devuelve sus items POR SEPARADO. Es la
    "poblacion individual" de cada lado de la interseccion, util cuando la
    interseccion misma es vacia (o pequena) y necesitas inspirar el naming
    mirando que hay en cada universo individual.

    Ejemplo: para nombrar Amo ∩ Bueno, ver que hay en Amo (caminar, pensar,
    musica...) y que hay en Bueno (escribir, hablar...) ayuda a acunar el
    concepto puente aunque ningun item los una directamente todavia.

    Returns:
      Lista ordenada por csv_value, una entrada por circulo:
        - csv_value: "1"
        - label:     "Amo"
        - emoji:     "❤️"
        - members:   list[Item] ordenado por id
        - count:     int
    """
    out: list[dict[str, object]] = []
    for circle in sorted(circles):
        ids = tag_sets.get(circle, frozenset())
        members = sorted(
            (items_by_id[i] for i in ids if i in items_by_id),
            key=lambda it: it.id,
        )
        out.append({
            "csv_value": circle,
            "label": _primitive_display_name(circle),
            "emoji": _primitive_display_emoji(circle),
            "members": members,
            "count": len(members),
        })
    return out


def compute_all_intersections(
    tag_sets: Mapping[str, frozenset[str]],
    items_by_id: Mapping[str, Item],
    personal_names: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Empaqueta las 11 intersecciones con todo lo que el template necesita.

    Para cada una calcula:
      - key: "1,2"
      - circles: frozenset({"1", "2"})
      - circles_sorted: ["1", "2"]  (iterar estable)
      - layer: 1, 2 o 3 (numero de circulos - 1; modelo constructivo de capas)
      - set_notation: "C1 ∩ C2"  (con prefijo C-, notacion humana de conjuntos)
      - bool_notation: "C1 · C2"
      - label: "❤️ Amo ∩ 💪 Bueno"  (human-friendly con emojis para subtitulo)
      - canonical_name: "Pasion" (de intersections.py) — usado como TITULO
      - canonical_tagline: "Lo que amas Y haces bien"
      - canonical_warning: "..." (puede ser "")
      - members: list[Item] con TODOS los tags de la interseccion (cohabitantes).
        Se llama `members` (no `items`) para evitar el clash de Jinja `c.items`
        con el metodo `dict.items()`.
      - count: int (= len(members))
      - individual_circles: materia prima por cada circulo participante.
      - ingredients_by_layer: PROPAGACION — sub-intersecciones de capas inferiores
        que componen esta, con su nombre canonico y personal. Vacio para cards
        de capa 1 (cuyo ingrediente son los primitivos, no otras intersecciones).
      - personal_name: str del YAML; "" si nunca se nombro.
    """
    personal_names = personal_names or {}
    out: list[dict[str, object]] = []
    for circles in ALL_CONCEPT_KEYS:
        sorted_circles = sorted(circles)
        ids = compute_intersection(circles, tag_sets)
        members = sorted(
            (items_by_id[i] for i in ids if i in items_by_id),
            key=lambda it: it.id,
        )
        canonical = intersections.lookup(circles)
        # Para primitivos (capa 0) no hay entrada en intersections.py —
        # construimos su "canonical_name" desde CIRCLE_LABELS (Amo, Bueno, etc.).
        # Asi todas las cards tienen un titulo aunque el lookup intersections falle.
        is_primitive = len(circles) == 1
        if is_primitive:
            primitive_csv = sorted_circles[0]
            canonical_name = _primitive_display_name(primitive_csv)
            canonical_tagline = f"Todo lo que etiquetaste como '{canonical_name}' en tu inventario"
            canonical_warning = ""
            set_notation = f"C{primitive_csv}"
            bool_notation = f"C{primitive_csv}"
            questions = PRIMITIVE_QUESTIONS.get(primitive_csv, {})
            primary_question = questions.get("primary", "")
            found = find_side(primitive_csv)
            evocative_question = found[1].pregunta_evocativa if found else ""
        else:
            canonical_name = canonical.name if canonical else ""
            canonical_tagline = canonical.tagline if canonical else ""
            canonical_warning = canonical.warning if canonical else ""
            set_notation = " ∩ ".join(f"C{c}" for c in sorted_circles)
            bool_notation = " · ".join(f"C{c}" for c in sorted_circles)
            primary_question = ""
            evocative_question = ""
        key = concept_key(circles)
        ingredients = _build_ingredients(circles, personal_names)
        personal_name = personal_names.get(key, "")
        if len(circles) == 1:
            prerequisites_met = True
        else:
            prerequisites_met = all(
                ing["has_personal"]
                for bucket in ingredients.values()
                for ing in bucket
            )

        # Guardado != asegurado. Asegurado implica nombre propio + base completa.
        is_secured = bool(personal_name) and prerequisites_met
        out.append({
            "key": key,
            "circles": circles,
            "circles_sorted": sorted_circles,
            "layer": layer_of(circles),
            "set_notation": set_notation,
            "bool_notation": bool_notation,
            "label": " ∩ ".join(_label_for(c) for c in sorted_circles),
            "canonical_name": canonical_name,
            "canonical_tagline": canonical_tagline,
            "canonical_warning": canonical_warning,
            "primary_question": primary_question,
            "evocative_question": evocative_question,
            "members": members,
            "count": len(members),
            "individual_circles": compute_individual_circles(circles, tag_sets, items_by_id),
            "ingredients_by_layer": ingredients,
            "personal_name": personal_name,
            "prerequisites_met": prerequisites_met,
            "is_secured": is_secured,
        })
    return out


def _build_ingredients(
    circles: frozenset[str],
    personal_names: Mapping[str, str],
) -> dict[int, list[dict[str, object]]]:
    """Para una interseccion de capa N, lista las sub-intersecciones de capas
    1..N-1 que la componen, con su nombre canonico, personal, y notacion.

    Cada ingrediente lleva:
      - key: "1,2"
      - set_notation: "C1 ∩ C2"
      - canonical_name: "Pasion"
      - personal_name: "customer journey" o "" si no acunado
      - has_personal: bool (template muestra el canonico tachado-en-gris cuando
        no hay personal, o el personal en azul cuando si lo hay).
    """
    subs_by_layer = sub_intersections(circles)
    out: dict[int, list[dict[str, object]]] = {}
    for layer, subs in subs_by_layer.items():
        bucket: list[dict[str, object]] = []
        for sub in subs:
            sub_sorted = sorted(sub)
            sub_key = concept_key(sub)
            personal = personal_names.get(sub_key, "")
            # Capa 0 (primitivos): no estan en intersections.py; usamos CIRCLE_LABELS.
            # Capa 1+: lookup en el catalogo canonico folclorico.
            if len(sub) == 1:
                canonical_name = _primitive_display_name(sub_sorted[0])
            else:
                canonical = intersections.lookup(sub)
                canonical_name = canonical.name if canonical else ""
            bucket.append({
                "key": sub_key,
                "set_notation": " ∩ ".join(f"C{c}" for c in sub_sorted),
                "canonical_name": canonical_name,
                "personal_name": personal,
                "has_personal": bool(personal),
            })
        out[layer] = bucket
    return out


# ─── Persistencia YAML ──────────────────────────────────────────────────
# Formato:
#   concepts:
#     "1,2": "pensamiento activo"
#     "1,2,3,4": "mi voz"
#
# Keys son strings de csv_values ordenados y joined por coma (igual que
# concept_key). El root es un dict con `concepts:` para dejar espacio a
# metadata futura (version, last_modified, etc.) sin romper el schema.


_YAML_FILENAME = "intersection_concepts.yaml"


def yaml_path_for(project_dir: Path) -> Path:
    """Path canonico del archivo de nombres personales para un proyecto."""
    return project_dir / _YAML_FILENAME


def _normalize_to_list(value: Any) -> list[str]:
    """Normaliza un valor del YAML a una lista de conceptos limpios.

    Acepta el formato legacy (un string) o el nuevo (una lista de strings).
    Strippea, descarta vacios y None. Asi el resto del modulo trabaja siempre
    con listas, sin importar como quedo escrito el YAML.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None and str(v).strip()]
    s = str(value).strip()
    return [s] if s else []


def _load_raw_concepts(yaml_path: Path) -> dict[str, list[str]]:
    """Lee el YAML y devuelve {key: [conceptos]}. Tolerante: {} si falla.

    Cada valor se normaliza a lista (ver _normalize_to_list), soportando el
    formato legacy (string) y el nuevo (lista). Keys sin conceptos se omiten.
    """
    if not yaml_path.exists():
        return {}
    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    concepts = data.get("concepts")
    if not isinstance(concepts, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in concepts.items():
        normalized = _normalize_to_list(v)
        if normalized:
            out[str(k)] = normalized
    return out


def load_personal_names(yaml_path: Path) -> dict[str, str]:
    """Lee el nombre PRINCIPAL (primer concepto) de cada interseccion.

    Contrato historico: dict[str, str]. Cuando una key tiene varios conceptos
    (capa 0 multi-concepto), el principal es el primero — el que propaga a las
    intersecciones y usa el visualizador. Tolerante: {} si el archivo no existe
    o esta corrupto.
    """
    return {k: vals[0] for k, vals in _load_raw_concepts(yaml_path).items()}


def load_personal_names_for(project_dir: Path) -> dict[str, str]:
    """Conveniencia: nombres principales de un proyecto, dado su directorio.

    Colapsa el patron repetido `load_personal_names(yaml_path_for(dir))`.
    El path del YAML es un detalle de implementacion; los callers de solo
    lectura quieren "los nombres de este proyecto", no el archivo.

    Para flujos load->modify->save usa `yaml_path_for` + `save_personal_name`
    explicitos.
    """
    return load_personal_names(yaml_path_for(project_dir))


def _serialize_concepts(raw: Mapping[str, list[str]]) -> dict[str, Any]:
    """Prepara el dict para el YAML manteniendo el formato lo mas limpio posible.

    - Una key con UN concepto se guarda como scalar string (compat legacy,
      diffs limpios).
    - Una key con VARIOS se guarda como lista.
    - Keys sin conceptos (lista vacia) se descartan.
    """
    out: dict[str, Any] = {}
    for key, vals in raw.items():
        clean = [v.strip() for v in vals if v and v.strip()]
        if not clean:
            continue
        out[key] = clean[0] if len(clean) == 1 else clean
    return out


def _write_concepts(yaml_path: Path, raw: Mapping[str, list[str]]) -> None:
    """Escribe el YAML de conceptos de forma atomica. Asume lock ya tomado."""
    payload = {"concepts": _serialize_concepts(raw)}
    atomic_io.atomic_write_text(
        yaml_path,
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=True, default_flow_style=False),
    )


def save_personal_name(yaml_path: Path, key: str, personal_name: str) -> None:
    """Guarda (o borra, si viene vacio) el nombre UNICO de una interseccion.

    Reemplaza el valor de la key por [personal_name] (una sola sintesis por
    nodo). Empty string remueve la entrada (YAML limpio). El loader tolera
    YAML legacy con listas (toma el primero como principal).

    D2: el bloque load -> modify -> save se serializa con un lock por archivo
    (keyed_lock), porque /sintesis y /visualizador escriben al MISMO YAML.
    Sin lock, dos writes concurrentes a keys distintos podian pisarse (lost update).
    """
    with keyed_lock(str(yaml_path)):
        raw = _load_raw_concepts(yaml_path)
        stripped = personal_name.strip()
        if stripped:
            raw[key] = [stripped]
        else:
            raw.pop(key, None)
        _write_concepts(yaml_path, raw)
