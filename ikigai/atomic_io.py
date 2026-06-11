"""I/O atómico al disco — primitivo de seguridad para no perder datos.

Todas las escrituras del usuario (items, concepts, viz framing) pasan por
aquí. La garantía es simple pero importante: o el archivo queda con el
contenido nuevo COMPLETO, o queda con el contenido anterior INTACTO.
Nunca queda en un estado intermedio (truncado, parcial, corrupto).

Cómo: escribir a un tmp en el mismo directorio, fsync (best-effort), y
luego `os.replace` que es atómico a nivel de filesystem en POSIX y NTFS.

Pre-v1.0 algunos callers escribían YAML directo con `path.write_text(...)`.
Eso permitía corrupciones silenciosas si el proceso moría a mitad de
escritura (Ctrl-C en el peor momento, kernel panic, batería que se acaba).
La consecuencia visible era `load_personal_names` devolviendo `{}` y el
usuario perdiendo todo su árbol de síntesis sin warning. Nunca más.
"""
from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    """Escribe `content` a `path` de forma atómica y durable.

    Crea el directorio padre si no existe. El tmp vive en el mismo
    directorio que el destino — esto es crítico porque `os.replace` solo
    es atómico cuando origen y destino están en el mismo filesystem.

    Durabilidad: `flush` + `os.fsync` ANTES del replace, para que los bytes
    estén en disco y el rename no quede ordenado antes que los datos (lo que
    en un corte de luz dejaría el archivo nuevo apuntando a basura). Si algo
    falla a mitad, se borra el tmp y se re-lanza — el destino queda intacto.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        # newline="" porque ya viene serializado: yaml.safe_dump y json.dumps
        # producen su propio formato y no queremos que Python reescriba \n.
        with tmp.open("w", encoding=encoding, newline="") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)
    except BaseException:
        # Limpia el tmp parcial ante cualquier fallo (incluido Ctrl-C) para
        # no dejar huérfanos. El destino original nunca se tocó.
        tmp.unlink(missing_ok=True)
        raise
