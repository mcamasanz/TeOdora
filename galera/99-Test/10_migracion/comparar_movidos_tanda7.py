# -*- coding: utf-8 -*-
"""Tanda 7: el MOS movido a teOdors frente al original de git, función a función.

    python comparar_movidos_tanda7.py <raíz de la planta> <commit original de la planta> <carpeta core nueva>

Por cada nombre del módulo, el TEXTO sin docstrings (caza comentarios y caracteres invisibles) y su AST. Cada diferencia esperada se quita de forma explícita, con su
motivo; lo demás tiene que dar igual byte a byte. Después: el diff entero de cada fichero, lo de planta.json frente a las constantes del original, los envoltorios,
quién importa estos ficheros y lo que no puede quedar en el core. No lanza ningún entrenamiento: los datos del MOS están en Z:.
"""
import ast
import difflib
import json
import os
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
TAB, ENT = "mos/tabla.py", "mos/entrenar.py"
PARES = [(GUI + "tareas/mos_tabla.py", TAB), (GUI + "tareas/mos_entrenar.py", ENT)]
PEREZOSO = "scikit-learn, joblib y xarray, al usarlos: hay que poder importar el módulo sin el extra `mos`"
ESTACIONES = "las estaciones se leían al importar: ahora, al empezar, de estaciones.codigos"

ESPERADOS = {
    (TAB, "gfs"): [('def gfs(desde="2021-05", hasta=HASTA):\n', 'def gfs(desde="2021-05", hasta=None):\n    import xarray as xr\n    hasta = config.pide("pronostico", "mos_hasta") if hasta is None else hasta\n',
                    "la última hora, de pronostico.mos_hasta, al llamar; " + PEREZOSO)],
    (TAB, "main"): [('.parse_args()\n    salida = config.DATOS / "mos"\n', '.parse_args()\n    ESTACIONES = tuple(config.pide("estaciones", "codigos"))\n    HASTA = config.pide("pronostico", "mos_hasta")\n    salida = config.DATOS / "mos"\n',
                     ESTACIONES + "; la última hora, de pronostico.mos_hasta")],
    (ENT, "entrenar_gb"): [("    m = HistGradientBoostingRegressor(**GB).fit(", "    from sklearn.ensemble import HistGradientBoostingRegressor\n    m = HistGradientBoostingRegressor(**GB).fit(", PEREZOSO)],
    (ENT, "main"): [('.parse_args()\n    base = config.DATOS / "mos"\n',
                     '.parse_args()\n    import joblib\n    from sklearn.linear_model import Ridge\n    from sklearn.pipeline import make_pipeline\n    from sklearn.preprocessing import StandardScaler\n    ESTACIONES = tuple(config.pide("estaciones", "codigos"))\n    base = config.DATOS / "mos"\n',
                     PEREZOSO + "; " + ESTACIONES),
                    ("media de las 8 estaciones", "media de las {len(ESTACIONES)} estaciones", "las 8 eran las de la planta: mismo texto con 8")],
}
QUITADOS = {(TAB, "ESTACIONES"): "se leía al importar: ahora en main, de estaciones.codigos", (TAB, "HASTA"): "a pronostico.mos_hasta de planta.json"}
NUEVOS = {}

mal = 0
iguales = 0
diferencias = []
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
            print("EXPLICADO, PERO NO CUADRA CON EL AST", nombre)
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
    # los docstrings de las funciones no se han tocado; el del módulo y el pie, aparte
    for nombre in t0:
        if nombre in t1 and isinstance(t0[nombre], ast.FunctionDef) and ast.get_docstring(t0[nombre]) != ast.get_docstring(t1[nombre]):
            print("DOCSTRING DISTINTO", nombre)
            mal += 1
    pie = 'if __name__ == "__main__":\n    main()\n'
    if not (s0.endswith(pie) and s1.endswith(pie)):
        print("PIE DISTINTO")
        mal += 1

print("\n== Diff entero, también docstrings y lo que queda fuera de las funciones ==")
for v_rel, n_rel in PARES:
    print(f"--- {n_rel}")
    for linea in difflib.unified_diff(viejo(v_rel).splitlines(), nuevo(n_rel).splitlines(), lineterm="", n=0):
        if not linea.startswith(("---", "+++", "@@")):
            print(linea)

print("\n== Caracteres invisibles, original -> nuevo ==")
cuenta = lambda t: {RARO[ord(c)]: t.count(c) for c in set(t) if ord(c) in RARO}
for v_rel, n_rel in PARES:
    a, b = cuenta(viejo(v_rel)), cuenta(nuevo(n_rel))
    print(n_rel, a, "->", b)
    mal += a != b

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
    mal += any("galera" in x or x.startswith(("sklearn", "joblib", "xarray", "PySide6", "folium")) for x in fuera)

print("\n== Lo que no puede quedar en el core ==")
for _, n_rel in PARES + [(None, "mos/__init__.py")]:
    t = nuevo(n_rel)
    for patron in (r"_8est", r"ENCE", r"[Gg]alera", r"CALPUFF|CALMET|AERMOD|AERMET|AERMAP|MAKEGEO|BPIP", r"99-Test", r"gui/", r"Madrid", r"CIRCE", r"2025-12-31", r"alcance", r"plan §", r"de las 8", r"\bC9\b"):
        if re.search(patron, t):
            print("HAY", patron, "en", n_rel)
            mal += 1
print("revisado")

print("\n== Quién importa estos dos ficheros en la planta (grafo real) ==")
quien = []
for f in [PLANTA / "main.py", *(PLANTA / "lib" / "galera").rglob("*.py")]:
    for n in ast.walk(ast.parse(f.read_bytes().decode("utf-8"))):
        nombres = [a.name for a in n.names] if isinstance(n, ast.Import) else ([n.module or ""] + [f"{n.module}.{a.name}" for a in n.names]) if isinstance(n, ast.ImportFrom) else []
        if any(re.search(r"mos_(tabla|entrenar)|teodors\.mos", x) for x in nombres):
            quien.append(f.relative_to(PLANTA).as_posix())
print(sorted(set(quien)))
mal += set(quien) != {GUI + "tareas/mos_tabla.py", GUI + "tareas/mos_entrenar.py"}

print("\n== Constantes del original frente a planta.json y a los envoltorios ==")
if os.environ.get("T7_PAQUETES"):                   # antes de fijar el clon: el core de desarrollo
    sys.path.insert(0, os.environ["T7_PAQUETES"])
    import teodors  # noqa: F401
sys.path[:0] = [str(PLANTA / "lib" / "paquetes"), str(PLANTA / "lib")]
import importlib  # noqa: E402

pj = json.loads((PLANTA / "lib/galera/gui/planta/planta.json").read_text(encoding="utf-8"))
pj0 = json.loads(viejo("lib/galera/gui/planta/planta.json"))
T = importlib.import_module("galera.gui.tareas.mos_tabla")
E = importlib.import_module("galera.gui.tareas.mos_entrenar")
from teodors.mos import entrenar as e_core, tabla as t_core  # noqa: E402

print("el core es el de", Path(t_core.__file__).resolve())
mal += Path(t_core.__file__).resolve().parent != (CORE / "mos").resolve()
hasta0 = ast.literal_eval(tabla(viejo(GUI + "tareas/mos_tabla.py"))["HASTA"].value)
a_pj = {k: v for k, v in pj["pronostico"].items() if k not in ("mos_hasta", "nota")}
b_pj = {k: v for k, v in pj0["pronostico"].items() if k != "nota"}
comprobaciones = [
    ("HASTA, el mismo", pj["pronostico"]["mos_hasta"] == hasta0 and T.HASTA == hasta0),
    ("ESTACIONES de los dos, las mismas y en su orden", T.ESTACIONES == tuple(pj0["estaciones"]["codigos"]) and E.ESTACIONES == T.ESTACIONES),
    ("planta.json: lo de antes, igual", all(pj[k] == pj0[k] for k in pj0 if k != "pronostico") and set(pj) == set(pj0) and a_pj == b_pj),
    ("planta.json, nota de pronostico: la de antes, ampliada", all(trozo in pj["pronostico"]["nota"] for trozo in pj0["pronostico"]["nota"].split(" n_col"))),
    ("mos no es un motor", "mos" not in importlib.import_module("teodors").MOTORES),
]
for texto, ok in comprobaciones:
    print(texto, ok)
    mal += not ok

print("\n== Envoltorios: cada nombre del original sigue, también los importados ==")
PERMITIDOS = {"joblib", "HistGradientBoostingRegressor", "Ridge", "make_pipeline", "StandardScaler", "xr"}     # se importan al usarlos: ya no son del módulo
for v_rel, n_rel in PARES:
    modulo = v_rel[4:-3].replace("/", ".")
    mod = importlib.import_module(modulo)
    nombres = set(tabla(viejo(v_rel)))
    for n in ast.parse(viejo(v_rel)).body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            nombres |= {(a.asname or a.name).split(".")[0] for a in n.names}
    faltan = sorted(n for n in nombres if not hasattr(mod, n))
    print(modulo, len(nombres), "nombres; sin él:", faltan)
    mal += bool(set(faltan) - PERMITIDOS)
    definidos = [n.name if isinstance(n, ast.FunctionDef) else "=" for n in ast.parse(Path(PLANTA, v_rel).read_bytes().decode("utf-8")).body if isinstance(n, (ast.FunctionDef, ast.Assign))]
    print("   lo que define el envoltorio:", definidos)
    mal += definidos != ["__getattr__"]

print("\n== Lo que se pone en un envoltorio llega al código movido ==")
for m, core, nombre in ((T, t_core, "error_dir"), (E, e_core, "GB")):
    orig = getattr(m, nombre)
    falso = object()
    setattr(m, nombre, falso)
    ok = getattr(core, nombre) is falso and getattr(m, nombre) is falso
    setattr(m, nombre, orig)
    ok = ok and getattr(core, nombre) is orig
    print(f"{m.__name__}.{nombre}:", ok)
    mal += not ok

print("\n== --help de las dos tareas, por el envoltorio y por el core ==")
env = dict(os.environ, PYTHONPATH=os.pathsep.join(([os.environ["T7_PAQUETES"]] if os.environ.get("T7_PAQUETES") else []) + [str(PLANTA / "lib" / "paquetes"), str(PLANTA / "lib")]), PYTHONIOENCODING="utf-8")
env.pop("TEODORS_PLANTA", None)
for orden in ("galera.gui.tareas.mos_tabla", "galera.gui.tareas.mos_entrenar", "teodors.mos.tabla", "teodors.mos.entrenar"):
    r = subprocess.run([sys.executable, "-m", orden, "--help"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(PLANTA))
    print(orden, "--help:", r.returncode, "·", "con la salida" if "DATOS/mos/" in r.stdout else "SIN LA SALIDA")
    mal += r.returncode != 0 or "DATOS/mos/" not in r.stdout
    if r.returncode:
        print(r.stderr[-1000:])
    r = subprocess.run([sys.executable, "-m", orden, "--no-existe"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(PLANTA))
    mal += r.returncode != 2                         # sus mismos argumentos: ninguno

print("\n== Resumen ==")
print(f"{iguales} nombres iguales, {len(diferencias)} con diferencia explicada:")
for n_rel, nombre, motivo in diferencias:
    print(f"  {n_rel} · {nombre}: {motivo}")
print("FALLOS:", mal)
sys.exit(1 if mal else 0)
