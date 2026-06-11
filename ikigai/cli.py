"""
CLI de ikigai (workspace-multi-ikigai).

Cada workspace es una carpeta con N subdirectorios (uno por ikigai). El
visualizador se sirve desde ese workspace y permite saltar de uno a otro
via el dropdown del chrome.

Comandos:
  ikigai init <workspace_dir>                 Crea workspace vacio (opcional: --demo)
  ikigai serve <workspace_dir>                Levanta web app (multi-ikigai)
  ikigai export <workspace_dir> --ikigai N    Snapshot HTML de UN ikigai
"""
from __future__ import annotations

import contextlib
import sys
import webbrowser
from pathlib import Path

import click

from ikigai import __version__

OUTPUT_DIRNAME = "output"


def _setup_utf8_stdout() -> None:
    """Forzar stdout/stderr a UTF-8 (Windows cp1252 rompe emojis).

    A IMPORT-time porque --help/--version de click imprimen ANTES de main().
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            with contextlib.suppress(AttributeError, OSError):
                stream.reconfigure(encoding="utf-8", errors="replace")


_setup_utf8_stdout()


@click.group()
@click.version_option(version=__version__, prog_name="ikigai")
def main() -> None:
    """ikigai \U0001f337 — Tulipán de Ikigai expandido a HTML interactivo."""


@main.command()
@click.argument("workspace_dir", type=click.Path(path_type=Path))
@click.option("--demo", is_flag=True, default=False,
              help="Bootstrap con el ikigai demo de Mariana adentro del workspace.")
def init(workspace_dir: Path, demo: bool) -> None:
    """Crea un workspace vacio en WORKSPACE_DIR.

    Con --demo: agrega 'mariana/' adentro (Ikigai completo de ejemplo).
    Sin --demo: solo crea el dir; usa `serve` y el wizard del browser
    para agregar el primer ikigai.
    """
    if workspace_dir.exists() and any(workspace_dir.iterdir()):
        click.echo(f"❌ {workspace_dir} ya existe y no esta vacio. Aborto.", err=True)
        sys.exit(1)

    workspace_dir.mkdir(parents=True, exist_ok=True)
    if demo:
        _copy_demo_into_workspace(workspace_dir)
        click.echo(f"✅ Workspace con demo creado en {workspace_dir}")
        click.echo("Proximos pasos:")
        click.echo(f"  1. ikigai serve {workspace_dir} --open      # ver el demo")
        click.echo("  2. Usa el dropdown del chrome para crear el tuyo")
    else:
        click.echo(f"✅ Workspace vacio creado en {workspace_dir}")
        click.echo("Proximos pasos:")
        click.echo(f"  1. ikigai serve {workspace_dir} --open      # abre el wizard")
        click.echo("  2. Crea tu primer ikigai en el browser")


@main.command()
@click.argument("workspace_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--open", "open_browser", is_flag=True, default=False,
              help="Abre el visualizador en el browser al arrancar.")
def serve(workspace_dir: Path, host: str, port: int, open_browser: bool) -> None:
    """Levanta un servidor local con todos los ikigais del WORKSPACE_DIR."""
    import uvicorn

    from ikigai.server import create_app

    app = create_app(workspace_dir)
    url = f"http://{host}:{port}/"
    click.echo(f"🌷 ikigai serve en {url}")
    click.echo("   (la raiz redirige al primer ikigai del workspace o al wizard si esta vacio)")
    click.echo("   Ctrl+C para detener")

    if open_browser:
        webbrowser.open(url)

    uvicorn.run(app, host=host, port=port, log_level="warning")


@main.command()
@click.argument("workspace_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--ikigai", "ikigai_name", required=True,
              help="Nombre (slug) del ikigai a exportar dentro del workspace.")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None,
              help="Path de salida del HTML. Default: <workspace>/<ikigai>/output/<ikigai>-ikigai.html")
@click.option("--open", "open_browser", is_flag=True, default=False,
              help="Abre el HTML generado en el browser.")
@click.option("--redact", is_flag=True, default=False,
              help="Oculta los textos de items (solo conteos). Para compartir publicamente.")
def export(
    workspace_dir: Path,
    ikigai_name: str,
    out_path: Path | None,
    open_browser: bool,
    redact: bool,
) -> None:
    """Genera un snapshot HTML estatico y autocontenido de UN ikigai."""
    from ikigai.export import export_snapshot
    from ikigai.migrations import migrate_all_if_needed
    from ikigai.workspace import resolve_project_dir

    try:
        project_dir = resolve_project_dir(workspace_dir.resolve(), ikigai_name)
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"❌ {exc}", err=True)
        sys.exit(1)

    # Migraciones one-shot (idempotentes): si el ikigai esta en formato pre-v0.4.
    for msg in migrate_all_if_needed(project_dir):
        click.echo(f"→ {msg}")

    if out_path is None:
        out_path = project_dir / OUTPUT_DIRNAME / f"{ikigai_name}-ikigai.html"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = export_snapshot(project_dir, out_path, redact=redact)

    click.echo(f"✅ Exportado a {written.resolve()}")
    if open_browser:
        webbrowser.open(written.absolute().as_uri())


def _copy_demo_into_workspace(workspace_dir: Path) -> None:
    """Copia el ikigai demo dentro del workspace como subdir 'mariana'.

    La data vive en `ikigai/_demo_data/` dentro del wheel (force-included
    desde examples/demo/ via hatch — ver pyproject.toml). Se accede con
    importlib.resources para que funcione tanto en dev (-e .) como en
    instalaciones pip/uv reales.
    """
    from importlib.resources import as_file, files

    demo_root = files("ikigai") / "_demo_data"
    if not demo_root.is_dir():
        click.echo(
            "❌ No encuentro el demo embebido (ikigai/_demo_data/). "
            "¿Wheel mal armada? Reporta el bug.", err=True,
        )
        sys.exit(1)

    target = workspace_dir / "mariana"
    target.mkdir()
    for entry in demo_root.iterdir():
        with as_file(entry) as src:
            _copy_tree(src, target / src.name)


def _copy_tree(src: Path, dst: Path) -> None:
    """Copia un archivo o directorio recursivamente. Sin sobrescribir."""
    import shutil

    if src.is_dir():
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)


if __name__ == "__main__":
    main()
