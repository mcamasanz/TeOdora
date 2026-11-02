# -*- coding: utf-8 -*-
"""Tanda 3: las fuentes de datos movidas a teOdors frente al original de git, función a función.

    python comparar_movidos_tanda3.py <raíz de la planta> <commit original> <carpeta core nueva>

Por cada nombre del módulo, el TEXTO de la función sin docstrings (caza comentarios y caracteres invisibles) y su AST. Cada diferencia
esperada se quita de forma explícita, con su motivo; lo demás tiene que dar igual byte a byte. Después, las constantes de planta.json
frente a las del original, los envoltorios frente a los nombres del original y las versiones de HTTP con reintentos.
"""
import ast
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

PLANTA, COMMIT, CORE = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
RARO = {0xa0: "NBSP", 0x202f: "NNBSP", 0x2009: "fino", 0x200b: "ancho cero", 0x2011: "guion duro", 0xad: "guion blando", 0x2212: "menos"}
sys.stdout.reconfigure(encoding="utf-8")


def viejo(rel):
    return subprocess.run(["git", "-C", str(PLANTA), "show", f"{COMMIT}:{rel}"], capture_output=True, check=True).stdout.decode("utf-8").replace("\r\n", "\n")


def nuevo(rel):
    return (CORE / "fuentes" / rel).read_text(encoding="utf-8")


def sin_docstring(nodo):
    for n in ast.walk(nodo):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Module)) and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str) and len(n.body) > 1:
            n.body = n.body[1:]
    return nodo


def tabla(src):
    d = {}
    for n in ast.parse(src).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            d[n.name] = n
        elif isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name):
            d[n.targets[0].id] = n
    return d


def texto_sin_doc(src, nodo):
    """El texto de la función, comentarios incluidos, sin los docstrings."""
    lineas = src.splitlines(keepends=True)
    fuera = set()
    for n in ast.walk(nodo):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) \
                and isinstance(n.body[0].value.value, str):
            fuera.update(range(n.body[0].lineno, n.body[0].end_lineno + 1))
    return "".join(lineas[i - 1] for i in range(nodo.lineno, nodo.end_lineno + 1) if i not in fuera)


PARES = [("lib/galera/entradas/terreno.py", "terreno.py"), ("lib/galera/entradas/edificios.py", "catastro.py"),
         ("lib/galera/entradas/estaciones.py", "meteocat.py"), ("lib/galera/entradas/meteo.py", "era5.py"),
         ("lib/galera/gui/tareas/descargar_era5.py", "descargar_era5.py"), ("lib/galera/gui/tareas/descargar_meteocat.py", "descargar_meteocat.py"),
         ("lib/galera/gui/tareas/descargar_gfs_niveles.py", "gfs_noaa.py"), ("lib/galera/gui/tareas/descargar_gfs_historico.py", "gfs_dynamical.py"),
         ("lib/galera/gui/tareas/lidar_planta.py", "lidar.py")]

DEF = "valor por defecto de planta: None, y se resuelve al llamar"
GEO = "geo de teodors.planta"
AGENTE = "agente HTTP de planta.json"
COM = "comentario sin el cajón ni nombres de pueblos"
REG = "registro de teodors.comun: necesita carpeta y prefijo"
GEO_L = ("from galera import geo\n", "from teodors.planta import geo\n", GEO)
AG = ('"Mozilla/5.0 ENCE-Galera"', "config.AGENTE_HTTP", AGENTE)
RES_L = "    res_m = config.RES_TERRENO_M if res_m is None else res_m\n"
ANIOS_L = "    anios = config.REANALISIS_ANIOS if anios is None else anios\n"
RADIO_L = '    radio_km = config.pide("estaciones", "radio_km") if radio_km is None else radio_km\n'
REGISTRO = ("    log = _planta.asegurar_carpetas(); registro.configurar(_planta.DIR_LOGS, _planta.REGISTRO)\n", "    config.asegurar_carpetas()\n    log = registro.configurar(config.DIR_LOGS, config.REGISTRO)\n", REG)

ESPERADOS = {
    ("terreno.py", "rejilla"): [("res_m=config.RES_TERRENO_M):\n", "res_m=None):\n" + RES_L, DEF), GEO_L],
    ("terreno.py", "caso_dir"): [("res_m=config.RES_TERRENO_M):\n", "res_m=None):\n" + RES_L, DEF)],
    ("terreno.py", "_wcs_tramo"): [AG],
    ("terreno.py", "descargar_mdt"): [("# negativos espurios a 0 (cajón)", "# negativos espurios a 0", COM)],
    ("terreno.py", "leer_corine"): [('"la variable de entorno ENCE_GALERA_CORINE."', '''f"la variable de entorno {config.nombre_env('CORINE')}."''', "la variable lleva el prefijo de la planta")],
    ("terreno.py", "resumen"): [GEO_L],
    ("terreno.py", "nombres_nucleos"): [AG],
    ("terreno.py", "en_punto"): [GEO_L],
    ("terreno.py", "descargar"): [("res_m=config.RES_TERRENO_M, progreso=None, cancelado=None):\n", "res_m=None, progreso=None, cancelado=None):\n" + RES_L, DEF)],
    ("catastro.py", "dir_caso"): [("radio_km=config.RADIO_EDIFICIOS_KM):\n", "radio_km=None):\n    radio_km = config.RADIO_EDIFICIOS_KM if radio_km is None else radio_km\n", DEF)],
    ("catastro.py", "_http"): [AG],
    ("catastro.py", "descargar"): [("radio_km=config.RADIO_EDIFICIOS_KM, progreso=None):\n", "radio_km=None, progreso=None):\n    radio_km = config.RADIO_EDIFICIOS_KM if radio_km is None else radio_km\n", DEF), GEO_L],
    ("catastro.py", "cercanos"): [("radio_m=config.RADIO_EDIFICIOS_FOCOS_M):\n", "radio_m=None):\n    radio_m = config.RADIO_EDIFICIOS_FOCOS_M if radio_m is None else radio_m\n", DEF)],
    ("catastro.py", "cargar"): [("radio_km=config.RADIO_EDIFICIOS_KM):\n", "radio_km=None):\n", DEF)],
    ("catastro.py", "en_punto"): [GEO_L],
    ("meteocat.py", "_get"): [('"ENCE-Galera/0.1"', 'config.bloque("estaciones").get("agente_http", config.AGENTE_HTTP)', "agente HTTP de planta.json, bloque estaciones")],
    ("meteocat.py", "cercanas"): [("radio_km=20.0, solo_operativas=True):\n", "radio_km=None, solo_operativas=True):\n" + RADIO_L, "radio de planta.json"), GEO_L],
    ("meteocat.py", "altura_viento"): [("'2021-01-01T00:00:00'", "'{config.REANALISIS_ANIOS[0]}-01-01T00:00:00'", "desde el primer año del reanálisis de la planta")],
    ("meteocat.py", "anio_estacion"): [("(~120 000 lecturas)", "(~120 mil lecturas)", "comentario: no es una coordenada"), ("(medido el 2026-10-15 con l'Aldea 2024)", "(medido el 2026-10-15)", COM)],
    ("meteocat.py", "descargar"): [("anios=config.REANALISIS_ANIOS, radio_km=20.0):\n", "anios=None, radio_km=None):\n" + ANIOS_L + RADIO_L, DEF)],
    ("meteocat.py", "cargar"): [("anios=config.REANALISIS_ANIOS):\n", "anios=None):\n" + ANIOS_L, DEF)],
    ("meteocat.py", "para_mapa"): [("radio_km=20.0):\n", "radio_km=None):\n", "radio de planta.json (lo resuelve cercanas)")],
    ("era5.py", "punto_era5"): [GEO_L],
    ("era5.py", "_quincena_pfl"): [GEO_L],
    ("era5.py", "descargar_reanalisis"): [("anios=config.REANALISIS_ANIOS, hilos=2, progreso=None):\n", "anios=None, hilos=2, progreso=None):\n" + ANIOS_L, DEF)],
    ("era5.py", "cargar_sfc"): [("anios=config.REANALISIS_ANIOS):\n", "anios=None):\n" + ANIOS_L, DEF)],
    ("era5.py", "cargar_pfl"): [("anios=config.REANALISIS_ANIOS):\n", "anios=None):\n" + ANIOS_L, DEF)],
    ("descargar_era5.py", "main"): [REGISTRO],
    ("descargar_meteocat.py", "main"): [REGISTRO],
    ("gfs_noaa.py", "plazo"): [("# solo aquí: quien solo quiere NIVELES (gfs_columnas) no lo necesita\n", "# solo aquí: quien solo quiere NIVELES no lo necesita\n    J, I = indices_caja()\n", "caja de planta.json")],
    ("gfs_noaa.py", "ejecucion"): [("    plazos = list(plazos)\n", "    import xarray as xr\n    plazos = list(plazos)\n", "xarray perezoso: test_importa"),
                                   ("    lat = 90.0 - 0.25", "    J, I = indices_caja()\n    lat = 90.0 - 0.25", "caja de planta.json"),
                                   ("    lon = 0.25 * np.arange(1440)[I]\n", "    lon = (0.25 * np.arange(1440)[I] + 180.0) % 360.0 - 180.0        # de −180 a 180, y creciente: se interpola en ella\n", "longitud al oeste de Greenwich; los mismos bits aquí"),
                                   ("np.full((5, 5), np.nan", "np.full((len(lat), len(lon)), np.nan", "el tamaño sale de la caja")],
    ("gfs_noaa.py", "main"): [("default=SEMANAS", "default=None", "semanas de planta.json"),
                              ("    a = ap.parse_args()\n", '    a = ap.parse_args()\n    if a.semanas is None:\n        a.semanas = config.pide("pronostico", "semanas_mos")\n', "semanas de planta.json")],
    ("gfs_dynamical.py", "abrir"): [("    import zarr\n", "    import xarray as xr\n    import zarr\n", "xarray perezoso: test_importa")],
    ("gfs_dynamical.py", "main"): [("    a = ap.parse_args()\n    SALIDA.mkdir", '    a = ap.parse_args()\n    import xarray as xr\n    salida, caja = config.DATOS / "meteo" / "gfs", config.pide("pronostico", "caja_gfs")\n    salida.mkdir', "DATOS y caja al llamar, no al importar; xarray perezoso"),
                                   ('CAJA["lat"]', 'caja["lat"]', "caja de planta.json"), ('CAJA["lon"]', 'caja["lon"]', "caja de planta.json"),
                                   ('"caja": CAJA,', '"caja": caja,', "caja de planta.json"), ("SALIDA /", "salida /", "DATOS al llamar")],
}
QUITADOS = {("gfs_noaa.py", "SEMANAS"): "bloque pronostico de planta.json", ("gfs_noaa.py", "J"): "indices_caja", ("gfs_noaa.py", "I"): "indices_caja",
            ("gfs_dynamical.py", "SALIDA"): "se calcula en main", ("gfs_dynamical.py", "CAJA"): "bloque pronostico de planta.json"}
NUEVOS = {("gfs_noaa.py", "indices_caja"): "de la caja de planta.json a filas y columnas", ("meteocat.py", "estaciones_dias"): "viene de gui/tareas/viento_dia_local.py (se compara aparte)",
          ("lidar.py", "rejillas"): "el cuerpo del main original (se compara aparte)"}

mal = 0
diferencias = []
for v_rel, n_rel in PARES:
    print(f"\n== {n_rel} frente a {v_rel} ==")
    s0, s1 = viejo(v_rel), nuevo(n_rel)
    t0, t1 = tabla(s0), tabla(s1)
    if n_rel == "lidar.py":
        continue
    for nombre in t0:
        if nombre not in t1:
            if (n_rel, nombre) in QUITADOS:
                print("quitado ", nombre, "·", QUITADOS[(n_rel, nombre)])
                diferencias.append((n_rel, nombre, "quitado: " + QUITADOS[(n_rel, nombre)]))
            else:
                print("FALTA   ", nombre)
                mal += 1
            continue
        a, b = t0[nombre], t1[nombre]
        ta, tb = texto_sin_doc(s0, a), texto_sin_doc(s1, b)
        motivos = []
        for de, a_, motivo in ESPERADOS.get((n_rel, nombre), []):
            if de not in ta:
                print("ESPERADO SIN USO", nombre, repr(de))
                mal += 1
            ta = ta.replace(de, a_)
            motivos.append(motivo)
        igual_txt = ta == tb
        if not igual_txt and isinstance(a, ast.Assign) and ast.dump(sin_docstring(a)) == ast.dump(sin_docstring(b)):
            igual_txt = None
        if igual_txt is False:
            print("DISTINTO", nombre)
            print("--- esperado\n" + ta + "--- hay\n" + tb)
            mal += 1
        else:
            print(("igual   " if not motivos else "explicado"), nombre, ("· " + "; ".join(dict.fromkeys(motivos))) if motivos else "", "(comentario de la asignación)" if igual_txt is None else "")
            if motivos:
                diferencias.append((n_rel, nombre, "; ".join(dict.fromkeys(motivos))))
    for nombre in t1:
        if nombre not in t0:
            if (n_rel, nombre) in NUEVOS:
                print("nuevo   ", nombre, "·", NUEVOS[(n_rel, nombre)])
                diferencias.append((n_rel, nombre, "nuevo: " + NUEVOS[(n_rel, nombre)]))
            else:
                print("SOBRA   ", nombre)
                mal += 1

print("\n== meteocat.estaciones_dias frente a gui/tareas/viento_dia_local.py ==")
s0 = viejo("lib/galera/gui/tareas/viento_dia_local.py")
a, b = tabla(s0)["estaciones_dias"], tabla(nuevo("meteocat.py"))["estaciones_dias"]
ta = texto_sin_doc(s0, a)
n = ta.count("estaciones.")
ta = ta.replace("estaciones.", "")
ok = ta == texto_sin_doc(nuevo("meteocat.py"), b)
print("igual, quitando el prefijo «estaciones.» de", n, "usos" if ok else "DISTINTO")
mal += not ok
ok = "def estaciones_dias" not in (PLANTA / "lib/galera/gui/tareas/viento_dia_local.py").read_text(encoding="utf-8")
print("ya no está en viento_dia_local:", ok)
mal += not ok

print("\n== lidar.rejillas + lidar.main frente al main original ==")
s0, s1 = viejo("lib/galera/gui/tareas/lidar_planta.py"), nuevo("lidar.py")
t0, t1 = tabla(s0), tabla(s1)
cuerpo0 = texto_sin_doc(s0, t0["main"])
cuerpo1 = texto_sin_doc(s1, t1["rejillas"])
ini = cuerpo0.index("    import laspy\n")
ok = cuerpo0[ini:] == cuerpo1[cuerpo1.index("    import laspy\n"):]
print("desde «import laspy» hasta el final, byte a byte:", ok)
mal += not ok
print("cabecera del main original:\n" + cuerpo0[:ini] + "main nuevo:\n" + texto_sin_doc(s1, t1["main"]))
diferencias.append(("lidar.py", "main", "partido en rejillas (el cuerpo, igual) y main; la zona por defecto ya no está aquí: main(zona=…)"))

print("\n== Caracteres invisibles, original -> nuevo ==")
cuenta = lambda t: {RARO[ord(c)]: t.count(c) for c in set(t) if ord(c) in RARO}
for v_rel, n_rel in PARES:
    a, b = cuenta(viejo(v_rel)), cuenta(nuevo(n_rel))
    print(n_rel, a, "->", b)

print("\n== Imports de nivel superior del core ==")
estandar = set(sys.stdlib_module_names)
for _, n_rel in PARES:
    fuera = []
    for n in ast.parse(nuevo(n_rel)).body:
        if isinstance(n, ast.Import):
            fuera += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            fuera.append(n.module)
    print(n_rel, sorted(x for x in fuera if x.split(".")[0] not in estandar))
    mal += any("galera" in x for x in fuera)

print("\n== Constantes del original frente a planta.json ==")
sys.path[:0] = [str(PLANTA / "lib" / "paquetes"), str(PLANTA / "lib")]
pj = json.loads((PLANTA / "lib/galera/gui/planta/planta.json").read_text(encoding="utf-8"))
g = {}
fuente_gfs = viejo("lib/galera/gui/tareas/descargar_gfs_niveles.py")
for n in ast.parse(fuente_gfs).body:
    if isinstance(n, ast.Assign) and n.targets[0].id in ("SEMANAS", "J", "I"):
        exec(ast.unparse(n), g)
for n in ast.parse(viejo("lib/galera/gui/tareas/descargar_gfs_historico.py")).body:
    if isinstance(n, ast.Assign) and n.targets[0].id == "CAJA":
        exec(ast.unparse(n), g)
for rel, nombre, clave in (("lib/galera/gui/tareas/f1_estacion.py", "CEROS_SOSPECHOSOS", "ceros_sospechosos"), ("lib/galera/gui/tareas/viento3d_series.py", "ESTACIONES", "codigos")):
    n = tabla(viejo(rel))[nombre]
    exec(ast.unparse(n), g)
    print(nombre, g[nombre] == pj["estaciones"][clave])
    mal += g[nombre] != pj["estaciones"][clave]
ok = list(eval(ast.unparse(tabla(viejo("lib/galera/gui/tareas/mos_tabla.py"))["ESTACIONES"].value))) == pj["estaciones"]["codigos"]
print("ESTACIONES de mos_tabla", ok)
mal += not ok
ok = g["SEMANAS"] == pj["pronostico"]["semanas_mos"]
print("SEMANAS", ok)
mal += not ok
ok = {k: list(v) for k, v in g["CAJA"].items()} == pj["pronostico"]["caja_gfs"]
print("CAJA", ok)
mal += not ok
ok = tuple(pj["viento_local"]["lidar_zona"]) == (286512.0, 4507400.0, 600.0)
print("zona del LiDAR", ok)
mal += not ok
ok = pj["identidad"]["agente_http"] == "Mozilla/5.0 ENCE-Galera" and pj["estaciones"]["agente_http"] == "ENCE-Galera/0.1"
print("agentes HTTP", ok)
mal += not ok

print("\n== Envoltorios: cada nombre del original sigue, también los privados ==")
import importlib  # noqa: E402

import numpy as np  # noqa: E402

for v_rel, _ in PARES:
    modulo = v_rel[4:-3].replace("/", ".")
    m = importlib.import_module(modulo)
    faltan = [n for n in tabla(viejo(v_rel)) if not hasattr(m, n)]
    print(modulo, len(tabla(viejo(v_rel))), "nombres; sin él:", faltan)
    n_quitados = {n for (f, n) in QUITADOS if f == dict(PARES)[v_rel]}
    mal += set(faltan) != n_quitados
gfs = importlib.import_module("teodors.fuentes.gfs_noaa")
J, I = gfs.indices_caja()
lat_o, lon_o = 90.0 - 0.25 * np.arange(721)[g["J"]], 0.25 * np.arange(1440)[g["I"]]
lat_n, lon_n = 90.0 - 0.25 * np.arange(721)[J], (0.25 * np.arange(1440)[I] + 180.0) % 360.0 - 180.0
malla = np.arange(721 * 1440, dtype=float).reshape(721, 1440)
ok = J == g["J"] and lat_o.tobytes() == lat_n.tobytes() and lon_o.tobytes() == lon_n.tobytes() and malla[g["J"], g["I"]].tobytes() == malla[J, I].tobytes()
print("caja de NOAA: mismas filas, mismas latitudes y longitudes byte a byte, mismo recorte:", ok)
mal += not ok

print("\n== HTTP con reintentos: se mueven tal cual, ninguna fundida ==")
versiones = {"terreno._wcs_tramo": tabla(nuevo("terreno.py"))["_wcs_tramo"], "catastro._http": tabla(nuevo("catastro.py"))["_http"],
             "meteocat._get": tabla(nuevo("meteocat.py"))["_get"], "gfs_noaa._get": tabla(nuevo("gfs_noaa.py"))["_get"],
             "gfs_dynamical.leer": tabla(nuevo("gfs_dynamical.py"))["leer"]}
web = (PLANTA / "lib/galera/gui/web.py").read_text(encoding="utf-8")
versiones["gui/web._descarga (se queda)"] = tabla(web)["_descarga"]
vistos = Counter(ast.dump(sin_docstring(v)) for v in versiones.values())
print(list(versiones), "· idénticas entre sí:", sum(c - 1 for c in vistos.values()))

print("\n== a_horario y medias_horarias: no se han tocado ==")
for repo, rel in ((PLANTA, "lib/galera/viento/validacion.py"), (CORE.parent, "core/preparacion/viento3d/estaciones.py")):
    r = subprocess.run(["git", "-C", str(repo), "status", "--short", "--", rel], capture_output=True, text=True).stdout.strip()
    print(rel, "sin cambios" if not r else r)
    mal += bool(r)

print("\n== Diferencias, para el informe ==")
for f, n, m in diferencias:
    print(f"{f} · {n}: {m}")
print("\nRESULTADO:", "todo igual, salvo lo que se dice" if not mal else f"{mal} distintos")
sys.exit(1 if mal else 0)
