"""viz_models.py - Modelo slim del Visualizador (v0.3.0+).

Refactor "una fuente de verdad": la Visualization ya NO almacena conceptos
ni evidencia. Solo guarda:
  - name + title (identidad)
  - categories (que csv_values son los circulos a, b, c, d, en que orden)
  - summary (resumen ejecutivo macro libre)

Todo lo demas (conceptos por region, items por region) se DERIVA en runtime:
  - Conceptos vienen de intersection_concepts.yaml (compartido con /sintesis)
  - Items vienen del CSV (compartido con /inventario, /cuestionario)

Region keys generados dinamicamente segun N categorias:
  N=0 -> []                                      (solo universo, sin circulos)
  N=1 -> "a"                                     (1 region: foco solitario)
  N=2 -> "a", "b", "ab"                          (3 regiones)
  N=3 -> "a", "b", "c", "ab", "ac", "bc", "abc"  (7 regiones)
  N=4 -> 15 regiones (combinatorias de a,b,c,d)   <- Ikigai clasico completo

Mas la region "out" (espacio negativo / universo) siempre presente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

# Letras canonicas para los 4 circulos del modelo Ikigai (L, G, W, P).
# Engine y producto comparten el mismo tope: N=4 (Edwards 1989, 15 regiones).
CIRCLE_LETTERS = ["a", "b", "c", "d"]

# Tope del motor de render Y del producto (el endpoint /categories tambien
# valida max 4). Dato y geometria coinciden en N=4.
MAX_CIRCLES = 4


def region_keys(n_circles: int) -> list[str]:
    """Todas las regiones de un Venn de N circulos, en orden de tamano creciente.

    Cada key es la concatenacion ordenada de las letras involucradas.
    Ejemplo N=3: ['a', 'b', 'c', 'ab', 'ac', 'bc', 'abc']
    N=0: [] (no hay regiones internas; solo el universo via "out")
    N=4: 15 regiones (Ikigai clasico completo; tope del motor).
    """
    if not (0 <= n_circles <= MAX_CIRCLES):
        raise ValueError(
            f"n_circles debe estar en [0, {MAX_CIRCLES}], vino {n_circles}"
        )
    letters = CIRCLE_LETTERS[:n_circles]
    keys: list[str] = []
    for size in range(1, n_circles + 1):
        for combo in combinations(letters, size):
            keys.append("".join(combo))
    return keys


def region_to_csv_values(region_key: str, categories: list[str]) -> list[str]:
    """Traduce una region_key del Venn (letras) a los csv_values que la componen.

    Ejemplo: region "ab" con categories ["3","1","2","4"] -> ["3", "1"]
    (porque a=categories[0]=3, b=categories[1]=1).

    Returns:
      Lista de csv_values en el orden posicional de las letras. Para "out"
      devuelve lista vacia (caso especial: representa el complemento del set).
      Letras que excedan len(categories) se ignoran (N=2 + region "abc"
      pediria un letter `c` inexistente; lo saltamos).
    """
    if region_key == "out":
        return []
    out: list[str] = []
    for letter in region_key:
        idx = CIRCLE_LETTERS.index(letter) if letter in CIRCLE_LETTERS else -1
        if 0 <= idx < len(categories):
            out.append(categories[idx])
    return out


@dataclass(slots=True)
class Visualization:
    """Una visualizacion Venn con N (0-4) categorias.

    Slim: solo el FRAMING (que circulos en que orden + resumen). El contenido
    de cada region (concepto + items) NO se almacena aqui; se deriva en runtime
    desde intersection_concepts.yaml + tulipan.jsonl.

    N=0 es el caso "solo universo": no se dibujan circulos, todo el espacio
    es el exterior, y la region "out" representa el universo completo.
    """

    name: str = "default"  # slug usado como filename
    title: str = "Default"  # nombre humano
    categories: list[str] = field(  # cuadrante csv_values; ej. ["1", "2", "3", "4"]
        default_factory=lambda: ["1", "2", "3", "4"]
    )
    summary: str = ""  # resumen ejecutivo macro de toda la viz (free text)

    def n_circles(self) -> int:
        return len(self.categories)

    def expected_region_keys(self) -> list[str]:
        """Las region keys del Venn (sin contar "out")."""
        return region_keys(self.n_circles())

    def all_region_keys(self) -> list[str]:
        """Region keys del Venn + "out" (siempre incluida al final)."""
        return [*self.expected_region_keys(), "out"]
