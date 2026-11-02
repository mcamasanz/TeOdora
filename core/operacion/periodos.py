# -*- coding: utf-8 -*-
"""El periodo de una simulación según la opción de Meteorología. Las tres modalidades son lo mismo: un periodo de viento y las
respuestas de cada foco en ese periodo; solo cambia la duración, y un plan o un gas se calculan sin lanzar el motor.

  reanalisis   los años del reanálisis (`simulacion.calcular`) y, si se quiere, un día dentro de ellos
  queja        1-3 días; el viento y las respuestas se preparan una vez (`preparar`)
  prediccion   1-5 días desde la última ejecución de las 00 UTC, igual

Un periodo es un dict: {"modo", "ini": "aaaa-mm-dd", "dias", "serie"}.
"""
import json
import subprocess
import sys
import threading
from collections import deque

import pandas as pd

from teodors import planta as config
from teodors.comun import procesos, registro

log = registro.get("periodos")

MODOS = {"reanalisis": "Reanálisis", "queja": "Episodio", "prediccion": "Predicción"}
DIAS = {"queja": (1, 2, 3), "prediccion": (1, 2, 3, 4, 5)}
DIAS_DEFECTO = {"queja": 1, "prediccion": 3}
PREFIJOS = ("queja_", "prediccion_")


def nuevo(modo, ini, dias=1, serie=None):
    ini = pd.Timestamp(ini)
    return {"modo": modo, "ini": f"{ini:%Y-%m-%d}", "dias": int(dias), "serie": serie or f"{modo}_{ini:%Y%m%d}_{int(dias)}d"}


def inicio_prediccion(ahora=None):
    """Día de la última ejecución de las 00 UTC ya publicada (tarda unas 5 h en estar completa)."""
    ahora = ahora or pd.Timestamp.now(tz="UTC").tz_localize(None)
    return (ahora - pd.Timedelta(hours=6)).normalize()


def etiqueta(p):
    ini = pd.Timestamp(p["ini"])
    if p["dias"] == 1:
        return f"{ini:%d/%m/%Y}"
    fin = ini + pd.Timedelta(days=p["dias"] - 1)
    return f"{ini:%d}-{fin:%d/%m/%Y}" if ini.month == fin.month else f"{ini:%d/%m}-{fin:%d/%m/%Y}"


def dir_respuestas(p):
    base = config.DATOS / "respuestas"
    if p["modo"] != "reanalisis":
        return base / p["serie"]
    return base / f"{p['serie']}_{pd.Timestamp(p['ini']):%Y%m%d}"


def listo(p):
    return (dir_respuestas(p) / "meta.json").is_file()


def fuente(p):
    """Con qué se ha calculado el viento del periodo: {"con_estaciones", "aviso"}; {} si no está."""
    f = config.DIR_VIENTO3D / p["serie"] / f"{pd.Timestamp(p['ini']):%Y%m}" / "caso.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def dias_reanalisis():
    """{día: serie} con las respuestas de un día ya calculadas. ⚠️ Prueba: hoy solo hay días sueltos; con la serie de 5 años serán todos."""
    base = config.DATOS / "respuestas"
    salen = {}
    for m in base.glob("*/meta.json") if base.is_dir() else []:
        if not m.parent.name.startswith(PREFIJOS):
            d = json.loads(m.read_text(encoding="utf-8"))
            salen[d["dia"]] = d["serie"]
    return dict(sorted(salen.items()))


def _lanzar(tarea, args, cuenta, cancelado):
    """Una tarea de este paquete en otro proceso: `python -m teodors.operacion.<tarea>`, con la misma planta (TEODORS_PLANTA, que deja
    `planta.activar`) y los mismos DATOS; `cuenta(linea)` sigue su avance por lo que escribe. Se corta si se cancela."""
    env = procesos.entorno(**{config.nombre_env("DATOS"): str(config.DATOS)})
    p = subprocess.Popen([sys.executable, "-m", f"teodors.operacion.{tarea}", *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", env=env, cwd=str(config.PLANTA))
    fin = threading.Event()

    def vigila():
        while not fin.wait(0.5):
            if cancelado and cancelado():
                p.kill()
                return
    threading.Thread(target=vigila, daemon=True).start()
    ultimas = deque(maxlen=12)
    for linea in p.stdout:
        ultimas.append(linea.rstrip())
        log.debug(linea.rstrip())
        cuenta(linea)
    p.wait()
    fin.set()
    if cancelado and cancelado():
        raise RuntimeError("Cálculo cancelado.")
    if p.returncode != 0:
        raise RuntimeError(f"{tarea}.py falló (rc={p.returncode}):\n" + "\n".join(ultimas))


def preparar(p, progreso=None, cancelado=None):
    """Descarga la meteorología del periodo, calcula su viento y las respuestas de los focos."""
    avisa = progreso or (lambda *_: None)
    avisa(1, "Descargando la meteorología…")
    pasos = {"1)": (2, "Estaciones…"), "2)": (10, "Modelo meteorológico…"), "3)": (25, "Modelo meteorológico…"), "4)": (30, "Viento 3D…"),
             "5)": (40, "Respuestas de los focos…")}

    def viento(linea):
        marca = linea.strip()[:2]
        if marca in pasos:
            avisa(*pasos[marca])
    args = ["--dia", p["ini"], "--dias", p["dias"], "--serie", p["serie"]]
    _lanzar("viento_periodo", args + (["--prediccion"] if p["modo"] == "prediccion" else []), viento, cancelado)
    hechos = {"n": 0}

    def respuestas(linea):
        if linea.startswith("  F") or " focos por calcular" in linea:
            hechos["n"] += 1
            avisa(min(40 + 4 * hechos["n"], 98), "Respuestas de los focos…")
    _lanzar("respuestas", args, respuestas, cancelado)
    avisa(100, "Hecho")
    log.info(f"{MODOS[p['modo']]} {etiqueta(p)}: viento y respuestas preparados.")
    return {"periodo": p}
