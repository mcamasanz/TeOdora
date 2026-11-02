# -*- coding: utf-8 -*-
"""Tanda 5: los casos movidos a teOdors frente al original de git, función a función.

    python comparar_movidos_tanda5.py <raíz de la planta> <commit original> <carpeta core nueva>

Por cada nombre del módulo, el TEXTO sin docstrings (caza comentarios y caracteres invisibles) y su AST. Cada diferencia esperada se quita de forma
explícita, con su motivo; lo demás tiene que dar igual byte a byte. Después, el diff entero de cada fichero (para ver también lo que queda fuera de las
funciones), lo de planta.json frente a las constantes del original, los envoltorios y lo que no puede quedar en el core.
"""
import ast
import difflib
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

PLANTA, COMMIT, CORE = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
RARO = {0xa0: "NBSP", 0x202f: "NNBSP", 0x2009: "fino", 0x200b: "ancho cero", 0x2011: "guion duro", 0xad: "guion blando", 0x2212: "menos"}
sys.stdout.reconfigure(encoding="utf-8")


def viejo(rel):
    return subprocess.run(["git", "-C", str(PLANTA), "show", f"{COMMIT}:{rel}"], capture_output=True, check=True).stdout.decode("utf-8").replace("\r\n", "\n")


def nuevo(rel):
    return (CORE / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def tabla(src):
    d = {}
    for n in ast.parse(src).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            d[n.name] = n
        elif isinstance(n, ast.Assign):
            for o in n.targets:
                for x in ast.walk(o):
                    if isinstance(x, ast.Name):
                        d[x.id] = n
    return d


def _doc(n):
    return isinstance(n, (ast.FunctionDef, ast.ClassDef)) and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str)


def texto_sin_doc(src, nodo):
    """El texto, comentarios incluidos, sin los docstrings."""
    lineas = src.splitlines(keepends=True)
    fuera = set()
    for n in ast.walk(nodo):
        if _doc(n):
            fuera.update(range(n.body[0].lineno, n.body[0].end_lineno + 1))
    return "".join(lineas[i - 1] for i in range(nodo.lineno, nodo.end_lineno + 1) if i not in fuera)


def ast_sin_doc(nodo):
    arbol = ast.parse(ast.unparse(nodo))
    for n in ast.walk(arbol):
        if _doc(n):
            n.body = n.body[1:] or [ast.Pass()]
    return ast.dump(arbol)


GUI = "lib/galera/gui/"
PARES = [(GUI + "tareas/control_fuentes.py", "preparacion/puffs/control_fuentes.py"), (GUI + "tareas/viento3d_casos.py", "casos/viento3d.py"),
         (GUI + "tareas/gfs_columnas.py", "casos/gfs_columnas.py"), (GUI + "receptores_mapa.py", "casos/receptores.py")]
V3D, GFS, REC, CF = "casos/viento3d.py", "casos/gfs_columnas.py", "casos/receptores.py", "preparacion/puffs/control_fuentes.py"

DEF = "valor por defecto de planta: None, y se resuelve al llamar"
MIGRA = "de galera.entradas y galera.viento a sus nombres en teodors.fuentes y teodors.metricas (ya son envoltorios de eso)"
CAB = "el nombre de la planta va a identidad.nombre_casos; la cabecera se compone al llamar y da el mismo texto (se comprueba abajo)"
R1 = ('        r1_km = config.pide("series", "r1_km") if r1_km is None else r1_km\n'
      '        rmax_km = config.pide("series", "rmax_km") if rmax_km is None else rmax_km\n')
R1_MES = ('    r1_km = config.bloque("series").get("r1_km") if r1_km is None else r1_km\n'
          '    rmax_km = config.bloque("series").get("rmax_km") if rmax_km is None else rmax_km\n')

ESPERADOS = {
    (CF, "geometria"): [("def geometria(foco, cota):\n", "def geometria(foco, cota, F):\n", "el módulo de los focos (gui/focos.py, tanda 6) llega por parámetro: preparacion no puede importar a galera; el cuerpo es el mismo")],
    (V3D, "TITULO_GEO"): [("ENCE La Galera", "%s", CAB)],
    (V3D, "TITULO_ERA5"): [("ENCE La Galera", "%s", CAB)],
    (V3D, "COMENTARIO_OBS"): [("ENCE La Galera", "%s", CAB)],
    (V3D, "rejilla"): [("celda_m=config.VIENTO3D_CELDA_M):\n", "celda_m=None):\n    celda_m = config.VIENTO3D_CELDA_M if celda_m is None else celda_m\n", DEF)],
    (V3D, "escribir_geo"): [("from galera.entradas import terreno", "from teodors.fuentes import terreno", MIGRA),
                            ("titulo=TITULO_GEO)", "titulo=cabecera(TITULO_GEO))", CAB)],
    (V3D, "obs_horarias"): [("from galera.entradas import estaciones", "from teodors.fuentes import meteocat as estaciones", MIGRA),
                            ("from galera.viento import validacion", "from teodors.metricas import viento as validacion", MIGRA)],
    (V3D, "preparar_mes"): [("r1_km=5.0, rmax_km=30.0, caso=None", "r1_km=None, rmax_km=None, caso=None", "los radios, de series en planta.json, y solo si hay estaciones (sin ellas no se usan)"),
                            ("from galera.entradas import meteo, terreno", "from teodors.fuentes import era5 as meteo, terreno", MIGRA),
                            ("        from galera.entradas import estaciones as est\n", R1 + "        from teodors.fuentes import meteocat as est\n", MIGRA + "; los radios, ver arriba"),
                            ("comentario=COMENTARIO_OBS)", "comentario=cabecera(COMENTARIO_OBS))", CAB),
                            ("titulo=TITULO_ERA5)", "titulo=cabecera(TITULO_ERA5))", CAB)],
    (V3D, "extraer_puntos"): [("from galera.entradas import estaciones", "from teodors.fuentes import meteocat as estaciones", MIGRA)],
    (V3D, "mes_serie"): [("estaciones=None, r1_km=5.0, rmax_km=30.0):", "estaciones=None, r1_km=None, rmax_km=None):", "los radios, de series en planta.json; sin estaciones y sin el bloque, None en el resumen"),
                         ("    from teodors.meteo.viento3d import almacen\n", "    from teodors.meteo.viento3d import almacen\n" + R1_MES, "los radios, de series en planta.json")],
    (GFS, "columnas"): [('N_COL, PASO_COL_M,\n                                              config.EPSG_UTM)',
                         'config.pide("pronostico", "n_col"),\n                                              config.pide("pronostico", "paso_col_m"), config.EPSG_UTM)', "n_col y paso_col_m, de pronostico en planta.json")],
    (REC, "malla"): [("NIVELES, discretos)", "niveles(), discretos)", "los niveles, de receptores en planta.json, al llamar")],
}
QUITADOS = {(GFS, "N_COL"): "a pronostico.n_col de planta.json", (GFS, "PASO_COL_M"): "a pronostico.paso_col_m de planta.json",
            (REC, "NIVELES"): "a receptores.niveles de planta.json", (REC, "ESTILOS"): "a receptores.estilos de planta.json"}
NUEVOS = {(V3D, "cabecera"): "compone una cabecera con identidad.nombre_casos, o teOdors si la planta no lo tiene",
          (REC, "niveles"): "lee receptores.niveles", (REC, "estilos"): "lee receptores.estilos"}

mal = 0
diferencias = []
iguales = 0
for v_rel, n_rel in PARES:
    print(f"\n== {n_rel} frente a {v_rel} ==")
    s0, s1 = viejo(v_rel), nuevo(n_rel)
    t0, t1 = tabla(s0), tabla(s1)
    for nombre in t0:
        if nombre not in t1:
            if (n_rel, nombre) in QUITADOS:
                print("quitado  ", nombre, "·", QUITADOS[(n_rel, nombre)])
                diferencias.append((n_rel, nombre, "quitado: " + QUITADOS[(n_rel, nombre)]))
            else:
                print("FALTA    ", nombre)
                mal += 1
            continue
        ta, tb = texto_sin_doc(s0, t0[nombre]), texto_sin_doc(s1, t1[nombre])
        motivos = []
        for de, a_, motivo in ESPERADOS.get((n_rel, nombre), []):
            if ta.count(de) != 1:
                print("ESPERADO SIN USO", nombre, repr(de))
                mal += 1
            ta = ta.replace(de, a_)
            motivos.append(motivo)
        if ta != tb:
            print("DISTINTO ", nombre)
            print("--- esperado\n" + ta + "--- hay\n" + tb)
            mal += 1
            continue
        mismo_ast = ast_sin_doc(t0[nombre]) == ast_sin_doc(t1[nombre])
        if motivos == [] and not mismo_ast:
            print("AST DISTINTO", nombre)
            mal += 1
        elif motivos and mismo_ast:
            print("EXPLICADO SIN DIFERENCIA", nombre)
            mal += 1
        elif not motivos:
            iguales += 1
            print("igual    ", nombre)
        else:
            print("explicado", nombre, "·", "; ".join(dict.fromkeys(motivos)))
            diferencias.append((n_rel, nombre, "; ".join(dict.fromkeys(motivos))))
    for nombre in t1:
        if nombre not in t0:
            if (n_rel, nombre) in NUEVOS:
                print("nuevo    ", nombre, "·", NUEVOS[(n_rel, nombre)])
                diferencias.append((n_rel, nombre, "nuevo: " + NUEVOS[(n_rel, nombre)]))
            else:
                print("SOBRA    ", nombre)
                mal += 1

print("\n== Diff entero, también docstrings y lo que queda fuera de las funciones ==")
for v_rel, n_rel in PARES:
    print(f"--- {n_rel}")
    for linea in difflib.unified_diff(viejo(v_rel).splitlines(), nuevo(n_rel).splitlines(), lineterm="", n=0):
        if not linea.startswith(("---", "+++", "@@")):
            print(linea)

print("\n== Caracteres invisibles, original -> nuevo (solo cuenta el código: los docstrings se han reescrito) ==")
cuenta = lambda t: {RARO[ord(c)]: t.count(c) for c in set(t) if ord(c) in RARO}
for v_rel, n_rel in PARES:
    print(n_rel, cuenta(viejo(v_rel)), "->", cuenta(nuevo(n_rel)))

print("\n== Imports de nivel superior del core ==")
estandar = set(sys.stdlib_module_names)
for _, n_rel in PARES:
    fuera = []
    for n in ast.parse(nuevo(n_rel)).body:
        if isinstance(n, ast.Import):
            fuera += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            fuera += [f"{n.module}.{a.name}" for a in n.names]
    print(n_rel, sorted(x for x in fuera if x.split(".")[0] not in estandar))
    mal += any("galera" in x for x in fuera)
    if n_rel.startswith("preparacion/"):
        mal += any("teodors.planta" in x or x == "teodors.planta" or "teodors.fuentes" in x for x in fuera)

print("\n== Lo que no puede quedar en el core ==")
for _, n_rel in PARES:
    t = nuevo(n_rel)
    for patron in (r"_8est", r"ENCE", r"[Gg]alera", r"CALPUFF|CALMET|AERMOD|AERMET|AERMAP|MAKEGEO|BPIP", r"99-Test", r"lib/"):
        n = len(re.findall(patron, t))
        if n:
            print("HAY", patron, "en", n_rel)
            mal += 1
ok = nuevo(V3D).count('"odora_run.log"') == 2
print("odora_run.log sigue, porque es un nombre de datos en disco", ok)
mal += not ok

print("\n== Constantes del original frente a planta.json y a los envoltorios ==")
sys.path[:0] = [str(PLANTA / "lib" / "paquetes"), str(PLANTA / "lib")]
pj = json.loads((PLANTA / "lib/galera/gui/planta/planta.json").read_text(encoding="utf-8"))
pj0 = json.loads(viejo("lib/galera/gui/planta/planta.json"))
import importlib  # noqa: E402

lit = lambda rel, nombre: ast.literal_eval(tabla(viejo(rel))[nombre].value)
vc = importlib.import_module("galera.gui.tareas.viento3d_casos")
gc = importlib.import_module("galera.gui.tareas.gfs_columnas")
rm = importlib.import_module("galera.gui.receptores_mapa")
cf = importlib.import_module("galera.gui.tareas.control_fuentes")
G0, R0, V0 = GUI + "tareas/gfs_columnas.py", GUI + "receptores_mapa.py", GUI + "tareas/viento3d_casos.py"
n0, p0 = ast.literal_eval(tabla(viejo(G0))["N_COL"].value)
comprobaciones = [
    ("N_COL y PASO_COL_M, mismo valor y tipo", (gc.N_COL, gc.PASO_COL_M, type(gc.N_COL), type(gc.PASO_COL_M)) == (n0, p0, type(n0), type(p0))),
    ("NIVELES, mismo valor y tipo", rm.NIVELES == lit(R0, "NIVELES") and [[type(x) for x in n] for n in rm.NIVELES] == [[type(x) for x in n] for n in lit(R0, "NIVELES")]),
    ("ESTILOS, mismo valor, tipo y orden", rm.ESTILOS == lit(R0, "ESTILOS") and list(rm.ESTILOS) == list(lit(R0, "ESTILOS")) and all(isinstance(v, tuple) for v in rm.ESTILOS.values())),
    ("TITULO_GEO, TITULO_ERA5 y COMENTARIO_OBS, el mismo texto", all(getattr(vc, k) == lit(V0, k) for k in ("TITULO_GEO", "TITULO_ERA5", "COMENTARIO_OBS"))),
    ("cabeceras en ASCII", all(getattr(vc, k).isascii() for k in ("TITULO_GEO", "TITULO_ERA5", "COMENTARIO_OBS"))),
]
for funcion in ("preparar_mes", "mes_serie"):
    sig = {a.arg: d for a, d in zip(tabla(viejo(V0))[funcion].args.args[::-1], tabla(viejo(V0))[funcion].args.defaults[::-1])}
    comprobaciones.append((f"r1_km y rmax_km de {funcion}: los mismos", (ast.literal_eval(sig["r1_km"]), ast.literal_eval(sig["rmax_km"])) == (pj["series"]["r1_km"], pj["series"]["rmax_km"])))
comprobaciones.append(("geometria del envoltorio, con la firma de antes", str(inspect.signature(cf.geometria)) == "(foco, cota)"))
# planta.json: los bloques y campos de antes, sin tocar
quita = {"identidad": {"nombre_casos"}, "receptores": {"niveles", "estilos", "nota"}, "pronostico": {"n_col", "paso_col_m", "nota"}}
for bloque in pj0:
    if isinstance(pj0[bloque], dict):
        a = {k: v for k, v in pj0[bloque].items() if k != "nota" or bloque != "pronostico"}
        b = {k: v for k, v in pj[bloque].items() if k not in quita.get(bloque, ())}
        comprobaciones.append((f"planta.json, bloque {bloque}: lo de antes, igual", a == b))
comprobaciones.append(("planta.json: el único bloque nuevo es series", set(pj) - set(pj0) == {"series"} and set(pj["series"]) == {"r1_km", "rmax_km", "nota"}))
comprobaciones.append(("planta.json, nota de pronostico: la de antes, ampliada", pj["pronostico"]["nota"].startswith(pj0["pronostico"]["nota"])))
for texto, ok in comprobaciones:
    print(texto, ok)
    mal += not ok

print("\n== Envoltorios: cada nombre del original sigue, también los privados ==")
for v_rel, n_rel in PARES:
    modulo = v_rel[4:-3].replace("/", ".")
    mod = importlib.import_module(modulo)
    nombres = set(tabla(viejo(v_rel)))
    for n in ast.parse(viejo(v_rel)).body:                  # y lo importado, que también se usa desde fuera (gc.NIVELES)
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            nombres |= {(a.asname or a.name).split(".")[0] for a in n.names}
    faltan = sorted(n for n in nombres if not hasattr(mod, n) and n not in ("galera", "F"))
    print(modulo, len(nombres), "nombres; sin él:", faltan)
    if v_rel.endswith("control_fuentes.py"):
        print("   F:", hasattr(mod, "F"))
    # importados en el original que el nuevo ya no necesita
    permitidos = {"config", "geo"} if not n_rel.startswith("casos") else set()
    mal += bool(set(faltan) - permitidos)
    definidos = [n.name if isinstance(n, ast.FunctionDef) else "=" for n in ast.parse(Path(PLANTA, v_rel).read_text(encoding="utf-8")).body if isinstance(n, (ast.FunctionDef, ast.Assign))]
    print("   lo que define el envoltorio:", definidos)
    mal += set(definidos) - {"__getattr__", "geometria"} != set()

print("\n== Diferencias, para el informe ==")
for f, n, motivo in diferencias:
    print(f"{f} · {n}: {motivo}")
print(f"\n{iguales} nombres iguales en texto y AST, {len(diferencias)} con su explicación")
print("RESULTADO:", "todo igual, salvo lo que se dice" if not mal else f"{mal} distintos")
sys.exit(1 if mal else 0)
