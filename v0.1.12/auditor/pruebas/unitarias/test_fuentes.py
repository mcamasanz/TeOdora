# -*- coding: utf-8 -*-
"""fuentes · de un servicio de internet a los ficheros de la planta, SIN RED: las respuestas se simulan y una conexión de verdad hace
fallar la prueba. La planta de prueba está inventada a propósito. Referencias externas: pyproj (reproyección), la ley logarítmica
del viento, las unidades de ERA5 y las clases de ASPRS. Lo que esto no comprueba: que los servicios sigan respondiendo así."""
import ast
import io
import json
import logging
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from pyproj import Transformer
from rasterio.transform import from_origin

from teodors import planta
from teodors.comun import procesos, registro
from teodors.comun.errores import Cancelado
from teodors.fuentes import catastro, descargar_era5, descargar_meteocat, era5, gfs_dynamical, gfs_noaa, lidar, meteocat, terreno
from teodors.planta import geo
from teodors.preparacion.viento3d.estaciones import medias_horarias

RAIZ = Path(__file__).resolve().parents[3]
FUENTES = RAIZ / "core" / "fuentes"
LAT, LON = 39.75, 1.25                # inventado: al este del meridiano 0, en el huso 31; el servicio trabaja en el 30

con_geopandas = pytest.mark.skipif(find_spec("geopandas") is None or find_spec("pyogrio") is None, reason="sin geopandas")
con_requests = pytest.mark.skipif(find_spec("requests") is None, reason="sin requests")
con_xarray = pytest.mark.skipif(find_spec("xarray") is None or find_spec("netCDF4") is None, reason="sin xarray o netCDF4")

JSON_PLANTA = {
    "formato": 1,
    "identidad": {"app_nombre": "Prueba", "organizacion": "ORG", "prefijo_env": "PRUEBA_FUENTES", "carpeta_local": "prueba_fuentes",
                  "registro": "prueba", "agente_http": "agente-general"},
    "proyeccion": {"epsg": "EPSG:25831", "crs_geo": "EPSG:4258"},
    "dominio": {"lado_km": 20, "margen_m": 250, "res_terreno_m": 100, "radio_edificios_km": 1, "radio_edificios_focos_m": 150,
                "celda_viento_m": 500, "zface": [0, 20, 40, 80]},
    "receptores": {"por_km2": 5},
    "reanalisis": {"anios": [2022, 2023]},
    "estaciones": {"radio_km": 30.0, "agente_http": "agente-estaciones"},
    "pronostico": {"caja_gfs": {"lat": [50.0, 50.5], "lon": [-0.5, 0.5]}, "semanas_mos": ["2023-03-06"]},
}


@pytest.fixture(autouse=True)
def sin_red_y_con_planta(tmp_path, monkeypatch):
    planta.desactivar()
    def sin_red(*a, **k):
        raise AssertionError("una prueba ha intentado salir a la red")
    monkeypatch.setattr(socket.socket, "connect", sin_red)
    monkeypatch.setattr(socket, "getaddrinfo", sin_red)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setenv("PRUEBA_FUENTES_DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("PRUEBA_FUENTES_LOCAL", str(tmp_path / "local"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "usuario"))              # la clave de verdad no se lee nunca
    monkeypatch.delenv("PRUEBA_FUENTES_CORINE", raising=False)
    carpeta = tmp_path / "planta"
    carpeta.mkdir()
    (carpeta / "planta.json").write_text(json.dumps(JSON_PLANTA), encoding="utf-8")
    (carpeta / "emplazamiento.json").write_text(json.dumps({"nombre": "Prueba", "lat": LAT, "lon": LON}), encoding="utf-8")
    planta.activar(carpeta)
    yield
    planta.desactivar()


def _urlopen(monkeypatch, *respuestas):
    """urlopen simulado: cada llamada da la siguiente respuesta (bytes) o lanza la excepción. Devuelve la lista de peticiones."""
    pedidas, pendientes = [], list(respuestas)
    def urlopen(req, timeout=None, context=None):
        pedidas.append(req)
        r = pendientes.pop(0)
        if isinstance(r, Exception):
            raise r
        return io.BytesIO(r)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return pedidas


# ── MDT: el WCS del IGN ──
MULTIPART = ("--frontera\r\nContent-Type: text/xml\r\n\r\n<gml>metadatos</gml>\r\n--frontera\r\nContent-Type: application/asc\r\n\r\n"
             "ncols 3\r\nnrows 2\r\nxllcorner 500000.0\r\nyllcorner 4000000.0\r\ncellsize 25.0\r\n0.0 0.0 12.5\r\n7.0 30.0 40.0\r\n--frontera--\r\n")


def test_wcs_multipart_y_sobre_el_mar_el_cero_es_cero():
    # sobre el mar el servicio da 0 m y su cabecera no trae nodata: 0 es una cota, no «sin dato»; los datos acaban en la primera «--»
    z, tr, nodata = terreno._parse_asc(MULTIPART)
    assert z.tolist() == [[0.0, 0.0, 12.5], [7.0, 30.0, 40.0]] and nodata is None
    assert (tr.c, tr.f, tr.a, tr.e) == (500000.0, 4000050.0, 25.0, -25.0)


def test_wcs_centro_de_celda_nodata_y_respuestas_malas():
    asc = "ncols 2\nnrows 1\nxllcenter 112.5\nyllcenter 212.5\ncellsize 25\nnodata_value -9999\n1 -9999\n"
    z, tr, nodata = terreno._parse_asc(asc)
    assert nodata == -9999.0 and (tr.c, tr.f) == (100.0, 225.0)
    with pytest.raises(ValueError, match="grid ASC"):
        terreno._parse_asc("<ows:ExceptionReport>demasiado grande</ows:ExceptionReport>")
    with pytest.raises(ValueError, match="incompleto"):
        terreno._parse_asc("ncols 2\nnrows 2\ncellsize 25\nxllcorner 0\nyllcorner 0\n1 2 3\n")


def test_wcs_reintenta_y_se_presenta_con_el_agente_de_la_planta(monkeypatch):
    pedidas = _urlopen(monkeypatch, urllib.error.URLError("corte"), b"<ExceptionReport/>", MULTIPART.encode("latin-1"))
    z, _, _ = terreno._wcs_tramo("Elevacion25830_25", (1.0, 2.0, 3.0, 4.0))
    assert len(pedidas) == 3 and z.shape == (2, 3)
    url = pedidas[-1].full_url
    assert "coverageId=Elevacion25830_25" in url and "subset=x(1.00,3.00)" in url and "subset=y(2.00,4.00)" in url
    assert pedidas[-1].get_header("User-agent") == "agente-general"
    _urlopen(monkeypatch, *[TimeoutError()] * 4)
    with pytest.raises(RuntimeError, match="no respondió tras 4 intentos"):
        terreno._wcs_tramo("Elevacion25830_25", (1.0, 2.0, 3.0, 4.0))


def _servicio_mdt(z_mar=0.0):
    """El servicio inventado: en su huso, un plano con 1 km de tierra al este del centro y después mar."""
    xc, yc = Transformer.from_crs("EPSG:4326", terreno.WCS_CRS, always_xy=True).transform(LON, LAT)

    def tramo(cobertura, bb):
        cs = 25.0
        xs = np.arange(np.floor(bb[0] / cs) * cs + cs / 2, bb[2] + cs, cs)
        ys = np.arange(np.ceil(bb[3] / cs) * cs - cs / 2, bb[1] - cs, -cs)
        X, Y = np.meshgrid(xs, ys)
        Z = np.where(X > xc + 1000.0, z_mar, 100.0 + 0.01 * (X - xc) + 0.02 * (Y - yc))
        return Z.astype("float32"), from_origin(xs[0] - cs / 2, ys[0] + cs / 2, cs, cs), None
    return tramo, xc, yc


@pytest.mark.parametrize("max_pix, tolerancia", [(2000, 0.05), (100, 0.3)])
def test_mdt_recortado_y_reproyectado_frente_a_pyproj(monkeypatch, max_pix, tolerancia):
    # el plano vale lo mismo en cualquier huso: la cota de cada celda se calcula aparte, llevando su centro con pyproj al huso del servicio
    tramo, xc, yc = _servicio_mdt()
    monkeypatch.setattr(terreno, "_wcs_tramo", tramo)
    # con 100, varios tramos. ⚠️ Heredado, sin tocar: en la costura gana la celda del primer tramo aunque su ventana bilineal quede
    # incompleta. Medido con este plano del 2 %: 0,26 m en 96 de 19 023 celdas; las demás, ≤ 0,05 m
    monkeypatch.setattr(terreno, "WCS_MAXPIX", max_pix)
    tr, forma, ext = terreno.rejilla(LAT, LON, 4.0, 25.0)
    assert forma == (160, 160) and ext[0] % 25 == 0 and ext[2] % 25 == 0
    Z, cobertura = terreno.descargar_mdt(tr, forma, 25.0)
    assert cobertura == "Elevacion25830_25" and Z.dtype == np.float32 and np.isfinite(Z).all()
    cols, filas = np.meshgrid(np.arange(160), np.arange(160))
    x, y = Transformer.from_crs("EPSG:25831", terreno.WCS_CRS, always_xy=True).transform(tr.c + (cols + 0.5) * tr.a, tr.f + (filas + 0.5) * tr.e)
    tierra, mar = x < xc + 950.0, x > xc + 1050.0               # junto a la costa, el bilineal mezcla los dos
    assert tierra.sum() > 100 and mar.sum() > 100
    assert abs(Z - (100.0 + 0.01 * (x - xc) + 0.02 * (y - yc)))[tierra].max() < tolerancia
    assert (Z[mar] == 0.0).all()                                 # el mar sigue a 0, no sale como hueco


def test_mdt_negativos_a_cero_y_se_puede_cancelar(monkeypatch):
    tramo, _, _ = _servicio_mdt(z_mar=-2.0)
    monkeypatch.setattr(terreno, "_wcs_tramo", tramo)
    tr, forma, _ = terreno.rejilla(LAT, LON, 4.0)
    assert terreno.descargar_mdt(tr, forma, 100.0)[0].min() == 0.0
    with pytest.raises(Cancelado):
        terreno.descargar_mdt(tr, forma, 100.0, cancelado=lambda: True)


def test_rejilla_y_carpeta_con_la_resolucion_de_la_planta_salvo_que_se_pida_otra(tmp_path):
    assert terreno.caso_dir(LAT, LON, 4.0) == planta.PLANTA / "terreno" / "39.75000_1.25000_4km_100m"
    assert terreno.caso_dir(LAT, LON, 4.0, 50).name.endswith("4km_50m")
    assert terreno.rejilla(LAT, LON, 4.0, 50)[1] == (80, 80)


def test_mar_estadisticas_y_bandas_de_cota():
    Z = np.array([[0.0, 0.0, 120.0, 600.0, 0.0]], dtype="float32")
    U = np.array([[0, 523, 223, 312, 223]], dtype="uint16")      # el último: tierra a cota 0, con polígono: no es mar
    assert terreno.mascara_mar(Z, U).tolist() == [[True, True, False, False, False]]
    e = terreno.estadisticas(Z, U)
    assert e["pct_mar"] == 40.0 and e["z_max"] == 600.0 and e["z_min"] == 0.0
    bandas = {b["banda"]: round(b["pct"], 3) for b in terreno.cotas_por_bandas(Z, U)}
    assert bandas == {"< 50 m": 33.333, "50–200 m": 33.333, "200–500 m": 0.0, "500–1000 m": 33.333, "> 1000 m": 0.0}
    assert sum(g["pct"] for g in terreno.usos_por_grupo(Z, U)) == pytest.approx(100.0)


def test_nucleos_con_8_vecinos_y_sin_los_recortes_pequenos():
    tr = from_origin(0.0, 1000.0, 100.0, 100.0)
    U = np.zeros((10, 10), dtype="uint16")
    U[0:3, 0:3] = 112                                           # 9 ha
    U[3:5, 3:5] = 111                                           # 4 ha que tocan por la esquina: la misma mancha
    U[8, 8] = 121                                               # 1 ha: menos de NUCLEO_MIN_HA
    salen = terreno.nucleos(U, tr)
    assert [(n["familia"], n["ha"], n["codigos"]) for n in salen] == [("residencial", 13.0, [111, 112])]
    assert terreno.en_punto(np.zeros((10, 10)), U, tr, 80.0, 50.0) == (None, None)     # fuera del terreno


def test_nombres_de_nucleos_de_la_cache_y_sin_perder_los_que_ya_habia(monkeypatch, tmp_path):
    lista = [{"lat": 40.0, "lon": 0.0}, {"lat": 41.0, "lon": 1.0}, {"lat": 42.0, "lon": 2.0}]
    (tmp_path / terreno.NOMBRES_NUCLEOS).write_text(json.dumps({"40.00000,0.00000": {"poblacion": "Vieja", "municipio": "V"}}), encoding="utf-8")
    pedidas = _urlopen(monkeypatch, json.dumps({"poblacion": 'l"Aldea', "muni": "M"}).encode(), urllib.error.URLError("corte"))
    info = {"dir": str(tmp_path)}
    assert list(terreno.nombres_nucleos(info, lista)) == ["40.00000,0.00000"] and not pedidas     # sin descargar=True no sale a la red
    nombres = terreno.nombres_nucleos(info, lista, descargar=True)
    assert len(pedidas) == 2 and nombres["41.00000,1.00000"] == {"poblacion": "l'Aldea", "municipio": "M"}
    assert nombres["40.00000,0.00000"]["poblacion"] == "Vieja" and "42.00000,2.00000" not in nombres
    assert json.loads((tmp_path / terreno.NOMBRES_NUCLEOS).read_text(encoding="utf-8")) == nombres


@con_geopandas
def test_terreno_entero_sin_red(monkeypatch, tmp_path):
    import geopandas as gpd
    from shapely.geometry import box
    tramo, xc, yc = _servicio_mdt()
    monkeypatch.setattr(terreno, "_wcs_tramo", tramo)
    with pytest.raises(FileNotFoundError, match="PRUEBA_FUENTES_CORINE"):      # la variable lleva el prefijo de la planta
        terreno.leer_corine(*terreno.rejilla(LAT, LON, 4.0)[:2])
    # CORINE inventado, en el huso del servicio; un polígono enorme se recorta y el que no se ve no entra
    usos = gpd.GeoDataFrame({"CODE_18": ["223", "112", "311"]},
                            geometry=[box(xc - 5e4, yc - 5e4, xc - 400, yc + 5e4), box(xc - 400, yc - 400, xc + 400, yc + 400), box(xc + 2e5, yc, xc + 2e5 + 10, yc + 10)],
                            crs=terreno.WCS_CRS)
    gpkg = tmp_path / "corine_prueba.gpkg"
    usos.to_file(gpkg, layer=terreno.CORINE_CAPA, driver="GPKG")
    monkeypatch.setenv("PRUEBA_FUENTES_CORINE", str(gpkg))
    info = terreno.descargar(LAT, LON, 4.0)
    assert Path(info["dir"]) == terreno.caso_dir(LAT, LON, 4.0) and info["epsg"] == "EPSG:25831"
    for f in ("elevacion.tif", "usos.tif", "corine.gpkg", "info.json", "mapa_elevacion.png", "mapa_usos.png"):
        assert (Path(info["dir"]) / f).is_file(), f
    assert terreno.ultimo_caso(LAT, LON)["dir"] == info["dir"] and terreno.ultimo_caso(LAT + 1, LON) is None
    Z, U, tr = terreno.cargar(info)
    assert Z.shape == (40, 40) and set(np.unique(U)) == {0, 112, 223}
    assert info["corine"]["poligonos"] == 2 and info["planta"]["uso"] == 112
    res = terreno.resumen(Z, U, tr, LAT, LON)
    assert res["nucleos"][0]["familia"] == "residencial" and res["nucleos"][0]["dist_m"] < 200
    assert res["alrededor"]["uso"] == 112 and res["alrededor"]["radio_m"] == terreno.RADIO_ALREDEDOR_M     # la planta, en el cuadro de 112
    assert terreno.describir_punto(Z, U, tr, LAT, LON)[2] == terreno.CLC_NOMBRES[112]


def test_lo_que_rodea_la_planta():
    # usuario, 2026-11-16: en la ficha de la página Planta, «rodeado de olivares» en vez de los edificios a 2 km: el uso del suelo que más
    # hay a menos de 500 m (en La Galera, el 79 % es olivar; a 1 km, ya solo el 49 %)
    U = np.full((40, 40), 223)                                   # olivares, en celdas de 50 m: 2 × 2 km
    U[:, 25:] = 222                                              # frutales, a más de 250 m al este del centro
    tr = SimpleNamespace(a=50.0, e=-50.0, c=0.0, f=2000.0)
    al = terreno.alrededor(U, tr, 1000.0, 1000.0)
    assert (al["uso"], al["nombre"], al["radio_m"]) == (223, terreno.CLC_NOMBRES[223], 500.0)
    assert 75 < al["pct"] < 85                                   # el segmento de más allá de 250 m es ~20 % del círculo
    assert terreno.alrededor(U, tr, 1000.0, 1000.0, radio_m=100.0)["pct"] == 100.0
    assert terreno.alrededor(U, tr, 1700.0, 1000.0)["uso"] == 222                  # junto al borde este, más frutales
    assert terreno.alrededor(U, tr, 9000.0, 9000.0) is None                        # el círculo, fuera del terreno
    U[:] = terreno.NODATA_USO
    assert terreno.alrededor(U, tr, 1000.0, 1000.0)["nombre"] == "Mar abierto (fuera de CORINE)"


# ── Catastro ──
@pytest.mark.parametrize("codigo, uso", [("1_residential", "Residencial"), ("2_agriculture", "Agrario"), ("3_industrial", "Industrial"),
                                         ("4_1_office", "Oficinas"), ("4_2_retail", "Comercial"), ("4_3_publicServices", "Serv. públicos"),
                                         ("4_x", "Comercio/serv."), (None, "Otro")])
def test_usos_inspire(codigo, uso):
    assert catastro.uso_legible(codigo) == uso


def _capas_catastro():
    """Tres edificios a distintas distancias del centro de la planta y uno fuera, en el huso del servicio, y sus plantas."""
    import geopandas as gpd
    from shapely.geometry import box
    cx, cy = geo.a_utm(LAT, LON)
    cuadro = lambda dx, dy: box(cx + dx - 5, cy + dy - 5, cx + dx + 5, cy + dy + 5)
    bld = gpd.GeoDataFrame({"localId": ["A", "B", "C", "D"], "currentUse": ["1_residential", "3_industrial", "2_agriculture", "1_residential"]},
                           geometry=[cuadro(50, 0), cuadro(0, 120), cuadro(500, 0), cuadro(3000, 0)], crs="EPSG:25831").to_crs(catastro.WFS_CRS)
    partes = gpd.GeoDataFrame({"numberOfFloorsAboveGround": ["2", "5", "3", None]},
                              geometry=[cuadro(48, 0).buffer(-3), cuadro(52, 0).buffer(-3), cuadro(500, 0).buffer(-3), cuadro(0, 120).buffer(-3)],
                              crs="EPSG:25831").to_crs(catastro.WFS_CRS)
    return {"bu:Building": bld, "bu:BuildingPart": partes}


@con_geopandas
def test_catastro_altura_3_m_por_planta_y_radios_de_la_planta_activa(monkeypatch, tmp_path):
    capas = _capas_catastro()
    monkeypatch.setattr(catastro, "_capa", lambda capa, limites: capas[capa])
    info = catastro.descargar(LAT, LON)
    assert Path(info["dir"]) == catastro.dir_caso(LAT, LON) == planta.PLANTA / "edificios" / "39.75000_1.25000_r1km"
    _, bld = catastro.cargar(LAT, LON)
    # 1 km de radio, el de la planta: D, a 3 km, no entra. A coge el máximo de sus partes; B no tiene plantas conocidas
    assert bld["ref"].tolist() == ["A", "B", "C"] and bld["plantas"].tolist() == [5, 0, 3]
    assert bld["altura_m"].tolist() == [15.0, 0.0, 9.0] and "plantas × 3 m" in info["altura"]
    assert abs(bld["dist_m"][0] - 45.0) < 0.5 and bld["uso"].tolist() == ["Residencial", "Industrial", "Agrario"]
    assert info["n"] == 3 and info["altura_max_m"] == 15.0
    assert catastro.cercanos(bld)["ref"].tolist() == ["A", "B"]                 # 150 m, los de la planta para los focos
    assert catastro.cercanos(bld, 1000)["ref"].tolist() == ["A", "B", "C"]
    la, lo = geo.a_geo(*geo.a_utm(LAT, LON))
    assert catastro.en_punto(bld, la, lo) is None
    assert len(catastro.geojson_mapa(bld)["features"]) == 3
    assert catastro.cargar(LAT + 1, LON) == (None, None)


@con_geopandas
def test_catastro_divide_la_tesela_que_rechaza_por_limite(monkeypatch):
    import geopandas as gpd
    pedidas = []
    def http(url):
        pedidas.append(url)
        return b"<ows:ExceptionReport>exceeded the number of features</ows:ExceptionReport>" if len(pedidas) == 1 else b"<gml/>"
    monkeypatch.setattr(catastro, "_http", http)
    monkeypatch.setattr(gpd, "read_file", lambda f: pd.DataFrame({"a": [1]}))
    cuenta = {"fallos": 0, "saturadas": 0}
    assert len(catastro._bbox("bu:Building", 0.0, 0.0, 800.0, 800.0, cuenta)) == 4 and len(pedidas) == 5
    # la tesela mínima que sigue rechazando se cuenta: puede faltar algún edificio. Otro error no es «límite»
    monkeypatch.setattr(catastro, "_http", lambda url: b"<ExceptionReport>exceeded</ExceptionReport>")
    assert catastro._bbox("bu:Building", 0.0, 0.0, 150.0, 150.0, cuenta) == [] and cuenta["saturadas"] == 1
    monkeypatch.setattr(catastro, "_http", lambda url: b"<ExceptionReport>error interno</ExceptionReport>")
    assert catastro._bbox("bu:Building", 0.0, 0.0, 800.0, 800.0, cuenta) == [] and cuenta["saturadas"] == 1


def test_catastro_reintenta_tres_veces(monkeypatch):
    pedidas = _urlopen(monkeypatch, urllib.error.URLError("corte"), TimeoutError(), b"datos")
    assert catastro._http("https://servicio/inventado") == b"datos" and len(pedidas) == 3
    assert pedidas[0].get_header("User-agent") == "agente-general"
    _urlopen(monkeypatch, *[ConnectionError()] * 3)
    with pytest.raises(ConnectionError):
        catastro._http("https://servicio/inventado")


# ── Meteocat ──
def _meteocat_simulado(monkeypatch, lecturas, altura="46"):
    """_get simulado. `lecturas`: {mes: filas}; responde a la consulta del anemómetro y a la del mes, y guarda los $where."""
    wheres = []
    def get(url, params, intentos=4):
        where = params["$where"]
        wheres.append(where)
        if "count(" in params["$select"]:
            return [{"n": "7" if f"codi_variable='{altura}'" in where else "0"}]
        return lecturas.get(int(where.split("between '")[1][5:7]), []) if params["$offset"] == 0 else []
    monkeypatch.setattr(meteocat, "_get", get)
    return wheres


def _fila(hora, var, valor):
    return {"data_lectura": hora, "codi_variable": var, "valor_lectura": str(valor)}


def test_meteocat_pide_mes_a_mes_y_guarda_la_hora_tal_cual(monkeypatch, tmp_path):
    # hora UTC con la etiqueta de INICIO del intervalo: en julio, sin mover ni 2 h de verano ni los 30 min del intervalo
    filas = [_fila("2024-07-01T12:30:00.000", "46", 3.0), _fila("2024-07-01T12:30:00.000", "47", 90), _fila("2024-07-01T12:30:00.000", "32", 25),
             _fila("2024-07-01T13:00:00.000", "46", 5.0), _fila("2024-07-01T13:00:00.000", "47", 90)]
    wheres = _meteocat_simulado(monkeypatch, {7: filas})
    f = meteocat.anio_estacion("AB", 2024)
    assert f == tmp_path / "datos" / "meteo" / "meteocat" / "AB" / "2024.csv"
    meses = [w for w in wheres if "between" in w]
    assert len(meses) == 12 and "between '2024-02-01T00:00:00' and '2024-02-29T23:59:59'" in meses[1]       # bisiesto
    assert all("codi_estacio='AB'" in w and "'46','47'" in w.replace(",'46'", "'46'") or "'46'" in w for w in meses)
    df = pd.read_csv(f, parse_dates=["time"])
    assert df["time"].tolist() == [pd.Timestamp("2024-07-01 12:30"), pd.Timestamp("2024-07-01 13:00")]
    assert df["ws"].tolist() == [3.0, 5.0] and df["wd"].tolist() == [90.0, 90.0] and (df["altura_viento_m"] == 2).all()
    # el que promedia sabe que es de INICIO: las medidas de las 12:30 y las 13:00 rodean a las 13:00
    hor = medias_horarias(df, "inicio")
    assert hor["time"].tolist() == [pd.Timestamp("2024-07-01 13:00")] and hor["ws"].tolist() == [4.0] and abs(hor["wd"][0] - 90.0) < 1e-9
    n = len(wheres)
    assert meteocat.anio_estacion("AB", 2024) == f and len(wheres) == n             # en la caché no vuelve a consultar


def test_meteocat_pagina_hasta_que_una_pagina_no_esta_llena(monkeypatch):
    monkeypatch.setattr(meteocat, "PAGINA", 2)
    offsets = []
    def get(url, params, intentos=4):
        offsets.append(params["$offset"])
        return [{"i": i} for i in range(params["$offset"], min(params["$offset"] + 2, 5))]
    monkeypatch.setattr(meteocat, "_get", get)
    assert len(meteocat._lecturas("AB", "d", "h", ["32"])) == 5 and offsets == [0, 2, 4]


def test_meteocat_sumar_dias_no_pierde_lo_que_ya_habia(monkeypatch):
    # se perdió una vez: en DATOS está el año entero y un día nuevo no puede pisarlo. Lo nuevo manda donde se solapa
    base = meteocat.dir_meteocat() / "AB"
    base.mkdir(parents=True)
    viejo = pd.DataFrame({"time": ["2023-01-05 00:00:00", "2023-12-31 23:00:00"], "ws": [1.0, 2.0], "wd": [10.0, 20.0], "t": [5.0, 6.0], "rh": [50.0, 51.0],
                          "p": [1000.0, 1001.0], "pr": [0.0, 0.0], "rad": [0.0, 0.0], "altura_viento_m": [10, 10]})
    viejo.to_csv(base / "2023.csv", index=False)
    monkeypatch.setattr(meteocat, "altura_viento", lambda c: 10)
    nuevas = [_fila("2023-12-31T23:00:00.000", "30", 9.0), _fila("2023-12-31T23:30:00.000", "30", 8.0), _fila("2024-01-01T00:00:00.000", "30", 7.0)]
    monkeypatch.setattr(meteocat, "_lecturas", lambda *a: nuevas)
    alturas = meteocat.estaciones_dias([{"codigo": "AB", "nombre": "Inventada"}], pd.Timestamp("2023-12-31 23:00"), pd.Timestamp("2024-01-01 00:00"))
    assert alturas == {"AB": 10.0}
    a = pd.read_csv(base / "2023.csv", parse_dates=["time"])
    assert a["time"].dt.strftime("%m-%d %H:%M").tolist() == ["01-05 00:00", "12-31 23:00", "12-31 23:30"] and a["ws"].tolist() == [1.0, 9.0, 8.0]
    b = pd.read_csv(base / "2024.csv", parse_dates=["time"])
    assert b["ws"].tolist() == [7.0]


def _inventario():
    cerca = [("A", LAT + 0.1, "2"), ("B", LAT + 0.2, "2"), ("C", LAT + 0.5, "2"), ("D", LAT + 0.05, "1")]
    filas = [{"codi_estacio": c, "nom_estacio": c, "latitud": str(la), "longitud": str(LON), "altitud": "10", "codi_estat_ema": e} for c, la, e in cerca]
    f = meteocat.dir_meteocat() / "estaciones.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps(filas + [{"codi_estacio": "sin coordenadas"}]), encoding="utf-8")


def test_meteocat_cercanas_con_el_radio_de_la_planta_y_sin_red():
    assert meteocat.para_mapa(LAT, LON) == []                    # sin inventario: la aplicación arranca igual, sin conexión
    _inventario()
    # 30 km, el de la planta: A (≈ 11 km) y B (≈ 22 km); C está lejos y D no está operativa
    assert [e["codigo"] for e in meteocat.cercanas(LAT, LON)] == ["A", "B"]
    assert [e["codigo"] for e in meteocat.cercanas(LAT, LON, radio_km=15.0)] == ["A"]
    assert [e["codigo"] for e in meteocat.cercanas(LAT, LON, 15.0, solo_operativas=False)] == ["D", "A"]
    assert [e["codigo"] for e in meteocat.para_mapa(LAT, LON)] == ["A", "B"]


def test_meteocat_sin_bloque_estaciones_el_error_dice_cual(tmp_path):
    j = json.loads(json.dumps(JSON_PLANTA))
    del j["estaciones"]
    (tmp_path / "planta" / "planta.json").write_text(json.dumps(j), encoding="utf-8")
    planta.activar(tmp_path / "planta")
    _inventario()
    with pytest.raises(ValueError, match=r"estaciones\.radio_km"):
        meteocat.cercanas(LAT, LON)


def test_meteocat_el_anemometro_se_busca_desde_el_primer_anio_de_la_planta(monkeypatch):
    wheres = _meteocat_simulado(monkeypatch, {}, altura="48")
    assert meteocat.altura_viento("AB") == 6                     # 10, 6 y 2 m, en ese orden
    assert all("data_lectura > '2022-01-01T00:00:00'" in w for w in wheres) and len(wheres) == 2


def test_meteocat_anios_de_la_planta_y_sigue_si_uno_falla(monkeypatch):
    monkeypatch.setattr(meteocat, "cercanas", lambda lat, lon, radio: [{"codigo": "AB", "nombre": "Inventada", "dist_m": 1000.0, "radio": radio}])
    pedidos = []
    def anio(codigo, a):
        pedidos.append(a)
        if a == 2022:
            raise RuntimeError("sin red")
    monkeypatch.setattr(meteocat, "anio_estacion", anio)
    assert meteocat.descargar(LAT, LON)[0]["radio"] == 30.0 and pedidos == [2022, 2023]
    base = meteocat.dir_meteocat() / "AB"
    base.mkdir(parents=True)
    for a in (2021, 2022):
        (base / f"{a}.csv").write_text(f"time,ws\n{a}-01-01 00:00:00,1.0\n", encoding="utf-8")
    assert meteocat.cargar("AB")["time"].dt.year.tolist() == [2022]
    assert meteocat.cargar("XX").empty


def test_meteocat_reintenta_con_su_agente(monkeypatch):
    pedidas = _urlopen(monkeypatch, urllib.error.URLError("corte"), json.dumps([{"a": 1}]).encode())
    assert meteocat._get("https://servicio/inventado", {"$limit": 5}) == [{"a": 1}] and len(pedidas) == 2
    assert pedidas[0].get_header("User-agent") == "agente-estaciones" and "%24limit=5" not in pedidas[0].full_url
    _urlopen(monkeypatch, *[TimeoutError()] * 4)
    with pytest.raises(RuntimeError, match="Meteocat no responde"):
        meteocat._get("https://servicio/inventado", {})


def test_a_10m_ley_logaritmica():
    # u(10) / u(2) = ln(10 / z0) / ln(2 / z0), con z0 = 0,1 m: ln(100) / ln(20) = 1,5372
    assert meteocat.a_10m(1.0, 2) == pytest.approx(1.5372, abs=1e-4)
    assert meteocat.a_10m(3.0, 10) == 3.0 and meteocat.a_10m(3.0, None) == 3.0


# ── ERA5: la cola del CDS ──
class _Remota:
    def __init__(self, estado):
        self.status = estado

    def download(self, destino):
        Path(destino).write_bytes(b"netcdf")

    def get_results(self):
        raise RuntimeError(f"motivo: {self.status}")


class _CDS:
    """El CDS inventado. `guion`: lo que responde cada consulta de estado: un estado o una excepción. Guarda envíos y consultas."""
    def __init__(self, *guion):
        self.guion, self.enviadas, self.consultadas = list(guion), [], []

    def submit(self, dataset, peticion):
        self.enviadas.append(f"peticion-{len(self.enviadas) + 1}")
        return SimpleNamespace(request_id=self.enviadas[-1])

    def get_remote(self, rid):
        self.consultadas.append(rid)
        r = self.guion.pop(0)
        if isinstance(r, Exception):
            raise r
        return _Remota(r)


def _http_error(codigo, texto=""):
    import requests
    return requests.exceptions.HTTPError(texto or f"{codigo}", response=SimpleNamespace(status_code=codigo))


def _pide(monkeypatch, cds):
    monkeypatch.setattr(era5, "_cliente", lambda: cds)
    monkeypatch.setattr(era5, "_INDICE_CDS", {})
    ruta = Path(era5._pedir("dataset", {"a": 1}, "prueba"))
    try:
        assert ruta.read_bytes() == b"netcdf"
    finally:
        ruta.unlink()


@con_requests
def test_es_de_red():
    import requests
    # un 4xx no es de red aunque `requests.HTTPError` herede de OSError: un 404 hizo esperar 48 h a una petición perdida
    for codigo in (400, 403, 404, 410):
        assert not era5._es_de_red(_http_error(codigo)), codigo
    for codigo in (429, 500, 502, 503):
        assert era5._es_de_red(_http_error(codigo)), codigo
    assert issubclass(requests.exceptions.HTTPError, OSError)
    assert era5._es_de_red(requests.exceptions.HTTPError("sin respuesta"))
    for e in (requests.exceptions.ConnectionError(), requests.exceptions.Timeout(), ConnectionError(), TimeoutError(), OSError()):
        assert era5._es_de_red(e), repr(e)
    assert not era5._es_de_red(ValueError())


@con_requests
def test_un_5xx_429_o_corte_de_red_espera_la_misma_peticion(monkeypatch):
    import requests
    cds = _CDS(_http_error(503), requests.exceptions.ConnectionError("dns"), _http_error(429), "running", "successful")
    _pide(monkeypatch, cds)
    assert cds.enviadas == ["peticion-1"] and set(cds.consultadas) == {"peticion-1"} and len(cds.consultadas) == 5


@con_requests
@pytest.mark.parametrize("error", [404, 400])
def test_un_4xx_reenvia_la_peticion(monkeypatch, error):
    cds = _CDS(_http_error(error), "successful")
    _pide(monkeypatch, cds)
    assert cds.enviadas == ["peticion-1", "peticion-2"] and cds.consultadas == ["peticion-1", "peticion-2"]


@con_requests
def test_una_peticion_fallida_se_reenvia_y_la_licencia_no(monkeypatch):
    cds = _CDS("failed", "successful")
    _pide(monkeypatch, cds)
    assert cds.enviadas == ["peticion-1", "peticion-2"]
    cds = _CDS(_http_error(403, "required licences not accepted"))
    with pytest.raises(era5.SinLicencia):
        _pide(monkeypatch, cds)
    assert cds.enviadas == ["peticion-1"]
    cds = _CDS(_http_error(400, "cost limit exceeded"))
    with pytest.raises(era5.DemasiadoGrande):
        _pide(monkeypatch, cds)
    assert cds.enviadas == ["peticion-1"]


@con_requests
def test_se_retoma_la_peticion_que_ya_estaba_en_la_cola(monkeypatch):
    cds = _CDS("successful")
    monkeypatch.setattr(era5, "_cliente", lambda: cds)
    monkeypatch.setattr(era5, "_INDICE_CDS", {era5._clave("dataset", {"a": 1}): ("de-antes", "running")})
    Path(era5._pedir("dataset", {"a": 1, "data_format": "netcdf"}, "prueba")).unlink()     # el formato no distingue dos peticiones
    assert cds.enviadas == [] and cds.consultadas == ["de-antes"] and not era5._INDICE_CDS


def test_unidades_de_era5():
    df = era5._convertir_sfc(pd.DataFrame({"t2m": [273.15], "d2m": [283.15], "sp": [101325.0], "tp": [0.002], "ssrd": [3.6e6], "sshf": [-7.2e5], "u10": [0.0], "v10": [-5.0]}))
    assert df["t2m"][0] == 0.0 and df["d2m"][0] == 10.0 and df["sp"][0] == 1013.25 and df["tp"][0] == 2.0
    assert df["ssrd"][0] == 1000.0 and df["sshf"][0] == -200.0                  # J/m² acumulados en la hora
    assert df["wspd"][0] == 5.0 and df["wdir"][0] == 0.0                        # v < 0: viene del norte


def test_era5_anios_de_la_planta(monkeypatch, tmp_path):
    assert era5.dir_era5(LAT, LON) == tmp_path / "datos" / "meteo" / "era5" / "39.750_1.250"
    monkeypatch.setattr(era5, "punto_era5", lambda la, lo: {"lat": la, "lon": lo, "lsm": 1.0, "cota_modelo_m": 1.0, "dist_planta_m": 1.0, "rumbo_desde_planta": "N"})
    monkeypatch.setattr(era5, "indexar_cds", lambda: 0)
    monkeypatch.setattr(era5, "serie_sfc", lambda la, lo, anios: pd.DataFrame({"anios": list(anios)}))
    hechas = []
    monkeypatch.setattr(era5, "anio_zust", lambda la, lo, a: hechas.append(("zust", a)))
    monkeypatch.setattr(era5, "construir_sfc_anio", lambda la, lo, a, serie: None)
    monkeypatch.setattr(era5, "quincena_pfl", lambda la, lo, a, m, q: hechas.append(("pfl", a)))
    r = era5.descargar_reanalisis(LAT, LON, hilos=1)
    assert r == {"hechos": 50, "total": 50, "fallidos": []}                     # 2 años: 2 de u* y 48 quincenas de perfil
    assert {a for _, a in hechas} == {2022, 2023}
    d = era5.dir_era5(LAT, LON)
    d.mkdir(parents=True)
    for a in (2021, 2022):
        (d / f"sfc_{a}01.csv").write_text(f"time,t2m\n{a}-01-01 00:00:00,1.0\n", encoding="utf-8")
        (d / f"pfl_{a}01_1.csv").write_text(f"time,level\n{a}-01-01 00:00:00,975\n", encoding="utf-8")
    assert era5.cargar_sfc(LAT, LON)["time"].dt.year.tolist() == [2022] and era5.cargar_pfl(LAT, LON)["time"].dt.year.tolist() == [2022]
    assert era5.cargar_sfc(LAT, LON, [2021])["time"].dt.year.tolist() == [2021]


# ── GFS ──
def test_caja_en_la_malla_de_gfs_tambien_al_oeste_de_greenwich():
    # la malla va de 90 a −90 y de 0 a 360, cada 0,25°
    J, I = gfs_noaa.indices_caja({"lat": [40.25, 41.25], "lon": [0.0, 1.0]})
    assert J == slice(195, 200) and I.tolist() == [0, 1, 2, 3, 4]
    assert gfs_noaa.indices_caja({"lat": [40.0, 40.5], "lon": [-2.0, -1.0]})[1].tolist() == [1432, 1433, 1434, 1435, 1436]
    J, I = gfs_noaa.indices_caja()                              # la de la planta, que cruza el meridiano 0
    assert J == slice(158, 161) and I.tolist() == [1438, 1439, 0, 1, 2]


def test_plazo_pide_por_rangos_y_recorta_la_caja(monkeypatch):
    malla = (1000.0 * np.arange(721))[:, None] + np.arange(1440)
    idx = ["1:0:d=2024010100:PRES:surface:anl:", "2:100:d=2024010100:HGT:1000 mb:anl:", "3:200:d=2024010100:ABSV:500 mb:anl:",
           "4:300:d=2024010100:UGRD:850 mb:anl:", "5:400:d=2024010100:ABSV:700 mb:anl:"]
    pedidos = []
    def get(url, rango=None, reintentos=6):
        pedidos.append(rango)
        return "\n".join(idx).encode() if rango is None else bytes((i // 100 + 1) for i in range(rango[0], rango[1] + 1))
    monkeypatch.setattr(gfs_noaa, "_get", get)
    monkeypatch.setitem(sys.modules, "pygrib", SimpleNamespace(fromstring=lambda b: SimpleNamespace(values=malla + 1e6 * b[0])))
    salen = gfs_noaa.plazo(pd.Timestamp("2024-01-01"), 3)
    assert set(salen) == {"surface_pressure", "geopotential_height_1000hPa", "wind_u_850hPa"}
    assert pedidos == [None, (0, 399)]                           # todos los mensajes en un solo rango: están a menos de HUECO
    assert salen["surface_pressure"].dtype == np.float32 and salen["surface_pressure"].shape == (3, 5)
    assert salen["wind_u_850hPa"][0, 0] == 4e6 + 158000 + 1438 and salen["wind_u_850hPa"][2, 2] == 4e6 + 160000


def test_mensajes_del_mos_solo_con_extra_y_de_la_nubosidad_la_media():
    """Con `extra` (la predicción), además el viento a 100 m y la MEDIA de la nubosidad y de la onda corta, que es lo que guarda el archivo con el que se entrenó el MOS. La nubosidad del
    viento 3D sigue siendo la primera que sale, con o sin `extra`."""
    idx = ["1:0:d=2025121500:PRMSL:mean sea level:3 hour fcst:", "2:100:d=2025121500:TCDC:entire atmosphere:3 hour fcst:",
           "3:200:d=2025121500:TCDC:entire atmosphere:0-3 hour ave fcst:", "4:300:d=2025121500:DSWRF:surface:0-3 hour ave fcst:",
           "5:400:d=2025121500:UGRD:100 m above ground:3 hour fcst:", "6:500:d=2025121500:VGRD:100 m above ground:3 hour fcst:",
           "7:600:d=2025121500:UGRD:850 mb:3 hour fcst:", "8:700:d=2025121500:ABSV:500 mb:3 hour fcst:"]
    siempre = {"pressure_msl": (0, 99), "cloud_cover": (100, 199), "wind_u_850hPa": (600, 699)}
    assert gfs_noaa.mensajes(idx) == siempre
    assert gfs_noaa.mensajes(idx, extra=True) == {**siempre, "total_cloud_cover_atmosphere": (200, 299), "downward_short_wave_radiation_flux_surface": (300, 399),
                                                  "wind_u_100m": (400, 499), "wind_v_100m": (500, 599)}
    # si la media sale antes que la instantánea, la del viento 3D es la primera (como siempre) y la del MOS, la media
    otro = ["1:0:d=2025121500:PRMSL:mean sea level:3 hour fcst:", "2:100:d=2025121500:TCDC:entire atmosphere:0-3 hour ave fcst:",
            "3:200:d=2025121500:TCDC:entire atmosphere:3 hour fcst:", "4:300:d=2025121500:ABSV:500 mb:3 hour fcst:"]
    r = gfs_noaa.mensajes(otro, extra=True)
    assert r["cloud_cover"] == (100, 199) and r["total_cloud_cover_atmosphere"] == (100, 199) and "downward_short_wave_radiation_flux_surface" not in r


def test_plazo_con_extra_trae_lo_del_mos(monkeypatch):
    malla = np.zeros((721, 1440))
    idx = ["1:0:d=2024010100:TCDC:entire atmosphere:3 hour fcst:", "2:100:d=2024010100:TCDC:entire atmosphere:0-3 hour ave fcst:",
           "3:200:d=2024010100:UGRD:100 m above ground:3 hour fcst:", "4:300:d=2024010100:ABSV:700 mb:3 hour fcst:"]
    monkeypatch.setattr(gfs_noaa, "_get", lambda url, rango=None, reintentos=6: "\n".join(idx).encode() if rango is None else bytes((i // 100 + 1) for i in range(rango[0], rango[1] + 1)))
    monkeypatch.setitem(sys.modules, "pygrib", SimpleNamespace(fromstring=lambda b: SimpleNamespace(values=malla + b[0])))
    assert set(gfs_noaa.plazo(pd.Timestamp("2024-01-01"), 3)) == {"cloud_cover"}
    salen = gfs_noaa.plazo(pd.Timestamp("2024-01-01"), 3, extra=True)
    assert set(salen) == {"cloud_cover", "total_cloud_cover_atmosphere", "wind_u_100m"}
    assert salen["cloud_cover"][0, 0] == 1.0 and salen["total_cloud_cover_atmosphere"][0, 0] == 2.0 and salen["wind_u_100m"][0, 0] == 3.0


def test_get_de_noaa_reintenta_y_pide_el_rango(monkeypatch):
    pedidas = _urlopen(monkeypatch, urllib.error.URLError("corte"), b"datos")
    assert gfs_noaa._get("https://servicio/inventado", (10, 20)) == b"datos" and len(pedidas) == 2
    assert pedidas[0].get_header("Range") == "bytes=10-20"
    _urlopen(monkeypatch, *[TimeoutError()] * 2)
    with pytest.raises(TimeoutError):
        gfs_noaa._get("https://servicio/inventado", reintentos=2)


@con_xarray
def test_ejecucion_con_las_coordenadas_de_la_caja_y_las_unidades(monkeypatch):
    def plazo(dia, p):
        campo = np.full((3, 5), 300.0, np.float32)
        return {"temperature_2m": campo, "surface_pressure": campo * 100, **({"cloud_cover": campo} if p else {})}
    monkeypatch.setattr(gfs_noaa, "plazo", plazo)
    ds = gfs_noaa.ejecucion(pd.Timestamp("2024-01-01"), 1, [0, 3])
    assert ds.latitude.values.tolist() == [50.5, 50.25, 50.0] and ds.longitude.values.tolist() == [-0.5, -0.25, 0.0, 0.25, 0.5]
    assert float(ds.temperature_2m[0, 0, 0]) == pytest.approx(26.85) and float(ds.surface_pressure[0, 0, 0]) == pytest.approx(300.0)
    assert np.isnan(ds.cloud_cover[0]).all() and not np.isnan(ds.cloud_cover[1]).any()     # lo que falta en un plazo, con el tamaño de la caja


@con_xarray
def test_ejecucion_con_extra_lo_pide_en_cada_plazo(monkeypatch):
    pedidos = []
    def plazo(dia, p, extra=False):
        pedidos.append((p, extra))
        campo = np.full((3, 5), 1.0, np.float32)
        return {"pressure_msl": campo * 101300.0, **({"wind_u_100m": campo} if extra else {})}
    monkeypatch.setattr(gfs_noaa, "plazo", plazo)
    ds = gfs_noaa.ejecucion(pd.Timestamp("2024-01-01"), 1, [0, 3], extra=True)
    assert sorted(pedidos) == [(0, True), (3, True)] and float(ds.wind_u_100m[1, 0, 0]) == 1.0 and float(ds.pressure_msl[0, 0, 0]) == pytest.approx(1013.0)


def test_gfs_noaa_semanas_de_la_planta_salvo_que_se_pidan_otras(monkeypatch, tmp_path):
    hechas = []
    def ejecucion(d, hilos):
        hechas.append(d)
        return SimpleNamespace(data_vars=[1], to_netcdf=lambda f: Path(f).write_bytes(b"nc"))
    monkeypatch.setattr(gfs_noaa, "ejecucion", ejecucion)
    monkeypatch.setattr(sys, "argv", ["x"])
    gfs_noaa.main()
    assert hechas[0] == pd.Timestamp("2023-03-04") and len(hechas) == 9                      # 2 días antes y la semana
    assert len(list((tmp_path / "datos" / "meteo" / "gfs_niveles").glob("gfs00_*.nc"))) == 9
    hechas.clear()
    gfs_noaa.main()
    assert not hechas                                           # reanudable
    monkeypatch.setattr(sys, "argv", ["x", "--semanas", "2020-06-08", "--paralelo", "1"])
    gfs_noaa.main()
    assert hechas[0] == pd.Timestamp("2020-06-06")


@con_xarray
def test_gfs_dynamical_guarda_la_caja_de_la_planta(monkeypatch, tmp_path):
    import xarray as xr
    lat, lon = np.arange(51.0, 49.5, -0.25), np.arange(-1.0, 1.25, 0.25)
    inits = pd.to_datetime(["2023-01-01 00:00", "2023-01-01 06:00", "2023-01-02 00:00", "2023-02-01 00:00"])
    plazos = np.array([0, 1, 200], dtype="timedelta64[h]")
    forma = (len(inits), len(plazos), len(lat), len(lon))
    g = {v: np.arange(np.prod(forma), dtype=float).reshape(forma) for v in gfs_dynamical.VARIABLES}
    ds = SimpleNamespace(latitude=SimpleNamespace(values=lat), longitude=SimpleNamespace(values=lon), lead_time=SimpleNamespace(values=plazos.astype("timedelta64[ns]")), init_time=SimpleNamespace(values=inits.values))
    monkeypatch.setattr(gfs_dynamical, "abrir", lambda: (ds, g, "s3://inventado"))
    monkeypatch.setattr(sys, "argv", ["x", "--desde", "2023-01", "--hasta", "2023-01", "--hilos", "1"])
    gfs_dynamical.main()
    d = tmp_path / "datos" / "meteo" / "gfs"
    assert json.loads((d / "origen.json").read_text(encoding="utf-8"))["caja"] == JSON_PLANTA["pronostico"]["caja_gfs"]
    with xr.open_dataset(d / "gfs00_202301.nc") as sal:
        assert sal.latitude.values.tolist() == [50.5, 50.25, 50.0] and sal.longitude.values.tolist() == [-0.5, -0.25, 0.0, 0.25, 0.5]
        assert len(sal.init_time) == 2 and sal.lead_time_h.values.tolist() == [0, 1]     # solo el ciclo de las 00 y hasta 120 h
        assert float(sal.wind_u_10m[1, 1, 0, 0]) == g["wind_u_10m"][2, 1, 2, 2]


# ── LiDAR ──
class _Laz:
    """Un .laz inventado, en dos trozos."""
    def __init__(self, trozos):
        self.trozos = trozos
        self.header = SimpleNamespace(point_count=sum(len(t) for t in trozos), parse_crs=lambda: None)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def chunk_iterator(self, n):
        for t in self.trozos:
            a = np.array(t, dtype=float)
            yield SimpleNamespace(x=a[:, 0], y=a[:, 1], z=a[:, 2], classification=a[:, 3].astype(int))


def test_lidar_rejillas_con_las_clases_de_asprs(monkeypatch, tmp_path):
    (tmp_path / "a.laz").write_bytes(b"")
    trozos = [[(1003.5, 2007.5, 5.0, 2), (1003.5, 2007.5, 12.0, 6), (1003.6, 2007.4, 14.0, 5)],     # 2 suelo, 6 edificio, 5 vegetación
              [(1003.5, 2007.5, 99.0, 7), (1003.5, 2007.5, 98.0, 18), (1003.5, 2007.5, 6.0, 2),       # 7 y 18: ruido
               (999.0, 2007.5, 50.0, 6), (1020.5, 2007.5, 50.0, 6)]]                                  # fuera del cuadrado
    monkeypatch.setitem(sys.modules, "laspy", SimpleNamespace(open=lambda f: _Laz(trozos)))
    salida = tmp_path / "r.npz"
    lidar.rejillas(tmp_path, salida, 1010.0, 2010.0, 10.0)
    r = np.load(salida)
    assert r["dsm"].shape == (20, 20) and r["x0"] == 1000.0 and r["y0"] == 2000.0
    # fila de la y, columna de la x
    assert r["dsm"][7, 3] == 14.0 and r["dsm_edif"][7, 3] == 12.0 and r["dtm"][7, 3] == 5.0
    assert r["total"][7, 3] == 4 and r["suelo"][7, 3] == 2 and r["edificio"][7, 3] == 1 and r["vegetacion"][7, 3] == 1
    assert r["dsm"][0, 0] == -np.inf and r["dtm"][0, 0] == np.inf and r["total"].sum() == 4


def test_lidar_la_zona_no_tiene_valor_por_defecto(monkeypatch, tmp_path):
    (tmp_path / "a.laz").write_bytes(b"")
    monkeypatch.setitem(sys.modules, "laspy", SimpleNamespace(open=lambda f: _Laz([[(10.5, 10.5, 1.0, 2)]])))
    monkeypatch.setattr(sys, "path", list(sys.path))
    base = [str(tmp_path), "libs", str(tmp_path / "r.npz")]
    with pytest.raises(SystemExit):
        lidar.main(base)
    lidar.main(base, zona=(10.0, 10.0, 5.0))
    assert np.load(tmp_path / "r.npz")["x0"] == 5.0
    lidar.main(base + ["20", "20", "12"], zona=(10.0, 10.0, 5.0))        # la línea de órdenes manda
    assert np.load(tmp_path / "r.npz")["x0"] == 8.0 and sys.path[0] == "libs"


def test_lidar_corre_con_python_aislado_y_no_importa_el_proyecto(tmp_path):
    # los .laz son datos descargados: «python -I» desde otra carpeta, sin nada del proyecto en el camino
    arriba = [n for n in ast.parse((FUENTES / "lidar.py").read_text(encoding="utf-8")).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    nombres = [a.name for n in arriba if isinstance(n, ast.Import) for a in n.names] + [n.module for n in arriba if isinstance(n, ast.ImportFrom)]
    assert all(x.split(".")[0] in sys.stdlib_module_names for x in nombres), nombres
    r = subprocess.run([sys.executable, "-I", str(FUENTES / "lidar.py"), "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tmp_path)
    assert r.returncode == 0 and "semilado" in r.stdout, r.stderr


# ── lo que no puede pasar al importar ──
def _nombres_leidos(nodos):
    return {n.id for nodo in nodos for n in ast.walk(nodo) if isinstance(n, ast.Name)}


@pytest.mark.parametrize("fichero", sorted(f.name for f in FUENTES.glob("*.py")))
def test_nada_lee_la_planta_al_importar_ni_en_un_valor_por_defecto(fichero):
    arbol = ast.parse((FUENTES / fichero).read_text(encoding="utf-8"))
    fuera = [n for n in arbol.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))]
    # el `if __name__ == "__main__"` no cuenta: al importar no corre
    fuera = [n for n in fuera if not (isinstance(n, ast.If) and "__name__" in _nombres_leidos([n.test]))]
    assert not _nombres_leidos(fuera) & {"config", "planta", "geo"}
    defectos = [d for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) for d in n.args.defaults + [k for k in n.args.kw_defaults if k]]
    assert not _nombres_leidos(defectos) & {"config", "planta", "geo"}


OPCIONALES = ("geopandas", "pyogrio", "shapely", "requests", "ecmwf", "xarray", "netCDF4", "pygrib", "laspy", "icechunk", "zarr", "PIL", "matplotlib", "scipy", "rasterio", "numba")


def _en_proceso_aparte(codigo, tmp_path):
    env = procesos.entorno()
    env.pop(planta.ENV_PLANTA, None)
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_al_importar_no_hay_planta_activa_ni_se_carga_lo_opcional(tmp_path):
    salida = _en_proceso_aparte("import importlib, pkgutil, sys\nimport teodors.fuentes as f\nfrom teodors import planta\n"
                                "for m in pkgutil.iter_modules(f.__path__, 'teodors.fuentes.'):\n    importlib.import_module(m.name)\n"
                                f"print(planta._activa, sorted(set({OPCIONALES!r}) & set(sys.modules)))", tmp_path)
    assert salida == "None []"


def test_el_python_aislado_no_necesita_mas_que_numpy_y_pandas(tmp_path):
    # el archivo de GFS corre en un Python ≥ 3.12 con icechunk, sin el resto de lo que usa teOdors
    assert _en_proceso_aparte("import sys\nfrom teodors import planta\nprint('numpy' in sys.modules)", tmp_path) == "False"
    salida = _en_proceso_aparte(f"import sys\nimport teodors.fuentes.gfs_dynamical\nprint(sorted(set({OPCIONALES!r}) & set(sys.modules)))", tmp_path)
    assert salida == "[]"


@pytest.mark.parametrize("modulo", [descargar_era5, descargar_meteocat, gfs_noaa, gfs_dynamical])
def test_las_descargas_responden_a_ayuda_sin_planta_y_sin_red(monkeypatch, modulo):
    planta.desactivar()
    monkeypatch.setattr(sys, "argv", ["x", "--help"])
    with pytest.raises(SystemExit) as e:
        modulo.main()
    assert e.value.code == 0


def test_descargar_era5_y_meteocat_con_el_registro_de_la_planta(monkeypatch, tmp_path):
    carpetas = []
    monkeypatch.setattr(registro, "configurar", lambda carpeta, prefijo: carpetas.append((carpeta, prefijo)) or logging.getLogger("prueba"))
    monkeypatch.setattr(sys, "argv", ["x"])
    pedidos = []
    monkeypatch.setattr(era5, "descargar_reanalisis", lambda la, lo: pedidos.append((la, lo)) or {"fallidos": []})
    assert descargar_era5.main() == 0 and pedidos == [(LAT, LON)]
    def sin_licencia(la, lo):
        raise era5.SinLicencia("no")
    monkeypatch.setattr(era5, "descargar_reanalisis", sin_licencia)
    assert descargar_era5.main() == 2
    monkeypatch.setattr(meteocat, "descargar", lambda la, lo: [1, 2])
    assert descargar_meteocat.main() == 0
    assert set(carpetas) == {(tmp_path / "local" / "logs", "prueba")} and (tmp_path / "local" / "logs").is_dir()


# ── la ortofoto del plano de focos ──
def test_la_ortofoto_de_los_focos_cose_las_teselas_y_las_lleva_a_utm(monkeypatch, tmp_path):
    # usuario, 2026-11-08: «que en el mapa de los focos del panel se vea la imagen satélite y encima los focos». Teselas inventadas, de un
    # color por tesela (rojo = x, verde = y): en el centro de una tesela, la imagen guardada tiene que tener el suyo
    from PIL import Image
    from teodors.fuentes import ortofoto as O
    with pytest.raises(ValueError, match="fondos"):
        O.descargar((0, 0, 100, 100))                                       # la planta de prueba no tiene fondos
    datos = json.loads(json.dumps(JSON_PLANTA))
    datos["fuentes"] = {"fondos": [["Satélite X", "https://teselas.x/{z}/{x}/{y}.jpg", "© <a href='x'>Fondo X</a> · CC BY", 18],
                                   ["Otro", "https://otro.x/{z}/{x}/{y}.png", "", 19]]}
    (planta.PLANTA / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
    planta.activar(planta.PLANTA)
    pedidas = []

    def tesela(url, z, x, y):
        pedidas.append((url, z, x, y))
        b = io.BytesIO()
        Image.new("RGB", (256, 256), (x % 256, y % 256, 90)).save(b, "PNG")
        return b.getvalue()

    monkeypatch.setattr(O, "_tesela", tesela)
    x, y = geo.a_utm(LAT, LON)
    cat = {"focos": [{"id": "A", "ubicacion": {"x": x, "y": y}},
                     {"id": "B", "ubicacion": {"poligono": [[x + 30, y], [x + 60, y], [x + 60, y + 20]]}}]}
    rec, nucleo = O.recuadros(cat)
    assert nucleo == pytest.approx((x - 18, y - 18, x + 78, y + 38))
    assert rec[2] - rec[0] == rec[3] - rec[1] == 2 * 90 and all(v % 10 == 0 for v in rec)       # 96 m · 1,7 / 2 → 90 m a cada lado
    assert rec[0] <= nucleo[0] and rec[2] >= nucleo[2] and O.recuadros({"focos": [{"id": "C", "ubicacion": {}}]}) is None
    info = O.para_focos(cat)
    # el primer fondo, a su zoom máximo; el crédito, sin HTML; con la planta, en su carpeta terreno/
    assert {u for u, *_ in pedidas} == {"https://teselas.x/{z}/{x}/{y}.jpg"} and {z for _, z, _, _ in pedidas} == {18}
    assert info["credito"] == "© Fondo X · CC BY" and info["teselas"] == len(pedidas) and info["fallos"] == 0
    assert Path(info["ruta"]) == planta.DIR_TERRENO / "ortofoto_focos.jpg" and info["epsg"] == planta.EPSG_UTM
    img = Image.open(info["ruta"])
    assert img.size == (720, 720)                                               # 180 m a 0,25 m
    # el centro de la tesela en la que cae la planta, en su sitio de la imagen (en UTM, con la convergencia de meridianos)
    n = 256 * 2 ** 18
    px = (LON + 180) / 360 * n
    py = (1 - np.arcsinh(np.tan(np.radians(LAT))) / np.pi) / 2 * n
    tx, ty = int(px // 256), int(py // 256)
    ix, iy = (tx + 0.5) * 256, (ty + 0.5) * 256
    lon_c = ix / n * 360 - 180
    lat_c = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * iy / n))))
    xc, yc = geo.a_utm(lat_c, lon_c)
    r, g, b = img.getpixel((int((xc - rec[0]) / O.RES_M), int((rec[3] - yc) / O.RES_M)))
    assert abs(r - tx % 256) <= 3 and abs(g - ty % 256) <= 3 and abs(b - 90) <= 3
    # la guardada vale mientras cubra los focos con el margen del plano: no se vuelve a pedir
    pedidas.clear()
    cat["focos"][0]["ubicacion"]["x"] += 5
    assert O.vigente(cat)["recuadro"] == info["recuadro"] and O.para_focos(cat)["fecha"] == info["fecha"] and pedidas == []
    cat["focos"][0]["ubicacion"]["x"] -= 500
    assert O.vigente(cat) is None
    # si fallan más de la cuarta parte de las teselas, no se guarda nada nuevo
    def sin_red(*a):
        raise urllib.error.URLError("sin red")
    monkeypatch.setattr(O, "_tesela", sin_red)
    with pytest.raises(RuntimeError, match="sin respuesta"):
        O.para_focos(cat)
    assert O.cargar()["recuadro"] == info["recuadro"]
