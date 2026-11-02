# -*- coding: utf-8 -*-
"""preparacion.viento3d · control escrito desde cero (solo asignaciones), pronóstico 3D en una columna
y en columnas, nubes, estaciones de superficie, malla geofísica y utilidades de salida. Lo escrito se
vuelve a leer con los lectores del motor (`meteo.viento3d.control` y `entradas`): así se comprueba
que el motor lo entiende. La equivalencia byte a byte con los escritores del proyecto de La Galera se
comprobó allí (2026-10-23)."""
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pd = pytest.importorskip("pandas")

from teodors.meteo.viento3d import entradas, fichero_viento  # noqa: E402
from teodors.meteo.viento3d.control import Control  # noqa: E402
from teodors.preparacion import control as ctl_base  # noqa: E402
from teodors.preparacion.viento3d import control, estaciones, geofisica, nubes, parametros  # noqa: E402
from teodors.preparacion.viento3d import pronostico, salida  # noqa: E402

REF = (Path(__file__).resolve().parents[2] / "casos" / "viento3d" / "llano_lleida" / "referencia"
       / "calmet.dat")
EPSG = "EPSG:25831"
MALLA = {"nx": 10, "ny": 8, "celda_m": 400.0, "ext": (280000.0, 284000.0, 4500000.0, 4503200.0)}
ZFACE = (0, 20, 40, 80, 160, 300, 600, 1000)
INI = pd.Timestamp("2024-07-01 00:00")


def _leer(c):
    return Control(c.texto())


def test_parametros_sin_texto_ni_datos_de_ejemplo():
    nombres = [e[0] for e in parametros.PARAMETROS]
    assert "_ESTACIONES" in nombres and "NX" in nombres and "ZFACE" in nombres
    assert not any(re.fullmatch(r"SS\d+", n) for n in nombres)            # sin estaciones de ejemplo
    assert not {"UPDAT", "SEADAT", "PRCDAT"} & set(nombres)
    texto = repr(parametros.PARAMETROS)
    assert not re.search(r"CALMET|STA1|UPPWM|GEO1KM|LSP2003", texto)


def test_control_sin_estaciones_lo_lee_el_motor():
    c = control.preparar(MALLA, INI, 48, 31, ZFACE, terrad_km=5.0)
    texto = c.texto()
    assert "*" not in texto.split("\n", 1)[1]                             # solo asignaciones activas
    assert all(l == "!END!" or re.fullmatch(r"! [A-Z0-9_]+ = .* !", l) for l in texto.splitlines()[1:])
    v = _leer(c)
    assert (v.entero("NX"), v.entero("NY"), v.entero("NZ")) == (10, 8, 7)
    assert v.entero("NOOBS") == 2 and v.entero("NSSTA") == 0 and v.entero("ITPROG") == 2
    assert not v.hay("SRFDAT") and v.cadena("CLDDAT") == "nubes.dat"
    assert v.cadena("M3DDAT") == "pronostico3d.dat" and v.cadena("METDAT") == "viento3d.dat"
    assert [float(x) for x in v.lista("ZFACE")[0]] == [float(z) for z in ZFACE]
    assert v.lista("NSMTH")[0] == ["2"] + ["4"] * 6 and v.lista("BIAS")[0] == ["0"] * 7
    assert (v.entero("IBYR"), v.entero("IBMO"), v.entero("IRLG")) == (2024, 7, 48)
    assert v.real("XORIGKM") == 280.0 and v.real("DGRIDKM") == 0.4


def test_control_con_estaciones_y_extra():
    est = [("C9", 100001, 280.5, 4501.25, 10.0), ("U7", 100002, 283.0, 4502.0, 2.0)]
    c = control.preparar(MALLA, INI, 24, 31, ZFACE, estaciones=est, r1_km=5.0, rmax_km=30.0,
                         isurft=2, extra={"IKINE": 1})
    v = _leer(c)
    assert v.entero("NOOBS") == 1 and v.entero("NSSTA") == 2 and v.entero("ITPROG") == 1
    assert v.cadena("SRFDAT") == "estaciones.dat" and v.entero("ISURFT") == 2
    assert v.cadena("SS1") == "'C9  '   100001      280.500     4501.250    0  10.0"
    assert v.cadena("SS2").startswith("'U7  '   100002")
    assert (v.real("R1"), v.real("RMAX2"), v.entero("JWAT1"), v.entero("IKINE")) == (5.0, 30.0, 999, 1)
    with pytest.raises(KeyError):
        control.preparar(MALLA, INI, 24, 31, ZFACE, extra={"NO_EXISTE": 1})


def test_control_generico_poner_apagar_insertar():
    c = ctl_base.Control([["A", "1", True], ["B", "2", False], ["END", None, True], ["_M", None, False]])
    c.poner("B", 5).apagar("A").insertar(c.indice("_M"), [("C", 7), ("END", None)])
    assert c.asignaciones() == [("B", "5"), ("C", "7")]
    assert c.texto().splitlines()[1:] == ["! B = 5 !", "!END!", "! C = 7 !", "!END!"]


def _tablas(horas, sp=990.0):
    sfc = pd.DataFrame({"time": horas, "sp": sp, "t2m": 20.0, "d2m": 12.0, "tp": 0.5, "ssrd": 300.0,
                        "wdir": 200.0, "wspd": 3.0, "tcc": 0.4})
    pfl = pd.DataFrame([{"time": t, "level": lev, "height_asl_m": h, "temp_c": 25 - h / 160,
                         "wdir": 210.0, "wspd": 4.0}
                        for t in horas for lev, h in ((975, 300), (950, 520), (850, 1500))])
    return sfc, pfl


def test_pronostico_columna_lo_lee_el_motor(tmp_path):
    horas = list(pd.date_range(INI, periods=3, freq="h"))
    sfc, pfl = _tablas(horas, sp=970.0)                                    # 975 hPa bajo el suelo
    punto = {"lat": 40.7, "lon": 0.5, "cota_modelo_m": 267.0}
    r = pronostico.escribir_columna(tmp_path / "p.dat", pfl, sfc, MALLA["ext"], punto, horas, EPSG)
    assert r == {"horas": 3, "niveles": 3, "sustituciones_975": 3}
    d = entradas.leer_3d(tmp_path / "p.dat")
    assert (d["cab"]["nxp"], d["cab"]["nyp"], d["cab"]["nzp"]) == (3, 3, 3) and len(d["horas"]) == 3
    assert d["horas"][0]["fecha"] == (2024, 7, 1, 0)


def test_pronostico_columnas_y_nubes_por_zonas(tmp_path):
    horas = list(pd.date_range(INI, periods=2, freq="h"))
    pts, (xs, ys) = pronostico.rejilla_puntos((282000.0, 4501600.0), 2, 3000.0, EPSG)
    assert [p[:2] for p in pts] == [(1, 1), (2, 1), (1, 2), (2, 2)]
    assert np.allclose(xs, [280500.0, 283500.0]) and np.allclose(ys, [4500100.0, 4503100.0])
    filas = []
    for t in horas:
        for i, j, _, _ in pts:
            f = {"time": t, "i": i, "j": j, "surface_pressure": 1000.0 - 15 * i, "pressure_msl": 1013.0,
                 "temperature_2m": 20.0, "dew_point_2m": 12.0, "precipitation": 0.0,
                 "shortwave_radiation": 0.0, "wind_speed_10m": 3.0, "wind_direction_10m": 250.0,
                 "cloud_cover": 25.0 * i}
            for p, z in ((1000, 110), (975, 330), (850, 1500)):
                f.update({f"geopotential_height_{p}hPa": z, f"temperature_{p}hPa": 18.0,
                          f"wind_speed_{p}hPa": 5.0, f"wind_direction_{p}hPa": 260.0})
            filas.append(f)
    df = pd.DataFrame(filas)
    r = pronostico.escribir_columnas(tmp_path / "c.dat", df, 2, xs, ys, horas, (1000, 975, 850),
                                     (40.7, 0.5), EPSG)
    assert r["columnas"] == 4 and r["sustituciones"] > 0
    d = entradas.leer_3d(tmp_path / "c.dat")
    assert (d["cab"]["nxp"], d["cab"]["nyp"], d["cab"]["nzp"]) == (2, 2, 3)
    nubes.escribir_zonas(tmp_path / "nz.dat", df, MALLA, xs, ys, horas)
    n = entradas.leer_nubes(tmp_path / "nz.dat", MALLA["nx"], MALLA["ny"])
    v = n[salida.fecha_registro(horas[0])]
    assert v.shape == (8, 10) and v[0, 0] == pytest.approx(0.25) and v[0, -1] == pytest.approx(0.5)


def test_nubes_uniformes(tmp_path):
    horas = list(pd.date_range(INI, periods=2, freq="h"))
    sfc, _ = _tablas(horas)
    nubes.escribir(tmp_path / "n.dat", sfc, horas, 10, 8)
    n = entradas.leer_nubes(tmp_path / "n.dat", 10, 8)
    assert sorted(n) == [salida.fecha_registro(h) for h in horas]
    assert np.all(n[salida.fecha_registro(horas[1])] == pytest.approx(0.4))


def test_estaciones_medias_horarias_y_fichero(tmp_path):
    t = pd.to_datetime(["2024-07-01 23:30", "2024-07-02 00:00", "2024-07-02 00:30"])
    df = pd.DataFrame({"time": t, "ws": [2.0, 2.0, 4.0], "wd": [350.0, 10.0, 90.0],
                       "t": [20.0, 21.0, 22.0], "rh": [50.0, 60.0, 70.0], "p": [1000.0] * 3})
    m = estaciones.medias_horarias(df, "inicio")              # 23:30 y 00:00 -> hora 00
    assert list(m.time) == list(pd.to_datetime(["2024-07-02 00:00", "2024-07-02 01:00"]))
    assert m.wd.iloc[0] == pytest.approx(0.0, abs=1e-9) and m.ws.iloc[0] == 2.0   # 350° y 10° -> N
    assert m.t.iloc[0] == 20.5
    m2 = estaciones.medias_horarias(df, "fin")
    assert list(m2.time) == list(pd.to_datetime(["2024-07-01 23:00", "2024-07-02 00:00"]))
    horas = list(pd.date_range("2024-07-02 00:00", periods=2, freq="h"))
    sfc, _ = _tablas(horas)
    n = estaciones.escribir(tmp_path / "e.dat", [(100001, m)], horas, sfc)
    assert n == 1
    s = entradas.leer_surf(tmp_path / "e.dat")
    assert s["ids"] == [100001] and len(s["horas"]) == 2


def test_geofisica_malla_y_fichero(tmp_path):
    res = 25.0
    Z = np.full((32, 48), 100.0)
    U = np.full((32, 48), 211, dtype=np.int32)
    U[:, :8] = 0                                              # franja de mar sin CORINE (cota 0)
    Z[:, :8] = 0.0
    tr = SimpleNamespace(a=res, c=280000.0, e=-res, f=4500800.0)
    m = geofisica.malla(Z, U, tr, 100.0)
    assert (m["nx"], m["ny"], m["ext"]) == (12, 8, (280000.0, 281200.0, 4500000.0, 4500800.0))
    with pytest.raises(ValueError):
        geofisica.malla(Z, U, tr, 110.0)
    g = geofisica.escribir(tmp_path / "geo.dat", m, 31, mar=(U == 0) & (Z <= 0))
    assert (g["nx"], g["ny"]) == (12, 8) and set(g["categorias"]) == {20, 55}
    leido = entradas.leer_geo(tmp_path / "geo.dat")
    assert (leido["nx"], leido["ny"]) == (12, 8) and np.asarray(leido["lu"])[0, 0] == 55


def test_salida_recorte_fecha_y_punto(tmp_path):
    shutil.copy(REF, tmp_path / "v.dat")
    cab, horas = fichero_viento.leer(REF)
    seg = horas[1].ndathr
    ini = pd.Timestamp(seg // 100000, 1, 1) + pd.Timedelta(days=(seg // 100) % 1000 - 1, hours=seg % 100)
    assert salida.fecha_registro(ini) == seg
    assert salida.recorte(ini, 5) == (ini.year, ini.month, 5, seg)
    quitados = salida.recortar_arranque(tmp_path / "v.dat", ini, len(horas) - 1, cab.nx, cab.ny)
    cab2, horas2 = fichero_viento.leer(tmp_path / "v.dat")
    assert quitados > 0 and [h.ndathr for h in horas2] == [h.ndathr for h in horas[1:]]
    assert cab2.irlg == len(horas) - 1
    xs, ys = np.array([0.0, 10.0, 20.0]), np.array([0.0, 10.0])
    campo = xs[None, :] + 100 * ys[:, None]                    # lineal: la bilineal es exacta
    assert salida.en_punto(campo, 15.0, 5.0, xs, ys) == pytest.approx(15.0 + 500.0)
    ws, wd = salida.viento_en_punto(np.ones((2, 3)), np.zeros((2, 3)), xs, ys, 5.0, 5.0, 0.0)
    assert ws == pytest.approx(1.0) and wd == pytest.approx(270.0)          # del oeste
    _, wd2 = salida.viento_en_punto(np.ones((2, 3)), np.zeros((2, 3)), xs, ys, 5.0, 5.0, -1.65)
    assert wd2 == pytest.approx(271.65)
