# -*- coding: utf-8 -*-
"""metricas · validación del viento frente a las estaciones, SIN RED, con una planta y unas estaciones inventadas a propósito. Referencias
externas: los umbrales de Emery, Tai y Yarwood (2001), el índice de Willmott (1981) a mano, la geometría del círculo y la salida del sol
en dos fechas conocidas. No dicen lo bien que acierta ningún modelo en ningún sitio."""
import ast
import json
import os
import socket
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from teodors import planta
from teodors.comun import procesos
from teodors.fuentes import era5, meteocat
from teodors.metricas import calidad, viento
from teodors.planta import geo
from teodors.preparacion.viento3d.estaciones import medias_horarias

METRICAS = Path(__file__).resolve().parents[3] / "core" / "metricas"
LAT, LON = 39.75, 1.25                # inventado: el mediodía solar cae a las 11,92 h UTC
con_matplotlib = pytest.mark.skipif(find_spec("matplotlib") is None, reason="sin matplotlib")

JSON_PLANTA = {
    "formato": 1,
    "identidad": {"app_nombre": "Prueba", "organizacion": "ORG", "prefijo_env": "PRUEBA_METRICAS", "carpeta_local": "prueba_metricas", "registro": "prueba"},
    "proyeccion": {"epsg": "EPSG:25831", "crs_geo": "EPSG:4258"},
    "dominio": {"lado_km": 20, "margen_m": 250, "res_terreno_m": 100, "radio_edificios_km": 1, "radio_edificios_focos_m": 150, "celda_viento_m": 500, "zface": [0, 20, 40, 80]},
    "receptores": {"por_km2": 5},
    "reanalisis": {"anios": [2023]},
    "estaciones": {"radio_km": 30.0, "objetivo": "AA", "ceros_sospechosos": {"AA": "2023-07-01"}},
}


def _planta(carpeta, estaciones=None):
    datos = json.loads(json.dumps(JSON_PLANTA))
    datos["estaciones"].update(estaciones or {})
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
    monkeypatch.setenv("PRUEBA_METRICAS_DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("PRUEBA_METRICAS_LOCAL", str(tmp_path / "local"))
    _planta(tmp_path / "planta")
    yield
    planta.desactivar()


def _horas(ws, wd, t=15.0):
    return pd.DataFrame({"time": pd.date_range("2023-01-01", periods=len(ws), freq="h"), "ws": np.asarray(ws, float), "wd": np.asarray(wd, float), "t": t})


def _anio(cambios=(), anio=2023):
    """Un año de medias de 30 min con la etiqueta de INICIO: viento del E que nunca se repite y radiación con su ciclo. `cambios`: (instante, columna, valor)."""
    t = pd.date_range(f"{anio}-01-01", f"{anio}-12-31 23:30", freq="30min")
    i = np.arange(len(t))
    sol = geo.elevacion_solar(pd.Series(t + pd.Timedelta(minutes=15)), LAT, LON)    # el centro de la media, 15 min después de su etiqueta
    df = pd.DataFrame({"time": t, "ws": 3.0 + 0.01 * (i % 7), "wd": 90.0 + 0.1 * (i % 5), "t": 15.0 + 0.01 * (i % 3), "rh": 60.0, "p": 1000.0, "pr": 0.0,
                       "rad": 800.0 * np.maximum(np.sin(np.radians(sol)), 0.0), "altura_viento_m": 10.0})
    for instante, columna, valor in cambios:
        df.loc[df.time == pd.Timestamp(instante), columna] = valor
    return df


def _estaciones(**tablas):
    """Inventario y lecturas en la caché de meteocat, como si ya estuvieran descargados."""
    inv = [{"codi_estacio": c, "nom_estacio": f"Estación {c}", "latitud": str(LAT + 0.05), "longitud": str(LON + 0.05), "altitud": "50", "codi_estat_ema": "2"} for c in tablas]
    meteocat.dir_meteocat().mkdir(parents=True, exist_ok=True)
    (meteocat.dir_meteocat() / "estaciones.json").write_text(json.dumps(inv), encoding="utf-8")
    for c, df in tablas.items():
        f = meteocat.dir_meteocat() / c / "2023.csv"
        f.parent.mkdir(parents=True)
        df.to_csv(f, index=False)


# ── métricas ──
@pytest.mark.parametrize("giro", [0.0, 37.0, 90.0, 180.0, 355.0])
def test_el_error_de_direccion_es_circular_y_no_depende_del_norte(giro):
    # 350° frente a 10° son 20°, no 340°, y girar todo el conjunto no cambia nada
    m = viento.metricas(_horas([5, 6], (np.array([10.0, 350.0]) + giro) % 360), _horas([5, 6], (np.array([350.0, 10.0]) + giro) % 360), 0.0, 0.0, 10)
    assert m["wd_error"] == pytest.approx(20.0) and m["wd_sesgo"] == pytest.approx(0.0)
    m = viento.metricas(_horas([5, 6], (np.array([10.0, 10.0]) + giro) % 360), _horas([5, 6], (np.array([350.0, 350.0]) + giro) % 360), 0.0, 0.0, 10)
    assert m["wd_error"] == pytest.approx(20.0) and m["wd_sesgo"] == pytest.approx(-20.0)


def test_metricas_a_mano():
    obs, mod = _horas([2, 4, 6, 8], [0, 0, 0, 0], 15.0), _horas([3, 3, 7, 9], [0, 0, 0, 0], 16.0)
    m = viento.metricas(obs, mod, altitud_est=200.0, cota_era5=100.0, altura_viento=10)
    # diferencias +1, −1, +1, +1
    assert m["horas"] == 4 and m["ws_obs"] == 5.0 and m["ws_mod"] == 5.5
    assert m["ws_sesgo"] == pytest.approx(0.5) and m["ws_rmse"] == pytest.approx(1.0)
    # 100 m por encima de la cota del modelo: 16 − 0,65 = 15,35 frente a 15
    assert m["t_sesgo"] == pytest.approx(0.35) and m["t_error"] == pytest.approx(0.35)
    assert m["ws_ioa"] == pytest.approx(1 - 4 / 92)


def test_metricas_lleva_la_estacion_a_10_m_y_solo_las_horas_comunes():
    obs, mod = _horas([1.0, 2.0, 0.3], [90, 90, 90]), _horas([1.0, 2.0, 0.3, 9.0], [90, 90, 90, 90])
    m = viento.metricas(obs, mod, 0.0, 0.0, 2)
    # ley logarítmica de 2 a 10 m con z0 = 0,1 m: ln(100) / ln(20) = 1,5372
    assert m["horas"] == 3 and m["ws_obs"] == pytest.approx(3.3 * 1.5372 / 3, abs=1e-3)
    # solo con viento ≥ 1 m/s en los dos lados: la 3.ª hora no cuenta, y es la única calma (0,46 m/s a 10 m)
    assert m["wd_horas"] == 2 and m["calmas_obs"] == pytest.approx(100 / 3) and m["calmas_mod"] == pytest.approx(100 / 3)
    assert viento.metricas(obs, mod, 0.0, 0.0, None)["ws_obs"] == pytest.approx(1.1)


def test_umbrales_de_emery():
    assert viento.UMBRALES == {"ws_rmse": 2.0, "ws_sesgo": 0.5, "ws_ioa": 0.6, "wd_error": 30.0, "wd_sesgo": 10.0, "t_error": 2.0, "t_sesgo": 0.5}


@pytest.mark.parametrize("clave, dws, dwd, dt, cumple", [
    ("ws_rmse", (2.0, -2.0), (0, 0), (0, 0), True), ("ws_rmse", (2.5, -2.5), (0, 0), (0, 0), False),
    ("ws_sesgo", (-0.5, -0.5), (0, 0), (0, 0), True), ("ws_sesgo", (-0.75, -0.75), (0, 0), (0, 0), False),
    ("wd_error", (0, 0), (30, -30), (0, 0), True), ("wd_error", (0, 0), (31, -31), (0, 0), False),
    ("wd_sesgo", (0, 0), (10, 10), (0, 0), True), ("wd_sesgo", (0, 0), (11, 11), (0, 0), False),
    ("t_error", (0, 0), (0, 0), (2.0, -2.0), True), ("t_error", (0, 0), (0, 0), (2.5, -2.5), False),
    ("t_sesgo", (0, 0), (0, 0), (0.5, 0.5), True), ("t_sesgo", (0, 0), (0, 0), (0.75, 0.75), False),
])
def test_cumple_justo_en_el_umbral_y_no_justo_despues(clave, dws, dwd, dt, cumple):
    obs = _horas([10.0, 12.0], [100.0, 100.0], 15.0)
    mod = _horas(np.array([10.0, 12.0]) + dws, 100.0 + np.array(dwd), 15.0 + np.array(dt))
    assert viento.metricas(obs, mod, 0.0, 0.0, 10)["cumple"][clave] is cumple


def test_ioa_a_mano(monkeypatch):
    obs = np.array([1.0, 2.0, 3.0])
    assert viento.ioa(obs, obs) == 1.0
    assert viento.ioa(np.array([2.0, 2.0, 2.0]), obs) == 0.0
    assert viento.ioa(np.array([1.0, 2.0, 4.0]), obs) == pytest.approx(12 / 13)
    assert np.isnan(viento.ioa(np.ones(3), np.ones(3)))
    for valor, cumple in ((0.6, True), (0.59, False)):
        monkeypatch.setattr(viento, "ioa", lambda m, o, v=valor: v)
        assert viento.metricas(_horas([5, 6], [0, 0]), _horas([5, 6], [0, 0]), 0.0, 0.0, 10)["cumple"]["ws_ioa"] is cumple


def test_era5_horario_con_sus_unidades(monkeypatch):
    pedidos = []
    tabla = pd.DataFrame({"time": pd.to_datetime(["2023-01-01"]), "u10": [3.0], "v10": [4.0], "t2m": [283.15], "ssrd": [7200.0]})
    monkeypatch.setattr(era5, "serie_sfc", lambda la, lo, anios: pedidos.append(anios) or tabla)
    s = viento.era5_horario(LAT, LON).iloc[0]
    # hacia el NE: viene del SO. ssrd va en J/m² acumulados en la hora
    assert s.ws == 5.0 and s.wd == pytest.approx(216.87, abs=0.01) and s.t == pytest.approx(10.0) and s.rad == 2.0
    assert pedidos == [(2023,)]


# ── hora de las estaciones ──
@pytest.mark.parametrize("lon", [-40.0, -6.0, 1.25, 35.0])
def test_convencion_por_el_mediodia_solar_de_cada_longitud(lon):
    # una ventana fija alrededor de las 12 UTC tomaría a −6° el inicio por el final
    t = pd.date_range("2023-01-01", "2023-12-31 23:30", freq="30min")
    def tabla(minutos):
        return pd.DataFrame({"time": t, "rad": np.maximum(geo.elevacion_solar(pd.Series(t + pd.Timedelta(minutes=minutos)), LAT, lon), 0.0)})
    assert viento.convencion(tabla(15), viento.mediodia_solar(lon))[0] == "inicio"
    assert viento.convencion(tabla(-15), viento.mediodia_solar(lon))[0] == "fin"


@pytest.mark.parametrize("c, sale", [(11.4, "inicio"), (11.999, "inicio"), (12.0, "fin"), (12.599, "fin"), (11.399, None), (12.6, None), (13.5, None)])
def test_ventana_de_la_convencion(monkeypatch, c, sale):
    monkeypatch.setattr(viento, "centroide_radiacion", lambda df: c)
    if sale is None:
        with pytest.raises(ValueError, match="no parece UTC"):
            viento.convencion(None, 12.0)
    else:
        assert viento.convencion(None, 12.0) == (sale, c)


def test_el_mediodia_sale_de_la_planta(monkeypatch, tmp_path):
    assert viento.mediodia_solar(0.0) == 12.0 and viento.mediodia_solar(15.0) == 11.0 and viento.mediodia_solar(-15.0) == 13.0
    monkeypatch.setattr(viento, "centroide_radiacion", lambda df: 11.95)
    assert viento.convencion(None)[0] == "fin"                                # sin el campo: 12 − 1,25 / 15 = 11,92 h
    _planta(tmp_path / "otra", {"mediodia_utc_h": 12.0})
    assert viento.convencion(None)[0] == "inicio"


def test_a_horario_exige_las_dos_medias_y_medias_horarias_no():
    # NO son la misma función aunque se parezcan: no fundirlas sin medir. Las horas que valida cada una son distintas
    df = pd.DataFrame({"time": pd.to_datetime(["2023-01-01 00:30", "2023-01-01 01:00", "2023-01-01 02:00"]), "ws": [2.0, 2.0, 5.0], "wd": [0.0, 90.0, 180.0],
                       "t": [10.0, 12.0, 20.0], "rh": 50.0, "p": 1000.0})
    dos, una = viento.a_horario(df, "inicio"), medias_horarias(df, "inicio")
    assert dos.time.tolist() == [pd.Timestamp("2023-01-01 01:00")]
    assert una.time.tolist() == [pd.Timestamp("2023-01-01 01:00"), pd.Timestamp("2023-01-01 02:00")]
    # en la hora común dan lo mismo: la dirección sale del vector (del N y del E: del NE) y la velocidad, de la media escalar
    assert dos.ws[0] == una.ws[0] == 2.0 and dos.wd[0] == pytest.approx(45.0) and dos.wd[0] == una.wd[0] and dos.t[0] == una.t[0] == 11.0
    assert viento.a_horario(df, "fin").empty                                  # con «fin», 00:30 y 01:00 caen en horas distintas


# ── rosas ──
def test_la_rosa_y_las_calmas_suman_100():
    rng = np.random.default_rng(3)
    ws, wd = rng.uniform(0.0, 12.0, 2000), rng.uniform(0.0, 360.0, 2000)
    f, calmas = viento.rosa(ws, wd)
    assert f.sum() + calmas == pytest.approx(100.0) and calmas == pytest.approx(100 * (ws < viento.CALMA).mean())
    tabla, calmas2 = viento._rosa_clases(ws, wd)
    assert calmas2 == calmas and np.sum(tabla) + calmas2 == pytest.approx(100.0, abs=0.05)    # cada casilla, redondeada a 3 decimales


@pytest.mark.parametrize("wd, sectores, sector", [(337.5, 8, 0), (337.49, 8, 7), (22.5, 8, 1), (22.49, 8, 0), (337.5, 16, 15), (22.5, 16, 1),
                                                  (348.75, 16, 0), (348.74, 16, 15), (11.25, 16, 1), (11.24, 16, 0), (0.0, 16, 0), (360.0, 16, 0)])
def test_sector_en_los_bordes(wd, sectores, sector):
    # con 8 sectores, 337,5° y 22,5° son bordes (el inferior es suyo); con 16, son los centros de NNO y NNE
    f, calmas = viento.rosa(np.array([5.0]), np.array([wd]), sectores)
    assert f[sector] == 100.0 and f.sum() == 100.0 and calmas == 0.0
    assert np.array(viento._rosa_clases([5.0], [wd], sectores)[0])[sector, 2] == 100.0


@pytest.mark.parametrize("ws, clase", [(0.49, None), (0.5, 0), (1.99, 0), (2.0, 1), (4.0, 2), (6.0, 3), (7.99, 3), (8.0, 4), (30.0, 4)])
def test_clases_de_velocidad(ws, clase):
    tabla, calmas = viento._rosa_clases([ws], [90.0])
    assert calmas == (100.0 if clase is None else 0.0)
    assert np.array(tabla)[4].tolist() == [100.0 if k == clase else 0.0 for k in range(5)]


def test_rosas_estaciones_con_su_cache(monkeypatch):
    _estaciones(AA=_anio())
    f = era5.dir_era5(LAT, LON) / "serie_sfc_2023_2023.csv"
    f.parent.mkdir(parents=True)
    t = pd.date_range("2023-01-01", "2023-12-31 23:00", freq="h")
    pd.DataFrame({"time": t, "u10": 0.0, "v10": -5.0, "t2m": 288.15, "ssrd": 0.0}).to_csv(f, index=False)            # ERA5, del N
    r = viento.rosas_estaciones(LAT, LON)["estaciones"]["AA"]
    assert r["horas"] == 8759 and r["altura_m"] == 10.0 and r["desde"] == r["hasta"] == "2023"                        # sin la 1.ª: solo tiene una media
    assert np.array(r["obs"])[4, 1] == pytest.approx(100.0) and r["calmas"] == 0.0                                    # del E, a 3 m/s
    assert r["era5"][0] == pytest.approx(100.0) and sum(r["era5"][1:]) == 0.0
    def no_recalcula(*a):
        raise AssertionError("tenía que salir de la caché")
    monkeypatch.setattr(viento, "era5_horario", no_recalcula)
    assert viento.rosas_estaciones(LAT, LON)["estaciones"]["AA"] == r
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 10))                                                          # los datos cambian: se recalcula
    with pytest.raises(AssertionError, match="caché"):
        viento.rosas_estaciones(LAT, LON)


def test_rosas_dia_solo_lo_medido_ese_dia():
    _estaciones(AA=_anio(), BB=_anio().iloc[:48])                                                                     # BB acaba el 1 de enero
    r = viento.rosas_dia(LAT, LON, "2023-03-15")
    assert list(r["estaciones"]) == ["AA"] and r["dia"] == "2023-03-15" and r["estaciones"]["AA"]["horas"] == 24
    assert np.sum(r["estaciones"]["AA"]["obs"]) + r["estaciones"]["AA"]["calmas"] == pytest.approx(100.0)


@con_matplotlib
def test_figura_rosas(tmp_path):
    rosa = viento.rosa(np.array([5.0, 0.1]), np.array([90.0, 0.0]))
    viento.figura_rosas({"ERA5": rosa, "Modelo": rosa, "Estación": rosa, "Otra": rosa}, tmp_path / "rosas.png")
    assert (tmp_path / "rosas.png").read_bytes()[:4] == b"\x89PNG"


# ── control de calidad ──
def _semihoras(n, ini="2023-06-30 12:00"):
    i = np.arange(n)
    return pd.DataFrame({"time": pd.date_range(ini, periods=n, freq="30min"), "ws": 3.0 + 0.1 * (i % 5), "wd": 100.0 + i % 7, "t": 15.0})


def test_medidas_limpias_sin_marcas():
    d, res = calidad.control_calidad(_semihoras(40))
    assert (d.qc == "").all() and res == {"medidas_30min": 40, "duplicadas": 0, "rango": 0, "atasco_wd": 0, "atasco_ws": 0, "pico": 0, "cero_sensor": 0}


def test_duplicados_se_quitan_y_queda_ordenado():
    df = _semihoras(5)
    d, res = calidad.control_calidad(pd.concat([df.iloc[::-1], df.iloc[[2]]]))
    assert res["medidas_30min"] == 6 and res["duplicadas"] == 1 and len(d) == 5
    assert d.time.is_monotonic_increasing and d.time.is_unique


@pytest.mark.parametrize("columna, valor, marca", [("ws", 60.0, False), ("ws", 60.5, True), ("ws", -0.1, True), ("wd", 360.0, False), ("wd", 361.0, True), ("wd", -1.0, True),
                                                   ("t", 50.0, False), ("t", 50.5, True), ("t", -30.0, False), ("t", -30.5, True)])
def test_rangos(columna, valor, marca):
    df = _semihoras(5)
    df.loc[2, columna] = valor
    d, res = calidad.control_calidad(df)
    assert res["rango"] == int(marca) and ("rango;" in d.qc[2]) is marca


@pytest.mark.parametrize("columna, n, marcadas", [("wd", 11, 0), ("wd", 12, 12), ("ws", 11, 0), ("ws", 12, 12)])
def test_atasco_desde_6_horas_seguidas(columna, n, marcadas):
    df = _semihoras(30)
    df.loc[5:4 + n, columna] = 123.0 if columna == "wd" else 4.56
    assert calidad.control_calidad(df)[1][f"atasco_{columna}"] == marcadas


def test_no_es_atasco_sin_viento():
    df = _semihoras(30)
    df.loc[5:20, "ws"] = 0.5
    df.loc[5:20, "wd"] = 123.0
    res = calidad.control_calidad(df)[1]
    assert res["atasco_wd"] == 0 and res["atasco_ws"] == 16                    # la dirección no está definida, pero 0,5 m/s fijos sí son sospechosos
    df.loc[5:20, "ws"] = 0.0
    assert calidad.control_calidad(df)[1]["atasco_ws"] == 0                    # una calma larga es una calma


def test_pico_de_velocidad():
    df = _semihoras(6)
    df.loc[3, "ws"] = 13.6                                                     # de 3,2 a 13,6: 10,4 m/s de salto, y otro al bajar
    d, res = calidad.control_calidad(df)
    assert res["pico"] == 2 and d.qc[3] == "pico;" and d.qc[4] == "pico;"
    df.loc[3, "ws"] = 13.0
    assert calidad.control_calidad(df)[1]["pico"] == 0


def test_los_ceros_sospechosos_solo_desde_su_fecha():
    df = _semihoras(100)                                                       # del 30 de junio a las 12 al 2 de julio
    antes, justo, despues = 10, df.index[df.time == "2023-07-01 00:00"][0], 80
    df.loc[[antes, justo, despues], "ws"] = 0.0
    d, res = calidad.control_calidad(df, "2023-07-01")
    assert res["cero_sensor"] == 2
    assert d.qc[antes] == "" and d.qc[justo] == "cero_sensor;" and d.qc[despues] == "cero_sensor;"
    assert calidad.control_calidad(df)[1]["cero_sensor"] == 0                  # sin fecha, un cero es un cero


# ── la orden completa ──
@con_matplotlib
def test_la_orden_completa_separa_el_dia_y_la_noche_por_el_sol(monkeypatch):
    # A 39,75° N y 1,25° E, con cos H = −tan φ · tan δ, sale el sol sobre las 4,5 h UTC el 21 de junio y las 7,3 h el 21 de diciembre: la
    # misma hora, las 05 UTC, es de día en junio y de noche en diciembre. Del N una, del S la otra; todas las demás, del E.
    cambios = [(f"2023-06-21 {h}", "wd", 0.0) for h in ("04:30", "05:00")] + [(f"2023-12-21 {h}", "wd", 180.0) for h in ("04:30", "05:00")]
    cambios += [("2023-03-01 10:00", "ws", 0.0), ("2023-08-01 10:00", "ws", 0.0)]        # la fecha de AA es el 1 de julio
    _estaciones(AA=_anio(cambios), BB=_anio(cambios))
    monkeypatch.setattr(sys, "argv", ["x"])
    calidad.main()
    salida = planta.DATOS / "reanalisis" / "01_estacion_AA"
    r = json.loads((salida / "resumen.json").read_text(encoding="utf-8"))
    assert r["estacion"] == "AA" and r["convencion_hora"] == "inicio" and r["horas_periodo"] == 8760
    assert r["cero_sensor"] == 1 and r["horas_validas"] == 8758                          # sin la 1.ª hora ni la que perdió su media por el cero
    t = pd.read_csv(salida / "rosas_observadas.csv")
    clases = ["0.5-2", "2-4", "4-6", "6-8", ">=8"]
    def horas(grupo, sector):
        return t[(t.subconjunto == grupo) & (t.sector == sector)][clases].to_numpy().sum()
    assert horas("día", "N") > 0 and horas("noche", "N") == 0 and horas("noche", "S") > 0 and horas("día", "S") == 0
    dia, noche = (int(t[t.subconjunto == g].horas.iloc[0]) for g in ("día", "noche"))
    assert dia + noche == 8758 and 4200 < dia < 4600                                     # en un año, algo más de la mitad
    for f in ("medidas_30min_qc.csv.gz", "horario_valido.csv", "rosas_total_y_anios.png", "rosas_estaciones_dia_noche.png"):
        assert (salida / f).stat().st_size > 0

    # otra estación: los ceros sospechosos son de cada una
    monkeypatch.setattr(calidad, "figura", lambda *a: None)
    monkeypatch.setattr(sys, "argv", ["x", "--codigo", "BB"])
    calidad.main()
    r = json.loads((planta.DATOS / "reanalisis" / "01_estacion_BB" / "resumen.json").read_text(encoding="utf-8"))
    assert r["estacion"] == "BB" and r["cero_sensor"] == 0 and r["horas_validas"] == 8759


def test_ayuda_sin_planta(monkeypatch):
    planta.desactivar()
    monkeypatch.setattr(sys, "argv", ["x", "--help"])
    with pytest.raises(SystemExit) as e:
        calidad.main()
    assert e.value.code == 0


# ── lo que no puede pasar al importar ──
def _leidos(nodos):
    return {n.id for nodo in nodos for n in ast.walk(nodo) if isinstance(n, ast.Name)}


@pytest.mark.parametrize("fichero", sorted(f.name for f in METRICAS.glob("*.py")))
def test_nada_lee_la_planta_al_importar_ni_en_un_valor_por_defecto(fichero):
    arbol = ast.parse((METRICAS / fichero).read_text(encoding="utf-8"))
    fuera = [n for n in arbol.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))]
    fuera = [n for n in fuera if not (isinstance(n, ast.If) and "__name__" in _leidos([n.test]))]
    assert not _leidos(fuera) & {"config", "planta", "geo"}
    defectos = [d for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) for d in n.args.defaults + [k for k in n.args.kw_defaults if k]]
    assert not _leidos(defectos) & {"config", "planta", "geo"}


def test_al_importar_no_hay_planta_activa_ni_se_carga_matplotlib(tmp_path):
    env = procesos.entorno()
    env.pop(planta.ENV_PLANTA, None)
    codigo = "import sys\nimport teodors.metricas.calidad, teodors.metricas.viento\nfrom teodors import planta\nprint(planta._activa, 'matplotlib' in sys.modules)"
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "None False"


def test_readme_con_sus_ficheros():
    tabla = (METRICAS / "README.md").read_text(encoding="utf-8").split("## Ficheros")[1]
    for f in sorted(f.name for f in METRICAS.glob("*.py")):
        assert f"`{f}`" in tabla
