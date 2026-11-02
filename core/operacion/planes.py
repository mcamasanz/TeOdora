# -*- coding: utf-8 -*-
"""Planes de operación: CÓMO emiten los focos, sin tocar los focos. Es lo que el operario puede crear, guardar y cargar; los focos no (`operacion.focos`).

Cada foco lleva su propio plan DIARIO, SEMANAL o MENSUAL: un perfil de 24 h por día, sin repetir los iguales. Un fichero JSON por plan en DATOS/escenarios/
(config.DIR_ESCENARIOS), mismo criterio que los focos.

    {"formato": 2, "nombre": "Volteos por la tarde", "creado": "aaaa-mm-ddThh:mm",
     "modificado": "...", "notas": "...",
     "mes": "aaaa-mm",     # calendario de los planes mensuales; null si no hay ninguno
     "focos": {"F08": {"plan": "semanal",
                       "perfiles": [[24 factores, hora oficial], [...]],
                       "dias": [0, 1, 0, 1, 0, 1, 1]}, ...}}

«dias» dice qué perfil toca cada día: 1 valor (diario), 7 (semanal, de lunes a domingo) o 31
(mensual, por día del mes). La emisión del foco es
    emisión de referencia × perfiles[dias[día]][hora oficial].
Un foco que no figura emite como en su ficha, así un plan guardado sigue valiendo si se añade un
foco. La «Base» no es un fichero: es la de las fichas.

Para calcular no hace falta el motor: `factores` da la emisión hora a hora y las respuestas guardadas
se pesan con ella (`operacion.simulacion`). Los planes van en hora oficial, la de `proyeccion.zona_horaria` de
planta.json (cambio de hora incluido), y el cálculo en UTC.
"""
import calendar
import datetime as dt
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from teodors import planta as config
from teodors.operacion import focos as F

FORMATO = 2
BASE = "Base"
PLANES = {"diario": 1, "semanal": 7, "mensual": 31}      # plan → número de días que define
NOMBRES_PLAN = {"diario": "Diario", "semanal": "Semanal", "mensual": "Mensual"}
DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def zona():
    """Zona horaria de la planta: la de su hora oficial."""
    return config.pide("proyeccion", "zona_horaria")


def _ahora():
    return dt.datetime.now().isoformat(timespec="minutes")


def _perfil_ficha(foco):
    return {"plan": "diario", "perfiles": [[float(x) for x in F.perfil(foco)]], "dias": [0]}


def base(catalogo):
    """El plan de las fichas: el perfil de cada foco, todos los días."""
    return {"formato": FORMATO, "nombre": BASE, "creado": None, "modificado": None, "notas": "",
            "mes": None, "focos": {f["id"]: _perfil_ficha(f) for f in catalogo["focos"]}}


def nuevo(catalogo, nombre, desde=None):
    """Plan nuevo, copia de `desde` (o de la Base)."""
    esc = json.loads(json.dumps(desde or base(catalogo)))
    esc.update(nombre=nombre, creado=_ahora(), modificado=_ahora())
    return esc


def plan_foco(foco, esc):
    """Plan del foco en `esc`; si no figura, se añade el de su ficha (para poder cambiarlo)."""
    return esc.setdefault("focos", {}).setdefault(foco["id"], _perfil_ficha(foco))


def perfil_dia(pf, i):
    """24 factores del día i del plan del foco."""
    return pf["perfiles"][pf["dias"][i]]


def poner_perfil(pf, dias, perfil):
    """El perfil en esos días (índices). Los perfiles iguales se guardan una sola vez."""
    p = [round(float(x), 3) for x in perfil]
    if len(p) != 24:
        raise ValueError("un perfil tiene 24 horas")
    if p not in pf["perfiles"]:
        pf["perfiles"].append(p)
    k = pf["perfiles"].index(p)
    for i in dias:
        pf["dias"][i] = k
    _limpiar(pf)


def _limpiar(pf):
    """Quita los perfiles que ya no usa ningún día."""
    usados = sorted(set(pf["dias"]))
    pf["dias"] = [usados.index(k) for k in pf["dias"]]
    pf["perfiles"] = [pf["perfiles"][k] for k in usados]


def anio_mes(mes):
    """«2026-11» → (2026, 11)."""
    a, m = str(mes).split("-")
    return int(a), int(m)


def dias_del_mes(mes):
    return calendar.monthrange(*anio_mes(mes))[1]


def cambiar_plan(pf, plan, mes=None):
    """Pasa el foco a otro plan conservando lo que se pueda: al pasar de semanal a mensual, cada día del
    mes toma el de su día de la semana (`mes` = «aaaa-mm»); al revés, el primero de cada día de la semana."""
    if plan not in PLANES:
        raise ValueError(f"plan desconocido: {plan}")
    d, antes = pf["dias"], pf["plan"]
    if plan == antes:
        return
    if plan == "diario":
        dias = [d[0]]
    elif antes == "diario":
        dias = [d[0]] * PLANES[plan]
    else:
        ini = dt.date(*anio_mes(mes), 1)                  # entre semanal y mensual hace falta el calendario
        semana = [(ini + dt.timedelta(days=k)).weekday() for k in range(31)]
        dias = [d[w] for w in semana] if plan == "mensual" else [d[semana.index(w)] for w in range(7)]
    pf.update(plan=plan, dias=dias)
    _limpiar(pf)


def nivel_medio(pf):
    """Emisión media del plan del foco, en tanto por uno de la de referencia."""
    return float(np.mean([np.mean(pf["perfiles"][k]) for k in pf["dias"]]))


def factores(pf, inicios_utc):
    """Factor de emisión del foco en cada hora que EMPIEZA en esos instantes (UTC, sin zona): lo que
    multiplica a la emisión de referencia. Se pasa a hora oficial con su cambio de hora."""
    loc = pd.DatetimeIndex(inicios_utc).tz_localize("UTC").tz_convert(zona())
    i = {"diario": np.zeros(len(loc), int), "semanal": np.asarray(loc.weekday),
         "mensual": np.asarray(loc.day) - 1}[pf["plan"]]
    return np.asarray(pf["perfiles"], float)[np.asarray(pf["dias"])[i], np.asarray(loc.hour)]


def horas_del_plan(esc, fines_utc):
    """Qué horas (por su fin, UTC sin zona) entran en las estadísticas: si algún foco tiene plan mensual,
    las de ese mes del año en todos los años; si no, todas."""
    fines = pd.DatetimeIndex(fines_utc)
    if not any(pf.get("plan") == "mensual" for pf in (esc.get("focos") or {}).values()):
        return np.ones(len(fines), bool)
    loc = fines.tz_localize("UTC").tz_convert(zona())
    return np.asarray(loc.month) == anio_mes(esc["mes"])[1]


def fichero(nombre):
    """Nombre de fichero a partir del del plan: «Volteos por la tarde» → volteos_por_la_tarde.json."""
    s = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "plan"
    return s + ".json"


def guardar(esc, carpeta=None):
    carpeta = Path(carpeta or config.DIR_ESCENARIOS)
    if esc.get("nombre") in (None, "", BASE):
        raise ValueError("la Base no se guarda: ponle otro nombre al plan")
    if any(pf.get("plan") == "mensual" for pf in esc.get("focos", {}).values()) and not esc.get("mes"):
        raise ValueError("un plan mensual necesita su mes")
    esc = dict(esc, formato=FORMATO, modificado=_ahora())
    esc["creado"] = esc.get("creado") or esc["modificado"]
    ruta = carpeta / fichero(esc["nombre"])
    F.escribir_json(ruta, esc)
    return ruta


def cargar(ruta):
    esc = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if esc.get("formato") != FORMATO:
        raise ValueError(f"{Path(ruta).name}: formato {esc.get('formato')!r}; esta versión lee "
                         f"el {FORMATO}")
    return esc


def listar(carpeta=None):
    """[(nombre, ruta, modificado)] de los planes guardados, el último modificado primero."""
    carpeta = Path(carpeta or config.DIR_ESCENARIOS)
    salida = []
    for ruta in carpeta.glob("*.json") if carpeta.is_dir() else []:
        try:
            e = cargar(ruta)
        except (ValueError, OSError):
            continue
        salida.append((e.get("nombre", ruta.stem), ruta, e.get("modificado") or ""))
    return sorted(salida, key=lambda t: t[2], reverse=True)
