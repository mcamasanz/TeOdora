# -*- coding: utf-8 -*-
"""El penacho hora a hora de un periodo (las imágenes de cada rejilla y, del olor, sus isolíneas), repartido entre varios procesos.

En un episodio son ~600 dibujos independientes (8 magnitudes × 72 horas: 2 PNG cada uno, más las isolíneas del olor). Sin esto,
`simulacion.calcular_periodo` los hace uno detrás de otro en un solo núcleo (~128 s en el episodio de ejemplo, medido el 2026-11-15).
Aquí se hacen con las MISMAS funciones (`simulacion._imagenes` y `simulacion._isolineas`), así que salen los mismos ficheros, byte a byte
(rendimiento/perfil/exp_imagenes_paralelo.py, 2026-11-14: 1272 de 1272 idénticos).

Cuántos procesos lo dice el interruptor del cálculo en paralelo (`reanalisis_paralelo.de_la_planta` y `procesos`). Con 1,
`calcular_periodo` no pasa por aquí y pinta como siempre.
"""
import multiprocessing as mp
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

_R = {}


def _iniciar(rejillas):
    from teodors import planta
    planta.actual()                                   # la planta del padre (TEODORS_PLANTA)
    _R["rejillas"] = rejillas


def _una(tarea):
    from teodors.operacion import simulacion as S
    tipo, campo, ruta, ref, niveles = tarea
    if tipo == "png":
        return S._imagenes(campo, _R["rejillas"], Path(ruta), ref)
    S._isolineas(campo, _R["rejillas"], Path(ruta), niveles)
    return None


def pintar(tareas, rejillas, procesos, hecha=None, cancelado=None):
    """Hace las `tareas` [(«png» o «iso», campo, ruta, ref, niveles)] en `procesos` procesos y devuelve lo que devuelve cada una, en su
    orden: de un «png», sus imágenes (`simulacion._imagenes`); de un «iso», None. `hecha(n)` cada vez que acaba una (n = las hechas);
    `cancelado()` se mira cada medio segundo."""
    salen = [None] * len(tareas)
    if not tareas:
        return salen
    with ProcessPoolExecutor(max(1, min(int(procesos), len(tareas))), mp_context=mp.get_context("spawn"),
                             initializer=_iniciar, initargs=(rejillas,)) as pool:
        pendientes = {pool.submit(_una, t): i for i, t in enumerate(tareas)}
        n = 0
        while pendientes:
            listos, _ = wait(list(pendientes), timeout=0.5, return_when=FIRST_COMPLETED)
            if cancelado and cancelado():
                for f in pendientes:
                    f.cancel()
                raise RuntimeError("Cálculo cancelado.")
            for f in listos:
                salen[pendientes.pop(f)] = f.result()
                n += 1
                if hecha:
                    hecha(n)
    return salen
