# -*- coding: utf-8 -*-
"""Todo lo que necesita el informe de un caso del reanálisis, sacado de la carpeta del caso y de la planta, sin Qt y sin capturas
(`reunir`): el resultado, los focos y el plan con los que se simuló, los pueblos, las zonas industriales y la vivienda más expuesta, la
superficie por encima de cada umbral de olor, el terreno, los edificios de la planta, el viento más frecuente y la operación hora a hora.

Lo de cada caso sale de su carpeta si lo guardó (`simulacion.guardar_caso`: focos.json, plan_operacion.json, lugares.json,
edificios_planta.json); si no, de la planta como está ahora, y el informe lo dice (`d["avisos"]`).
"""
import datetime as dt
import json
from pathlib import Path

import numpy as np

from teodors import planta as config
from teodors.comun import registro
from teodors.operacion import comparacion as C, focos as F, planes as E, serie_respuestas as SR, simulacion as S
from teodors.writer import estilo

log = registro.get("writer")


class NoEsReanalisis(ValueError):
    """Por ahora, el informe es el de un caso del reanálisis (usuario, 2026-11-10: el de queja y el de predicción, más adelante)."""


def _json(ruta):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _focos(raiz, avisos):
    cat = _json(raiz / "focos.json")
    if cat is not None:
        return cat
    avisos.append("El caso no guardó sus focos: se describen los de la planta de ahora.")
    return F.cargar()


def _lugares(raiz):
    """{«centro», «etiquetas»} de los receptores del caso: su lugares.json o el índice de la serie del reanálisis; None si no hay."""
    lug = _json(raiz / "lugares.json")
    if lug is not None:
        return lug
    carpeta = S.dir_respuestas()
    if carpeta is None:
        return None
    ind = SR.indice(carpeta)
    return {"centro": ind["centro"], "etiquetas": ind.get("etiquetas", [])}


def _edificios(raiz):
    eds = _json(raiz / "edificios_planta.json")
    if eds is not None:
        return eds.get("edificios", [])
    from teodors.operacion import edificios_planta as EP
    try:
        return EP.cargar()["edificios"]
    except (ValueError, OSError):
        return []


def _terreno(emp):
    """El terreno descargado de la planta: sus mallas, su resumen (grupos de usos, bandas de cota, núcleos) y el nombre de sus núcleos (de la
    caché: sin red); None si no hay."""
    from teodors.fuentes import terreno as T
    info = T.ultimo_caso(emp["lat"], emp["lon"])
    if not info:
        return None
    Z, U, tr = T.cargar(info)
    res = T.resumen(Z, U, tr, emp["lat"], emp["lon"])
    try:
        nombres = T.nombres_nucleos(info, res["nucleos"])
    except (OSError, ValueError):
        nombres = {}
    return {"Z": Z, "U": U, "tr": tr, "info": info, "resumen": res, "nombres": nombres}


def _viento():
    """De dónde sopla el viento más a menudo en la planta (la rosa del reanálisis), o None."""
    try:
        from teodors.operacion import viento_mapa as VM
        serie = VM.serie_disponible()
        if not serie:
            return None
        rp = VM.resumen_planta(VM.serie_planta(serie))
    except Exception as ex:                                  # noqa: BLE001 (sin viento, el informe igual)
        log.warning(f"Informe: sin el viento de la planta ({ex}).")
        return None
    if not rp:
        return None
    tot = [sum(s) for s in rp["rosa"]]
    k = int(np.argmax(tot))
    return {"de_donde": k * 360.0 / len(tot), "pct": float(tot[k]), "media": rp["media"], "calmas": rp["calmas"]}


def eventos_viento(horas, ws, wd, frecuentes=2):
    """Las situaciones del viento en la planta que enseña el informe (usuario, 2026-11-10: «el evento más frecuente y el más extremo»; luego,
    «como queda espacio, pon los dos escenarios más frecuentes y el más intenso»):
    - las más frecuentes (`frecuentes`): una por cada rumbo de los que más horas sopla (16 rumbos, sin las calmas), con su velocidad típica (la
      mediana de esas horas): el día en que más horas sopla de ese rumbo (a igualdad, el de velocidad más típica; sin repetir día) y, de ese
      día, la hora más típica;
    - la más extrema: la hora de más viento.
    `horas`, «aaaa-mm-dd HH» (las de la serie). {"frecuentes": [...], de la que más a la que menos, "extremo"}, cada una {"hora", "dia", "h"
    (su hora en el día, para el mapa), "ws", "wd", "rumbo"}; las frecuentes, además, "rumbo_dominante" (el suyo), "pct" (% de las horas con
    viento), "tipica" (m/s) y "horas_dia" (las de ese día con ese rumbo). None si todo es calma."""
    from teodors.operacion import viento_mapa as VM
    ws, wd = np.asarray(ws, float), np.asarray(wd, float)
    ok = ws >= VM.CALMA
    if not ok.any():
        return None
    sec = (((wd + 11.25) % 360.0) // 22.5).astype(int)
    por_rumbo = np.bincount(sec[ok], minlength=16)
    dias, inv = np.unique(np.array([h[:10] for h in horas]), return_inverse=True)

    def evento(i):
        return {"hora": horas[i], "dia": horas[i][:10], "h": int(horas[i][11:13]), "ws": float(ws[i]), "wd": float(wd[i]), "rumbo": VM.rumbo(wd[i])}
    salen, usados = [], []
    for s in np.argsort(-por_rumbo, kind="stable")[:frecuentes]:
        en = ok & (sec == s)
        cuenta = np.bincount(inv, weights=en.astype(float), minlength=len(dias))
        cuenta[usados] = 0.0                                        # otro día que el de las de antes
        if not en.any() or cuenta.max() <= 0:
            break
        tipica = float(np.median(ws[en]))
        suma = np.bincount(inv, weights=np.where(en, ws, 0.0), minlength=len(dias))
        media = np.divide(suma, cuenta, out=np.full(len(dias), np.inf), where=cuenta > 0)
        cand = np.flatnonzero(cuenta == cuenta.max())
        j = int(cand[np.argmin(np.abs(media[cand] - tipica))])
        usados.append(j)
        del_dia = np.flatnonzero((inv == j) & en)
        k = int(del_dia[np.argmin(np.abs(ws[del_dia] - tipica))])
        salen.append(dict(evento(k), rumbo_dominante=VM.RUMBOS[int(s)], pct=float(en.sum() / ok.sum() * 100), tipica=tipica,
                          horas_dia=int(cuenta[j])))
    return {"frecuentes": salen, "extremo": evento(int(np.argmax(ws)))}


def _estaciones(emp, periodo=None):
    """Las estaciones de la zona con su rosa: la de los años del reanálisis (`rosas_estaciones`, en caché) o, con `periodo`, la de SUS días
    (`rosas_periodo`). {"clases", "lista"}, de la más cercana a la más lejana, o None."""
    from teodors.fuentes import meteocat as M
    from teodors.metricas import viento as MV
    from teodors.operacion import viento_mapa as VM
    try:
        lista = M.cercanas(emp["lat"], emp["lon"])
        if periodo is not None:
            fin = (dt.date.fromisoformat(periodo["ini"]) + dt.timedelta(days=periodo["dias"] - 1)).isoformat()
            rosas = MV.rosas_periodo(emp["lat"], emp["lon"], periodo["ini"], fin)
        else:
            rosas = MV.rosas_estaciones(emp["lat"], emp["lon"])
    except Exception as ex:                                  # noqa: BLE001 (sin estaciones, el informe igual)
        log.warning(f"Informe: sin las rosas de las estaciones ({ex}).")
        return None
    salen = []
    for e in lista:
        r = rosas.get("estaciones", {}).get(e["codigo"])
        if not r or not r.get("horas"):
            continue
        obs = np.asarray(r["obs"], float)
        por = obs.sum(axis=1)
        s = int(por.argmax())
        desde = r.get("desde") or (rosas.get("ini") or "")       # reanálisis: años; episodio: fechas del periodo
        hasta = r.get("hasta") or (rosas.get("fin") or "")
        salen.append({"codigo": e["codigo"], "nombre": e["nombre"], "km": e["dist_m"] / 1000.0, "desde_planta": e["rumbo"], "lat": e["lat"],
                      "lon": e["lon"],
                      "altitud": e.get("altitud_m"), "altura": r.get("altura_m"), "horas": r["horas"], "desde": desde, "hasta": hasta,
                      "obs": r["obs"], "calmas": float(r["calmas"]), "dominante": VM.RUMBOS[s], "dominante_grados": s * 22.5,
                      "dominante_pct": float(por[s] / max(por.sum(), 1e-9) * 100), "fuerte": float(obs[:, -1].sum())})
    return {"clases": rosas.get("clases"), "lista": salen} if salen else None


# el tiempo en la planta (usuario, 2026-11-10: «gráficas de los valores medios por día de estos 5 años… de todas las variables del ERA5»)
HORAS_NOCHE, HORAS_DIA = tuple(range(0, 6)), tuple(range(11, 17))   # en hora oficial: lo hondo de la noche y el centro del día
NOCHE_LARGA = tuple(range(20, 24)) + tuple(range(0, 8))            # «de noche», para las horas difíciles
DIFICIL_VIENTO, DIFICIL_MEZCLA = 1.5, 200.0     # horas difíciles para el olor: viento de menos de 1,5 m/s, aire estable y capa de mezcla < 200 m


def _magnus(t):
    return np.exp(17.625 * t / (243.04 + t))


def _fecha(d):
    return f"{d.day}/{d.month}/{d.year}"


def clima(sfc, horas, ws, wd):
    """El tiempo en la planta en los años del reanálisis, día a día y resumido. Del ERA5 (`sfc`: `fuentes.era5.cargar_sfc`, horario, en
    UTC), la temperatura, la humedad relativa (de su punto de rocío), las nubes, la lluvia, la radiación solar, la presión, la velocidad de
    fricción, el calor sensible (hacia arriba: −sshf) y la capa de mezcla; el viento, el de la planta (`horas` UTC «aaaa-mm-dd HH», `ws`,
    `wd`: el del viento 3D, el de las rosas). Los días y las horas, en hora oficial.
    {"dias": [date], "series": {clave: {"v": [...], y "min" y "max" las que tienen banda}}, "resumen": {...}}, o None sin ERA5."""
    import pandas as pd
    from teodors.operacion import viento_mapa as VM
    if sfc is None or len(sfc) == 0:
        return None
    df = sfc.copy()
    df["time"] = pd.to_datetime(df["time"])
    pl = pd.DataFrame({"time": pd.to_datetime([h[:13] + ":00" for h in horas]), "ws": np.asarray(ws, float), "wd": np.asarray(wd, float)})
    df = df.merge(pl, on="time", how="left").sort_values("time").reset_index(drop=True)
    loc = df["time"].dt.tz_localize("UTC").dt.tz_convert(E.zona())
    df["dia"], df["mes"], df["h"] = loc.dt.date, loc.dt.month, loc.dt.hour
    primero, ultimo = df["time"].iloc[0].date(), df["time"].iloc[-1].date()
    df = df[(df["dia"] >= primero) & (df["dia"] <= ultimo)].copy()      # sin el pico de un día que deja la hora oficial
    df["hr"] = 100.0 * _magnus(df["d2m"]) / _magnus(df["t2m"])
    df["nubes"] = 100.0 * df["tcc"]
    df["H"] = -df["sshf"]
    rad = np.radians(df["wd"])
    df["_s"], df["_c"] = df["ws"] * np.sin(rad), df["ws"] * np.cos(rad)
    g = df.groupby("dia")
    media = g[["ws", "t2m", "hr", "nubes", "ssrd", "sp", "zust", "H", "blh", "_s", "_c"]].mean()
    lluvia = g["tp"].sum()
    dias = list(media.index)

    def lista(s):
        return [float(x) for x in s]
    series = {"viento": {"v": lista(media["ws"])},
              "direccion": {"v": lista(np.degrees(np.arctan2(media["_s"], media["_c"])) % 360.0)},   # de dónde sopla: el vector medio
              "temperatura": {"v": lista(media["t2m"]), "min": lista(g["t2m"].min()), "max": lista(g["t2m"].max())},
              "humedad": {"v": lista(media["hr"])}, "nubes": {"v": lista(media["nubes"])}, "lluvia": {"v": lista(lluvia)},
              "radiacion": {"v": lista(media["ssrd"])}, "presion": {"v": lista(media["sp"])}, "friccion": {"v": lista(media["zust"])},
              "calor": {"v": lista(media["H"])},
              "mezcla": {"v": lista(media["blh"]), "min": lista(g["blh"].min()), "max": lista(g["blh"].max())}}

    def cuando(i):
        return _fecha(loc[i])
    T, H = df["t2m"], df["H"]
    noche, dia = df["h"].isin(HORAS_NOCHE), df["h"].isin(HORAS_DIA)
    verano, invierno = df["mes"].isin((6, 7, 8)), df["mes"].isin((12, 1, 2))
    meses = range(1, 13)
    anio = pd.Series([d.year for d in dias], index=media.index)
    sec = (((df["wd"].fillna(0.0) + 11.25) % 360.0) // 22.5).astype(int)
    con_viento = df["ws"] >= VM.CALMA

    def dominante(m):
        m = m & con_viento
        if not m.any():
            return None
        c = np.bincount(sec[m], minlength=16)
        s = int(c.argmax())
        return {"rumbo": VM.RUMBOS[s], "grados": s * 22.5, "pct": float(100 * c[s] / c.sum())}
    resumen = {
        "desde": dias[0], "hasta": dias[-1],
        "horas": {"noche": (HORAS_NOCHE[0], HORAS_NOCHE[-1] + 1), "dia": (HORAS_DIA[0], HORAS_DIA[-1] + 1), "noche_larga": (NOCHE_LARGA[0], NOCHE_LARGA[-1] + 1)},
        "t": {"media": float(T.mean()), "por_mes": lista(df.groupby("mes")["t2m"].mean().reindex(meses)), "min": float(T.min()),
              "min_dia": cuando(T.idxmin()), "max": float(T.max()), "max_dia": cuando(T.idxmax())},
        "humedad": float(df["hr"].mean()),
        "lluvia": {"por_anio": {int(a): float(v) for a, v in lluvia.groupby(anio).sum().items()},
                   "dias_anio": float((lluvia >= 1.0).groupby(anio).sum().mean()), "max": float(lluvia.max()), "max_dia": _fecha(lluvia.idxmax())},
        "nubes": {"media": float(df["nubes"].mean()), "despejados": float(100 * (media["nubes"] < 20).mean()),
                  "cubiertos": float(100 * (media["nubes"] > 80).mean())},
        "radiacion": {"media": float(df["ssrd"].mean()), "por_mes": lista(df.groupby("mes")["ssrd"].mean().reindex(meses))},
        "presion": {"media": float(df["sp"].mean()), "min": float(df["sp"].min()), "min_dia": cuando(df["sp"].idxmin())},
        "mezcla": {"noche": float(df.loc[noche, "blh"].median()), "dia": float(df.loc[dia, "blh"].mean()),
                   "friccion": float(df["zust"].mean()), "friccion_noche": float(df.loc[noche, "zust"].mean()),
                   "friccion_dia": float(df.loc[dia, "zust"].mean()), "estable": float(100 * (H < 0).mean()),
                   "estable_noche": float(100 * (H[noche] < 0).mean())},
        "viento": None, "dificil": None}
    if df["ws"].notna().any():
        ws_ = df["ws"]
        resumen["viento"] = {"media": float(ws_.mean()), "noche": float(ws_[noche].mean()), "dia": float(ws_[dia].mean()),
                             "invierno": float(ws_[invierno].mean()), "verano": float(ws_[verano].mean()),
                             "dom_noche": dominante(noche), "dom_dia": dominante(dia), "dom_verano_dia": dominante(verano & dia),
                             "dom_invierno_noche": dominante(invierno & noche)}
        dificil = (ws_ < DIFICIL_VIENTO) & (H < 0) & (df["blh"] < DIFICIL_MEZCLA)
        if dificil.any():
            resumen["dificil"] = {"viento": DIFICIL_VIENTO, "mezcla": DIFICIL_MEZCLA,
                                  "pct": float(100 * dificil[ws_.notna()].mean()), "noche": float(100 * df.loc[dificil, "h"].isin(NOCHE_LARGA).mean()),
                                  "por_mes": lista(100 * dificil.groupby(df["mes"]).mean().reindex(meses)), "dominante": dominante(dificil)}
    return {"dias": dias, "series": series, "resumen": resumen}


def _era5(emp, horas, ws, wd):
    """El tiempo en la planta del ERA5 (`clima`) y su celda (punto.json, si está: sin pedírsela al CDS), o None."""
    from teodors.fuentes import era5 as E5
    try:
        sfc = E5.cargar_sfc(emp["lat"], emp["lon"])
        f = E5.dir_era5(emp["lat"], emp["lon"]) / "punto.json"
        c = clima(sfc, horas, ws, wd)
    except Exception as ex:                                  # noqa: BLE001 (sin ERA5, el informe igual)
        log.warning(f"Informe: sin el tiempo del ERA5 ({ex}).")
        return None
    if not c:
        return None
    t = sfc["time"] if "time" in sfc else None
    horario = ({"horas": list(np.datetime_as_string(np.asarray(t, "datetime64[h]"), unit="h")), "H": list(-np.asarray(sfc["sshf"], float)),
                "blh": list(np.asarray(sfc["blh"], float))} if t is not None else None)
    if horario:
        horario["horas"] = [h.replace("T", " ") for h in horario["horas"]]                     # «aaaa-mm-dd HH», como la serie del viento
    return dict(c, punto=_json(f) if f.is_file() else None, _sfc=horario)


# ── la meteo del episodio frente a lo NORMAL de esas fechas (2021-2025), del ERA5 en la celda de la planta (usuario, 2026-11-13: «para estas
# fechas los históricos dan X y los de esa fecha han dado Y») ──
VARS_COMPARACION = (
    ("viento", "Velocidad del viento", "m/s", "linea", True),
    ("direccion", "De dónde sopla el viento", "", "rumbos", False),
    ("temperatura", "Temperatura", "°C", "linea", False),
    ("humedad", "Humedad relativa", "%", "linea", False),
)   # solo lo que MIDEN las estaciones (ws, wd, t, rh); la capa de mezcla y el calor sensible solo los daba el modelo ERA5

_COL_COMP = {"viento": "ws", "direccion": "wd", "temperatura": "t", "humedad": "rh"}


def _dir_media(grados):
    """Media circular de una dirección en grados (0-360); NaN si no hay datos."""
    a = np.asarray(list(grados), float)
    a = a[np.isfinite(a)]
    if not len(a):
        return float("nan")
    r = np.deg2rad(a)
    return float(np.degrees(np.arctan2(np.mean(np.sin(r)), np.mean(np.cos(r)))) % 360.0)


def _clima_comparacion(emp, periodo):
    """La meteo de los días del episodio frente a lo NORMAL de esas mismas fechas, SOLO de las estaciones de la zona (ya descargadas en la
    preparación del episodio; sin ERA5 ni CDS). Para cada hora del episodio (hora oficial) el valor medido (media de las estaciones con dato) y, de
    los años del reanálisis en la misma fecha y hora, el mínimo-mediana-máximo (la «banda normal»: un valor por año = media de las estaciones ese
    año). La dirección: nube de puntos del histórico + puntos del episodio. Sin capa de mezcla ni calor sensible (solo los daba el modelo ERA5).
    None si ninguna estación tiene datos de esas fechas. {"ini","dias","anios","cobertura","n_horas","fuente","variables":[{"clave","nombre",
    "unidad","forma","cero","ep":[N],"lo":[N],"med":[N],"hi":[N],"nube":[(i,valor)] (solo rumbos),"media_ep","media_normal","anomalia"}]}."""
    import pandas as pd
    from teodors import planta as config
    from teodors.casos import viento3d as VC
    from teodors.fuentes import meteocat as M
    ini = dt.date.fromisoformat(str(periodo["ini"]))
    dias = int(periodo["dias"])
    anios_hi = sorted(int(a) for a in config.REANALISIS_ANIOS if int(a) != ini.year)   # el «normal» nunca incluye el propio año del episodio
    if not anios_hi:
        return None
    anios = sorted(set(anios_hi) | {ini.year})
    zona = E.zona()
    try:
        cercanas = M.cercanas(emp["lat"], emp["lon"])
    except Exception as ex:                                           # noqa: BLE001 (sin estaciones, el informe sale igual)
        log.warning(f"Informe: sin la comparación de meteo del episodio ({ex}).")
        return None
    frames = []
    for e in cercanas:
        try:
            o = VC.obs_horarias(e["codigo"], anios)                   # estaciones en caché (incluye los días del episodio): sin red
        except Exception:                                            # noqa: BLE001 (una estación sin datos no tumba la página)
            continue
        if o is None or getattr(o, "empty", True) or "time" not in getattr(o, "columns", []):
            continue
        o = o.copy()
        loc = pd.to_datetime(o["time"]).dt.tz_localize("UTC").dt.tz_convert(zona)
        o["mes"], o["dia"], o["hh"], o["anio"] = loc.dt.month, loc.dt.day, loc.dt.hour, loc.dt.year
        frames.append(o)
    if not frames:
        return None
    obs = pd.concat(frames, ignore_index=True)
    ranuras = [((ini + dt.timedelta(days=i // 24)).month, (ini + dt.timedelta(days=i // 24)).day, i % 24) for i in range(dias * 24)]
    variables = []
    for clave, nombre, unidad, forma, cero in VARS_COMPARACION:
        col = _COL_COMP[clave]
        if col not in obs.columns:
            continue
        vcol = pd.to_numeric(obs[col], errors="coerce").to_numpy(float)
        fin = np.isfinite(vcol)
        sub = obs.loc[fin, ["mes", "dia", "hh", "anio"]].copy()
        sub["val"] = vcol[fin]
        if forma == "rumbos":
            mm, dd, hh, an, vv = (sub[c].to_numpy() for c in ("mes", "dia", "hh", "anio", "val"))
            epv, nube = [], []
            for i, (m, d, h) in enumerate(ranuras):
                mask = (mm == m) & (dd == d) & (hh == h)
                nube += [(i, float(x)) for x in vv[mask & (an != ini.year)]]
                epv.append(_dir_media(vv[mask & (an == ini.year)]))
            variables.append({"clave": clave, "nombre": nombre, "unidad": unidad, "forma": forma, "cero": cero,
                              "ep": epv, "lo": [float("nan")] * len(ranuras), "med": [float("nan")] * len(ranuras),
                              "hi": [float("nan")] * len(ranuras), "nube": nube,
                              "media_ep": _dir_media([x for x in epv if np.isfinite(x)]), "media_normal": float("nan"), "anomalia": float("nan")})
            continue
        g = sub.groupby(["anio", "mes", "dia", "hh"])["val"].mean()   # un valor por año y ranura = media de las estaciones
        epv, lo, med, alt = [], [], [], []
        for (m, d, h) in ranuras:
            vals = np.array([g.get((a, m, d, h), float("nan")) for a in anios_hi], float)
            vals = vals[np.isfinite(vals)]
            if len(vals):
                lo.append(float(np.min(vals))); med.append(float(np.median(vals))); alt.append(float(np.max(vals)))
            else:
                lo.append(float("nan")); med.append(float("nan")); alt.append(float("nan"))
            ev = g.get((ini.year, m, d, h), float("nan"))
            epv.append(float(ev) if np.isfinite(ev) else float("nan"))
        epa, meda = np.array(epv), np.array(med)
        ok = np.isfinite(epa)
        media_ep = float(np.nanmean(epa)) if ok.any() else float("nan")
        media_normal = float(np.nanmean(meda[ok])) if (ok.any() and np.isfinite(meda[ok]).any()) else (float(np.nanmean(meda)) if np.isfinite(meda).any() else float("nan"))
        variables.append({"clave": clave, "nombre": nombre, "unidad": unidad, "forma": forma, "cero": cero,
                          "ep": epv, "lo": lo, "med": med, "hi": alt, "nube": [], "media_ep": media_ep, "media_normal": media_normal,
                          "anomalia": (media_ep - media_normal) if (np.isfinite(media_ep) and np.isfinite(media_normal)) else float("nan")})
    if not variables:
        return None
    cobertura = int(max((np.isfinite(np.array(v["ep"])).sum() for v in variables), default=0))
    if cobertura == 0:
        return None
    return {"ini": ini.isoformat(), "dias": dias, "anios": f"{anios_hi[0]}–{anios_hi[-1]}", "cobertura": cobertura,
            "n_horas": dias * 24, "variables": variables, "fuente": "estaciones"}


def _meteo(emp, serie=None, periodo=None):
    """La meteorología del informe a partir del viento 3D: el de la planta (su rosa y sus cifras), las estaciones de la zona (sus rosas), las
    situaciones del mapa (`eventos_viento`) y, en reanálisis, el tiempo día a día (`clima` del ERA5). Con `periodo` (episodio/predicción) se
    usa SU serie y solo SUS días (sin el día de arranque), las rosas de esos días (`rosas_periodo`) y sin el clima de ERA5. None si no hay
    serie de viento."""
    try:
        from teodors.operacion import viento_mapa as VM
        if serie is None:
            serie = VM.serie_disponible()
        if not serie:
            return None
        datos = VM.serie_planta(serie)
        rp = VM.resumen_planta(datos)
    except Exception as ex:                                  # noqa: BLE001 (sin viento, el informe igual)
        log.warning(f"Informe: sin el viento ({ex}).")
        return None
    if not rp:
        return None
    desde = hasta = None
    if periodo is not None:                                  # solo los días del episodio/predicción (fuera el día de arranque)
        desde = str(periodo["ini"])
        hasta = (dt.date.fromisoformat(periodo["ini"]) + dt.timedelta(days=periodo["dias"])).isoformat()
    horas, ws, wd = [], [], []
    for k in sorted(datos):
        hs, a, b = datos[k]["horas"], datos[k]["ws"], datos[k]["wd"]
        sel = range(len(hs)) if desde is None else [i for i, h in enumerate(hs) if desde <= h[:10] < hasta]
        horas += [hs[i] for i in sel]
        ws += [a[i] for i in sel]
        wd += [b[i] for i in sel]
    ev = eventos_viento(horas, ws, wd)
    if ev is None:
        return None
    return {"serie": serie, "titulo": VM.titulos().get(serie, serie), "planta": {k: v for k, v in rp.items() if k != "dias"}, "eventos": ev,
            "periodo": periodo, "estaciones": _estaciones(emp, periodo),
            "era5": _era5(emp, horas, ws, wd) if periodo is None else None,
            "clima_comp": _clima_comparacion(emp, periodo) if periodo is not None else None,
            "_horas": {"horas": horas, "ws": ws, "wd": wd}}


def _penacho_instantes(periodo):
    """Los instantes del penacho que van al informe del episodio: el día de la queja (el del medio), cada 2 horas (12 fotos). Cada uno, con su
    número de fotograma (el índice de hora en la serie del penacho, que empieza en el día 0 a las 00:00 en hora oficial) y su hora."""
    central = dt.date.fromisoformat(periodo["ini"]) + dt.timedelta(days=periodo["dias"] // 2)
    base = 24 * (periodo["dias"] // 2)
    return {"dia": central.isoformat(),
            "instantes": [{"frame": base + h, "etiqueta": f"{h:02d}:00", "hora": f"{central.isoformat()} {h:02d}:00"}
                          for h in range(0, 24, 2)]}


def operacion(res, focos, periodo=None):
    """La emisión de olor con el plan del caso: en el último año del reanálisis o, con `periodo`, solo en los días del episodio/predicción. La
    de la planta cada día (en tanto por uno de la de todos los
    focos al 100 %; None fuera del plan, si es de un mes) y en el día medio, hora a hora; y la de cada foco: su semana tipo (la primera semana
    del plan), su media de cada mes y su media. `constante`: cada foco emite lo mismo todas las horas, sea lo que sea; `al_100`: además, todos
    al 100 %."""
    esc = res["esc"]
    if periodo is not None:                                     # episodio/predicción: el calendario es solo sus días (víspera/día/siguiente)
        anio = int(periodo["ini"][:4])
        mes = None
        dias = [dt.date.fromisoformat(periodo["ini"]) + dt.timedelta(days=k) for k in range(periodo["dias"])]
        en_plan = dias
    else:
        anio = int(res["datos"]["fin"][:4])
        mes = E.anio_mes(esc["mes"])[1] if esc.get("mes") and any(pf.get("plan") == "mensual" for pf in esc.get("focos", {}).values()) else None
        dias = [dt.date(anio, 1, 1) + dt.timedelta(days=k) for k in range((dt.date(anio + 1, 1, 1) - dt.date(anio, 1, 1)).days)]
        en_plan = [d for d in dias if mes is None or d.month == mes]
    q = {f["id"]: F.olor_ouE_s(f) or 0.0 for f in focos}
    Q = sum(q.values()) or 1.0
    salen, tipos = [], {}
    total_dia = {d: 0.0 for d in en_plan}
    horas = np.zeros(24)
    constante = al_100 = True
    for f in focos:
        pf = E.plan_foco(f, json.loads(json.dumps(esc)))
        tipos[pf["plan"]] = tipos.get(pf["plan"], 0) + 1
        perf = {d: np.asarray(E.perfil_dia(pf, E.indice_dia(pf, d)), float) for d in en_plan}
        valores = np.concatenate(list(perf.values()))
        fijo = bool(np.ptp(valores) == 0)
        constante &= fijo
        al_100 &= bool(np.all(valores == 1.0))
        for d, p in perf.items():
            total_dia[d] += q[f["id"]] * p.mean()
            horas += q[f["id"]] * p
        lunes = (next((d for d in en_plan if d.weekday() == 0), en_plan[0])) if mes is None else en_plan[0]
        semana = sorted(((lunes + dt.timedelta(days=k)) for k in range(7)), key=lambda d: d.weekday())
        semana = [(d.weekday(), [float(x) for x in perf.get(d, np.asarray(E.perfil_dia(pf, E.indice_dia(pf, d)), float))]) for d in semana]
        meses = {}
        for d, p in perf.items():
            meses.setdefault(d.month, []).append(float(p.mean()))
        salen.append({"id": f["id"], "nombre": f.get("nombre") or f["id"], "modelo": f.get("modelo"), "q": q[f["id"]], "plan": pf["plan"],
                      "media": float(np.mean([p.mean() for p in perf.values()])), "semana": semana, "constante": fijo,
                      "meses": {mm: float(np.mean(v)) for mm, v in meses.items()}})
    por_dia = [(d, total_dia[d] / Q if d in total_dia else None) for d in dias]
    horas = horas / (Q * len(en_plan))
    return {"anio": anio, "mes": mes, "dias": por_dia, "horas": [float(x) for x in horas], "q": Q, "constante": constante, "al_100": al_100,
            "media": float(np.mean([v for _, v in por_dia if v is not None])), "focos": salen, "tipos": tipos}


def reunir(caso, viento=True, escalas=None, meteo=None):
    """Lo que necesita el informe del caso de la carpeta `caso` (la del caso guardado o la de sus resultados). `viento`: con el viento más
    frecuente en la planta y la meteorología: las estaciones y las situaciones del mapa (la primera vez lee la serie: un minuto);
    `escalas`: {«olor», «gases»}, las de la configuración de la app; `meteo`: la meteorología ya reunida (la de otro escenario: es la misma)."""
    res = S.cargar_caso(caso)
    periodo = res.get("periodo")                                # None = reanálisis; dict = episodio (queja) o predicción
    tipo = "episodio" if periodo and periodo.get("modo") == "queja" else ("prediccion" if periodo else "reanalisis")
    if periodo is not None and "datos" not in res:              # el episodio no trae `datos`: lo sintetizo (sus fechas/horas) para reutilizar todo el writer
        _ini = dt.date.fromisoformat(periodo["ini"])
        res["datos"] = {"ini": periodo["ini"], "fin": (_ini + dt.timedelta(days=periodo["dias"] - 1)).isoformat(),
                        "dias": periodo["dias"], "horas": int(res.get("horas") or 24 * periodo["dias"]),
                        "huecos": [], "anios": {}, "incompletos": []}
    raiz = Path(res["carpeta"])
    avisos = []
    cat = _focos(raiz, avisos)
    emp = config.cargar_emplazamiento()
    k = "olor" if "olor" in res["magnitudes"] else res["orden"][0]
    m = res["magnitudes"][k]
    cols = m["columnas"]
    col_est = next((c for c in cols if c["capa"] == "norma"), next(c for c in cols if c["clave"] == "maximo"))
    est = col_est["clave"]
    with np.load(raiz / k / "resumen.npz") as z:
        x, y, clase = z["x"], z["y"], z["clase"]
        campos = {c["clave"]: z[c["clave"]] for c in cols if c["clave"] in z.files}
    lugares = _lugares(raiz)
    if lugares is None:
        from teodors.planta import geo
        avisos.append("Sin los lugares de los receptores: los pueblos son los de la tabla del resultado.")
        centro = list(geo.a_utm(emp["lat"], emp["lon"]))
        filas = m["filas"]
    else:
        lugares = S.lugares_al_dia(lugares, x, y)                # cada pueblo, con sus receptores (operacion.pueblos)
        centro = lugares["centro"]
        filas = S._tabla(lugares, x, y, clase, campos, cols, True)
    xc, yc = centro
    pueblos = sorted((f for f in filas if f.get("tipo") == "pueblo"), key=lambda f: -f[est])
    vivienda = next((f for f in filas if f.get("tipo") == "vivienda"), None)
    donde, industrias = {}, {}
    for et in (lugares or {}).get("etiquetas", []):
        if et.get("clase") != "nucleo":
            continue
        i = et["i"]
        dxy = (float(x[i] - xc), float(y[i] - yc))
        km = round(float(np.hypot(*dxy)) / 1000.0, 1)
        if et.get("familia") == "residencial" and (et["nombre"] not in donde or np.hypot(*dxy) < np.hypot(*donde[et["nombre"]])):
            donde[et["nombre"]] = dxy
        if et.get("familia") == "industrial":
            nombre = et.get("nombre") or "Zona industrial"
            fila = industrias.setdefault(nombre, {"nombre": nombre, "km": km, **{c: 0.0 for c in campos}})
            fila["km"] = min(fila["km"], km)
            for c, v in campos.items():
                fila[c] = max(fila[c], float(v[i]))
    industrias = sorted(industrias.values(), key=lambda f: -f[est])
    criterios, alcances = [], {}
    if k == "olor":
        rej = S._rejillas(x, y, centro)
        dx, dy = x - xc, y - yc
        dist = np.hypot(dx, dy) / 1000.0
        for u in C.CRITERIOS_OLOR:
            criterios.append(dict(_alcance(campos[est], rej, dist, dx, dy, u), pueblos=sum(f[est] > u for f in pueblos),
                                  pueblos_maximo=sum(f.get("maximo", 0.0) > u for f in pueblos)))      # en su peor hora (usuario, 2026-11-10)
        alcances = {c: [_alcance(v, rej, dist, dx, dy, u) for u in C.CRITERIOS_OLOR] for c, v in campos.items()}   # cada estadístico
    if meteo is None and viento:
        meteo = _meteo(emp, serie=res.get("serie"), periodo=periodo) if periodo else _meteo(emp)
    repetida = _repetida(res) if periodo is None else None          # lo de la «serie de prueba» es del reanálisis
    if repetida:
        avisos.append(f"La dispersión es la de una serie de prueba: {len(repetida['dias'])} días simulados, copiados de {repetida['desde']} a "
                      f"{repetida['hasta']}; los resultados se repiten de una semana a otra.")
    escalas = dict(estilo.ESCALAS_DEFECTO, **(escalas or {}))
    niveles = S.niveles_isolineas(m["ref"], k)
    d = {"res": res, "tipo": tipo, "periodo": periodo, "caso_dir": Path(res["caso"]["ruta"]), "raiz": raiz, "emp": emp,
         "planta": emp.get("nombre") or "Planta", "focos": cat,
         "mag": m, "estadistico": est, "estadistico_nombre": "P98" if est == "p98" else col_est["titulo"], "campos": campos,
         "n_receptores": int(len(x)), "centro": centro, "pueblos": pueblos, "vivienda": vivienda, "industrias": industrias, "donde": donde,
         "criterios": criterios, "alcances": alcances, "niveles": niveles, "bandas": estilo.bandas(niveles, escalas["olor" if k == "olor" else "gases"]),
         "escalas": escalas, "terreno": _terreno(emp), "edificios": _edificios(raiz), "viento": _viento() if viento else None,
         "meteo": meteo,
         "horas": (horas_pueblos(raiz, filas, meteo, repetida) if (k == "olor" and periodo is None)
                   else horas_pueblos_periodo(raiz, filas, lugares, clase, campos, est, periodo)
                   if (k == "olor" and tipo == "episodio" and lugares is not None) else None),
         "repetida": repetida,
         "operacion": operacion(res, cat["focos"], periodo), "avisos": avisos, "hoy": dt.date.today(),
         "penacho": _penacho_instantes(periodo) if tipo == "episodio" else None}
    if k == "olor" and d["horas"] is None and periodo is None:
        avisos.append("Este caso se calculó antes de guardar la hora a hora de los pueblos: para ver cuándo se huele en ellos, vuelve a calcularlo.")
    return d


# cuándo se huele en los pueblos (usuario, 2026-11-10: «horas al año por encima de 1, 3 y 5 ou_E/m³, por mes y por hora del día, y los peores
# días con su viento»), de la hora a hora del caso (`simulacion.HORAS_PUEBLOS`)
UMBRALES_HORAS = (1.0, 3.0, 5.0)
PEORES_DIAS = 6
CALOR_PUEBLOS = 3                           # los pueblos con su mes y hora del día


def _repetida(res):
    """Si la serie de respuestas del caso es de prueba (`serie_respuestas.repetir`: unas semanas simuladas, copiadas en todos los años), su
    «repetida» (los días simulados y el periodo); si no, o no se sabe, None."""
    try:
        carpeta = S.dir_respuestas()
        ind = SR.indice(carpeta) if carpeta else None
    except Exception:                                        # noqa: BLE001 (sin el índice, como si no lo fuera)
        return None
    if not ind or ind.get("serie") != res.get("serie"):
        return None
    return ind.get("repetida")


def horas_pueblos(raiz, filas, me=None, repetida=None):
    """Cuándo y cuánto se huele en cada pueblo y en la peor vivienda, de su hora a hora (lo peor de sus receptores en cada hora); None si el
    caso no la tiene (calculado antes de guardarla). `filas`: la tabla del olor (su km y su tipo); `me`: la meteorología (`_meteo`), para el
    viento en la planta y el aire (ERA5) de los peores días. Las horas, en hora oficial; «por año», entre los años de la serie.
    {"anios", "lugares": [{"nombre", "tipo", "km", "horas" (por año, por encima de cada UMBRALES_HORAS), "dias" (por año, con alguna hora
    por encima de 1), "peor": {"valor", "dia", "hora"}}], de más a menos horas por encima de 1; "calor": [{"nombre", "M" (12 × 24: horas por
    año por encima de 1 en cada mes y hora del día)}]; "todos": lo mismo para cualquier pueblo, con su «horas», su «noche» (% de ellas de
    20 a 8 h) y su «M»; "peores": [{"dia", "hora", "pueblo", "valor", "horas" (por encima de 1 ese día), "ws", "wd", "rumbo", "H", "blh",
    "origen"}]}. Con una serie de prueba (`repetida`), cada peor día, una sola vez por día simulado, con el viento y el aire del simulado del
    que se copió (el que dio ese olor: «origen», su fecha)."""
    import pandas as pd
    from teodors.operacion import viento_mapa as VM
    ruta = Path(raiz) / "olor" / S.HORAS_PUEBLOS
    if not ruta.is_file():
        return None
    with np.load(ruta) as z:
        horas, nombres, Cm = z["horas"], [str(n) for n in z["nombres"]], np.asarray(z["C"], float)
    t = pd.DatetimeIndex(horas.astype("datetime64[h]")).tz_localize("UTC").tz_convert(E.zona())
    anios = len(horas) / (365.25 * 24)
    fila = {f["nombre"]: f for f in filas}
    dia = np.array(t.date)
    mes, hora = np.asarray(t.month) - 1, np.asarray(t.hour)
    u0 = UMBRALES_HORAS[0]

    def calor(sel):
        M = np.zeros((12, 24))
        np.add.at(M, (mes[sel], hora[sel]), 1.0)
        return (M / anios).tolist()
    lugares = []
    for j, nombre in enumerate(nombres):
        c = Cm[:, j]
        k = int(np.argmax(c))
        tipo = fila.get(nombre, {}).get("tipo") or ("vivienda" if nombre.startswith("Peor vivienda") else "pueblo")
        lugares.append({"nombre": nombre, "tipo": tipo, "km": fila.get(nombre, {}).get("km"), "j": j,
                        "horas": [float((c > u).sum() / anios) for u in UMBRALES_HORAS], "dias": len(set(dia[c > u0])) / anios,
                        "peor": {"valor": float(c[k]), "dia": _fecha(t[k]), "hora": f"{t[k].hour}:00"}})
    lugares.sort(key=lambda f: (-f["horas"][0], -f["peor"]["valor"]))
    pueblos = [f for f in lugares if f["tipo"] == "pueblo"]
    salen = {"anios": anios, "lugares": lugares,
             "calor": [{"nombre": f["nombre"], "M": calor(Cm[:, f["j"]] > u0)} for f in pueblos[:CALOR_PUEBLOS] if f["horas"][0] > 0],
             "todos": None, "peores": []}
    if not pueblos:
        return salen
    jp = [f["j"] for f in pueblos]
    algun = (Cm[:, jp] > u0).any(axis=1)
    salen["todos"] = {"horas": float(algun.sum() / anios), "M": calor(algun),
                      "noche": float(100 * np.isin(hora[algun], NOCHE_LARGA).mean()) if algun.any() else 0.0}
    # los peores días: el más alto de cualquier pueblo, día a día, con el viento en la planta y el aire a esa hora
    Cp = Cm[:, jp]
    alto, quien = Cp.max(axis=1), Cp.argmax(axis=1)
    df = pd.DataFrame({"dia": dia, "alto": alto, "i": np.arange(len(t))})
    mejores = df.loc[df.groupby("dia")["alto"].idxmax()].sort_values("alto", ascending=False, kind="stable")
    origen = [pd.Timestamp(x) for x in repetida["dias"]] if repetida else None
    vistos = set()
    viento, aire = {}, {}
    if me and me.get("_horas"):
        h = me["_horas"]
        viento = {x: (float(a), float(b)) for x, a, b in zip(h["horas"], h["ws"], h["wd"])}
    if me and (me.get("era5") or {}).get("_sfc"):
        s = me["era5"]["_sfc"]
        aire = {x: (float(a), float(b)) for x, a, b in zip(s["horas"], s["H"], s["blh"])}
    for _, r in mejores.iterrows():
        if len(salen["peores"]) >= PEORES_DIAS or r["alto"] <= 0:
            break
        i = int(r["i"])
        j = jp[int(quien[i])]
        utc = pd.Timestamp(int(horas[i]), unit="h")
        de = None
        if origen:                                                  # una copia: el día simulado, una sola vez
            de = SR.dia_de_origen(utc.normalize(), origen)
            if de in vistos:
                continue
            vistos.add(de)
            utc = de + pd.Timedelta(hours=utc.hour)
        clave = utc.strftime("%Y-%m-%d %H")                         # la de la serie del viento y del ERA5: UTC
        ws, wd = viento.get(clave, (None, None))
        H, blh = aire.get(clave, (None, None))
        salen["peores"].append({"dia": _fecha(t[i]), "hora": f"{t[i].hour}:00", "pueblo": nombres[j], "valor": float(r["alto"]),
                                "horas": int(((dia == r["dia"]) & (Cm[:, j] > u0)).sum()), "ws": ws, "wd": wd,
                                "rumbo": VM.rumbo(wd) if wd is not None else None, "H": H, "blh": blh,
                                "origen": _fecha(utc.tz_localize("UTC").tz_convert(E.zona())) if de is not None else None})
    return salen


def horas_pueblos_periodo(raiz, filas, lugares, clase, campos, est, periodo):
    """Cuándo y cuánto se huele en cada pueblo y en la peor vivienda DURANTE el episodio, hora a hora, reconstruido desde
    `olor/penacho.npz` (el episodio no guarda la `horas_pueblos.npz` del reanálisis; el penacho es [hora, receptor], en hora
    oficial desde el día `ini` a las 00:00). Cuenta sobre las HORAS DEL EPISODIO (no «al año»). None si no hay penacho.
    {"ini", "dias", "n_horas", "pico": {«nombre», «valor», «dia», «hora», «ih»} (el mayor de todos), "alguno_supera" (si algún
    lugar pasa de 1 ou_E/m³), "tope" (el mayor ou_E/m³, color común de los mapas), "lugares": [{"nombre", "tipo", "km",
    "horas": [nº de horas > 1, > 3, > 5], "ndias" (días con alguna hora > 1), "pico": {«valor», «dia», «hora», «ih»},
    "M": [dias][24] (ou_E/m³ hora a hora, para el mapa de calor día × hora)}], de más a menos horas > 1 y luego pico;
    "calor": los CALOR_PUEBLOS pueblos con más pico, con su M}."""
    ruta = Path(raiz) / "olor" / "penacho.npz"
    if not ruta.is_file():
        return None
    with np.load(ruta) as z:
        Cpen = np.asarray(z["C"], float)                    # [hora, receptor], ou_E/m³, en hora oficial desde ini 00:00
    n_h = Cpen.shape[0]
    dias = max(n_h // 24, 1)
    ini = dt.date.fromisoformat(str(periodo["ini"]))
    u1 = UMBRALES_HORAS[0]
    fila = {f["nombre"]: f for f in filas}
    grupos = [(nombre, idx, "pueblo") for nombre, idx in S._grupos_pueblos(lugares)]
    clase = np.asarray(clase)
    viv = np.flatnonzero(clase == "vivienda")
    if len(viv) and est in campos:
        iv = int(viv[np.argmax(np.asarray(campos[est])[viv])])
        grupos.append((f"Peor vivienda (< {config.RADIO_EDIFICIOS_KM:g} km)", np.array([iv], dtype=np.int64), "vivienda"))
    lugares_s = []
    for nombre, idx, tipo in grupos:
        c = Cpen[:, idx].max(axis=1) if len(idx) else np.zeros(n_h)
        ih = int(np.argmax(c))
        M = [[float(c[d * 24 + h]) if d * 24 + h < n_h else float("nan") for h in range(24)] for d in range(dias)]
        ndias = len({i // 24 for i in range(n_h) if c[i] > u1})
        lugares_s.append({"nombre": nombre, "tipo": fila.get(nombre, {}).get("tipo") or tipo,
                          "km": fila.get(nombre, {}).get("km"),
                          "horas": [int((c > u).sum()) for u in UMBRALES_HORAS], "ndias": ndias,
                          "pico": {"valor": float(c[ih]), "dia": _fecha(ini + dt.timedelta(days=ih // 24)), "hora": f"{ih % 24}:00", "ih": ih},
                          "M": M})
    lugares_s.sort(key=lambda f: (-f["horas"][0], -f["pico"]["valor"]))
    peor = lugares_s[0] if lugares_s else None
    return {"ini": ini.isoformat(), "dias": dias, "n_horas": n_h,
            "pico": ({"nombre": peor["nombre"], **peor["pico"]} if peor else None),
            "alguno_supera": any(f["horas"][0] > 0 for f in lugares_s),
            "tope": max((f["pico"]["valor"] for f in lugares_s), default=0.0),
            "lugares": lugares_s, "calor": sorted(lugares_s, key=lambda f: -f["pico"]["valor"])[:CALOR_PUEBLOS]}


def _alcance(campo, rej, dist, dx, dy, u):
    """Hasta dónde pasa `campo` de `u`: su superficie (km²) y el receptor más lejos, a cuántos km y hacia dónde."""
    sel = campo > u
    c = {"umbral": u, "km2": float(C._superficie(campo, rej, u)), "hasta_km": None, "rumbo": None, "rumbo_grados": None}
    if sel.any():
        j = int(np.argmax(np.where(sel, dist, -1)))
        c.update(hasta_km=float(dist[j]), rumbo=_rumbo8(dx[j], dy[j]), rumbo_grados=float(np.degrees(np.arctan2(dx[j], dy[j])) % 360))
    return c


# ── el informe de la comparación de dos escenarios del reanálisis (usuario, 2026-11-10: «mantener la estructura del informe de las cosas en
# común (lugar, pueblos, focos, meteo) y comparar la operabilidad entre los dos casos, luego el informe de resultados individual de cada uno
# y por último una página comparativa entre los escenarios») ──
def _igual(x, y):
    """¿La misma operación de un foco en los dos? (su emisión al 100 %, su semana tipo y su media de cada mes)."""
    if x is None or y is None or abs(x["q"] - y["q"]) > 1e-9 * max(x["q"], 1.0) or x["plan"] != y["plan"]:
        return False
    sx, sy = [p for _, p in x["semana"]], [p for _, p in y["semana"]]
    return (len(sx) == len(sy) and all(np.allclose(p, q) for p, q in zip(sx, sy)) and set(x["meses"]) == set(y["meses"])
            and all(abs(x["meses"][k] - y["meses"][k]) < 1e-9 for k in x["meses"]))


def operacion_comparada(op_a, op_b):
    """La operación de los dos escenarios, foco a foco: {"focos": [{"id", "nombre", "modelo", "q", "a", "b" (su media con cada plan, en tanto
    por uno; None si no está), "plan_a", "plan_b", "igual", "fa", "fb" (lo de `operacion` de cada uno)}], de más a menos emisión al 100 %;
    "a", "b": {"q" (todos al 100 %), "media", "emite" (ou_E/s de media)}; "cambian": los ids de los que no operan igual}."""
    fa, fb = {f["id"]: f for f in op_a["focos"]}, {f["id"]: f for f in op_b["focos"]}
    ids = sorted(set(fa) | set(fb), key=lambda i: -(fa.get(i) or fb.get(i))["q"])
    focos = []
    for i in ids:
        x, y = fa.get(i), fb.get(i)
        u = x or y
        focos.append({"id": i, "nombre": u["nombre"], "modelo": u["modelo"], "q": u["q"], "a": x["media"] if x else None,
                      "b": y["media"] if y else None, "plan_a": x["plan"] if x else None, "plan_b": y["plan"] if y else None,
                      "igual": _igual(x, y), "fa": x, "fb": y})

    def total(op):
        return {"q": op["q"], "media": op["media"], "emite": sum(f["q"] * f["media"] for f in op["focos"])}
    return {"focos": focos, "a": total(op_a), "b": total(op_b), "cambian": [f["id"] for f in focos if not f["igual"]]}


def reunir_comparacion(caso_a, caso_b, viento=True, escalas=None, salida=None):
    """Lo que necesita el informe de la comparación de dos escenarios del reanálisis: los de `reunir` de cada uno («a», la referencia, y «b»,
    con la misma meteorología: la de la planta), su operación foco a foco (`operacion_comparada`) y el cambio de cada receptor y de cada
    pueblo (`comparacion.comparar`, con sus isolíneas en `salida`). Si no se pueden comparar (otras horas u otros receptores), ValueError."""
    a = reunir(caso_a, viento=viento, escalas=escalas)
    b = reunir(caso_b, viento=False, escalas=escalas, meteo=a["meteo"])
    comp = C.comparar(a["raiz"], b["raiz"], salida=salida or Path(config.LOCAL) / "informes" / "comparacion_cambio")
    receptores = None
    est = a["estadistico"]
    if est in a["campos"] and est in b["campos"]:
        umbral = S.niveles_isolineas(a["mag"]["ref"], a["mag"]["clave"])[0]
        pct = C.cambio(a["campos"][est], b["campos"][est], umbral)
        ok = pct[np.isfinite(pct)]
        if ok.size:                                          # los receptores con olor en alguno de los dos: cuántos bajan, suben o igual
            receptores = {"n": int(ok.size), "bajan": float(100 * (ok < -10).mean()), "suben": float(100 * (ok > 10).mean()),
                          "igual": float(100 * (np.abs(ok) <= 10).mean()), "mediana": float(np.median(ok)), "umbral": umbral}
    return {"a": a, "b": b, "comp": comp, "op": operacion_comparada(a["operacion"], b["operacion"]), "receptores": receptores,
            "avisos": list(comp["avisos"]), "hoy": dt.date.today()}


def _rumbo8(dx, dy):
    from teodors.writer.textos import rumbo8
    return rumbo8(dx, dy)
