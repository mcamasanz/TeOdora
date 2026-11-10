# -*- coding: utf-8 -*-
"""Reglas para entrar en la rama principal.

| Regla | Qué exige |
|---|---|
| R1 sintaxis | todo el código compila |
| R2 pruebas | pasan todas las pruebas (unitarias y de regresión) |
| R3 rapidez | cada prueba dura como mucho LIMITE_PRUEBA_S y el conjunto LIMITE_TOTAL_S, medidas con la caché de numba caliente (las marcadas `compilacion` quedan fuera) |
| R4 pruebas nuevas | cada motor (o parte del paquete) con código añadido o modificado trae pruebas nuevas o modificadas que lo nombran, o un caso nuevo de regresión |
| R5 referencias | una referencia o un caso.json modificado solo se acepta si CAMBIOS_REFERENCIA.md tiene una entrada nueva que nombra el caso |
| R6 sin perder pruebas | no se borran ficheros de pruebas ni casos, ni bajan las funciones de prueba de un fichero |
| R7 versiones | cada carpeta se llama como su versión, una versión publicada no se toca y cada planta usa una versión que existe |

R4-R6 comparan esta carpeta con la de la versión anterior, que está a su lado (v0.1.4 frente a v0.1.3): lo que git
sigue o seguiría, también lo que aún no está confirmado. Si no hay versión anterior, no hay con qué comparar.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

AUDITOR = Path(__file__).resolve().parent
RAIZ = AUDITOR.parent
LIMITE_PRUEBA_S = 20.0
LIMITE_TOTAL_S = 300.0
CAMBIOS = "auditor/CAMBIOS_REFERENCIA.md"


@dataclass
class Resultado:
    regla: str
    ok: bool
    detalle: list = field(default_factory=list)


# ------------------------------------------------------------------------------ git
def _git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd or RAIZ, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def _numero(carpeta):
    """(0, 1, 3) si la carpeta se llama como una versión (v0.1.3); None si no."""
    m = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", Path(carpeta).name)
    return tuple(int(x) for x in m.groups()) if m else None


def version_anterior():
    """La carpeta de la versión anterior a esta, a su lado; None si no hay ninguna."""
    yo = _numero(RAIZ)
    if yo is None:
        return None
    otras = [(_numero(c), c) for c in RAIZ.parent.iterdir() if c.is_dir() and _numero(c) and _numero(c) < yo]
    return max(otras, key=lambda o: o[0])[1] if otras else None


def _ficheros(carpeta):
    """Lo que git sigue o seguiría en esa carpeta, sin lo ignorado: {ruta relativa: fichero}."""
    nombres = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard", cwd=carpeta).split("\0")
    return {n: Path(carpeta) / n for n in nombres if n and (Path(carpeta) / n).is_file()}


def _bytes(fichero):
    return fichero.read_bytes().replace(b"\r\n", b"\n")      # el final de línea depende de cómo los saque git


def cambios(base):
    """{ruta: estado} de lo que cambia respecto a la carpeta `base` (A añadido, M modificado, D borrado); {} si no hay con qué comparar."""
    if base is None:
        return {}
    ahora, antes = _ficheros(RAIZ), _ficheros(base)
    out = {r: "A" for r in ahora if r not in antes}
    out.update({r: "D" for r in antes if r not in ahora})
    out.update({r: "M" for r in ahora if r in antes and _bytes(ahora[r]) != _bytes(antes[r])})
    return out


def _en_base(base, ruta):
    f = Path(base) / ruta
    return f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""


# ------------------------------------------------------------------------------ reglas
def r1_sintaxis():
    errores = []
    for f in sorted(list((RAIZ / "core").rglob("*.py")) + list(AUDITOR.rglob("*.py"))):
        if "_nucleo_gen" in f.name:
            continue
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except (SyntaxError, UnicodeDecodeError) as e:
            errores.append("%s: %s" % (f.relative_to(RAIZ).as_posix(), e))
    return Resultado("R1 sintaxis", not errores, errores)


def _pytest(argumentos):
    """Corre pytest en la raíz del repositorio: (código de salida, salida, {prueba: tiempo y marcas})."""
    with tempfile.TemporaryDirectory() as d:
        tiempos = Path(d) / "tiempos.json"
        # el cargador de ESTA carpeta, delante: con varias versiones, las pruebas no pueden coger otra
        camino = os.pathsep.join(p for p in (str(RAIZ / "cargador"), os.environ.get("PYTHONPATH")) if p)
        env = dict(os.environ, AUDITOR_TIEMPOS=str(tiempos), PYTHONIOENCODING="utf-8", PYTHONPATH=camino)
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *argumentos],
                           cwd=RAIZ, env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        datos = json.loads(tiempos.read_text(encoding="utf-8")) if tiempos.exists() else {}
    return r.returncode, r.stdout, datos


def r2_r3_pruebas(limite=LIMITE_PRUEBA_S, total=LIMITE_TOTAL_S, extra=()):
    """Corre pytest y aplica las reglas de pruebas y de rapidez.

    La rapidez se mide en régimen: la primera vez que se ejecuta un motor tras cambiar su código,
    numba compila sus núcleos (decenas de segundos). Las pruebas que pasan del límite se repiten
    una vez, ya con la caché caliente, y cuenta esa segunda medida."""
    codigo, salida, datos = _pytest([str(AUDITOR / "pruebas"), *extra])
    fallos = [n for n, v in datos.items() if v["resultado"] != "passed"]
    r2 = Resultado("R2 pruebas", codigo == 0 and not fallos,
                   ["%d pruebas, %d fallan" % (len(datos), len(fallos))] + fallos +
                   ([] if codigo == 0 else [l for l in salida.splitlines()[-25:] if l.strip()]))
    repetir = [n for n, v in datos.items() if v["segundos"] > limite and v["resultado"] == "passed"
               and "compilacion" not in v["marcas"]]
    if repetir:
        _c, _s, segunda = _pytest(repetir)
        for n in repetir:
            if n in segunda:
                datos[n]["segundos"] = segunda[n]["segundos"]
    lentas = ["%s: %.1f s (límite %.0f s)" % (n, v["segundos"], limite) for n, v in datos.items()
              if v["segundos"] > limite and "compilacion" not in v["marcas"]]
    suma = sum(v["segundos"] for v in datos.values() if "compilacion" not in v["marcas"])
    det = ["%.1f s en total (límite %.0f s); la más lenta: %s" % (
        suma, total, max(((v["segundos"], n) for n, v in datos.items()), default=(0, "—"))[1])] + lentas
    if suma > total:
        det.append("el conjunto supera el límite total")
    return r2, Resultado("R3 rapidez", not lentas and suma <= total, det)


def _parte(ruta):
    """Motor (o parte del paquete) al que pertenece un fichero de código."""
    p = Path(ruta).parts
    if len(p) >= 4 and p[0] == "core" and p[1] in ("terreno", "meteo", "dispersion"):
        return p[2]
    return "paquete"


def r4_pruebas_nuevas(cam):
    # core/__init__.py lleva el número de versión, que cambia en todas: si contara, y con él la prueba que lo mira, cualquier código pasaría
    codigo = [r for r, e in cam.items() if e in "AM" and r.startswith("core/") and r.endswith(".py") and r != "core/__init__.py"]
    pruebas = [r for r, e in cam.items() if e in "AM" and r.startswith("auditor/pruebas/") and r.endswith(".py")]
    casos_nuevos = {Path(r).parts[2] for r, e in cam.items() if e == "A" and r.startswith("auditor/casos/")
                    and r.endswith("caso.json")}
    texto = {r: (RAIZ / r).read_text(encoding="utf-8", errors="replace") for r in pruebas if (RAIZ / r).exists()}
    falta = []
    for parte in sorted({_parte(r) for r in codigo}):
        modulos = [Path(r).stem for r in codigo if _parte(r) == parte]
        nombrada = any(parte in t or any(m in t for m in modulos) for t in texto.values())
        if not (nombrada or parte in casos_nuevos):
            falta.append("%s: código nuevo o modificado (%s) sin pruebas nuevas que lo nombren ni caso nuevo"
                         % (parte, ", ".join(sorted(set(modulos)))))
    det = ["código cambiado en: %s" % (", ".join(sorted({_parte(r) for r in codigo})) or "nada")] + falta
    return Resultado("R4 pruebas nuevas", not falta, det)


def r5_referencias(cam, base):
    tocados = sorted({"/".join(Path(r).parts[2:4]) for r, e in cam.items() if r.startswith("auditor/casos/")
                      and e in "MD" and ("/referencia/" in r or r.endswith("caso.json"))})
    if not tocados:
        return Resultado("R5 referencias", True, ["ninguna referencia modificada"])
    nuevo = (RAIZ / CAMBIOS).read_text(encoding="utf-8") if (RAIZ / CAMBIOS).exists() else ""
    anadido = nuevo.replace(_en_base(base, CAMBIOS), "", 1) if CAMBIOS in cam else ""
    sin = [c for c in tocados if c not in anadido]
    return Resultado("R5 referencias", not sin,
                     ["referencias modificadas: %s" % ", ".join(tocados)] +
                     ["%s: falta su justificación en %s" % (c, CAMBIOS) for c in sin])


def r6_sin_perder_pruebas(cam, base):
    det = []
    for r, e in cam.items():
        if e == "D" and (r.startswith("auditor/pruebas/") or r.startswith("auditor/casos/")):
            det.append("borrado: %s" % r)
        elif e == "M" and r.startswith("auditor/pruebas/") and r.endswith(".py"):
            antes = len(re.findall(r"(?m)^\s*def test_", _en_base(base, r)))
            ahora = len(re.findall(r"(?m)^\s*def test_", (RAIZ / r).read_text(encoding="utf-8")))
            if ahora < antes:
                det.append("%s: %d funciones de prueba en lugar de %d" % (r, ahora, antes))
    return Resultado("R6 sin perder pruebas", not det, det or ["ninguna prueba ni caso eliminado"])


def r7_versiones():
    """Cada carpeta se llama como su versión, una publicada (con su etiqueta) no se toca y cada planta usa una versión que existe."""
    det = []
    version = re.search(r'__version__ = "([^"]+)"', (RAIZ / "core" / "__init__.py").read_text(encoding="utf-8")).group(1)
    proyecto = re.search(r'(?m)^version = "([^"]+)"', (RAIZ / "pyproject.toml").read_text(encoding="utf-8")).group(1)
    if version != proyecto:
        det.append("core dice %s y pyproject.toml dice %s" % (version, proyecto))
    if _numero(RAIZ) is None:
        return Resultado("R7 versiones", not det, det or ["no está en una carpeta de versión: nada más que mirar"])
    if RAIZ.name != "v" + version:
        det.append("la carpeta %s contiene la versión %s" % (RAIZ.name, version))
    padre = RAIZ.parent
    for c in sorted((p for p in padre.iterdir() if p.is_dir() and _numero(p)), key=_numero):
        etiqueta = "refs/tags/" + c.name
        if not _git("tag", "--list", c.name, cwd=padre).strip() or not _git("ls-tree", "-d", etiqueta, c.name, cwd=padre).strip():
            continue                                 # sin publicar, o publicada antes de que hubiera carpetas
        tocados = _git("diff", "--name-only", etiqueta, "--", c.name + "/", cwd=padre).split("\n")
        tocados += _git("ls-files", "--others", "--exclude-standard", "--", c.name + "/", cwd=padre).split("\n")
        tocados = [t for t in tocados if t]
        if tocados:
            det.append("%s está publicada y ha cambiado: %s" % (c.name, ", ".join(tocados[:5])))
    plantas = sorted(p for p in padre.iterdir() if p.is_dir() and (p / "VERSION").is_file())
    for c in plantas:
        pide = (c / "VERSION").read_text(encoding="utf-8").strip()
        if not (padre / pide / "cargador").is_dir():
            det.append("la planta %s usa %s, que no existe" % (c.name, pide))
        if not (c / "entrada" / "planta.json").is_file():
            det.append("la planta %s no tiene entrada/planta.json" % c.name)
    return Resultado("R7 versiones", not det, det or ["%s · plantas: %s" % (RAIZ.name, ", ".join(c.name for c in plantas) or "ninguna")])


def auditar(base=None, solo_pruebas=False, limite=LIMITE_PRUEBA_S, total=LIMITE_TOTAL_S):
    """`base`: la carpeta con la que comparar; por defecto, la de la versión anterior."""
    res = [r1_sintaxis()]
    res += list(r2_r3_pruebas(limite, total))
    if not solo_pruebas:
        base = Path(base) if base else version_anterior()
        try:
            cam = cambios(base)
        except RuntimeError as e:
            res.append(Resultado("R4-R6 cambios", False, ["no se pudo comparar con «%s»: %s" % (base, e)]))
        else:
            res.append(Resultado("R4-R6 base", True, ["frente a %s" % base.name if base else "no hay versión anterior con la que comparar"]))
            res += [r4_pruebas_nuevas(cam), r5_referencias(cam, base), r6_sin_perder_pruebas(cam, base), r7_versiones()]
    return res
