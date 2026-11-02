# -*- coding: utf-8 -*-
"""Tanda 4: las métricas movidas a teOdors frente al original de git, función a función.

    python comparar_movidos_tanda4.py <raíz de la planta> <commit original> <carpeta core nueva>

Por cada nombre del módulo, el TEXTO de la función sin docstrings (caza comentarios y caracteres invisibles) y su AST. Cada diferencia
esperada se quita de forma explícita, con su motivo; lo demás tiene que dar igual byte a byte. Después, el diff entero de cada fichero
(para ver también lo que queda fuera de las funciones), las constantes de planta.json frente a las del original, los envoltorios y las
parejas que no se funden.
"""
import ast
import difflib
import json
import subprocess
import sys
from pathlib import Path

PLANTA, COMMIT, CORE = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
RARO = {0xa0: "NBSP", 0x202f: "NNBSP", 0x2009: "fino", 0x200b: "ancho cero", 0x2011: "guion duro", 0xad: "guion blando", 0x2212: "menos"}
sys.stdout.reconfigure(encoding="utf-8")


def viejo(rel):
    return subprocess.run(["git", "-C", str(PLANTA), "show", f"{COMMIT}:{rel}"], capture_output=True, check=True).stdout.decode("utf-8").replace("\r\n", "\n")


def nuevo(rel):
    return (CORE / "metricas" / rel).read_text(encoding="utf-8")


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


PARES = [("lib/galera/viento/validacion.py", "viento.py"), ("lib/galera/gui/tareas/f1_estacion.py", "calidad.py")]

DEF = "valor por defecto de planta: None, y se resuelve al llamar"
ANIOS_L = "    anios = config.REANALISIS_ANIOS if anios is None else anios\n"
VENTANA = "la ventana va alrededor de mediodia_h: 12,0 en esta planta, y los mismos bits (se comprueba abajo); sin el campo, el mediodía solar en su longitud"
MEDIODIA = ('    if mediodia_h is None:\n        mediodia_h = config.bloque("estaciones").get("mediodia_utc_h")\n'
            '    if mediodia_h is None:\n        mediodia_h = mediodia_solar(config.cargar_emplazamiento()["lon"])\n')

ESPERADOS = {
    ("viento.py", "era5_horario"): [("anios=config.REANALISIS_ANIOS):\n", "anios=None):\n" + ANIOS_L, DEF)],
    ("viento.py", "convencion"): [("def convencion(df):\n", "def convencion(df, mediodia_h=None):\n" + MEDIODIA, VENTANA),
                                  ("if 11.4 <= c < 12.0:", "if mediodia_h - 0.6 <= c < mediodia_h:", VENTANA),
                                  ("if 12.0 <= c < 12.6:", "if mediodia_h <= c < mediodia_h + 0.6:", VENTANA)],
    ("viento.py", "rosas_estaciones"): [("anios=config.REANALISIS_ANIOS, progreso=None):\n", "anios=None, progreso=None):\n" + ANIOS_L, DEF)],
    ("calidad.py", "figura"): [("from galera.gui.escalas import COLORES_VEL", "from teodors.comun.escalas import COLORES_VEL", "COLORES_VEL ya está en teodors.comun.escalas")],
    ("calidad.py", "main"): [('    ap.add_argument("--codigo", default=config.pide("estaciones", "objetivo"))\n    codigo = ap.parse_args().codigo\n',
                              '    ap.add_argument("--codigo", default=None)\n    codigo = ap.parse_args().codigo\n    if codigo is None:\n        codigo = config.pide("estaciones", "objetivo")\n',
                              "la estación objetivo, después de leer los argumentos: --help responde sin planta"),
                             ("CEROS_SOSPECHOSOS.get(codigo)", 'config.bloque("estaciones").get("ceros_sospechosos", {}).get(codigo)',
                              "al llamar y no al importar; opcional: una planta sin sensores dudosos no tiene por qué declararlo")],
}
QUITADOS = {("calidad.py", "CEROS_SOSPECHOSOS"): "se lee en main, de planta.json: nada puede leer la planta al importar; nadie lo usaba desde fuera"}
NUEVOS = {("viento.py", "mediodia_solar"): "el mediodía solar en una longitud, para las plantas sin mediodia_utc_h"}

mal = 0
diferencias = []
for v_rel, n_rel in PARES:
    print(f"\n== {n_rel} frente a {v_rel} ==")
    s0, s1 = viejo(v_rel), nuevo(n_rel)
    t0, t1 = tabla(s0), tabla(s1)
    for nombre in t0:
        if nombre not in t1:
            if (n_rel, nombre) in QUITADOS:
                print("quitado ", nombre, "·", QUITADOS[(n_rel, nombre)])
                diferencias.append((n_rel, nombre, "quitado: " + QUITADOS[(n_rel, nombre)]))
            else:
                print("FALTA   ", nombre)
                mal += 1
            continue
        ta, tb = texto_sin_doc(s0, t0[nombre]), texto_sin_doc(s1, t1[nombre])
        motivos = []
        for de, a_, motivo in ESPERADOS.get((n_rel, nombre), []):
            if de not in ta:
                print("ESPERADO SIN USO", nombre, repr(de))
                mal += 1
            ta = ta.replace(de, a_)
            motivos.append(motivo)
        if ta != tb:
            print("DISTINTO", nombre)
            print("--- esperado\n" + ta + "--- hay\n" + tb)
            mal += 1
        else:
            print(("igual   " if not motivos else "explicado"), nombre, ("· " + "; ".join(dict.fromkeys(motivos))) if motivos else "")
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

print("\n== Diff entero, también docstrings y lo que queda fuera de las funciones ==")
for v_rel, n_rel in PARES:
    print(f"--- {n_rel}")
    for linea in difflib.unified_diff(viejo(v_rel).splitlines(), nuevo(n_rel).splitlines(), lineterm="", n=0):
        if not linea.startswith(("---", "+++", "@@")):
            print(linea)

print("\n== Caracteres invisibles, original -> nuevo ==")
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
    mal += any("matplotlib" in x for x in fuera)

print("\n== Constantes del original frente a planta.json ==")
sys.path[:0] = [str(PLANTA / "lib" / "paquetes"), str(PLANTA / "lib")]
pj = json.loads((PLANTA / "lib/galera/gui/planta/planta.json").read_text(encoding="utf-8"))
pj0 = json.loads(viejo("lib/galera/gui/planta/planta.json"))
ok = pj["estaciones"]["ceros_sospechosos"] == {"C9": "2025-06-01"} and pj["estaciones"]["objetivo"] == "C9"
print("ceros sospechosos y objetivo", ok)
mal += not ok
m = pj["estaciones"]["mediodia_utc_h"]
ok = (m - 0.6, m, m + 0.6) == (11.4, 12.0, 12.6)
print("mediodia_utc_h = 12,0: los mismos tres límites, bit a bit (11,4 · 12,0 · 12,6)", ok)
mal += not ok
ok = set(pj0) == set(pj) and pj0["formato"] == pj["formato"]
print("mismos bloques y mismo formato", ok)
mal += not ok
for bloque in (k for k in pj0 if isinstance(pj0[k], dict)):
    a, b = dict(pj0[bloque]), dict(pj[bloque])
    if bloque == "estaciones":
        b.pop("mediodia_utc_h")
        a.pop("nota"), b.pop("nota")
    ok = a == b
    print(f"bloque {bloque}: igual" + (" (salvo mediodia_utc_h y su nota)" if bloque == "estaciones" else ""), ok)
    mal += not ok

print("\n== Envoltorios: cada nombre del original sigue, también los privados ==")
import importlib  # noqa: E402

for v_rel, n_rel in PARES:
    modulo = v_rel[4:-3].replace("/", ".")
    mod = importlib.import_module(modulo)
    faltan = [n for n in tabla(viejo(v_rel)) if not hasattr(mod, n)]
    print(modulo, len(tabla(viejo(v_rel))), "nombres; sin él:", faltan)
    mal += set(faltan) != {n for (f, n) in QUITADOS if f == n_rel}
    n_cod = sum(1 for n in ast.parse(Path(PLANTA, v_rel).read_text(encoding="utf-8")).body if isinstance(n, (ast.FunctionDef, ast.Assign)))
    print("   lo que define el envoltorio:", n_cod, "(solo __getattr__)")
    mal += n_cod != 1

print("\n== Parejas que no se funden: no se han tocado ==")
g = viejo("lib/galera/viento/validacion.py")
ok = texto_sin_doc(g, tabla(g)["a_horario"]) == texto_sin_doc(nuevo("viento.py"), tabla(nuevo("viento.py"))["a_horario"]) and 'g = g[g["n"] == 2]' in nuevo("viento.py")
print("a_horario, byte a byte y con n == 2:", ok)
mal += not ok
r = subprocess.run(["git", "-C", str(CORE.parent), "diff", "--stat", "6e84f60", "--", "core/preparacion/viento3d/estaciones.py", "core/comun/geo.py", "core/meteo/viento3d/sol.py"], capture_output=True, text=True).stdout.strip()
print("medias_horarias, elevacion_solar y seno_elevacion sin cambios frente a la tanda 3:", "sí" if not r else r)
mal += bool(r)

print("\n== Diferencias, para el informe ==")
for f, n, motivo in diferencias:
    print(f"{f} · {n}: {motivo}")
print("\nRESULTADO:", "todo igual, salvo lo que se dice" if not mal else f"{mal} distintos")
sys.exit(1 if mal else 0)
