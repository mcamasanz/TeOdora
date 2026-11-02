# -*- coding: utf-8 -*-
"""Del plan (`operacion.planes`) y las respuestas de los focos (`operacion.respuestas`) a lo que dice `operacion.normativa` en cada receptor, sin lanzar el motor.

Dos cálculos, según la opción de Meteorología (`operacion.periodos`): `calcular`, los años del reanálisis, y
`calcular_periodo`, un día de ellos, un episodio o una predicción, que además dan el penacho hora a hora.

    C(t, r) = Σ_foco Q_foco Σ_h  R_foco[h, H(t), r] · F_foco(te),   te = última vez que fue la hora h
    con Q = emisión de referencia y F = parte del tiempo si es por eventos × plan.

Lo mismo para cada MAGNITUD (focos.magnitudes): el olor (Q en ou_E/s) y cada gas (Q en µg/s). Solo cambia Q, así que el
producto de F por R se hace una vez y sirve para todas.

⚠️ Mientras no haya una serie de varios años, `calcular` repite UN día de viento en todos: sirve para probar la herramienta, no da
resultados: el penacho va siempre a los mismos sitios y lo demás sale a cero. Con la serie, R dejará de ser periódica; las cuentas son las mismas.

El P98 sale de la serie horaria y sobre horas válidas. Se recorre por bloques de receptores, cada uno con su serie completa en memoria.
"""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import Delaunay

from teodors import planta as config
from teodors.casos import receptores as receptores_mapa
from teodors.comun import registro
from teodors.operacion import focos as F, normativa, penacho_mapa, periodos, planes as E

log = registro.get("planes")

BLOQUE = 500                                               # receptores a la vez
# Escala de color FIJA en ou_E/m³: con «máximo / 10» los valores junto a los focos, dentro de la planta,
# cambiarían todo el mapa
VMIN, DECADAS = 0.1, 4
VMAX = VMIN * 10 ** DECADAS
ESTADISTICAS = (("media", "Media", "media"), ("maximo", "Máximo", "máximo"), ("p98", "P98", "P98"))     # las del olor en 5 años
CAPAS = ("media", "maximo", "norma")                       # capas de cada resultado: <prefijo>_<capa>
FORMATO_RESULTADO = 1                                      # al cambiar lo que se guarda: lo anterior no vale
CERCA_M, PASO_CERCA_M, PASO_ZONA_M = 3000.0, 10.0, 100.0   # imágenes: la zona cercana con más detalle


def horas_reanalisis():
    """Fin de la 1.ª y de la última hora (UTC) de los años del reanálisis de la planta: años completos."""
    anios = config.REANALISIS_ANIOS
    return f"{anios[0]}-01-01 01:00", f"{anios[-1] + 1}-01-01 00:00"


def dir_respuestas():
    """Carpeta de las respuestas de reanálisis más recientes; None si aún no hay. ⚠️ Prueba: un día que se repite 5 años."""
    base = config.DATOS / "respuestas"
    metas = sorted((m for m in (base.glob("*/meta.json") if base.is_dir() else []) if not m.parent.name.startswith(periodos.PREFIJOS)),
                   key=lambda p: p.stat().st_mtime)
    return metas[-1].parent if metas else None


def disponible():
    return dir_respuestas() is not None


def carpeta_resultados(esc, periodo=None):
    """Carpeta del plan en ese periodo (5 años si no se da), con una subcarpeta por magnitud (olor, H2S…) y resultado.json."""
    plan = E.fichero(esc.get("nombre") or E.BASE).replace(".json", "")
    tramo = (config.DATOS / "resultados_planes" / "reanalisis" / "5_anios" if periodo is None else
             config.DATOS / "resultados_planes" / periodo["modo"] / f"{pd.Timestamp(periodo['ini']):%Y%m%d}_{periodo['dias']}d")
    return tramo / plan


def firma(esc, catalogo, periodo=None):
    """Huella de lo que decide el resultado: si cambia algo, lo guardado no vale."""
    texto = json.dumps({"formato": FORMATO_RESULTADO, "periodo": periodo, "focos": catalogo["focos"], "mes": esc.get("mes"),
                        "planes": {f["id"]: E.plan_foco(f, esc) for f in catalogo["focos"]},
                        "normativa": normativa.datos()["gases"]}, sort_keys=True, default=str)
    return hashlib.sha1(texto.encode()).hexdigest()


def guardado(esc, catalogo, periodo=None):
    """El resultado guardado si sigue valiendo, con sus imágenes; si no, None."""
    ruta = carpeta_resultados(esc, periodo) / "resultado.json"
    if not ruta.is_file():
        return None
    try:
        res = json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if res.get("firma") != firma(esc, catalogo, periodo):
        return None
    urls = [i["url"] for m in res["magnitudes"].values() for c in m["capas"] for i in c["imagenes"]]
    return res if all(Path(url_a_ruta(u)).is_file() for u in urls) else None


def url_a_ruta(url):
    from urllib.parse import unquote, urlparse
    return unquote(urlparse(url).path).lstrip("/")


def _focos_calculables(esc, catalogo, meta, fines):
    """{id: F(t), plan × parte del tiempo si es por eventos} de los focos que se pueden calcular, y {id: motivo} de
    los demás."""
    factores, fuera = {}, {}
    inicios = fines - pd.Timedelta(hours=1)                # el periodo con fin T emite de T − 1 h a T
    for f in catalogo["focos"]:
        duty, calc = F.fraccion_eventos(f), meta["focos"].get(f["id"])
        if duty is None:
            fuera[f["id"]] = "sin frecuencia o duración de sus eventos"
        elif calc is None:
            fuera[f["id"]] = "sin respuesta calculada"
        elif calc["huella"] != F.huella(f):
            fuera[f["id"]] = "ha cambiado desde que se calculó su respuesta"
        else:
            factores[f["id"]] = E.factores(E.plan_foco(f, esc), inicios) * duty
    return factores, fuera


def _emisiones(catalogo, fuera):
    """{clave: magnitud con «emisiones» {id: Q} y «fuera» [textos]} de lo que se puede calcular. Un foco que no emite un
    gas no aporta y no se avisa; sin olor, sí: en el mapa de olor no se debe dar por cero sin decirlo."""
    salen = {}
    for m in F.magnitudes(catalogo):
        q, sin, estimados = {}, [], []
        for f in catalogo["focos"]:
            nombre, e = f.get("nombre") or f["id"], F.emision(f, m["clave"])
            if e is None:
                if m["clave"] == "olor":
                    sin.append(f"{nombre}: sin emisión de olor")
            elif f["id"] in fuera:
                sin.append(f"{nombre}: {fuera[f['id']]}")
            else:
                q[f["id"]] = e
                if m["clave"] == "olor" and F.olor_medido(f) is None:   # sin olfatometría: Nagata, no ou_E medidas
                    gas = F.gas_dominante(f)[1]
                    estimados.append(f"{nombre} ({F.NOMBRES.get(gas, gas)})")
        if q:
            salen[m["clave"]] = dict(m, emisiones=q, fuera=sin, estimados=estimados)
    return salen


def _preparar_foco(carpeta, id_foco, e, tes):
    """Para cada índice k de R: (horas t, filas de R no nulas, pesos: e es F(t)). Solo las especies con algo en esa hora:
    lo emitido hace muchas horas ya ha salido del dominio."""
    with np.load(carpeta / f"R_{id_foco}.npz") as z:
        R = z["R"]
    partes = []
    for k, (t, te) in tes.items():
        hs = np.flatnonzero(R[:, k].max(axis=1) > 0)
        if not len(hs):
            continue
        ind = te[:, hs]
        W = np.where(ind >= 0, e[np.maximum(ind, 0)], 0.0).astype(np.float32)
        partes.append((t, R[hs, k], W))
    return partes


def _tiempos(hora, k_resp=None):
    """Para cada índice k de R (en un día que se repite, la hora H del fin; en un periodo, su hora, y < 0 si no tiene): (periodos
    t, te[t, h]). El factor h se aplica en el periodo cuyo fin tiene hora h + 1 (`teodors`: hora_reloj); te < 0: aún no había emisión."""
    k_resp = hora if k_resp is None else k_resp
    out = {}
    for k in np.unique(k_resp[k_resp >= 0]):
        t = np.flatnonzero(k_resp == k)
        out[int(k)] = (t, t[:, None] - ((hora[t[0]] - (np.arange(24) + 1)) % 24)[None, :])
    return out


def _series(partes, r0, r1, n, emisiones):
    """{clave: C(t, r)} de un bloque de receptores (n horas × receptores), en ou_E/m³ o µg/m³. partes: {id: _preparar_foco};
    emisiones: {clave: {id: Q}}."""
    C = {k: np.zeros((n, r1 - r0), np.float32) for k in emisiones}
    for id_foco, foco in partes.items():
        usa = [(C[k], q[id_foco]) for k, q in emisiones.items() if id_foco in q]
        for t, R, W in foco:
            b = R[:, r0:r1]
            if b.any():
                x = W @ b
                for c, q in usa:
                    c[t] += q * x
    return C


def calcular(esc, catalogo, progreso=None, cancelado=None):
    """Los años del reanálisis con el plan, en todas sus magnitudes, y guarda el resultado. Devuelve lo que necesita la interfaz."""
    t0 = time.time()
    avisa = progreso or (lambda *_: None)
    carpeta = dir_respuestas()
    if carpeta is None:
        raise RuntimeError("Aún no hay respuestas de los focos (operacion.respuestas).")
    meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
    with np.load(carpeta / "receptores.npz") as z:
        x, y, clase = z["x"], z["y"], z["clase"]
    fines = pd.date_range(*horas_reanalisis(), freq="h")
    hora = np.asarray(fines.hour)
    mascara = E.horas_del_plan(esc, fines)
    mascara[:24] = False                                   # el primer día aún no ha llegado todo
    i_horas = np.flatnonzero(mascara)
    horas = (slice(i_horas[0], i_horas[-1] + 1)            # sin copiar la serie si son horas seguidas
             if len(i_horas) and i_horas[-1] - i_horas[0] + 1 == len(i_horas) else mascara)
    factores, fuera = _focos_calculables(esc, catalogo, meta, fines)
    mags = _emisiones(catalogo, fuera)
    if not mags:
        raise RuntimeError("Ningún foco se puede calcular:\n" + "\n".join(
            f"{f.get('nombre') or f['id']}: {fuera.get(f['id'], 'sin emisión de olor ni de gases')}"
            for f in catalogo["focos"]))
    emisiones = {k: m["emisiones"] for k, m in mags.items()}
    usados = sorted({i for q in emisiones.values() for i in q})
    tes = _tiempos(hora)
    partes = {}
    for k, i in enumerate(usados):
        avisa(int(15 * k / len(usados)), f"Preparando {i}…")
        if factores[i].any():                              # un foco apagado no aporta nada
            partes[i] = _preparar_foco(carpeta, i, factores[i], tes)
    n, nrec = len(fines), len(x)
    cols = {k: normativa.columnas(k, "anios") for k in mags}
    fines_h = fines[horas]
    campos = {k: {c["clave"]: np.zeros(nrec) for c in cols[k]} for k in mags}
    for r0 in range(0, nrec, BLOQUE):
        if cancelado and cancelado():
            raise RuntimeError("Cálculo cancelado.")
        r1 = min(r0 + BLOQUE, nrec)
        for k, C in _series(partes, r0, r1, n, emisiones).items():
            C = C[horas]
            for col in cols[k]:
                campos[k][col["clave"]][r0:r1] = normativa.estadistico(col, C, fines_h)
        avisa(15 + int(65 * r1 / nrec), f"Receptores: {r1} de {nrec}")
    seg_serie = time.time() - t0
    raiz = carpeta_resultados(esc)
    del partes
    raiz = carpeta_resultados(esc)
    for k in mags:
        (raiz / k).mkdir(parents=True, exist_ok=True)
        np.savez_compressed(raiz / k / "resumen.npz", x=x, y=y, clase=clase, **campos[k])
    rejillas = _rejillas(x, y, meta["centro"])
    capas = {k: _capas(campos[k], cols[k], rejillas, raiz / k, avisa, m, 80 + 20 * j // len(mags), "plan")
             for j, (k, m) in enumerate(mags.items())}
    magnitudes = {k: _magnitud(m, factores, cols[k], capas[k], campos[k], _tabla(meta, x, y, clase, campos[k], cols[k]), None, [])
                  for k, m in mags.items()}
    res = {"formato": FORMATO_RESULTADO, "firma": firma(esc, catalogo), "nombre": esc.get("nombre"), "fecha": time.strftime("%Y-%m-%d %H:%M"),
           "esc": esc, "periodo": None, "largo": "anios", "serie": meta["serie"], "horas": int(mascara.sum()), "orden": list(mags), "magnitudes": magnitudes,
           "segundos": round(time.time() - t0, 1), "segundos_serie": round(seg_serie, 1)}
    (raiz / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    avisa(100, "Hecho")
    log.info(f"Plan «{res['nombre']}» calculado en {res['segundos']:.0f} s: {len(usados)} focos, {len(mags)} magnitudes, "
             f"{res['horas']} horas, {nrec} receptores.")
    return res


def _magnitud(m, factores, cols, capas, campos, filas, penacho, horas_txt):
    salen = {c: m[c] for c in ("clave", "nombre", "unidad", "escala", "ref", "emisiones")}
    salen.update(focos=sum(1 for i in m["emisiones"] if factores[i].any()), fuera=m["fuera"], estimados=m["estimados"], columnas=cols,
                 capas=capas, penacho=penacho, horas_txt=horas_txt, maximos={c: float(v.max()) for c, v in campos.items()}, filas=filas)
    return salen


def calcular_periodo(esc, catalogo, periodo, progreso=None, cancelado=None):
    """Un día del reanálisis, un episodio o una predicción: sus estadísticos y el penacho hora a hora, etiquetado por el FIN de la
    hora como el viento. Las 23 horas de antes son la emisión que aún sigue en el aire a las 00 (te en `_tiempos`)."""
    t0 = time.time()
    avisa = progreso or (lambda *_: None)
    carpeta = periodos.dir_respuestas(periodo)
    if not (carpeta / "meta.json").is_file():
        raise RuntimeError(f"Falta preparar el viento de {periodos.etiqueta(periodo)}.")
    meta = json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
    with np.load(carpeta / "receptores.npz") as z:
        x, y, clase = z["x"], z["y"], z["clase"]
    ini, n = pd.Timestamp(periodo["ini"]), periodo["dias"]
    fines = pd.date_range(ini - pd.Timedelta(hours=23), ini + pd.Timedelta(hours=24 * n - 1), freq="h")
    hora = np.asarray(fines.hour)
    tes = _tiempos(hora, np.arange(len(fines)) - 23)
    factores, fuera = _focos_calculables(esc, catalogo, meta, fines)
    mags = _emisiones(catalogo, fuera)
    if not mags:
        raise RuntimeError("Ningún foco se puede calcular:\n" + "\n".join(
            f"{f.get('nombre') or f['id']}: {fuera.get(f['id'], 'sin emisión de olor ni de gases')}" for f in catalogo["focos"]))
    emisiones = {k: m["emisiones"] for k, m in mags.items()}
    avisa(2, "Sumando las respuestas…")
    partes = {i: _preparar_foco(carpeta, i, factores[i], tes) for i in sorted({i for q in emisiones.values() for i in q}) if factores[i].any()}
    nrec = len(x)
    series = _series(partes, 0, nrec, len(fines), emisiones)
    del partes
    fines_r = fines[23:]
    locales = fines_r.tz_localize("UTC").tz_convert(E.zona())
    horas_txt = [f"{h:%H:%M}" if n == 1 else f"{h:%d/%m %H:%M}" for h in locales]
    raiz = carpeta_resultados(esc, periodo)
    rejillas = _rejillas(x, y, meta["centro"])
    magnitudes = {}
    for j, (k, m) in enumerate(mags.items()):
        C = series[k][23:]
        cols = normativa.columnas(k, "dias")
        campos = {c["clave"]: normativa.estadistico(c, C, fines_r) for c in cols}
        (raiz / k).mkdir(parents=True, exist_ok=True)
        np.savez_compressed(raiz / k / "resumen.npz", x=x, y=y, clase=clase, **campos)
        np.savez_compressed(raiz / k / "penacho.npz", C=C)
        base = 10 + 90 * j // len(mags)
        capas = _capas(campos, cols, rejillas, raiz / k, avisa, m, base, "dia")
        frames, limites = [], None
        for t in range(len(C)):
            if cancelado and cancelado():
                raise RuntimeError("Cálculo cancelado.")
            if t % 6 == 0:
                avisa(base + 90 * t // (len(C) * len(mags)), f"{m['nombre']}: penacho, hora {t + 1} de {len(C)}")
            imagenes = _imagenes(C[t], rejillas, raiz / k / f"penacho_{t:03d}", m["ref"])
            frames.append([i["url"] for i in imagenes])
            limites = [i["limites"] for i in imagenes]
        penacho = {"dia": periodo["ini"], "dias": n, "frames": frames, "limites": limites, "leyenda": _leyenda("penacho", m)}
        magnitudes[k] = _magnitud(m, factores, cols, capas, campos, _tabla(meta, x, y, clase, campos, cols), penacho, horas_txt)
    res = {"formato": FORMATO_RESULTADO, "firma": firma(esc, catalogo, periodo), "nombre": esc.get("nombre"), "fecha": time.strftime("%Y-%m-%d %H:%M"),
           "esc": esc, "periodo": periodo, "largo": "dias", "serie": meta["serie"], "horas": 24 * n, "orden": list(mags), "magnitudes": magnitudes,
           "segundos": round(time.time() - t0, 1)}
    (raiz / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    avisa(100, "Hecho")
    log.info(f"Plan «{res['nombre']}», {periodos.MODOS[periodo['modo']]} {periodos.etiqueta(periodo)}: {res['segundos']:.0f} s, {len(mags)} magnitudes.")
    return res


def _rejillas(x, y, centro):
    """Rejillas de las imágenes: la zona cercana con detalle y el resto con un hueco para no solaparse. Cada una
    con la interpolación lineal en los receptores ya preparada: solo cambian los valores (24 horas, 3 capas)."""
    tri = Delaunay(np.c_[x, y])
    xc, yc = centro
    rejillas = []
    for r, paso in ((CERCA_M, PASO_CERCA_M), (config.RADIO_CALCULO_KM * 1000.0, PASO_ZONA_M)):
        k = np.arange(-int(r / paso), int(r / paso) + 1) * paso
        X, Y = np.meshgrid(xc + k, yc + k)
        pts = np.c_[X.ravel(), Y.ravel()]
        s = tri.find_simplex(pts)
        T = tri.transform[s]
        b = np.einsum("ijk,ik->ij", T[:, :2], pts - T[:, 2])
        rejillas.append({"x": xc + k, "y": yc + k, "paso": paso, "forma": X.shape, "fuera": s < 0,
                         "vertices": tri.simplices[s], "pesos": np.c_[b, 1.0 - b.sum(axis=1)],
                         "hueco": None if r == CERCA_M else ((np.abs(X - xc) < CERCA_M) & (np.abs(Y - yc) < CERCA_M)).ravel()})
    return rejillas


def _imagenes(campo, rejillas, ruta, ref=1.0):
    """Una imagen por rejilla de un campo en los receptores, interpolando en logaritmos: la concentración cae
    órdenes de magnitud entre receptores. La escala va de VMIN a VMAX veces `ref`. Fichero <ruta>_<rejilla>.png."""
    log_c = np.log10(np.maximum(campo, VMIN * ref / 100.0))
    imagenes = []
    for z, r in enumerate(rejillas):
        v = 10.0 ** (log_c[r["vertices"]] * r["pesos"]).sum(axis=1)
        v[r["fuera"]] = 0.0
        if r["hueco"] is not None:
            v[r["hueco"]] = 0.0
        destino = ruta.with_name(f"{ruta.name}_{z}.png")
        lim = penacho_mapa.pintar(v.reshape(r["forma"]), r["x"], r["y"], r["paso"], VMIN * ref, VMAX * ref, destino,
                                  decadas=DECADAS, suavizado=1, max_px=1300, escala=None)
        imagenes.append({"url": destino.as_uri() + f"?v={int(destino.stat().st_mtime)}", "limites": lim})
    return imagenes


def _leyenda(titulo, m):
    return penacho_mapa.leyenda_html({"vmin": VMIN * m["ref"], "decadas": DECADAS, "unidad": m["unidad"],
                                      "escala": m["escala"]}, f"{m['nombre']} · {titulo}")


def _capas(campos, cols, rejillas, salida, avisa, m, avance, prefijo):
    """Las capas del mapa de una magnitud: media, máximo y, si lo tiene, el percentil o el estadístico de su límite."""
    capas = []
    for col in cols:
        if col["capa"]:
            avisa(avance, f"{m['nombre']}: imagen de «{col['nombre']}»…")
            capas.append({"id": f"{prefijo}_{col['capa']}", "nombre": col["nombre"], "titulo": col["titulo"],
                          "imagenes": _imagenes(campos[col["clave"]], rejillas, salida / col["clave"], m["ref"]),
                          "leyenda": _leyenda(col["nombre"], m), "escala": m["escala"]})
    return capas


def datos_penacho(res, clave):
    """Lo que necesita la capa del penacho de una magnitud: sus imágenes y, si está, el tiempo en la planta ese día."""
    m = res["magnitudes"][clave]
    p = m["penacho"]
    return dict(p, nombre="Penacho", opacidad=penacho_mapa.OPACIDAD, grupo=penacho_mapa.GRUPO, escala=m["escala"],
                **penacho_mapa.tiempo_dia(p["dia"], res["serie"], p["dias"]))


def valores(res, clave):
    """{(x, y): {columna: valor}} de una magnitud del resultado `res`, por receptor (x, y redondeados a 0,1 m)."""
    with np.load(carpeta_resultados({"nombre": res["nombre"]}, res.get("periodo")) / clave / "resumen.npz") as z:
        x, y = z["x"], z["y"]
        c = {k: z[k] for k in z.files if k not in ("x", "y", "clase")}
    return {(round(float(a), 1), round(float(b), 1)): {k: float(v[i]) for k, v in c.items()}
            for i, (a, b) in enumerate(zip(x, y))}


def texto_celda(col, v, m):
    """Lo que se lee en una celda de la tabla: concentración, número de horas u hora oficial."""
    if col["tipo"] == "hora":
        return m["horas_txt"][int(v)] if v >= 0 else "—"
    return f"{v:.0f}" if col["tipo"] == "horas" else cifra(v)


def supera(col, v):
    """¿Pasa de su límite? Las horas por encima cuentan como tal en cuanto hay alguna."""
    if col.get("limite") is None:
        return False
    return v > 0 if col["tipo"] == "horas" else v > col["limite"]


def tabla_punto(v, titulo, m):
    """Tabla HTML (para el tooltip de un lugar del mapa) con los valores de una magnitud."""
    td = "style='padding:1px 7px;text-align:right'"
    cols = m["columnas"]
    return (f"<table style='margin-top:4px;border-collapse:collapse;font-size:11px'>"
            f"<tr><td colspan='{len(cols)}' style='font-weight:600;padding-bottom:2px'>{titulo} · {m['nombre']} ({m['unidad']})</td></tr>"
            "<tr style='color:var(--tenue)'>" + "".join(f"<td {td}>{c['titulo']}</td>" for c in cols) + "</tr>"
            "<tr>" + "".join(f"<td {td}>{texto_celda(c, v[c['clave']], m)}</td>" for c in cols) + "</tr></table>")


def cifra(v):
    """Concentración con dos cifras significativas y coma decimal; lo muy pequeño, sin más detalle."""
    if v <= 0:
        return "0"
    if v < 0.01:
        return "< 0,01"
    dec = max(0, 1 - int(np.floor(np.log10(v))))
    return f"{v:.{dec}f}".replace(".", ",")


def _tabla(meta, x, y, clase, campos, cols):
    """Lugares con nombre: los receptores con nombre (salvo los marcados `"en_tabla": false`), la peor vivienda (por el estadístico de
    su capa o, si no tiene, por el máximo) y los núcleos urbanos cercanos."""
    xc, yc = meta["centro"]

    def fila(nombre, i):
        return {"nombre": nombre, "km": round(float(np.hypot(x[i] - xc, y[i] - yc)) / 1000.0, 1),
                **{c: float(v[i]) for c, v in campos.items()}}
    en_tabla = {r["nombre"] for r in receptores_mapa.con_nombre() if r.get("en_tabla", True)}
    filas = [fila(e["nombre"], e["i"]) for e in meta["etiquetas"]
             if e["clase"] == "nombrado" and e["nombre"] in en_tabla]
    viv = np.flatnonzero(clase == "vivienda")
    if len(viv):
        peor = next((c["clave"] for c in cols if c["capa"] == "norma"), "maximo")
        filas.append(fila(f"Peor vivienda (< {config.RADIO_EDIFICIOS_KM:g} km)", viv[np.argmax(campos[peor][viv])]))
    nucleos = [fila(e["nombre"], e["i"]) for e in meta["etiquetas"]
               if e["clase"] == "nucleo" and e.get("familia") == "residencial"]
    return filas + sorted(nucleos, key=lambda f: f["km"])[:10]
