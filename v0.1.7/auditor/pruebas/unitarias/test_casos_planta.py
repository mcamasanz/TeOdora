# -*- coding: utf-8 -*-
"""casos y preparacion.puffs.control_fuentes · lo que une una planta, sus datos y los motores, SIN RED y con una planta inventada a propósito.
Los ficheros se vuelven a leer con los lectores de los motores y, donde cuenta, se lanza el motor de verdad: la suma de las respuestas por hora de
emisión tiene que dar la corrida directa con un perfil, y un área va POR m². Comprueban el código: no dicen nada del viento de ningún sitio."""
import ast
import json
import math
import re
import shutil
import socket
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pd = pytest.importorskip("pandas")
xr = pytest.importorskip("xarray")

from teodors import planta  # noqa: E402
from teodors.casos import gfs_columnas, receptores, viento3d  # noqa: E402
from teodors.comun import procesos  # noqa: E402
from teodors.dispersion.puffs import entrada  # noqa: E402
from teodors.dispersion.puffs.principal import ejecutar  # noqa: E402
from teodors.fuentes import era5, meteocat, terreno  # noqa: E402
from teodors.fuentes.gfs_noaa import NIVELES  # noqa: E402
from teodors.meteo.viento3d import almacen, entradas, fichero_viento  # noqa: E402
from teodors.meteo.viento3d.control import Control as LectorViento  # noqa: E402
from teodors.operacion import focos  # noqa: E402
from teodors.planta import geo  # noqa: E402
from teodors.preparacion.puffs import control_fuentes, salida  # noqa: E402
from teodors.preparacion.viento3d import pronostico  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
CASOS = RAIZ / "core" / "casos"
VIENTO_PUFFS = RAIZ / "auditor" / "casos" / "puffs" / "area_D" / "entrada" / "CALMET.DAT"
VIENTO_24H = RAIZ / "auditor" / "casos" / "viento3d" / "llano_lleida" / "referencia" / "calmet.dat"
LAT, LON = 38.6, 1.4                  # inventado, en el mar
EPSG = "EPSG:25831"
ZFACE = [0, 20, 40, 80, 160, 300, 600, 1000]
HORAS = ["H%02d" % h for h in range(24)]

JSON_PLANTA = {
    "formato": 1,
    "identidad": {"app_nombre": "Prueba", "organizacion": "ORG", "prefijo_env": "PRUEBA_CASOS", "carpeta_local": "prueba_casos", "registro": "prueba", "nombre_casos": "Planta X"},
    "proyeccion": {"epsg": EPSG, "crs_geo": "EPSG:4258"},
    "dominio": {"lado_km": 3, "margen_m": 250, "res_terreno_m": 25, "radio_edificios_km": 1, "radio_edificios_focos_m": 150, "celda_viento_m": 100, "zface": ZFACE},
    "receptores": {"por_km2": 5, "niveles": [["a", 50.0, 200.0], ["b", 100.0, 500.0], ["c", 400.0, None]],
                   "estilos": {"a": ["#111111", 1.0, "A"], "b": ["#222222", 2.0, "B"]}},
    "reanalisis": {"anios": [2023]},
    "pronostico": {"n_col": 2, "paso_col_m": 5000.0},
    "series": {"r1_km": 7.0, "rmax_km": 40.0},
}


def _planta(carpeta, quita=None):
    datos = json.loads(json.dumps(JSON_PLANTA))
    if quita:
        del datos[quita]
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
    (carpeta / "emplazamiento.json").write_text(json.dumps({"nombre": "Prueba", "lat": LAT, "lon": LON}), encoding="utf-8")
    return planta.activar(carpeta)


@pytest.fixture(autouse=True)
def sin_red_y_con_planta(tmp_path, monkeypatch):
    planta.desactivar()

    def sin_red(*a, **k):
        raise AssertionError("una prueba ha intentado salir a la red")
    monkeypatch.setattr(socket.socket, "connect", sin_red)
    monkeypatch.setattr(socket, "getaddrinfo", sin_red)
    monkeypatch.setenv("PRUEBA_CASOS_DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("PRUEBA_CASOS_LOCAL", str(tmp_path / "local"))
    _planta(tmp_path / "planta")
    yield
    planta.desactivar()


# ── el control de varias especies y fuentes, con el motor de verdad ──
@pytest.fixture
def viento(tmp_path):
    """El viento de puffs/area_D: 40 × 40 celdas de 240 m, llano a 200 m, 4 horas."""
    shutil.copy(VIENTO_PUFFS, tmp_path / "viento3d.dat")
    cab, _ = fichero_viento.leer(VIENTO_PUFFS)
    xc, yc = cab.xorig + cab.nx * cab.dgrid / 2, cab.yorig + cab.ny * cab.dgrid / 2
    ang = np.radians(np.arange(0, 360, 15))
    return SimpleNamespace(carpeta=tmp_path, cab=cab, xc=xc, yc=yc, zona=30, zface=[float(z) for z in cab.zface],
                           malla={"nx": cab.nx, "ny": cab.ny, "celda_m": cab.dgrid, "ext": (cab.xorig, cab.xorig + cab.nx * cab.dgrid, cab.yorig, cab.yorig + cab.ny * cab.dgrid)},
                           ini=pd.Timestamp(cab.ibyr, cab.ibmo, cab.ibdy, cab.ibhr),
                           recs=[(xc + r * np.sin(a), yc + r * np.cos(a), 200.0) for r in (300.0, 1500.0, 3500.0) for a in ang])


def _corre(v, nombre, especies, **fuentes):
    nom = {"viento": "viento3d.dat", "listado": nombre + ".lst", "concentraciones": nombre + ".dat"}
    control_fuentes.escribir(v.carpeta / (nombre + ".inp"), v.malla, v.zface, v.ini, 4, v.zona, especies, receptores=v.recs, nombres=nom, **fuentes)
    ejecutar(v.carpeta / (nombre + ".inp"), verbose=False)
    return v.carpeta / (nombre + ".dat")


def _cuadrado(xc, yc, lado):
    return [(xc - lado / 2, yc - lado / 2), (xc + lado / 2, yc - lado / 2), (xc + lado / 2, yc + lado / 2), (xc - lado / 2, yc + lado / 2)]


def test_la_suma_de_las_respuestas_da_la_corrida_directa(viento):
    """Área, punto (con sobreelevación) y volumen a la vez: 24 especies, cada una emitida en su hora, y una corrida con un perfil cualquiera."""
    v = viento
    area = {"id": "A1", "verts": _cuadrado(v.xc, v.yc, 100.0), "h": 2.0, "cota": 200.0}
    punto = {"id": "P1", "x": v.xc + 200.0, "y": v.yc, "h": 12.0, "cota": 200.0, "d": 1.0, "w": 10.0, "t": 400.0}
    vol = {"id": "V1", "x": v.xc - 200.0, "y": v.yc, "h": 5.0, "cota": 200.0, "sy0": 10.0, "sz0": 4.0}
    perfil = [0.3 + 0.1 * h for h in range(24)]
    perfil[:3] = [1.0, 0.25, 2.0]

    def con(f, q, especies, perf):
        return dict(f, q={e: q for e in especies}, perfil=perf)
    unidad = {e: [1.0 if k == h else 0.0 for k in range(24)] for h, e in enumerate(HORAS)}
    dat = _corre(v, "respuestas", HORAS, areas=[con(area, 1e-4, HORAS, unidad)], puntos=[con(punto, 1.0, HORAS, unidad)], volumenes=[con(vol, 1.0, HORAS, unidad)])
    R = np.array([salida.concentraciones(dat, especie=e)[1] for e in HORAS])
    assert {h for h in range(24) if R[h].max() > 0} == {23, 0, 1, 2}        # el 1.er periodo emite la hora anterior a su inicio
    directa = {"OLOR": perfil}
    C = salida.concentraciones(_corre(v, "directa", ["OLOR"], areas=[con(area, 1e-4, ["OLOR"], directa)], puntos=[con(punto, 1.0, ["OLOR"], directa)], volumenes=[con(vol, 1.0, ["OLOR"], directa)]))[1]
    suma = np.tensordot(np.array(perfil), R, axes=1)
    assert C.max() > 0 and np.abs(suma - C).max() <= 1e-6 * C.max()
    assert np.abs(R.sum(axis=0) - C).max() > 0.1 * C.max()                  # el perfil cuenta: la prueba podría fallar


def test_un_area_va_por_m2_la_misma_emision_total_da_lo_mismo_lejos(viento):
    v = viento
    lejos = {}
    for lado in (10.0, 100.0):
        foco = {"id": "A1", "modelo": "superficie", "altura_m": 2.0, "ubicacion": {"poligono": _cuadrado(v.xc, v.yc, lado)}}
        modelo, d, q0 = focos.geometria(foco, lambda x, y: 200.0)
        assert modelo == "superficie" and q0 == pytest.approx(1.0 / lado ** 2)
        d.update(q={"OLOR": q0}, perfil=None)
        lejos[lado] = salida.concentraciones(_corre(v, "lado%d" % lado, ["OLOR"], areas=[d]))[1][:, 48:]      # a 3,5 km
    a, b = lejos[10.0], lejos[100.0]
    m = a > 0.01 * a.max()
    assert m.sum() > 0 and np.abs(b[m] / a[m] - 1.0).max() < 0.05           # sin dividir por la superficie, ×100


def test_volumen_y_punto_en_lo_que_lee_el_motor():
    malla = {"nx": 10, "ny": 8, "celda_m": 400.0, "ext": (280000.0, 284000.0, 4300000.0, 4303200.0)}
    cota = lambda x, y: 55.5
    vol = {"id": "V1", "modelo": "volumen", "altura_m": 4.0, "ubicacion": {"x": 281000.0, "y": 4301000.0}, "dimensiones": {"largo_m": 30.0, "ancho_m": 12.0, "alto_m": 8.0}}
    pun = {"id": "P1", "modelo": "punto", "altura_m": 15.0, "ubicacion": {"x": 282000.0, "y": 4302000.0}, "salida": {"diametro_m": 2.0, "temperatura_C": 40.0, "velocidad_m_s": None, "caudal_m3_h": 5.0 * math.pi * 3600.0}}
    mv, dv, qv = focos.geometria(vol, cota)
    mp, dp, qp = focos.geometria(pun, cota)
    assert (mv, mp, qv, qp) == ("volumen", "punto", 1.0, 1.0)
    dv.update(q={"OLOR": 2.0}, perfil=None)
    dp.update(q={"OLOR": 3.0}, perfil=None)
    cfg = entrada.leer(control_fuentes.preparar(malla, ZFACE, pd.Timestamp("2023-02-01"), 2, 31, ["OLOR"], volumenes=[dv], puntos=[dp], receptores=[(281000.0, 4301000.0, 10.0)]).texto())
    f = {x.nombre: x for x in cfg.fuentes}
    assert f["V1"].tipo == 2 and f["V1"].sy0 == pytest.approx(math.sqrt(30.0 * 12.0) / 4.3, abs=1e-3) and f["V1"].sz0 == pytest.approx(8.0 / 2.15, abs=1e-3)
    assert (f["V1"].x, f["V1"].y, f["V1"].h, f["V1"].zbase, f["V1"].q) == (281.0, 4301.0, 4.0, 55.5, 2.0)
    assert f["P1"].tipo == 1 and (f["P1"].h, f["P1"].d, f["P1"].q) == (15.0, 2.0, 3.0)
    assert f["P1"].w == pytest.approx(5.0) and f["P1"].ts == pytest.approx(313.15)      # velocidad = caudal / sección; °C a K


def test_el_control_lleva_las_fichas_que_espera_el_motor():
    malla = {"nx": 10, "ny": 8, "celda_m": 400.0, "ext": (280000.0, 284000.0, 4300000.0, 4303200.0)}
    fac = [float(k) for k in range(24)]
    area = {"id": "A1", "verts": _cuadrado(281000.0, 4301000.0, 50.0), "h": 2.0, "cota": 10.0, "q": {"OLOR": 1e-3, "NH3": 2e-3}, "perfil": None}
    punto = {"id": "P1", "x": 282000.0, "y": 4302000.0, "h": 9.0, "cota": 11.0, "d": 1.0, "w": 5.0, "t": 300.0, "q": {"OLOR": 4.0}, "perfil": {"OLOR": fac}}
    vol = {"id": "V1", "x": 283000.0, "y": 4302000.0, "h": 3.0, "cota": 12.0, "sy0": 1.0, "sz0": 2.0, "q": {"NH3": 5.0}, "perfil": {"NH3": fac}}
    c = control_fuentes.preparar(malla, ZFACE, pd.Timestamp("2023-02-01 06:00"), 6, 31, ["olor", "nh3"], areas=[area], puntos=[punto], volumenes=[vol],
                                 receptores=[(281000.0, 4301000.0, 10.0, 0.0), (282000.0, 4302000.0, 20.0, 7.5)])
    texto = c.texto()
    assert control_fuentes.TEMPORAL not in texto
    assert all(l == "!END!" or re.fullmatch(r"! [A-Z0-9_]+ = .* !", l) for l in texto.splitlines()[1:])
    cfg = entrada.leer(texto)
    assert [e.nombre for e in cfg.especies] == ["OLOR", "NH3"]
    assert [cfg.i(k) for k in ("NSPEC", "NSE", "NPT1", "NSPT1", "NAR1", "NSAR1", "NVL1", "NSVL1", "NREC")] == [2, 2, 1, 1, 1, 0, 1, 1, 2]
    f = {x.nombre: x for x in cfg.fuentes}
    assert f["A1"].qs == pytest.approx([1e-3, 2e-3]) and f["P1"].qs == pytest.approx([4.0, 0.0]) and f["V1"].qs == pytest.approx([0.0, 5.0])
    assert f["P1"].variacion["OLOR"][0] == 1 and f["P1"].variacion["OLOR"][1] == pytest.approx(fac)
    assert f["P1"].variacion["NH3"][1] == [1.0] * 24                        # una especie sin perfil emite constante
    assert f["V1"].variacion["NH3"][1] == pytest.approx(fac) and not f["A1"].variacion
    assert cfg.receptores[1] == pytest.approx([282.0, 4302.0, 20.0, 7.5])
    with pytest.raises(ValueError, match="24 factores"):
        control_fuentes.preparar(malla, ZFACE, pd.Timestamp("2023-02-01"), 6, 31, ["OLOR"], puntos=[dict(punto, perfil={"OLOR": [1.0] * 23})])


def test_la_estela_de_un_edificio_llega_al_motor_y_cambia_el_penacho(viento):
    # usuario, 2026-11-08: el edificio de la ficha no llegaba al cálculo (indicador 0, sin 13c). Ahora la estela de `operacion.estela`, con
    # cavidad (MBDW = 2), y la orientación de la salida (FMFAC)
    from teodors.operacion import estela
    v = viento
    nave = {"ref": "N", "verts": [(v.xc - 45.0, v.yc - 30.0), (v.xc - 8.0, v.yc - 30.0), (v.xc - 8.0, v.yc + 30.0), (v.xc - 45.0, v.yc + 30.0)],
            "altura_m": 15.0, "fuente": "x", "dist_m": 8.0}
    est = estela.calcular(v.xc, v.yc, 18.0, [nave])
    punto = {"id": "P1", "x": v.xc, "y": v.yc, "h": 18.0, "cota": 200.0, "d": 1.0, "w": 8.0, "t": 300.0, "q": {"OLOR": 1.0}, "perfil": None}
    cfg = entrada.leer(control_fuentes.preparar(v.malla, v.zface, v.ini, 4, v.zona, ["OLOR"], puntos=[dict(punto, edif=estela.para_motor(est), fmfac=0.0)],
                                                receptores=v.recs).texto())
    f = cfg.fuentes[0]
    assert cfg.i("MBDW") == 2 and f.bdw == 1.0 and f.fmfac == 0.0 and list(f.edif["HEIGHT"]) == pytest.approx(est["hb"])
    assert list(f.edif["XBADJ"]) == pytest.approx(est["xadj"])
    sin = salida.concentraciones(_corre(v, "sin", ["OLOR"], puntos=[punto]))[1]
    con = salida.concentraciones(_corre(v, "con", ["OLOR"], puntos=[dict(punto, edif=estela.para_motor(est))]))[1]
    assert sin.max() > 0 and con.max() > 0 and np.abs(con - sin).max() > 0.05 * sin.max()          # la estela cuenta


def test_la_malla_del_control_es_la_del_viento(viento):
    v = viento
    area = {"id": "A1", "verts": _cuadrado(v.xc, v.yc, 100.0), "h": 2.0, "cota": 200.0, "q": {"OLOR": 1e-4}, "perfil": None}
    cfg = entrada.leer(control_fuentes.preparar(v.malla, v.zface, v.ini, 4, v.zona, ["OLOR"], areas=[area], receptores=v.recs).texto())
    assert (cfg.i("NX"), cfg.i("NY"), cfg.i("NZ")) == (v.cab.nx, v.cab.ny, v.cab.nz)
    assert [float(z) for z in cfg.lista("ZFACE")] == pytest.approx([float(z) for z in v.cab.zface])
    nom = {"viento": "viento3d.dat", "listado": "x.lst", "concentraciones": "x.dat"}
    control_fuentes.escribir(v.carpeta / "x.inp", dict(v.malla, nx=v.cab.nx - 1), v.zface, v.ini, 4, v.zona, ["OLOR"], areas=[area], receptores=v.recs, nombres=nom)
    with pytest.raises(ValueError, match="malla"):
        ejecutar(v.carpeta / "x.inp", verbose=False)


# ── la malla de receptores ──
def test_cada_nivel_fuera_del_interior_y_sin_duplicados():
    xc, yc = geo.a_utm(LAT, LON)
    recs = receptores.malla()
    xy = [(x, y) for x, y, _ in recs]
    assert len(set(xy)) == len(xy) and recs == sorted(recs)
    interior = 0.0
    tol = 0.11                                                              # redondeo a 0,1 m
    for clase, paso, semilado in receptores.niveles():
        r = planta.RADIO_CALCULO_KM * 1000.0 if semilado is None else semilado
        de = [(x - xc, y - yc) for x, y, c in recs if c == clase]
        assert de
        m = np.max(np.abs(de), axis=1)
        assert m.max() <= r + tol and (interior == 0.0 or m.min() >= interior - tol)
        assert np.abs(np.array(de) / paso - np.round(np.array(de) / paso)).max() <= tol / paso      # en su rejilla
        interior = r
    assert planta.RADIO_CALCULO_KM == 1.25 and max(np.max(np.abs(np.array(xy) - (xc, yc)), axis=1)) == pytest.approx(1200.0, abs=tol)


def test_un_receptor_con_nombre_sobrevive():
    xc, yc = geo.a_utm(LAT, LON)
    def _guarda(epsg, lista):
        planta.RECEPTORES_JSON.write_text(json.dumps({"epsg": epsg, "receptores": lista}), encoding="utf-8")
    assert receptores.con_nombre() == []                                    # sin fichero
    lista = [{"id": "r1", "nombre": "Vecino", "x": xc + 123.4, "y": yc - 56.7},
             {"id": "r2", "nombre": "Sobre la rejilla", "x": xc + 100.0, "y": yc + 100.0},
             {"id": "r3", "nombre": "Fuera", "x": xc + 5000.0, "y": yc}]
    _guarda(EPSG, lista)
    assert [r["id"] for r in receptores.con_nombre()] == ["r1", "r2", "r3"]
    por_punto = {(x, y): c for x, y, c in receptores.malla()}
    assert por_punto[(round(xc + 123.4, 1), round(yc - 56.7, 1))] == "nombrado"
    assert por_punto[(round(xc + 100.0, 1), round(yc + 100.0, 1))] == "nombrado"     # gana al de la rejilla
    assert not any(abs(x - xc) > 2000.0 for x, _ in por_punto)
    assert receptores.resumen(receptores.malla())["por_clase"]["nombrado"] == 2
    _guarda("EPSG:25830", lista)
    with pytest.raises(ValueError, match="25830"):
        receptores.malla()


@pytest.mark.skipif(find_spec("geopandas") is None, reason="sin geopandas")
def test_nucleos_y_solo_las_viviendas_son_discretos():
    import geopandas as gpd
    from shapely.geometry import Point
    xc, yc = geo.a_utm(LAT, LON)
    bld = gpd.GeoDataFrame({"uso": ["Residencial", "Industrial"]}, geometry=[Point(xc + 77.7, yc), Point(xc + 88.8, yc)], crs=EPSG)
    por_punto = {(x, y): c for x, y, c in receptores.malla([{"x": xc - 33.3, "y": yc}], bld)}
    assert por_punto[(round(xc + 77.7, 1), round(yc, 1))] == "vivienda" and (round(xc + 88.8, 1), round(yc, 1)) not in por_punto
    assert por_punto[(round(xc - 33.3, 1), round(yc, 1))] == "nucleo"


def test_estilos_y_coordenadas():
    assert receptores.niveles() == [("a", 50.0, 200.0), ("b", 100.0, 500.0), ("c", 400.0, None)]
    assert receptores.estilos() == {"a": ("#111111", 1.0, "A"), "b": ("#222222", 2.0, "B")} and list(receptores.estilos()) == ["a", "b"]
    x, y = geo.a_utm(LAT, LON)
    la, lo, c = receptores.a_geo([(x, y, "a")])[0]
    assert la == pytest.approx(LAT, abs=1e-8) and lo == pytest.approx(LON, abs=1e-8) and c == "a"


# ── columnas de GFS ──
def _ejecucion(dia, k, plazos=range(0, 25, 3)):
    """Un fichero de `gfs_noaa`: T = 10 + plazo + 100·k, para saber de qué ejecución y plazo sale un valor; presión al nivel del mar lineal en latitud."""
    plazos = list(plazos)
    lat, lon = np.arange(39.5, 37.74, -0.25), np.arange(0.5, 2.26, 0.25)
    forma = (len(plazos), len(lat), len(lon))
    pl = np.array(plazos, float)[:, None, None] * np.ones(forma)
    nubes = np.full(forma, 50.0)
    nubes[0] = np.nan                                                       # no existe en el plazo 0
    datos = {"temperature_2m": 10.0 + pl + 100.0 * k, "relative_humidity_2m": np.full(forma, 100.0), "surface_pressure": np.full(forma, 960.0),
             "pressure_msl": 1010.0 + 10.0 * (lat[None, :, None] - LAT) * np.ones(forma), "wind_u_10m": np.full(forma, 3.0), "wind_v_10m": np.full(forma, 4.0), "cloud_cover": nubes}
    for p in NIVELES:
        datos.update({f"geopotential_height_{p}hPa": np.full(forma, (1013.0 - p) * 9.0), f"temperature_{p}hPa": np.full(forma, 10.0),
                      f"wind_u_{p}hPa": np.full(forma, 0.0), f"wind_v_{p}hPa": np.full(forma, -2.0)})
    return xr.Dataset({n: (("plazo_h", "latitude", "longitude"), v) for n, v in datos.items()},
                      coords={"plazo_h": plazos, "latitude": lat, "longitude": lon, "init_time": pd.Timestamp(dia)})


def _guarda_gfs(dia, k=0, plazos=range(0, 25, 3)):
    carpeta = planta.DATOS / "meteo" / "gfs_niveles"
    carpeta.mkdir(parents=True, exist_ok=True)
    _ejecucion(dia, k, plazos).to_netcdf(carpeta / f"gfs00_{dia:%Y%m%d}.nc")


def test_columnas_interpola_entre_plazos_de_3_h():
    d0, d1 = pd.Timestamp("2023-03-09"), pd.Timestamp("2023-03-10")
    _guarda_gfs(d0, 0)
    _guarda_gfs(d1, 1)
    assert gfs_columnas.dia1(d1 + pd.Timedelta(hours=4)) == (d1, 4)
    assert gfs_columnas.dia1(d1) == (d0, 24)                                # las 00 son de la ejecución del día anterior
    ds = gfs_columnas.niveles([d0, d1])
    assert list(ds.init_time.values) == [np.datetime64(d0), np.datetime64(d1)]
    assert not np.isnan(ds.cloud_cover.values).any()                        # el plazo 0 toma el valor del siguiente
    col, xs, ys = gfs_columnas.columnas(ds, [d1, d1 + pd.Timedelta(hours=4)])
    x0, y0 = geo.a_utm(LAT, LON)
    assert xs == pytest.approx([x0 - 2500.0, x0 + 2500.0]) and ys == pytest.approx([y0 - 2500.0, y0 + 2500.0])
    assert len(col) == 2 * 2 * 2 and set(col.time) == {d1, d1 + pd.Timedelta(hours=4)}
    a = col[col.time == d1]
    b = col[col.time == d1 + pd.Timedelta(hours=4)]
    assert a.temperature_2m.values == pytest.approx(10.0 + 24.0)            # ejecución d0 (k = 0), plazo 24
    assert b.temperature_2m.values == pytest.approx(110.0 + 4.0)            # ejecución d1, 4 h: ni el plazo 3 ni el 6
    assert b.dew_point_2m.values == pytest.approx(b.temperature_2m.values)  # HR = 100 %
    assert b.wind_speed_10m.values == pytest.approx(5.0) and b.wind_direction_10m.values == pytest.approx(geo.direccion(3.0, 4.0))
    assert b.wind_speed_700hPa.values == pytest.approx(2.0) and b.wind_direction_700hPa.values == pytest.approx(0.0, abs=1e-9)    # del norte
    la = [geo.a_geo(x0 + dx, y0 + dy)[0] for dy in (-2500.0, 2500.0) for dx in (-2500.0, 2500.0)]
    assert b.sort_values(["j", "i"]).pressure_msl.values == pytest.approx(1010.0 + 10.0 * (np.array(la) - LAT), abs=1e-3)   # en el punto de cada columna


@pytest.mark.filterwarnings("ignore:In a future version of xarray")     # heredado: ver el README, ejecuciones con plazos distintos
def test_columnas_de_la_prediccion_desde_que_empieza_el_ciclo():
    ciclo, previa = pd.Timestamp("2023-03-10"), pd.Timestamp("2023-03-09")
    _guarda_gfs(previa, 0)
    _guarda_gfs(ciclo, 1, range(0, 49, 3))
    ds = gfs_columnas.niveles([previa, ciclo])
    col, _, _ = gfs_columnas.columnas(ds, [ciclo, ciclo + pd.Timedelta(hours=26)], ciclo)
    assert col[col.time == ciclo].temperature_2m.values == pytest.approx(10.0 + 24.0)     # la hora del ciclo aún es del día anterior
    assert col[col.time != ciclo].temperature_2m.values == pytest.approx(110.0 + 26.0)


def test_alturas_bajo_el_suelo_escalonadas(tmp_path):
    """Con varios niveles a la misma altura, el espesor de capa es 0 y el motor divide por cero."""
    d = pd.Timestamp("2023-03-10")
    _guarda_gfs(d)
    horas = [d + pd.Timedelta(hours=h) for h in (3, 4)]
    col, xs, ys = gfs_columnas.columnas(gfs_columnas.niveles([d]), horas)
    r = pronostico.escribir_columnas(tmp_path / "p.dat", col, 2, xs, ys, horas, NIVELES, (LAT, LON), EPSG)
    assert r["sustituciones"] == 2 * 4 * 2                                  # 1000 y 975 hPa: por debajo de los 960 de superficie
    leido = entradas.leer_3d(tmp_path / "p.dat")
    z = leido["horas"][0]["niv"]["z"]
    cota = leido["cab"]["elev"]
    assert np.all(np.diff(z, axis=0) > 0)
    assert np.all(np.abs(z[1] - z[0] - 2.0) <= 1.0) and np.all(np.abs(z[0] - cota - 10.0) <= 1.0)     # redondeados a 1 m


# ── un mes de viento 3D ──
@pytest.fixture
def datos_mes(tmp_path, monkeypatch):
    """Terreno y ERA5 inventados, sin descargar: terreno de 1,2 × 0,8 km, y `horas` da las tablas de ERA5."""
    res = 25.0
    Z, U = np.full((32, 48), 100.0), np.full((32, 48), 211, dtype=np.int32)
    x0, y0 = geo.a_utm(LAT, LON)
    tr = SimpleNamespace(a=res, c=round(x0) - 600.0, e=-res, f=round(y0) + 400.0)
    monkeypatch.setattr(terreno, "ultimo_caso", lambda lat, lon: {"caso": 1})
    monkeypatch.setattr(terreno, "cargar", lambda info: (Z, U, tr))
    d = tmp_path / "era5"
    d.mkdir()
    (d / "punto.json").write_text(json.dumps({"lat": LAT, "lon": LON, "cota_modelo_m": 120.0}), encoding="utf-8")
    monkeypatch.setattr(era5, "dir_era5", lambda lat, lon: d)

    def horas(ini, fin):
        h = list(pd.date_range(ini, fin, freq="h"))
        sfc = pd.DataFrame({"time": h, "sp": 990.0, "t2m": 15.0, "d2m": 8.0, "tp": 0.0, "ssrd": 200.0, "wdir": 200.0, "wspd": 3.0, "tcc": 0.4})
        pfl = pd.DataFrame([{"time": t, "level": lev, "height_asl_m": z, "temp_c": 20 - z / 160, "wdir": 210.0, "wspd": 4.0} for t in h for lev, z in ((975, 300), (950, 520), (850, 1500))])
        monkeypatch.setattr(era5, "cargar_sfc", lambda lat, lon, anios=None: sfc)
        monkeypatch.setattr(era5, "cargar_pfl", lambda lat, lon, anios=None: pfl)
    return horas


@pytest.fixture
def sin_geofisica(monkeypatch):
    """El fichero geofísico lanza otro proceso: basta con lanzarlo en una prueba."""
    monkeypatch.setattr(viento3d, "escribir_geo", lambda ruta, r, zona: {"nx": r["nx"], "ny": r["ny"], "categorias": [20]})


def _caso(caso):
    return json.loads((Path(caso) / "caso.json").read_text(encoding="utf-8"))


def _lee_control(caso):
    return LectorViento((Path(caso) / "viento3d.inp").read_text(encoding="utf-8"))


def test_el_mes_empieza_24_h_antes_y_las_recorta(datos_mes, sin_geofisica):
    datos_mes("2023-01-31 00:00", "2023-03-01 00:00")
    caso = viento3d.preparar_mes(2023, 2)
    assert caso == planta.DIR_TRABAJO / "viento3d" / "202302"
    info = _caso(caso)
    assert (info["arranque_h"], info["horas"], info["ini_corrida"]) == (24, 672, "2023-01-31 00:00")
    v = _lee_control(caso)
    assert [v.entero(k) for k in ("IBYR", "IBMO", "IBDY", "IBHR", "IRLG")] == [2023, 1, 31, 0, 24 + 672]
    assert [float(z) for z in v.lista("ZFACE")[0]] == [float(z) for z in ZFACE] and v.entero("NOOBS") == 2
    leido = entradas.leer_3d(caso / "pronostico3d.dat")
    assert leido["horas"][0]["fecha"] == (2023, 1, 31, 0) and leido["horas"][-1]["fecha"] == (2023, 3, 1, 0)    # con 1 h de cola
    assert viento3d.recorte_de(caso) == (2023, 2, 672, 2023 * 100000 + 32 * 100)                                # 1 de febrero, día 32


def test_sin_era5_de_antes_arranca_en_frio_y_sin_todo_el_mes_no_sigue(datos_mes, sin_geofisica):
    datos_mes("2023-02-01 00:00", "2023-03-01 00:00")
    caso = viento3d.preparar_mes(2023, 2)
    assert _caso(caso)["arranque_h"] == 0 and _caso(caso)["ini_corrida"] == "2023-02-01 00:00"
    assert _lee_control(caso).entero("IRLG") == 672 and viento3d.recorte_de(caso) is None
    datos_mes("2023-02-01 00:00", "2023-02-20 00:00")
    with pytest.raises(ValueError, match="incompleto"):
        viento3d.preparar_mes(2023, 2)


def _con_estaciones(monkeypatch):
    lista = [{"codigo": "AA", "lat": LAT + 0.1, "lon": LON, "dist_m": 9000.0}, {"codigo": "BB", "lat": LAT, "lon": LON + 0.05, "dist_m": 4000.0}]
    monkeypatch.setattr(meteocat, "cercanas", lambda lat, lon: lista)
    monkeypatch.setattr(meteocat, "para_mapa", lambda lat, lon: [{"codigo": "AA", "altura_viento_m": 2.0}, {"codigo": "BB", "altura_viento_m": None}])
    medidas = pd.DataFrame({"time": pd.date_range("2023-02-01", "2023-03-01", freq="h"), "ws": 2.0, "wd": 90.0, "t": 12.0, "rh": 60.0, "p": 1000.0})
    monkeypatch.setattr(viento3d, "obs_horarias", lambda codigo, anios, conv=None: medidas)


def test_con_estaciones_toma_los_radios_de_la_planta(datos_mes, sin_geofisica, monkeypatch):
    datos_mes("2023-02-01 00:00", "2023-03-01 00:00")
    _con_estaciones(monkeypatch)
    caso = viento3d.preparar_mes(2023, 2, estaciones=["AA", "BB"])
    v = _lee_control(caso)
    assert (v.entero("NOOBS"), v.entero("NSSTA"), v.real("R1"), v.real("R2"), v.real("RMAX1"), v.real("RMAX2")) == (1, 2, 7.0, 7.0, 40.0, 40.0)
    assert v.entero("ISURFT") == 2                                          # la estación más cercana
    assert v.cadena("SS1").startswith("'AA  '   100001") and v.cadena("SS2").startswith("'BB  '   100002")
    info = _caso(caso)
    assert (info["r1_km"], info["rmax_km"]) == (7.0, 40.0) and [e["anemometro_m"] for e in info["estaciones"]] == [2.0, 10.0]     # sin altura, 10 m
    assert (caso / "estaciones.dat").read_text().splitlines()[2] == "Meteocat XEMA, medias horarias centradas (Planta X)"
    assert "ERA5 -> pronostico 3D (Planta X)" in (caso / "pronostico3d.dat").read_text().splitlines()[0]
    v = _lee_control(viento3d.preparar_mes(2023, 2, estaciones=["AA"], r1_km=3.0, rmax_km=9.0))
    assert (v.real("R1"), v.real("RMAX1")) == (3.0, 9.0)


def test_los_radios_solo_hacen_falta_con_estaciones(datos_mes, sin_geofisica, monkeypatch, tmp_path):
    _planta(tmp_path / "sin_series", quita="series")
    datos_mes("2023-02-01 00:00", "2023-03-01 00:00")
    _con_estaciones(monkeypatch)
    assert _caso(viento3d.preparar_mes(2023, 2))["r1_km"] is None
    with pytest.raises(ValueError, match=r"series\.r1_km"):
        viento3d.preparar_mes(2023, 2, estaciones=["AA"])


def test_cada_cabecera_con_el_nombre_de_la_planta(tmp_path):
    assert viento3d.cabecera(viento3d.TITULO_ERA5) == "ERA5 -> pronostico 3D (Planta X)"
    assert viento3d.cabecera(viento3d.TITULO_GEO) == "Malla geofisica de Planta X (CORINE + MDT del IGN)"
    otra = json.loads(json.dumps(JSON_PLANTA))
    del otra["identidad"]["nombre_casos"]
    c = tmp_path / "otra"
    c.mkdir()
    (c / "planta.json").write_text(json.dumps(otra), encoding="utf-8")
    planta.activar(c)
    assert viento3d.cabecera(viento3d.TITULO_ERA5) == "ERA5 -> pronostico 3D (teOdors)"


def test_un_mes_de_una_serie_con_el_motor_de_verdad(datos_mes, monkeypatch):
    """Prepara, calcula con viento3d, saca las series y guarda SIN las horas de arranque. Con el fichero geofísico de verdad."""
    datos_mes("2023-01-31 00:00", "2023-03-01 00:00")
    monkeypatch.setattr(meteocat, "cercanas", lambda lat, lon: [{"codigo": "AA", "lat": LAT + 0.01, "lon": LON, "dist_m": 1000.0}])
    r = viento3d.mes_serie(2023, 2, "teodors", "serie_x")
    base = viento3d.dir_serie("serie_x")
    assert base == planta.DIR_VIENTO3D / "serie_x" and (r["serie"], r["r1_km"], r["rmax_km"]) == ("serie_x", 7.0, 40.0)
    fechas, u = almacen.leer_campo(base / "cmz" / "202302.cmz", "U-LEV  1")
    assert len(fechas) == 672 and fechas[0] == 2023 * 100000 + 32 * 100 and u.shape == (672, 8, 12)          # sin las 24 h de arranque
    assert sorted(f.name for f in (base / "202302").iterdir()) == sorted(viento3d.CONSERVAR)
    puntos = pd.read_csv(base / "202302" / "puntos.csv", parse_dates=["time"])
    assert set(puntos.codigo) == {"PLANTA", "AA"} and puntos.time.min() == pd.Timestamp("2023-02-01")
    assert not (planta.DIR_TRABAJO / "serie_x" / "202302").exists()
    assert viento3d.mes_serie(2023, 2, "teodors", "serie_x") == {"anio": 2023, "mes": 2, "ya_estaba": True}


def test_si_el_motor_falla_lo_dice(tmp_path):
    (tmp_path / "viento3d.inp").write_text("nada\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="viento3d falló"):
        viento3d.ejecutar(tmp_path)


def test_leer_el_fichero_de_viento_y_las_series_en_cada_punto(tmp_path, monkeypatch):
    shutil.copy(VIENTO_24H, tmp_path / "viento3d.dat")
    cab, horas = fichero_viento.leer(VIENTO_24H)
    (tmp_path / "caso.json").write_text(json.dumps({"anio": 2026, "mes": 10, "nx": cab.nx, "ny": cab.ny, "celda_m": cab.dgrid, "ext": [cab.xorig, 0, cab.yorig, 0]}), encoding="utf-8")
    c = viento3d.leer(tmp_path, niveles=(1,), campos2d=("TEMPK",))
    n = horas[0].ndathr
    assert c["horas"][0] == pd.Timestamp(n // 100000, 1, 1) + pd.Timedelta(days=(n // 100) % 1000 - 1, hours=n % 100)
    assert c["u"][1].shape == (len(horas), cab.ny, cab.nx) and c["x"][0] == cab.xorig + cab.dgrid / 2 and c["TEMPK"].shape == c["u"][1].shape
    x, y = c["x"][3], c["y"][5]
    la, lo = geo.a_geo(x, y)
    d = viento3d.viento_en_punto(c, la, lo)
    wd = (270.0 - np.degrees(np.arctan2(c["v"][1][0, 5, 3], c["u"][1][0, 5, 3]))) % 360.0
    assert d.ws[0] == pytest.approx(np.hypot(c["u"][1][0, 5, 3], c["v"][1][0, 5, 3]), rel=1e-4)
    assert d.wd[0] == pytest.approx((wd - geo.acimut_norte_en_rejilla(la, lo)) % 360.0, abs=0.05)        # geográfica, con la convergencia
    monkeypatch.setattr(meteocat, "cercanas", lambda lat, lon: [{"codigo": "AA", "lat": la, "lon": lo, "dist_m": 1.0}])
    p = viento3d.extraer_puntos(tmp_path)
    assert (tmp_path / "puntos.csv").is_file() and len(p) == 2 * len(horas) and set(p.codigo) == {"PLANTA", "AA"}


def test_las_observaciones_sin_lo_que_marco_el_control_de_calidad(monkeypatch):
    t = pd.date_range("2023-02-01 00:00", periods=4, freq="30min")
    monkeypatch.setattr(meteocat, "cargar", lambda codigo, anios=None: pd.DataFrame({"time": t, "ws": [1.0, 2.0, 3.0, 4.0], "wd": 90.0, "t": 10.0, "rh": 50.0, "p": 1000.0}))
    assert viento3d.obs_horarias("AA", [2023], conv="inicio").ws.tolist() == [1.0, 2.5, 4.0]
    qc = planta.DATOS / "reanalisis" / "01_estacion_AA" / "medidas_30min_qc.csv.gz"
    qc.parent.mkdir(parents=True)
    pd.DataFrame({"time": t, "qc": ["", "pico", "", ""]}).to_csv(qc, index=False)
    assert viento3d.obs_horarias("AA", [2023], conv="inicio").ws.tolist() == [1.0, 3.0, 4.0]             # sin la de 2 m/s
    monkeypatch.setattr(meteocat, "cargar", lambda codigo, anios=None: pd.DataFrame())
    assert viento3d.obs_horarias("AA", [2023]).empty


def test_no_arranca_si_no_cabe_el_mes(monkeypatch):
    class Sigue(Exception):
        pass

    def espera(s):
        raise Sigue
    monkeypatch.setattr(shutil, "disk_usage", lambda p: SimpleNamespace(free=9e9))
    monkeypatch.setattr(viento3d.time, "sleep", espera)
    viento3d._esperar_disco(2023, 2)                                        # 9 GB libres ≥ 4 + 4
    caso = planta.DIR_TRABAJO / "viento3d" / "202301"
    caso.mkdir(parents=True)
    (caso / "viento3d.dat").write_bytes(b"x")                               # otro mes en marcha: le faltan casi 4 GB
    assert viento3d._reservado_gb() == pytest.approx(4.0, abs=1e-6)
    with pytest.raises(Sigue):
        viento3d._esperar_disco(2023, 2)


# ── lo que no puede pasar al importar ──
def _leidos(nodos):
    return {n.id for nodo in nodos for n in ast.walk(nodo) if isinstance(n, ast.Name)}


FICHEROS = sorted(f.name for f in CASOS.glob("*.py"))


@pytest.mark.parametrize("fichero", FICHEROS)
def test_nada_lee_la_planta_al_importar_ni_en_un_valor_por_defecto(fichero):
    arbol = ast.parse((CASOS / fichero).read_text(encoding="utf-8"))
    fuera = [n for n in arbol.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))]
    assert not _leidos(fuera) & {"config", "planta", "geo"}
    defectos = [d for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) for d in n.args.defaults + [k for k in n.args.kw_defaults if k]]
    assert not _leidos(defectos) & {"config", "planta", "geo"}


def test_al_importar_no_hay_planta_activa(tmp_path):
    env = procesos.entorno()
    env.pop(planta.ENV_PLANTA, None)
    codigo = ("import sys\nimport teodors.casos.gfs_columnas, teodors.casos.receptores, teodors.casos.viento3d\nfrom teodors import planta\n"
              "print(planta._activa)")
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "None"
    r = subprocess.run([sys.executable, "-c", "import sys, teodors.preparacion.puffs.control_fuentes\nprint('teodors.planta' in sys.modules, 'teodors.fuentes' in sys.modules)"],
                       capture_output=True, text=True, encoding="utf-8", cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "False False"                                # el control no necesita ni planta ni fuentes


def test_readme_con_sus_ficheros():
    tabla = (CASOS / "README.md").read_text(encoding="utf-8").split("## Ficheros")[1]
    for f in FICHEROS:
        assert f"`{f}`" in tabla
