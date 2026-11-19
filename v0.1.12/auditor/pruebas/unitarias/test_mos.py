# -*- coding: utf-8 -*-
"""mos · corrección estadística de la predicción, SIN RED, con una planta, un GFS y unas estaciones inventados a propósito. Referencias externas: el calendario ISO y la geometría del
círculo. Comprueban el código: no dicen lo bien que corrige ningún MOS en ningún sitio."""
import ast
import json
import socket
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import teodors
from teodors import planta
from teodors.comun import procesos
from teodors.comun.geo import direccion
from teodors.fuentes import gfs_noaa, meteocat
from teodors.mos import aplicar, entrenar, tabla

MOS = Path(__file__).resolve().parents[3] / "core" / "mos"
LAT, LON = 39.75, 1.25                # inventado
PUNTOS = {"AA": (39.8, 1.3), "BB": (39.7, 1.2)}
con_modelos = pytest.mark.skipif(any(find_spec(m) is None for m in ("sklearn", "joblib", "pyarrow")), reason="sin teodors[mos]")
con_tabla = pytest.mark.skipif(any(find_spec(m) is None for m in ("xarray", "netCDF4", "dask", "scipy", "pyarrow")), reason="sin teodors[mos]")
# `aplicar` no abre ficheros del archivo (no necesita dask ni netCDF4): sí xarray y scipy (interpolar al punto) y, para entrenar sus modelos de prueba, pyarrow
con_xarray = pytest.mark.skipif(any(find_spec(m) is None for m in ("xarray", "scipy")), reason="sin xarray o scipy")

JSON_PLANTA = {
    "formato": 1,
    "identidad": {"app_nombre": "Prueba", "organizacion": "ORG", "prefijo_env": "PRUEBA_MOS", "carpeta_local": "prueba_mos", "registro": "prueba"},
    "proyeccion": {"epsg": "EPSG:25831", "crs_geo": "EPSG:4258"},
    "dominio": {"lado_km": 20, "margen_m": 250, "res_terreno_m": 100, "radio_edificios_km": 1, "radio_edificios_focos_m": 150, "celda_viento_m": 500, "zface": [0, 20, 40, 80]},
    "receptores": {"por_km2": 5},
    "reanalisis": {"anios": [2023]},
    "estaciones": {"radio_km": 30.0, "codigos": ["AA", "BB"]},
    "pronostico": {"mos_hasta": "2023-12-31 23:00"},
}


def _planta(carpeta, cambios=None):
    datos = json.loads(json.dumps(JSON_PLANTA))
    for bloque, valor in (cambios or {}).items():
        datos[bloque] = valor
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
    monkeypatch.setenv("PRUEBA_MOS_DATOS", str(tmp_path / "datos"))
    monkeypatch.setenv("PRUEBA_MOS_LOCAL", str(tmp_path / "local"))
    monkeypatch.setattr(sys, "argv", ["mos"])
    _planta(tmp_path / "planta")
    meteocat.dir_meteocat().mkdir(parents=True)
    inv = [{"codi_estacio": c, "nom_estacio": f"Estación {c}", "latitud": str(la), "longitud": str(lo), "altitud": "50", "codi_estat_ema": "2"} for c, (la, lo) in PUNTOS.items()]
    (meteocat.dir_meteocat() / "estaciones.json").write_text(json.dumps(inv), encoding="utf-8")
    yield
    planta.desactivar()


def _gfs_y_medidas():
    """GFS: una ejecución al día, plazos cada 6 h, en 2 × 2 puntos, con el viento lineal en latitud y longitud. Hay un mes más de lo que cuenta. Medidas: 5 m/s del E cada 6 h."""
    import xarray as xr
    plazos, lat, lon = np.arange(0, 121, 6), np.array([39.5, 40.0]), np.array([1.0, 1.5])
    gradiente = np.add.outer(4.0 * (lat - 39.5), 2.0 * (lon - 1.0))
    carpeta = planta.DATOS / "meteo" / "gfs"
    carpeta.mkdir(parents=True)
    for mes in pd.period_range("2023-01", "2024-01", freq="M"):
        inits = pd.date_range(mes.start_time, mes.end_time.normalize(), freq="D")
        lleno = lambda x: (("init_time", "lead_time_h", "latitude", "longitude"), np.broadcast_to(x, (len(inits), len(plazos), 2, 2)).astype(np.float32))
        campos = {"wind_u_10m": 2.0 + gradiente, "wind_v_10m": -3.0, "wind_u_100m": 4.0 + gradiente, "wind_v_100m": -6.0, "temperature_2m": 15.0, "relative_humidity_2m": 60.0,
                  "total_cloud_cover_atmosphere": 50.0, "downward_short_wave_radiation_flux_surface": 200.0, "pressure_reduced_to_mean_sea_level": 101300.0}
        xr.Dataset({v: lleno(x) for v, x in campos.items()}, coords={"init_time": inits, "lead_time_h": plazos, "latitude": lat, "longitude": lon}).to_netcdf(carpeta / f"gfs00_{mes.strftime('%Y%m')}.nc")
    horas = pd.date_range("2023-01-01", "2024-01-10", freq="6h")
    for c in PUNTOS:
        destino = planta.DATOS / "reanalisis" / f"01_estacion_{c}" / "horario_valido.csv"
        destino.parent.mkdir(parents=True)
        pd.DataFrame({"time": horas, "ws": 5.0, "wd": 90.0, "t": 15.0}).to_csv(destino, index=False)


def _tabla_inventada(estaciones=("AA", "BB"), semanas=30, sesgo=1.5, giro=30.0):
    """Lo que escribe `tabla`, con un error de GFS conocido: sopla de 320-340° y lo medido está girado `giro` (cruza los 360°) y es `sesgo` m/s más flojo."""
    rng = np.random.default_rng(1)
    t = pd.date_range("2023-01-02", periods=24 * 7 * semanas, freq="h")
    lunes = t.normalize() - pd.to_timedelta(t.weekday, unit="D")
    part = tabla.particion(pd.DatetimeIndex(sorted(lunes.unique())))
    conjunto = pd.Series(lunes).map(dict(zip(pd.to_datetime(part.semana_inicio), part.conjunto))).to_numpy()
    filas = []
    for c in estaciones:
        wd, ws = rng.uniform(320.0, 340.0, len(t)), rng.uniform(3.0, 10.0, len(t))
        u, v = -ws * np.sin(np.radians(wd)), -ws * np.cos(np.radians(wd))
        d = pd.DataFrame({"estacion": c, "init_time": t, "plazo_h": 1 + np.arange(len(t)) % 120, "valid_time": t, "wind_u_10m": u, "wind_v_10m": v, "wind_u_100m": 1.5 * u, "wind_v_100m": 1.5 * v,
                          "gfs_ws10": ws, "gfs_wd10": direccion(u, v), "gfs_ws100": 1.5 * ws, "cizalla": 0.5 * ws, "temperature_2m": 15.0, "relative_humidity_2m": 60.0, "total_cloud_cover_atmosphere": 50.0,
                          "downward_short_wave_radiation_flux_surface": 200.0, "pressure_reduced_to_mean_sea_level": 101300.0, "hora_sin": 0.0, "hora_cos": 1.0, "doy_sin": 0.0, "doy_cos": 1.0,
                          "obs_ws": ws - sesgo, "obs_wd": (wd + giro) % 360.0, "conjunto": conjunto})
        rad = np.radians(d.obs_wd)
        d["obs_u"], d["obs_v"] = -d.obs_ws * np.sin(rad), -d.obs_ws * np.cos(rad)
        filas.append(d)
    return pd.concat(filas, ignore_index=True)


def _entrenar(t, monkeypatch):
    """Lanza `entrenar.main` sobre la tabla t y devuelve la carpeta. Con pocas iteraciones: aquí no se mide su calidad."""
    base = planta.DATOS / "mos"
    base.mkdir(parents=True, exist_ok=True)
    t.to_parquet(base / "tabla_gfs00.parquet", index=False)
    monkeypatch.setitem(entrenar.GB, "max_iter", 30)
    entrenar.main()
    return base


# ── la partición ──
def test_particion_una_de_cada_cinco_semanas_con_el_calendario_iso():
    semanas = pd.date_range("2021-01-04", "2025-12-29", freq="W-MON")
    p = tabla.particion(semanas)
    assert p.semana_inicio.is_unique and len(p) == len(semanas)
    assert 0.18 < (p.conjunto == "valid").mean() < 0.22
    conjunto = dict(zip(pd.to_datetime(p.semana_inicio), p.conjunto))
    # a mano. El 4 de enero siempre es de la semana 1: 2021-01-04, semana 1, 1 + 2021 ≡ 2; 2021-01-25, semana 4, 4 + 2021 ≡ 0; 2021-12-27, semana 52, 52 + 2021 ≡ 3; 2023-01-02, semana 1 de 2023, 2024 ≡ 4
    assert [conjunto[pd.Timestamp(d)] for d in ("2021-01-04", "2021-01-25", "2021-12-27", "2023-01-02")] == ["train", "valid", "train", "train"]


@con_tabla
def test_la_tabla_parte_por_la_semana_de_la_hora_de_validez():
    _gfs_y_medidas()
    tabla.main()
    base = planta.DATOS / "mos"
    t = pd.read_parquet(base / "tabla_gfs00.parquet")
    lunes = t.valid_time.dt.normalize() - pd.to_timedelta(t.valid_time.dt.weekday, unit="D")
    assert t.groupby(lunes).conjunto.nunique().max() == 1                                  # ninguna semana repartida
    assert (t.groupby(["estacion", "init_time"]).conjunto.nunique() == 2).any()            # y sí alguna ejecución: se parte por la validez, no por la ejecución
    assert 0.15 < (t.conjunto == "valid").mean() < 0.25
    assert set(t.conjunto[lunes == pd.Timestamp("2023-01-09")]) == {"valid"}               # semana 2 de 2023: 2 + 2023 ≡ 0
    part = pd.read_csv(base / "particion.csv", parse_dates=["semana_inicio"])
    assert set(part.semana_inicio) == set(lunes) and part.semana_inicio.is_unique

    # lo que no cuenta, fuera: enero del año siguiente, como ejecución y como hora de validez
    assert t.valid_time.max() == pd.Timestamp("2023-12-31 18:00") and t.init_time.max() == pd.Timestamp("2023-12-31")
    # bilineal sobre un campo lineal: exacta
    for c, (la, lo) in PUNTOS.items():
        assert t.wind_u_10m[t.estacion == c].to_numpy() == pytest.approx(2.0 + 4.0 * (la - 39.5) + 2.0 * (lo - 1.0), abs=1e-5)
    # la referencia sale de lo medido y del GFS sin corregir
    ref = pd.read_csv(base / "referencia_gfs.csv")
    assert ref.sesgo_vel[ref.estacion == "AA"].to_numpy() == pytest.approx(np.hypot(3.8, 3.0) - 5.0, abs=1e-3)
    assert json.loads((base / "resumen.json").read_text(encoding="utf-8"))["estaciones"] == ["AA", "BB"]


# ── lo que entra en cada modelo ──
@con_tabla
def test_las_entradas_salen_solo_de_gfs():
    _gfs_y_medidas()
    g = tabla.gfs()
    d = entrenar.preparar(tabla.entradas_gfs(g, *PUNTOS["AA"]))             # no recibe ninguna medida
    assert set(entrenar.ENTRADAS) <= set(d.columns)
    assert not [e for e in entrenar.ENTRADAS if e.startswith("obs_") or e in ("estacion", "conjunto", "anemometro_m")]


@con_modelos
def test_la_estacion_que_se_valida_no_entra_en_sus_propias_entradas(monkeypatch):
    import joblib
    columnas = ["lin_u", "lin_v", "lin_ws", "gb_u", "gb_v", "gb_ws"]
    obs = ["obs_u", "obs_v", "obs_ws", "obs_wd"]

    def prediccion(t):
        v = pd.read_parquet(_entrenar(t, monkeypatch) / "prediccion_valid.parquet")
        return v[v.estacion == "AA"][columnas].to_numpy()

    t = _tabla_inventada()
    base = prediccion(t)
    # ni lo medido en sus semanas de validación ni lo de otra estación cambian nada, bit a bit
    otra = t.copy()
    otra.loc[((t.estacion == "AA") & (t.conjunto == "valid")) | (t.estacion == "BB"), obs] = 1.0
    assert np.array_equal(base, prediccion(otra))
    # y la prueba distingue: lo medido en las de entrenamiento, sí
    otra = t.copy()
    otra.loc[(t.estacion == "AA") & (t.conjunto == "train"), obs] = 1.0
    assert not np.array_equal(base, prediccion(otra))

    guardado = joblib.load(planta.DATOS / "mos" / "modelos" / "AA_u.joblib")
    assert guardado["entradas"] == entrenar.ENTRADAS and set(guardado) == {"lineal", "gb", "entradas"}


# ── lo que corrige ──
@con_modelos
def test_corrige_un_sesgo_conocido_y_la_direccion_sale_de_u_y_v(monkeypatch):
    base = _entrenar(_tabla_inventada(), monkeypatch)
    m = pd.read_csv(base / "metricas.csv")
    fila = lambda modelo: m[(m.estacion == "AA") & (m.plazo == "día 1") & (m.franja == "todo") & (m.modelo == modelo)].iloc[0]
    assert fila("GFS").sesgo_vel == pytest.approx(1.5, abs=0.01) and fila("GFS").error_dir == pytest.approx(30.0, abs=0.1)
    # lo inventado es lineal en las entradas: el ridge lo clava; al gb, con 30 iteraciones, solo se le pide que mejore mucho
    assert abs(fila("MOS lineal").sesgo_vel) < 0.05 and fila("MOS lineal").rmse_vel < 0.1 and fila("MOS lineal").error_dir < 1.0
    assert abs(fila("MOS gb").sesgo_vel) < 0.2 and fila("MOS gb").error_dir < 10.0

    # lo medido cruza los 360°: una media de grados daría ~180°, y de u y v sale bien
    v = pd.read_parquet(base / "prediccion_valid.parquet")
    assert (v.lin_wd > 350.0).any() and (v.lin_wd < 10.0).any()
    assert np.abs((v.lin_wd - v.obs_wd + 180.0) % 360.0 - 180.0).max() < 5.0
    assert (v.conjunto == "valid").all() and {"elev_sol", "gb_wd"} <= set(v.columns)
    assert set(m.estacion) == {"AA", "BB", "media"} and set(m.franja) == {"todo", "día", "noche"}


def test_geometria_de_la_direccion_a_mano():
    assert tabla.error_dir(np.array([350.0, 10.0, 180.0]), np.array([10.0, 350.0, 0.0])).tolist() == [20.0, 20.0, 180.0]
    assert direccion(np.array([0.0, -5.0, 5.0]), np.array([-5.0, 0.0, 0.0])) % 360.0 == pytest.approx([0.0, 90.0, 270.0])     # del N, del E, del O
    d = pd.DataFrame({"obs_ws": [5.0, 5.0], "obs_wd": [350.0, 10.0]})
    r = entrenar.metricas(d, d.obs_ws, pd.Series([10.0, 350.0]))
    assert r["error_dir"] == 20.0 and r["sesgo_dir"] == 0.0 and r["rmse_vel"] == 0.0 and r["rosa"] == 0.0        # 350° y 10° caen en el mismo sector, el N
    f, calmas = entrenar.rosa(np.array([5.0, 5.0, 0.1]), np.array([350.0, 10.0, 90.0]))
    assert f[0] == 1.0 and f.sum() == 1.0 and calmas == pytest.approx(100.0 / 3.0)


# ── aplicar: el MOS en una ejecución nueva (la predicción) ──
def _ejecucion_noaa(ini, plazos=range(0, 25, 3), ws=7.0, wd=330.0):
    """Una ejecución como la de `gfs_noaa.ejecucion(…, extra=True)`: el viento de `wd` a `ws` m/s en todos los puntos, la latitud de norte a sur y la presión en hPa, como allí."""
    import xarray as xr
    plazos = list(plazos)
    u, v = -ws * np.sin(np.radians(wd)), -ws * np.cos(np.radians(wd))
    campos = {"wind_u_10m": u, "wind_v_10m": v, "wind_u_100m": 1.5 * u, "wind_v_100m": 1.5 * v, "temperature_2m": 15.0, "relative_humidity_2m": 60.0,
              "total_cloud_cover_atmosphere": 50.0, "downward_short_wave_radiation_flux_surface": 200.0, "pressure_msl": 1013.0, "surface_pressure": 1000.0}
    forma = (len(plazos), 2, 2)
    return xr.Dataset({k: (("plazo_h", "latitude", "longitude"), np.full(forma, x, np.float32)) for k, x in campos.items()},
                      coords={"plazo_h": plazos, "latitude": [40.0, 39.5], "longitude": [1.0, 1.5], "init_time": pd.Timestamp(ini)})


@con_xarray
def test_aplicar_pone_el_gfs_de_noaa_como_el_archivo_del_entrenamiento():
    g = aplicar.entradas(_ejecucion_noaa("2024-01-05"))
    assert list(g.data_vars) == aplicar.VARIABLES and g.temperature_2m.dims == ("init_time", "lead_time_h", "latitude", "longitude")
    assert pd.Timestamp(g.init_time.values[0]) == pd.Timestamp("2024-01-05") and g.lead_time_h.values.tolist() == list(range(0, 25, 3))
    assert float(g.pressure_reduced_to_mean_sea_level.max()) == pytest.approx(101300.0)           # el archivo, en Pa; `gfs_noaa`, en hPa
    with pytest.raises(ValueError, match="extra=True"):
        aplicar.entradas(_ejecucion_noaa("2024-01-05").drop_vars("wind_u_100m"))
    assert set(gfs_noaa.EXTRA.values()) | set(gfs_noaa.EXTRA_MEDIA.values()) <= set(aplicar.VARIABLES) <= set(entrenar.ENTRADAS) | {"pressure_reduced_to_mean_sea_level"}


@con_modelos
@con_xarray
def test_aplicar_corrige_una_ejecucion_nueva_con_los_modelos_entrenados(monkeypatch):
    assert aplicar.carpeta_modelos() is None and aplicar.cargar(["AA"]) == {}                     # sin modelos todavía
    _entrenar(_tabla_inventada(), monkeypatch)
    assert aplicar.carpeta_modelos() == planta.DATOS / "mos" / "modelos"
    modelos = aplicar.cargar(["AA", "BB", "CC"])
    assert set(modelos) == {"AA", "BB"} and set(modelos["AA"]) == {"u", "v", "ws"}                   # CC no tiene modelos: no sale
    est = [{"codigo": c, "lat": la, "lon": lo} for c, (la, lo) in PUNTOS.items()] + [{"codigo": "CC", "lat": 39.75, "lon": 1.25}]
    t = aplicar.corregir(_ejecucion_noaa("2024-01-05"), est, modelos)
    assert list(t.columns) == aplicar.COLUMNAS and len(t) == 2 * 9 and set(t.codigo) == {"AA", "BB"}
    assert t.valid_time.min() == pd.Timestamp("2024-01-05") and t.valid_time.max() == pd.Timestamp("2024-01-06")
    # GFS sopla de 330° a 7 m/s; lo medido (inventado) está girado 30° y es 1,5 m/s más flojo: la corrección lo deshace (el gb, con 30 iteraciones, aproximado)
    assert t.gfs_ws10.to_numpy() == pytest.approx(7.0, abs=1e-4) and t.gfs_wd10.to_numpy() == pytest.approx(330.0, abs=1e-3)
    assert np.abs(t.ws - 5.5).max() < 0.5 and tabla.error_dir(t.wd.to_numpy(), np.zeros(len(t))).max() < 10.0
    # lo mismo que el modelo con la tabla del entrenamiento: las entradas salen de `tabla.entradas_gfs` y `entrenar.preparar`
    fila = entrenar.preparar(tabla.entradas_gfs(aplicar.entradas(_ejecucion_noaa("2024-01-05")), *PUNTOS["AA"]))
    assert t[t.codigo == "AA"].ws.to_numpy() == pytest.approx(np.maximum(modelos["AA"]["ws"].predict(fila[entrenar.ENTRADAS].to_numpy(np.float32)), 0.0))


@con_modelos
def test_aplicar_no_acepta_modelos_con_otras_entradas(tmp_path):
    import joblib
    for k in aplicar.OBJETIVOS:
        joblib.dump({"lineal": None, "gb": None, "entradas": ["otra"]}, tmp_path / f"ZZ_{k}.joblib")
    with pytest.raises(ValueError, match="ZZ"):
        aplicar.cargar(["ZZ"], tmp_path)
    assert aplicar.cargar(["YY"], tmp_path) == {}


def test_horaria_interpola_u_v_y_la_velocidad_y_la_direccion_cruza_el_norte():
    rumbo = np.radians([350.0, 10.0])
    t = pd.DataFrame({"codigo": "AA", "valid_time": pd.to_datetime(["2024-01-05 00:00", "2024-01-05 03:00"]), "plazo_h": [0, 3],
                      "u": -5.0 * np.sin(rumbo), "v": -5.0 * np.cos(rumbo), "ws": [4.0, 7.0]})
    horas = pd.date_range("2024-01-04 23:00", "2024-01-05 04:00", freq="h")
    r = aplicar.horaria(t, horas)["AA"]
    assert r.time.tolist() == list(horas) and r.ws.isna().tolist() == [True, False, False, False, False, True]     # fuera de los plazos, nada
    assert r.ws.iloc[1:5].tolist() == pytest.approx([4.0, 5.0, 6.0, 7.0])
    assert tabla.error_dir(r.wd.iloc[1:5].to_numpy(), np.zeros(4)).max() <= 10.0 + 1e-9                  # entre 350° y 10°, por el N: una media de grados daría ~180°


# ── lo propio de cada planta y lo que no puede pasar al importar ──
def test_sin_mos_hasta_el_error_dice_cual(tmp_path):
    planta.desactivar()
    _planta(tmp_path / "otra", {"pronostico": {}})
    with pytest.raises(ValueError, match="pronostico.mos_hasta"):
        tabla.gfs()


def _leidos(nodos):
    return {n.id for nodo in nodos for n in ast.walk(nodo) if isinstance(n, ast.Name)}


@pytest.mark.parametrize("fichero", sorted(f.name for f in MOS.glob("*.py")))
def test_nada_lee_la_planta_al_importar_ni_en_un_valor_por_defecto(fichero):
    arbol = ast.parse((MOS / fichero).read_text(encoding="utf-8"))
    fuera = [n for n in arbol.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom))]
    fuera = [n for n in fuera if not (isinstance(n, ast.If) and "__name__" in _leidos([n.test]))]
    assert not _leidos(fuera) & {"config", "planta", "geo", "estaciones"}
    defectos = [d for n in ast.walk(arbol) if isinstance(n, ast.FunctionDef) for d in n.args.defaults + [k for k in n.args.kw_defaults if k]]
    assert not _leidos(defectos) & {"config", "planta", "geo", "estaciones"}


def test_al_importar_no_hay_planta_activa_ni_se_cargan_los_extras(tmp_path):
    env = procesos.entorno()
    env.pop(planta.ENV_PLANTA, None)
    codigo = "import sys\nimport teodors.mos.tabla, teodors.mos.entrenar, teodors.mos.aplicar\nfrom teodors import planta\nprint(planta._activa, [m for m in ('sklearn', 'joblib', 'xarray', 'dask') if m in sys.modules])"
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, encoding="utf-8", cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "None []"


@pytest.mark.parametrize("modulo", ["tabla", "entrenar"])
def test_la_ayuda_responde_sin_planta(modulo, tmp_path):
    env = procesos.entorno()
    env.pop(planta.ENV_PLANTA, None)
    r = subprocess.run([sys.executable, "-m", f"teodors.mos.{modulo}", "--help"], capture_output=True, text=True, encoding="utf-8", cwd=tmp_path, env=env)
    assert r.returncode == 0, r.stderr
    assert f"teodors.mos.{modulo}" in r.stdout and "DATOS/mos/" in r.stdout


def test_no_es_un_motor_y_el_readme_dice_sus_ficheros():
    assert "mos" not in teodors.MOTORES
    texto = (MOS / "README.md").read_text(encoding="utf-8")
    for f in sorted(f.name for f in MOS.glob("*.py")):
        assert f"`{f}`" in texto.split("## Ficheros")[1]
    assert "LOCAL" in texto.split("## Ficheros")[0]                         # la limitación medida
