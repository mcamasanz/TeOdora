# -*- coding: utf-8 -*-
"""Regresión: cada caso de auditor/casos/ debe reproducir su referencia.

Un caso es una entrada pequeña de un motor (unos segundos) cuyas salidas se guardaron con el código
validado frente al programa original. Si una salida cambia, la prueba falla y dice qué fichero y
qué línea; para cambiar una referencia a propósito hay que justificarlo en
auditor/CAMBIOS_REFERENCIA.md.
"""
import datetime

import pytest

from auditor import casos as C

CASOS = C.listar()


def _param(caso):
    marcas = [getattr(pytest.mark, m) for m in caso.marcas]
    return pytest.param(caso, id=caso.nombre, marks=marcas)


def test_hay_casos_de_todos_los_motores():
    import teodors
    motores = {c.motor for c in CASOS}
    faltan = set(teodors.MOTORES) - motores
    assert not faltan, "motores sin caso de regresión: %s" % ", ".join(sorted(faltan))


@pytest.mark.parametrize("caso", [_param(c) for c in CASOS])
def test_reproduce_la_referencia(caso, tmp_path):
    C.ejecutar(caso, tmp_path / "trabajo")
    dif = C.diferencias(caso, tmp_path / "trabajo")
    assert not dif, "%s (%s)\n  " % (caso.nombre, caso.descripcion) + "\n  ".join(dif)


# un caso por motor (el primero que no compila el núcleo): basta para ver si alguna salida depende
# de la fecha de la corrida en un formato que el comparador no enmascara
UNO_POR_MOTOR = list({c.motor: c for c in reversed(CASOS) if "compilacion" not in c.marcas}.values())


@pytest.mark.parametrize("caso", [_param(c) for c in UNO_POR_MOTOR])
def test_no_depende_del_dia_ni_de_la_hora(caso, tmp_path):
    # otro día y otra hora, con cifras sueltas (mes, día, hora, minuto y segundo < 10) y de mañana
    C.ejecutar(caso, tmp_path / "trabajo", reloj=datetime.datetime(2027, 1, 5, 9, 5, 3))
    dif = C.diferencias(caso, tmp_path / "trabajo")
    assert not dif, "%s corrido el 05/01/2027 a las 09:05:03\n  " % caso.nombre + "\n  ".join(dif)
