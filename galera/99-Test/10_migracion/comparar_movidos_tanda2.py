# -*- coding: utf-8 -*-
"""Tanda 2: el viento local movido a teOdors frente al original de git, función a función.

    python comparar_movidos_tanda2.py <raiz con lib/galera en git> <commit original> <carpeta core nueva>

Por cada función: AST sin docstrings y, aparte, el TEXTO sin docstrings (cazan también comentarios y caracteres invisibles).
Cada diferencia esperada se quita de forma explícita, y se dice cuál. Lo demás tiene que dar igual.
"""
import ast
import subprocess
import sys
from pathlib import Path

PLANTA, COMMIT, CORE = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
RARO = {0xa0: "NBSP", 0x202f: "NNBSP", 0x2009: "fino", 0x200b: "ancho cero", 0x2011: "guion duro", 0xad: "guion blando", 0x2212: "menos"}
sys.stdout.reconfigure(encoding="utf-8")


def viejo(rel):
    return subprocess.run(["git", "-C", str(PLANTA), "show", f"{COMMIT}:{rel}"], capture_output=True, check=True).stdout.decode("utf-8").replace("\r\n", "\n")


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


mal = 0
print("== modelo.py frente a lib/galera/viento/local.py ==")
s0 = viejo("lib/galera/viento/local.py")
s1 = (CORE / "meteo" / "viento_local" / "modelo.py").read_text(encoding="utf-8")
t0, t1 = tabla(s0), tabla(s1)
print("nombres iguales:", list(t0) == list(t1), list(t1))
mal += list(t0) != list(t1)
for nombre in t0:
    a, b = t0[nombre], t1[nombre]
    ta = texto_sin_doc(s0, a)
    tb = texto_sin_doc(s1, b)
    nota = ""
    if nombre in ("lee_lidar", "obstaculos"):
        # diferencia esperada: el import perezoso de scipy, al principio de la función
        sb = sin_docstring(b)
        importes = [n for n in sb.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        nota = " · quitado el import perezoso: " + ", ".join(f"{n.module}: {[x.name for x in n.names]}" for n in importes)
        sb.body = [n for n in sb.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
        lineas = [l for l in tb.splitlines(keepends=True) if not l.strip().startswith("from scipy")]
        tb = "".join(l for i, l in enumerate(lineas) if not (l.strip() == "" and i < 3))
    igual_ast = ast.dump(sin_docstring(a)) == ast.dump(sin_docstring(b))
    igual_txt = ta == tb
    print(("igual   " if igual_ast else "DISTINTO"), ("texto igual   " if igual_txt else "TEXTO DISTINTO"), nombre + nota)
    mal += (not igual_ast) + (not igual_txt)


print("\n== biblioteca.py frente a lib/galera/gui/tareas/viento_local_biblioteca.py ==")
s0 = viejo("lib/galera/gui/tareas/viento_local_biblioteca.py")
s1 = (CORE / "meteo" / "viento_local" / "biblioteca.py").read_text(encoding="utf-8")
t0, t1 = tabla(s0), tabla(s1)


class Renombra(ast.NodeTransformer):
    """Lo que se esperaba cambiar en `principal`: constantes del módulo -> parámetros."""
    NOMBRES = {"DX": "dx", "DZ": "dz", "CENTRO": "centro", "SEMILADO": "semilado", "MARGEN": "margen", "ALTO": "alto", "SALIDA": "salida",
               "RADIO": "radio", "RADIO_BORDE": "radio_borde", "local": "modelo"}

    def visit_Name(self, n):
        if n.id == "PLANTA" or n.id == "DACAME":
            return ast.Subscript(value=ast.Name(id="puntos", ctx=ast.Load()), slice=ast.Constant(value=0 if n.id == "PLANTA" else 1), ctx=ast.Load())
        return ast.Name(id=self.NOMBRES.get(n.id, n.id), ctx=n.ctx)


a = Renombra().visit(sin_docstring(t0["principal"]))
b = sin_docstring(t1["principal"])
# diferencia esperada: firma y dos líneas al principio
primeras = [ast.unparse(n) for n in b.body[:2]]
print("añadido al principio de principal:", primeras)
print("firma nueva:", ast.unparse(b.args))
b.body = b.body[2:]
a.args = b.args
igual = ast.dump(a) == ast.dump(b)
print("igual   " if igual else "DISTINTO", "principal, con las constantes como parámetros")
mal += not igual
if not igual:
    print(ast.unparse(a)); print(ast.unparse(b))
for nombre in ("ESCALA", "SOLIDO"):
    igual = ast.dump(t0[nombre]) == ast.dump(t1[nombre])
    print("igual   " if igual else "DISTINTO", nombre)
    mal += not igual

# zona(): las mismas cuentas que CENTRO y SEMILADO, con la constantes del original
g = {}
exec("\n".join(l for l in s0.splitlines() if l.split(" = ")[0].split(",")[0].strip() in ("PLANTA", "DACAME", "RADIO", "RADIO_BORDE", "MARGEN", "CENTRO", "SEMILADO", "DX", "ALTO", "ESCALA", "SOLIDO")), g)
print("mismas cuentas en el original:", g["CENTRO"], g["SEMILADO"])
print("\nConstantes del original:", {k: g[k] for k in ("PLANTA", "DACAME", "RADIO", "RADIO_BORDE", "MARGEN", "DX", "DZ", "ALTO") if k in g})
sys.path[:0] = [str(PLANTA / "lib" / "paquetes")]
from teodors.meteo.viento_local import biblioteca as bib  # noqa: E402
import json  # noqa: E402

bl = json.loads((PLANTA / "lib" / "galera" / "gui" / "planta" / "planta.json").read_text(encoding="utf-8"))["viento_local"]
p = bib.parametros(bl, PLANTA / "lib" / "galera" / "gui" / "planta")
print("Bloque de planta.json ->", {k: v for k, v in p.items()})
comprueba = {"puntos": p["puntos"] == [tuple(g["PLANTA"]), (286228.0, 4507320.0)], "radio": p["radio"] == g["RADIO"], "radio_borde": p["radio_borde"] == g["RADIO_BORDE"],
             "margen": p["margen"] == g["MARGEN"], "dx": p["dx"] == 2.5, "dz": p["dz"] == 1.25, "alto": p["alto"] == g["ALTO"],
             "zona": bib.zona(p["puntos"], p["radio_borde"], p["margen"]) == (g["CENTRO"], g["SEMILADO"])}
print(comprueba)
mal += not all(comprueba.values())

print("\n== Caracteres invisibles, original -> nuevo ==")
cuenta = lambda t: {RARO[ord(c)]: t.count(c) for c in set(t) if ord(c) in RARO}
print("local.py", cuenta(viejo("lib/galera/viento/local.py")), "->", cuenta((CORE / "meteo/viento_local/modelo.py").read_text(encoding="utf-8")))
print("biblioteca", cuenta(viejo("lib/galera/gui/tareas/viento_local_biblioteca.py")), "->", cuenta((CORE / "meteo/viento_local/biblioteca.py").read_text(encoding="utf-8")))
print("\nRESULTADO:", "todo igual, salvo lo que se dice" if not mal else f"{mal} distintos")
sys.exit(1 if mal else 0)
