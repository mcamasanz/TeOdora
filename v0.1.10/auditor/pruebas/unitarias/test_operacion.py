# -*- coding: utf-8 -*-
"""operacion · de los focos y los planes a los resultados, SIN RED y con una planta inventada a propósito. Las cuentas se comprueban a mano, con series hechas para que
el resultado se sepa de antemano, con la ley de los gases ideales y, en la cuenta entera, frente a una corrida directa del motor. Comprueban el código: los focos son
inventados, y no dicen nada de ninguna planta."""
import ast
import base64
import json
import os
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
from teodors.operacion import serie_respuestas as SR  # noqa: E402
from teodors.operacion import estela as ES  # noqa: E402
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


def _guarda_respuestas(focos, valor, nt=24, carpeta=None, serie="serie_b", dia="2023-03-10"):
    """R[h, t, r] = 0 salvo R[H − 1, t, r] = valor(t, r), con H la hora del fin de t: lo emitido en esa hora solo llega en esa hora, y C(t, r) = Q · F(t) · valor(t, r)."""
    carpeta = carpeta or planta.DATOS / "respuestas" / f"{serie}_{dia.replace('-', '')}"
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
        "formato": 1, "dia": dia, "dias": 1, "serie": serie, "receptores": len(x), "centro": list(geo.a_utm(LAT, LON)), "focos": {f["id"]: {"huella": F.huella(f)} for f in focos},
        "etiquetas": [{"i": 1, "nombre": "Vecino", "clase": "nombrado"}, {"i": 5, "nombre": "Pueblo", "clase": "nucleo", "familia": "residencial"}]}), encoding="utf-8")
    return x, y


SERIE_INI, SERIE_FIN = "2023-01-01", "2023-02-28"


def _guarda_serie(focos, valor, ini=SERIE_INI, fin=SERIE_FIN, serie="serie_a"):
    """La serie del reanálisis en planta.DIR_DISPERSION (`serie_respuestas.importar`): cada día de `ini` a `fin`, las mismas
    respuestas de `_guarda_respuestas`, en su carpeta de un día."""
    origen = planta.DATOS / "respuestas"
    dias = pd.date_range(ini, fin)
    primero = origen / f"{serie}_{dias[0]:%Y%m%d}"
    x, y = _guarda_respuestas(focos, valor, carpeta=primero, serie=serie, dia=f"{dias[0]:%Y-%m-%d}")
    meta = json.loads((primero / "meta.json").read_text(encoding="utf-8"))
    for d in dias[1:]:
        c = origen / f"{serie}_{d:%Y%m%d}"
        shutil.copytree(primero, c, dirs_exist_ok=True)
        (c / "meta.json").write_text(json.dumps(dict(meta, dia=f"{d:%Y-%m-%d}")), encoding="utf-8")
    SR.importar(planta.DIR_DISPERSION, SR._origenes(origen, serie))
    return x, y


def _horas_serie(ini=SERIE_INI, fin=SERIE_FIN):
    """Fin de cada hora de la serie, como las respuestas: de las 00 a las 23 UTC de cada día."""
    return pd.date_range(f"{ini} 00:00", f"{fin} 23:00", freq="h")


def _campos(esc, clave="olor", periodo=None):
    with np.load(S.carpeta_resultados(esc, periodo) / clave / "resumen.npz") as z:
        return {c: z[c] for c in z.files if c not in ("x", "y", "clase")}


# ── la serie del reanálisis ──
def test_serie_respuestas_error_acotado_y_el_maximo_exacto():
    rng = np.random.default_rng(3)
    R = np.where(rng.random((24, 24, 50)) < 0.3, 10 ** rng.uniform(-12, -1.5, (24, 24, 50)), 0.0).astype(np.float32)
    D = SR.densa(*SR.codificar(R), R.shape)
    sobre = R >= np.float32(SR.UMBRAL)
    assert np.array_equal(D > 0, sobre)                                               # por debajo del umbral, cero; lo demás, no
    assert np.abs(D[sobre] / R[sobre] - 1).max() <= SR.ERROR + 1e-6
    assert D.max() == pytest.approx(R.max(), rel=1e-6)                                # el máximo de cada día, exacto
    G = R * 1e3                                                                       # hasta ~30 s/m³: la escala baja desde el máximo
    D = SR.densa(*SR.codificar(G), G.shape)
    queda = G >= G.max() * np.exp(-254 * 2 * np.log1p(SR.ERROR)) * (1 + 1e-6)
    assert D.max() == pytest.approx(G.max(), rel=1e-6) and np.abs(D[queda] / G[queda] - 1).max() <= SR.ERROR + 1e-6
    assert not SR.densa(*SR.codificar(np.zeros((24, 24, 5), np.float32)), (24, 24, 5)).any()


def test_serie_respuestas_importar_anade_dias_y_quita_los_de_un_foco_cambiado():
    a, b = _foco("F01"), _foco("F02")
    _guarda_serie([a, b], lambda i, t, r: 1e-3 * (r + 1), fin="2023-01-03")
    ind = SR.indice(planta.DIR_DISPERSION)
    assert SR.dias(ind) == list(pd.date_range("2023-01-01", "2023-01-03")) and set(ind["focos"]) == {"F01", "F02"}
    assert [p.name for p in (planta.DIR_DISPERSION / "F01").iterdir()] == ["202301.rz"]
    idx, val = SR.leer_dia(planta.DIR_DISPERSION, "F02", "2023-01-02")
    assert len(idx) == 24 * 16 and val.max() == pytest.approx(16e-3, rel=1e-6)
    b2 = dict(b, altura_m=9.0)                                                        # el F02 ha cambiado: lo de antes ya no vale
    origen = planta.DATOS / "otras"
    for d in ("2023-01-04", "2023-01-05"):
        _guarda_respuestas([a, b2], lambda i, t, r: 2e-3, carpeta=origen / f"serie_a_{d.replace('-', '')}", serie="serie_a", dia=d)
    avisos = []
    ind = SR.importar(planta.DIR_DISPERSION, SR._origenes(origen, "serie_a"), huellas={"F01": F.huella(a), "F02": F.huella(b2)},
                      avisa=avisos.append)
    assert len(SR.dias_foco(ind, "F01")) == 5 and [f"{d:%d}" for d in SR.dias_foco(ind, "F02")] == ["04", "05"]
    assert SR.dias(ind) == list(pd.date_range("2023-01-04", "2023-01-05")) and any("F02: ha cambiado" in t for t in avisos)
    _guarda_respuestas([b], lambda i, t, r: 1e-3, carpeta=origen / "serie_a_20230106", serie="serie_a", dia="2023-01-06")
    with pytest.raises(ValueError, match="huellas distintas"):                       # sin huellas, dos versiones de un foco no
        SR.importar(planta.DIR_DISPERSION, SR._origenes(origen, "serie_a"))
    otra = planta.DATOS / "otra_malla" / "serie_a_20230107"
    x, y = _guarda_respuestas([a], lambda i, t, r: 1e-3, carpeta=otra, serie="serie_a", dia="2023-01-07")
    np.savez_compressed(otra / "receptores.npz", x=x + 1.0, y=y, cota=np.zeros(len(x)), clase=np.array(["a"] * len(x)))
    with pytest.raises(ValueError, match="la malla ha cambiado"):
        SR.importar(planta.DIR_DISPERSION, SR._origenes(otra.parent, "serie_a"))


def test_serie_respuestas_repetir_semanas_de_prueba_en_todo_el_periodo():
    # usuario, 2026-11-09: mientras no estén los focos de la planta, un banco de pruebas del tamaño de la serie de verdad, «para buscar el método
    # de convertir todos los datos de dispersión en menos espacio y leer y calcular rápido»: una semana por estación, simulada y copiada en los 5
    # años. Cada día, el del mismo día de la semana más cercano en el calendario; lo que ya estaba se queda; y la comprobación avisa
    a, b = _foco("F01"), _foco("F02")
    origen = planta.DATOS / "respuestas"
    invierno, verano = pd.date_range("2023-02-20", "2023-02-26"), pd.date_range("2023-08-07", "2023-08-13")      # de lunes a domingo
    valores = {**{d: 1e-3 * (k + 1) for k, d in enumerate(invierno)}, **{d: 1e-3 * (k + 11) for k, d in enumerate(verano)},
               pd.Timestamp("2023-03-10"): 8e-3}                                       # y un viernes suelto, con lo suyo
    for d, v in valores.items():
        _guarda_respuestas([a, b], lambda i, t, r, v=v: v, carpeta=origen / f"serie_a_{d:%Y%m%d}", serie="serie_a", dia=f"{d:%Y-%m-%d}")
    SR.importar(planta.DIR_DISPERSION, [o for o in SR._origenes(origen, "serie_a") if o[1]["dia"] in ("2023-02-20", "2023-02-21")])
    with pytest.raises(ValueError, match="los 7 días de la semana"):                  # con dos días de la semana, no
        SR.repetir(planta.DIR_DISPERSION, "2023-01-01", "2023-12-31")
    SR.importar(planta.DIR_DISPERSION, SR._origenes(origen, "serie_a"))
    avisos = []
    ind = SR.repetir(planta.DIR_DISPERSION, "2023-01-01", "2023-12-31", avisa=avisos.append)
    assert SR.dias(ind) == list(pd.date_range("2023-01-01", "2023-12-31")) and len(avisos) == 2 and ind == SR.indice(planta.DIR_DISPERSION)
    assert ind["repetida"] == {"dias": [f"{d:%Y-%m-%d}" for d in sorted(valores)], "desde": "2023-01-01", "hasta": "2023-12-31"}
    for d, v in (("2023-01-02", 1e-3), ("2023-07-03", 11e-3), ("2023-12-25", 1e-3), ("2023-10-29", 17e-3), ("2023-11-26", 7e-3),
                 ("2023-03-17", 8e-3), ("2023-02-26", 7e-3), ("2023-08-13", 17e-3)):
        _, val = SR.leer_dia(planta.DIR_DISPERSION, "F02", d)          # el lunes de enero, el de invierno; el de julio, el de verano; y así
        assert val.max() == pytest.approx(v, rel=1e-6), d
    # copias de verdad: el banco de pruebas tiene el tamaño de la serie
    assert len(SR.leer_mes(planta.DIR_DISPERSION, "F02", 2023, 1)) == 31 and (planta.DIR_DISPERSION / "F02" / "202301.rz").stat().st_size > 31 * 50
    assert SR.repetir(planta.DIR_DISPERSION, "2023-01-01", "2023-12-31")["repetida"] == ind["repetida"]       # otra vez, igual
    assert SR.semanas_repetidas(ind["repetida"]) == [pd.Timestamp("2023-02-20"), pd.Timestamp("2023-03-06"), pd.Timestamp("2023-08-07")]
    from teodors.operacion import comprobar as C
    codigos, _ = C._respuestas()
    assert codigos[0][0] == "DIS-03" and ("de prueba: 15 días simulados (semanas del 20/02/2023, 06/03/2023, 07/08/2023), copiados de "
                                          "2023-01-01 a 2023-12-31") in codigos[0][1]


def test_media_maximo_y_p98_de_la_serie_horaria_a_mano(sin_imagenes):
    """Sobre las horas simuladas: las de los días que hay, sin contar con años completos. El primer día cuenta: lo emitido la víspera
    ya va en sus respuestas. Lo guardado lleva un error relativo de serie_respuestas.ERROR como mucho."""
    f = _foco("F01", q=1000.0)
    cat = {"focos": [f]}
    _guarda_serie([f], lambda i, t, r: (t + 1) * (r + 1) * 1e-3)               # Q · R = (hora + 1) · (r + 1)
    esc = E.nuevo(cat, "P")
    res = S.calcular(esc, cat)
    z = _campos(esc)
    fines = _horas_serie()
    serie = np.outer(fines.hour + 1, np.arange(16) + 1)
    assert res["horas"] == len(fines) == 59 * 24 and res["largo"] == "anios"
    assert res["datos"] == {"ini": SERIE_INI, "fin": SERIE_FIN, "dias": 59, "horas": 59 * 24, "huecos": 0, "anios": {2023: 59 * 24},
                            "incompletos": [2023]}
    assert z["media"] == pytest.approx(serie.mean(axis=0), rel=SR.ERROR)
    assert z["maximo"] == pytest.approx(serie.max(axis=0), rel=SR.ERROR)
    assert z["p98"] == pytest.approx(np.percentile(serie, 98, axis=0), rel=SR.ERROR)
    assert z["p98"][0] > 1.8 * z["media"][0]                                   # no sale de las medias: el 2 % más alto es casi el doble
    m = res["magnitudes"]["olor"]
    nombres = [fila["nombre"] for fila in m["filas"]]
    assert m["unidad"] == "ou_E/m³" and "Pueblo" in nombres and "Peor vivienda (< 1.5 km)" in nombres
    assert {f["nombre"]: f["tipo"] for f in m["filas"]} == {"Peor vivienda (< 1.5 km)": "vivienda", "Pueblo": "pueblo"}
    assert m["filas"][nombres.index("Peor vivienda (< 1.5 km)")]["maximo"] == pytest.approx(24 * 16, rel=1e-5)    # el máximo del día, exacto
    # la hora a hora de cada pueblo (lo peor de sus receptores) y de la peor vivienda (usuario, 2026-11-10: cuándo se huele, en el informe)
    ruta = S.carpeta_resultados(esc) / "olor" / S.HORAS_PUEBLOS
    with np.load(ruta) as h:
        horas, lugares, C = h["horas"], list(h["nombres"]), h["C"]
    assert lugares == ["Pueblo", "Peor vivienda (< 1.5 km)"] and C.shape == (59 * 24, 2) and C.dtype == np.float32
    assert np.array_equal(horas, fines.values.astype("datetime64[h]").astype(np.int64))
    for j, nombre in enumerate(lugares):                                       # su peor hora, la de la tabla
        assert C[:, j].max() == pytest.approx(m["filas"][nombres.index(nombre)]["maximo"], rel=1e-6)
    assert C[:, 1] == pytest.approx(serie[:, 15], rel=SR.ERROR)                # la peor vivienda, el receptor 15: el de más P98
    assert not (planta.DIR_TRABAJO / "reanalisis").exists()                    # v0.1.10: acumulando, sin la serie entera en ficheros
    # cortado a medias (usuario, 2026-11-09: quedaron 17 GB de un cálculo de 5 años que se cerró): no deja nada, y lo que dejara otro se borra
    vueltas = []
    with pytest.raises(RuntimeError, match="cancelado"):
        S.calcular(esc, cat, cancelado=lambda: vueltas.append(1) or len(vueltas) > 20)
    assert len(vueltas) > 20 and not (planta.DIR_TRABAJO / "reanalisis").exists()
    (planta.DIR_TRABAJO / "reanalisis").mkdir(parents=True)
    (planta.DIR_TRABAJO / "reanalisis" / "C_olor.f32").write_bytes(b"de un calculo cortado")
    S.calcular(esc, cat)
    assert not (planta.DIR_TRABAJO / "reanalisis").exists()


def test_solo_cuentan_las_horas_del_plan_y_el_primer_dia_tambien(sin_imagenes):
    """Plan mensual de enero, alto todo el día 1. Cuenta el primer día de la serie (el máximo es el alto) y no cuenta febrero."""
    f = _foco("F01", q=1.0)
    cat = {"focos": [f]}
    _guarda_serie([f], lambda i, t, r: 1.0)
    esc = E.nuevo(cat, "M")
    esc["mes"] = "2023-01"
    pf = E.plan_foco(f, esc)
    E.cambiar_plan(pf, "mensual")
    E.poner_perfil(pf, list(range(1, 31)), [0.25] * 24)
    E.poner_perfil(pf, [0], [1.0] * 24)
    res = S.calcular(esc, cat)
    z = _campos(esc)
    # por el fin de la hora en hora oficial: de la 01 del 1 de enero a las 23 del 31 (743 h: la que acaba a las 00 del 1 es del
    # 31 de diciembre, que no está, y la de las 24 del 31 ya es febrero); lo emitido el día 1 (en hora oficial) llega en las 24
    # primeras; febrero, fuera aunque tenga días
    assert res["horas"] == 743 and res["datos"]["horas"] == 743
    assert z["maximo"] == pytest.approx(1.0, rel=1e-6)
    assert z["media"] == pytest.approx((24 * 1.0 + 719 * 0.25) / 743, rel=1e-6)


# ── el reanálisis en paralelo (v0.1.10): repartido entre procesos y acumulando, sin la serie entera en ficheros ──
def test_el_reanalisis_en_paralelo_da_lo_mismo_salvo_la_ultima_cifra_de_las_medias(sin_imagenes):
    """`calcular(..., paralelo=2)` (un mes en cada proceso): el máximo, el P98, las normas de 1 h y de 24 h, lo peor de cada pueblo y la peor
    vivienda, idénticos bit a bit al cálculo de siempre; las medias (la de todo y la anual), en la cifra 14-15. Sin nada en disco, y se cancela."""
    a = _foco("F01", q=100.0, gases=[{"gas": "SO2", "valor": 0.5, "unidad": "g/s"}, {"gas": "NO2", "valor": 0.2, "unidad": "g/s"}])
    b = _foco("F02", q=30.0, gases=[{"gas": "SO2", "valor": 0.1, "unidad": "g/s"}])
    cat = {"focos": [a, b]}
    _guarda_serie([a, b], lambda i, t, r: (1e-3 if i == "F01" else 5e-3) * (((7 * t + 3 * r) % 11) + (r % 3 == 0)) * (t % 5 != 0))
    esc = E.nuevo(cat, "P")
    pf = E.plan_foco(a, esc)
    E.cambiar_plan(pf, "semanal")
    for w in range(7):                                                          # cada día de la semana, otro: los días no son iguales
        E.poner_perfil(pf, [w], [(w + 1) / 7.0] * 24)
    uno = S.calcular(esc, cat, paralelo=False)
    campos = {k: _campos(esc, k) for k in uno["orden"]}
    ruta = S.carpeta_resultados(esc) / "olor" / S.HORAS_PUEBLOS
    with np.load(ruta) as h:
        horas_uno = h["C"]
    dos = S.calcular(esc, cat, paralelo=2)
    assert not (planta.DIR_TRABAJO / "reanalisis").exists()                    # nada en disco
    assert dos["orden"] == uno["orden"] and set(uno["orden"]) == {"olor", "SO2", "NO2"}
    assert {c["clave"] for c in dos["magnitudes"]["SO2"]["columnas"]} >= {"norma_hora", "norma_dia"}
    assert {c["clave"] for c in dos["magnitudes"]["NO2"]["columnas"]} >= {"norma_hora", "norma_anio"}
    for k in uno["orden"]:
        z = _campos(esc, k)
        assert set(z) == set(campos[k])
        for c, v in campos[k].items():
            if c in ("media", "norma_anio"):
                assert z[c] == pytest.approx(v, rel=1e-12), (k, c)
            else:
                assert z[c].dtype == v.dtype and z[c].tobytes() == v.tobytes(), (k, c)
    with np.load(ruta) as h:
        assert h["C"].tobytes() == horas_uno.tobytes()                         # los pueblos y la peor vivienda, hora a hora
    with pytest.raises(RuntimeError, match="cancelado"):
        S.calcular(esc, cat, paralelo=2, cancelado=lambda: True)
    assert not (planta.DIR_TRABAJO / "reanalisis").exists()


def test_el_paralelo_por_defecto_sale_de_la_planta(monkeypatch, tmp_path):
    from teodors.operacion import reanalisis_paralelo as RP
    assert RP.de_la_planta() is False                                           # sin decir nada: el cálculo de siempre
    assert RP.procesos(None) == RP.procesos(False) == RP.procesos(1) == 1 and RP.procesos(4) == 4
    assert 1 <= RP.procesos(True) <= RP.MAX_PROCESOS
    _planta(tmp_path / "otra", operacion={"paralelo": 4})
    assert RP.de_la_planta() == 4
    for texto, sale in (("no", False), ("0", False), ("2", 2), ("auto", True), ("sí", True)):   # la variable, antes que planta.json
        monkeypatch.setenv("PRUEBA_OPER_PARALELO", texto)
        assert RP.de_la_planta() == sale and type(RP.de_la_planta()) is type(sale)


def test_los_acumuladores_del_paralelo_dan_lo_mismo_que_la_serie_entera():
    """`reanalisis_paralelo.Acum` frente a `normativa.estadistico` con la serie entera (que cruza el año y con horas fuera del plan): en un
    tramo, todo idéntico bit a bit; en tramos que parten días por medio, también, salvo las medias (otro orden de suma)."""
    from teodors.operacion import reanalisis_paralelo as RP
    rng = np.random.default_rng(7)
    fines = pd.date_range("2022-12-20 01:00", periods=24 * 40, freq="h")
    fines = fines[rng.random(len(fines)) >= 0.1]
    n, nrec = len(fines), 37
    C = (rng.random((n, nrec)) ** 6 * 50).astype(np.float32)
    C[rng.random((n, nrec)) < 0.4] = 0
    C[:, 3] = 0                                                                 # un receptor al que nunca llega nada
    cols = [{"clave": "media"}, {"clave": "maximo"}, {"clave": "p98", "percentil": 98.0}, {"clave": "norma_hora", "promedio": "hora", "n": 18},
            {"clave": "norma_dia", "promedio": "dia", "n": 3}, {"clave": "norma_anio", "promedio": "anio", "n": 0}]
    anio, fecha = np.asarray(fines.year), np.asarray(fines.normalize().asi8)
    dia = np.asarray((fines - pd.Timedelta(hours=1)).normalize())             # el día de cálculo: las horas con fin de la 01 a las 00

    def acumular(tramos):
        partes = []
        for f0, f1 in tramos:
            a, mes = RP.Acum(cols, n, nrec, anio, fecha), None
            for d in pd.unique(dia[f0:f1]):
                filas = f0 + np.flatnonzero(dia[f0:f1] == d)
                if (pd.Timestamp(d).year, pd.Timestamp(d).month) != mes:
                    a.cerrar_lote()
                    mes = (pd.Timestamp(d).year, pd.Timestamp(d).month)
                a.anadir(filas, C[filas])
            a.cerrar_lote()
            partes.append(a)
        for p in partes[1:]:
            partes[0].juntar(p)
        return partes[0].resultado(fines, 10)
    uno = acumular([(0, n)])
    tres = acumular([(0, n // 3), (n // 3, n // 2 + 5), (n // 2 + 5, n)])
    for col in cols:
        ref = N.estadistico(col, C, fines)
        assert uno[col["clave"]].dtype == ref.dtype and uno[col["clave"]].tobytes() == ref.tobytes(), col["clave"]
        if col["clave"] in ("media", "norma_anio"):
            assert tres[col["clave"]] == pytest.approx(ref, rel=1e-12), col["clave"]
        else:
            assert tres[col["clave"]].tobytes() == ref.tobytes(), col["clave"]


def test_el_percentil_de_las_horas_mas_altas_es_el_de_numpy_bit_a_bit():
    """`percentil_de_las_altas`, con solo las K horas más altas de cada receptor, da lo mismo que `np.percentile` sobre todas (si numpy
    cambia su cuenta, esta prueba lo dice): con ceros, empates, pocos y muchos datos y otros percentiles."""
    from teodors.operacion import reanalisis_paralelo as RP
    rng = np.random.default_rng(11)
    for n in (5, 37, 100, 1416, 8761, 43824):
        for p in (98.0, 95.0, 50.0, 99.9):
            C = (rng.random((n, 13)) ** 5 * 40).astype(np.float32)
            C[rng.random((n, 13)) < 0.5] = 0
            C[:, 2] = 0                                                        # todo ceros
            C[:, 5] = np.round(C[:, 5])                                       # empates
            K = n - int(np.floor((n - 1) * p / 100.0)) + 1
            top = np.partition(C.T, n - K, axis=1)[:, n - K:]
            mio = RP.percentil_de_las_altas(top, n, p)
            ref = np.percentile(C.T, p, axis=1)
            assert mio is not None and mio.dtype == ref.dtype and mio.tobytes() == ref.tobytes(), (n, p)


def test_las_horas_mas_altas_se_mantienen_exactas_al_llegar_por_tandas():
    from teodors.operacion import reanalisis_paralelo as RP
    rng = np.random.default_rng(3)
    nrec, K = 29, 40
    tandas = [(rng.random((m, nrec)) ** 4 * 10).astype(np.float32) for m in (7, 744, 3, 200, 744, 744, 1, 60)]
    for L in tandas:
        L[rng.random(L.shape) < 0.6] = 0
    tandas[2][:, 4] = 9.0                                                     # empates con lo que ya hay
    a = RP._Altas(nrec, K)
    a.CAP = 300                                                               # que se llene (y se junte) a menudo
    for L in tandas:
        a.anadir(L)
    todas = np.concatenate(tandas)
    assert np.array_equal(np.sort(a.final(), axis=1), np.sort(np.partition(todas.T, len(todas) - K, axis=1)[:, -K:], axis=1))
    b1, b2 = RP._Altas(nrec, K), RP._Altas(nrec, K)                          # en dos tramos, juntados
    for L in tandas[:4]:
        b1.anadir(L)
    for L in tandas[4:]:
        b2.anadir(L)
    b1.juntar(b2)
    assert np.array_equal(np.sort(b1.final(), axis=1), np.sort(a.final(), axis=1))


def _dos_focos():
    a, b = _foco("F01", q=100.0), _foco("F02", q=30.0)
    cat = {"focos": [a, b]}
    _guarda_serie([a, b], lambda i, t, r: (1e-3 if i == "F01" else 5e-3) * ((t + r) % 7 + 1))
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
    ini, fin = "2023-01-02", "2023-03-26"                                      # 12 semanas, de lunes a domingo, con febrero entero
    _guarda_serie([f], lambda i, t, r: (t + 1.0) * 1e-3, ini=ini, fin=fin)
    diario = E.nuevo(cat, "Diario")
    S.calcular(diario, cat)
    d = _campos(diario)
    lunes = E.nuevo(cat, "Lunes")
    pf = E.plan_foco(f, lunes)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, [1, 2, 3, 4, 5, 6], [0.0] * 24)
    S.calcular(lunes, cat)
    fines = _horas_serie(ini, fin)
    es_lunes = (fines - pd.Timedelta(hours=1)).tz_localize("UTC").tz_convert("Europe/Madrid").weekday == 0   # por el inicio de la hora, en hora oficial
    peso = np.asarray(fines.hour) + 1.0
    parte = (peso * np.asarray(es_lunes)).sum() / peso.sum()
    assert parte == pytest.approx(1 / 7, rel=1e-2)
    assert _campos(lunes)["media"] == pytest.approx(d["media"] * parte, rel=1e-5)
    assert _campos(lunes)["maximo"] == pytest.approx(d["maximo"], rel=1e-5)
    mes = E.nuevo(cat, "Febrero")
    mes["mes"] = "2023-02"
    E.cambiar_plan(E.plan_foco(f, mes), "mensual")
    r = S.calcular(mes, cat)
    assert r["horas"] == 28 * 24 and _campos(mes)["media"] == pytest.approx(d["media"], rel=1e-5)


def test_lo_que_no_se_puede_calcular_se_dice(sin_imagenes):
    f, sin, cambiado, nada = _foco("F01"), _foco("F02", olor={}), _foco("F03"), _foco("F04", funcionamiento={"modo": "eventos"})
    _guarda_serie([f, sin, cambiado], lambda i, t, r: 1e-3, fin="2023-01-03")
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
    _guarda_serie([f], lambda i, t, r: 2e-6 * (r + 1))
    esc = E.nuevo(cat, "G")
    res = S.calcular(esc, cat)
    assert res["orden"] == ["olor", "H2S", "NO2"]
    assert _campos(esc, "H2S")["media"][0] == pytest.approx(0.5e6 * 2e-6, rel=SR.ERROR)      # µg/s × s/m³ = µg/m³
    assert _campos(esc, "H2S")["media"][15] == pytest.approx(0.5e6 * 2e-6 * 16, rel=1e-6)    # el máximo de cada día, exacto
    umbral = 0.41 * 34.08 / 24.45                                                            # µg/m³ del H2S: el dominante
    assert _campos(esc, "olor")["media"][15] == pytest.approx(0.5e6 / umbral * 2e-6 * 16, rel=1e-5)
    assert res["magnitudes"]["olor"]["estimados"] == ["Foco F01 (H₂S)"]
    assert [c["clave"] for c in res["magnitudes"]["NO2"]["columnas"]] == ["media", "maximo", "norma_hora", "norma_anio"]
    assert _campos(esc, "NO2")["norma_hora"][15] == pytest.approx(32.0, rel=1e-5)            # constante: su 19.ª hora también
    assert res["datos"]["incompletos"] == [2023]                                             # la norma, por año civil: este, a medias


def test_isolineas_rellenas_y_guardar_y_cargar_resultados(tmp_path):
    """Usuario, 2026-11-09: la media, el máximo y el P98 también en isolíneas rellenas; y «Guardar resultados» y «Cargar resultados»."""
    # usuario, 2026-11-09: de los gases, «el color map de 4 órdenes de magnitud»: una franja por orden, en potencias de 10; del olor, «añadir
    # 0,01-0,1 y de 0,1-1, 1-3, 3-5 y de 5-10» (y encima, por órdenes)
    assert S.niveles_isolineas() == [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]               # como el degradado: desde 0,01 (usuario, 2026-11-10)
    assert S.niveles_isolineas(1044.8) == [10.0, 100.0, 1000.0, 1e4, 1e5, 1e6] and S.niveles_isolineas(0.1377) == [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
    assert S.niveles_isolineas(1.0, "olor") == [0.01, 0.1, 1.0, 3.0, 5.0, 10.0, 100.0, 1000.0]
    f = _foco("F01")
    cat = {"focos": [f]}
    _guarda_serie([f], lambda i, t, r: 1e-3 * (r + 1), fin="2023-01-02")
    esc = E.nuevo(cat, "Con isolíneas")
    res = S.calcular(esc, cat)
    capa = res["magnitudes"]["olor"]["capas"][0]
    datos = S.leer_isolineas(capa)
    franjas = [x for x in datos["features"] if x["properties"]["tipo"] == "franja"]
    lineas = [x for x in datos["features"] if x["properties"]["tipo"] == "linea"]
    assert franjas and lineas and all(x["geometry"]["type"] == "MultiPolygon" for x in franjas)
    assert capa["isolineas"]["niveles"] == S.niveles_isolineas(1.0, "olor")
    assert {x["properties"]["desde"] for x in franjas} <= set(capa["isolineas"]["niveles"][:-1]) and len(franjas) <= 7
    assert {x["properties"]["f"] for x in franjas} <= {(i + 0.5) / 7 for i in range(7)}    # repartidas a partes iguales en la escala
    assert capa["isolineas"]["leyenda"].count("background-position") == 7
    # con otras franjas, lo guardado rehace sus isolíneas de su resumen, sin volver a calcular la serie
    antes = Path(S.url_a_ruta(capa["imagenes"][0]["url"])).stat().st_mtime_ns
    S.NIVELES_OLOR, viejas = (0.1, 1.0, 10.0), S.NIVELES_OLOR
    try:
        otra = S.guardado(esc, cat)
        c = otra["magnitudes"]["olor"]["capas"][0]
        assert c["isolineas"]["niveles"] == [0.1, 1.0, 10.0] and {x["properties"]["f"] for x in S.leer_isolineas(c)["features"]
                                                                   if x["properties"]["tipo"] == "franja"} <= {0.25, 0.75}
        assert Path(S.url_a_ruta(c["imagenes"][0]["url"])).stat().st_mtime_ns == antes             # las imágenes, sin tocar
        assert S.guardado(esc, cat)["magnitudes"]["olor"]["capas"][0]["isolineas"]["niveles"] == [0.1, 1.0, 10.0]   # y quedan guardadas
    finally:
        S.NIVELES_OLOR = viejas
    res = S.guardado(esc, cat)
    capa = res["magnitudes"]["olor"]["capas"][0]
    datos = S.leer_isolineas(capa)
    lon, lat = franjas[0]["geometry"]["coordinates"][0][0][0]
    assert abs(lat - LAT) < 0.05 and abs(lon - LON) < 0.05                                 # en lat/lon, junto a la planta
    assert "var(--escala-olor)" in capa["isolineas"]["leyenda"]
    # guardar el caso (usuario, 2026-11-09: «te pide un nombre que se añade a la fecha, año/mes/día-nombre, creándose esa carpeta, donde guardará
    # los resultados y la operabilidad de los focos en una carpeta llamada resultados») y cargarlo: las mismas cifras, y sus imágenes e isolíneas allí
    import datetime as dt
    caso = S.carpeta_caso("  Mi caso: prueba/1 ", fecha=dt.date(2026, 11, 9))
    assert caso == S.dir_guardados() / "2026-11-09-Mi caso- prueba-1" and S.carpeta_caso("Otro").name == f"{dt.date.today():%Y-%m-%d}-Otro"
    with pytest.raises(ValueError, match="nombre"):
        S.carpeta_caso(" /: ")
    otro_cat = {"focos": [dict(f, nombre="Cambiado")]}
    assert S.guardar_caso(res, caso, otro_cat) == {"carpeta": str(caso), "focos": False}       # otros focos que los de la simulación: sin ellos
    assert not (caso / "resultados" / "focos.json").exists()
    assert S.guardar_caso(res, caso, cat) == {"carpeta": str(caso), "focos": True}             # se sustituye
    hay = sorted(p.relative_to(caso).as_posix() for p in caso.rglob("*") if p.is_file())
    assert {"resultados/resultado.json", "resultados/plan_operacion.json", "resultados/focos.json", "resultados/olor/resumen.npz",
            "resultados/olor/p98_isolineas.json"} <= set(hay) and all(h.startswith("resultados/") for h in hay)
    assert json.loads((caso / "resultados" / "plan_operacion.json").read_text(encoding="utf-8")) == res["esc"]
    assert json.loads((caso / "resultados" / "focos.json").read_text(encoding="utf-8")) == cat
    cargado = S.cargar_caso(caso)
    assert Path(cargado["carpeta"]) == caso / "resultados" and cargado["caso"] == {"nombre": caso.name, "ruta": str(caso)}
    assert cargado["firma"] == res["firma"] and cargado["magnitudes"]["olor"]["maximos"] == res["magnitudes"]["olor"]["maximos"]
    c2 = cargado["magnitudes"]["olor"]["capas"][0]
    assert Path(S.url_a_ruta(c2["imagenes"][0]["url"])).parent == caso / "resultados" / "olor"
    assert S.leer_isolineas(c2) == datos
    x, y = _receptores()
    assert S.valores(cargado, "olor")[(round(float(x[0]), 1), round(float(y[0]), 1))] == S.valores(res, "olor")[(round(float(x[0]), 1), round(float(y[0]), 1))]
    shutil.rmtree(S.carpeta_resultados(esc))                       # lo guardado no depende de lo simulado
    assert S.leer_isolineas(S.cargar_caso(caso / "resultados")["magnitudes"]["olor"]["capas"][0]) == datos     # también desde «resultados»
    # un caso cargado, guardado con otro nombre: sus focos van con él aunque los de ahora sean otros
    otro = S.carpeta_caso("Copia", fecha=dt.date(2026, 11, 10))
    assert S.guardar_caso(cargado, otro, otro_cat)["focos"] is True and S.cargar_caso(otro)["caso"]["nombre"] == "2026-11-10-Copia"
    assert "carpeta" not in json.loads((otro / "resultados" / "resultado.json").read_text(encoding="utf-8"))
    # los casos, en la carpeta de su modo (usuario, 2026-11-10: «casos, con 3 carpetas: reanálisis, episodios y predicción»), junto a la planta
    assert caso.parent == planta.DIR_CASOS / "reanalisis" and planta.DIR_CASOS == planta.PLANTA.parent / "casos"
    assert S.dir_guardados("queja") == planta.DIR_CASOS / "episodios" and S.carpeta_caso("P", modo="prediccion").parent.name == "prediccion"
    planta.asegurar_carpetas()
    assert sorted(p.name for p in planta.DIR_CASOS.iterdir()) == ["episodios", "prediccion", "reanalisis"]
    # el degradado hasta 0,01 (usuario, 2026-11-10): un caso pintado con la escala de antes (de 0,1, sin apuntarla) se repinta al abrirlo
    assert (S.VMIN, S.VMAX) == (0.01, 1000.0) and c2["vmin"] == 0.01 and c2["decadas"] == 5
    guardado = json.loads((otro / "resultados" / "resultado.json").read_text(encoding="utf-8"))
    for c in guardado["magnitudes"]["olor"]["capas"]:
        c.pop("vmin"), c.pop("decadas")
        c["leyenda"] = "la de antes"
    (otro / "resultados" / "resultado.json").write_text(json.dumps(guardado), encoding="utf-8")
    png = otro / "resultados" / "olor" / "p98_0.png"
    png.write_bytes(b"de antes")
    viejo = S.cargar_caso(otro)["magnitudes"]["olor"]["capas"]
    assert all(c["vmin"] == 0.01 and c["leyenda"] != "la de antes" and "0,01" in c["leyenda"] for c in viejo)
    assert png.read_bytes()[:4] == b"\x89PNG"                                                # repintada
    assert json.loads((otro / "resultados" / "resultado.json").read_text(encoding="utf-8"))["magnitudes"]["olor"]["capas"][0]["vmin"] == 0.01
    (tmp_path / "nada").mkdir()
    with pytest.raises(ValueError, match="no es un caso guardado"):
        S.cargar_caso(tmp_path / "nada")
    (tmp_path / "viejo" / "resultados").mkdir(parents=True)
    (tmp_path / "viejo" / "resultados" / "resultado.json").write_text(json.dumps({"formato": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="otra versión"):
        S.cargar_caso(tmp_path / "viejo")


def test_la_tabla_del_reanalisis_tiene_todos_los_pueblos_uno_por_nombre():
    """Usuario, 2026-11-09: «los resultados tabulados deben ser de los pueblos». Un pueblo en dos partes sale una vez, con lo peor de ellas
    y la distancia de la más cercana; sin `todos_los_pueblos` (un periodo), los 10 más cercanos, como antes."""
    xc, yc = geo.a_utm(LAT, LON)
    km = np.array([1.0, 2.0, 3.0] + list(range(4, 16)))
    x, y = xc + 1000.0 * km, np.full(len(km), yc)
    etiquetas = [{"i": 0, "nombre": "Dos partes", "clase": "nucleo", "familia": "residencial"},
                 {"i": 1, "nombre": "Polígono", "clase": "nucleo", "familia": "industrial"},
                 {"i": 2, "nombre": "Dos partes", "clase": "nucleo", "familia": "residencial"}]
    etiquetas += [{"i": i, "nombre": f"Pueblo {i}", "clase": "nucleo", "familia": "residencial"} for i in range(3, len(km))]
    campos = {"media": np.arange(len(km), dtype=float), "maximo": 100.0 - np.arange(len(km))}
    filas = S._tabla({"centro": (xc, yc), "etiquetas": etiquetas}, x, y, np.array(["a"] * len(km)), campos, [], todos_los_pueblos=True)
    assert all(f["tipo"] == "pueblo" for f in filas) and len(filas) == len(km) - 2 and "Polígono" not in [f["nombre"] for f in filas]
    assert filas[0] == {"nombre": "Dos partes", "tipo": "pueblo", "km": 1.0, "media": 2.0, "maximo": 100.0}
    assert len(S._tabla({"centro": (xc, yc), "etiquetas": etiquetas}, x, y, np.array(["a"] * len(km)), campos, [])) == 10


def _contorno(x0, x1, y0, y1):
    """Un rectángulo en UTM, como anillo [[lon, lat], …] de planta.json."""
    esquinas = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [[geo.a_geo(x, y)[1], geo.a_geo(x, y)[0]] for x, y in esquinas]


def test_cada_pueblo_vale_lo_que_el_peor_de_sus_receptores_y_la_planta_anade_los_que_corine_no_tiene():
    # usuario, 2026-11-10: un pueblo a 1,5 km de la planta no salía (CORINE lo tiene como cultivo): «a mano en planta.json», y cada pueblo con
    # «el peor receptor dentro de su contorno», también los de CORINE
    from types import SimpleNamespace
    from teodors.operacion import pueblos as P
    xc, yc = geo.a_utm(LAT, LON)
    x, y = xc + 100.0 * np.arange(20), np.full(20, yc)                      # una fila de receptores, cada 100 m hacia el este
    U = np.zeros((20, 45), int)
    U[10, 11:16] = 112                                                       # CORINE: una mancha residencial sobre los receptores 5, 6 y 7
    U[10, 30] = 121                                                          # y una industrial, que no es un pueblo
    tr = SimpleNamespace(a=50.0, e=-50.0, c=xc - 50.0, f=yc + 500.0)
    assert P.manchas(U, tr, x, y)[[4, 5, 6, 7, 8, 14]].tolist() == [0, 1, 1, 1, 0, 0]
    etiquetas = [{"i": 6, "nombre": "De CORINE", "clase": "nucleo", "familia": "residencial"},
                 {"i": 14, "nombre": "Polígono", "clase": "nucleo", "familia": "industrial"}]
    firma = P.firma()
    _planta(planta.PLANTA, pueblos={"lista": [{"nombre": "A mano", "contorno": [_contorno(xc + 1150, xc + 1450, yc - 100, yc + 100)]}]})
    assert P.firma() != firma and [p["nombre"] for p in P.de_la_planta()] == ["A mano"]
    (c,) = P.centros()                                                       # su icono en el mapa: en el centro de su casco
    assert (c["nombre"], round(c["x"] - xc), round(c["y"] - yc)) == ("A mano", 1300, 0) and c["ha"] == pytest.approx(6.0, rel=0.01)
    et = P.etiquetas(etiquetas, x, y, terreno=(U, tr))
    assert [(e["nombre"], e.get("receptores")) for e in et] == [("De CORINE", [5, 6, 7]), ("Polígono", None), ("A mano", [12, 13, 14])]
    assert et[2]["i"] == 13 and et[2]["origen"] == "planta" and P.etiquetas(et, x, y, terreno=(U, tr)) == et      # se rehace igual
    assert P.etiquetas(etiquetas, x, y, terreno=False)[0]["receptores"] == [6]                                    # sin el terreno, su punto
    campos = {"p98": np.arange(20.0), "maximo": 100.0 - np.arange(20.0)}
    filas = S._tabla({"centro": (xc, yc), "etiquetas": et}, x, y, np.array(["a"] * 20), campos, [], todos_los_pueblos=True)
    assert filas == [{"nombre": "De CORINE", "tipo": "pueblo", "km": 0.6, "p98": 7.0, "maximo": 95.0},       # lo peor de cada estadístico
                     {"nombre": "A mano", "tipo": "pueblo", "km": 1.3, "p98": 14.0, "maximo": 88.0}]       # y la distancia, la de su punto
    # un contorno sin receptores dentro: vale el de su centro, y se avisa
    _planta(planta.PLANTA, pueblos={"lista": [{"nombre": "Pequeño", "contorno": [_contorno(xc + 1520, xc + 1560, yc + 10, yc + 50)]}]})
    assert [(e["nombre"], e["receptores"]) for e in P.etiquetas([], x, y, terreno=False)] == [("Pequeño", [15])]


def test_comparar_dos_escenarios_ya_simulados():
    """Usuario, 2026-11-09: en el reanálisis, comparar dos escenarios ya simulados: el % de más o de menos de cada sitio respecto a la referencia,
    sin volver a calcular; sin darlo donde los dos casi no llegan; y, del olor, la superficie y los pueblos por encima de 1, 3 y 5 ou_E/m³."""
    from teodors.operacion import comparacion as C
    assert np.allclose(C.cambio([0.001, 1.0, 0.0], [0.002, 2.0, 0.05], 0.01), [np.nan, 100.0, 5000.0], equal_nan=True)
    f = _foco("F01")
    cat = {"focos": [f]}
    _guarda_serie([f], lambda i, t, r: 1e-3 * (r + 1), fin="2023-01-02")             # C = r + 1 ou_E/m³ en todas las horas
    ref, menos = E.nuevo(cat, "Referencia"), E.nuevo(cat, "Al 40 %")
    E.poner_perfil(E.plan_foco(f, menos), [0], [0.4] * 24)
    S.calcular(ref, cat)
    S.calcular(menos, cat)
    lista = C.escenarios()
    assert [e["nombre"] for e in lista] == ["Al 40 %", "Referencia"] and not any(e["caso"] for e in lista)
    a, b = (str(S.carpeta_resultados(e)) for e in (ref, menos))
    r = C.comparar(a, b)
    assert (r["ref"]["nombre"], r["otro"]["nombre"], r["orden"], r["avisos"]) == ("Referencia", "Al 40 %", ["olor"], [])
    m = r["magnitudes"]["olor"]
    assert m["umbral"] == 0.01 and [c["id"] for c in m["capas"]] == ["comp_media", "comp_maximo", "comp_norma"]
    pueblo = next(p for p in m["pueblos"] if p["nombre"] == "Pueblo")
    assert pueblo["p98"][0] == pytest.approx(6.0, rel=SR.ERROR) and pueblo["p98"][2] == pytest.approx(-60.0, abs=0.1)
    datos = json.loads(Path(m["capas"][2]["ruta"]).read_text(encoding="utf-8"))
    franjas = [x for x in datos["features"] if x["properties"]["tipo"] == "franja"]
    assert franjas and {x["properties"]["color"] for x in franjas} == {C.COLORES[1]}            # −60 %: la franja de −75 a −50
    assert "cambio (%)" in m["capas"][0]["leyenda"]
    cr = {c["umbral"]: c for c in r["criterios"]}
    assert [cr[u]["pueblos"] for u in C.CRITERIOS_OLOR] == [[1, 1], [1, 0], [1, 0]]               # el pueblo: 6 → 2,4 ou_E/m³
    assert cr[1.0]["km2"][0] > cr[1.0]["km2"][1] > 0 and cr[5.0]["km2"][0] > cr[5.0]["km2"][1]
    with pytest.raises(ValueError, match="mismo escenario"):
        C.comparar(a, a)
    # los casos guardados también se comparan, y salen después de los simulados; uno de otra carpeta, si se da
    import datetime as dt
    S.guardar_caso(C.leer(b), S.carpeta_caso("Mitad", fecha=dt.date(2026, 11, 9)), cat)
    fuera = Path(b).parents[3] / "en otro sitio"
    S.guardar_caso(C.leer(b), fuera, cat)
    lista = C.escenarios([str(fuera / "resultados")])
    assert [(e["texto"], e["caso"]) for e in lista[2:]] == [("2026-11-09-Mitad · caso guardado", "2026-11-09-Mitad"),
                                                          ("en otro sitio · caso guardado", "en otro sitio")]
    assert C.comparar(a, lista[2]["carpeta"])["magnitudes"]["olor"]["pueblos"] == m["pueblos"]
    otra = Path(b).with_name("otras_horas")
    shutil.copytree(b, otra)
    res = json.loads((otra / "resultado.json").read_text(encoding="utf-8"))
    res["datos"]["horas"] -= 24
    (otra / "resultado.json").write_text(json.dumps(res), encoding="utf-8")
    with pytest.raises(ValueError, match="mismas horas"):
        C.comparar(a, str(otra))


def test_con_imagenes_se_guarda_y_se_vuelve_a_leer():
    f = _foco("F01")
    cat = {"focos": [f]}
    _guarda_serie([f], lambda i, t, r: 1e-2 * (r + 1), fin="2023-01-03")
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
    assert v[(round(float(x[0]), 1), round(float(y[0]), 1))]["maximo"] == pytest.approx(10.0, rel=SR.ERROR)
    assert S.cifra(0) == "0" and S.cifra(0.004) == "< 0,01" and S.cifra(1.234) == "1,2" and S.cifra(123.4) == "123"
    assert S.periodo_reanalisis() == {"ini": "2023-01-01", "fin": "2023-01-03", "dias": 3, "horas": 72, "huecos": 0,
                                      "anios": {2023: 72}, "incompletos": [2023]}
    # se añaden días (otro mes): el periodo se amplía solo, con un hueco, y lo guardado ya no vale
    _guarda_serie([f], lambda i, t, r: 1e-2 * (r + 1), ini="2023-03-01", fin="2023-03-02")
    p = S.periodo_reanalisis()
    assert (p["ini"], p["fin"], p["dias"], p["huecos"]) == ("2023-01-01", "2023-03-02", 5, 56)
    assert S.guardado(esc, cat) is None and S.calcular(esc, cat)["horas"] == 5 * 24


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
    # el promedio de 8 h, con una normativa de la planta (la plantilla nacional ya no tiene el CO: la app es de olores)
    planta.NORMATIVA_JSON.write_text(json.dumps({"olor": {"percentil": 98}, "sin_limite": {"percentil": 98},
                                                 "gases": {"H2S": [{"valor": 100, "promedio": "8h"}]}}), encoding="utf-8")
    assert N.estadistico(_col("norma_8h", gas="H2S"), C, fines) == pytest.approx([800, 400])


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
    assert d["gases"]["SO2"][0]["superaciones_anio"] == 24 and "CO" not in d["gases"] and "NOx" not in d["gases"]
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
    assert ruta == planta.DIR_PLANES / "volteos_por_la_tarde.json" and E.cargar(ruta)["focos"] == esc["focos"]
    assert [n for n, _, _ in E.listar()] == ["Volteos por la tarde"]
    with pytest.raises(ValueError, match="Base"):
        E.guardar(E.base(cat))
    E.cambiar_plan(pf, "mensual", "2023-05")                                    # el 1 de mayo fue lunes
    assert len(pf["dias"]) == 31 and E.perfil_dia(pf, 0) == [0.5] * 24 and E.perfil_dia(pf, 1) == [1.0] * 24
    ruta.write_text(json.dumps({"formato": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="formato"):
        E.cargar(ruta)


def test_la_emision_de_la_planta_dia_a_dia_con_su_plan():
    # usuario, 2026-11-08: el calendario de la página Focos, «igual que el del viento pero con olores y gases»
    import datetime as dt
    pila = {"id": "P", "modelo": "superficie", "olor": {"valor": 1000, "unidad": "ou_E/s"},
            "gases": [{"gas": "H2S", "valor": 0.5, "unidad": "g/s"}], "funcionamiento": {"modo": "horario", "horas": "8-16", "fuera_pct": 50}}
    venteo = {"id": "V", "modelo": "punto", "olor": {"valor": 3000, "unidad": "ou_E/s"},
              "funcionamiento": {"modo": "eventos", "veces_mes": 2, "duracion_min": 30}}
    roto = {"id": "R", "modelo": "punto", "olor": {"valor": 99, "unidad": "ou_E/s"}, "funcionamiento": {"modo": "eventos"}}   # sin frecuencia: no cuenta
    cat = {"focos": [pila, venteo, roto]}
    parte = 2 * 30 / (365.25 / 12 * 24 * 60)
    lunes, domingo = dt.date(2026, 11, 9), dt.date(2026, 11, 8)
    base = E.base(cat)
    d = E.emision_dias(base, cat, "olor", [lunes])["2026-11-09"]
    # la pila, al 100 % de 8 a 16 y al 50 % el resto; el venteo, su parte del tiempo repartida todo el día, como en la simulación
    assert d["horas"][8] == pytest.approx(1000 + 3000 * parte) and d["horas"][3] == pytest.approx(500 + 3000 * parte)
    assert d["media"] == pytest.approx((8 * 1000 + 16 * 500) / 24 + 3000 * parte)
    assert d["modelos"]["superficie"][7] == 500 and d["modelos"]["punto"][7] == pytest.approx(3000 * parte)
    assert E.emision_maxima(cat, "olor") == pytest.approx(1000 + 3000 * parte)
    assert E.emision_dias({"focos": {}}, cat, "olor", [lunes]) == E.emision_dias(base, cat, "olor", [lunes])     # sin plan: el de su ficha
    # un gas, en g/s; quien no lo emite no aporta
    assert E.emision_dias(base, cat, "H2S", [lunes])["2026-11-09"]["horas"][8] == pytest.approx(0.5)
    assert E.unidad_emision("olor") == "ou_E/s" and E.unidad_emision("H2S") == "g/s" and E.emision_maxima(cat, "H2S") == pytest.approx(0.5)
    # semanal, con el domingo parado: el día es el oficial (una fecha, sin pasar por UTC), y el plan no cambia
    esc = E.nuevo(cat, "Domingos parada")
    pf = E.plan_foco(pila, esc)
    E.cambiar_plan(pf, "semanal")
    E.poner_perfil(pf, [6], [0.0] * 24)
    antes = json.dumps(esc, sort_keys=True)
    dias = E.emision_dias(esc, cat, "olor", [domingo, lunes])
    assert dias["2026-11-08"]["media"] == pytest.approx(3000 * parte) and dias["2026-11-09"]["media"] == pytest.approx(d["media"])
    # lo de cada foco ese día (la lista de la página Focos): suma lo del calendario; el que no cuenta, None
    por_foco = E.emision_focos_dia(esc, cat, "olor", domingo)
    assert por_foco == {"P": 0.0, "V": pytest.approx(3000 * parte), "R": None}
    lunes_f = E.emision_focos_dia(esc, cat, "olor", lunes)
    assert lunes_f["P"] == pytest.approx((8 * 1000 + 16 * 500) / 24) and sum(v for v in lunes_f.values() if v) == pytest.approx(d["media"])
    assert E.emision_focos_dia(esc, cat, "H2S", lunes) == {"P": pytest.approx(0.5 * 16 / 24), "V": None, "R": None}
    assert json.dumps(esc, sort_keys=True) == antes and E.emision_dias(esc, cat, "olor", []) == {}
    # el calendario: el mes del plan si algún foco lo tiene mensual; si no, del año pasado al que viene
    assert E.dias_calendario(esc, domingo) == (dt.date(2025, 1, 1), dt.date(2027, 12, 31))
    E.cambiar_plan(pf, "mensual", "2027-02")
    esc["mes"] = "2027-02"
    assert E.dias_calendario(esc) == (dt.date(2027, 2, 1), dt.date(2027, 2, 28)) and E.indice_dia(pf, dt.date(2027, 2, 14)) == 13


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
    vals = [F.gases_g_s(_punto(t, [{"gas": "NO2", "valor": 10, "unidad": "ppm"}], caudal_Nm3_h=1000))["NO2"] for t in (25, 127, 400, 800)]
    assert max(vals) / min(vals) - 1 < 1e-12 and vals[0] == pytest.approx(10e-6 * P_ATM * 46.01 / (R_GAS * 273.15) * (1000 / 3600), rel=2e-3)
    assert F.caudal_m3_s(_punto(180, caudal_Nm3_h=1000)) == pytest.approx(1000 / 3600 * 453.15 / 273.15, rel=1e-9)


def test_mg_nm3_y_olor_a_20_grados():
    assert F.gases_g_s(_punto(180, [{"gas": "NO2", "valor": 120, "unidad": "mg/Nm3"}], caudal_Nm3_h=3600))["NO2"] == pytest.approx(0.120, rel=1e-9)
    assert F.gases_g_s(_punto(180, [{"gas": "NO2", "valor": 120, "unidad": "mg/Nm3"}], velocidad_m_s=15))["NO2"] == pytest.approx(120e-3 * (15 * np.pi * 0.25 ** 2) * 273.15 / 453.15, rel=1e-9)
    assert F.olor_ouE_s(_punto(20, olor={"valor": 500, "unidad": "ou_E/m3"}, caudal_m3_h=3600)) == pytest.approx(500.0)
    assert F.olor_ouE_s(_punto(180, olor={"valor": 500, "unidad": "ou_E/m3"}, caudal_m3_h=3600)) == pytest.approx(500 * 293.15 / 453.15)
    assert F.gases_g_s(_punto(20, [{"gas": "H2S", "valor": 1.0, "unidad": "ppm"}])) == {}       # sin caudal, no hay masa


def test_olor_estimado_con_el_gas_dominante_en_el_foco():
    gases = [{"gas": "H2S", "valor": 1.0, "unidad": "g/s"}, {"gas": "NH3", "valor": 1.0, "unidad": "g/s"}]
    f = _punto(20, gases)
    assert F.ug_por_ouE("H2S") == pytest.approx(0.41 * 34.08 / 24.45)
    assert F.gas_dominante(f)[1] == "H2S" and F.olor_ouE_s(f) == pytest.approx(1e6 / F.ug_por_ouE("H2S"))     # máx(gas / umbral): no la suma
    assert F.olor_ouE_s(_punto(20, gases, {"valor": 5, "unidad": "ou_E/s"})) == 5                              # manda la olfatometría
    # los gases de combustión (CO, NOx) no están en la tabla de Nagata: no cuentan (usuario, 2026-11-08: la app es de olores)
    combustion = _punto(20, [{"gas": "NOx", "valor": 1.0, "unidad": "g/s"}, {"gas": "CO", "valor": 1.0, "unidad": "g/s"}])
    assert F.gases_g_s(combustion) == {} and F.olor_ouE_s(combustion) is None and F.emision(combustion, "CO") is None
    assert [m["clave"] for m in F.magnitudes({"focos": [f, combustion]})] == ["olor", "H2S", "NH3"]


def test_los_gases_son_los_223_de_nagata_y_ninguno_mas(tmp_path, monkeypatch):
    # usuario, 2026-11-08: «los gases que se permiten son los que producen olor, es decir los de Nagata: añade todos los gases del artículo»;
    # «la app se centra en dispersión de olores, no de gases de combustión: quítalos». La tabla 2 de Nagata (2003), con los umbrales tal
    # como están impresos y las masas molares de PubChem
    tabla = F.NAGATA["gases"]
    assert len(tabla) == 223 and [g["numero"] for g in tabla] == list(range(1, 224)) and "Nagata" in F.NAGATA["fuente"]
    assert all(g["umbral_ppm"] > 0 and g["masa_molar"] > 0 for g in tabla)
    por_nombre = {g["nombre_nagata"]: g for g in tabla}
    # algunas filas, contra el artículo (pp. 122-123): las del principio y el final de cada columna, y las de umbral extremo
    assert [por_nombre[n]["umbral_ppm"] for n in ("Formaldehyde", "Hydrogen sulfide", "Carbonyl sulfide", "2, 2-Dimethylbutane",
                                                   "2, 3-Dimethylbutane", "Ethyl acetate", "Mthyl acetate", "Tetrachloroethylene")] == \
        [0.50, 0.00041, 0.055, 20.0, 0.42, 0.87, 1.7, 0.77]
    assert por_nombre["Isoamyl mercaptane"]["umbral_ppm"] == 0.00000077 and por_nombre["Propane"]["umbral_ppm"] == 1500.0
    assert por_nombre["Diethyl disulfide"]["umbral_ppm"] == 0.0020                       # impreso «0 0020»
    # las de siempre conservan su clave, su masa y su umbral
    assert F.GASES["H2S"][:2] == pytest.approx((34.08, 0.41)) and F.GASES["NH3"][:2] == pytest.approx((17.03, 1500.0))
    assert F.GASES["CH3SH"][:2] == pytest.approx((48.11, 0.07)) and F.GASES["ESCATOL"][1] == pytest.approx(0.0056)
    assert F.GASES["ISOAMYL_MERCAPTANE"][2] == "Isoamyl mercaptane" and F.NOMBRES["ALFA_PINENE"] == "α-Pinene"
    # cualquiera de ellos estima el olor: 1 ou_E = el umbral en µg (aquí, el acetato de etilo: 0,87 ppm de 88,11 g/mol)
    ac = _punto(20, [{"gas": "ETHYL_ACETATE", "valor": 1.0, "unidad": "g/s"}])
    assert F.olor_ouE_s(ac) == pytest.approx(1e6 / (870.0 * 88.11 / F.VM_25C))
    # ninguno más: el CO y los NOx de una combustión no cuentan y el foco lo dice
    assert len(F.GASES) == 223 and "CO" not in F.GASES and "NOx" not in F.GASES
    mixto = _punto(20, [{"gas": "H2S", "valor": 1.0, "unidad": "g/s"}, {"gas": "CO", "valor": 1.0, "unidad": "g/s"},
                        {"gas": "NOx", "valor": 1.0, "unidad": "g/s"}])
    assert set(F.gases_g_s(mixto)) == {"H2S"} and [m["clave"] for m in F.magnitudes({"focos": [mixto]})] == ["olor", "H2S"]
    assert any("Nagata" in t and "CO, NOx" in t for t in F.pendientes(dict(mixto, ubicacion={"x": 1, "y": 2}, altura_m=5)))
    # sin la tabla, el programa arranca (sin gases) y «Comprobar la herramienta» lo dice: falta, dañada o incompleta
    from teodors.operacion import comprobar as C
    assert C._nagata()[1] == "223 gases con su umbral de olor (Nagata, 2003)"
    monkeypatch.setattr(F, "RUTA_NAGATA", tmp_path / "no_esta.json")
    assert F._nagata() == {"gases": []}
    with pytest.raises(C.Problema) as e:
        C._nagata()
    assert e.value.codigo == "INS-31"
    (tmp_path / "rota.json").write_text("{ no es json", encoding="utf-8")
    monkeypatch.setattr(F, "RUTA_NAGATA", tmp_path / "rota.json")
    with pytest.raises(C.Problema) as e:
        C._nagata()
    assert e.value.codigo == "INS-32"
    corta = dict(F.NAGATA, gases=F.NAGATA["gases"][:200] + [dict(F.NAGATA["gases"][200], umbral_ppm=None)])
    (tmp_path / "corta.json").write_text(json.dumps(corta), encoding="utf-8")
    monkeypatch.setattr(F, "RUTA_NAGATA", tmp_path / "corta.json")
    with pytest.raises(C.Problema) as e:
        C._nagata()
    assert e.value.codigo == "INS-33" and "201 de 223" in e.value.detalle


def test_las_areas_van_por_m2():
    pol = {"modelo": "superficie", "ubicacion": {"poligono": [[0, 0], [40, 0], [40, 25], [0, 25]]}, "altura_m": 2.0, "olor": {"valor": 3.0, "unidad": "ou_E/(s·m2)"}, "gases": [{"gas": "NH3", "valor": 2.0, "unidad": "mg/(s·m2)"}]}
    assert F.area_m2(pol) == 1000.0 and F.olor_ouE_s(pol) == 3000.0 and F.gases_g_s(pol)["NH3"] == pytest.approx(2.0)
    assert F.por_m2(pol, F.olor_ouE_s(pol)) == 3.0 and F.por_m2(pol, None) is None
    modelo, d, q0 = F.geometria(dict(pol, id="A"), lambda x, y: 7.0)
    assert (modelo, q0, d["cota"]) == ("superficie", 1 / 1000.0, 7.0)           # sin esto, ×1000
    d = RS.fuente(dict(pol, id="A"), lambda x, y: 7.0)[1][0]                      # una fuente (una pila larga, varias)
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
    assert len(F.TIPOS) == 13 and not {"antorcha", "motor"} & set(F.TIPOS)        # sin combustión (usuario, 2026-11-08)
    assert "tolva" not in F.TIPOS and "tolva" in F.tipos() and F.tipos()["tolva"] == ("Tolva", ("punto", "volumen"), "continuo")
    cat = F.vacio()
    assert cat["epsg"] == EPSG and cat["planta"] == "Prueba"
    assert F.nuevo(cat, "tolva")["modelo"] == "punto" and F.nombre_tipo({"tipo": "tolva"}) == "Tolva" and F.nombre_tipo({"tipo": "pila"}) == "Pila o hilera de compostaje"
    with pytest.raises(ValueError, match="no previsto"):
        F.nuevo(cat, "tolva", "superficie")
    # usuario, 2026-11-09: cada foco nace con su operación por defecto, la de su tipo; sin tipo (el editor), continuo; y es la de la Base
    from teodors.operacion import planes as E
    assert F.nuevo(cat, "pila")["funcionamiento"] == {"modo": "horario"} and F.nuevo(cat, "venteo")["funcionamiento"] == {"modo": "eventos"}
    for modelo in F.MODELOS:
        f = F.nuevo(cat, None, modelo)
        assert f["funcionamiento"] == F.funcionamiento_defecto(f) == {"modo": "continuo"}
        cat["focos"].append(f)
    assert all(pf == {"plan": "diario", "perfiles": [[1.0] * 24], "dias": [0]} for pf in E.base(cat)["focos"].values())
    assert sorted(E.base(cat)["focos"]) == ["F01", "F02", "F03"]


def test_copiar_la_operacion_de_un_foco_a_otros_del_mismo_tipo():
    # usuario, 2026-11-09: «copiar una operabilidad de un foco, del mismo tipo, a otro: por ejemplo, pila 1 a pila 2»
    pila1, pila2 = ({"id": i, "modelo": "volumen", "volumen": {"clase": "pila"}} for i in ("F05", "F06"))
    nave = {"id": "F07", "modelo": "volumen", "volumen": {"clase": "nave"}}
    balsa1, balsa2 = ({"id": i, "modelo": "superficie", "superficie": {"clase": "balsa"}} for i in ("F02", "F03"))
    tanque = {"id": "F01", "modelo": "superficie", "superficie": {"clase": "tanque"}}
    assert F.mismo_tipo(pila1, pila2) and F.mismo_tipo(balsa1, balsa2) and F.mismo_tipo({"modelo": "punto"}, {"modelo": "punto"})
    assert not F.mismo_tipo(pila1, nave) and not F.mismo_tipo(balsa1, tanque) and not F.mismo_tipo(pila1, balsa1)
    assert F.mismo_tipo({"tipo": "lavador", "modelo": "punto"}, {"tipo": "lavador", "modelo": "punto"})        # con tipo, el tipo
    assert not F.mismo_tipo({"tipo": "lavador", "modelo": "punto"}, {"tipo": "soplador", "modelo": "punto"})
    assert (F.nombre_clase(pila1), F.nombre_clase(balsa1), F.nombre_clase(tanque), F.nombre_clase({"modelo": "punto"})) == (
        "Pila o hilera", "Balsa o piscina", "Tanque abierto", F.MODELOS["punto"])
    semana = {"plan": "semanal", "perfiles": [[1.0] * 24, [0.0] * 24], "dias": [0, 0, 0, 0, 0, 1, 1]}
    esc = {"focos": {"F05": json.loads(json.dumps(semana)), "F06": {"plan": "diario", "perfiles": [[0.5] * 24], "dias": [0]}}}
    E.copiar_operacion(esc, "F05", ["F06", "F07", "F05"])                  # a una que ya tenía la suya, a otra que no figuraba, y a sí misma
    assert esc["focos"]["F05"] == esc["focos"]["F06"] == esc["focos"]["F07"] == semana
    E.poner_perfil(esc["focos"]["F06"], [5], [0.5] * 24)                    # cada una, con su copia
    assert esc["focos"]["F05"] == esc["focos"]["F07"] == semana and esc["focos"]["F06"]["dias"] == [0, 0, 0, 0, 0, 2, 1]


# una nave de 10 m de alto, de 20 a 50 m al este de la chimenea y 30 m de ancho
NAVE_ESTE = {"ref": "N1", "verts": [(20.0, -15.0), (50.0, -15.0), (50.0, 15.0), (20.0, 15.0)], "altura_m": 10.0, "fuente": "LiDAR", "dist_m": 20.0}


def test_la_estela_de_una_nave_al_este_por_direccion():
    # usuario, 2026-11-08: los edificios no se escriben, los pone el código. La chimenea de 12 m queda en la estela de la nave con el viento del
    # este (saldría libre a 10 + 1,5·10 = 25 m) y no con el del norte; las 36 direcciones del motor son las del vector de flujo
    est = ES.calcular(0.0, 0.0, 12.0, [NAVE_ESTE])
    assert all(len(est[c]) == 36 for c in ES.CLAVES) and est["gep_m"] == pytest.approx(25.0)
    k = ES.sector_flujo(90.0)                                       # el viento del este va hacia el oeste: 270°
    assert k == 26 and est["hb"][k] == 10.0 and est["xadj"][k] < 0                # la nave, a barlovento de la chimenea
    filas = {f["desde"]: f for f in ES.por_viento(est, 12.0)}
    assert filas[90.0]["dentro"] and filas[90.0]["libre_m"] == pytest.approx(25.0)
    assert not filas[360.0]["dentro"] and filas[360.0]["alto"] == 0.0
    assert ES.resumen(est, 30.0)[0] == 0 and ES.resumen(est, 12.0) == (sum(f["dentro"] for f in filas.values()), pytest.approx(25.0))
    assert ES.para_motor(est)["HEIGHT"] == est["hb"] and ES.para_motor({"hb": [0.0] * 36}) is None and ES.para_motor(None) is None
    assert ES.calcular(0.0, 0.0, 12.0, []) is None and ES.calcular(0.0, 0.0, None, [NAVE_ESTE]) is None
    assert est["edificios"] == [{"ref": "N1", "altura_m": 10.0, "fuente": "LiDAR", "dist_m": 20.0}]
    assert ES.angulo_texto(90.0) == "E" and ES.angulo_texto(360.0) == "N" and ES.angulo_texto(225.0) == "SO"


def test_los_edificios_de_alrededor_con_la_altura_del_lidar_y_si_no_la_del_catastro(monkeypatch):
    # el Catastro da plantas × 3 m (y en una planta industrial, cualquier cosa): manda el LiDAR donde llega; bajo un tejado no hay suelo,
    # y la altura se cuenta desde el de alrededor
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Polygon
    cuadro = lambda x, y, l: Polygon([(x, y), (x + l, y), (x + l, y + l), (x, y + l)])        # noqa: E731
    bld = gpd.GeoDataFrame({"ref": ["A", "B", "C"], "altura_m": [24.0, 6.0, 9.0]},
                           geometry=[cuadro(1010.0, 2010.0, 20.0), cuadro(1100.0, 2000.0, 10.0), cuadro(1040.0, 2040.0, 5.0)], crs=EPSG)
    n = 60
    dtm, dsm, dsm_edif = np.full((n, n), 100.0), np.full((n, n), 100.0), np.full((n, n), -np.inf)
    dtm[10:30, 10:30] = np.inf                                  # A: sin suelo bajo el tejado; su tejado, a 111 m
    dsm_edif[10:30, 10:30] = 111.0
    dsm[40:45, 40:45] = 101.0                                   # C: el LiDAR ve 1 m (el Catastro, 9 m)
    monkeypatch.setattr(ES, "_descargados", lambda: bld)
    monkeypatch.setattr(ES, "_lidar", lambda: {"dsm": dsm, "dsm_edif": dsm_edif, "dtm": dtm, "x0": 1000.0, "y0": 2000.0})
    ed = ES.edificios_cerca(1005.0, 2005.0)
    assert [(e["ref"], e["altura_m"], e["fuente"]) for e in ed] == [("A", 11.0, "LiDAR"), ("B", 6.0, "descargados")]     # B, fuera del LiDAR
    assert ed[0]["dist_m"] == pytest.approx(7.1, abs=0.1) and len(ed[0]["verts"]) == 4
    monkeypatch.setattr(ES, "_descargados", lambda: None)
    assert ES.edificios_cerca(1005.0, 2005.0) == []


def test_precargar_deja_las_alturas_hechas_y_mover_la_chimenea_no_las_rehace(monkeypatch):
    # usuario, 2026-11-08: «¿qué tal se actualiza el visor 3D de cambiar un punto a otro?»: la altura de cada huella se mide una vez
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Polygon
    x, y = geo.a_utm(LAT, LON)
    bld = gpd.GeoDataFrame({"ref": ["A"], "altura_m": [9.0]}, geometry=[Polygon([(x + 10, y), (x + 30, y), (x + 30, y + 20), (x + 10, y + 20)])], crs=EPSG)
    medidas = []
    monkeypatch.setattr(ES, "_descargados", lambda: bld)
    monkeypatch.setattr(ES, "_lidar", lambda: None)
    real = ES._altura_lidar
    monkeypatch.setattr(ES, "_altura_lidar", lambda g, lidar: medidas.append(1) or real(g, lidar))
    ES.precargar()
    assert ES._cache_alturas[(0, 0)] == (9.0, "descargados") and ES._cache_alturas["de"][0] is bld
    for dx in (0.0, 5.0, 12.0):                                                      # mover la chimenea: ya están
        assert [e["ref"] for e in ES.edificios_cerca(x - dx, y)] == ["A"]
    otros = bld.copy()
    monkeypatch.setattr(ES, "_descargados", lambda: otros)                          # otros edificios: se vuelven a medir
    ES.edificios_cerca(x, y)
    assert ES._cache_alturas["de"][0] is otros


def test_los_edificios_de_la_planta_por_tres_caminos(monkeypatch):
    # usuario, 2026-11-08: «configurar los edificios vía 3 caminos: Catastro, LiDAR y dibujar/modificar desde el usuario de CIRCE»
    gpd = pytest.importorskip("geopandas")
    from shapely.geometry import Point, Polygon
    from teodors.operacion import edificios_planta as EP
    cuadro = lambda x, y, l: Polygon([(x, y), (x + l, y), (x + l, y + l), (x, y + l)])        # noqa: E731
    # A, una nave que el LiDAR ve (11 m; el Catastro dice 24); B, fuera del LiDAR (6 m del Catastro); C, una era que el LiDAR no ve como
    # edificio; y D, un edificio que el LiDAR ve (7 m) y el Catastro no tiene
    bld = gpd.GeoDataFrame({"ref": ["A", "B", "C"], "altura_m": [24.0, 6.0, 9.0]},
                           geometry=[cuadro(1010.0, 2010.0, 20.0), cuadro(1100.0, 2000.0, 10.0), cuadro(1045.0, 2005.0, 10.0)], crs=EPSG)
    n = 60
    dtm, dsm, dse = np.full((n, n), 100.0), np.full((n, n), 100.0), np.full((n, n), -np.inf)
    dtm[10:30, 10:30], dse[10:30, 10:30] = np.inf, 111.0
    dtm[40:50, 5:15], dse[40:50, 5:15] = np.inf, 107.0
    dsm[5:15, 45:55] = 101.0
    lidar = {"dsm": dsm, "dsm_edif": dse, "dtm": dtm, "x0": 1000.0, "y0": 2000.0}
    monkeypatch.setattr(ES, "_descargados", lambda: bld)
    monkeypatch.setattr(ES, "_lidar", lambda: lidar)
    n = EP.nombre_origen("catastro")                                                 # el de la fuente de la planta; esta no tiene: «descargados»
    assert n == "descargados" and EP.nombre_origen("lidar") == "LiDAR" and EP.nombre_origen("dibujo") == "Dibujado"
    cat = EP.desde_catastro(1005.0, 2005.0, 200.0)
    # se llaman por su forma, del más alto al más bajo; la referencia descargada, aparte
    assert [(e["nombre"], e["origen"], e["altura_m"], e.get("ref")) for e in cat] == [("Edificio 1", "catastro", 24.0, "A"),
                                                                                     ("Edificio 3", "catastro", 6.0, "B"),
                                                                                     ("Edificio 2", "catastro", 9.0, "C")]
    lid = EP.desde_lidar(1005.0, 2005.0, 200.0)
    assert [(e["nombre"], e["origen"], e["altura_m"], e.get("ref")) for e in lid] == [("Edificio 1", "lidar", 11.0, "A"),
                                                                                     ("Edificio 3", "catastro", 6.0, "B"),
                                                                                     ("Edificio 2", "lidar", 7.0, None)]
    assert EP.redondo(Point(0, 0).buffer(7.0)) and not EP.redondo(cuadro(0.0, 0.0, 10.0))         # un digestor, «Depósito N»
    assert EP._nombrar([{"altura_m": 9.0, "poligono": list(Point(0, 0).buffer(7.0).exterior.coords)[:-1]}])[0]["nombre"] == "Depósito 1"
    assert EP.area_m2(lid[2]) == pytest.approx(100.0, rel=0.1) and EP.altura_lidar([[1012, 2012], [1028, 2012], [1028, 2028], [1012, 2028]]) == 11.0
    # importar: los dibujados se quedan y lo importado que los pisa, fuera
    datos = EP.vacio()
    datos["edificios"] = [{"id": "E01", "nombre": "Nave B", "origen": "dibujo", "poligono": [[1100, 2000], [1110, 2000], [1110, 2010], [1100, 2010]],
                           "altura_m": 8.0}]
    datos = EP.importar(EP.importar(datos, cat), lid)                               # el LiDAR, en lugar del Catastro
    assert [(e["id"], e["nombre"], e["origen"]) for e in datos["edificios"]] == [("E01", "Nave B", "dibujo"), ("E02", "Edificio 1", "lidar"),
                                                                                ("E03", "Edificio 2", "lidar")]
    assert not EP.hay() and EP.resumen(datos) == {"total": 3, "por_origen": {"catastro": 0, "lidar": 2, "dibujo": 1}}
    EP.guardar(datos)
    assert EP.hay() and EP.cargar()["edificios"] == datos["edificios"] and EP.ruta().parent == planta.actual().PLANTA
    # con edificios propios, la estela usa solo esos
    cerca = ES.edificios_cerca(1005.0, 2005.0)
    assert [(e["ref"], e["fuente"], e["altura_m"]) for e in cerca] == [("E02", "LiDAR", 11.0), ("E03", "LiDAR", 7.0), ("E01", "Dibujado", 8.0)]
    # y al cambiarlos, la estela guardada en los focos punto se rehace
    cat_focos = F.vacio()
    cat_focos["focos"] = [{"id": "F01", "nombre": "Chimenea", "tipo": None, "modelo": "punto", "ubicacion": {"x": 1005.0, "y": 2005.0}, "altura_m": 12.0,
                           "salida": {"diametro_m": 0.5, "velocidad_m_s": 10.0, "temperatura_C": 20.0}}]
    F.guardar(cat_focos)
    assert EP.recalcular_focos() == ["F01"] and F.cargar()["focos"][0]["edificios"]["hb"] and EP.recalcular_focos() == []


def test_las_superficies_balsa_tanque_abierto_y_biofiltro():
    # usuario, 2026-11-08: «focos de superficies, desde piscinas, superficies de tanques abiertos»: como en AERMOD y CALPUFF, una fuente de
    # área (contorno, altura de emisión y emisión por m²); su clase da la altura por defecto y la unidad de su olfatometría
    from teodors.operacion import edificios_planta as EP
    f = F.nuevo(F.vacio(), None, "superficie")
    assert f["superficie"] == {"clase": "balsa"} and f["altura_m"] == 0.0 and f["olor"] == {"unidad": "ou_E/m3"}       # como un punto
    assert F.subtitulo(f) == f"Balsa o piscina · Superficie · {f['id']}" and F.clase_superficie(f) == "balsa"
    bio = dict(f, superficie={"clase": "biofiltro"})
    assert F.es_biofiltro(bio) and F.unidad_olor(bio) == "ou_E/m3" and not F.es_biofiltro(f) and F.unidad_olor({"modelo": "volumen"}) == "ou_E/m3"
    assert F.clase_superficie({"modelo": "superficie", "tipo": "biofiltro"}) == "biofiltro"        # los de catálogo, por su tipo
    assert F.nuevo(F.vacio(), "pila", "superficie").get("superficie") is None                      # y sin clase
    # un tanque abierto en la boca de un edificio de la planta: su contorno y su altura, enlazados
    tanque = {"id": "E05", "nombre": "Depósito 4", "origen": "lidar", "altura_m": 6.2,
              "poligono": [[500000.0, 4500000.0], [500010.0, 4500000.0], [500010.0, 4500010.0], [500000.0, 4500010.0]]}
    f["superficie"]["clase"] = "tanque"
    assert F.poner_sobre(f, tanque) and not F.poner_sobre(f, tanque)                                 # la 2.ª vez, nada cambia
    assert f["altura_m"] == 6.2 and f["superficie"]["sobre"] == "E05" and F.area_m2(f) == pytest.approx(100.0)
    m, d, q0 = F.geometria(f, lambda x, y: 50.0)
    assert m == "superficie" and d["h"] == 6.2 and d["cota"] == 50.0 and len(d["verts"]) == 4 and q0 == pytest.approx(0.01)   # por m²
    # al guardar los edificios, la boca sigue a su edificio; si el edificio ya no está, se queda como estaba, sin el enlace
    EP.guardar(dict(EP.vacio(), edificios=[dict(tanque, altura_m=7.0)]))
    f["id"] = "F01"
    F.guardar(dict(F.vacio(), focos=[f]))
    assert EP.recalcular_focos() == ["F01"] and F.cargar()["focos"][0]["altura_m"] == 7.0 and EP.recalcular_focos() == []
    EP.guardar(dict(EP.vacio(), edificios=[]))
    assert EP.recalcular_focos() == ["F01"]
    g = F.cargar()["focos"][0]
    assert "sobre" not in g["superficie"] and g["altura_m"] == 7.0 and F.area_m2(g) == pytest.approx(100.0)


def test_los_volumenes_pila_de_compost_y_nave():
    # usuario, 2026-11-08: «pasamos a volúmenes donde añadiremos las pilas de compostaje». Como en AERMOD: altura de emisión a media altura,
    # σz0 = alto/2,15; una pila emite por su piel y, alargada, va al motor como una fila de volúmenes contiguos (σy0 = lado/2,15)
    import math
    p = F.nuevo(F.vacio(), None, "volumen")
    assert p["volumen"] == {"clase": "pila", "seccion": "hilera"} and F.clase(p) == "pila" and F.unidad_gas(p) == "ppm"
    assert F.subtitulo(p).startswith("Pila o hilera · Volumen") and F.altura_emision(p) is None and F.seccion(p) is None
    p.update(ubicacion={"x": 1000.0, "y": 2000.0})
    p["dimensiones"].update(largo_m=40.0, ancho_m=6.0, alto_m=3.0, orientacion_deg=90.0)              # una hilera de este a oeste
    assert F.seccion(p) == [(-3.0, 0.0), (3.0, 0.0), (0.0, 3.0)] and F.altura_emision(p) == 1.5
    talud = math.hypot(3.0, 3.0)
    assert F.piel_m2(p) == pytest.approx(40 * 2 * talud + 2 * 9.0) and F.area_m2(p) == F.piel_m2(p)       # sus taludes y sus testeros
    meseta = dict(p, volumen={"clase": "pila", "seccion": "meseta"}, dimensiones=dict(p["dimensiones"], ancho_m=10.0))
    assert F.seccion(meseta) == [(-5.0, 0.0), (5.0, 0.0), (2.0, 3.0), (-2.0, 3.0)]                     # cima de 4 m, taludes a 45°
    partes = F.partes_volumen(p)                                                    # 40 / 6 → 7 volúmenes de 5,7 m, a lo largo del eje E-O
    assert len(partes) == 7 and all(y == pytest.approx(2000.0) for _, y, _ in partes)
    assert partes[0][0] == pytest.approx(1000.0 - 20.0 + 40 / 14) and partes[0][2] == pytest.approx(40 / 7 / 2.15)
    fuentes = F.fuentes_motor(dict(p, id="F05"), lambda x, y: 50.0)
    assert [d["id"] for _, d, _ in fuentes] == [f"F05_{k:02d}" for k in range(1, 8)] and sum(q for _, _, q in fuentes) == pytest.approx(1.0)
    assert all(m == "volumen" and d["h"] == 1.5 and d["sz0"] == pytest.approx(3.0 / 2.15) for m, d, _ in fuentes)
    m, ds = RS.fuente(dict(p, id="F05"), lambda x, y: 50.0)
    assert m == "volumen" and len(ds) == 7 and sum(d["q"]["H00"] for d in ds) == pytest.approx(1.0)        # 1 g/s entre todos
    # su gas de salida, como en un punto: por m² de su piel
    p["salida"].update(caudal_m3_m2_h=3.6, temperatura_C=40.0)
    assert F.caudal_m3_s(p) == pytest.approx(F.piel_m2(p) * 1e-3)
    # una nave: un volumen solo, su planta, su caudal de ventilación
    nave = dict(p, volumen={"clase": "nave"}, id="F06")
    assert F.area_m2(nave) == 240.0 and len(F.partes_volumen(nave)) == 1 and len(F.fuentes_motor(nave, lambda x, y: 50.0)) == 1
    assert F.fuentes_motor(nave, lambda x, y: 50.0)[0][1]["sy0"] == pytest.approx(math.sqrt(240.0) / 4.3)
    assert F.poner_gases_tipicos(nave) == 7 and "AC_BUTIRICO" in {g["gas"] for g in nave["gases"]}


def test_una_superficie_se_define_por_sus_gases():
    # usuario, 2026-11-08: «quiero que definas los focos de superficie no por olor sino por gases»: lo que emite cada gas por m² (cámara de
    # flujo), en mg/(m²·h) o g/(m²·d); el olor sale del gas con más veces su umbral (Nagata)
    balsa = F.nuevo(F.vacio(), None, "superficie")
    balsa["ubicacion"] = {"poligono": [[0, 0], [100, 0], [100, 10], [0, 10]]}                      # 1 000 m²
    assert F.unidad_gas(balsa) == "ppm" and {"ppm", "mg/m3", "mg/(m2·h)", "g/(m2·d)"} <= set(F.unidades_gas(balsa))   # como un punto, o por m²
    assert F.poner_gases_tipicos(balsa) == 6 and F.poner_gases_tipicos(balsa) == 0                     # una sola vez cada uno
    assert [g["gas"] for g in balsa["gases"]] == ["NH3", "H2S", "CH3SH", "DMS", "DMDS", "P_CRESOL"]
    assert all(g["valor"] is None and g["unidad"] == "ppm" for g in balsa["gases"]) and F.olor_ouE_s(balsa) is None
    balsa["gases"][0].update(valor=36.0, unidad="mg/(m2·h)")           # NH3: 36 mg/(m²·h) = 10 µg/(s·m²) → 10 mg/s en 1 000 m²
    balsa["gases"][1].update(valor=0.864, unidad="g/(m2·d)")           # H2S: 0,864 g/(m²·d) = 10 µg/(s·m²)
    gs = F.gases_g_s(balsa)
    assert gs == {"NH3": pytest.approx(0.01), "H2S": pytest.approx(0.01)}
    q, gas = F.gas_dominante(balsa)
    assert gas == "H2S" and q == pytest.approx(0.01 * 1e6 / F.ug_por_ouE("H2S")) and F.olor_ouE_s(balsa) == pytest.approx(q)   # el H₂S manda
    # un biofiltro: lo de su salida (con el caudal tratado) o por m², y sus terpenos
    bio = dict(F.nuevo(F.vacio(), None, "superficie"), superficie={"clase": "biofiltro"})
    assert F.unidad_gas(bio) == "ppm" and "mg/m3" in F.unidades_gas(bio) and "mg/(m2·h)" in F.unidades_gas(bio)
    F.poner_gases_tipicos(bio)
    assert {"ALFA_PINENE", "LIMONENE"} <= {g["gas"] for g in bio["gases"]}
    assert F.unidad_gas({"modelo": "punto"}) == "ppm" and "mg/(m2·h)" not in F.unidades_gas({"modelo": "punto"})
    # en concentración, como un punto (usuario, 2026-11-08: «falta velocidad o caudal por área; además de temperatura y gases de salida»):
    # por su caudal por m² (m³/(m²·h)), su área y su temperatura
    conc = F.nuevo(F.vacio(), None, "superficie")
    conc["ubicacion"] = balsa["ubicacion"]
    assert set(conc["salida"]) == {"caudal_m3_m2_h", "temperatura_C", "composicion"} and F.caudal_m3_s(conc) is None
    conc["gases"] = [{"gas": "H2S", "valor": 2.0, "unidad": "mg/m3"}]
    assert "caudal por m² o caudal de salida (sus gases van en concentración)" in F.pendientes(conc) and "temperatura de salida" in F.pendientes(conc)
    conc["salida"].update(caudal_m3_m2_h=3.6, temperatura_C=20.0)       # 3,6 m³/(m²·h) = 1 L/(s·m²) → 1 m³/s en 1 000 m²
    assert F.caudal_m3_s(conc) == pytest.approx(1.0) and F.gases_g_s(conc) == {"H2S": pytest.approx(2e-3)}
    assert not [p for p in F.pendientes(conc) if "caudal" in p or "temperatura" in p]


def test_el_punto_lleva_al_motor_su_estela_y_su_orientacion():
    est = ES.calcular(0.0, 0.0, 12.0, [NAVE_ESTE])
    pun = {"id": "P", "modelo": "punto", "altura_m": 12.0, "ubicacion": {"x": 0.0, "y": 0.0}, "edificios": est,
           "salida": {"diametro_m": 1.0, "velocidad_m_s": 10.0, "temperatura_C": 20.0, "orientacion": "sombrerete"}}
    d = F.geometria(pun, lambda x, y: 0.0)[1]
    assert d["fmfac"] == 0.0 and d["edif"]["HEIGHT"] == est["hb"] and d["edif"]["YBADJ"] == est["yadj"]   # con sombrerete, sin impulso
    sin = dict(pun, salida=dict(pun["salida"], orientacion="vertical"))
    del sin["edificios"]
    d = F.geometria(sin, lambda x, y: 0.0)[1]
    assert d["fmfac"] == 1.0 and d["edif"] is None
    assert F.huella(dict(sin, edificios=est)) != F.huella(sin)                  # la estela cambia la respuesta: hay que volver a simularlo
    nuevo = F.nuevo(F.vacio(), "lavador")
    assert nuevo["salida"]["orientacion"] == "vertical" and "edificio" not in nuevo and set(F.ORIENTACIONES) == {"vertical", "sombrerete", "horizontal", "abajo"}


def test_la_densidad_del_gas_de_salida_sale_de_su_composicion():
    # usuario, 2026-11-08: «para el gas de salida poner CO₂, CO, metano, H₂, etano y su composición para calcular la densidad». Gas ideal a 1 atm
    def punto(comp, t=20.0, **salida):
        return {"modelo": "punto", "id": "P", "altura_m": 10.0, "ubicacion": {"x": 0.0, "y": 0.0},
                "salida": {"diametro_m": 0.5, "temperatura_C": t, "composicion": comp, **salida}}
    # «añade O₂ y N₂, no aire»: sin el campo, la de un aire de ventilación (N₂ 79 %, O₂ 21 %), que el motor trata como aire
    m_ref = 0.79 * 28.014 + 0.21 * 31.998
    sin = punto(None)
    del sin["salida"]["composicion"]
    assert F.composicion(sin) == {"N2": 79.0, "O2": 21.0} and F.masa_molar_salida(sin) == pytest.approx(m_ref)
    assert F.densidad_salida(sin) == pytest.approx(P_ATM * m_ref / 1000 / (R_GAS * 293.15)) and F.temperatura_equivalente_K(sin) == pytest.approx(293.15)
    assert F.nuevo(F.vacio(), None, "punto")["salida"]["composicion"] == {"N2": 79.0, "O2": 21.0}
    biogas = punto({"CH4": 60.0, "CO2": 40.0})
    assert F.masa_molar_salida(biogas) == pytest.approx(0.6 * 16.043 + 0.4 * 44.009)
    assert F.masa_molar_salida(punto({"CH4": 60.0, "CO2": 39.5})) == pytest.approx((60 * 16.043 + 39.5 * 44.009) / 99.5)    # ± 1 %: se reparte
    co2 = punto({"CO2": 100.0})
    assert F.densidad_salida(co2) == pytest.approx(P_ATM * 44.009e-3 / (R_GAS * 293.15))
    # el motor solo mira la temperatura: la de un aire con su densidad (el CO₂ a 20 °C, como un aire a −80 °C: no sube)
    assert F.temperatura_equivalente_K(co2) == pytest.approx(293.15 * m_ref / 44.009)
    assert F.geometria(dict(co2, salida=dict(co2["salida"], velocidad_m_s=5.0)), lambda x, y: 0.0)[1]["t"] == pytest.approx(293.15 * m_ref / 44.009)
    # el caudal másico pasa a volumen con su densidad
    q = F.caudal_m3_s(punto({"CO2": 100.0}, caudal_kg_h=3600.0))
    assert q == pytest.approx(1.0 / F.densidad_salida(co2))
    for malo in (punto({"CO2": 70.0, "CH4": 40.0}), punto({"CO2": 50.0}), punto({})):          # pasa, no llega, vacía
        assert F.masa_molar_salida(malo) is None and F.densidad_salida(malo) is None and any("composición" in t for t in F.pendientes(malo))
    assert list(F.GAS_SALIDA) == ["CO2", "CO", "CH4", "H2", "C2H6", "O2", "N2"]


def test_un_foco_del_editor_no_tiene_tipo_y_su_nombre_no_se_repite():
    # usuario, 2026-11-08: la actividad es el nombre, y «que no se pisen los nombres al crear nuevos equipos»
    cat = F.vacio()
    f = F.nuevo(cat, None, "volumen")
    assert (f["tipo"], f["nombre"], f["modelo"], f["funcionamiento"]["modo"]) == (None, "", "volumen", "continuo") and "dimensiones" in f
    assert F.nombre_tipo(f) == "Volumen" and F.subtitulo(f) == "Pila o hilera · Volumen · F01" and "nombre" in F.pendientes(f)
    assert F.subtitulo(dict(f, tipo="pila", modelo="superficie")) == "Pila o hilera de compostaje · Superficie · F01"
    cat["focos"].append(dict(f, nombre="Nave de recepción"))
    otro = F.nuevo(cat, None, "punto")
    assert otro["id"] == "F02" and F.nombre_repetido(cat, otro) is None
    otro["nombre"] = "  nave DE   recepción "
    assert F.nombre_repetido(cat, otro)["id"] == "F01"
    assert F.nombre_repetido(cat, cat["focos"][0]) is None                       # consigo mismo, no


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
    # con el código original y estos datos, sin cambiar nada de lo que se hash: si estos valores cambian, se invalidan todas las simulaciones guardadas.
    # Cambiaron el 2026-11-08, a propósito: la plantilla nacional de normativa ya no tiene el CO ni los NOx (usuario: la app es de olores), y
    # una simulación guardada con ellos no vale (antes: e5c2758928cbebbb47c9c1581d8ba35ca0d685b0 y 8202b855a0df6fab9a1dd9bb9f9cbbc19f075d0f)
    # Y el 2026-11-09, a propósito: el formato 2 guarda las isolíneas rellenas de cada capa, que lo anterior no tiene, y el 3, todos los
    # pueblos, cada uno con su tipo (antes: 0ed3a2660657130fd779f699d850dcf0352418eb y 6b83a28f8c17bec725fcca80d88679036d5642c3)
    assert S.firma(ESC_FIRMA, CAT_FIRMA) == "1c274a61eaec0835e35131440a17ae43d953ca16"
    assert S.firma(ESC_FIRMA, CAT_FIRMA, PERIODO_FIRMA) == "790d6f8154f6b5e376fcf661b0617976f000d96e"


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
    assert periodos.listo(r) and S.dir_respuestas() is None                    # ni un día suelto ni un episodio son la serie del reanálisis
    assert periodos.dias_reanalisis() == {"2023-03-10": "serie_b"} and S.periodo_reanalisis() is None
    with pytest.raises(RuntimeError, match="Aún no hay respuestas"):
        S.calcular(E.nuevo({"focos": []}, "x"), {"focos": []})
    _guarda_serie([_foco("F01")], lambda i, t, r_: 0.0, fin="2023-01-02")
    assert S.dir_respuestas() == planta.DIR_DISPERSION == planta.PLANTA.parent / "dispersion" and S.disponible()
    shutil.rmtree(periodos.dir_respuestas(r))


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


def test_comprobar_la_herramienta_da_un_codigo_por_cada_problema(tmp_path, monkeypatch, caplog):
    # usuario, 2026-11-07: categorías genéricas en el panel y un código por cada problema, «para que si el cliente me dice me sale error de
    # código tal, saber qué es lo que le está fallando»
    from teodors.fuentes import era5
    from teodors.operacion import comprobar as C
    # el catálogo: cada código, de una categoría y con un elemento y un «qué pasa» de los suyos; y lo dice el README
    cats = [c for c, _ in C.CATEGORIAS]
    assert cats == ["INS", "ENT", "VIE", "DIS", "MET", "RED"]
    for codigo, (grav, que, hacer) in C.CODIGOS.items():
        cat, num = codigo.split("-")
        assert cat in cats and len(num) == 2 and int(num[0]) in C.ELEMENTOS[cat] and int(num[1]) in C.QUE_PASA, codigo
        assert grav in (C.AVISO, C.FALLO) and que and hacer.endswith("."), codigo
    readme = (OPERACION / "README.md").read_text(encoding="utf-8")
    assert all(f"**{c}**" in readme for c in C.CODIGOS) and C.catalogo().split("\n### ")[1].splitlines()[0] == "INS · Instalación"
    usados = set(re.findall(r"[\"']([A-Z]{3}-\d\d)[\"']", (OPERACION / "comprobar.py").read_text(encoding="utf-8").split("\ndef pedir")[1]))
    assert usados <= set(C.CODIGOS) and set(C.CODIGOS) - usados == set(), set(C.CODIGOS) - usados     # ninguno sin usar
    assert C.tesela("https://x/{z}/{x}/{y}.png", 0.0, 0.0, z=1) == "https://x/1/1/1.png" and C.tesela("{z}/{x}/{y}", 85.0, -179.9, z=2) == "2/0/0"
    assert C.estado_de([]) == "ok" and C.estado_de(["ENT-31"]) == "aviso" and C.estado_de(["ENT-31", "VIE-01"]) == "fallo"
    # sin nada: cada problema con su código, en su categoría; el motor no se lanza de verdad
    monkeypatch.setattr(C, "_subproceso", lambda *a: (0.1, ""))
    monkeypatch.setattr(C, "_programa", lambda: ([], "Versión X"))
    avance = []
    caplog.set_level("INFO")
    r = C.ejecutar(sin_red=True, progreso=lambda k, n, x: avance.append((k, n, x["estado"])))
    cod = {x["clave"]: [c for c, _ in x["codigos"]] for x in r["resultados"]}
    assert len(avance) == 36 and avance[0] == (0, 18, "en_curso") and avance[-1][:2] == (18, 18)
    assert cod["trabajo"] == ["INS-11"] and cod["terreno"] == ["ENT-11"] and cod["edificios"] == ["ENT-21"] and cod["focos"] == ["ENT-31"]
    assert cod["viento3d"] == ["VIE-01"] and cod["respuestas"] == ["DIS-01"] and cod["local"] == cod["planes"] == cod["viento_local"] == cod["nagata"] == []
    assert cod["informe"] == []                                   # su motor está; sin casos guardados, nada más que mirar
    assert r["categorias"]["INS"] == {"estado": "fallo", "codigos": ["INS-11"]} and r["categorias"]["ENT"]["codigos"] == ["ENT-11", "ENT-21", "ENT-31"]
    assert "MET" not in r["categorias"] and (r["ok"], r["aviso"], r["fallo"]) == (0, 0, 4)
    assert any(m.startswith("✗ VIE-01 · No hay viento 3D") and "Qué hacer: Recuperar la carpeta viento/3d" in m for m in caplog.messages)
    assert any(m.startswith("⚠ ENT-31 · No hay focos") for m in caplog.messages)
    # con la carpeta de trabajo y un mes de viento: INS y el viento, bien; faltan los meses de antes y después de ese, no: es uno solo
    cab, fecha = _serie_viento("serie_b")
    r = C.ejecutar(sin_red=True)
    cod = {x["clave"]: x for x in r["resultados"]}
    assert cod["trabajo"]["codigos"] == [] and cod["viento3d"]["codigos"] == [] and f"{fecha:%m/%Y}" in cod["viento3d"]["texto"]
    # un foco sin emisión o sin sitio (los de superficie, con su polígono, sí tienen sitio)
    F.guardar({"formato": F.FORMATO, "epsg": planta.EPSG_UTM, "focos": [
        _foco(1), dict(_foco(2), ubicacion={"poligono": [[0, 0], [10, 0], [10, 10]]}), dict(_foco(3), olor={}), dict(_foco(4), ubicacion={})]})
    assert C._focos() == ([("ENT-33", "Foco 3, Foco 4")], "4 focos")
    (planta.PLANTA / "focos.json").write_text("{", encoding="utf-8")
    with pytest.raises(C.Problema) as e:
        C._focos()
    assert e.value.codigo == "ENT-32"
    # una prueba que revienta sin código no para las demás; y se puede cancelar
    monkeypatch.setattr(C, "_planes", lambda: 1 / 0)
    r = C.ejecutar(sin_red=True)
    assert {x["clave"]: x["texto"] for x in r["resultados"]}["planes"].startswith("No se pudo comprobar: ZeroDivisionError") and len(r["resultados"]) == 18
    assert C.ejecutar(sin_red=True, cancelado=lambda: True)["resultados"] == []
    # los servicios, sin red de verdad: lo que responderían
    pedidas = []

    def pedir(url, cabeza=False, cuanto=4096):
        pedidas.append((url, cabeza))
        if "transparenciacatalunya" in url:
            return 200, "application/json", b"[{}]"
        if "copernicus" in url:
            return 200, "application/json", b"{}"
        if "noaa" in url:
            return 200, "binary/octet-stream", b""
        raise OSError("sin conexión")
    monkeypatch.setattr(C, "pedir", pedir)
    clave = tmp_path / "cds.txt"
    monkeypatch.setattr(planta.actual(), "CDS_CLAVE", clave)
    r = {x["clave"]: [c for c, _ in x["codigos"]] for x in C.ejecutar()["resultados"]}
    assert r["estaciones"] == ["MET-01"] and r["era5"] == ["MET-18"] and r["gfs"] == [] and r["fondos"] == [] and "internet" not in r
    assert any(c for u, c in pedidas if "noaa" in u) and not any(c for u, c in pedidas if "noaa" not in u)   # de GFS, solo la cabecera
    clave.write_text("x", encoding="utf-8")

    class Cliente:
        def check_authentication(self):
            raise RuntimeError("401 Unauthorized")
    monkeypatch.setattr(era5, "_cliente", lambda: Cliente())
    with pytest.raises(C.Problema) as e:
        C._era5()
    assert e.value.codigo == "MET-17" and "401" in e.value.detalle
    monkeypatch.setattr(Cliente, "check_authentication", lambda self: {})
    assert C._era5()[1].endswith("y acepta la clave")
    # que no responda, que responda mal o que falle la conexión segura: un código distinto
    import ssl
    import urllib.error
    for error, codigo in ((OSError("sin conexión"), "MET-05"), (urllib.error.HTTPError("u", 503, "caída", {}, None), "MET-06"),
                          (urllib.error.URLError(ssl.SSLError(1, "CERTIFICATE_VERIFY_FAILED")), "RED-17")):
        monkeypatch.setattr(C, "pedir", lambda *a, e=error, **k: (_ for _ in ()).throw(e))
        with pytest.raises(C.Problema) as e:
            C._estaciones()
        assert e.value.codigo == codigo
    monkeypatch.setattr(C, "pedir", lambda *a, **k: (200, "text/html", b"<html>"))
    with pytest.raises(C.Problema) as e:
        C._estaciones()
    assert e.value.codigo == "MET-06"
    # sin internet: todos los servicios caídos, y además RED-05
    monkeypatch.setattr(C, "pedir", lambda *a, **k: (_ for _ in ()).throw(OSError("sin conexión")))
    monkeypatch.setattr(planta.actual(), "_json", dict(planta.actual()._json, fuentes={"fondos": [["Fondo", "https://f/{z}/{x}/{y}.png", "", 19]]}))
    r = C.ejecutar()
    assert r["categorias"]["RED"]["codigos"] == ["RED-05", "RED-25"] and r["categorias"]["MET"]["codigos"] == ["MET-05", "MET-15", "MET-25"]


def test_el_viento_en_la_planta_hora_a_hora_y_por_dias_para_el_calendario(monkeypatch):
    # usuario, 2026-11-07: el calendario del viento de Meteorología pinta cada día con su viento en la planta
    cab, fecha = _serie_viento("serie_b")
    cmz = planta.DIR_VIENTO3D / "serie_b" / "cmz" / f"{fecha:%Y%m}.cmz"
    assert vc.origen_mes("serie_b", fecha.year, fecha.month) == cmz and vc.origen_mes("serie_b", fecha.year + 1, 1) is None
    _, u = almacen.leer_campo(cmz, "U-LEV  1")
    _, v = almacen.leer_campo(cmz, "V-LEV  1")
    j, i = VM._celda_planta(vc.info_mes("serie_b", fecha.year, fecha.month), cab.nx, cab.ny)
    assert 0 <= i < cab.nx and 0 <= j < cab.ny
    horas, ws, wd = VM.planta_mes("serie_b", fecha.year, fecha.month)
    assert len(horas) == len(u) and np.allclose(ws, np.hypot(u[:, j, i], v[:, j, i]), atol=1e-5)
    # procedencia desde el norte GEOGRÁFICO: un viento que va hacia el este de la cuadrícula viene del oeste, girado la convergencia
    giro = geo.dir_geo_a_rejilla(0.0, LAT, LON)
    ws1, wd1 = VM.velocidad_procedencia([3.0], [0.0])
    assert ws1[0] == 3.0 and abs((wd1[0] + giro) % 360 - 270) < 1e-9
    assert [VM.rumbo(x) for x in (0, 11.2, 11.3, 292.5, 348.7, 348.8, 359.9)] == ["N", "N", "NNE", "ONO", "NNO", "N", "N"]
    # la caché, en LOCAL: la segunda vez no se lee el viento, y se rehace el mes cuyo fichero cambia
    avance = []
    d = VM.serie_planta("serie_b", progreso=lambda k, n: avance.append((k, n)))
    clave = f"{fecha:%Y%m}"
    assert list(d) == [clave] and avance == [(1, 1)] and (planta.LOCAL / "viento_planta" / "serie_b.json").is_file()
    assert d[clave]["horas"][0] == f"{horas[0]:%Y-%m-%d %H}" and d[clave]["ws"] == [round(float(x), 2) for x in ws]
    leidos = []
    real = VM.planta_mes
    monkeypatch.setattr(VM, "planta_mes", lambda *a: leidos.append(a) or real(*a))
    assert VM.serie_planta("serie_b") == d and leidos == []
    st = cmz.stat()
    os.utime(cmz, (st.st_atime, st.st_mtime + 10))
    assert VM.serie_planta("serie_b") == d and leidos == [("serie_b", fecha.year, fecha.month)]
    # el resumen: el periodo y cada día
    r = VM.resumen_planta(d)
    del_dia = np.array([h.date() == fecha.date() for h in horas])
    dia = r["dias"][f"{fecha:%Y-%m-%d}"]
    assert r["horas"] == len(horas) and dia["horas"] == int(del_dia.sum())
    assert dia["media"] == round(float(np.round(ws, 2)[del_dia].mean()), 2) and dia["maxima"] == round(float(np.round(ws, 2)[del_dia].max()), 1)
    assert dia["calmas"] == int((np.round(ws, 2)[del_dia] < VM.CALMA).sum()) and dia["rumbo"] in VM.RUMBOS + (None,)
    assert abs(sum(sum(f) for f in r["rosa"]) + r["calmas"] - 100) < 0.1 and r["clases"][0] == VM.CALMA
    assert VM.resumen_planta({}) is None
    # y el día que se carga en el mapa lleva sus horas en la planta
    dd = VM.datos_dia(fecha, "serie_b")
    assert len(dd["planta"]["ws"]) == len(dd["horas"]) and dd["planta"]["ws"][0] == round(float(ws[list(horas).index(pd.Timestamp(dd["horas"][0]))]), 2)


def test_sin_cmz_el_viento_sale_del_paquete_de_la_planta(tmp_path):
    from teodors.meteo.viento3d import paquete
    serie = "serie_paquete"
    cab, fecha = _serie_viento(serie)
    _, u = almacen.leer_campo(planta.DIR_VIENTO3D / serie / "cmz" / f"{fecha:%Y%m}.cmz", "U-LEV  1")
    assert vc.paquete_viento() is None
    ind = vc.construir_paquete(serie, ajustes={n: {"k": 4} for n in paquete.AJUSTES})
    assert vc.paquete_viento() == planta.DIR_VIENTO_PAQUETE == planta.PLANTA.parent / "viento" / "3d"
    assert ind["meses"] == [f"{fecha:%Y%m}"]
    shutil.rmtree(planta.DIR_VIENTO3D / serie)                                   # sin la carpeta de cálculos
    assert VM.meses(serie) == vc.meses_serie(serie) == [(fecha.year, fecha.month)]
    assert vc.origen_mes(serie, fecha.year, fecha.month) == planta.DIR_VIENTO_PAQUETE / f"{fecha:%Y%m}.vz"
    assert VM.dia_inicial(serie) == fecha and vc.info_mes(serie, fecha.year, fecha.month)["dias_completos"]
    d = VM.datos_dia(fecha, serie)
    decodificado = np.frombuffer(base64.b64decode(d["u"][0]), "<i2").reshape(cab.ny, cab.nx)
    paso = paquete.AJUSTES["U-LEV"]["paso"]
    assert np.abs(decodificado / 100 - u[0]).max() <= paso / 2 + 0.01
    cab2, horas2 = fichero_viento.leer(vc.descomprimir_mes(serie, fecha.year, fecha.month, tmp_path / "v.dat"))
    assert (cab2.nx, cab2.ny, len(horas2)) == (cab.nx, cab.ny, 24)
    assert vc.meses_serie("otra_serie") == [] and vc.info_mes("otra_serie", fecha.year, fecha.month) is None
    with pytest.raises(FileNotFoundError, match="paquete"):                     # el paquete es de otra serie
        vc.descomprimir_mes("otra_serie", fecha.year, fecha.month, tmp_path / "w.dat")
    # llega otro mes a la serie (otro año): se añade con las mismas bases, sin rehacer el paquete
    assert vc.anadir_paquete(serie) is None                                      # nada nuevo en DATOS
    _serie_viento(serie)
    nuevo = planta.DIR_VIENTO3D / serie / "cmz" / f"{fecha:%Y%m}.cmz"
    otro = nuevo.with_name(f"{fecha.year + 1}{fecha.month:02d}.cmz")
    nuevo.rename(otro)
    ind = vc.anadir_paquete(serie)
    assert ind["meses"] == [f"{fecha:%Y%m}", otro.stem] and vc.meses_serie(serie)[-1] == (fecha.year + 1, fecha.month)
    with pytest.raises(ValueError, match="es de la serie"):
        vc.anadir_paquete("otra_serie")


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


@pytest.mark.skipif(find_spec("pyvista") is None, reason="sin pyvista: es opcional")
def test_comprobar_el_visor_3d_dibuja_y_sin_vtk_avisa(tmp_path, monkeypatch):
    # galera-66, 2026-11-10: en el ejecutable faltaba VTK y la comprobación daba ✓, porque solo miraba que estaba pyvista (que carga VTK al usarlo)
    from teodors.operacion import comprobar as C
    assert P3D.prueba().endswith("triángulos")
    codigos, texto = C._visor3d()
    assert codigos == [] and texto.startswith("Dibuja una superficie de prueba como proceso aparte")
    roto = tmp_path / "sin_vtk"
    (roto / "vtkmodules").mkdir(parents=True)
    (roto / "vtkmodules" / "__init__.py").write_text("raise ImportError('sin VTK')", encoding="utf-8")
    entorno = procesos.entorno
    monkeypatch.setattr(procesos, "entorno", lambda **k: dict(e := entorno(**k), PYTHONPATH=os.pathsep.join([str(roto), e["PYTHONPATH"]])))
    with pytest.raises(C.Problema) as p:
        C._visor3d()
    assert p.value.codigo == "DIS-22" and "sin VTK" in p.value.detalle


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
    for tarea in ("respuestas", "serie_respuestas", "viento3d_series"):
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


# ── el usuario administrador ──
def test_la_contrasena_del_administrador_se_guarda_como_huella_y_se_frena_al_fallar(tmp_path, monkeypatch):
    # usuario, 2026-11-08: dos usuarios, normal y administrador; al administrador se entra desde la terminal con una contraseña
    from teodors.operacion import administrador as A
    assert not A.hay_clave() and A.ruta() == planta.PLANTA / "administrador.json"
    reloj = [1000.0]
    puerta = A.Puerta(reloj=lambda: reloj[0])
    assert puerta.abrir("lo-que-sea") is False                              # sin contraseña puesta, nada abre
    with pytest.raises(ValueError, match="8 caracteres"):
        A.poner_clave("corta")
    A.poner_clave("una-clave-larga")
    texto = A.ruta().read_text(encoding="utf-8")
    d = json.loads(texto)
    assert A.hay_clave() and "una-clave-larga" not in texto and d["algoritmo"] == "pbkdf2_sha256" and d["iteraciones"] >= 100_000
    assert len(bytes.fromhex(d["sal"])) == 16 and len(d["huella"]) == 64
    assert puerta.abrir("una-clave-larga") is True and puerta.abrir("otra") is False
    # con la misma contraseña, otra sal y otra huella
    A.poner_clave("una-clave-larga")
    assert json.loads(A.ruta().read_text(encoding="utf-8"))["huella"] != d["huella"] and puerta.abrir("una-clave-larga") is True
    # tres fallos seguidos: hay que esperar, y mientras tanto ni la buena abre
    assert [puerta.abrir("mal") for _ in range(A.FALLOS_MAX)] == [False] * A.FALLOS_MAX and puerta.espera() == pytest.approx(A.ESPERA_S)
    assert puerta.abrir("una-clave-larga") is False
    reloj[0] += A.ESPERA_S + 1
    assert puerta.espera() == 0 and puerta.abrir("una-clave-larga") is True
    # por línea de órdenes: la pide dos veces, sin que se vea
    respuestas = iter(["nueva-clave-1", "nueva-clave-1", "x-larga-1", "x-larga-2"])
    monkeypatch.setattr(A.getpass, "getpass", lambda _texto="": next(respuestas))
    assert A.main(["--clave"]) == 0 and puerta.abrir("nueva-clave-1") is True
    assert A.main(["--clave"]) == 1 and puerta.abrir("nueva-clave-1") is True          # no coinciden: no cambia


def test_que_focos_estan_simulados_para_el_reanalisis():
    # la ventana de los focos marca los que hay que simular: sin respuesta, o modificados desde que se calculó (usuario, 2026-11-08)
    a = {"id": "A", "modelo": "punto", "ubicacion": {"x": 1.0, "y": 2.0}, "altura_m": 5.0}
    b = {"id": "B", "modelo": "punto", "ubicacion": {"x": 3.0, "y": 4.0}, "altura_m": 5.0}
    c = {"id": "C", "modelo": "punto", "ubicacion": {"x": 5.0, "y": 6.0}, "altura_m": 5.0}
    cat = {"focos": [a, b, c]}
    assert S.estado_respuestas(cat) == {"A": "sin_calcular", "B": "sin_calcular", "C": "sin_calcular"}     # sin carpeta dispersion
    planta.DIR_DISPERSION.mkdir(parents=True, exist_ok=True)
    (planta.DIR_DISPERSION / SR.INDICE).write_text(json.dumps({"focos": {
        "A": {"huella": F.huella(a), "dias": {"202101": [1, 2]}},
        "B": {"huella": F.huella(dict(b, altura_m=9.0)), "dias": {"202101": [1]}},
        "C": {"huella": F.huella(c), "dias": {}}}}), encoding="utf-8")
    assert S.estado_respuestas(cat) == {"A": "ok", "B": "cambiado", "C": "sin_calcular"}
    assert S.estado_respuestas({"focos": [dict(a, olor={"valor": 9})]}) == {"A": "ok"}      # la emisión no cambia la respuesta


def test_lo_que_falta_a_un_foco_sin_su_operabilidad():
    # usuario, 2026-11-08: la operabilidad (horas, eventos) sale de la ventana de los focos; lo que «falta» allí no la incluye
    f = F.nuevo({"focos": []}, "pila")
    assert f["funcionamiento"]["modo"] == "horario" and "horas de funcionamiento" in F.pendientes(f)
    assert "horas de funcionamiento" not in F.pendientes(f, operacion=False) and "altura de emisión" in F.pendientes(f, operacion=False)


def test_la_emision_con_el_viento():
    # usuario, 2026-11-08: «tenemos que dejar una correlación en función del viento, en superficies y volúmenes»: (u / u_ref)^β
    f = F.nuevo(F.vacio(), None, "superficie")
    assert F.factor_viento(f, 5.0) == 1.0                                             # sin ella, constante
    f["emision_viento"] = {"exponente": F.VIENTO_EXPONENTE, "viento_ref_m_s": F.VIENTO_REF_M_S}
    assert F.factor_viento(f, F.VIENTO_REF_M_S) == pytest.approx(1.0) and F.factor_viento(f, 4 * F.VIENTO_REF_M_S) == pytest.approx(4 ** F.VIENTO_EXPONENTE)
    assert F.factor_viento(f, 0.0) == 0.0 and F.factor_viento(dict(f, emision_viento={"exponente": 0.0, "viento_ref_m_s": 1.0}), 7.0) == 1.0
    f["emision_viento"]["viento_ref_m_s"] = None
    assert "exponente y viento de la medida de su emisión con el viento" in F.pendientes(f) and F.factor_viento(f, 5.0) == 1.0
