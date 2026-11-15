# -*- coding: utf-8 -*-
"""Lectura del fichero de control CALPUFF.INP (sintaxis publicada) a una configuración.

Sintaxis y significado de las variables: CALPUFF Version 6 User Instructions (2011), sec. 9.1 y
tabla 9-3; guía v5 (2000), sec. 4.1. Las entradas «!VAR = valor!» se leen en orden; los subgrupos
de datos (fuentes, vértices, perfiles, receptores) se asignan por su posición tras las variables que
abren cada grupo (NPT1 -> 13, NAR1 -> 14, NLN2/NLINES -> 15, NVL1 -> 16, NREC -> 17).
Datos de edificio de las fuentes puntuales (subgrupo 13c, tabla 9-3 de la guía V6): HEIGHT, WIDTH,
LENGTH, XBADJ e YBADJ con 36 valores cada uno, para los vectores de flujo de 10° a 360°.

Especies (grupos 3a, 5, 7, 8 y 10; [UG] sec. 4.1): las entradas cuya variable es el nombre de una
especie se asignan al grupo por la zona en la que aparecen (la abren variables propias de cada
grupo: CSPEC el 3, ICON el 5, NHILL el 6 —tras él vienen los grupos 7 y 8, que se distinguen por el
número de valores: 5 de los gases y 2 de las partículas—, RCUTR el 9 —tras él, el 10—, MOZ el 11).
"""
import re
from dataclasses import dataclass, field

import numpy as np

_ENTRADA = re.compile(r"!([^!]*)!")


class NoImplementado(Exception):
    pass


def _valores(v):
    out = []
    for x in v.replace(" ", "").split(","):
        if not x:
            continue
        if "*" in x:
            k, val = x.split("*", 1)
            out += [val] * int(k)
        else:
            out.append(x)
    return out


def _real(x):
    return float(x.replace("D", "E").replace("d", "e"))


EDIF = ("HEIGHT", "WIDTH", "LENGTH", "XBADJ", "YBADJ")


def _36(val):
    """36 valores por dirección del subgrupo 13c (los que falten, 0; los que sobren se ignoran)."""
    out = np.zeros(36)
    if val is not None:
        x = [_real(t) for t in _valores(val)][:36]
        out[:len(x)] = x
    return out


@dataclass
class Especie:
    nombre: str
    modelada: int = 1
    emitida: int = 1
    seca: int = 0             # 0 no, 1 gas (resistencias), 2 partícula, 3 del usuario (VD.DAT)
    grupo: int = 0            # grupo de salida CGRUP (0 ninguno)
    salida: tuple = (1, 1, 0, 1, 0, 1, 0)   # grupo 5: conc. impr./disco, seca, húmeda, flujo másico
    gas: tuple = None         # grupo 7: difusividad (cm2/s), α*, reactividad, r. mesófilo (s/cm), Henry
    part: tuple = None        # grupo 8: diámetro medio másico (µm), desviación geométrica (µm)
    lavado: tuple = (0.0, 0.0)  # grupo 10: coeficientes de lavado, precipitación líquida y helada (1/s)


@dataclass
class Fuente:
    nombre: str
    tipo: int                 # 1 puntual, 3 área, 2 volumen (código ISTYPE del CONC.DAT: 1, 3, 7)
    x: float                  # km (área: centroide)
    y: float
    h: float                  # altura de emisión (m)
    zbase: float              # cota de la base (m)
    q: float                  # g/s (área: g/m2/s) de la primera especie emitida
    sy0: float = 0.0          # σ iniciales (m)
    sz0: float = 0.0
    d: float = 0.0
    w: float = 0.0
    ts: float = 0.0
    vx: list = field(default_factory=list)    # vértices (km), solo área
    vy: list = field(default_factory=list)
    ivary: int = 0
    factores: list = field(default_factory=list)
    bdw: float = 0.0          # indicador de efecto edificio de la columna «Bldg. Dwash» (13b)
    edif: dict = None         # dimensiones por sector del vector de flujo (13c): 5 × 36 valores
    qs: list = field(default_factory=list)    # emisión de cada especie emitida (en el orden de 3a)
    variacion: dict = field(default_factory=dict)  # especie -> (IVARY, factores) (13d, 14d, 16c)
    fmfac: float = 1.0        # factor de cantidad de movimiento (13b)


@dataclass
class Config:
    v: dict                   # todas las variables escalares (última aparición)
    fuentes: list
    receptores: np.ndarray    # (n, 4): x km, y km, cota m, altura m
    especies: list = field(default_factory=list)

    def i(self, n, d=None):
        return int(float(self.v[n][0])) if n in self.v else d

    def r(self, n, d=None):
        return _real(self.v[n][0]) if n in self.v else d

    def s(self, n, d=None):
        return self.v[n][0] if n in self.v else d

    def lista(self, n):
        return [_real(x) for x in self.v[n]] if n in self.v else None

    def emitidas(self):
        """Especies emitidas (las que llevan emisión en los datos de las fuentes), en orden."""
        return [e for e in self.especies if e.emitida]


# variables que abren la zona de cada grupo (para asignar las entradas con nombre de especie)
_ZONA = {"CSPEC": 3, "PMAP": 4, "ICON": 5, "NHILL": 6, "RCUTR": 9, "MOZ": 11, "SYTDEP": 12}


def _variacion(sub, nombres):
    """IVARY y factores por especie de un subgrupo 13d/14d/16c."""
    iv = int(float(_valores(sub["IVARY"])[0]))
    out = {}
    for k, val in sub.items():
        if k in nombres:
            out[k] = (iv, [_real(t) for t in _valores(val)])
    if not out:
        # sin nombre de especie reconocido: los factores de la primera entrada (compatibilidad)
        esp = [kk for kk in sub if kk not in ("SRCNAM", "IVARY", "X", "XVERT", "YVERT", "_sub")]
        if esp:
            out[None] = (iv, [_real(t) for t in _valores(sub[esp[0]])])
    return out


def leer(texto):
    ent = []
    for m in _ENTRADA.finditer(texto):
        c = m.group(1).strip()
        if not c or c.upper() == "END" or "=" not in c:
            continue
        k, val = c.split("=", 1)
        ent.append((k.strip().upper(), val.strip()))
    v = {}
    grupo = 0
    zona = 0
    puntos, areas, vols, recs = [], [], [], []
    actual = None
    nombres = []                       # especies (CSPEC) en orden
    por_esp = {}                       # nombre -> {grupo: valores}
    for k, val in ent:
        if k in _ZONA:
            zona = _ZONA[k]
        if k == "NPT1":
            grupo = 13
        elif k == "NAR1":
            grupo = 14
        elif k in ("NLN2", "NLINES"):
            grupo = 15
        elif k == "NVL1":
            grupo = 16
        elif k == "NREC":
            grupo = 17
        if k == "CSPEC" and grupo == 0:
            nombres.append(val.strip().upper())
            por_esp.setdefault(nombres[-1], {})
            v["CSPEC"] = [val.strip()]
            continue
        if grupo == 0 and k in por_esp:
            vals = _valores(val)
            if zona == 3:
                por_esp[k][3] = vals
            elif zona == 5:
                por_esp[k][5] = vals
            elif zona == 6:
                por_esp[k][7 if len(vals) >= 5 else 8] = vals
            elif zona == 9:
                por_esp[k][10] = vals
            continue
        if grupo == 13 and k == "SRCNAM":
            actual = {"SRCNAM": val}
            puntos.append(actual)
            continue
        if grupo == 13 and actual is not None and (k in ("X", "SIGYZI", "FMFAC", "ZPLTFM", "IVARY") + EDIF
                                                   or k in por_esp):
            actual[k] = val
            continue
        if grupo == 14 and k == "SRCNAM":
            actual = {"SRCNAM": val}
            # el tipo de subgrupo se decide por la variable que sigue
            actual["_sub"] = None
            areas.append(actual)
            continue
        if grupo == 14 and actual is not None and k not in ("NAR1", "IARU", "NSAR1", "NAR2"):
            actual[k] = val
            continue
        if grupo == 16 and k == "SRCNAM":
            actual = {"SRCNAM": val}
            vols.append(actual)
            continue
        if grupo == 16 and actual is not None and k not in ("NVL1", "IVLU", "NSVL1", "NVL2"):
            actual[k] = val
            continue
        if grupo == 17 and k == "X":
            recs.append([_real(x) for x in _valores(val)])
            continue
        v.setdefault(k, [])
        v[k] = _valores(val) if k not in v or True else v[k]
    # especies
    especies = []
    for n in nombres:
        d = por_esp[n]
        e = Especie(n)
        if 3 in d:
            f = [int(float(x)) for x in d[3]] + [0] * 4
            e.modelada, e.emitida, e.seca, e.grupo = f[:4]
        if 5 in d:
            e.salida = tuple(int(float(x)) for x in d[5])
        if 7 in d:
            e.gas = tuple(_real(x) for x in d[7][:5])
        if 8 in d:
            e.part = tuple(_real(x) for x in d[8][:2])
        if 10 in d:
            e.lavado = tuple(_real(x) for x in d[10][:2])
        if e.modelada:
            especies.append(e)
        if e.grupo:
            raise NoImplementado("grupos de especies de salida (CGRUP)")
    if not especies:
        especies = [Especie(v["CSPEC"][0].strip().upper() if "CSPEC" in v else "SPEC")]
    nom_esp = set(nombres)
    nemi = sum(1 for e in especies if e.emitida)
    # fuentes de área: reunir 14b (X), 14c (XVERT/YVERT) y 14d (IVARY) por nombre
    fuentes = []
    porn = {}
    for a in areas:
        n = a["SRCNAM"]
        if "IVARY" in a:
            porn.setdefault(n, {}).setdefault("_var", {}).update(_variacion(a, nom_esp))
            continue
        porn.setdefault(n, {}).update({kk: vv for kk, vv in a.items() if kk not in ("SRCNAM", "_sub")})
    # subgrupos de las fuentes puntuales: 13b (X), 13c (dimensiones del edificio) y 13d (IVARY)
    sub13c = [p for p in puntos if "X" not in p and any(kk in p for kk in EDIF)]
    sub13d = [p for p in puntos if "X" not in p and "IVARY" in p]
    puntos = [p for p in puntos if "X" in p]
    var13 = {}
    for s in sub13d:
        var13.setdefault(s["SRCNAM"], {}).update(_variacion(s, nom_esp))
    con_bdw = 0
    for p in puntos:
        x = [_real(t) for t in _valores(p["X"])]
        qs = x[8:8 + nemi] if len(x) > 8 else [0.0]
        f = Fuente(p["SRCNAM"], 1, x[0], x[1], x[2], x[3], qs[0] if qs else 0.0, d=x[4],
                   w=x[5], ts=x[6], qs=qs)
        f.bdw = x[7]
        if f.bdw != 0.0:
            # el original lee un subgrupo 13c por cada fuente con efecto edificio, en orden (el
            # nombre no se comprueba); cada uno necesita al menos HEIGHT y WIDTH (caja negra)
            if con_bdw >= len(sub13c):
                raise ValueError("faltan datos de edificio (subgrupo 13c) para la fuente %s" % f.nombre)
            s = sub13c[con_bdw]
            if "HEIGHT" not in s or "WIDTH" not in s:
                raise ValueError("subgrupo 13c de la fuente %s sin HEIGHT o WIDTH" % f.nombre)
            f.edif = {kk: _36(s.get(kk)) for kk in EDIF}
            con_bdw += 1
            if "ZPLTFM" in p and _real(_valores(p["ZPLTFM"])[0]) > 0.0:
                raise NoImplementado("efecto edificio sobre plataformas elevadas (ZPLTFM > 0)")
        if "SIGYZI" in p:
            f.sy0, f.sz0 = [_real(t) for t in _valores(p["SIGYZI"])][:2]
        f.variacion = var13.get(f.nombre, {})
        if "FMFAC" in p:
            f.fmfac = _real(_valores(p["FMFAC"])[0])
        fuentes.append(f)
    if len(sub13c) != con_bdw:
        raise ValueError("datos de edificio (subgrupo 13c) para %d fuentes; se esperaban %d"
                         % (len(sub13c), con_bdw))
    for n, a in porn.items():
        if "X" not in a:
            continue
        x = [_real(t) for t in _valores(a["X"])]
        vx = [_real(t) for t in _valores(a["XVERT"])]
        vy = [_real(t) for t in _valores(a["YVERT"])]
        qs = x[3:3 + nemi]
        f = Fuente(n, 3, float(np.mean(vx)), float(np.mean(vy)), x[0], x[1], qs[0], sz0=x[2], vx=vx,
                   vy=vy, qs=qs)
        f.variacion = a.get("_var", {})
        if f.variacion:
            iv, fac = next(iter(f.variacion.values()))
            f.ivary, f.factores = iv, fac
        fuentes.append(f)
    # fuentes de volumen (16b: X, Y, altura efectiva, cota, σy0, σz0, emisiones; 16c: IVARY)
    porv = {}
    for s in vols:
        n = s["SRCNAM"]
        if "IVARY" in s:
            porv.setdefault(n, {}).setdefault("_var", {}).update(_variacion(s, nom_esp))
        else:
            porv.setdefault(n, {}).update(s)
    for n, s in porv.items():
        if "X" not in s:
            continue
        x = [_real(t) for t in _valores(s["X"])]
        qs = x[6:6 + nemi]
        f = Fuente(n, 2, x[0], x[1], x[2], x[3], qs[0], sy0=x[4], sz0=x[5], qs=qs)
        f.variacion = s.get("_var", {})
        fuentes.append(f)
    return Config(v, fuentes, np.array(recs, float).reshape(-1, 4) if recs else np.zeros((0, 4)),
                  especies)
