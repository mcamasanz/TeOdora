# Lo que se reescribió a mano en la tanda 1 frente al original de git, función a función y sin docstrings: el texto se ve igual
# en pantalla aunque cambie un espacio duro. Sin docstrings ni comentarios, porque esos sí se retocaron a propósito.
#   python comparar_movidos.py <raiz con lib/galera en git> <commit original> <carpeta core nueva>
import ast
import subprocess
import sys
from pathlib import Path

RAIZ, COMMIT, CORE = sys.argv[1], sys.argv[2], Path(sys.argv[3])
# (fichero original, nombre, fichero nuevo, renombrar en el nuevo para comparar)
PARES = [("lib/galera/gui/formato.py", "num", "comun/formato.py"), ("lib/galera/gui/formato.py", "km", "comun/formato.py"),
         ("lib/galera/geo.py", "direccion", "comun/geo.py"), ("lib/galera/geo.py", "elevacion_solar", "comun/geo.py"),
         ("lib/galera/gui/escalas.py", "lut", "comun/escalas.py"), ("lib/galera/gui/escalas.py", "colores", "comun/escalas.py"),
         ("lib/galera/gui/escalas.py", "para_mapa", "comun/escalas.py"), ("lib/galera/gui/registro.py", "FormatoES", "comun/registro.py"),
         ("lib/galera/gui/registro.py", "get", "comun/registro.py")]
CONSTANTES = [("lib/galera/gui/escalas.py", "COLORES_VEL", "comun/escalas.py"), ("lib/galera/gui/registro.py", "NIVELES_ES", "comun/registro.py")]
RARO = {0xa0: "NBSP", 0x202f: "NNBSP", 0x2009: "fino", 0x200b: "ancho cero", 0x2011: "guion duro", 0xad: "guion blando", 0x2212: "menos"}


def sin_docstring(nodo):
    for n in ast.walk(nodo):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef, ast.Module)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) \
                and isinstance(n.body[0].value.value, str) and len(n.body) > 1:
            n.body = n.body[1:]
    return ast.dump(nodo)


def buscar(src, nombre):
    for n in ast.parse(src).body:
        if getattr(n, "name", None) == nombre:
            return n
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == nombre:
            return n
    raise KeyError(nombre)


def viejo(rel):
    return subprocess.run(["git", "-C", RAIZ, "show", f"{COMMIT}:{rel}"], capture_output=True, encoding="utf-8", check=True).stdout


mal = 0
for rel, nombre, nuevo in PARES + CONSTANTES:
    a = sin_docstring(buscar(viejo(rel), nombre))
    b = sin_docstring(buscar((CORE / nuevo).read_text(encoding="utf-8"), nombre))
    igual = a == b
    print(("igual   " if igual else "DISTINTO") + f" {nuevo}: {nombre}")
    mal += not igual

# a_mercator cambia de firma a propósito (recibe el epsg): se compara quitando esa diferencia
a = buscar(viejo("lib/galera/entradas/terreno.py"), "a_mercator")
b = buscar((CORE / "comun/mercator.py").read_text(encoding="utf-8"), "a_mercator")
ta = sin_docstring(a).replace("rgba", "bandas")
tb = sin_docstring(b)
ta = ta.replace("Attribute(value=Name(id='config', ctx=Load()), attr='EPSG_UTM', ctx=Load())", "Name(id='epsg', ctx=Load())")
args = "arguments(posonlyargs=[], args=[arg(arg='bandas'), arg(arg='transform'), arg(arg='max_px')]"
args2 = "arguments(posonlyargs=[], args=[arg(arg='bandas'), arg(arg='transform'), arg(arg='epsg'), arg(arg='max_px')]"
ta = ta.replace(args, args2)
print(("igual   " if ta == tb else "DISTINTO") + " comun/mercator.py: a_mercator (salvo el epsg)")
mal += ta != tb

print("\nCaracteres invisibles en los originales y en lo nuevo:")
for rel, nuevo in (("lib/galera/gui/formato.py", "comun/formato.py"), ("lib/galera/geo.py", "comun/geo.py"), ("lib/galera/gui/escalas.py", "comun/escalas.py"),
                   ("lib/galera/gui/registro.py", "comun/registro.py"), ("lib/galera/errores.py", "comun/errores.py"), ("lib/galera/gui/config.py", "planta/__init__.py")):
    cuenta = lambda t: {RARO[ord(c)]: t.count(c) for c in set(t) if ord(c) in RARO}
    print(f"  {rel}: {cuenta(viejo(rel))}   ->   {nuevo}: {cuenta((CORE / nuevo).read_text(encoding='utf-8'))}")
print("\nRESULTADO:", "todo igual" if not mal else f"{mal} distintos")
sys.exit(1 if mal else 0)
