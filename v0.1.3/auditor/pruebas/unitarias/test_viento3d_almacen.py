# -*- coding: utf-8 -*-
"""meteo.viento3d · almacén comprimido (`almacen`: .cmz) y lectura selectiva del fichero de viento
(`fichero_viento.leer_campos`), con la salida de referencia del caso de regresión llano_lleida."""
from pathlib import Path

import numpy as np
import pytest

from teodors.meteo.viento3d import almacen, fichero_viento

REF = (Path(__file__).resolve().parents[2] / "casos" / "viento3d" / "llano_lleida" / "referencia"
       / "calmet.dat")


@pytest.fixture(scope="module")
def comprimido(tmp_path_factory):
    cab, _ = fichero_viento.leer(REF, horas=False)
    d = tmp_path_factory.mktemp("almacen")
    res = almacen.comprimir(REF, d / "viento.cmz", cab.nx, cab.ny)
    rec = almacen.descomprimir(d / "viento.cmz", d / "reconstruido.dat")
    return cab, d / "viento.cmz", res, rec


def _es_campo(b, cab):
    return len(b) == 12 + 4 * cab.nx * cab.ny and b[:8].decode("latin-1").isprintable()


def test_almacen_reconstruye_la_misma_secuencia_de_registros(comprimido):
    cab, _, res, rec = comprimido
    a, b = list(almacen._registros(REF)), list(almacen._registros(rec))
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert len(x) == len(y)
        if not _es_campo(x, cab):
            assert x == y                                  # cabeceras: sin pérdida
        else:
            assert x[:12] == y[:12]                        # etiqueta y fecha
            if almacen._nombre(x[:8].decode("latin-1")) in almacen.ENTEROS | almacen.SIN_PERDIDA:
                assert x == y                              # enteros y EL: sin pérdida
    assert res["ratio"] > 1.0


def test_almacen_error_acotado_por_la_cuantizacion(comprimido):
    cab, _, res, rec = comprimido
    peor, rango = {}, {}
    for x, y in zip(almacen._registros(REF), almacen._registros(rec)):
        if not _es_campo(x, cab):
            continue
        nom = almacen._nombre(x[:8].decode("latin-1"))
        if nom in almacen.ENTEROS:
            continue
        vx, vy = np.frombuffer(x[12:], "<f4"), np.frombuffer(y[12:], "<f4")
        peor[nom] = max(peor.get(nom, 0.0), float(np.abs(vx.astype(float) - vy).max()))
        lo, hi = rango.get(nom, (np.inf, -np.inf))
        rango[nom] = (min(lo, float(vx.min())), max(hi, float(vx.max())))
    for nom, e in peor.items():
        assert e <= res["errores"][nom] + 1e-6, nom
        lo, hi = rango[nom]
        assert e <= (hi - lo) / almacen.PASOS / 2 + 1e-6 * max(abs(lo), abs(hi), 1.0), nom


def test_almacen_leer_campo_igual_que_la_reconstruccion(comprimido):
    _, cmz, _, rec = comprimido
    _, horas = fichero_viento.leer(rec)
    fechas, u1 = almacen.leer_campo(cmz, "U-LEV  1")
    assert list(fechas) == [h.ndathr for h in horas]
    np.testing.assert_array_equal(u1, np.stack([h.u[0] for h in horas]))


def test_almacen_recorte_quita_las_horas_de_arranque(tmp_path):
    cab, horas = fichero_viento.leer(REF)
    segunda = horas[1].ndathr
    almacen.comprimir(REF, tmp_path / "r.cmz", cab.nx, cab.ny,
                      recorte=(cab.ibyr, cab.ibmo, len(horas) - 1, segunda))
    fechas, _ = almacen.leer_campo(tmp_path / "r.cmz", "U-LEV  1")
    assert list(fechas) == [h.ndathr for h in horas[1:]]
    cab2, horas2 = fichero_viento.leer(almacen.descomprimir(tmp_path / "r.cmz", tmp_path / "r.dat"))
    assert cab2.irlg == len(horas) - 1 and len(horas2) == len(horas) - 1


def test_leer_campos_igual_que_el_lector_completo():
    _, horas = fichero_viento.leer(REF)
    cab, d = fichero_viento.leer_campos(REF, niveles=(1, 2), campos2d=("TEMPK", "IPGT", "ZI"))
    assert set(d) == {"ndathr", "u", "v", "TEMPK", "IPGT", "ZI"}
    assert list(d["ndathr"]) == [h.ndathr for h in horas]
    for k in (1, 2):
        np.testing.assert_array_equal(d["u"][k], np.stack([h.u[k - 1] for h in horas]))
        np.testing.assert_array_equal(d["v"][k], np.stack([h.v[k - 1] for h in horas]))
    for c in ("TEMPK", "IPGT", "ZI"):
        np.testing.assert_array_equal(d[c], np.stack([h.d2[c] for h in horas]))
    assert d["IPGT"].dtype == np.int32 and d["TEMPK"].dtype == np.float32
    assert d["u"][1].shape == (len(horas), cab.ny, cab.nx)


def test_leer_campos_solo_campos_2d():
    _, horas = fichero_viento.leer(REF)
    _, d = fichero_viento.leer_campos(REF, niveles=(), campos2d=("USTAR",))
    assert d["u"] == {} and d["v"] == {}
    assert list(d["ndathr"]) == [h.ndathr for h in horas]
    np.testing.assert_array_equal(d["USTAR"], np.stack([h.d2["USTAR"] for h in horas]))
