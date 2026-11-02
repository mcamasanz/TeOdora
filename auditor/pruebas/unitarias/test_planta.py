# -*- coding: utf-8 -*-
"""planta · una planta se lee de su carpeta: constantes, prioridad de rutas, errores claros, herencia
en los procesos hijos y coordenadas en su huso. El emplazamiento de prueba es inventado a propósito,
para que nada dependa de una planta concreta."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from teodors import planta
from teodors.comun import geo as comun_geo
from teodors.comun import procesos
from teodors.planta import geo

RAIZ = Path(__file__).resolve().parents[3]
LAT, LON = 40.6905923, 0.4764197      # punto de control de comun.geo: γ = +2,26° en EPSG:25830

JSON_PLANTA = {
    "formato": 1,
    "identidad": {"app_nombre": "Planta de prueba", "organizacion": "ORG", "prefijo_env": "PRUEBA_PLANTA",
                  "carpeta_local": "prueba_planta", "registro": "prueba"},
    "proyeccion": {"epsg": "EPSG:25830", "crs_geo": "EPSG:4258"},
    "dominio": {"lado_km": 20, "margen_m": 250, "res_terreno_m": 25, "radio_edificios_km": 1,
                "radio_edificios_focos_m": 100, "celda_viento_m": 500, "zface": [0, 20, 40, 80]},
    "receptores": {"por_km2": 5},
    "reanalisis": {"anios": [2022, 2023]},
}


def _escribe(carpeta, cambios=None, quita=None):
    datos = json.loads(json.dumps(JSON_PLANTA))
    for bloque, valores in (cambios or {}).items():
        datos.setdefault(bloque, {}).update(valores)
    if quita:
        del datos[quita[0]][quita[1]]
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "planta.json").write_text(json.dumps(datos), encoding="utf-8")
    (carpeta / "emplazamiento.json").write_text(json.dumps({"nombre": "Prueba", "lat": LAT, "lon": LON}), encoding="utf-8")
    return carpeta


@pytest.fixture(autouse=True)
def sin_planta(monkeypatch):
    planta.desactivar()
    for v in ("DATOS", "LOCAL", "MODO", "CORINE"):
        monkeypatch.delenv(f"PRUEBA_PLANTA_{v}", raising=False)
    yield
    planta.desactivar()


def test_constantes_con_su_tipo(tmp_path):
    p = planta.Planta(_escribe(tmp_path))
    assert p.APP_NOMBRE == "Planta de prueba" and p.ORGANIZACION == "ORG"
    assert p.EPSG_UTM == "EPSG:25830" and p.CRS_GEO == "EPSG:4258"
    assert p.DOMINIO_DESCARGA_KM == 20.0 and isinstance(p.DOMINIO_DESCARGA_KM, float)
    assert p.VIENTO3D_ZFACE == (0, 20, 40, 80) and p.REANALISIS_ANIOS == (2022, 2023)
    assert p.RECEPTORES_POR_KM2 == 5
    assert p.EMPLAZAMIENTO_JSON == tmp_path.resolve() / "emplazamiento.json"
    assert p.FOCOS_JSON == tmp_path.resolve() / "focos.json"
    assert p.NORMATIVA_JSON == tmp_path.resolve() / "normativa.json"
    assert p.cargar_emplazamiento()["lat"] == LAT


def test_radio_de_calculo_es_mitad_del_lado_menos_el_margen(tmp_path):
    # el lado se confundió una vez con la distancia al centro: 20 km de lado, 250 m de margen -> 9,75 km
    p = planta.Planta(_escribe(tmp_path))
    assert p.RADIO_CALCULO_KM == 9.75
    assert p.radio_calculo_max(50.0) == 24.75


def test_datos_variable_antes_que_rutas_antes_que_la_carpeta(tmp_path, monkeypatch):
    c = _escribe(tmp_path / "p")
    assert planta.Planta(c).DATOS == c.resolve() / "datos"
    (c / "rutas.json").write_text(json.dumps({"datos": str(tmp_path / "red")}), encoding="utf-8")
    assert planta.Planta(c).DATOS == tmp_path / "red"
    monkeypatch.setenv("PRUEBA_PLANTA_DATOS", str(tmp_path / "var"))
    p = planta.Planta(c)
    assert p.DATOS == tmp_path / "var" and p.DIR_METEO == tmp_path / "var" / "meteo"
    assert p.DIR_TERRENO == p.PLANTA / "terreno" and p.DIR_EDIFICIOS == p.PLANTA / "edificios"      # van con la planta, no con los cálculos


def test_las_variables_llevan_el_prefijo_de_la_planta(tmp_path, monkeypatch):
    monkeypatch.setenv("OTRA_PLANTA_DATOS", str(tmp_path / "ajena"))
    monkeypatch.setenv("OTRA_PLANTA_MODO", "edicion")
    p = planta.Planta(_escribe(tmp_path / "p"))
    assert p.DATOS != tmp_path / "ajena" and not p.MODO_EDICION
    assert p.nombre_env("DATOS") == "PRUEBA_PLANTA_DATOS"


def test_local_y_trabajo_fuera_de_datos(tmp_path, monkeypatch):
    monkeypatch.setenv("PRUEBA_PLANTA_LOCAL", str(tmp_path / "local"))
    p = planta.Planta(_escribe(tmp_path / "p"))
    assert p.DIR_LOGS == tmp_path / "local" / "logs" and p.DIR_TRABAJO == tmp_path / "local" / "trabajo"
    monkeypatch.delenv("PRUEBA_PLANTA_LOCAL")
    monkeypatch.setenv("TEMP", str(tmp_path / "temp"))
    assert planta.Planta(tmp_path / "p").LOCAL == tmp_path / "temp" / "prueba_planta"


def test_claves_fuera_de_la_carpeta_de_la_planta(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "usuario"))
    p = planta.Planta(_escribe(tmp_path / "p"))
    assert p.CDS_CLAVE == tmp_path / "usuario" / "ORG" / "claves" / "cds-api-key.txt"
    assert p.PLANTA not in p.CDS_CLAVE.parents


def test_modo_de_edicion_con_la_clave_de_la_planta(tmp_path, monkeypatch):
    c = _escribe(tmp_path / "p", {"operacion": {"modo_edicion": "taller"}})
    assert not planta.Planta(c).MODO_EDICION
    monkeypatch.setenv("PRUEBA_PLANTA_MODO", "edicion")
    assert not planta.Planta(c).MODO_EDICION
    monkeypatch.setenv("PRUEBA_PLANTA_MODO", " Taller ")
    assert planta.Planta(c).MODO_EDICION


def test_sin_carpeta_o_sin_campo_el_error_dice_cual(tmp_path):
    with pytest.raises(FileNotFoundError, match="planta.json"):
        planta.Planta(tmp_path / "no_existe")
    with pytest.raises(ValueError, match=r"dominio\.lado_km"):
        planta.Planta(_escribe(tmp_path / "p", quita=("dominio", "lado_km")))


def test_corine_variable_datos_y_copias_con_variables(tmp_path, monkeypatch):
    copia = tmp_path / "unidad" / "CLC.gpkg"
    copia.parent.mkdir()
    copia.write_bytes(b"x")
    monkeypatch.setenv("COPIAS_CLC", str(copia.parent))
    c = _escribe(tmp_path / "p", {"fuentes": {"corine_gpkg": ["$COPIAS_CLC/CLC.gpkg", "$NO_DEFINIDA_XYZ/CLC.gpkg"]}})
    assert planta.Planta(c).corine_gpkg() == copia
    monkeypatch.delenv("COPIAS_CLC")
    assert planta.Planta(c).corine_gpkg() is None
    otra = tmp_path / "otra.gpkg"
    otra.write_bytes(b"x")
    monkeypatch.setenv("PRUEBA_PLANTA_CORINE", str(otra))
    assert planta.Planta(c).corine_gpkg() == otra


def test_agente_http_y_campos_que_hacen_falta(tmp_path):
    p = planta.Planta(_escribe(tmp_path / "p"))
    assert p.AGENTE_HTTP == "teOdors"
    with pytest.raises(ValueError, match=r"estaciones\.radio_km"):
        p.pide("estaciones", "radio_km")
    planta.activar(_escribe(tmp_path / "q", {"identidad": {"agente_http": "Prueba/1"}, "estaciones": {"radio_km": 5}}))
    assert planta.AGENTE_HTTP == "Prueba/1" and planta.pide("estaciones", "radio_km") == 5


def test_datos_disponibles_y_carpetas(tmp_path, monkeypatch):
    monkeypatch.setenv("PRUEBA_PLANTA_DATOS", str(tmp_path / "d"))
    monkeypatch.setenv("PRUEBA_PLANTA_LOCAL", str(tmp_path / "l"))
    p = planta.Planta(_escribe(tmp_path / "p"))
    assert not p.datos_disponibles()
    p.asegurar_carpetas()
    assert p.datos_disponibles() and p.DIR_TERRENO.is_dir() and p.DIR_METEO.is_dir() and p.DIR_LOGS.is_dir()


def test_sin_planta_activa_lo_dice(monkeypatch):
    monkeypatch.delenv(planta.ENV_PLANTA, raising=False)
    with pytest.raises(RuntimeError, match="activar"):
        planta.DATOS
    with pytest.raises(RuntimeError, match="activar"):
        planta.corine_gpkg()


def test_activar_delega_en_el_modulo(tmp_path):
    p = planta.activar(_escribe(tmp_path))
    assert planta.actual() is p
    assert planta.EPSG_UTM == "EPSG:25830" and planta.RADIO_CALCULO_KM == 9.75
    assert planta.bloque("no_existe") == {}
    with pytest.raises(AttributeError):
        planta.NO_EXISTE
    with pytest.raises(AttributeError):
        planta.no_existe


def test_el_proceso_hijo_hereda_la_planta(tmp_path):
    planta.activar(_escribe(tmp_path))
    r = subprocess.run([sys.executable, "-c", "from teodors import planta; print(planta.EPSG_UTM, planta.RADIO_CALCULO_KM)"],
                       env=procesos.entorno(), capture_output=True, text=True, encoding="utf-8", cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["EPSG:25830", "9.75"]


def test_geo_usa_el_huso_de_la_planta(tmp_path):
    # EPSG:25830 a propósito: comun.geo sin epsg elegiría el huso de la longitud, el 31
    planta.activar(_escribe(tmp_path))
    assert geo.a_utm(LAT, LON) == comun_geo.a_utm(LAT, LON, "EPSG:25830")
    assert geo.a_utm(LAT, LON) != comun_geo.a_utm(LAT, LON)
    assert abs(geo.convergencia_deg(LAT, LON) - 2.26) < 0.01
    x, y = geo.a_utm(LAT, LON)
    la, lo = geo.a_geo(x, y)
    assert abs(la - LAT) < 1e-9 and abs(lo - LON) < 1e-9
    assert geo.dir_geo_a_rejilla(10.0, LAT, LON) == comun_geo.dir_geo_a_rejilla(10.0, LAT, LON, "EPSG:25830")
    assert geo.cuadrado_utm(LAT, LON, 10.0)[1] == comun_geo.cuadrado_utm(LAT, LON, 10.0, "EPSG:25830")[1]
    assert geo.distancia_rumbo(LAT, LON, LAT + 0.1, LON) == comun_geo.distancia_rumbo(LAT, LON, LAT + 0.1, LON, "EPSG:25830")


def test_geo_con_epsg_explicito_manda_ese(tmp_path):
    planta.activar(_escribe(tmp_path))
    assert geo.a_utm(LAT, LON, "EPSG:25831") == comun_geo.a_utm(LAT, LON, "EPSG:25831")
    assert abs(geo.convergencia_deg(LAT, LON, "EPSG:25831") + 1.65) < 0.01


def _importa_planta(fichero):
    for n in ast.walk(ast.parse(fichero.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import) and any(a.name.startswith("teodors.planta") for a in n.names):
            return True
        if isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if mod.startswith("teodors.planta") or (mod == "teodors" and any(a.name == "planta" for a in n.names)):
                return True
            if n.level and (mod.startswith("planta") or any(a.name == "planta" for a in n.names)):
                return True
    return False


def test_los_motores_no_dependen_de_ninguna_planta():
    # un motor recibe ficheros de control: si leyera la planta activa, su resultado dependería de ella
    malos = [str(f.relative_to(RAIZ)) for carpeta in ("terreno", "meteo", "dispersion", "preparacion", "comun")
             for f in (RAIZ / "core" / carpeta).rglob("*.py") if "_nucleo_gen" not in f.name and _importa_planta(f)]
    assert not malos, malos


def test_el_codigo_de_planta_no_trae_datos_de_un_emplazamiento():
    # lo de cada sitio llega de su carpeta o por parámetro. También en el viento local, las fuentes de datos, las métricas, los casos, la operación, el MOS y la interfaz, que nacieron en una planta
    ficheros = [*(RAIZ / "core" / "planta").glob("*.py"), *(RAIZ / "core" / "meteo" / "viento_local").glob("*.py"), *(RAIZ / "core" / "fuentes").glob("*.py"), *(RAIZ / "core" / "metricas").glob("*.py"),
                *(RAIZ / "core" / "casos").glob("*.py"), RAIZ / "core" / "preparacion" / "puffs" / "control_fuentes.py", *(RAIZ / "core" / "operacion").glob("*.py"), *(RAIZ / "core" / "mos").glob("*.py"), *(RAIZ / "core" / "gui").glob("*.py")]
    assert {"geo.py", "modelo.py", "biblioteca.py", "terreno.py", "catastro.py", "meteocat.py", "era5.py", "gfs_noaa.py", "gfs_dynamical.py", "lidar.py", "viento.py", "calidad.py",
            "viento3d.py", "gfs_columnas.py", "receptores.py", "control_fuentes.py", "focos.py", "planes.py", "normativa.py", "periodos.py", "simulacion.py", "penacho_mapa.py", "viento_mapa.py",
            "penacho_3d.py", "respuestas.py", "viento_periodo.py", "viento3d_series.py", "ejemplo_configuracion.py", "tabla.py", "entrenar.py", "mapa_web.py", "focos_mapa.py", "panel.py", "ventana.py", "principal.py"} <= {f.name for f in ficheros}
    for f in ficheros:
        texto = f.read_text(encoding="utf-8")
        # también lo propio de una malla y de una serie: su nombre, los niveles y las columnas de GFS
        palabras = ["Galera", "galera", "ENCE", "25831", "Montsià", "Z:\\", "Dacame", "Santa Bàrbara", "Barberans", "Ràpita", "l'Aldea", "C9", "40,25", "41,25", "e2s", "_8est", "12500", "Cercana ·"]
        if not (f.parent.name in ("metricas", "casos") or (f.parent.name == "fuentes" and f.name in ("__init__.py", "meteocat.py", "descargar_meteocat.py")) or f.name == "viento_periodo.py"):      # ahí, es el nombre del servicio
            palabras.append("Meteocat")
        if f.parent.name == "operacion":                                       # la zona horaria, la ortofoto, los días de prueba y las rutas de la aplicación son de cada proyecto
            palabras += ["Madrid", "PNOA", "CIRCE", "2026-10-21", "99-Test", "gui/", "ence."]
        if f.parent.name == "mos":                                             # la última hora descargada, el número de estaciones y las fases de un plan son de cada proyecto
            palabras += ["2025-12-31", "de las 8", "alcance", "plan §", "gui/", "f1_estacion"]
        for palabra in palabras:
            assert palabra not in texto, f"{f.name}: {palabra}"
        # una coordenada UTM es un número de 6 o 7 cifras: ninguna en el código
        # 1e6 y 1e9: de bytes a MB y a GB; en las fuentes, 2e6 (bytes entre rangos de GFS) y 4e6 (puntos por bloque del LiDAR); en los casos, 100000 (fechas AAAAJJJHH e identificador de cada estación)
        arbol = ast.parse(texto)
        numeros = [n.value for n in ast.walk(arbol) if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))]
        grandes = [v for v in numeros if abs(v) >= 100000 and v not in (1e6, 1e9, 2e6, 4e6, 100000)]
        assert not grandes, f"{f.name}: {grandes}"
        assert not {40.25, 41.25} & set(numeros), f"{f.name}: ¿una caja de GFS?"
        sin_colores = re.sub(r"#[0-9a-fA-F]{6}\b|\b100000\b|viewBox=.[\d ]+", "", texto)     # viewBox: el tamaño de un icono
        assert not re.search(r"\b\d{3}[  ]?\d{3}\b|\b\d[  ]?\d{3}[  ]?\d{3}\b", sin_colores), f"{f.name}: ¿una coordenada en un texto?"


# Lo que no puede salir en la interfaz, que dice lo de cada planta: el nombre del cliente, el de la app, su entidad, sus servicios (van a planta.json, con sus créditos), su zona horaria y sus años
_INTERFAZ_NO = (r"[Gg]alera", r"\bENCE\b", r"\bence\b", r"\bence-", r"enceViento", r"CIRCE", r"\bcirce\b", r"Dacame", r"Santa Bàrbara", r"Montsià", r"Tarragona", r"Madrid", r"PNOA", r"\bIGN\b", r"\bOSM\b", r"OpenStreetMap", r"scne\.es",
                r"Catastro", r"CORINE", r"Copernicus", r"CartoCiudad", r"Meteocat", r"Cartogràfic", r"\b202[0-5]\b", r"\b5 años\b", r"_8est", r"25831", r"Z:\\", r"e2s", r"99-Test", r"cajon_reutilizable")
# Lo que no puede salir en lo que viene de fuera (three.js y sus controles), que no se ha escrito aquí: solo los nombres propios, porque una palabra corta puede estar en su código
_DE_FUERA_NO = (r"[Gg]alera", r"\bENCE\b", r"\bence\b", r"CIRCE", r"Dacame", r"Madrid", r"PNOA")


def test_la_interfaz_no_trae_nada_de_una_planta():
    # .py, y con ellos el JavaScript y el CSS de mapa_web y focos_mapa, que van en cadenas y aquí se leen como texto; .html; y, por separado, los .js de fuera
    gui = RAIZ / "core" / "gui"
    propios = [*gui.glob("*.py"), gui / "recursos" / "visor3d" / "plantilla.html"]
    assert {"mapa_web.py", "focos_mapa.py", "panel.py", "ventana.py", "tema.py", "principal.py", "plantilla.html"} <= {f.name for f in propios}
    for f in propios:
        texto = f.read_text(encoding="utf-8")
        for patron in _INTERFAZ_NO:
            assert not re.search(patron, texto), f"{f.name}: {patron}: {re.search(patron, texto)}"
        assert not re.search(r"\b\d{3}[ \u00a0\u202f]\d{3}\b", re.sub(r"#[0-9a-fA-F]{6}\b|viewBox=.[\d ]+", "", texto)), f"{f.name}: ¿una coordenada en un texto?"
    assert re.search(r"window\.mapaApp", (gui / "mapa_web.py").read_text(encoding="utf-8")), "¿se ha leído el JavaScript?"
    for nombre in ("three.min.js", "OrbitControls.js"):
        texto = (gui / "recursos" / "visor3d" / nombre).read_text(encoding="utf-8")
        for patron in _DE_FUERA_NO:
            assert not re.search(patron, texto), f"{nombre}: {patron}"
    # los ficheros de la planta no están en el core
    assert not list(gui.rglob("*.jpg")) and not list(gui.rglob("ejemplo*")) and not list(gui.rglob("*.png"))


def test_la_ficha_del_mapa_se_va_al_apartar_el_raton():
    # Leaflet la pone a opacidad 0 y la quita 200 ms después: con un `opacity:…!important` en la ficha sigue entera a la vista esos 200 ms (medido: 209 ms frente a 1 ms)
    gui = RAIZ / "core" / "gui"
    for nombre in ("mapa_web.py", "focos_mapa.py"):
        texto = (gui / nombre).read_text(encoding="utf-8")
        assert not re.search(r"\.leaflet-tooltip\{[^}]*opacity[^}]*!important", texto), nombre
        assert "L.Tooltip.mergeOptions({opacity: 1})" in texto, f"{nombre}: la ficha saldría al 90 % de opacidad, lo normal de Leaflet"


_TERCEROS = ("CALPUFF", "CALMET", "CALPOST", "AERMOD", "AERMET", "AERMAP", "AERSURFACE", "BPIP", "MAKEGEO")


def test_los_mensajes_no_nombran_programas_de_terceros():
    # un error o un aviso de puffs, relieve o superficie habla de sus ficheros, no del programa al que equivale
    malos = []
    for f in (RAIZ / "core").rglob("*.py"):
        if "_nucleo_gen" in f.name:
            continue
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Raise) or (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"):
                malos += [f"{f.name}:{c.lineno}: {c.value[:60]}" for c in ast.walk(n) if isinstance(c, ast.Constant) and isinstance(c.value, str)
                          and any(t in c.value for t in _TERCEROS)]
    assert not malos, malos


def test_rutas_relativas_a_la_carpeta_de_la_planta(tmp_path):
    c = _escribe(tmp_path / "entrada")
    (c / "rutas.json").write_text(json.dumps({"datos": "../datos"}), encoding="utf-8")
    assert planta.Planta(c).DATOS == (tmp_path / "datos").resolve()


def test_nueva_planta_se_activa_y_trae_lo_que_pide_la_interfaz(tmp_path):
    from teodors.gui.principal import CAMPOS
    from teodors.operacion import focos
    from teodors.planta import nueva
    raiz = nueva.crear(tmp_path / "otra_planta", "Otra planta", 41.63, 0.38, version="v9.9.9")
    assert (raiz / "VERSION").read_text(encoding="utf-8").strip() == "v9.9.9"
    compile((raiz / "main.py").read_text(encoding="utf-8"), "main.py", "exec")
    p = planta.activar(raiz / "entrada")
    assert p.EPSG_UTM == "EPSG:25831" and p.PREFIJO_ENV == "OTRA_PLANTA" and p.DATOS == (raiz / "datos").resolve()
    assert p.cargar_emplazamiento() == {"nombre": "Otra planta", "lat": 41.63, "lon": 0.38}
    for bloque, clave in CAMPOS:
        p.pide(bloque, clave)
    caja = p.pide("pronostico", "caja_gfs")          # alrededor de la planta y sobre la malla de GFS, de 0,25°
    assert caja["lat"][0] < 41.63 < caja["lat"][1] and caja["lon"][0] < 0.38 < caja["lon"][1] and caja["lat"][0] % 0.25 == 0
    assert focos.cargar()["focos"] == []
    with pytest.raises(FileExistsError):             # nunca encima de una planta que ya existe
        nueva.crear(tmp_path / "otra_planta", "Otra planta", 41.63, 0.38)


def test_nueva_planta_en_el_huso_de_sus_coordenadas(tmp_path):
    from teodors.planta import nueva
    p = planta.Planta(nueva.crear(tmp_path / "oeste", "Oeste", 42.0, -3.5) / "entrada")
    assert p.EPSG_UTM == "EPSG:25830"
