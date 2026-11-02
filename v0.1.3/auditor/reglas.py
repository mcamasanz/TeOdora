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

R4-R6 comparan con una referencia de git (por defecto la rama `main`): los cambios ya confirmados y
los que aún están en el árbol de trabajo.
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
def _git(*args):
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def cambios(base):
    """{ruta: estado} de lo que cambia respecto a `base` (A añadido, M modificado, D borrado, R…),
    contando también lo no confirmado y los ficheros nuevos sin seguimiento."""
    out = {}
    for linea in _git("diff", "--name-status", "-M", base).splitlines():
        p = linea.split("\t")
        if p[0].startswith("R"):
            out[p[1]] = "D"
            out[p[2]] = "A"
        else:
            out[p[1]] = p[0][0]
    for linea in _git("ls-files", "--others", "--exclude-standard").splitlines():
        out.setdefault(linea, "A")
    return out


def _en_base(base, ruta):
    try:
        return _git("show", "%s:%s" % (base, ruta))
    except RuntimeError:
        return ""


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
        env = dict(os.environ, AUDITOR_TIEMPOS=str(tiempos), PYTHONIOENCODING="utf-8")
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
    codigo = [r for r, e in cam.items() if e in "AM" and r.startswith("core/") and r.endswith(".py")]
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


def auditar(base="main", solo_pruebas=False, limite=LIMITE_PRUEBA_S, total=LIMITE_TOTAL_S):
    res = [r1_sintaxis()]
    res += list(r2_r3_pruebas(limite, total))
    if not solo_pruebas:
        try:
            cam = cambios(base)
        except RuntimeError as e:
            res.append(Resultado("R4-R6 cambios", False, ["no se pudo comparar con «%s»: %s" % (base, e)]))
        else:
            res += [r4_pruebas_nuevas(cam), r5_referencias(cam, base), r6_sin_perder_pruebas(cam, base)]
    return res
