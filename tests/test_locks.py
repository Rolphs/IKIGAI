"""Tests de locks.py: locks por-clave para serializar read-modify-write (D2)."""
from __future__ import annotations

import threading
import time

from ikigai.locks import keyed_lock


def test_same_key_serializes_critical_section() -> None:
    # Dos threads con la MISMA key no deben solaparse en la seccion critica:
    # cada 'in' debe ir seguido de su 'out' antes de que entre el otro.
    order: list[str] = []

    def worker(tag: str) -> None:
        with keyed_lock("shared"):
            order.append(f"{tag}-in")
            time.sleep(0.02)
            order.append(f"{tag}-out")

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert order in (
        ["a-in", "a-out", "b-in", "b-out"],
        ["b-in", "b-out", "a-in", "a-out"],
    )


def test_different_keys_do_not_block_each_other() -> None:
    # Keys distintas tienen locks distintos: pueden correr en paralelo.
    # Si se bloquearan, el segundo thread no entraria hasta que el primero
    # suelte; aqui verificamos que AMBOS entran antes de que cualquiera salga.
    entered = threading.Barrier(2, timeout=2.0)
    released: list[str] = []

    def worker(key: str) -> None:
        with keyed_lock(key):
            entered.wait()  # solo pasa si los DOS entraron a la vez
            released.append(key)

    t1 = threading.Thread(target=worker, args=("k1",))
    t2 = threading.Thread(target=worker, args=("k2",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert sorted(released) == ["k1", "k2"]
