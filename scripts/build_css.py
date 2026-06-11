"""build_css.py - (Re)genera el frontend vendorizado (Tailwind CSS + htmx).

Por que existe: para no depender de CDNs externos en runtime
(cdn.tailwindcss.com / unpkg.com), servimos assets locales desde
ikigai/static/ (tailwind.css buildeado + htmx.min.js).

Que hace:
  1. Descarga el Tailwind CLI standalone + htmx desde los releases publicos
     de GitHub si faltan (detecta plataforma: macOS arm64/x64, Linux, Windows).
  2. Buildea ikigai/static/tailwind.css escaneando templates + JS
     (config en tailwind.config.js, entrada en tailwind.input.css).

El CLI standalone (~40MB, platform-specific) NO se commitea (.gitignore).
tailwind.css y htmx.min.js SI se commitean (son los assets servidos).

Uso:
  uv run python scripts/build_css.py
"""
from __future__ import annotations

import platform
import subprocess
import sys
import urllib.request as u
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GH = "https://github.com"
TW_VERSION = "v3.4.17"
HTMX_VERSION = "v2.0.3"

HTMX = ROOT / "ikigai" / "static" / "htmx.min.js"
CONFIG = ROOT / "tailwind.config.js"
INPUT = ROOT / "tailwind.input.css"
OUTPUT = ROOT / "ikigai" / "static" / "tailwind.css"


def _cli_asset() -> tuple[str, str]:
    """Devuelve (nombre_del_asset, nombre_del_binario_local) segun la plataforma."""
    system = platform.system()
    machine = platform.machine().lower()
    is_arm = machine in ("arm64", "aarch64")
    if system == "Darwin":
        asset = "tailwindcss-macos-arm64" if is_arm else "tailwindcss-macos-x64"
        return asset, "_tw_cli"
    if system == "Windows":
        return "tailwindcss-windows-x64.exe", "_tw_cli.exe"
    # Linux (default)
    asset = "tailwindcss-linux-arm64" if is_arm else "tailwindcss-linux-x64"
    return asset, "_tw_cli"


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"GET {url}")
    data = u.urlopen(url, timeout=180).read()
    dest.write_bytes(data)
    print(f"  -> {dest.relative_to(ROOT)} ({len(data):,} bytes)")


def main() -> int:
    asset, cli_name = _cli_asset()
    cli = ROOT / cli_name

    if not cli.exists():
        _download(
            f"{GH}/tailwindlabs/tailwindcss/releases/download/"
            f"{TW_VERSION}/{asset}",
            cli,
        )
        cli.chmod(0o755)
    if not HTMX.exists():
        _download(
            f"{GH}/bigskysoftware/htmx/releases/download/"
            f"{HTMX_VERSION}/htmx.min.js",
            HTMX,
        )

    print("Building tailwind.css...")
    result = subprocess.run(
        [str(cli), "-c", str(CONFIG), "-i", str(INPUT),
         "-o", str(OUTPUT), "--minify"],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        print("ERROR: el build de Tailwind fallo.", file=sys.stderr)
        return result.returncode
    print(f"OK -> {OUTPUT.relative_to(ROOT)} ({OUTPUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
