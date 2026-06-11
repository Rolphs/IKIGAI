#  IKIGAI — Instalación y arranque

> **Para el humano:** descomprimí el zip, abrí una terminal en la carpeta y
> seguí los pasos de abajo. Tarda menos de un minuto.

---

## TL;DR (copy-paste)

**Prerequisitos:** Python 3.11+ y `uv`.

### Windows (PowerShell / cmd)
```bat
cd ikigai
uv venv
uv pip install -e .
uv run ikigai init mi-ikigai --demo
uv run ikigai serve mi-ikigai --open
```

### macOS / Linux
```bash
cd ikigai
uv venv
uv pip install -e .
uv run ikigai init mi-ikigai --demo
uv run ikigai serve mi-ikigai --open
```

Eso levanta la app en **http://127.0.0.1:8000/** y abre el navegador.
`Ctrl+C` para detener.

---

## Qué es esto

Web app **local-first** (FastAPI + HTMX + Tailwind, SQLite/JSONL — sin nube)
para construir tu **Ikigai** personal: cuestionario → inventario taggeable →
síntesis dialéctica → visualización en **Venn de 4 círculos**. Todo corre en
tu máquina; tus reflexiones nunca salen de tu disco.

---

## Pasos detallados

### 1. Descomprimir
Descomprimí el zip. Vas a tener una carpeta `ikigai/` con `pyproject.toml`,
`ikigai/` (código), `tests/`, `README.md`, etc.

### 2. Instalar `uv` (si no lo tenés)
`uv` es el gestor de entornos/paquetes de Python (rapidísimo).
- Verificá si ya lo tenés:
  ```bat
  uv --version
  ```
- Si no: https://docs.astral.sh/uv/getting-started/installation/

### 3. Crear entorno e instalar dependencias
Desde **adentro** de la carpeta `ikigai/`:
```bat
uv venv
uv pip install -e .
```

### 4. Crear un workspace y arrancar
Un *workspace* es una carpeta que contiene N ikigais (uno por persona/intento).
```bat
uv run ikigai init mi-ikigai --demo
uv run ikigai serve mi-ikigai --open
```
- `init --demo` crea el workspace con un ejemplo ("mariana") adentro para que
  veas cómo se ve uno completo.
- `serve --open` levanta el server y abre el navegador. Usá el **dropdown del
  encabezado** para crear tu propio ikigai con el wizard.

### 5. (Opcional) Exportar tu resultado
Snapshot HTML autocontenido (un solo archivo, sin servidor):
```bat
uv run ikigai export mi-ikigai --ikigai mariana --open
```
Y desde el visualizador, el botón **"Export SVG"** baja el diagrama Venn con
todos los nombres completos (callouts con líneas guía).

---

## Verificar que quedó bien

```bat
uv run pytest -q
```
Debería decir algo como `512 passed`. Y `http://127.0.0.1:8000/health`
responde `{"status":"ok"}`.

---

## Comandos disponibles

| Comando | Qué hace |
|---|---|
| `ikigai init <ws> [--demo]` | Crea un workspace (con o sin ejemplo) |
| `ikigai serve <ws> [--open]` | Levanta la web app |
| `ikigai export <ws> --ikigai <slug> [--open] [--redact]` | Snapshot HTML estático |

(Prefijá con `uv run ` si no activaste el venv.)

---

## Troubleshooting

- **`Address already in use` (puerto 8000)** → usá otro puerto:
  `uv run ikigai serve mi-ikigai --port 8010 --open`
- **El SVG/snapshot se ve raro tras actualizar** → hacé *hard refresh* en el
  navegador (`Ctrl+F5`); el navegador cachea el JS/CSS.
- **`python` no encontrado** → instalá Python 3.11+ o dejá que `uv` lo baje:
  `uv python install 3.11`.

---

Hecho con 🌷 por Raúl Mercado. Versión del proyecto: ver `pyproject.toml` / `CHANGELOG.md`.
