# Changelog

Todos los cambios notables a este proyecto se documentan acá. Sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y la versión
respeta [SemVer](https://semver.org/lang/es/).

---

## [Unreleased]

### Removed
- **Soporte N=5 del motor Venn**: el engine queda capado a 4 círculos, igual
  que el producto. Se eliminan las 5 elipses de Grünbaum (`viz_geometry.js`),
  la letra `e` de `CIRCLE_LETTERS` y `MAX_CIRCLES` baja de 5 a 4
  (`viz_models.py`). El endpoint `/visualizador/categories` ahora valida
  contra `MAX_CIRCLES` en vez de un 4 hardcodeado. Documentación (README) y
  tests alineados: dato, geometría y producto comparten el mismo tope, N=4.

---

## [3.0.0] — 2026-06-11

**Release pública: proyecto independiente, sin dependencias ni branding corporativo.**

Primer corte público bajo licencia MIT. Esta versión despersonaliza el
proyecto por completo y lo endurece para vivir como software libre autónomo.

### Removed
- **Integración con LLM externo** (cliente de IA y endpoint de sugerencias):
  eliminada de raíz —backend, UI, tests y la dependencia `httpx` de runtime.
  La síntesis de conceptos vuelve a ser 100% del usuario.
- **Función "share" / publicación a hosting interno**: el flag `--share` y el
  bloque `SHARE_REQUEST` ya no existen. El export estático (`--redact`) cubre
  el caso de compartir.

### Changed
- **Identidad visual nueva**: paleta del proyecto (tema tulipán 🌷) con tokens
  neutros `brand/accent/success/danger/ink`, reemplazando el esquema anterior.
- **Build de CSS portable**: `scripts/build_css.py` baja el CLI de Tailwind
  desde releases públicos de GitHub, con detección de plataforma (macOS/Linux/
  Windows). Instalación vía PyPI público, sin índices privados.
- **Branding**: el coach del cuestionario pasa a llamarse simplemente "Coach";
  se retiran mascotas y referencias de marca.

### Fixed (hardening post-review)
- **XSS** en el handler de error 500: el mensaje de excepción ahora se escapa
  con `html.escape` antes de inyectarse en el HTML.
- **Manejo de errores**: `HTTPException` se maneja explícito para que los 4xx
  conserven su status; logging unificado (`logging` en vez de `print`).
- **Validación de scores**: nuevo `Item.validate()` (rango 1-5) aplicado en el
  endpoint y en el import CSV (antes un CSV editado podía colar valores fuera
  de rango).
- **Concurrencia del store JSONL**: `append`/`update`/`delete`/
  `add_with_generated_id` e import CSV ahora toman `keyed_lock` por-archivo
  (mismo patrón que el storage YAML). Cierra una brecha de read-modify-write
  donde dos requests rápidos podían duplicar IDs o perder escrituras.
- **Repo**: se purga de la historia un binario de 46MB que se había colado y
  el workspace demo de runtime; `.gitignore` corregido.

### Added (infra)
- **CI** (`.github/workflows/ci.yml`): lint (ruff) + tipos (mypy) + tests
  (pytest), más un job que buildea el wheel, lo instala en un entorno limpio y
  corre un smoke test (CLI, `init --demo`, `/health`, render de página y CSS)
  para blindar que templates/static/`_demo_data` viajen dentro del paquete.

### Notes
- 525 tests verdes · ruff y mypy limpios.

---

## [2.9.1] — 2026-06-10

**Fix: callouts colapsaban a una sola linea fuera de Chrome.**

Los renglones de cada etiqueta (nombre + cruce) y de las 4 esquinas usaban
`dy="1.25em"` (relativo). Chrome lo respeta, pero Inkscape / Illustrator /
Microsoft Office / el visor de Windows NO soportan `em` en `dy` y colapsaban
todos los tspans a la misma `y` -> todo encimado en una linea.

### Fixed
- Cada tspan ahora se posiciona con `y` ABSOLUTO (name en `ly`, cruce en
  `ly+13`; esquinas en `y`, `y+18`, `y+33`). Funciona en todos los visores.
- Guard test: `render_venn_svg` no debe emitir ningun `dy=`.

### Notes
- Solo cambio en la plantilla compartida `_venn4_svg.html.j2` -> arregla el
  SVG descargable Y el snapshot. 547 tests verdes.

---

## [2.9.0] — 2026-06-10

**Claridad: el Venn-4 exportado ya no pierde palabras (callouts con lineas guia).**

En un Venn de 4 elipses hay 15 regiones diminutas. Antes el snapshot encimaba
el texto y el SVG descargable lo TRUNCABA ("Narrador que tr…"), traicionando
la premisa del Ikigai: claridad. Ahora cada region tiene un punto en su
centroide y una LINEA GUIA hacia su nombre COMPLETO en los margenes, con
subtitulo del cruce ("Gusto ∩ Mundo"). La corona (Ikigai central) va arriba.

### Added
- `_venn4_svg.html.j2`: plantilla del Venn-4 con callouts. **Fuente unica**
  compartida por el snapshot HTML y el .svg descargable (DRY).
- `export.render_venn_svg(project_dir)`: renderiza el Venn como SVG standalone
  (prolog XML + xmlns), reusando build_export_context.
- `GET /visualizador/venn.svg`: endpoint que sirve ese SVG como descarga
  (`Content-Disposition: attachment`).

### Changed
- `_venn4_hero.html.j2`: ahora es solo el chrome (figure + caption + leyenda)
  e incluye `_venn4_svg.html.j2`.
- Boton "Export SVG" (viz_main.js): en vez de serializar el Venn EN PANTALLA
  (que abrevia para caber), hace fetch del endpoint claro. El Venn interactivo
  sigue abreviando en pantalla (es correcto ahi); el export es la version
  imprimible sin perdida.

### Notes
- Verificado con Playwright: snapshot y .svg descargable identicos, cero
  truncado, corona con aire. 546 tests verdes (nuevos: test_venn_svg.py).

---

## [2.8.3] — 2026-06-10

**UX: el letrero del rail de capas ya no esta siempre presente (tapaba cards).**

El mini-nav lateral (dots por capa) mostraba el letrero de la zona ACTUAL de
forma permanente (`.layer-rail-dot.active::after { opacity: 1 }`), y se montaba
sobre las cards ("FUNDAMENTOS", "VINCULOS"...).

### Changed
- El letrero (tooltip `::after`) ahora aparece SOLO en `:hover` y
  `:focus-visible` (accesibilidad de teclado). "Donde estoy" se sigue
  indicando con el dot `.active` (azul, mas grande, con halo) — que es claro
  sin necesidad del letrero permanente.
- Cambio CSS puro (inline en `_sintesis_styles.html.j2`); no requiere rebuild
  de Tailwind. 543 tests verdes.

---

## [2.8.2] — 2026-06-10

**Fix x2 en /sintesis: propagacion sin refrescar + jerarquia de info en capas
superiores.**

### Fixed
- **Propagacion al guardar**: al bautizar una sintesis, las cards de capas
  superiores que la usan como ingrediente NO se actualizaban hasta refrescar.
  Ahora el endpoint `/sintesis/concept` devuelve la card guardada (swap normal)
  + todas las dependientes (superset estricto de sus circulos) como **OOB
  swaps** (`hx-swap-oob`), asi reflejan el nombre nuevo al instante. Guardar
  un primitivo ("1") propaga a toda card que contenga ese circulo.
- **Jerarquia de informacion** en cards de capa 2-3: antes los ingredientes se
  listaban con los primitivos (capa 0) arriba. Ahora se ordenan DESCENDENTE:
  los **componentes directos** (capa N-1, ya bautizados) van primero, en azul
  y a opacidad plena, etiquetados "COMPONENTES DIRECTOS"; los cimientos (capas
  mas bajas) bajan, se atenuan (opacity-60) y se etiquetan "CIMIENTO · Capa N".
  Ademas la notacion del header ("C1 ∩ C2 ∩ C3") se demota a gris chico en
  capa >=2 para que ceda protagonismo a las sintesis ya nombradas.

### Notes
- Rebuild de `static/tailwind.css` (clase nueva `opacity-60`).
- Verificado con Playwright: guardar en capa 1 actualiza la card de capa 2 sin
  reload; capa 2 muestra componentes directos arriba y primitivos atenuados.
  543 tests verdes (nuevos: propagacion OOB de pares y de primitivos).

---

## [2.8.1] — 2026-06-10

**Add: endpoint `/health` (liveness/readiness probe).**

Higiene de deploy: cualquier plataforma de hosting (k8s, contenedores, PaaS,
etc.) necesita un probe HTTP para saber si el proceso esta vivo.

### Added
- `GET /health` -> `200 {"status": "ok"}`. A nivel workspace (sin prefix
  /u/...). Deliberadamente SIN estado ni I/O: no toca el filesystem ni el
  workspace, asi el probe no falla por disco lento o workspace vacio.

### Notes
- Contexto: esta app es local-first y human-centered, no pensada para un
  deploy multi-tenant. Camino preferido para compartir: `ikigai export` ->
  un hosting estático (HTML autocontenido, sin infra). El /health queda igual
  como buena higiene por si en el futuro se hostea.

---

## [2.8.0] — 2026-06-10

**Cambio de rumbo: UNA sintesis por primitivo + boton "+ Item" para sumar
materia prima desde /sintesis.**

En v2.7.0 "mas de un concepto en los primitivos" se habia interpretado como
*multi-sintesis* (varias palabras/concepto por nodo, con pills). No era el
camino: el usuario queria UNA sola sintesis por primitivo y, en cambio, poder
AGREGAR ITEMS a la lista de cada circulo sin salir de la pagina.

### Removed (revierte el multi-concepto de v2.7.0)
- Cards de capa 0 vuelven al input UNICO de sintesis (igual que capas 1-3).
  Fuera las pills, el concepto "principal" y los secundarios.
- Endpoints `/sintesis/concept/add` y `/sintesis/concept/remove`.
- `intersection_concepts`: `load_personal_concepts()` / `_for()`,
  `add_personal_concept()`, `remove_personal_concept()`, el parametro
  `personal_concepts` de `compute_all_intersections` y el campo
  `personal_concepts` de cada card.

### Added
- Boton **"+ Item"** en la caja "Items que pertenecen a este circulo" de cada
  primitivo (positivos y sombras). Crea el item en el inventario con
  cuadrante=key y re-renderiza la card (lista + contadores) via HTMX.
- Endpoint `POST /sintesis/item/add`.
- `item_queries.tag_fields_for_cuadrante()`: helper publico que mapea
  circulo->tag al CREAR un item (positivos auto-taggean; sombras van por
  `cuadrante`). Mantiene el mapeo en UN lugar (DRY con /inventario).

### Notes
- El loader SIGUE tolerando YAML legacy (scalar o lista de la v2.7.0): si
  encuentra una lista toma el primero como principal. `save_personal_name`
  reescribe a scalar limpio.
- `bg-accent-140` (boton) era una clase nueva no usada antes -> hubo que
  rebuildear `static/tailwind.css` (mismo gotcha del scanner: clases que no
  existian no estaban compiladas). Boton marron accent-140 + texto blanco =
  contraste WCAG AA OK.
- Verificado con Playwright (click real del "+": items 1->2, item nuevo en la
  lista, sin endpoints viejos). 540 tests verdes (nuevos tests de
  /sintesis/item/add y tolerancia legacy del loader).

---

## [2.7.2] — 2026-06-10

**Fix: capa 1 de /sintesis mostraba 2 columnas en vez de 3 (clase Tailwind dinamica).**

Bug pre-existente detectado en v2.7.1. La grilla de las capas 1-2 usaba
`xl:grid-cols-{{ step.cols }}` — una clase construida en runtime por Jinja. El
scanner del Tailwind CLI standalone solo ve strings literales en el source, asi
que `xl:grid-cols-3` nunca se compilaba a static/tailwind.css → la capa 1 caia
al `md:grid-cols-2` previo. (Capa 0 funcionaba porque `xl:grid-cols-4` aparece
literal en otro lado.)

### Fixed
- Las clases de columnas ahora son literales (`'grid_cls': 'xl:grid-cols-3'` /
  `'xl:grid-cols-4'` en el dict de capas), asi el scanner las compila. Capa 1
  vuelve a 3 columnas y capa 2 a 4.
- Rebuild de `static/tailwind.css` con el CLI standalone (ahora incluye
  `grid-cols-3` y `grid-cols-4`).

### Notes
- Leccion: nunca construir nombres de clase Tailwind por interpolacion
  (`grid-cols-{{ x }}`, `text-{{ color }}`, etc.); el JIT/scanner no los ve.
  Usar siempre literales completos o un safelist en tailwind.config.js.
- Verificado con Playwright: capa 1 = 3 cols, capa 2 = 4 cols, alineacion
  subgrid intacta. 543 tests verdes.

---

## [2.7.1] — 2026-06-10

**Fix: alineacion entre cards en /sintesis (problema viejo) via CSS subgrid.**

Cada card era un flex-column independiente: cada banda (titulo, notacion C1/C2,
tagline, pregunta, items, producir, etc.) crecia a su altura natural y NADA se
alineaba entre cards hermanas. El header de "Desarrollar universos" (2 lineas)
empujaba todo distinto que "Pago" (1 linea). Resultado: cuadros de tamanos y
alineaciones distintas.

### Fixed
- Las cards de un mismo grid ahora comparten los row-tracks via `subgrid`: cada
  banda cae en la MISMA fila en todas las cards hermanas (capas 0, 1 y 2).
- Header: se elimino el `flex-wrap` que hacia saltar el badge "N items" a otra
  linea con titulos largos (badge ahora fijo arriba-derecha con `shrink-0`,
  titulo con `min-w-0` para envolver).
- `min-h` en el titulo (h3) para reservar 2 lineas → la notacion C1/C2/C3/C4
  cae a la misma altura aunque el titulo sea de 1 o 2 lineas.
- `grid-template-columns: minmax(0,1fr)` en la card para que el contenido ancho
  (pills, badges) no desborde al pasar la card a display:grid.

### Notes
- `--card-bands` por grid (positivos 5, sombras 4, intersecciones 6): subgrid
  exige mismo nº de hijos directos entre hermanas. El tagline ahora SIEMPRE
  se renderiza (banda fija) aunque este vacio.
- Degrada con gracia: navegadores sin subgrid (`@supports`) ven las cards como
  flex-column de siempre (sin la alineacion perfecta). Soporte: Chrome 117+,
  Firefox 71+, Safari 16+.
- Verificado con Playwright headless (no solo a ojo): screenshots de capa 0 y 1
  confirman bandas alineadas fila a fila y cards parejas abajo. 543 tests verdes.
- DETECTADO bug PRE-EXISTENTE (no de este fix, no tocado): capa 1 cae a 2
  columnas en vez de 3 porque `xl:grid-cols-{{ step.cols }}` es una clase
  Tailwind dinamica que el scanner no compila. Pendiente de decidir.

---

## [2.7.0] — 2026-06-10

**Feature: varios conceptos por primitivo en /sintesis (capa 0 multi-concepto).**

Antes cada nodo tenia UN solo nombre personal. Ahora los 8 primitivos de capa 0
(Amo/Bueno/Mundo/Pago + sus 4 sombras) aceptan VARIOS conceptos acunados,
mostrados como pills con boton de quitar + un form inline para agregar.

### Added
- `intersection_concepts`: `load_personal_concepts()` / `_for()` (listas
  completas), `add_personal_concept()`, `remove_personal_concept()`. El YAML
  ahora acepta valor `str` (legacy) o `list[str]`; un solo concepto se sigue
  guardando como scalar (compat + diffs limpios), varios como lista.
- Cada card lleva `personal_concepts` (lista). Las cards de capa 0 renderizan
  pills (primer concepto = principal, marcado) con quitar via HTMX y un input
  "+ Agregar". Capas 1-3 sin cambios (un concepto).
- Endpoints `/sintesis/concept/add` y `/sintesis/concept/remove`.

### Changed
- `compute_all_intersections` acepta `personal_concepts` opcional; si se omite
  se deriva del principal (1 concepto), asi los callers viejos no cambian.
- Refactor del router: `_is_valid_key`, `_unknown_key_response` y
  `_render_updated_card` compartidos por los 3 endpoints de concepto (DRY).

### Notes
- DISENO cero-riesgo (decision): el PRIMER concepto es el principal — es el
  unico que PROPAGA a las intersecciones y el que lee el visualizador.
  `load_personal_names()` sigue devolviendo `dict[str,str]` (el principal), asi
  que propagacion, visualizador y ~40 tests no se tocaron. Los conceptos extra
  son del primitivo y NO propagan (se puede extender despues si se quiere).
- Verificado end-to-end (no solo unit): add x2 -> pills + principal; remove ->
  promociona el siguiente. 543 tests verdes, ruff + mypy limpios.

---

## [2.6.1] — 2026-06-10

**Fix: el toast "Reflexion guardada" no se auto-descartaba (se quedaba para siempre).**

### Fixed
- `viz/viz_helpers.js` (`showToast`): el template de toasts no traia un
  `.toast-close`, asi que `closeBtn` era `null` y `closeBtn.onclick = remove`
  lanzaba un TypeError. Esa excepcion mataba la linea siguiente
  (`setTimeout(remove, 4000)`), el auto-descarte -> el toast PERSISTIA en
  pantalla (bottom-right) tras cada guardado en introspeccion/sintesis/viz.
  Fix: guard `if (closeBtn) closeBtn.onclick = remove;` para que el timer
  de 4s SIEMPRE se registre. Es la causa raiz; afecta a TODOS los toasts (DRY).

### Added
- Anti-pileup en `showToast`: al encadenar acciones rapidas (varias reflexiones
  seguidas), no se apilan toasts identicos; cada uno renueva al anterior con el
  mismo mensaje (`data-toast-msg` + CSS.escape).
- Boton de cierre accesible en el template de toasts (`_toasts.html.j2`):
  `<button aria-label="Cerrar notificacion">` con `&times;` y focus-ring
  (WCAG: las notificaciones deben poder descartarse manualmente). De paso, el
  `closeBtn` que el JS ya esperaba deja de ser codigo fantasma.

### Notes
- Causa encontrada por analisis estatico cuidadoso (la lecion del repo:
  el timer "existia" pero estaba muerto por una excepcion previa).

---

## [2.6.0] — 2026-06-10

**Exterminio de codigo muerto (YAGNI estricto).**

Barrido con `vulture` (+ filtrado manual de ~35 falsos positivos de framework:
rutas FastAPI, comandos CLI, campos de dataclass usados en templates). Lo que
quedaba era zombi real.

### Removed
- `algebra.dice()`, `algebra.overlap_coefficient()`: metricas de similitud sin
  ningun consumidor en la app (solo `jaccard` se usa). Tenian tests pero nada
  las llamaba — API especulativa.
- `algebra.preset_by_key()`: la app itera `PRESETS`, nunca buscaba uno por key.
- `portability.export_csv_text()`: superseded por `export_csv_from_items()` (el
  router ya usa esa desde el refactor D4). Era un wrapper path-based sin
  consumidor en produccion.
- `cli.ITEMS_NAME`: constante huerfana (el nombre real vive en
  `algebra_state.JSONL_NAME`).
- `navigation_context.resolve_master_viz()` + su parametro `preferred_name`:
  el arg nunca se pasaba ("compat con multi-viz futuro" = especulacion). Se
  colapso la indireccion de 2 funciones en 1 (`resolve_master_from_request`).
- Sus tests asociados (TestDice, TestOverlapCoefficient, preset_by_key,
  TestExportCsvText): no dejamos tests testeando el vacio. 541 -> 530 tests.

### Notes
- Cero cambio de comportamiento de cara al usuario. Verificado: vulture
  --min-confidence 80 limpio, ruff + mypy limpios, 530 tests verdes.

---

## [2.5.1] — 2026-06-10

**Docs: comentarios fosiles que mentian sobre CSV vs JSONL.**

La fuente de verdad es `tulipan.jsonl` desde v0.4, pero ~5 comentarios seguian
describiendo el CSV como el almacen principal — confundian a quien leyera el
codigo. Cero cambio de comportamiento.

### Changed
- `algebra.py`, `auditor.py`, `cuadrantes.py`, `viz_models.py`,
  `routers/visualizador.py`: comentarios/docstrings ahora dicen `tulipan.jsonl`
  (no "CSV") como materia prima.
- `cuadrantes.py`: el campo `csv_value` ahora documenta que su nombre es un
  artefacto historico (pre-v0.4 era columna CSV) y que hoy se guarda en el
  campo `cuadrante` del JSONL. NO se renombra el campo: esta en dataclass, JS
  (`dataset.csvValue`), templates y YAML — el churn no justifica el cosmetico.

### Notes
- CSV sigue VIVO pero solo en la frontera: import/export para humanos
  (`/csv/export`, `/csv/import` en inventario) y la migracion legacy idempotente
  `tulipan.csv -> tulipan.jsonl` (migrations.py). Adentro, todo es JSONL.

---

## [2.5.0] — 2026-06-10

**Refactor DRY: mata hardcodes de cuadrantes y el patron load-names repetido.**

Mismo espiritu que el fix D1 ("fuente de verdad unica"), aplicado a 3 fugas
que se habian colado despues.

### Added
- `cuadrantes.positive_csv_values()`: fuente de verdad para "los 4 circulos
  clasicos" (`['1','2','3','4']`), derivada de CUADRANTES. Nadie debe volver a
  hardcodear `{'1','2','3','4'}`.
- `intersection_concepts.load_personal_names_for(project_dir)`: conveniencia que
  colapsa el patron repetido `load_personal_names(yaml_path_for(dir))` (aparecia
  en 5 sitios de solo-lectura). El path del YAML pasa a ser detalle interno.

### Changed
- `sintesis.py`: el dict `primitive_concepts` ya no hardcodea el tuple
  `('1','1b',...,'4b')` — usa `all_csv_values()`. Antes rompia la promesa D1:
  agregar un 5º primitivo lo dejaba corto en silencio.
- `visualizador.py`, `export.py`, `auditor.py`: el set de positivos
  `{'1','2','3','4'}` (estaba triplicado) ahora deriva de `positive_csv_values()`.
- Los 5 call-sites de solo-lectura de nombres personales usan
  `load_personal_names_for()`. Los flujos load->modify->save
  (`save_personal_name`, `migrations`, `sintesis_save_concept`) mantienen el
  `yaml_path` explicito a proposito (leen y escriben el mismo path).

### Notes
- **YAGNI honesto**: se descarto un `compute_cards_for_project()` propuesto
  porque solo le servia limpio a 1 caller (los demas necesitan el `state`
  completo) — habria sido sobre-abstraccion.
- Refactor sin cambio de comportamiento: 537 tests previos siguen verdes; +4
  tests nuevos blindan las dos funciones fuente-de-verdad.

---

## [2.4.2] — 2026-06-10

**Export vendorizado: los snapshots se ven bien en CUALQUIER red.**

### Fixed
- `export/snapshot.html.j2` cargaba Tailwind desde `cdn.tailwindcss.com` (CDN).
  Un snapshot compartido DENTRO de la red corporativa se veia sin estilos (el proxy
  bloquea el CDN con 407). Ahora el CSS buildeado se **inyecta inline** en el
  HTML: el snapshot sigue siendo autocontenido y se ve bien con o sin internet,
  dentro o fuera de la VPN. (~31KB de CSS purgado inline, no megabytes.)
- `routers/visualizador.py` (`_error_page`): la pagina de error tambien usaba
  el CDN y clases genericas (`bg-gray-50`, `border-red-500`...). Ahora linkea a
  `/static/tailwind.css` (servido por el server) y usa la paleta `wm*` oficial.

### Added
- `export._read_vendored_css()` (cacheado): lee `ikigai/static/tailwind.css` y
  lo inyecta en el render del snapshot via `tailwind_css`.

### Changed
- `tailwind.config.js`: el scan de `content` ahora incluye `./ikigai/**/*.py`,
  para que las clases del HTML inline (como el `_error_page`) entren al build.

### Notes
- **Deuda de CDN cerrada al 100%**: cero referencias a CDNs externos en codigo
  (solo quedan menciones en comentarios que explican POR QUE no usarlos).

---

## [2.4.1] — 2026-06-10

**Limpieza: Alpine.js muerto fuera.**

### Removed
- `sintesis.html.j2` cargaba Alpine.js desde `unpkg.com` (CDN) pero **ninguna**
  plantilla usa una sola directiva Alpine (`x-data`, `x-show`, `@click`...).
  Toda la interactividad es htmx + JS vanilla. El `<script>` era un fosil de
  una iteracion vieja que, ademas, pegaba a un CDN que el proxy corporativo
  bloquea (407) — un request desperdiciado + error en consola en VPN. Borrado:
  dependencia muerta menos (YAGNI) y una llamada externa menos.
- Comentario de `_base.html.j2` que listaba "Alpine" como ejemplo de
  `extra_head` (ya no aplica).

### Notes
- Deuda conocida que QUEDA (documentada, no urgente): los templates de
  **export** (`export/snapshot.html.j2` y el HTML inline de
  `routers/visualizador.py`) aun usan `cdn.tailwindcss.com`. Es intencional
  para snapshots que se abren en una maquina con internet libre; solo se verian
  sin estilos si se comparten DENTRO de la red corporativa.

---

## [2.4.0] — 2026-06-10

**Wizard de creacion simplificado: un solo campo + slug automatico.**

Antes el wizard `/_new` pedia DOS campos: un *Nombre* restringido a
`[a-z0-9_-]` (el slug, que el usuario tenia que pensar como
filesystem/URL-safe) y un *Titulo* libre. Confuso: la gente leia "solo
minusculas sin caracteres especiales" y creia que el nombre bonito tambien
estaba limitado. Ahora se pide **un solo nombre libre** y el slug se deriva
solo.

### Added
- **`workspace.slugify(text)`**: convierte texto libre en slug URL-safe
  (normaliza unicode acentos->ASCII, minusculas, separadores->`-`, colapsa
  y recorta a 50 chars). Devuelve `""` si no hay nada slugificable.
- **`workspace.derive_unique_slug(workspace, text)`**: slugify + manejo de
  borde: fallback a `"ikigai"` si queda vacio, sufijo `-2`, `-3`... ante
  colision con un ikigai existente o un slug reservado.
- **`workspace.RESERVED_SLUGS`**: set unico de slugs que chocarian con rutas
  del server (`u`, `static`, `docs`, `redoc`). `_new` ya lo cubre el regex.
- **`GET /_new/slug-preview`**: endpoint HTMX que devuelve el slug derivado en
  vivo mientras el usuario teclea. Reusa `derive_unique_slug` (fuente unica:
  el preview NUNCA miente respecto a lo que `create_ikigai` hara).
- **`tests/test_workspace.py`**: +37 tests (slugify, derive_unique_slug,
  create_ikigai con auto/explicit slug, y los 3 endpoints del wizard).

### Changed
- **`new_ikigai.html.j2`**: un campo principal *"Nombre del ikigai"* (libre,
  admite mayusculas/acentos/emojis) + preview del slug en vivo + un
  `<details>` "avanzado" plegado para forzar el slug a mano (el 1%).
- **`create_ikigai(workspace, title, slug=None)`**: firma nueva. Recibe el
  nombre amigable; deriva el slug si no se da uno explicito. Valida el slug
  manual (formato + reservado + colision).
- **`POST /_new`**: ahora toma `name` (libre) + `slug` opcional; deriva el
  slug del name si viene vacio; redirige al slug final real.

### Stats
- 537 tests verdes (+37), ruff + mypy clean.

---

## [2.3.2] — 2026-06-08

**Render arreglado: la app dejaba de tener estilos en la red corporativa.**

### Fixed
- `_base.html.j2` cargaba Tailwind (`cdn.tailwindcss.com`) y htmx
  (`unpkg.com`) desde CDNs públicos que el proxy corporativo bloquea con
  **407** — el navegador nunca bajaba el CSS y la app se veía sin estilos.
  Ahora los assets se sirven **localmente** desde `/static/`.

### Added
- `ikigai/static/tailwind.css` — CSS buildeado con el CLI standalone (escanea
  templates + JS; incluye los colores `wm*` que antes vivían como config de
  runtime del Play CDN).
- `ikigai/static/htmx.min.js` — htmx vendorizado.
- `tailwind.config.js` + `tailwind.input.css` — inputs del build.
- `scripts/build_css.py` — descarga el CLI desde los releases públicos de
  GitHub y re-buildea el CSS de forma reproducible.

### Notes
- El CLI `_tw_cli.exe` (~40MB, platform-specific) queda gitignored.
- 500 tests verdes (ningún test dependía de los CDNs).

---

## [2.3.1] — 2026-06-08

**M1 — último cabo del bug-hunt. Bug-hunt 100% cerrado.**

### Fixed
- El import CSV no validaba que el id concordara con el cuadrante: podías
  importar `id=1.001, cuadrante=3` — un item incoherente que además rompía
  `next_id_for_cuadrante` (que secuencia por prefijo del id), causando
  colisiones/saltos al agregar items después. Ahora
  `parse_and_validate_csv_text` exige la convención `<cuadrante>.<NNN>`: el
  prefijo del id debe ser exactamente el cuadrante (rechaza con número de fila).

### Stats
- +4 tests (mismatch, id sin punto, sombra ok, sombra mismatch). **500 verdes**,
  ruff + mypy clean.
- **Bug-hunt cerrado al 100%** (B1–B3, D1–D4, M1). El código quedó impecable.

---

## [2.3.0] — 2026-06-08

**Cierre del bug-hunt: concurrencia consistente + perf del store (D2, D4).**

### Added
- **`ikigai/locks.py`** — `keyed_lock(key)`: locks por-clave en proceso,
  fuente única del patrón para serializar read-modify-write. `viz_storage`
  deja de tener su propio registro de locks duplicado y lo reusa.
- **`jsonl_store.add_with_generated_id()`** — genera id + append en UNA sola
  lectura del store.
- **`portability.export_csv_from_items()`** — variante pura del export que
  recibe items ya leídos (`export_csv_text` ahora delega en ella).

### Fixed
- **D2 — locking inconsistente en escrituras de concepts**: `save_personal_name`
  (escrito por `/sintesis` **y** `/visualizador` al MISMO YAML) no tomaba lock.
  Dos writes concurrentes a keys distintas partían del mismo estado y el último
  ganaba — **lost update**. Ahora serializa load→modify→save con lock por archivo.

### Changed
- **D4 — fin de la doble lectura completa del store**:
  - `POST /item` hacía `next_id_for_cuadrante` (read_all) + `append` (re-read_all
    para chequear duplicados) = **2 lecturas O(n) por item**. Ahora una sola.
  - `GET /csv/export` leía el store y, si había items, lo re-leía dentro de
    `export_csv_text`. Ahora lee una sola vez.

### Stats
- +10 tests (locks, concurrencia D2, `add_with_generated_id`, `export_from_items`).
  496 verdes, ruff + mypy clean.
- **Bug-hunt cerrado.** Pendiente menor: **M1** (import CSV no valida que el
  prefijo del id concuerde con el cuadrante).

---

## [2.2.2] — 2026-06-08

**B3 — el store ya no se vuelve ilegible por un crash a mitad de append.**

### Fixed
- Antes, un `append` interrumpido a mitad de línea (Ctrl-C, corte de luz)
  dejaba JSON truncado; `read_all` hacía `json.loads` sobre esa línea y
  **crasheaba — el store ENTERO quedaba ilegible** (pérdida total de items).
- Ahora el daño está acotado y se auto-sana:
  - **`read_all` resiliente**: salta líneas no parseables (o que no son objeto
    JSON) con `logging.warning` y sigue leyendo el resto.
  - **`append` auto-protegido**: si el archivo no termina en `\n` (línea torn
    previa), inserta el separador antes de escribir, para que el item nuevo no
    se fusione con la línea rota (lo que perdería ambos).
  - **auto-sanado**: el siguiente `update`/`delete` reescribe desde `read_all`
    y purga la línea rota.

### Stats
- +6 tests (línea truncada, rota en medio, JSON no-objeto, no-merge tras torn,
  sin blank-line extra, self-heal). 486 verdes, ruff + mypy clean.
- Pendiente del bug-hunt: **D2** (locking inconsistente en YAML), **D4**
  (doble lectura del store), **M1** (import CSV no valida prefijo-id vs cuadrante).

---

## [2.2.1] — 2026-06-08

**Cacería de bugs + deuda técnica.** Batch de fixes seguros surgido de una
revisión de código. Sin cambios de comportamiento visible salvo el rechazo
de ediciones inválidas (B1).

### Fixed
- **B1 — PATCH de item validaba a medias**: `PATCH /inventario/item/{id}`
  no validaba el `cuadrante` (sí lo hacía `POST`). Se podía editar un item a
  `cuadrante="99"` y dejarlo sin clasificación — corrupción silenciosa.
  Ahora rechaza con 400 vía `find_side`.
- **B2 — `atomic_io` prometía `fsync` y no lo hacía**: ahora hace
  `flush` + `os.fsync` ANTES del `os.replace` (durabilidad real ante corte de
  luz / Ctrl-C) y limpia el `.tmp` huérfano si algo falla a mitad.

### Changed
- **D1 — fin de la triplicación de `VALID_CUADRANTES`**: el set de cuadrantes
  válidos y `all_csv_values()` viven solo en `cuadrantes.py` (la fuente de
  verdad). `jsonl_store`, `portability` y `visualizador` los importan en vez
  de hardcodear `'1234'`. Ahora sí: agregar/quitar un primitivo se propaga
  solo (el comentario "edita SOLO este archivo" dejó de ser mentira).
- **D3 — API pública para reemplazo total**: `jsonl_store._write_all_atomic`
  (privado) promovido a `jsonl_store.write_all`. `portability` y los tests
  dejan de acceder a un `_privado` de otro módulo.
- Docstring de `jsonl_store` corregido: ya no afirma que `append` es atómico
  (no lo es; queda anotado como TODO B3).

### Stats
- 14 archivos, +151 / −50 líneas. 480 tests verdes (+7 nuevos), ruff + mypy clean.
- Pendiente (no en este batch): **B3** (append no-atómico), **D2** (locking
  inconsistente en escrituras de YAML), **D4** (doble lectura del store).

---

## [2.2.0] — 2026-06-08

**Introspección inline**: la pantalla de Cuestionario abandona el flujo
"chat paso a paso" (un cursor que revelaba las preguntas de a una) por un
diseño donde **las 8 preguntas se muestran de una**, cada una con su propio
formulario de reflexión. Más directo, menos JS, y respeta que la gente no
piensa en orden lineal.

### Changed
- **Form inline por pregunta** (`_cuestionario_section_block.html.j2`): los 8
  bloques se renderizan server-side siempre (con o sin items previos), cada
  uno con su `section-answer-form` propio. Las pills caen al lado de SU
  pregunta, no al fondo del chat.
- **Router `cuestionario.py`**: siempre arma las 8 secciones; se elimina la
  lógica de `first_unanswered_index` / cursor.

### Removed
- **~120 líneas de JS de cursor** en `cuestionario.html.j2`:
  `askCurrentQuestion`, `nextQuestion`, `ensureSectionBlock`,
  `pointFormToSection`, `updateProgress`, la barra de progreso y el
  `FIRST_UNANSWERED_INDEX`. El handler queda en `onSectionAnswer` (limpia
  textarea, reenfoca, refresca el strip de su sección).

### Fixed
- Comentario stale en `_cuestionario_section_block.html.j2` que aún
  describía el cursor inexistente.
- **Docs drift**: el README creía que la versión era 2.0.0 y no documentaba
  el Venn engine v2 (2.1.0). Ahora el README refleja la realidad: features
  del visualizador v2, introspección inline, y la tabla de arquitectura
  completa (se habían quedado fuera `atomic_io`, `migrations`, `stats`,
  `navigation_context`, `cli`).

### Stats
- 4 archivos cambiados, +76 / −243 líneas (refactor).
- 473/473 tests verdes, mypy clean, ruff clean.

---

## [2.1.0] — 2026-06-04

**Venn engine v2**: el motor de geometría del visualizador deja de depender
de hitboxes hardcodeados `{x,y,r}` por N y pasa a derivar todo de la
geometría. Cinco mejoras, ordenadas por impacto visual.

### Added
- **Highlight de región REAL** (mejora #1, alta): al hacer hover o activar
  una región se ilumina su **forma exacta** (lúnula/triángulo curvo), no un
  círculo aproximado. Construido con `buildHighlights()`: inclusión vía
  `clip-path` encadenados, exclusión vía `<mask>` negro. Estilos `.venn-hl`
  (`.hover` 0.55 / `.active` 0.85) en `viz.css`.
- **Soporte N=5 completo** (mejora #2, alta): se resuelve el `"abcde"` a
  medias. El motor dibuja las **5 elipses de Grünbaum** (coords pyvenn) con
  sus 31 regiones. `region_keys()` y `CIRCLE_LETTERS` suben a `MAX_CIRCLES=5`
  (el app clásico sigue restringido a 4; el engine es la verdad del tope).
- **Hint de descubribilidad** (mejora #5, baja): los badges de regiones
  **con concepto** laten suave 3 veces al cargar (`@keyframes
  venn-badge-pulse`), invitando al click. Respeta `prefers-reduced-motion`.
- **`TestVennGeometryRegression`**: geometría JS portada a Python (sin Node
  en CI). Verifica que toda región sea clickeable, la robustez de la
  región-astilla de N=5, y un tripwire del valor de `step`.

### Changed
- **Hitboxes DERIVADOS de la geometría** (mejora #3, media): adiós a los
  `{x,y,r}` manuales por N. `computeRegionGeometry()` muestrea el lienzo,
  clasifica cada punto a su región, calcula centroide + área, refina
  (centroide adentro de regiones no-convexas) y descongestiona por repulsión
  (`declutter`). Cero tuning frágil; sirve para cualquier N.
- **Paleta GENERATIVA** (mejora #4, media): `colorFor(i, n)` reemplaza el
  array fijo de 4 colores. Preserva la identidad del proyecto (rosa/ámbar/verde/
  rojo + violeta para el 5º) y genera matices por golden-angle más allá de 5.
- **Sampling `step` 3→2**: el Venn de 5 elipses tiene regiones-astilla (ej.
  `"bc"`) que con step=3 captaban UNA sola muestra → hitbox de radio mínimo
  en un punto, frágil ante redondeo float y potencialmente inclickeable.
  step=2 lleva la región más chica de 1 a 11 muestras. El sampling corre
  una vez por render, así que el costo ~2.25× es imperceptible.

### Stats
- 6 archivos cambiados, +468 / -126 líneas (dos commits: engine v2 + fix).
- 474/474 tests verdes.

---

## [2.0.0] — 2026-05-29

**Breaking release**: introduce el modelo **workspace + multi-ikigai**. Un
único directorio puede albergar N ikigais (uno por subdir), accesibles via
`/u/<slug>/<seccion>` con switch instantáneo desde el chrome.

### Added
- **`ikigai/workspace.py`**: discovery de ikigais en un workspace,
  validación de slugs (`[a-z0-9_-]{1,49}`, sin colisión con rutas reservadas
  `_new`, `u`, `static`, `docs`), y `create_ikigai()`.
- **`ikigai/render.py`**: helper `render()` que inyecta `ikigai_url`
  (`/u/<slug>`) y la lista de ikigais en todo template. Single source of
  truth para el chrome multi-ikigai.
- **`tests/conftest.py`**: `PrefixedTestClient` que envuelve `TestClient`
  y prepende `/u/test/` automáticamente, evitando reescribir ~120 URLs en
  tests legacy. Wrapper transparente (forwarding via `__getattr__`).
- **Endpoints workspace-level**:
  - `GET /` → redirige al primer ikigai alfabético, o a `/_new` si está vacío.
  - `GET /_new` → wizard de creación de ikigai (form).
  - `POST /_new` → crea el ikigai y redirige a `/u/<slug>/introspeccion`.
- **Dropdown switcher** en el chrome (`_ikigai_switcher.html.j2`): cambia
  entre ikigais o crea uno nuevo sin tocar CLI.

### Changed (BREAKING)
- **CLI `ikigai serve <dir>`**: ahora `<dir>` es un **workspace**, no un
  project-dir. Sirve todos los ikigais bajo `/u/<slug>/...`.
- **CLI `ikigai export <dir>`**: requiere `--ikigai <slug>` para identificar
  qué ikigai exportar. Default out: `<workspace>/<slug>/output/<slug>-ikigai.html`.
- **CLI `ikigai init <dir> --demo`**: crea workspace con `mariana/` adentro
  (antes creaba el project-dir directamente con el demo en la raíz).
- **Rutas web**: todas las secciones (`/inventario`, `/sintesis`,
  `/visualizador`, `/introspeccion`) viven ahora bajo `/u/<slug>`.
- **Templates**: todas las URLs absolutas usan `{{ikigai_url}}` en vez de
  hardcodear `/...`. JS lee `window.IKIGAI_URL` para fetchs HTMX.

### Migration (v1.x → v2.0)
Trivial, sin herramienta automática porque es 1 comando:
```bash
# Antes:  ikigai serve ~/mi-ikigai/
# Después:
mkdir ~/mi-workspace/ && mv ~/mi-ikigai ~/mi-workspace/yo
ikigai serve ~/mi-workspace/      # → /u/yo/introspeccion
```
Un `serve` apuntando a un dir-sin-subdirs-válidos te lo dice explícitamente
(no destruye nada y muestra el path al wizard `/_new`).

### Stats
- 31 archivos cambiados, +763 / -307 líneas.
- 457/457 tests verdes, mypy clean, ruff clean.

---

## [1.0.0] — 2026-05-29

Primera release estable. El formato del disco está **congelado**: cualquier
cambio incompatible futuro se libera como v2.x con migración explícita.

### Added

- **Proyecto demo** (`examples/demo/`) con un Ikigai ficticio completo
  (Mariana, ingeniera senior en WM). Permite ver el flow end-to-end sin
  sembrar items desde cero. Acompañado de tests E2E (`tests/test_demo_project.py`)
  que cachan regresiones de formato antes de que un usuario las vea.
- **Módulo `ikigai.atomic_io`** con `atomic_write_text()` para escritura
  segura a disco (tmp-file + `os.replace`). Cierra el data-loss silencioso
  cuando un Ctrl-C interrumpía una escritura YAML.
- **Módulo `ikigai.migrations`** que materializa las migraciones one-shot
  que el README prometía pero el código no implementaba:
  - `tulipan.csv` pre-v0.4 → `tulipan.jsonl` con backup `.csv.bak`
  - `visualizations/*.yaml` con `regions[].concept` pre-v0.3 → `intersection_concepts.yaml`
- **LICENSE** MIT explícito.
- **Quickstart de 60 segundos** en el README.

### Changed
- **Distribution rename: `ikigai` → `ikigai-tulipan`** en `pyproject.toml`.
  Otro autor ya había squateado el nombre `ikigai` en
  `el índice corporativo`. Para evitar colisión y la confusión de
  que un usuario haga `uv pip install ikigai` y se baje el equivocado,
  cambiamos el distribution name. **El Python module sigue siendo `ikigai`**:
  `import ikigai`, `ikigai serve` y `ikigai init` siguen funcionando igual.
  Solo cambia `pip install` y el lookup de `importlib.metadata.version()`.
- **Single source of truth para versión**: `__version__` se lee de
  `importlib.metadata.version("ikigai")`. Antes vivía duplicado en
  `pyproject.toml` y `ikigai/__init__.py` (DRY violation).
- **`/algebra` renombrado a `/sintesis`** en todas las rutas, templates y
  navegación. El módulo matemático puro (`algebra.py`) conserva su nombre
  por ser un concepto correcto.
- **Test gigante partido**: `tests/test_intersection_concepts.py` (634 LoC,
  sobre el límite de 600) se separó en sus dos preocupaciones naturales:
  el módulo puro y el endpoint HTTP (`tests/test_intersection_endpoints.py`).

### Fixed
- **Escrituras YAML no atómicas** en `intersection_concepts.save_personal_name()`:
  si el proceso moría a mitad de write, el archivo quedaba truncado y el
  loader tolerante devolvía `{}` silenciosamente, perdiendo todo el árbol
  de síntesis del usuario sin warning.
- Comentarios y referencias stale del rename `/algebra → /sintesis`
  (sub-IDs en HTMX, tabs CSS, header de `_sintesis_styles.html.j2`).
- Campo fantasma `partial` en `viz_models.region_to_csv_values()` y rename
  `csv_path` → `items_path` en navegación (artefactos del refactor JSONL).

### Removed
- Wizard de 5 pasos legacy (`_algebra_set_card.html.j2`, etc.) — 116 LoC
  muertos tras el refactor a "scroll dramatúrgico".

---

## [0.4.0] — pre-1.0 — JSONL como single source of truth

- **BREAKING (con migración automática)**: el store interno pasó de
  `tulipan.csv` a `tulipan.jsonl` (append-only, una línea JSON por item).
  El CSV sigue existiendo solo como puente humano (import/export en
  `/inventario`).
- **Migración one-shot**: la primera vez que `serve` o `export` ven un
  `tulipan.csv` sin `tulipan.jsonl`, el CSV se importa al JSONL y el
  original se renombra a `tulipan.csv.bak`. Idempotente, cero pérdida.
  (NOTA: la implementación real de esta migración llegó en 1.0.0; en
  0.4.0 sólo estaba documentada.)
- **Adiós CSV escape hell**: los textos pueden contener comas, comillas,
  newlines y emojis libremente.
- **`models.py` trimmed**: eliminado dead code (`Region`, `Universo`,
  `Circle`, `CurationEntry`, `AuditReport`, `VALID_REGIONS`).
- **Nuevos módulos**: `jsonl_store.py`, `item_queries.py`, `portability.py`.
  Eliminado `csv_writer.py`.

---

## [0.3.0] — Una fuente de verdad

- **BREAKING**: los conceptos acuñados ya no viven en
  `visualizations/<name>.yaml`. Ahora viven en `intersection_concepts.yaml`
  compartido con Síntesis. La viz solo guarda framing (orden de cuadrantes
  + resumen). Los items por región se derivan del CSV via tags.
- **Eliminado multi-viz**: una sola visualización "default" por proyecto.
- **N=0 y N=1 válidos**: el Venn acepta cero círculos (solo universo) o
  uno (foco solitario), no solo 2–4.
- **Cajones del visualizador read-only**: editar/borrar items va por
  Inventario, donde pertenece.
- **Net**: −476 líneas de código.

---

## [0.2.x] — Multi-viz + AI suggestions

Multi-viz CRUD con tabs, drag-and-drop de items a regiones, AI suggestions
via un LLM externo, snapshot HTML compartible.
