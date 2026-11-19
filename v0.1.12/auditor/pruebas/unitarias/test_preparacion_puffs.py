# -*- coding: utf-8 -*-
"""preparacion.puffs y preparacion.receptores · control de puffs escrito desde cero (solo
asignaciones), lectura de las concentraciones y malla de receptores anidada. El control se vuelve a
leer con el lector del motor (`dispersion.puffs.entrada`) y se lanza el motor sobre el viento del
caso de regresión puffs/area_D. La equivalencia con el escritor del proyecto de La Galera (misma
secuencia de asignaciones salvo los nombres de las salidas de deposición) se comprobó allí
(2026-10-23)."""
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

pd = pytest.importorskip("pandas")

from teodors.dispersion.puffs import entrada  # noqa: E402
from teodors.dispersion.puffs.principal import ejecutar  # noqa: E402
from teodors.meteo.viento3d import fichero_viento  # noqa: E402
from teodors.preparacion import receptores  # noqa: E402
from teodors.preparacion.puffs import control, parametros, salida  # noqa: E402

CASO = Path(__file__).resolve().parents[2] / "casos" / "puffs" / "area_D" / "entrada" / "CALMET.DAT"
MALLA = {"nx": 125, "ny": 125, "celda_m": 400.0, "ext": (262000.0, 312000.0, 4482000.0, 4532000.0)}
ZFACE = (0, 20, 40, 80, 160, 300, 600, 1000, 1500, 2200, 3000, 4000, 5000)


def _cuadrado(nombre, x0, y0, lado=100.0, q=1e-4):
    v = [(x0, y0), (x0 + lado, y0), (x0 + lado, y0 + lado), (x0, y0 + lado)]
    return control.fuente_area(nombre, v, 2.0, 98.0, q)


def test_parametros_sin_datos_de_ejemplo():
    nombres = [e[0] for e in parametros.PARAMETROS]
    for marca in ("_AREAS_X", "_AREAS_VERTICES", "_RECEPTORES", "_ESPECIE"):
        assert marca in nombres
    assert nombres.count("METDAT") == 1 and "SRCNAM" not in nombres
    assert not re.search(r"CALMET|CALPUFF|CPUF|STK1|'SO2'|SO4|PM10|HNO3", repr(parametros.PARAMETROS))


def test_control_lo_lee_el_motor():
    fuentes = [_cuadrado("A1", 286700.0, 4507400.0), _cuadrado("A2", 287000.0, 4507400.0, q=3e-4)]
    recs = [(286763.0, 4507474.0, 98.0), (290000.0, 4510000.0, 300.5)]
    c = control.preparar(MALLA, ZFACE, pd.Timestamp("2024-07-01 06:00"), 42, 31, fuentes, recs,
                         especie="olor")
    texto = c.texto()
    assert all(l == "!END!" or re.fullmatch(r"! [A-Z0-9_]+ = .* !", l) for l in texto.splitlines()[1:])
    cfg = entrada.leer(texto)
    assert (cfg.i("NX"), cfg.i("NY"), cfg.i("NZ")) == (125, 125, 12)
    assert (cfg.i("IBYR"), cfg.i("IBMO"), cfg.i("IBDY"), cfg.i("IBHR"), cfg.i("IRLG")) == (2024, 7, 1, 6, 42)
    assert cfg.s("METDAT") == "viento3d.dat" and cfg.s("CONDAT") == "conc.dat"
    assert (cfg.i("MCHEM"), cfg.i("MWET"), cfg.i("MDRY"), cfg.i("NPT1"), cfg.i("NAR1")) == (0, 0, 0, 0, 2)
    assert [e.nombre for e in cfg.especies] == ["OLOR"]
    a1, a2 = cfg.fuentes
    assert (a1.nombre, a1.tipo, a2.q) == ("A1", 3, pytest.approx(3e-4))
    assert a1.vx == pytest.approx([286.7, 286.8, 286.8, 286.7]) and a1.vy[2] == pytest.approx(4507.5)
    assert cfg.receptores.shape == (2, 4) and cfg.receptores[1] == pytest.approx([290.0, 4510.0, 300.5, 0.0])
    with pytest.raises(KeyError):
        control.preparar(MALLA, ZFACE, pd.Timestamp("2024-07-01"), 1, 31, fuentes, recs,
                         extra={"NO_EXISTE": 1})


def test_caso_completo_con_el_motor(tmp_path):
    """Control desde cero sobre el viento de puffs/area_D (40×40 celdas de 240 m, llano a 200 m):
    una fuente de área en el centro y dos anillos de receptores; 3 horas."""
    shutil.copy(CASO, tmp_path / "viento3d.dat")
    cab, horas = fichero_viento.leer(CASO)
    malla = {"nx": cab.nx, "ny": cab.ny, "celda_m": cab.dgrid,
             "ext": (cab.xorig, cab.xorig + cab.nx * cab.dgrid, cab.yorig, cab.yorig + cab.ny * cab.dgrid)}
    xc, yc = cab.xorig + cab.nx * cab.dgrid / 2, cab.yorig + cab.ny * cab.dgrid / 2
    fuente = control.fuente_area("PILA", [(xc - 50, yc - 50), (xc + 50, yc - 50), (xc + 50, yc + 50),
                                          (xc - 50, yc + 50)], 2.0, 200.0, 1e-4)
    ang = np.radians(np.arange(0, 360, 45))
    recs = [(xc + r * np.sin(a), yc + r * np.cos(a), 200.0) for r in (500.0, 1000.0) for a in ang]
    ini = pd.Timestamp(cab.ibyr, cab.ibmo, cab.ibdy, cab.ibhr)
    control.escribir(tmp_path / "puffs.inp", malla, [float(z) for z in cab.zface], ini, 3, 30,
                     [fuente], recs)
    ejecutar(tmp_path / "puffs.inp", verbose=False)
    fines, conc = salida.concentraciones(tmp_path / "conc.dat")
    assert conc.shape == (3, 16) and np.all(conc >= 0) and conc.max() > 0
    assert [f - fines[0] for f in fines] == [pd.Timedelta(hours=h) for h in range(3)]
    n = horas[0].ndathr                     # el periodo k lleva la fecha del registro k del viento
    assert fines[0] == datetime(n // 100000, 1, 1) + timedelta(days=(n // 100) % 1000 - 1, hours=n % 100)
    assert salida.concentraciones(tmp_path / "conc.dat", especie="OLOR")[1] == pytest.approx(conc)


def test_malla_anidada():
    recs = receptores.malla_anidada((0.0, 0.0), 1000.0, [("fina", 100.0, 200.0), ("gruesa", 500.0, None)],
                                    discretos=[(50.04, 0.0, "casa"), (100.0, 100.0, "pueblo"),
                                               (5000.0, 0.0, "lejos")])
    r = receptores.resumen(recs)
    assert r == {"total": 50, "por_clase": {"fina": 24, "gruesa": 24, "casa": 1, "pueblo": 1}}
    assert recs == sorted(recs) and (50.0, 0.0, "casa") in recs and (100.0, 100.0, "pueblo") in recs
    xy = [(x, y) for x, y, _ in recs]
    assert len(set(xy)) == len(xy) and (-1000.0, 1000.0) in xy and (500.0, 0.0) in xy
