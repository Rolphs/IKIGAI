"""locks.py - Locks por-clave en proceso, para serializar read-modify-write.

La app es local-first (un solo proceso uvicorn), pero FastAPI atiende requests
en un thread pool. Dos requests concurrentes que hacen load -> modify -> save
sobre el MISMO archivo pueden pisarse (ambos cargan el estado A, cada uno
escribe su cambio, gana el ultimo => se pierde el del otro).

Este modulo da un lock por clave (un path, un nombre de viz, etc.) para
serializar ese bloque critico. Fuente unica del patron: antes estaba
duplicado en viz_storage; ahora viz_storage e intersection_concepts lo
comparten.

LIMITACION (importante si algun dia se escala): estos locks son IN-PROCESS
(viven en un dict de este modulo). Solo protegen contra escrituras
concurrentes DENTRO del mismo proceso Python. Si se corre la app con varios
workers (uvicorn --workers N, gunicorn, o varias instancias apuntando al
MISMO workspace en disco), dos procesos distintos NO comparten estos locks
y podrian pisarse en un read-modify-write. El diseno actual es local-first
de un solo proceso, donde esto alcanza. Para multi-proceso haria falta un
lock a nivel de filesystem (p.ej. fcntl/flock sobre el archivo) o mover el
storage a una DB con su propio control de concurrencia.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()


def _get_lock(key: str) -> threading.Lock:
    """Devuelve (creando si hace falta) el lock asociado a `key`.

    El `_guard` protege el dict de locks de un race en la propia creacion.
    """
    with _guard:
        return _locks.setdefault(key, threading.Lock())


@contextmanager
def keyed_lock(key: str) -> Iterator[None]:
    """Serializa el bloque para una `key` dada.

    Mantener el bloque corto: solo load+modify+save. NO hacer I/O lento ni
    llamadas al LLM adentro (bloquearia a otros writers de la misma clave).

    Uso:
        with keyed_lock(str(yaml_path)):
            data = load(...)
            data[...] = ...
            save(...)
    """
    with _get_lock(key):
        yield
