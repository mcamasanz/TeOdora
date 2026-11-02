# -*- coding: utf-8 -*-
"""operacion · de los focos y los planes a los resultados, SIN RED y con una planta inventada a propósito. Las cuentas se comprueban a mano, con series hechas para que
el resultado se sepa de antemano, con la ley de los gases ideales y, en la cuenta entera, frente a una corrida directa del motor. Comprueban el código: los focos son
inventados, y no dicen nada de ninguna planta."""
import ast
import base64
import json
import re
import shutil
import socket
import subprocess
import sys
import tomllib
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pd = pytest.importorskip("pandas")
xr = pytest.importorskip("xarray")
pytest.importorskip("PIL")

from teodors import planta  # noqa: E402
from teodors.casos import viento3d as vc  # noqa: E402
from teodors.comun import procesos  # noqa: E402
from teodors.dispersion.puffs.principal import ejecutar  # noqa: E402
from teodors.fuentes import terreno  # noqa: E402
from teodors.fuentes.gfs_noaa import NIVELES  # noqa: E402
from teodors.meteo.viento3d import almacen, fichero_viento  # noqa: E402
from teodors.operacion import ejemplo_configuracion, focos as F, normativa as N, penacho_3d as P3D, penacho_mapa as PM, periodos, planes as E, respuestas as RS, simulacion as S  # noqa: E402
from teodors.operacion import viento_mapa as VM, viento_periodo as VP  # noqa: E402
from teodors.planta import geo  # noqa: E402
from teodors.preparacion.puffs import control_fuentes, salida  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
OPERACION = RAIZ / "core" / "operacion"
VIENTO_24H = RAIZ / "auditor" / "casos" / "viento3d" / "llano_lleida" / "referencia" / "calmet.dat"
LAT, LON = 38.6, 1.4                  # inventado, en el mar
EPSG = "EPSG:25831"
ZFACE = [0, 20, 40, 80, 160, 300, 600, 1000]
R_GAS, P_ATM = 8.314462618, 101325.0
JSON_PLANTA = {
    "formato": 1,
    "identidad": {"app_nombre": "Prueba", "organizacion": "ORG", "prefijo_env": "PRUEBA_OPER", "carpeta_local": "prueba_oper", "registro": "prueba", "nombre_casos": "Planta X"},
    "proyeccion": {"epsg": EPSG, "crs_geo": "EPSG:4258", "zona_horaria": "Europe/Madrid"},
    "dominio": {"lado_km": 3, "margen_m": 250, "res_terreno_m": 25, "radio_edificios_km": 1.5, "radio_edificios_focos_m": 150, "celda_viento_m": 100, "zface": ZFACE},
    "receptores": {"por_km2": 5, "niveles": [["a", 100.0, 500.0], ["b", 400.0, None]], "estilos": {}},
    "reanalisis": {"anios": [2023]},
    "estaciones": {"codigos": ["AA", "BB"]},
    "pronostico": {"n_col": 2, "paso_col_m": 5000.0},
    "series": {"r1_km": 7.0, "rmax_km": 40.0, "era5": "serie_a", "gfs": "serie_b", "preferidas": ["serie_a", "serie_b"], "titulos": {"serie_a": "Título A"}, "dia_prueba": "2023-03-10"},
    "operacion": {"tipos_foco_extra": {"tolva": ["Tolva", ["punto", "volumen"], "continuo"]}, "ejemplo": "su_ejemplo"},
    "visor3d": {"semilado_m": 400.0, "rotulos": [{"t": "Pueblo X", "lon": LON + 0.002, "lat": LAT}]},
}


def _planta(carpeta, **bloques):
    datos = json.loads(json.dumps(JSON_PLANTA))
    for k, v in bloques.items():
        datos[k] = dict(datos.get(k, {}), **v)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
    (carpeta / "emplazamiento.json").write_text(json.dumps({"nombre": "Prueba", "lat": LAT, "lon": LON}), encoding="utf-8")
    return planta.activar(carpeta)


@pytest.fixture(autouse=True)
def sin_red_y_con_planta(tmp_path, monkeypatch):
    def sin_red(*a, **k):
        raise AssertionError("una prueba ha intentado salir a la red")
    monkeypatch.setattr(socket.socket, "connect", sin_red)
    monkeypatch.setattr(socket, "getaddrinfo", sin_red)
    monkeypatch.setenv("PRUEBA_OPER_DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("PRUEBA_OPER_LOCAL", str(tmp_path / "local"))
    planta.desactivar()
    _planta(tmp_path / "planta")
    for f in (VM.datos_local, VM._mes, VM._rejilla):
        f.cache_clear()
    yield
    planta.desactivar()


@pytest.fixture
def sin_imagenes(monkeypatch):
    """Solo las series: las imágenes se comprueban aparte."""
    monkeypatch.setattr(S, "_rejillas", lambda *a: [])
    monkeypatch.setattr(S, "_imagenes", lambda *a, **k: [])


def _foco(i, q=1000.0, **extra):
    return {"id": i, "nombre": f"Foco {i}", "tipo": "fugitivas", "modelo": "volumen", "ubicacion": {"x": 1000.0, "y": 2000.0}, "altura_m": 3.0,
            "dimensiones": {"largo_m": 10.0, "ancho_m": 10.0, "alto_m": 4.0}, "funcionamiento": {"modo": "continuo"}, "olor": {"valor": q, "unidad": "ou_E/s"}, "gases": [], **extra}


def _receptores(n=4):
    xc, yc = geo.a_utm(LAT, LON)
    k = np.arange(n) * 300.0
    X, Y = np.meshgrid(xc + k, yc + k)
    return X.ravel(), Y.ravel()


def _guarda_respuestas(focos, valor, nt=24, carpeta=None, serie="serie_b"):
    """R[h, t, r] = 0 salvo R[H − 1, t, r] = valor(t, r), con H la hora del fin de t: lo emitido en esa hora solo llega en esa hora, y C(t, r) = Q · F(t) · valor(t, r)."""
    carpeta = carpeta or planta.DATOS / "respuestas" / f"{serie}_20230310"
    carpeta.mkdir(parents=True, exist_ok=True)
    x, y = _receptores()
    for f in focos:
        R = np.zeros((24, nt, len(x)), np.float32)
        for t in range(nt):
            R[(t - 1) % 24, t] = [valor(f["id"], t, r) for r in range(len(x))]
        np.savez_compressed(carpeta / f"R_{f['id']}.npz", R=R)
    clase = np.array(["a"] * (len(x) - 1) + ["vivienda"])
    np.savez_compressed(carpeta / "receptores.npz", x=x, y=y, cota=np.zeros(len(x)), clase=clase)
    (carpeta / "meta.json").write_text(json.dumps({
        "formato": 1, "dia": "2023-03-10", "dias": 1, "serie": serie, "receptores": len(x), "centro": list(geo.a_utm(LAT, LON)), "focos": {f["id"]: {"huella": F.huella(f)} for f in focos},
        "etiquetas": [{"i": 1, "nombre": "Vecino", "clase": "nombrado"}, {"i": 5, "nombre": "Pueblo", "clase": "nucleo", "familia": "residencial"}]}), encoding="utf-8")
    return x, y


def _campos(esc, clave="olor", periodo=None):
    with np.load(S.carpeta_resultados(esc, periodo) / clave / "resumen.npz") as z:
        return {c: z[c] for c in z.files if c not in ("x", "y", "clase")}


def _anios():
    return pd.date_range("2023-01-01 01:00", "2024-01-01 00:00", freq="h")


# ── los años del reanálisis ──
def test_media_maximo_y_p98_de_la_serie_horaria_a_mano(sin_imagenes):
    f = _foco("F01", q=1000.0)
    cat = {"focos": [f]}
    _guarda_respuestas([f], lambda i, t, r: (t + 1) * (r + 1) * 1e-3)         # Q · R = (hora + 1) · (r + 1)
    esc = E.nuevo(cat, "P")
    res = S.calcular(esc, cat)
    z = _campos(esc)
    serie = np.outer(_anios().hour + 1, np.arange(16) + 1)[24:]                # sin el primer día: aún no ha llegado todo
    assert res["horas"] == len(_anios()) - 24 and res["largo"] == "anios"
    assert z["media"] == pytest.approx(serie.mean(axis=0), rel=1e-5)
    assert z["maximo"] == pytest.approx(serie.max(axis=0), rel=1e-5)
    assert z["p98"] == pytest.approx(np.percentile(serie, 98, axis=0), rel=1e-5)
    assert z["p98"][0] > 1.8 * z["media"][0]                                   # no sale de las medias: el 2 % más alto es casi el doble
    m = res["magnitudes"]["olor"]
    nombres = [fila["nombre"] for fila in m["filas"]]
    assert m["unidad"] == "ou_E/m³" and "Pueblo" in nombres and "Peor vivienda (< 1.5 km)" in nombres
    assert m["filas"][nombres.index("Peor vivienda (< 1.5 km)")]["maximo"] == pytest.approx(24 * 16, rel=1e-5)


def test_solo_cuentan_las_horas_validas_ni_el_primer_dia_ni_otro_mes(sin_imagenes):
    """Plan mensual de enero, alto solo el día 1. Si contara el primer día de la serie, el máximo sería el alto, y si contara otro mes, habría más horas."""
    f = _foco("F01", q=1.0)
    cat = {"focos": [f]}
    _guarda_respuestas([f], lambda i, t, r: 1.0)
    esc = E.nuevo(cat, "M")
    esc["mes"] = "2023-01"
    pf = E.plan_foco(f, esc)
    E.cambiar_plan(pf, "mensual")
    E.poner_perfil(pf, list(range(1, 31)), [0.25] * 24)
    E.poner_perfil(pf, [0], [0.25] + [1.0] * 23)                                # la hora 0 del día 1, baja: la última hora de la serie ya es esa, en hora oficial
    res = S.calcular(esc, cat)
    z = _campos(esc)
    # por el fin de la hora en hora oficial, y sin el primer día: de las 02 del 2 de enero a las 23 del 31 (718 h)... y las 2 últimas horas UTC de la serie, que ya son enero de 2024
    assert res["horas"] == 720
    assert z["maximo"] == pytest.approx(0.25, rel=1e-5) and z["media"] == pytest.approx(0.25, rel=1e-5)


def _dos_focos():
    a, b = _foco("F01", q=100.0), _foco("F02", q=30.0)
    cat = {"focos": [a, b]}
    _guarda_respuestas([a, b], lambda i, t, r: (1.0 if i == "F01" else 5.0) * ((t + r) % 7 + 1))
    return a, b, cat


def _apagado(esc, foco):
    E.poner_perfil(E.plan_foco(foco, esc), [0], [0.0] * 24)


def test_la_emision_es_lineal_y_los_focos_se_suman(sin_imagenes):
    a, b, cat = _dos_focos()
    base = E.nuevo(cat, "Base2")
    S.calcular(base, cat)
    z = _campos(base)
    mitad = E.nuevo(cat, "Mitad")
    for f in (a, b):
        E.poner_perfil(E.plan_foco(f, mitad), [0], [0.5] * 24)
    S.calcular(mitad, cat)
    m = _campos(mitad)
    for c in ("media", "maximo", "p98"):
        assert m[c] == pytest.approx(0.5 * z[c], rel=1e-5)
    solo_a, solo_b = E.nuevo(cat, "Solo A"), E.nuevo(cat, "Solo B")
    _apagado(solo_a, b)
    _apagado(solo_b, a)
    S.calcular(solo_a, cat)
    S.calcular(solo_b, cat)
    assert _campos(solo_a)["media"] + _campos(solo_b)["media"] == pytest.approx(z["media"], rel=1e-5)
    todo = E.nuevo(cat, "Apagado")
    _apagado(todo, a)
    _apagado(todo, b)
    res = S.calcular(todo, cat)
    assert _campos(todo)["maximo"].max() == 0.0 and res["magnitudes"]["olor"]["focos"] == 0


def test_solo_el_lunes_es_un_septimo_y_mensual_constante_es_diario(sin_imagenes):
    f = _foco("F01")
    cat = {"focos": [f]}
    _guarda_respuestas([f], lambda i, t, r: t + 1.0)
    diario = E.nuevo(cat, "Diario")
    S.calcular(diario, cat)
    d = _campos(diario)
    lunes = E.nuevo(cat, "Lunes")
    pf = E.plan_foco(f, lunes)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, [1, 2, 3, 4, 5, 6], [0.0] * 24)
    S.calcular(lunes, cat)
    assert _campos(lunes)["media"] == pytest.approx(d["media"] / 7, rel=2e-3)
    assert _campos(lunes)["maximo"] == pytest.approx(d["maximo"], rel=1e-5)
    mes = E.nuevo(cat, "Febrero")
    mes["mes"] = "2023-02"
    E.cambiar_plan(E.plan_foco(f, mes), "mensual")
    r = S.calcular(mes, cat)
    assert r["horas"] == 28 * 24 and _campos(mes)["media"] == pytest.approx(d["media"], rel=1e-5)


def test_lo_que_no_se_puede_calcular_se_dice(sin_imagenes):
    f, sin, cambiado, nada = _foco("F01"), _foco("F02", olor={}), _foco("F03"), _foco("F04", funcionamiento={"modo": "eventos"})
    _guarda_respuestas([f, sin, cambiado], lambda i, t, r: 1e-3)
    otra = dict(cambiado, altura_m=99.0)
    cat = {"focos": [f, sin, otra, nada]}
    res = S.calcular(E.nuevo(cat, "F"), cat)
    fuera = " ".join(res["magnitudes"]["olor"]["fuera"])
    assert "Foco F02: sin emisión de olor" in fuera and "Foco F03: ha cambiado" in fuera and "Foco F04: sin frecuencia" in fuera
    with pytest.raises(RuntimeError, match="Ningún foco"):
        S.calcular(E.nuevo({"focos": [sin]}, "N"), {"focos": [sin]})


def test_gases_con_las_mismas_respuestas_y_olor_estimado(sin_imagenes):
    f = _foco("F01", olor={}, gases=[{"gas": "H2S", "valor": 0.5, "unidad": "g/s"}, {"gas": "NO2", "valor": 1.0, "unidad": "g/s"}])
    cat = {"focos": [f]}
    _guarda_respuestas([f], lambda i, t, r: 2e-6 * (r + 1))
    esc = E.nuevo(cat, "G")
    res = S.calcular(esc, cat)
    assert res["orden"] == ["olor", "H2S", "NO2"]
    assert _campos(esc, "H2S")["media"][0] == pytest.approx(0.5e6 * 2e-6, rel=1e-5)          # µg/s × s/m³ = µg/m³
    umbral = 0.41 * 34.08 / 24.45                                                            # µg/m³ del H2S: el dominante
    assert _campos(esc, "olor")["media"][0] == pytest.approx(0.5e6 / umbral * 2e-6, rel=1e-5)
    assert res["magnitudes"]["olor"]["estimados"] == ["Foco F01 (H₂S)"]
    assert [c["clave"] for c in res["magnitudes"]["NO2"]["columnas"]] == ["media", "maximo", "norma_hora", "norma_anio"]
    assert _campos(esc, "NO2")["norma_hora"][0] == pytest.approx(2.0, rel=1e-5)              # constante: su 19.ª hora también


def test_con_imagenes_se_guarda_y_se_vuelve_a_leer():
    f = _foco("F01")
    cat = {"focos": [f]}
    _guarda_respuestas([f], lambda i, t, r: 1e-2 * (r + 1))
    esc = E.nuevo(cat, "Con imágenes")
    res = S.calcular(esc, cat)
    assert res["firma"] == S.firma(esc, cat) and [c["id"] for c in res["magnitudes"]["olor"]["capas"]] == ["plan_media", "plan_maximo", "plan_norma"]
    guardado = S.guardado(esc, cat)
    assert guardado is not None and guardado["firma"] == res["firma"]
    url = res["magnitudes"]["olor"]["capas"][0]["imagenes"][0]["url"]
    assert url.startswith("file:") and Path(S.url_a_ruta(url)).is_file()
    assert S.guardado(dict(esc, mes="2023-05"), cat) is None
    Path(S.url_a_ruta(url)).unlink()
    assert S.guardado(esc, cat) is None                                         # sin una imagen, no vale
    v = S.valores(res, "olor")
    x, y = _receptores()
    assert v[(round(float(x[0]), 1), round(float(y[0]), 1))]["maximo"] == pytest.approx(10.0, rel=1e-5)
    assert S.cifra(0) == "0" and S.cifra(0.004) == "< 0,01" and S.cifra(1.234) == "1,2" and S.cifra(123.4) == "123"
    assert S.horas_reanalisis() == ("2023-01-01 01:00", "2024-01-01 00:00")


# ── un periodo: día, episodio o predicción ──
def test_periodo_en_hora_oficial_con_cambio_de_hora(sin_imagenes):
    """El plan va en hora oficial y el cálculo en UTC: a las 8 oficiales son las 7 UTC antes del cambio de hora y las 6 después."""
    f = _foco("F01", q=10.0)
    cat = {"focos": [f]}
    periodo = periodos.nuevo("queja", "2023-03-25", 2)
    _guarda_respuestas([f], lambda i, t, r: 1.0, nt=48, carpeta=periodos.dir_respuestas(periodo), serie=periodo["serie"])
    perfil = [0.0] * 24
    perfil[8] = 1.0
    esc = E.nuevo(cat, "Ocho")
    E.poner_perfil(E.plan_foco(f, esc), [0], perfil)
    res = S.calcular_periodo(esc, cat, periodo)
    C = np.load(S.carpeta_resultados(esc, periodo) / "olor" / "penacho.npz")["C"]
    assert C.shape == (48, 16)
    assert np.flatnonzero(C[:, 0]).tolist() == [8, 24 + 7]                      # por el FIN de la hora: 7-8 UTC y, tras el cambio, 6-7 UTC
    assert C[8, 0] == pytest.approx(10.0)
    m = res["magnitudes"]["olor"]
    assert m["horas_txt"][8] == "25/03 09:00" and m["horas_txt"][31] == "26/03 09:00" and len(m["penacho"]["frames"]) == 48
    z = _campos(esc, periodo=periodo)
    assert z["hora_max"][0] == 8 and z["media"][0] == pytest.approx(2 * 10.0 / 48, rel=1e-5)
    assert [c["clave"] for c in m["columnas"]] == ["media", "maximo", "hora_max"]        # en días, sin P98
    assert S.texto_celda(m["columnas"][2], z["hora_max"][0], m) == "25/03 09:00"


def test_las_horas_de_antes_del_periodo_siguen_en_el_aire(sin_imagenes):
    """Lo emitido el día anterior llega a primera hora: R[h, t] con h de horas de antes."""
    f = _foco("F01", q=1.0)
    cat = {"focos": [f]}
    periodo = periodos.nuevo("queja", "2023-03-25", 1)
    carpeta = periodos.dir_respuestas(periodo)
    _guarda_respuestas([f], lambda i, t, r: 0.0, carpeta=carpeta, serie=periodo["serie"])
    R = np.zeros((24, 24, 16), np.float32)
    R[22, 2] = 3.0                                                              # lo emitido de 22 a 23 UTC (las 23 oficiales del viernes 24) llega a la t = 2 del sábado
    np.savez_compressed(carpeta / "R_F01.npz", R=R)
    esc = E.nuevo(cat, "Noche")
    pf = E.plan_foco(f, esc)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, [4], [0.0] * 24)                                         # el viernes apagado
    S.calcular_periodo(esc, cat, periodo)
    C = np.load(S.carpeta_resultados(esc, periodo) / "olor" / "penacho.npz")["C"]
    assert C[2, 0] == 0.0
    E.poner_perfil(pf, [4], [1.0] * 24)                                         # solo el viernes: el sábado que se ve no emite, y aun así llega
    E.poner_perfil(pf, [0, 1, 2, 3, 5, 6], [0.0] * 24)
    S.calcular_periodo(esc, cat, periodo)
    C = np.load(S.carpeta_resultados(esc, periodo) / "olor" / "penacho.npz")["C"]
    assert C[2, 0] == pytest.approx(3.0) and C[3, 0] == 0.0


# ── la cuenta entera, frente al motor ──
def _ejecucion_gfs(dia, plazos=range(0, 25, 3)):
    plazos = list(plazos)
    lat, lon = np.arange(39.5, 37.74, -0.25), np.arange(0.5, 2.26, 0.25)
    forma = (len(plazos), len(lat), len(lon))
    datos = {"temperature_2m": np.full(forma, 15.0), "relative_humidity_2m": np.full(forma, 70.0), "surface_pressure": np.full(forma, 1000.0), "pressure_msl": np.full(forma, 1012.0),
             "wind_u_10m": np.full(forma, 3.0), "wind_v_10m": np.full(forma, 2.0), "cloud_cover": np.full(forma, 40.0)}
    for p in NIVELES:
        datos.update({f"geopotential_height_{p}hPa": np.full(forma, (1013.0 - p) * 9.0), f"temperature_{p}hPa": np.full(forma, 12.0), f"wind_u_{p}hPa": np.full(forma, 4.0), f"wind_v_{p}hPa": np.full(forma, 3.0)})
    return xr.Dataset({n: (("plazo_h", "latitude", "longitude"), v) for n, v in datos.items()}, coords={"plazo_h": plazos, "latitude": lat, "longitude": lon, "init_time": pd.Timestamp(dia)})


@pytest.fixture(scope="module")
def cadena(tmp_path_factory):
    """Viento de verdad (`viento_periodo.preparar_caso` con un GFS inventado y `meteo.viento3d`) y respuestas de verdad de dos focos (`respuestas.correr`, `dispersion.puffs`)."""
    base = tmp_path_factory.mktemp("cadena")
    dia = pd.Timestamp("2023-03-10")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("PRUEBA_OPER_DATOS", str(base / "datos"))
        mp.setenv("PRUEBA_OPER_LOCAL", str(base / "local"))
        _planta(base / "planta", proyeccion={"zona_horaria": "Etc/UTC"})
        Z, U = np.full((32, 48), 100.0), np.full((32, 48), 211, dtype=np.int32)
        x0, y0 = geo.a_utm(LAT, LON)
        tr = SimpleNamespace(a=25.0, c=round(x0) - 600.0, e=-25.0, f=round(y0) + 400.0)
        mp.setattr(terreno, "cargar", lambda info: (Z, U, tr))
        carpeta = planta.DATOS / "meteo" / "gfs_niveles"
        carpeta.mkdir(parents=True)
        for k in (-2, -1, 0):
            d = dia + pd.Timedelta(days=k)
            _ejecucion_gfs(d).to_netcdf(carpeta / f"gfs00_{d:%Y%m%d}.nc")
        caso = base / "caso"
        VP.preparar_caso(dia, {"caso": 1}, None, caso, 1)
        vc.ejecutar(caso)
        info = json.loads((caso / "caso.json").read_text(encoding="utf-8"))
        malla = {k: info[k] for k in ("nx", "ny", "celda_m", "ext")}
        xc, yc = geo.a_utm(LAT, LON)
        area = _foco("A1", q=500.0, modelo="superficie", ubicacion={"poligono": [[xc - 30, yc - 20], [xc + 30, yc - 20], [xc + 30, yc + 20], [xc - 30, yc + 20]]}, tipo="biofiltro", altura_m=2.0)
        vol = _foco("V1", q=200.0, ubicacion={"x": xc + 100.0, "y": yc}, altura_m=5.0)
        cat = {"focos": [area, vol]}
        recs = [(xc + dx, yc + dy, 100.0) for dx in (-450.0, -200.0, 150.0, 400.0) for dy in (-300.0, -50.0, 200.0)]
        salida_r = base / "respuestas"
        salida_r.mkdir()
        for f in cat["focos"]:
            RS.correr(f, lambda x, y: 100.0, malla, info["zona"], dia - pd.Timedelta(hours=18), recs, caso, salida_r, dia, 1)
        planta.desactivar()
    return SimpleNamespace(caso=caso, info=info, malla=malla, cat=cat, recs=recs, respuestas=salida_r, dia=dia)


def test_lo_que_escribe_preparar_caso_sale_de_la_planta(cadena):
    assert "(Planta X)" in (cadena.caso / "pronostico3d.dat").read_text().splitlines()[0]
    assert cadena.info["fuente"] == "GFS 0,25° (predicción)" and cadena.info["con_estaciones"] is False and cadena.info["dias_completos"] == ["2023-03-10"]
    assert VP.TITULO_GFS % "Y" == "GFS 0.25 -> pronostico 3D (Y)"


def test_el_plan_con_las_respuestas_da_lo_mismo_que_el_motor_con_ese_perfil(cadena, tmp_path, sin_imagenes):
    """La referencia externa de toda la cuenta: `simulacion.calcular_periodo` sin motor, frente a `dispersion.puffs` con la emisión del plan."""
    _planta(tmp_path / "planta", proyeccion={"zona_horaria": "Etc/UTC"})
    periodo = periodos.nuevo("queja", cadena.dia, 1)
    carpeta = periodos.dir_respuestas(periodo)
    shutil.copytree(cadena.respuestas, carpeta)
    xr_, yr_ = np.array([r[0] for r in cadena.recs]), np.array([r[1] for r in cadena.recs])
    np.savez_compressed(carpeta / "receptores.npz", x=xr_, y=yr_, cota=np.full(len(xr_), 100.0), clase=np.array(["a"] * len(xr_)))
    (carpeta / "meta.json").write_text(json.dumps({"formato": 1, "dia": "2023-03-10", "dias": 1, "serie": periodo["serie"], "receptores": len(xr_), "centro": list(geo.a_utm(LAT, LON)),
                                                   "focos": {f["id"]: {"huella": F.huella(f)} for f in cadena.cat["focos"]}, "etiquetas": []}), encoding="utf-8")
    perfil = [0.2 + 0.05 * h for h in range(24)]
    esc = E.nuevo(cadena.cat, "Plan")
    for f in cadena.cat["focos"]:
        E.poner_perfil(E.plan_foco(f, esc), [0], perfil)
    S.calcular_periodo(esc, cadena.cat, periodo)
    C = np.load(S.carpeta_resultados(esc, periodo) / "olor" / "penacho.npz")["C"]
    # directa: la misma emisión total, por m² en el área, con ese perfil por hora
    areas, volumenes = [], []
    for f in cadena.cat["focos"]:
        modelo, d, q0 = F.geometria(f, lambda x, y: 100.0)
        d.update(q={"OLOR": q0 * F.olor_ouE_s(f)}, perfil={"OLOR": perfil})
        (areas if modelo == "superficie" else volumenes).append(d)
    shutil.copy(cadena.caso / "viento3d.dat", tmp_path / "viento3d.dat")
    control_fuentes.escribir(tmp_path / "d.inp", cadena.malla, ZFACE, cadena.dia - pd.Timedelta(hours=18), 42, cadena.info["zona"], ["OLOR"], areas=areas, volumenes=volumenes, receptores=cadena.recs,
                             nombres={"viento": "viento3d.dat", "listado": "d.lst", "concentraciones": "d.dat"})
    ejecutar(tmp_path / "d.inp", verbose=False)
    fines, directa = salida.concentraciones(tmp_path / "d.dat", especie="OLOR")
    fines = pd.to_datetime(fines)
    directa = np.asarray(directa)[(fines >= cadena.dia) & (fines < cadena.dia + pd.Timedelta(days=1))]
    assert directa.shape == C.shape and directa.max() > 1e-3
    assert np.abs(C - directa).max() <= 1e-5 * directa.max()


def test_penacho_3d_reparte_los_receptores_y_los_recompone(cadena, tmp_path):
    """`_correr` lanza el motor en varios procesos: tienen que volver en su sitio, con altura sobre el suelo."""
    _planta(tmp_path / "planta", proyeccion={"zona_horaria": "Etc/UTC"})
    shutil.copy(cadena.caso / "viento3d.dat", tmp_path / P3D.VIENTO)
    f = cadena.cat["focos"][1]
    modelo, d, q0 = F.geometria(f, lambda x, y: 100.0)
    d.update(q={P3D.ESPECIE: q0 * 200.0}, perfil={P3D.ESPECIE: [1.0] * 24})
    salen = {"superficie": [], "punto": [], "volumen": [d]}
    recs = [(x, y, z, h) for x, y, z in cadena.recs[-6:] for h in (0.0, 30.0)]
    viento = {"malla": cadena.malla, "zona": cadena.info["zona"]}
    fines, C = P3D._correr(tmp_path, viento, cadena.dia, 3, salen, recs, "vol", None)
    control_fuentes.escribir(tmp_path / "u.inp", cadena.malla, ZFACE, cadena.dia, 3, cadena.info["zona"], [P3D.ESPECIE], volumenes=[d], receptores=recs,
                             nombres={"viento": P3D.VIENTO, "listado": "u.lst", "concentraciones": "u.dat"})
    ejecutar(tmp_path / "u.inp", verbose=False)
    unica = np.asarray(salida.concentraciones(tmp_path / "u.dat", especie=P3D.ESPECIE)[1], np.float32)
    assert C.shape == unica.shape and C.max() > 0 and np.array_equal(C, unica)


# ── normativa ──
def _col(clave, largo="anios", gas="NO2"):
    return next(c for c in N.columnas(gas, largo) if c["clave"] == clave)


def _dos_anios():
    fines = pd.date_range("2021-01-01 01:00", "2023-01-01 00:00", freq="h")
    anios = np.asarray(fines.year)
    return fines, np.flatnonzero(anios == 2021), np.flatnonzero(anios == 2022)


def test_la_19a_hora_del_peor_anio_y_la_25a_del_so2():
    fines, a21, a22 = _dos_anios()
    C = np.ones((len(fines), 3), np.float32)
    C[a21[:19], 0] = 300                       # 19 horas en un año: supera
    C[a21[:18], 1] = 300                       # 18 cada año: cumple, aunque sean 36 en dos años
    C[a22[:18], 1] = 300
    C[a22[:40], 2] = 500                       # 40 solo en 2022: cuenta ese
    v = N.estadistico(_col("norma_hora"), C, fines)
    assert v.tolist() == [300, 1, 500]
    assert _col("norma_hora")["limite"] == 200 and _col("norma_hora")["n"] == 18
    so2 = _col("norma_hora", gas="SO2")
    assert so2["limite"] == 350 and so2["n"] == 24
    C = np.ones((len(fines), 2), np.float32)
    C[a21[:25], 0] = 400                       # 25 horas: la 25.ª es alta
    C[a21[:24], 1] = 400                       # 24: las que admite
    assert N.estadistico(so2, C, fines).tolist() == [400, 1]


def test_30_horas_en_un_anio_se_ven_aunque_pasaran_por_un_percentil_de_dos_anios():
    fines, a21, _ = _dos_anios()
    D = np.ones((len(fines), 1), np.float32)
    D[a21[:30], 0] = 300
    juntos = np.percentile(D[:, 0], 100 * (1 - 18 / 8760))
    assert juntos == 1 and N.estadistico(_col("norma_hora"), D, fines)[0] == 300


def test_media_anual_cuarto_dia_y_ocho_horas():
    fines, a21, a22 = _dos_anios()
    C = np.zeros((len(fines), 1), np.float32)
    C[a21, 0], C[a22, 0] = 10, 30
    assert N.estadistico(_col("norma_anio"), C, fines)[0] == pytest.approx(30)
    C = np.zeros((len(fines), 1), np.float32)
    dias = fines.normalize()
    unicos = pd.DatetimeIndex(sorted(set(dias[a21])))[1:6]
    for k, d in enumerate(unicos):
        C[dias == d, 0] = 100 + 10 * k         # medias de 100 a 140: la 4.ª más alta es 110
    assert N.estadistico(_col("norma_dia", gas="SO2"), C, fines)[0] == pytest.approx(110)
    C = np.zeros((len(fines), 2), np.float32)
    C[100:108, 0], C[200:204, 1] = 800, 800
    assert N.estadistico(_col("norma_8h", gas="CO"), C, fines) == pytest.approx([800, 400])


def test_en_dias_no_se_cuenta_por_anio():
    fd = pd.date_range("2023-10-25 00:00", periods=72, freq="h")
    C = np.zeros((72, 2), np.float32)
    C[[5, 30, 60], 0] = [300, 250, 100]
    cols = {c["clave"]: c for c in N.columnas("NO2", "dias")}
    assert set(cols) == {"media", "maximo", "hora_max", "horas_sobre"}
    assert N.estadistico(cols["horas_sobre"], C, fd)[0] == 2 and N.estadistico(cols["hora_max"], C, fd).tolist() == [5, -1]
    assert [c["clave"] for c in N.columnas("olor", "dias")] == ["media", "maximo", "hora_max"]
    assert S.supera(cols["horas_sobre"], 2) and not S.supera(cols["media"], 1e9)


def test_sin_fichero_manda_la_plantilla_nacional_y_el_de_la_planta_la_sustituye():
    assert N.ruta() == N.PLANTILLA and N.PLANTILLA.parent == OPERACION
    d = N.datos()
    assert "RD 102/2011" in d["notas"] and d["gases"]["NO2"][0] == {"valor": 200, "promedio": "hora", "superaciones_anio": 18}
    assert d["gases"]["SO2"][0]["superaciones_anio"] == 24 and d["gases"]["CO"] == [{"valor": 10000, "promedio": "8h"}]
    assert N.criterios("olor") == [] and N.criterios("H2S") == []
    assert F.magnitud("NO2")["ref"] == 2.0 and F.magnitud("H2S")["ref"] == F.ug_por_ouE("H2S")
    propio = {"olor": {"percentil": 95}, "sin_limite": {"percentil": 90}, "gases": {"NO2": [{"valor": 100, "promedio": "hora", "superaciones_anio": 3}], "H2S": [{"valor": 7, "promedio": "dia"}]}}
    planta.NORMATIVA_JSON.write_text(json.dumps(propio), encoding="utf-8")
    assert N.ruta() == planta.NORMATIVA_JSON and N.criterios("SO2") == []
    cols = N.columnas("NO2", "anios")
    assert [c["clave"] for c in cols] == ["media", "maximo", "norma_hora"] and cols[2]["limite"] == 100 and cols[2]["n"] == 3
    assert F.magnitud("NO2")["ref"] == 1.0
    assert N.columnas("olor", "anios")[2]["titulo"] == "P95" and N.columnas("NH3", "anios")[2]["titulo"] == "P90"


# ── planes y hora oficial ──
def test_el_plan_va_en_hora_oficial_con_sus_dos_cambios_de_hora():
    perfil = [float(h) for h in range(24)]
    pf = {"plan": "diario", "perfiles": [perfil], "dias": [0]}
    # marzo: de 01 a 02 UTC es la hora que no existe (de las 3 a las 4 oficiales)
    i = pd.date_range("2023-03-26 00:00", periods=4, freq="h")
    assert E.factores(pf, i).tolist() == [1.0, 3.0, 4.0, 5.0]
    # octubre: las 2 oficiales salen dos veces
    i = pd.date_range("2023-10-29 00:00", periods=3, freq="h")
    assert E.factores(pf, i).tolist() == [2.0, 2.0, 3.0]


def test_el_dia_del_plan_tambien_es_el_oficial_y_la_zona_es_de_la_planta(tmp_path):
    sem = {"plan": "semanal", "perfiles": [[1.0] * 24, [0.0] * 24], "dias": [0, 1, 1, 1, 1, 1, 1]}      # solo el lunes
    i = pd.DatetimeIndex(["2023-01-01 22:00", "2023-01-01 23:00", "2023-01-02 22:00", "2023-01-02 23:00"])       # 1 de enero, domingo; UTC + 1
    assert E.factores(sem, i).tolist() == [0.0, 1.0, 1.0, 0.0]
    mens = {"plan": "mensual", "perfiles": [[1.0] * 24, [0.0] * 24], "dias": [0] + [1] * 30}             # solo el día 1
    assert E.factores(mens, pd.DatetimeIndex(["2023-03-31 22:00", "2023-03-31 21:00"])).tolist() == [1.0, 0.0]    # UTC + 2 en verano
    _planta(tmp_path / "otra", proyeccion={"zona_horaria": "America/New_York"})
    pf = {"plan": "diario", "perfiles": [[float(h) for h in range(24)]], "dias": [0]}
    assert E.zona() == "America/New_York" and E.factores(pf, pd.DatetimeIndex(["2023-01-10 13:00"])).tolist() == [8.0]
    assert E.horas_del_plan({"mes": "2023-01", "focos": {"F": {"plan": "mensual"}}}, pd.DatetimeIndex(["2023-02-01 04:00", "2023-02-01 05:00"])).tolist() == [True, False]


def test_sin_zona_horaria_el_error_dice_cual(tmp_path):
    datos = json.loads(json.dumps(JSON_PLANTA))
    del datos["proyeccion"]["zona_horaria"]
    (tmp_path / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
    planta.activar(tmp_path)
    with pytest.raises(ValueError, match=r"proyeccion\.zona_horaria"):
        E.factores({"plan": "diario", "perfiles": [[1.0] * 24], "dias": [0]}, pd.DatetimeIndex(["2023-01-10"]))


def test_formato_de_un_plan_se_guarda_y_se_relee():
    f = _foco("F01")
    cat = {"focos": [f]}
    esc = E.nuevo(cat, "Volteos por la tarde")
    pf = E.plan_foco(f, esc)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, [0, 2], [0.5] * 24)
    assert pf["dias"] == [1, 0, 1, 0, 0, 0, 0] and len(pf["perfiles"]) == 2 and E.nivel_medio(pf) == pytest.approx((2 * 0.5 + 5) / 7)
    ruta = E.guardar(esc)
    assert ruta == planta.DIR_ESCENARIOS / "volteos_por_la_tarde.json" and E.cargar(ruta)["focos"] == esc["focos"]
    assert [n for n, _, _ in E.listar()] == ["Volteos por la tarde"]
    with pytest.raises(ValueError, match="Base"):
        E.guardar(E.base(cat))
    E.cambiar_plan(pf, "mensual", "2023-05")                                    # el 1 de mayo fue lunes
    assert len(pf["dias"]) == 31 and E.perfil_dia(pf, 0) == [0.5] * 24 and E.perfil_dia(pf, 1) == [1.0] * 24
    ruta.write_text(json.dumps({"formato": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="formato"):
        E.cargar(ruta)


# ── focos y unidades ──
def _punto(t_c, gases=(), olor=None, **salida_):
    return {"modelo": "punto", "salida": dict(diametro_m=0.5, temperatura_C=t_c, **salida_), "gases": list(gases), "olor": olor or {}}


def test_caudal_a_la_temperatura_de_salida_gases_ideales_a_mano():
    # 50 ppm de H2S a 35 °C con 300 m³/h reales
    T = 35 + 273.15
    f = _punto(35, [{"gas": "H2S", "valor": 50, "unidad": "ppm"}], caudal_m3_h=300)
    assert F.gases_g_s(f)["H2S"] == pytest.approx(50e-6 * P_ATM * 34.08 / (R_GAS * T) * (300 / 3600), rel=2e-3)
    # con el mismo caudal real, a 25 °C daría de más: T / 298 K
    caliente = _punto(400, [{"gas": "H2S", "valor": 1, "unidad": "ppm"}], caudal_m3_h=1000)
    a_25 = 1 * 34.08 / F.VM_25C * 1000 * (1000 / 3600) * 1e-6
    assert a_25 / F.gases_g_s(caliente)["H2S"] == pytest.approx((400 + 273.15) / 298.15, rel=2e-3)
    # el mismo caudal normal a cualquier temperatura: la misma masa, la de los gases ideales a 0 °C
    vals = [F.gases_g_s(_punto(t, [{"gas": "NOx", "valor": 10, "unidad": "ppm"}], caudal_Nm3_h=1000))["NOx"] for t in (25, 127, 400, 800)]
    assert max(vals) / min(vals) - 1 < 1e-12 and vals[0] == pytest.approx(10e-6 * P_ATM * 46.01 / (R_GAS * 273.15) * (1000 / 3600), rel=2e-3)
    assert F.caudal_m3_s(_punto(180, caudal_Nm3_h=1000)) == pytest.approx(1000 / 3600 * 453.15 / 273.15, rel=1e-9)


def test_mg_nm3_y_olor_a_20_grados():
    assert F.gases_g_s(_punto(180, [{"gas": "NOx", "valor": 120, "unidad": "mg/Nm3"}], caudal_Nm3_h=3600))["NOx"] == pytest.approx(0.120, rel=1e-9)
    assert F.gases_g_s(_punto(180, [{"gas": "NOx", "valor": 120, "unidad": "mg/Nm3"}], velocidad_m_s=15))["NOx"] == pytest.approx(120e-3 * (15 * np.pi * 0.25 ** 2) * 273.15 / 453.15, rel=1e-9)
    assert F.olor_ouE_s(_punto(20, olor={"valor": 500, "unidad": "ou_E/m3"}, caudal_m3_h=3600)) == pytest.approx(500.0)
    assert F.olor_ouE_s(_punto(180, olor={"valor": 500, "unidad": "ou_E/m3"}, caudal_m3_h=3600)) == pytest.approx(500 * 293.15 / 453.15)
    assert F.gases_g_s(_punto(20, [{"gas": "H2S", "valor": 1.0, "unidad": "ppm"}])) == {}       # sin caudal, no hay masa


def test_olor_estimado_con_el_gas_dominante_en_el_foco():
    gases = [{"gas": "H2S", "valor": 1.0, "unidad": "g/s"}, {"gas": "NH3", "valor": 1.0, "unidad": "g/s"}]
    f = _punto(20, gases)
    assert F.ug_por_ouE("H2S") == pytest.approx(0.41 * 34.08 / 24.45)
    assert F.gas_dominante(f)[1] == "H2S" and F.olor_ouE_s(f) == pytest.approx(1e6 / F.ug_por_ouE("H2S"))     # máx(gas / umbral): no la suma
    assert F.olor_ouE_s(_punto(20, gases, {"valor": 5, "unidad": "ou_E/s"})) == 5                              # manda la olfatometría
    sin_umbral = _punto(20, [{"gas": "NOx", "valor": 1.0, "unidad": "g/s"}, {"gas": "CO", "valor": 1.0, "unidad": "g/s"}])
    assert F.olor_ouE_s(sin_umbral) is None and F.emision(sin_umbral, "CO") == pytest.approx(1e6)
    assert [m["clave"] for m in F.magnitudes({"focos": [f, sin_umbral]})] == ["olor", "H2S", "NH3", "NOx", "CO"]


def test_las_areas_van_por_m2():
    pol = {"modelo": "superficie", "ubicacion": {"poligono": [[0, 0], [40, 0], [40, 25], [0, 25]]}, "altura_m": 2.0, "olor": {"valor": 3.0, "unidad": "ou_E/(s·m2)"}, "gases": [{"gas": "NH3", "valor": 2.0, "unidad": "mg/(s·m2)"}]}
    assert F.area_m2(pol) == 1000.0 and F.olor_ouE_s(pol) == 3000.0 and F.gases_g_s(pol)["NH3"] == pytest.approx(2.0)
    assert F.por_m2(pol, F.olor_ouE_s(pol)) == 3.0 and F.por_m2(pol, None) is None
    modelo, d, q0 = F.geometria(dict(pol, id="A"), lambda x, y: 7.0)
    assert (modelo, q0, d["cota"]) == ("superficie", 1 / 1000.0, 7.0)           # sin esto, ×1000
    d = RS.fuente(dict(pol, id="A"), lambda x, y: 7.0)[1]
    assert d["q"]["H05"] == pytest.approx(1 / 1000.0) and d["perfil"]["H05"][5] == 1.0 and sum(d["perfil"]["H05"]) == 1.0 and len(d["q"]) == 24


def test_perfil_y_eventos():
    h = {"funcionamiento": {"modo": "horario", "horas": "8-16, 20", "fuera_pct": 10}}
    assert F.horas("8-16, 20") == [8, 9, 10, 11, 12, 13, 14, 15, 20] and F.horas("22-2") == [0, 1, 22, 23]
    p = F.perfil(h)
    assert p[8] == 1.0 and p[16] == pytest.approx(0.1) and p[20] == 1.0 and len(p) == 24
    assert F.fraccion_eventos({"funcionamiento": {"modo": "eventos", "veces_mes": 2, "duracion_min": 30}}) == pytest.approx(60 / (365.25 / 12 * 24 * 60))
    assert F.fraccion_eventos({"funcionamiento": {"modo": "eventos"}}) is None and F.fraccion_eventos({}) == 1.0
    with pytest.raises(ValueError, match="no se entiende"):
        F.horas("mañana")


def test_tipos_genericos_y_de_la_planta():
    assert len(F.TIPOS) == 15 and "tolva" not in F.TIPOS and "tolva" in F.tipos() and F.tipos()["tolva"] == ("Tolva", ("punto", "volumen"), "continuo")
    cat = F.vacio()
    assert cat["epsg"] == EPSG and cat["planta"] == "Prueba"
    assert F.nuevo(cat, "tolva")["modelo"] == "punto" and F.nombre_tipo({"tipo": "tolva"}) == "Tolva" and F.nombre_tipo({"tipo": "pila"}) == "Pila o hilera de compostaje"
    with pytest.raises(ValueError, match="no previsto"):
        F.nuevo(cat, "tolva", "superficie")


def test_el_catalogo_se_guarda_y_se_relee_y_su_huella_solo_mira_lo_que_recalcula():
    cat = F.cargar()                                                            # sin fichero: vacío
    assert cat["focos"] == []
    f = F.nuevo(cat, "lavador")
    cat["focos"].append(f)
    assert F.guardar(cat) == planta.FOCOS_JSON and F.cargar()["focos"] == cat["focos"]
    d = json.loads(planta.FOCOS_JSON.read_text(encoding="utf-8"))
    planta.FOCOS_JSON.write_text(json.dumps(dict(d, epsg="EPSG:25830")), encoding="utf-8")
    with pytest.raises(ValueError, match="25830"):
        F.cargar()
    assert F.huella(f) == F.huella(dict(f, olor={"valor": 9}, observaciones="x")) and F.huella(f) != F.huella(dict(f, altura_m=9.0))
    assert "altura de emisión" in F.pendientes(f) and "emisión de olor o de gases" in F.pendientes(f)


# ── firma: lo guardado tiene que seguir valiendo ──
CAT_FIRMA = {"focos": [{"id": "F01", "nombre": "Uno", "tipo": "biofiltro", "modelo": "superficie", "ubicacion": {"poligono": [[0, 0], [10, 0], [10, 10]]}, "altura_m": 2.0,
                        "funcionamiento": {"modo": "continuo"}, "olor": {"valor": 5.0, "unidad": "ou_E/(s·m2)"}, "gases": []}]}
ESC_FIRMA = {"formato": 2, "nombre": "X", "mes": None, "focos": {"F01": {"plan": "diario", "perfiles": [[1.0] * 24], "dias": [0]}}}
PERIODO_FIRMA = {"modo": "queja", "ini": "2023-03-10", "dias": 2, "serie": "queja_20230310_2d"}


def test_la_firma_da_el_valor_de_antes_de_llevarla_a_teodors():
    # con el código original y estos datos, sin cambiar nada de lo que se hash: si estos valores cambian, se invalidan todas las simulaciones guardadas
    assert S.firma(ESC_FIRMA, CAT_FIRMA) == "e5c2758928cbebbb47c9c1581d8ba35ca0d685b0"
    assert S.firma(ESC_FIRMA, CAT_FIRMA, PERIODO_FIRMA) == "8202b855a0df6fab9a1dd9bb9f9cbbc19f075d0f"


def test_la_firma_cambia_con_plan_focos_periodo_y_normativa_y_sin_ellos_no():
    a = S.firma(ESC_FIRMA, CAT_FIRMA, PERIODO_FIRMA)
    assert a == S.firma(json.loads(json.dumps(dict(ESC_FIRMA, nombre="Otro nombre"))), json.loads(json.dumps(CAT_FIRMA)), dict(PERIODO_FIRMA))
    otro = json.loads(json.dumps(ESC_FIRMA))
    otro["focos"]["F01"]["perfiles"] = [[0.5] * 24]
    assert S.firma(otro, CAT_FIRMA, PERIODO_FIRMA) != a
    assert S.firma(dict(ESC_FIRMA, mes="2023-01"), CAT_FIRMA, PERIODO_FIRMA) != a
    cat = json.loads(json.dumps(CAT_FIRMA))
    cat["focos"][0]["olor"]["valor"] = 6.0
    assert S.firma(ESC_FIRMA, cat, PERIODO_FIRMA) != a
    assert S.firma(ESC_FIRMA, CAT_FIRMA, dict(PERIODO_FIRMA, dias=3)) != a and S.firma(ESC_FIRMA, CAT_FIRMA) != a
    d = N.datos()
    d["gases"]["NO2"][0]["valor"] = 150
    planta.NORMATIVA_JSON.write_text(json.dumps(d), encoding="utf-8")
    assert S.firma(ESC_FIRMA, CAT_FIRMA, PERIODO_FIRMA) != a
    d["gases"]["NO2"][0]["valor"] = 200
    d["notas"] = "otra nota"
    planta.NORMATIVA_JSON.write_text(json.dumps(d), encoding="utf-8")
    assert S.firma(ESC_FIRMA, CAT_FIRMA, PERIODO_FIRMA) == a                    # solo cuentan los gases


def test_carpeta_de_resultados_rutas_de_datos():
    assert S.carpeta_resultados({"nombre": "Base"}) == planta.DATOS / "resultados_planes" / "reanalisis" / "5_anios" / "base"
    assert S.carpeta_resultados({"nombre": "Volteos de día"}, PERIODO_FIRMA) == planta.DATOS / "resultados_planes" / "queja" / "20230310_2d" / "volteos_de_dia"


# ── periodos ──
def test_nombres_de_serie_e_inicio_de_la_prediccion():
    p = periodos.nuevo("queja", "2023-03-10", 3)
    assert p == {"modo": "queja", "ini": "2023-03-10", "dias": 3, "serie": "queja_20230310_3d"}
    assert periodos.nuevo("prediccion", pd.Timestamp("2023-03-10"), 2)["serie"] == "prediccion_20230310_2d" and periodos.nuevo("reanalisis", "2023-03-10", 1, "serie_b")["serie"] == "serie_b"
    # la ejecución de las 00 UTC tarda unas 5 h: hasta las 6 UTC, la del día anterior
    assert periodos.inicio_prediccion(pd.Timestamp("2023-03-10 05:59")) == pd.Timestamp("2023-03-09")
    assert periodos.inicio_prediccion(pd.Timestamp("2023-03-10 06:00")) == pd.Timestamp("2023-03-10")
    assert periodos.etiqueta(periodos.nuevo("queja", "2023-03-10", 1)) == "10/03/2023" and periodos.etiqueta(p) == "10-12/03/2023"
    assert periodos.etiqueta(periodos.nuevo("queja", "2023-03-30", 3)) == "30/03-01/04/2023"


def test_carpetas_de_las_respuestas_y_lo_que_ya_esta():
    q = periodos.nuevo("queja", "2023-03-10", 1)
    r = periodos.nuevo("reanalisis", "2023-03-10", 1, "serie_b")
    assert periodos.dir_respuestas(q) == planta.DATOS / "respuestas" / "queja_20230310_1d"
    assert periodos.dir_respuestas(r) == planta.DATOS / "respuestas" / "serie_b_20230310"
    assert not periodos.listo(r) and periodos.fuente(q) == {} and not S.disponible() and periodos.dias_reanalisis() == {}
    _guarda_respuestas([_foco("F01")], lambda i, t, r_: 0.0)
    _guarda_respuestas([_foco("F01")], lambda i, t, r_: 0.0, carpeta=periodos.dir_respuestas(q), serie=q["serie"])
    assert periodos.listo(r) and S.dir_respuestas() == periodos.dir_respuestas(r)   # un episodio no cuenta como reanálisis
    assert periodos.dias_reanalisis() == {"2023-03-10": "serie_b"}
    shutil.rmtree(periodos.dir_respuestas(r))
    with pytest.raises(RuntimeError, match="Aún no hay respuestas"):
        S.calcular(E.nuevo({"focos": []}, "x"), {"focos": []})


def test_preparar_lanza_las_dos_tareas_con_sus_argumentos(monkeypatch):
    llamadas = []

    def falso(tarea, args, cuenta, cancelado):
        llamadas.append((tarea, [str(a) for a in args]))
        cuenta("1) terreno\n")
    monkeypatch.setattr(periodos, "_lanzar", falso)
    avance = []
    periodos.preparar(periodos.nuevo("prediccion", "2023-03-10", 2), lambda p, m: avance.append(p))
    assert [t for t, _ in llamadas] == ["viento_periodo", "respuestas"]
    assert "--prediccion" in llamadas[0][1] and "--prediccion" not in llamadas[1][1] and llamadas[1][1][:4] == ["--dia", "2023-03-10", "--dias", "2"]
    assert avance[-1] == 100


def test_un_hijo_encuentra_la_planta_y_los_datos():
    """`python -m teodors.operacion.X` no sabe de qué proyecto viene: hereda la planta por TEODORS_PLANTA y sus datos por <prefijo>_DATOS."""
    lineas = []
    periodos._lanzar("viento3d_series", ["--anios"], lineas.append, None)
    texto = "".join(lineas)
    assert f"datos en {planta.DATOS}" in texto and "0 meses pendientes" in texto
    assert list(planta.DIR_LOGS.glob("prueba_*.log"))                           # su registro, en la carpeta de esta planta


def test_si_una_tarea_falla_o_se_cancela_lo_dice():
    with pytest.raises(RuntimeError, match=r"viento3d_series\.py falló"):
        periodos._lanzar("viento3d_series", ["--no-existe"], lambda l: None, None)
    with pytest.raises(RuntimeError, match="cancelado"):
        periodos._lanzar("viento3d_series", ["--anios"], lambda l: None, lambda: True)


# ── imágenes y viento en el mapa ──
def _malla_imagen(tmp_path, escala="turbo"):
    x0, y0 = geo.a_utm(LAT, LON)
    x, y = x0 + np.arange(40) * 50.0, y0 + np.arange(30) * 50.0
    campo = np.zeros((30, 40))
    campo[10:20, 10:30] = 50.0
    ruta = tmp_path / f"{escala}.png"
    return ruta, PM.pintar(campo, x, y, 50.0, 0.1, 1000.0, ruta, escala=escala)


def test_pintar_da_siempre_los_mismos_bytes_y_el_gris_es_el_nivel():
    from PIL import Image
    d = planta.LOCAL
    d.mkdir(parents=True)
    ruta, lim = _malla_imagen(d)
    a = ruta.read_bytes()
    assert _malla_imagen(d)[1] == lim and ruta.read_bytes() == a
    gris, _ = _malla_imagen(d, None)
    with Image.open(gris) as im:
        assert im.mode == "LA"
        L, A = np.asarray(im).T
    assert A.max() > 0 and A[0, 0] == 0 and L[0, 0] == 0                        # transparente por debajo de vmin
    f = np.log10(50.0 / 0.1) / 4
    assert L[A > 0].max() == pytest.approx(round(255 * f), abs=1)               # 50 en la escala de 0,1 a 1000, 4 décadas
    with Image.open(ruta) as im:
        assert im.mode == "RGBA"
    assert lim[0][0] < LAT + 0.02 and lim[1][1] > LON                           # en su sitio


def test_leyenda_y_tiempo():
    h = PM.leyenda_html({"vmin": 0.1, "decadas": 4, "unidad": "ou_E/m³", "escala": "olor"}, "Media")
    assert "<h4>Media (ou_E/m³)</h4>" in h and "var(--escala-olor)" in h and all(f"<span>{v}</span>" in h for v in ("0,1", "1", "10", "100", "1000"))
    assert PM.icono_tiempo(100, 0.1, 0.5)[0] == "d_rain" and PM.icono_tiempo(0, 0.9, 0)[0] == "n_cloud" and PM.icono_tiempo(100, 0, 0)[1] == "Despejado · día"
    assert PM.tiempo_dia("2023-03-10", "serie_b") == {}
    d = planta.DIR_VIENTO3D / "serie_b" / "202303"
    d.mkdir(parents=True)
    meteo = [{"hora": f"2023-03-10 {h:02d}:00", "ws": 1.0 + h, "t": 10.0 - h, "icono": "d_clear"} for h in range(24)]
    (d / "meteo.json").write_text(json.dumps(meteo), encoding="utf-8")
    t = PM.tiempo_dia("2023-03-10", "serie_b")
    assert (t["wsmax"], t["tmin"], t["tmax"]) == (24.0, -13.0, 10.0) and sorted(t["iconos"]) == ["d_clear", "d_cloud", "d_rain", "n_clear", "n_cloud", "n_rain"]
    assert "<svg" in t["termometro"]
    assert PM.tiempo_dia("2023-03-10", "serie_b", 2) == {}                      # no están las 48 horas


def _serie_viento(serie):
    base = planta.DIR_VIENTO3D / serie
    cab, horas = fichero_viento.leer(VIENTO_24H)
    (base / "cmz").mkdir(parents=True)
    fecha = pd.Timestamp(horas[0].ndathr // 100000, 1, 1) + pd.Timedelta(days=(horas[0].ndathr // 100) % 1000 - 1)
    almacen.comprimir(VIENTO_24H, base / "cmz" / f"{fecha:%Y%m}.cmz", cab.nx, cab.ny)
    (base / f"{fecha:%Y%m}").mkdir()
    (base / f"{fecha:%Y%m}" / "caso.json").write_text(json.dumps({"celda_m": cab.dgrid, "ext": [cab.xorig, 0, cab.yorig, 0], "dias_completos": [f"{fecha:%Y-%m-%d}"]}), encoding="utf-8")
    return cab, fecha


def test_el_viento_del_mapa_es_el_del_fichero_y_las_series_son_de_la_planta():
    assert VM.preferidas() == ("serie_a", "serie_b") and VM.serie_defecto() == "serie_a" and VM.titulos() == {"serie_a": "Título A"}
    assert VM.serie_disponible() is None and VM.meses() == [] and VM.dia_inicial("serie_b") is None and VM.rango_dias("serie_b") is None
    cab, fecha = _serie_viento("serie_b")
    assert VM.serie_disponible() == "serie_b" and VM.meses("serie_b") == [(fecha.year, fecha.month)] and VM.dia_inicial("serie_b") == fecha
    assert VM.rango_dias("serie_b") == (fecha, fecha)
    d = VM.datos_dia(fecha, "serie_b")
    _, u = almacen.leer_campo(planta.DIR_VIENTO3D / "serie_b" / "cmz" / f"{fecha:%Y%m}.cmz", "U-LEV  1")
    decodificado = np.frombuffer(base64.b64decode(d["u"][0]), "<i2").reshape(cab.ny, cab.nx)
    assert (d["nx"], d["ny"], d["dg"], d["escala"]) == (cab.nx, cab.ny, cab.dgrid, 0.01) and d["titulo"] == "serie_b"
    assert np.array_equal(decodificado, np.round(u[0] * 100).astype("<i2")) and d["horas"][0][:10] == f"{fecha:%Y-%m-%d}"
    with pytest.raises(ValueError, match="sin datos"):
        VM.datos_dia(fecha.replace(day=28 if fecha.day < 20 else 1), "serie_b")


def test_la_biblioteca_es_la_de_la_planta(tmp_path):
    assert VM.biblioteca() is None and VM.datos_local() is None                 # sin el bloque
    VM.datos_local.cache_clear()
    _planta(tmp_path / "otra", viento_local={"biblioteca": "lib.npz"})
    ruta = planta.PLANTA / "lib.npz"
    assert VM.biblioteca() == ruta and VM.datos_local() is None                 # sin el fichero
    VM.datos_local.cache_clear()
    x, y = geo.a_utm(LAT, LON)
    np.savez(ruta, u=np.zeros((36, 4, 5), "<i2"), v=np.ones((36, 4, 5), "<i2"), dx=2.5, x0=x, y0=y, cx=x, cy=y, cx2=x + 10, cy2=y, radio=20.0, radio_borde=30.0, paso=10.0, escala=0.001, solido=-32768)
    d = VM.datos_local()
    assert (d["nx"], d["ny"], d["dx"], d["solido"]) == (5, 4, 2.5, -32768) and len(d["u"]) == 36
    assert d["esquinas"]["c00"] == pytest.approx(geo.a_geo(x, y), abs=1e-8)
    assert VM.datos_local() is d                                                # una sola copia en memoria


def test_ejemplo_va_a_la_carpeta_de_la_planta():
    assert ejemplo_configuracion.carpeta_ejemplo() == planta.PLANTA / "su_ejemplo"


# ── penacho en 3D, sin motor ──
def test_3d_terreno_rotulos_y_lo_guardado(tmp_path):
    xc, yc = geo.a_utm(LAT, LON)
    t = P3D._terreno_vista((xc, yc), lambda x, y: 12.5)
    assert t["n"] == 17 and t["semilado"] == 400.0 and t["paso"] == 50.0 and len(base64.b64decode(t["z"])) == 2 * 17 * 17
    x, y = np.array([xc + 100.0, xc + 9000.0, xc + 50.0]), np.array([yc, yc, yc + 50.0])
    meta = {"etiquetas": [{"i": 0, "nombre": "Cerca", "clase": "nucleo"}, {"i": 1, "nombre": "Lejos", "clase": "nucleo"}, {"i": 2, "nombre": "Una vivienda", "clase": "vivienda"}]}
    r = P3D._rotulos(meta, x, y, np.array([1.0, 2.0, 3.0]), (xc, yc), lambda a, b: 9.0)
    assert [c["t"] for c in r] == ["Planta", "Pueblo X", "Cerca"]
    gx, gy = geo.a_utm(LAT, LON + 0.002)
    assert r[1]["x"] == pytest.approx(gx - xc, abs=0.5) and r[1]["z"] == 9.0 and r[2]["x"] == 100.0
    res = {"firma": "abc", "nombre": "Plan", "periodo": PERIODO_FIRMA, "orden": ["olor"], "magnitudes": {"olor": {"nombre": "Olor"}}}
    ruta_res = S.carpeta_resultados({"nombre": "Plan"}, PERIODO_FIRMA) / "resultado.json"
    ruta_res.parent.mkdir(parents=True)
    ruta_res.write_text(json.dumps(res), encoding="utf-8")
    assert P3D.firma(res, "olor") != P3D.firma(res, "H2S") and P3D.abrir(ruta_res, "olor") is None
    assert P3D.lista()[0]["magnitudes"] == [{"clave": "olor", "nombre": "Olor", "listo": False}] and "Episodio" in P3D.lista()[0]["texto"]
    guardado = P3D.ruta_guardada(res, "olor")
    guardado.parent.mkdir(parents=True)
    guardado.write_text(json.dumps({"firma": P3D.firma(res, "olor"), "horas_utc": ["2023-03-10 00:00"]}), encoding="utf-8")
    abierto = P3D.abrir(ruta_res, "olor")
    assert abierto["horas"] == ["2023-03-10 00:00"] and abierto["datos"]["firma"] == P3D.firma(res, "olor") and P3D.lista()[0]["magnitudes"][0]["listo"]


def test_3d_los_factores_son_los_del_plan_ese_dia():
    f, g = _foco("F01"), _foco("F02", funcionamiento={"modo": "eventos", "veces_mes": 1, "duracion_min": 60})
    cat = {"focos": [f, g]}
    esc = E.nuevo(cat, "X")
    pf = E.plan_foco(f, esc)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, [4], [0.25] * 24)                                        # viernes
    fac = P3D._factores(esc, cat, "2023-03-10")                                 # viernes
    assert fac["F01"][12] == 0.25 and fac["F01"][23] == 1.0                     # las 23 UTC ya son sábado en hora oficial
    assert fac["F02"][0] == pytest.approx(F.fraccion_eventos(g))


@pytest.mark.skipif(find_spec("pyvista") is None, reason="sin pyvista: es opcional")
def test_3d_superficies_con_pyvista():
    xs, ys = np.arange(5) * 100.0, np.arange(4) * 100.0
    malla = P3D._malla_base(xs, ys, lambda x, y: 50.0, 200.0, 100.0)
    Z = np.array(P3D.ALTURAS, float)
    campo = np.exp(-Z[:, None, None] / 20.0) * 10.0 * np.ones((len(Z), 4, 5))
    s = P3D._superficies(campo.astype(np.float32), malla, [1.0, 1000.0])
    assert s[1] is None and s[0]["n"] > 0 and not s[0]["i32"]
    p = np.frombuffer(base64.b64decode(s[0]["p"]), "<i2").reshape(-1, 3) * P3D.ESCALA_M
    assert p[:, 2].max() - 50.0 == pytest.approx(20.0 * np.log(10.0), abs=5.0)  # C = 1 a esa altura, interpolando en log entre alturas


# ── lo que no puede pasar al importar, y lo que tiene que ir con el paquete ──
FICHEROS = sorted(f.name for f in OPERACION.glob("*.py"))


def _leidos(nodos):
    return {n.id for nodo in nodos for n in ast.walk(nodo) if isinstance(n, ast.Name)}


@pytest.mark.parametrize("fichero", FICHEROS)
def test_nada_lee_la_planta_al_importar_ni_en_un_valor_por_defecto(fichero):
    arbol = ast.parse((OPERACION / fichero).read_text(encoding="utf-8"))
    fuera = [n for n in arbol.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))]
    assert not _leidos(fuera) & {"config", "planta", "geo"}
    defectos = [d for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) for d in n.args.defaults + [k for k in n.args.kw_defaults if k]]
    assert not _leidos(defectos) & {"config", "planta", "geo"}


def test_al_importar_no_hay_planta_ni_interfaz_ni_se_escribe_nada(tmp_path):
    env = procesos.entorno()
    env.pop(planta.ENV_PLANTA, None)
    mods = ", ".join("teodors.operacion." + f[:-3] for f in FICHEROS if f != "__init__.py")
    codigo = f"import sys\nimport {mods}\nfrom teodors import planta\nprint(planta._activa, 'PySide6' in sys.modules, 'folium' in sys.modules, 'pyvista' in sys.modules)"
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", cwd=vacia, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "None False False False" and list(vacia.iterdir()) == []


def test_ayuda_de_cada_tarea_sin_planta(tmp_path):
    env = procesos.entorno()
    env.pop(planta.ENV_PLANTA, None)
    for tarea in ("respuestas", "viento3d_series"):
        r = subprocess.run([sys.executable, "-m", f"teodors.operacion.{tarea}", "--help"], capture_output=True, text=True, encoding="utf-8", cwd=tmp_path, env=env)
        assert r.returncode == 0 and "usage" in r.stdout, (tarea, r.stderr)


def test_preparacion_no_sabe_de_focos():
    assert not hasattr(control_fuentes, "geometria")
    texto = (RAIZ / "core" / "preparacion" / "puffs" / "control_fuentes.py").read_text(encoding="utf-8")
    assert "operacion" not in texto


def test_el_paquete_instalado_lleva_sus_recursos():
    py = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"]
    assert "teodors.operacion" in py["packages"]
    patrones = py["package-data"]["teodors.operacion"]
    ficheros = [f.relative_to(OPERACION) for f in OPERACION.rglob("*") if f.is_file() and f.suffix not in (".py", ".pyc", ".md")]
    assert {"normativa_nacional.json", "termometro.svg", "d_clear.svg"} <= {f.name for f in ficheros}
    for f in ficheros:
        assert any(f.match(p) for p in patrones), f


def test_readme_con_sus_ficheros():
    tabla = (OPERACION / "README.md").read_text(encoding="utf-8").split("## Ficheros")[1]
    for f in FICHEROS + ["normativa_nacional.json", "recursos/iconos/"]:
        assert f"`{f}`" in tabla


def test_la_plantilla_no_lleva_nada_de_una_planta():
    texto = (OPERACION / "normativa_nacional.json").read_text(encoding="utf-8")
    assert not re.search(r"Galera|ENCE|docs/|usuario", texto)
