# ikigai 🌷

> **Web app interactiva para construir tu Ikigai personal (o el de tu equipo) a través de un proceso de síntesis dialéctica, desde la captura cruda hasta el núcleo del propósito.**

Útil para autoconocimiento, sesiones de mentoring, planeación de carrera o cualquier ejercicio donde necesites transformar el caos de observaciones sueltas en una estructura de sentido coherente.

---

## 🚀 Quickstart (60 segundos)

```bash
# 1. Instala (desde PyPI público)
uv pip install ikigai-tulipan

# 2. Crea un workspace con el demo (Ikigai ficticio ya completo: Mariana)
ikigai init mi-workspace/ --demo
ikigai serve mi-workspace/ --open      # → abre /u/mariana/introspeccion

# 3. Crea TU ikigai junto al demo, desde el chrome:
#    dropdown "Ikigai" → "+ Nuevo ikigai" → elige tu slug → listo.

# (alternativa CLI) workspace vacio + wizard del browser:
ikigai init mi-workspace-personal/
ikigai serve mi-workspace-personal/ --open   # → /_new (wizard de creacion)
```

> ℹ️ **Nombre del paquete vs. del comando**: el distribution name es `ikigai-tulipan` (para evitar colisión con otro `ikigai` en PyPI), pero el CLI y el Python module siguen llamándose `ikigai`. Es decir: instalas `ikigai-tulipan`, corres `ikigai`, importas `import ikigai`.

Vas a estar en http://127.0.0.1:8000 viendo el flow Introspección → Síntesis → Visualizador (con el Inventario como vista de gestión) para el ikigai seleccionado. Los items se guardan localmente en `mi-workspace/<ikigai>/tulipan.jsonl` (append-only JSONL — git-friendly, sin lock-in).

> 💡 **Un workspace, N ikigais.** Podés tener tu propio ikigai, el de tu pareja, el de tu equipo Q3, y un sandbox — todos al lado, con switch instantáneo en el chrome.

---

## 🗺️ El Proceso

Ikigai no es solo un formulario; es un camino para guiar tu pensamiento. La
navegación principal es un **toggle de 3 secciones** siempre visible:

| Sección (ruta) | Función | Metáfora |
| :--- | :--- | :--- |
| **🧘 Introspección** (`/introspeccion`) | **Descubrimiento Guiado.** Preguntas evocadoras para sacar items del subconsciente y darle forma a tu inventario. | 🌱 **La Semilla** |
| **∑ Síntesis** (`/sintesis`) | **Scroll dramatúrgico.** El proceso dialéctico de unir ramas (dominios ∩ intersecciones) hasta llegar al centro. | ⚗️ **El Laboratorio** |
| **🌷 Visualizador** (`/visualizador`) | **Resultado Espacial.** Proyección final en un mapa de Venn para reflexión, exportación y narrativa. | 🌷 **El Tulipán** |

Además existe el **Inventario** (`/inventario`) como vista de **gestión de
materia prima** (organizar, limpiar y etiquetar los items crudos con sus
tags 🏗️ *La Cantera*). No vive en el toggle: se llega a él desde los enlaces
"añade items aquí →" del Visualizador y de la Introspección.

---

## Lo que ves al correrlo

```powershell
ikigai serve mi-workspace/ --open
→ http://127.0.0.1:8000/
  → redirige a /u/<primer-ikigai>/introspeccion (alfabético)
  → o a /_new si el workspace está vacío (wizard de creación)
```

La app mantiene un **Toggle de Navegación** siempre visible para saltar entre las etapas del proceso (Introspección / Síntesis / Visualizador), más un **dropdown de Ikigai** en el chrome para cambiar entre ikigais del workspace o crear uno nuevo.

---

## 🏘️ Workspace + multi-ikigai

Un **workspace** es un directorio que contiene N **ikigais** (uno por subdir). Cada ikigai vive aislado en su propia carpeta con su propio `tulipan.jsonl`, `intersection_concepts.yaml`, etc. El nombre del subdir es el "slug" del ikigai y aparece en las URLs (`/u/<slug>/...`).

**Por qué multi-ikigai en un workspace en vez de un dir por ikigai:**
- **Switch instantáneo** desde el chrome (no hay que matar/relanzar el server).
- **Comparación cruzada** natural: tu ikigai personal, el de tu pareja, el de tu equipo — mismo server, links cortos.
- **Privacidad por slug**: cada ikigai es un sandbox; no hay leak entre uno y otro.
- **Backup atomic**: un solo `git init` cubre todos tus ikigais.

Reglas de slug (validadas server-side):
- Solo `[a-z0-9_-]`, 1-50 caracteres.
- No empieza con guion ni número solo.
- Reservados: `_new`, `u`, `static`, `docs`, `redoc` (cualquier path con `_` o reservado del server).

**El usuario no escribe el slug a mano.** El wizard (`/_new`) pide un solo
campo libre — el *nombre del ikigai*, que admite mayúsculas, acentos y emojis
(ej. `María López` o nombres con emoji). El slug se **deriva automáticamente** (`slugify`:
unicode→ASCII, minúsculas, separadores→`-`) y se muestra en vivo como preview
(HTMX). Las colisiones se resuelven con sufijo (`maria-lopez-2`); un nombre sin
caracteres slugificables cae a `ikigai`. Un `<details>` "avanzado" permite forzar
el slug a mano para el 1% que lo necesite.

---

## Features Principales

### ⚗️ Síntesis (El Scroll Dramatúrgico)
- **Árbol de Síntesis** (v0.3.0): No es solo ver datos, es acuñar vocabulario propio.
- **Capas de Naming**:
  - **Nivel 0**: Acuña la síntesis de tus 4 dominios base (Amo, Bueno, Mundo, Pago).
  - **Nivel 1-2**: Nombra las intersecciones binarias y ternarias (Pasión, Misión, etc.).
  - **Nivel 3**: Nombra tu **✨ Ikigai** (el centro).
- **Feedback en Tiempo Real**: Los conceptos que acuñas aquí se reflejan instantáneamente en el Visualizador.
- **Matriz de Similitud**: Análisis de Jaccard para ver qué tanto se parecen tus intersecciones entre sí.

### 🌷 Visualizador (El Mapa Narrativo)
- **Una fuente de verdad**: Los conceptos vienen de Síntesis, los items del Inventario.
- **Venn Dinámico**: Badges que muestran tus **palabras-síntesis** en lugar de números.
- **Venn engine v2** (v2.1.0): la geometría ya no depende de hitboxes hardcodeados.
  - **N = 0 a 5 círculos**: desde solo-universo hasta las 5 elipses de Grünbaum (31 regiones). El app clásico opera 0-4; el engine soporta hasta 5.
  - **Highlight de forma real**: al hacer hover/activar una región se ilumina su **forma exacta** (lúnula/triángulo curvo), no un círculo aproximado.
  - **Hitboxes derivados de la geometría**: se muestrea el lienzo y se calcula centroide + área por región → cero tuning frágil, sirve para cualquier N.
  - **Paleta generativa**: los 4 colores base del proyecto (rosa/ámbar/verde/rojo + violeta para el 5º) extendidos por golden-angle más allá de 5 círculos.
  - **Hint de descubribilidad**: los badges con concepto laten suave al cargar (respeta `prefers-reduced-motion`).
- **Tooltip Inteligente**: Hover para ver el concepto completo si es muy largo.
- **Barra de Progreso**: Visualiza cuánto te falta para terminar de sintetizar todo tu árbol.
- **Export SVG**: Descarga el diagrama vectorial para tus presentaciones.

### 🌱 Introspección (Génesis)
- Preguntas evocadoras diseñadas para romper el "bloqueo del escritor" y generar los primeros items.
- **Diseño inline** (v2.2.0): las 8 preguntas (4 pares +/-) se muestran de una, cada una con su propio campo de reflexión. Sin cursor lineal: respondés donde quieras y en el orden que quieras.
- Cada pregunta muestra en paralelo su **resultado real** (la distribución de tus respuestas por círculo), que se actualiza al instante con cada reflexión.

### 🏗️ Inventario (Gestión Local-First)
- **Single Source of Truth**: Los items viven en un JSONL append-only (`tulipan.jsonl`).
- **Edición Inline**: Doble-click para corregir, Ctrl+Z para deshacer.
- **Tags**: El lugar donde decides a qué círculos pertenece cada item.

---

## Estructura de un workspace

```
mi-workspace/                          ← el dir que le pasás a `ikigai serve`
├── mariana/                           ← un ikigai (slug = nombre del subdir)
│   ├── tulipan.jsonl                  ← Items crudos (única fuente de verdad)
│   ├── intersection_concepts.yaml     ← Vocabulario acuñado (tu árbol de síntesis)
│   ├── visualizations/
│   │   └── default.yaml               ← Framing del Venn (orden y resumen)
│   └── output/                        ← Snapshots generados por `ikigai export`
├── juan/                              ← otro ikigai, totalmente independiente
│   ├── tulipan.jsonl
│   └── …
└── q3-equipo/                         ← · podes tener tantos como quieras
    └── …
```

Un ikigai es "válido" cuando su subdir contiene un `tulipan.jsonl` (aunque sea vacío). El server descubre los ikigais escaneando los subdirs del workspace al arrancar.

**Separation of concerns** dentro de cada ikigai: cada archivo cambia a un ritmo distinto y tiene un único dueño.
- `tulipan.jsonl` crece cada vez que capturás/editás un item (Inventario). Append-only: cada índice es una línea JSON independiente.
- `intersection_concepts.yaml` cambia cuando acuñás nombres para intersecciones (Síntesis o Visualizador).
- `visualizations/default.yaml` solo cambia cuando reordenás cuadrantes o editás el resumen macro.

### Schema: `tulipan.jsonl`

Una línea JSON por item. Solo `id`, `item` y `cuadrante` son obligatorios; todo lo demás se omite si está vacío para mantener el archivo legible.

```jsonl
{"id": "1.001", "item": "Construir marcos conceptuales", "cuadrante": "1", "tag_amo": "1"}
{"id": "1b.002", "item": "Burocracia sin sentido", "cuadrante": "1b"}
{"id": "3.015", "item": "Traductores de complejidad,\nentre silos", "cuadrante": "3", "tag_mundo": "1"}
```

Cuadrantes válidos: `1, 1b, 2, 2b, 3, 3b, 4, 4b`. Los textos pueden contener comas, comillas, newlines y emojis libremente (a diferencia del CSV).

### Portabilidad CSV (puente para humanos)

El JSONL es el store interno. Para edición offline en Excel/Numbers o envío por correo, `/inventario/csv/export` baja un CSV equivalente, y `/inventario/csv/import` reemplaza el store con el CSV editado. Round-trip blindado por tests (caracteres asesinos: comas, comillas, newlines, emojis).

### Schema: `visualizations/default.yaml` (auto-generado, slim v0.3.0+)

```yaml
name: default
title: "Default"
categories: ["1", "2", "3", "4"]    # 0-4 csv_values (el orden define a, b, c, d)
summary: "Encontrar el centro del Ikigai clásico antes de Q3"
```

Eso es todo. Los conceptos por región NO viven aquí — viven en `intersection_concepts.yaml` (compartido con Síntesis). Los items por región se DERIVAN del JSONL en runtime usando sus tags.

### Schema: `intersection_concepts.yaml` (auto-generado)

```yaml
concepts:
  "1,2": "Pasión por la docencia"           # csv_value-set ordenado
  "1,2,3": "Mentoría con propósito social"   # vocación personalizada
  "1,2,3,4": "✨ Mi centro Ikigai"             # el santo grial
```

La key es el set de csv_values ordenados alfabéticamente y joined por coma. Así el concepto sigue siendo el mismo aunque reordenes los círculos del Venn.

### Migración automática desde v0.2.x

Si venís de una versión anterior y tu `default.yaml` tenía formato viejo con `regions[k].concept`, la primera vez que cargues la app:
1. Los conceptos se mueven a `intersection_concepts.yaml` (sin pisar los que ya tengas allí por Síntesis).
2. El `default.yaml` se reescribe en formato slim.
3. La evidencia manual se descarta (los items se derivan ahora de tags en `tulipan.jsonl`, así que asegurate de que tus items tengan los tags correctos en Inventario).

La migración es one-shot, idempotente y no destructiva del lado semántico (concepts).

### Migración manual de v0.3.x → v1.0 (single-project → workspace)

Si en v0.3 tenías un único project-dir (sin nivel de workspace), la "migración" es trivial: tu project-dir simplemente pasa a ser **un ikigai adentro** de un workspace. Cero copia de datos.

```bash
# Antes (v0.3.x):
#   ~/ikigai-personal/
#     ├── tulipan.jsonl
#     └── …
#   ikigai serve ~/ikigai-personal/

# Después (v1.0+): mové todo a un subdir con tu slug
mkdir ~/ikigai-workspace/
mv ~/ikigai-personal ~/ikigai-workspace/yo
ikigai serve ~/ikigai-workspace/      # → /u/yo/introspeccion
```

No hay migración automática para este paso porque es 1 comando, y un `serve` apuntando a un dir-sin-subdirs-válidos lo detecta y te lo dice explícitamente.

---

## CLI

| Comando | Para qué |
|---|---|
| `ikigai init mi-workspace/` | Crea un workspace vacío. Usá el wizard del browser para agregar el primer ikigai. |
| `ikigai init mi-workspace/ --demo` | Crea workspace + ikigai demo de Mariana adentro (`mariana/`). Ideal para entender el flow. |
| `ikigai serve mi-workspace/ [--open]` | Web app. Sirve todos los ikigais del workspace bajo `/u/<slug>/...`. Default port `8000`. |
| `ikigai export mi-workspace/ --ikigai <slug> [--open] [--redact]` | Snapshot HTML estático de **un** ikigai (Venn-4 + 15 intersecciones + cards). Autocontenido, abrible offline, compartible. |

### Flags de `ikigai export`

| Flag | Para qué |
|---|---|
| `--ikigai <slug>` | **Requerido**. Qué ikigai del workspace exportás. |
| `--out <path>` | Override del destino (default: `<workspace>/<slug>/output/<slug>-ikigai.html`) |
| `--open` | Abre el HTML en el browser al terminar |
| `--redact` | **Modo compartible**: oculta los textos de items (solo muestra conteos). Las síntesis acuñadas (nombres personales de cada intersección) se mantienen — ese es el punto del snapshot. Agrega un badge 🔒 al header. |

Combinación recomendada para compartir: `ikigai export mi-workspace/ --ikigai yo --redact` y luego mandá el HTML por el medio que prefieras.

---

## Compartir tu Ikigai

El snapshot generado por `ikigai export` es **autocontenido**: un único HTML con todo el CSS inline, sin assets locales ni dependencias de CDN. Es decir: lo abrís offline, lo mandás por mail, lo subís a cualquier hosting estático, o lo guardás como respaldo.

```bash
# Genera la versión compartible (sin items textuales personales)
ikigai export mi-workspace/ --ikigai yo --redact
# → escribe mi-workspace/yo/output/yo-ikigai.html
```

**Recomendación privacy**: usá `--redact` por default si vas a compartir. Los nombres personales que acuñaste para cada intersección SON el valor del snapshot — los items crudos son materia prima personal que rara vez aportan al lector.

---

## Desarrollo

```bash
# Setup
uv venv
uv pip install -e ".[dev]"

# Triple-check (lo que esperas verde antes de commitear)
uv run ruff check .
uv run mypy ikigai/
uv run pytest -q
```

Stack:
- **FastAPI + Jinja2** (server + templates)
- **HTMX + vanilla JS** (interactividad sin framework pesado)
- **Tailwind** (CSS vendorizado local, paleta del proyecto brand/accent/success/danger/ink)
- **PyYAML** (storage de viz + concepts)
- Datos planos: **JSONL** (items) + **YAML** (viz / concepts) — CSV solo como puente humano

### Arquitectura

Módulos puros con responsabilidad única:

| Módulo | Hace |
|---|---|
| `cuadrantes.py` | Define los **4 pares +/-** (los 4 primitivos: Gusto, Habilidad, Mundo, Mercado). Fuente de verdad del modelo. |
| `intersections.py` | Tabla canónica de nombres clásicos (Pasión, Misión, Vocación, Profesión, las 2 diagonales, los 4 Casi-Ikigai, y el centro Ikigai). |
| `models.py` | Dataclass `Item` (frozen). Es el contrato único entre disco, HTTP y lógica. |
| `workspace.py` | Discovery de ikigais en un workspace, validación de slugs, y `create_ikigai`. La fuente de verdad sobre qué vive en el filesystem. |
| `render.py` | Helper `render()` que inyecta `ikigai_url` (`/u/<slug>`) y la lista de ikigais en todo template. Single point of truth para el chrome. |
| `jsonl_store.py` | CRUD del JSONL append-only: `read_all`, `append`, `update`, `delete`, `next_id_for_cuadrante`. Escrituras atómicas. |
| `item_queries.py` | Filtros puros sobre `list[Item]` (`items_by_tag`, `items_by_evoking_cuadrante`, `classify_items_by_circle`). |
| `portability.py` | Puente CSV↔JSONL para humanos (export, import validado). |
| `viz_models.py` | Dataclass `Visualization` slim (name, title, categories, summary) + helpers `region_keys`/`region_to_csv_values`. |
| `viz_storage.py` | Load/save de la viz única + migración automática desde formato v0.2.x. |
| `intersection_concepts.py` | Source of truth de nombres acuñados por intersección (csv_value-set → nombre personal). |
| `algebra.py` | Operaciones puras de conjuntos + parser de expresiones + presets narrativos. |
| `algebra_state.py` | Lectura unificada del store → `AlgebraState` (items_by_cuad, primitive_sets, items_by_id, universe). |
| `auditor.py` | `ZenAuditReport`: detecta gaps de cobertura items↔círculos para los nudges del Inventario. |
| `export.py` | Genera snapshot HTML autocontenido (`ikigai export`). |
| `stats.py` | Fingerprint de secciones del cuestionario + labels/emojis/colores de los 4 círculos. |
| `navigation_context.py` | Resuelve el ikigai "master" desde el request (contexto de navegación entre vistas). |
| `atomic_io.py` | `atomic_write_text()`: escritura atómica (tmp-file + `os.replace`) contra data-loss en Ctrl-C. |
| `locks.py` | Locks por-clave in-process para serializar read-modify-write concurrentes (FastAPI atiende en thread pool). Compartido por `viz_storage` e `intersection_concepts`. |
| `migrations.py` | Migraciones one-shot idempotentes (CSV→JSONL; `regions[].concept` viejo → `intersection_concepts.yaml`). |
| `cli.py` | Entry point Click (`init` / `serve` / `export`) + fix de stdout UTF-8 para Windows. |
| `server.py` | FastAPI: descubre ikigais via `workspace.py`, monta los routers bajo `/u/<slug>`, expone `/_new` para crear. |

Diagramas Mermaid del sistema: ver [`docs/architecture.html`](docs/architecture.html).

---

## Changelog

Ver [`CHANGELOG.md`](CHANGELOG.md) — fuente de verdad de la versión. Versión
actual: **3.0.0**, el primer corte público bajo licencia MIT: proyecto
independiente, sin integraciones ni branding corporativo, con identidad visual
propia y un pase de hardening (XSS, validación de scores, manejo de errores).
La línea 2.9.x había dejado el Venn-4 exportado **sin pérdida** (callouts con
líneas guía al nombre completo de cada región). El formato de cada ikigai
individual sigue siendo el congelado en 1.0.

---

## Licencia

[MIT](LICENSE) — úsalo, módifica, comparte. Sin warranty.

🌷 Hecho con cariño.
