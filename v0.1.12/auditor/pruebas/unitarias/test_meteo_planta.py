# -*- coding: utf-8 -*-
"""planta · fuentes · metricas · writer.datos · operacion.meteo_planta: la meteo de los informes, YA PROCESADA, con la planta (v0.1.10). La
hace `operacion.meteo_planta` desde la caché, en el equipo que tiene la meteo en bruto; donde no está (el equipo del cliente), los informes
leen esos productos y salen iguales, sin ir a la red, sin escribir en la caché ni en la planta y sin que ningún fichero lleve la ruta de
DATOS. Sin red: una prueba que lo intente, falla."""
import json
import math
import shutil
import socket
import time

import numpy as np
import pandas as pd
import pytest

from teodors import planta
from teodors.fuentes import era5, meteocat
from teodors.metricas import viento as MV
from teodors.operacion import meteo_planta as MP
from teodors.operacion import viento_mapa as VM
from teodors.writer import datos as W

LAT, LON = 39.75, 1.25                # inventado, como en test_fuentes
CELDA = f"{LAT:.3f}_{LON:.3f}"
ANIOS = [2022, 2023]
JSON_PLANTA = {
    "formato": 1,
    "identidad": {"app_nombre": "Prueba", "organizacion": "ORG", "prefijo_env": "PRUEBA_METEO", "carpeta_local": "prueba_meteo",
                  "registro": "prueba", "agente_http": "agente-general"},
    "proyeccion": {"epsg": "EPSG:25831", "crs_geo": "EPSG:4258", "zona_horaria": "Europe/Madrid"},
    "dominio": {"lado_km": 20, "margen_m": 250, "res_terreno_m": 100, "radio_edificios_km": 1, "radio_edificios_focos_m": 150,
                "celda_viento_m": 500, "zface": [0, 20, 40, 80]},
    "receptores": {"por_km2": 5},
    "reanalisis": {"anios": ANIOS},
    "estaciones": {"radio_km": 30.0, "agente_http": "agente-estaciones", "mediodia_utc_h": 12.0},
}
INVENTARIO = [
    {"codi_estacio": "AA", "nom_estacio": "Estación A", "latitud": LAT + 0.05, "longitud": LON, "codi_estat_ema": meteocat.ESTADO_OPERATIVA,
     "altitud": "10", "nom_municipi": "Uno"},
    {"codi_estacio": "BB", "nom_estacio": "Estación B", "latitud": LAT, "longitud": LON + 0.08, "codi_estat_ema": meteocat.ESTADO_OPERATIVA,
     "altitud": "20", "nom_municipi": "Dos"},
    {"codi_estacio": "ZZ", "nom_estacio": "Lejos", "latitud": LAT + 2.0, "longitud": LON, "codi_estat_ema": meteocat.ESTADO_OPERATIVA,
     "altitud": "5", "nom_municipi": "Tres"},
]
EPISODIOS = ({"ini": "2026-01-10", "dias": 3}, {"ini": "2023-01-20", "dias": 2})   # uno de ahora y otro de un año del reanálisis


@pytest.fixture(autouse=True)
def planta_sin_red(tmp_path, monkeypatch):
    planta.desactivar()

    def sin_red(*a, **k):
        raise AssertionError("una prueba ha intentado salir a la red")
    monkeypatch.setattr(socket.socket, "connect", sin_red)
    monkeypatch.setattr(socket, "getaddrinfo", sin_red)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(meteocat, "_get", lambda *a, **k: pytest.fail("ha pedido a Meteocat"))
    monkeypatch.setattr(era5, "_pedir", lambda *a, **k: pytest.fail("ha pedido al CDS"))
    monkeypatch.setenv("PRUEBA_METEO_DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("PRUEBA_METEO_LOCAL", str(tmp_path / "local"))
    monkeypatch.delenv("PRUEBA_METEO_METEO", raising=False)
    entrada = tmp_path / "entrada"                                         # como una planta de verdad: la meteo, junto a entrada/
    entrada.mkdir()
    (entrada / "planta.json").write_text(json.dumps(JSON_PLANTA), encoding="utf-8")
    (entrada / "emplazamiento.json").write_text(json.dumps({"nombre": "Prueba", "lat": LAT, "lon": LON}), encoding="utf-8")
    planta.activar(entrada)
    yield
    planta.desactivar()


# ── la meteo en bruto de la caché, inventada ──
def _inventario(base):
    (base / "meteocat").mkdir(parents=True, exist_ok=True)
    (base / "meteocat" / "estaciones.json").write_text(json.dumps(INVENTARIO), encoding="utf-8")


def _estacion(base, codigo, desde, dias, k=0.0):
    """Medidas cada media hora (hora UTC del INICIO de la media, como Meteocat): la radiación, con su centro a las 11:45 («inicio»); con
    alguna calma (velocidad 0) para la dirección. Cada valor sale de su hora: los días que se vuelvan a bajar dan lo mismo."""
    horas = pd.date_range(desde, periods=dias * 48, freq="30min")
    h = (horas.hour + horas.minute / 60).to_numpy()
    i = ((horas - pd.Timestamp("2020-01-01")) // pd.Timedelta("30min")).to_numpy()
    ws = np.round(2.0 + 1.5 * np.sin(i / 7.0 + k) + 0.1 * (horas.year.to_numpy() - 2022), 1)
    ws[i % 37 == 0] = 0.0
    df = pd.DataFrame({"time": horas, "ws": ws, "wd": np.round((200 + 120 * np.sin(i / 11.0 + k)) % 360),
                       "t": np.round(8 + 5 * np.sin(2 * np.pi * (h - 9) / 24) + k, 1), "rh": np.round(70 + 20 * np.cos(i / 9.0), 0),
                       "p": 1010.0, "pr": 0.0, "rad": np.round(np.clip(800 * np.cos(2 * np.pi * (h - 11.75) / 24), 0, None), 0),
                       "altura_viento_m": 10.0})
    f = base / "meteocat" / codigo / f"{horas[0].year}.csv"
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.is_file():
        df = pd.concat([pd.read_csv(f, parse_dates=["time"]), df]).drop_duplicates("time", keep="last").sort_values("time")
    df.to_csv(f, index=False)


def _era5(base):
    celda = base / "era5" / CELDA
    celda.mkdir(parents=True, exist_ok=True)
    (celda / "punto.json").write_text(json.dumps({"lat": LAT, "lon": LON, "lsm": 1.0}), encoding="utf-8")
    for a in ANIOS:
        for m in range(1, 13):
            t = pd.date_range(f"{a}-{m:02d}-01", periods=48 if m > 1 else 31 * 24, freq="h")
            x = np.arange(len(t))
            pd.DataFrame({"time": t, "u10": 1.0, "v10": 0.5, "t2m": 10 + 4 * np.sin(x / 4.0) + m, "d2m": 5 + np.cos(x / 5.0),
                          "tcc": (x % 10) / 10.0, "ssrd": np.clip(500 * np.sin(x / 3.8), 0, None), "sshf": 40 * np.cos(x / 3.8) - 5,
                          "blh": 100 + 50.123456 * (x % 7), "zust": 0.2 + 0.01 * (x % 5), "sp": 990 + (x % 3), "tp": 0.1 * (x % 4 == 0),
                          "wspd": 1.1, "wdir": 243.4}).to_csv(celda / f"sfc_{a}{m:02d}.csv", index=False)
    t = pd.date_range(f"{ANIOS[0]}-01-01", f"{ANIOS[-1]}-02-01", freq="h")
    x = np.arange(len(t))
    pd.DataFrame({"time": t, "u10": 2 * np.sin(x / 6.0), "v10": 2 * np.cos(x / 8.0), "t2m": 283.0, "ssrd": 0.0}).to_csv(
        celda / f"serie_sfc_{ANIOS[0]}_{ANIOS[-1]}.csv", index=False)


def _viento():
    t = pd.date_range(f"{ANIOS[0]}-01-01", f"{ANIOS[-1]}-12-31 23:00", freq="h")
    x = np.arange(len(t))
    return "prueba", [f"{h:%Y-%m-%d %H}" for h in t], [round(1.5 + np.sin(i / 5.0), 2) for i in x], [round((90 * i) % 360, 1) for i in x]


@pytest.fixture
def cache_completa(monkeypatch):
    """La caché del equipo de CIRCE: inventario, dos estaciones (enero de los dos años y los días de un episodio de 2026), el ERA5 de la
    celda, su serie y el viento en la planta."""
    c = planta.DIR_METEO
    _inventario(c)
    for k, cod in enumerate(("AA", "BB")):
        for a in ANIOS:
            _estacion(c, cod, f"{a}-01-01", 31, k)
        _estacion(c, cod, "2026-01-09", 6, k)                               # lo que se baja al preparar un episodio
    _era5(c)
    monkeypatch.setattr(VM, "serie_disponible", lambda: "prueba")
    monkeypatch.setattr(MP, "viento_en_la_planta", _viento)
    return c


def _igual(x, y, tol=0.0, ruta=""):
    """Lo mismo, con los NaN iguales y los números con `tol`; la lista de diferencias."""
    if isinstance(x, dict) and isinstance(y, dict):
        if set(x) != set(y):
            return [f"{ruta}: claves {sorted(set(x) ^ set(y))}"]
        return [d for k in x for d in _igual(x[k], y[k], tol, f"{ruta}.{k}")]
    if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
        if len(x) != len(y) or type(x) is not type(y):
            return [f"{ruta}: {type(x).__name__}[{len(x)}] != {type(y).__name__}[{len(y)}]"]
        return [d for i, (p, q) in enumerate(zip(x, y)) for d in _igual(p, q, tol, f"{ruta}[{i}]")]
    if isinstance(x, float) and isinstance(y, float):
        return [] if (math.isnan(x) and math.isnan(y)) or abs(x - y) <= tol else [f"{ruta}: {x} != {y}"]
    return [] if (type(x) is type(y) and x == y) else [f"{ruta}: {x!r} != {y!r}"]


def _ficheros(d):
    return sorted(f.relative_to(d).as_posix() for f in d.rglob("*") if f.is_file()) if d.exists() else []


# ── dónde está y cuándo se lee ──
def test_la_meteo_de_la_planta_va_junto_a_entrada_y_la_cache_sigue_en_datos(tmp_path, monkeypatch):
    # el fallo de la 0.1.9 (descartada): DIR_METEO pasaba a la carpeta de la planta y las descargas iban a parar allí. La caché no se mueve
    assert planta.DIR_METEO_PLANTA.resolve() == (tmp_path / "meteo").resolve()
    assert planta.DIR_METEO.resolve() == (tmp_path / "datos" / "meteo").resolve()
    monkeypatch.setenv("PRUEBA_METEO_METEO", str(tmp_path / "otra"))
    assert planta.Planta(tmp_path / "entrada").DIR_METEO_PLANTA == tmp_path / "otra"


def test_un_producto_se_lee_solo_si_faltan_sus_datos_en_bruto():
    m, c = planta.DIR_METEO_PLANTA, planta.DIR_METEO
    m.mkdir(parents=True)
    assert planta.meteo_procesada("no_esta.json") is None
    (m / "roto.json").write_text("{no es json", encoding="utf-8")
    assert planta.meteo_procesada("roto.json") is None
    (m / "p.json").write_text(json.dumps({"x": 1, "de": ["meteocat/AA/2022.csv", "meteocat/AA/2023.csv"]}), encoding="utf-8")
    assert planta.meteo_procesada("p.json") == {"x": 1, "de": ["meteocat/AA/2022.csv", "meteocat/AA/2023.csv"]}
    _estacion(c, "AA", "2023-01-20", 2)                                    # un episodio de 2023 en el equipo del cliente: no basta
    assert planta.meteo_procesada("p.json") is not None
    _estacion(c, "AA", "2022-01-01", 1)                                    # con TODO aquello de lo que salió: se calcula de ello
    assert planta.meteo_procesada("p.json") is None
    (m / "lista.json").write_text(json.dumps([{"codi_estacio": "AA"}]), encoding="utf-8")   # sin `de` (el inventario): se lee
    assert planta.meteo_procesada("lista.json") == [{"codi_estacio": "AA"}]


def test_sin_la_cache_el_inventario_sale_de_la_planta_sin_ir_a_la_red():
    m = planta.DIR_METEO_PLANTA
    m.mkdir(parents=True)
    (m / "estaciones.json").write_text(json.dumps(INVENTARIO[:1]), encoding="utf-8")
    assert [e["codigo"] for e in meteocat.cercanas(LAT, LON)] == ["AA"]
    assert [e["codigo"] for e in meteocat.para_mapa(LAT, LON)] == ["AA"]
    _inventario(planta.DIR_METEO)                                          # con el de la caché, manda el de la caché
    assert [e["codigo"] for e in meteocat.cercanas(LAT, LON)] == ["AA", "BB"]
    assert not (m / "meteocat").exists()                                   # y nada se ha escrito en la planta


def test_una_hora_en_calma_no_da_direccion():
    # con el viento parado la dirección no existe: la media de la hora la dejaba en 0° o en 180° según el signo de un cero, y una estación
    # en calma movía la dirección media del episodio hasta 16° (según cuántos datos tuviera el fichero)
    obs = pd.DataFrame({"mes": [1, 1, 1], "dia": [10, 10, 10], "hh": [5, 5, 6], "anio": [2026] * 3, "ws": [0.0, 2.0, 0.0],
                        "wd": [180.0, 90.0, 0.0], "t": [1.0, 2.0, 3.0]})
    assert list(W._con_dato(obs, "wd")["val"]) == [90.0]
    assert list(W._con_dato(obs, "t")["val"]) == [1.0, 2.0, 3.0]          # lo demás, también en calma
    assert list(W._con_dato(obs, "ws")["val"]) == [0.0, 2.0, 0.0]


def test_las_ranuras_del_anio():
    r = W._ranuras_del_anio()
    assert len(r) == 366 * 24 and r[0] == "01-01-00" and r[-1] == "12-31-23" and len(set(r)) == len(r)
    m, d, h = [2, 2, 12, 3], [28, 29, 31, 1], [23, 0, 23, 0]
    assert [r[i] for i in W._indice_ranura(m, d, h)] == ["02-28-23", "02-29-00", "12-31-23", "03-01-00"]


# ── operacion.meteo_planta y lo que leen los informes ──
def test_faltan_lo_que_no_esta_en_la_cache(cache_completa, monkeypatch):
    assert MP.faltan() == []
    (cache_completa / "era5" / CELDA / "sfc_202301.csv").unlink()
    assert MP.faltan() == [f"era5/{CELDA}/sfc_202301.csv"]
    monkeypatch.setattr(VM, "serie_disponible", lambda: None)
    assert len(MP.faltan()) == 2 and "viento" in MP.faltan()[-1]


def test_construir_deja_solo_lo_procesado_y_sin_ninguna_ruta(cache_completa, tmp_path):
    ind = MP.construir()
    m = planta.DIR_METEO_PLANTA
    assert _ficheros(m) == sorted(list(MP.PRODUCTOS) + ["indice.json", "LEEME.md"])   # ni un fichero en bruto
    assert set(ind["ficheros"]) == set(MP.PRODUCTOS) and ind["anios"] == ANIOS and ind["estaciones"] == ["AA", "BB"]
    for f in m.iterdir():                                                  # ni la ruta de DATOS ni ninguna otra del equipo
        texto = f.read_text(encoding="utf-8").lower()
        assert str(tmp_path).lower() not in texto and tmp_path.as_posix().lower() not in texto and not MP.lleva_ruta(f, MP.rutas_de_datos())
    assert [e["codi_estacio"] for e in json.loads((m / "estaciones.json").read_text(encoding="utf-8"))] == ["AA", "BB"]   # sin la lejana
    nor = json.loads((m / "normales_estaciones.json").read_text(encoding="utf-8"))
    assert nor["de"] == [f"meteocat/{c}/{a}.csv" for c in ("AA", "BB") for a in ANIOS]   # relativos a la caché; sin los días de 2026
    assert nor["convencion"] == {"AA": "inicio", "BB": "inicio"}
    v = nor["variables"]["viento"]
    i = nor["ranuras"].index("01-15-12")
    anio = [v["por_anio"][str(a)][i] for a in ANIOS]
    assert v["min"][i] == min(anio) and v["max"][i] == max(anio) and v["mediana"][i] == pytest.approx(np.median(anio), abs=5e-4)   # con los decimales con los que se guarda
    assert v["por_anio"]["2022"][nor["ranuras"].index("07-15-12")] is None                       # julio: sin medidas
    assert all(isinstance(x, int) for x in nor["variables"]["direccion"]["nube"]["2022"][i])      # en grados enteros, como se mide
    t = json.loads((m / "tiempo_planta.json").read_text(encoding="utf-8"))
    assert t["anios"] == ANIOS and t["viento"]["serie"] == "prueba" and t["era5"]["dias"][0] == "2022-01-01" and t["era5"]["dias"][-1] == "2023-12-02"
    assert all(p.startswith(f"era5/{CELDA}/") for p in t["de"]) and len(t["de"]) == 1 + 12 * len(ANIOS)
    assert "| Temperatura | °C |" in (m / "LEEME.md").read_text(encoding="utf-8")
    assert not (m.parent / "meteo.parcial").exists() and not (m.parent / "meteo.anterior").exists()


def test_sin_la_meteo_en_bruto_los_informes_salen_iguales(cache_completa):
    # el equipo de CIRCE calcula de la caché; el del cliente (sin ella: solo los días que bajó para sus episodios) lee la planta
    emp = planta.cargar_emplazamiento()
    _, horas, ws, wd = _viento()
    MP.construir()
    calculados = MP.PRODUCTOS[1:]                                          # los que salen de la meteo en bruto (el inventario, aparte)
    assert all(planta.meteo_procesada(n) is None for n in calculados)      # aquí está todo: se calcula de la caché, como siempre
    en_bruto = {"era5": W._era5(emp, horas, ws, wd), "estaciones": W._estaciones(emp),
                "episodios": [W._clima_comparacion(emp, p) for p in EPISODIOS]}
    assert all(en_bruto["episodios"]) and en_bruto["era5"] and en_bruto["estaciones"]
    # el equipo del cliente: ni la historia de las estaciones ni el ERA5, solo los días de sus episodios
    c = planta.DIR_METEO
    shutil.rmtree(c)
    for k, cod in enumerate(("AA", "BB")):
        _estacion(c, cod, "2026-01-09", 6, k)
        _estacion(c, cod, "2023-01-19", 4, k)
        sub = pd.read_csv(c / "meteocat" / cod / "2023.csv", parse_dates=["time"])          # los mismos valores que en CIRCE
        assert len(sub) == 4 * 48
    assert all(planta.meteo_procesada(n) is not None for n in calculados)  # aquí no: se lee lo que trae la planta
    antes_planta = {f: f.stat().st_mtime_ns for f in planta.DIR_METEO_PLANTA.iterdir()}
    antes_cache = _ficheros(c)
    del_cliente = {"era5": W._era5(emp, horas, ws, wd), "estaciones": W._estaciones(emp),
                   "episodios": [W._clima_comparacion(emp, p) for p in EPISODIOS]}
    a, b = dict(en_bruto["era5"]), dict(del_cliente["era5"])
    sa, sb = a.pop("_sfc"), b.pop("_sfc")
    assert _igual(a, b) == []                                              # el tiempo en la planta: el mismo
    assert sa["horas"] == sb["horas"] and _igual(sa["H"], sb["H"], 0.05 + 1e-9) == [] and _igual(sa["blh"], sb["blh"], 0.05 + 1e-9) == []
    assert _igual(en_bruto["estaciones"], del_cliente["estaciones"]) == []  # las rosas: las mismas
    for p, x, y in zip(EPISODIOS, en_bruto["episodios"], del_cliente["episodios"]):
        x, y = dict(x), dict(y)
        vx, vy = x.pop("variables"), y.pop("variables")
        assert _igual(x, y) == [], p
        for u, v in zip(vx, vy):
            u, v = dict(u), dict(v)
            assert _igual(u.pop("ep"), v.pop("ep")) == [], (p, u["clave"])                   # lo del episodio: lo medido, igual
            nu, nv = sorted(u.pop("nube")), sorted(v.pop("nube"))
            assert len(nu) == len(nv) and all(i == j and abs(s - t) <= 0.5 for (i, s), (j, t) in zip(nu, nv)), (p, u["clave"])
            tol = {"viento": 6e-4, "temperatura": 6e-4, "humedad": 6e-3}.get(u["clave"], 0.0)
            assert _igual(u, v, tol) == [], (p, u["clave"])                                  # lo normal, con lo que se guarda
            if u["forma"] != "rumbos":
                assert np.isfinite(u["med"]).any()
    assert {f: f.stat().st_mtime_ns for f in planta.DIR_METEO_PLANTA.iterdir()} == antes_planta   # la planta, intacta
    assert _ficheros(c) == antes_cache                                                         # y nada escrito en la caché


def test_lo_normal_nunca_incluye_el_anio_del_episodio(cache_completa):
    MP.construir()
    shutil.rmtree(planta.DIR_METEO)
    for k, cod in enumerate(("AA", "BB")):
        _estacion(planta.DIR_METEO, cod, "2023-01-19", 4, k)
    _inventario(planta.DIR_METEO)
    cc = W._clima_comparacion(planta.cargar_emplazamiento(), EPISODIOS[1])
    assert cc["anios"] == "2022–2022"
    nor = json.loads((planta.DIR_METEO_PLANTA / "normales_estaciones.json").read_text(encoding="utf-8"))
    v = next(x for x in cc["variables"] if x["clave"] == "temperatura")
    i = nor["ranuras"].index("01-20-00")
    assert v["med"][0] == v["lo"][0] == v["hi"][0] == nor["variables"]["temperatura"]["por_anio"]["2022"][i]   # solo 2022


def test_construir_no_toca_nada_si_falta_algo_o_si_un_fichero_lleva_la_ruta_de_datos(cache_completa, monkeypatch):
    MP.construir()
    m = planta.DIR_METEO_PLANTA
    antes = {f: f.read_bytes() for f in m.iterdir()}
    bueno = MP.productos
    monkeypatch.setattr(MP, "productos", lambda emp=None: dict(bueno(emp), **{"estaciones.json": [{"nota": str(planta.DATOS)}]}))
    with pytest.raises(ValueError, match="ruta de la carpeta de DATOS"):
        MP.construir()
    assert {f: f.read_bytes() for f in m.iterdir()} == antes and not (m.parent / "meteo.parcial").exists()
    monkeypatch.setattr(MP, "productos", bueno)
    (cache_completa / "era5" / CELDA / "sfc_202301.csv").unlink()
    with pytest.raises(FileNotFoundError, match="sfc_202301.csv"):
        MP.construir()
    assert {f: f.read_bytes() for f in m.iterdir()} == antes and not (m.parent / "meteo.parcial").exists()


def test_los_modelos_del_mos_viajan_con_la_planta_sin_tocar_lo_demas(cache_completa):
    """0.1.12: la predicción corrige la previsión con el MOS (`mos.aplicar`), y el equipo del cliente no tiene la caché: sus modelos van con la planta, en `meteo/mos/`."""
    from teodors.mos import aplicar
    MP.construir()
    m = planta.DIR_METEO_PLANTA
    antes = {f: f.read_bytes() for f in m.iterdir() if f.is_file()}
    with pytest.raises(FileNotFoundError, match="modelos del MOS"):
        MP.construir_mos()
    assert not (m / MP.MOS).exists() and aplicar.carpeta_modelos() is None
    modelos = planta.DATOS / "mos" / "modelos"
    modelos.mkdir(parents=True)
    for c in ("AA", "BB"):
        for k in ("u", "v", "ws"):
            (modelos / f"{c}_{k}.joblib").write_bytes(f"modelo {c} {k}".encode())
    (planta.DATOS / "mos" / "resumen.json").write_text(json.dumps({"periodo": ["2022-01-01 00:00:00", "2023-12-31 23:00:00"], "ejecuciones": 700}), encoding="utf-8")
    assert aplicar.carpeta_modelos() == modelos                                                  # en el equipo con la caché, los de la caché
    ind = MP.construir_mos()
    assert _ficheros(m / MP.MOS) == sorted([f"{c}_{k}.joblib" for c in ("AA", "BB") for k in ("u", "v", "ws")] + ["indice.json"])
    assert ind["estaciones"] == ["AA", "BB"] and ind["ejecuciones"] == 700 and ind["periodo"][0] == "2022-01-01 00:00:00" and len(ind["ficheros"]) == 6
    assert ind["ficheros"]["AA_u.joblib"]["sha256"] == MP._huella(m / MP.MOS / "AA_u.joblib")
    assert {f: f.read_bytes() for f in m.iterdir() if f.is_file()} == antes                      # lo demás, igual
    assert aplicar.carpeta_modelos() == m / MP.MOS                                               # y desde ahora, los de la planta
    ind = MP.construir()                                                                         # al rehacerla entera, siguen, y lo dicen el índice y el LEEME
    assert ind["mos"] == {"estaciones": ["AA", "BB"], "ficheros": 6} and (m / MP.MOS / "BB_ws.joblib").is_file()
    assert "`mos/`" in (m / "LEEME.md").read_text(encoding="utf-8")
    (modelos / "AA_u.joblib").write_bytes(str(planta.DATOS).encode())                           # un modelo con la ruta de DATOS: no se toca nada
    with pytest.raises(ValueError, match="ruta de la carpeta de DATOS"):
        MP.construir_mos()
    assert (m / MP.MOS / "AA_u.joblib").read_bytes() == b"modelo AA u" and not (m.parent / "meteo.mos_parcial").exists()


def test_las_rosas_que_trae_la_planta_no_se_recalculan(cache_completa, monkeypatch):
    MP.construir()
    shutil.rmtree(planta.DIR_METEO)
    monkeypatch.setattr(MV, "era5_horario", lambda *a, **k: pytest.fail("ha recalculado unas rosas que ya traía la planta"))
    r = MV.rosas_estaciones(LAT, LON)
    assert set(r["estaciones"]) == {"AA", "BB"} and r["anios"] == ANIOS
    assert not planta.DIR_METEO.exists() or _ficheros(planta.DIR_METEO) == []          # ni su caché en DATOS

    def calcula(*a, **k):
        raise RuntimeError("las calcula")
    monkeypatch.setattr(MV, "era5_horario", calcula)
    with pytest.raises(RuntimeError, match="las calcula"):                             # sin la planta (procesada=False): las calcula
        MV.rosas_estaciones(LAT, LON, procesada=False)
