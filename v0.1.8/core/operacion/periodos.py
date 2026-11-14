# -*- coding: utf-8 -*-
"""El periodo de una simulación según la opción de Meteorología. Las tres modalidades son lo mismo: un periodo de viento y las
respuestas de cada foco en ese periodo; solo cambia la duración, y un plan o un gas se calculan sin lanzar el motor.

  reanalisis   los años del reanálisis (`simulacion.calcular`) y, si se quiere, un día dentro de ellos
  queja        1-3 días; el viento y las respuestas se preparan una vez (`preparar`)
  prediccion   1-5 días desde la última ejecución de las 00 UTC, igual

Un periodo es un dict: {"modo", "ini": "aaaa-mm-dd", "dias", "serie"}.
"""
import json
import os
import subprocess
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
    from teodors.casos import viento3d as vc
    ini = pd.Timestamp(p["ini"])
    return vc.info_mes(p["serie"], ini.year, ini.month) or {}                      # de DATOS o del paquete de viento


def dias_reanalisis():
    """{día: serie} con las respuestas de un día ya calculadas. ⚠️ Prueba: hoy solo hay días sueltos; con la serie de 5 años serán todos."""
    base = config.DATOS / "respuestas"
    salen = {}
    for m in base.glob("*/meta.json") if base.is_dir() else []:
        if not m.parent.name.startswith(PREFIJOS):
            d = json.loads(m.read_text(encoding="utf-8"))
            salen[d["dia"]] = d["serie"]
    return dict(sorted(salen.items()))


def _matar_arbol(proc):
    """Mata el proceso Y todos sus hijos. En Windows `proc.kill()` solo mata al padre y deja huérfanos los subprocesos (los `puffs` de cada
    foco, el motor `viento3d`), así que se mata el árbol con `taskkill /T`."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            proc.kill()
    except Exception:                                    # noqa: BLE001
        try:
            proc.kill()
        except Exception:                                # noqa: BLE001
            pass


def _lanzar(tarea, args, cuenta, cancelado):
    """Una tarea de este paquete en otro proceso: `python -m teodors.operacion.<tarea>`, con la misma planta (TEODORS_PLANTA, que deja
    `planta.activar`) y los mismos DATOS; `cuenta(linea)` sigue su avance por lo que escribe. Se corta si se cancela (matando el árbol)."""
    env = procesos.entorno(**{config.nombre_env("DATOS"): str(config.DATOS)})
    p = subprocess.Popen(procesos.orden(f"teodors.operacion.{tarea}", *args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", env=env, cwd=str(config.PLANTA))
    fin = threading.Event()

    def vigila():
        while not fin.wait(0.5):
            if cancelado and cancelado():
                _matar_arbol(p)                          # mata el proceso Y sus hijos (los puff de cada foco, el motor 3D): si no, quedan huérfanos
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


def preparar_respuestas(p, progreso=None, cancelado=None):
    """Solo las RESPUESTAS (puff) de los focos del periodo (el viento ya tiene que estar hecho). Paralelo por foco (`respuestas.py`). Para
    el botón «Simular episodio» cuando aún no están calculadas."""
    avisa = progreso or (lambda *_: None)
    total = {"n": 0, "focos": 0}

    def respuestas(linea):
        s = linea.strip()
        if "focos por calcular" in s:                     # «N focos por calcular y M ya hechos · …»
            try:
                total["focos"] = int(s.split()[0])
            except (ValueError, IndexError):
                pass
        elif "máx." in s:                                 # «  <foco> (…): N s · máx. … µg/m³ por g/s» = un foco terminado
            total["n"] += 1
            pct = min(5 + 90 * total["n"] // max(total["focos"], 1), 98) if total["focos"] else min(5 + 11 * total["n"], 98)
            avisa(pct, f"Respuestas de los focos… ({total['n']}/{total['focos'] or '?'})")
    avisa(2, "Respuestas de los focos (puff)…")
    _lanzar("respuestas", ["--dia", p["ini"], "--dias", p["dias"], "--serie", p["serie"]], respuestas, cancelado)
    avisa(100, "Respuestas listas")
    log.info(f"{MODOS[p['modo']]} {etiqueta(p)}: respuestas de los focos preparadas.")
    return {"periodo": p}


def preparar_viento(p, progreso=None, cancelado=None):
    """Solo el VIENTO del periodo: descarga la meteorología (GFS + estaciones) y calcula su viento 3D, SIN las respuestas de
    dispersión. Para el modo episodio (parte Meteo). Lo descargado va a la carpeta local; el viento 3D, a la serie (se guarda/carga)."""
    avisa = progreso or (lambda *_: None)
    avisa(1, "Descargando la meteorología…")
    pasos = {"1)": (5, "Estaciones…"), "2)": (25, "Modelo meteorológico (GFS)…"),
             "3)": (60, "Modelo meteorológico (GFS)…"), "4)": (85, "Viento 3D…")}

    def viento(linea):
        marca = linea.strip()[:2]
        if marca in pasos:
            avisa(*pasos[marca])
    args = ["--dia", p["ini"], "--dias", p["dias"], "--serie", p["serie"]]
    _lanzar("viento_periodo", args, viento, cancelado)
    avisa(100, "Viento listo")
    log.info(f"{MODOS[p['modo']]} {etiqueta(p)}: viento preparado (sin respuestas).")
    return {"periodo": p}


def coherencia_viento(p):
    """Coherencia de las estaciones del periodo (lee la caché `DATOS/meteo/meteocat/<cod>/<año>.csv`): cobertura, viento sin dato,
    valores imposibles, sensor atascado (varianza ~0, no «mucha calma») y divergencia de la media frente al grupo. Devuelve
    {"estaciones": {cod: {...}}, "avisos": [str], "mediana_grupo": x}."""
    import numpy as np
    base = config.DIR_METEO / "meteocat"
    if not base.is_dir():
        return {"estaciones": {}, "avisos": ["Sin caché de estaciones"], "mediana_grupo": None}
    ini = pd.Timestamp(p["ini"])
    fin = ini + pd.Timedelta(days=int(p["dias"]))
    esperadas = 48 * int(p["dias"])                                  # medias-horas
    est, medias = {}, []
    for d in sorted(x for x in base.iterdir() if x.is_dir()):
        anios = {ini.year, (fin - pd.Timedelta(days=1)).year}
        trozos = [pd.read_csv(d / f"{a}.csv", parse_dates=["time"]) for a in anios if (d / f"{a}.csv").is_file()]
        if not trozos:
            continue
        x = pd.concat(trozos, ignore_index=True)
        x = x[(x.time >= ini) & (x.time < fin)]
        ws = pd.to_numeric(x.get("ws"), errors="coerce")
        ok = ws.dropna()
        s = {"cobertura": round(100 * len(x) / esperadas) if esperadas else 0,
             "ws_nan": round(100 * ws.isna().mean()) if len(x) else 100,
             "media": round(float(ok.mean()), 2) if len(ok) else None,
             "std": round(float(ok.std()), 3) if len(ok) > 1 else 0.0,
             "fuera_rango": int(((ok < 0) | (ok > 40)).sum())}
        est[d.name] = s
        if s["media"] is not None:
            medias.append(s["media"])
    med = float(np.median(medias)) if medias else None
    avisos = []
    for cod, s in est.items():
        if s["cobertura"] < 90:
            avisos.append(f"{cod}: cobertura {s['cobertura']} % (huecos)")
        if s["ws_nan"] > 10:
            avisos.append(f"{cod}: {s['ws_nan']} % de viento sin dato")
        if s["fuera_rango"]:
            avisos.append(f"{cod}: {s['fuera_rango']} valores imposibles")
        if s["media"] is not None and s["std"] < 0.05:
            avisos.append(f"{cod}: viento constante (¿sensor atascado?)")
        if s["media"] is not None and med is not None and abs(s["media"] - med) > 2.0:
            avisos.append(f"{cod}: se desvía {s['media'] - med:+.1f} m/s del grupo")
    return {"estaciones": est, "avisos": avisos, "mediana_grupo": round(med, 2) if med is not None else None}


def dir_episodios():
    """Base de los episodios guardados: `casos/episodios` (`DIR_CASOS`/`CARPETAS_CASOS["queja"]`)."""
    from teodors.planta import CARPETAS_CASOS
    return config.DIR_CASOS / CARPETAS_CASOS["queja"]


def central_episodio(p):
    """El día de la queja (central de la ventana víspera/día/siguiente): ini + dias//2, «AAAA-MM-DD»."""
    return f"{pd.Timestamp(p['ini']) + pd.Timedelta(days=p['dias'] // 2):%Y-%m-%d}"


def guardar_viento(p):
    """Guarda de forma PERMANENTE el viento 3D del episodio (que vive en tmp) en `casos/episodios/<central>/viento`, con un `viento.json`
    (serie, ini, dias, central). Devuelve la carpeta. El viento sigue también en tmp para poder usarlo sin recargar."""
    import shutil
    from teodors.casos import viento3d as vc
    src = vc.dir_serie(p["serie"])
    if not src.is_dir():
        raise FileNotFoundError(f"No hay viento calculado en tmp para «{p['serie']}».")
    central = central_episodio(p)
    dest = dir_episodios() / central / "viento"
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    (dest / "viento.json").write_text(
        json.dumps({"serie": p["serie"], "ini": p["ini"], "dias": p["dias"], "central": central}, ensure_ascii=False),
        encoding="utf-8")
    log.info(f"Viento del episodio guardado en {dest}")
    return dest


def vientos_episodio():
    """Los vientos de episodio GUARDADOS en `casos/episodios/<fecha>/viento` (por su `viento.json`): [{serie, ini, dias, central,
    carpeta}], de nuevo a viejo. El día central es el de la queja."""
    out = []
    base = dir_episodios()
    if base.is_dir():
        for d in sorted(base.iterdir()):
            meta = d / "viento" / "viento.json"
            if meta.is_file():
                try:
                    v = json.loads(meta.read_text(encoding="utf-8"))
                    v["carpeta"] = str(d / "viento")
                    out.append(v)
                except (OSError, ValueError):
                    pass
    return sorted(out, key=lambda x: x.get("ini", ""), reverse=True)


def cargar_viento(v):
    """Trae un viento de episodio guardado (`casos/episodios/.../viento`) a tmp (`dir_serie`), para usarlo/animarlo. Devuelve su periodo."""
    import shutil
    from pathlib import Path
    from teodors.casos import viento3d as vc
    src = Path(v["carpeta"])
    dest = vc.dir_serie(v["serie"])
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    return nuevo("queja", v["ini"], v["dias"], v["serie"])


def borrar_viento_tmp(p):
    """Borra de tmp lo del episodio al cancelar: el viento 3D, su caso de trabajo y el GFS descargado del episodio. NO toca lo guardado en
    `casos/episodios` ni el histórico compartido de estaciones (`DATOS/meteo/meteocat`)."""
    import shutil
    from teodors.casos import viento3d as vc
    for d in (vc.dir_serie(p["serie"]),
              config.DIR_TRABAJO / "viento_dia_local" / p["serie"],
              config.LOCAL / "meteo_episodio" / p["serie"]):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
