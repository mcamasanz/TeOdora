# -*- coding: utf-8 -*-
"""Del plan (`operacion.planes`) y las respuestas de los focos (`operacion.respuestas`) a lo que dice `operacion.normativa` en cada receptor, sin lanzar el motor.

Dos cálculos, según la opción de Meteorología (`operacion.periodos`): `calcular`, los años del reanálisis, y
`calcular_periodo`, un día de ellos, un episodio o una predicción, que además dan el penacho hora a hora.

    C(t, r) = Σ_foco Q_foco Σ_h  R_foco[h, H(t), r] · F_foco(te),   te = última vez que fue la hora h
    con Q = emisión de referencia y F = parte del tiempo si es por eventos × plan.

Lo mismo para cada MAGNITUD (focos.magnitudes): el olor (Q en ou_E/s) y cada gas (Q en µg/s). Solo cambia Q, así que el
producto de F por R se hace una vez y sirve para todas.

El reanálisis (`calcular`) lee las respuestas de CADA día de la serie (`serie_respuestas`, en `planta.DIR_DISPERSION`): su periodo es
el de los días que hay, de todos los focos que entran, sin contar con años completos y con huecos si los hay; al añadir días (otro
año) se amplía solo. La media, el máximo y el P98 salen de las horas simuladas (las del plan, si es de un mes); la norma de los
gases, por año civil con las horas simuladas de cada año (`normativa`). Se recorre día a día, guardando C(t, r) en un fichero
temporal por bloques de receptores, y los estadísticos salen después bloque a bloque, cada uno con su serie entera.
"""
import datetime as dt
import hashlib
import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import Delaunay

from teodors import planta as config
from teodors.casos import receptores as receptores_mapa
from teodors.comun import registro
from teodors.operacion import focos as F, normativa, penacho_mapa, periodos, planes as E, pueblos as P, serie_respuestas as SR

log = registro.get("planes")

BLOQUE = 500                                               # receptores a la vez
# Escala de color FIJA en ou_E/m³: con «máximo / 10» los valores junto a los focos, dentro de la planta,
# cambiarían todo el mapa
VMIN, DECADAS = 0.01, 5              # el degradado, de 0,01 a 1000 veces `ref` (usuario, 2026-11-10: «solo llega hasta 0,1: a 0,01»)
VMAX = VMIN * 10 ** DECADAS
ESTADISTICAS = (("media", "Media", "media"), ("maximo", "Máximo", "máximo"), ("p98", "P98", "P98"))     # las del olor en 5 años
CAPAS = ("media", "maximo", "norma")                       # capas de cada resultado: <prefijo>_<capa>
# la hora a hora del olor en cada pueblo (lo peor de sus receptores en cada hora) y en la peor vivienda, en un caso del reanálisis (usuario,
# 2026-11-10: para el informe, cuándo y cuánto se huele en cada pueblo): olor/horas_pueblos.npz. Sin él (lo calculado antes), lo demás vale igual
HORAS_PUEBLOS = "horas_pueblos.npz"
FORMATO_RESULTADO = 3                                      # al cambiar lo que se guarda: lo anterior no vale (2: con isolíneas; 3: todos los pueblos)
CERCA_M, PASO_CERCA_M, PASO_ZONA_M = 3000.0, 10.0, 100.0   # imágenes: la zona cercana con más detalle


def dir_respuestas():
    """La carpeta de las respuestas de la serie del reanálisis (`serie_respuestas`, `planta.DIR_DISPERSION`); None si aún no hay."""
    d = config.DIR_DISPERSION
    return d if (d / SR.INDICE).is_file() else None


def disponible():
    return dir_respuestas() is not None


def _horas(dias):
    """Fin de cada hora (UTC) de esos días, como las respuestas: de las 00 a las 23 de cada uno."""
    return pd.DatetimeIndex(dias).repeat(24) + pd.to_timedelta(np.tile(np.arange(24), len(dias)), unit="h")


def _cobertura(dias, fines=None):
    """{"ini", "fin", "dias", "horas", "huecos" (días que faltan entre los dos), "anios" {año: horas simuladas}, "incompletos"
    [años con menos horas que el año civil]} de unos días; `fines`, las horas que cuentan (por defecto, todas las de los días)."""
    fines = _horas(dias) if fines is None else fines
    anios = pd.Series(1, index=fines).groupby(fines.year).size()
    completos = {a: (pd.Timestamp(a + 1, 1, 1) - pd.Timestamp(a, 1, 1)).days * 24 for a in anios.index}
    return {"ini": f"{dias[0]:%Y-%m-%d}", "fin": f"{dias[-1]:%Y-%m-%d}", "dias": len(dias), "horas": int(len(fines)),
            "huecos": int((dias[-1] - dias[0]).days + 1 - len(dias)), "anios": {int(a): int(n) for a, n in anios.items()},
            "incompletos": [int(a) for a, n in anios.items() if n < completos[a]]}


def periodo_reanalisis(focos=None):
    """El periodo del reanálisis: los días con respuesta de todos esos focos (de todos, si no se dan), en `_cobertura`; None si no hay."""
    carpeta = dir_respuestas()
    if carpeta is None:
        return None
    dias = SR.dias(SR.indice(carpeta), focos)
    return _cobertura(dias) if dias else None


def carpeta_resultados(esc, periodo=None):
    """Carpeta del plan en ese periodo (5 años si no se da), con una subcarpeta por magnitud (olor, H2S…) y resultado.json."""
    plan = E.fichero(esc.get("nombre") or E.BASE).replace(".json", "")
    tramo = (config.DATOS / "resultados_planes" / "reanalisis" / "5_anios" if periodo is None else
             config.DATOS / "resultados_planes" / periodo["modo"] / f"{pd.Timestamp(periodo['ini']):%Y%m%d}_{periodo['dias']}d")
    return tramo / plan


def firma(esc, catalogo, periodo=None):
    """Huella de lo que decide el resultado: si cambia algo, lo guardado no vale. En el reanálisis, también los días con respuesta
    de cada foco: al añadir días, hay que volver a calcular."""
    carpeta = dir_respuestas() if periodo is None else None
    que = {"formato": FORMATO_RESULTADO, "periodo": periodo, "focos": catalogo["focos"], "mes": esc.get("mes"),
           "planes": {f["id"]: E.plan_foco(f, esc) for f in catalogo["focos"]}, "normativa": normativa.datos()["gases"]}
    if carpeta is not None:
        que["datos"] = SR.indice(carpeta)["focos"]
    texto = json.dumps(que, sort_keys=True, default=str)
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
    if res.get("firma") != firma(esc, catalogo, periodo) or not _completo(res):
        return None
    _isolineas_al_dia(res, ruta.parent, periodo)
    _imagenes_al_dia(res, ruta.parent, periodo)
    pueblos_al_dia(res, ruta.parent, periodo)
    return res


def _urls(res):
    """Los ficheros de un resultado que se leen por su url: las imágenes y las isolíneas de sus capas y los fotogramas del penacho."""
    for m in res["magnitudes"].values():
        for c in m["capas"]:
            yield from (i["url"] for i in c["imagenes"])
            if c.get("isolineas"):
                yield c["isolineas"]["url"]
        pen = m.get("penacho") or {}
        for fotos in pen.get("frames", []):
            yield from fotos
        yield from (pen.get("frames_iso") or [])             # las isolíneas del penacho hora a hora (olor): también se copian y se comprueban


def _completo(res):
    return all(Path(url_a_ruta(u)).is_file() for u in _urls(res))


def url_a_ruta(url):
    from urllib.parse import unquote, urlparse
    return unquote(urlparse(url).path).lstrip("/")


# ── guardar y cargar un caso (usuario, 2026-11-09: «le damos a guardar, te pide un nombre que se añade a la fecha, año/mes/día-nombre, creándose
# esa carpeta, donde guardará los resultados y la operabilidad de los focos en una carpeta llamada resultados»; luego, el informe en PDF) ──
def dir_guardados(modo="reanalisis"):
    """Donde se guardan los casos de un modo de simulación (usuario, 2026-11-10: «una carpeta… que sean casos, con 3 carpetas:
    reanálisis, episodios y predicción»): `planta.DIR_CASOS`/reanalisis, episodios o prediccion (`planta.CARPETAS_CASOS`), una
    carpeta por caso (`carpeta_caso`), con «resultados» y, a su lado, el informe."""
    from teodors.planta import CARPETAS_CASOS
    return config.DIR_CASOS / CARPETAS_CASOS[modo]


def carpeta_caso(nombre, fecha=None, modo="reanalisis"):
    """La carpeta de un caso: «AAAA-MM-DD-nombre» en `dir_guardados` (la de su modo), con la fecha de hoy (o `fecha`). Del nombre se quita lo
    que no puede ir en una carpeta."""
    limpio = " ".join("".join("-" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in nombre).split()).strip(" .")
    if not any(c.isalnum() for c in limpio):
        raise ValueError("Ponle un nombre al caso, con alguna letra o número.")
    return dir_guardados(modo) / f"{(fecha or dt.date.today()):%Y-%m-%d}-{limpio[:80]}"


def _carpeta(res):
    return Path(res["carpeta"]) if res.get("carpeta") else carpeta_resultados(res["esc"], res.get("periodo"))


def guardar_caso(res, carpeta, catalogo=None, progreso=None):
    """Guarda un resultado en la carpeta de un caso (`carpeta_caso`), en «resultados»: su resultado.json y la carpeta de cada magnitud (resumen,
    imágenes e isolíneas), y la operación de los focos: el plan con el que se simuló (plan_operacion.json) y los focos (focos.json), si
    `catalogo` es el de la simulación (su firma) o el caso ya los traía. Para el informe (`teodors.writer`), aunque se abra en otro equipo, los
    lugares de los receptores (lugares.json: el centro y sus nombres) y los edificios de la planta (edificios_planta.json). Lo que hubiera en
    «resultados» se sustituye; lo demás de la carpeta del caso (el informe) no se toca. Devuelve {"carpeta", "focos": si se han guardado los
    focos}."""
    avisa = progreso or (lambda *_: None)
    origen, caso = _carpeta(res), Path(carpeta)
    destino = caso / "resultados"
    parcial = caso / "resultados.parcial"
    shutil.rmtree(parcial, ignore_errors=True)
    parcial.mkdir(parents=True)
    for j, k in enumerate(res["orden"]):
        avisa(int(90 * j / len(res["orden"])), f"Guardando {res['magnitudes'][k]['nombre']}…")
        shutil.copytree(origen / k, parcial / k)
    limpio = {k: v for k, v in res.items() if k not in ("carpeta", "caso")}
    (parcial / "resultado.json").write_text(json.dumps(limpio, ensure_ascii=False, indent=1), encoding="utf-8")
    F.escribir_json(parcial / "plan_operacion.json", res["esc"])
    focos = False
    if (origen / "focos.json").is_file():                       # un caso ya guardado: sus focos
        shutil.copy2(origen / "focos.json", parcial / "focos.json")
        focos = True
    elif catalogo is not None and firma(res["esc"], catalogo, res.get("periodo")) == res.get("firma"):
        F.escribir_json(parcial / "focos.json", catalogo)
        focos = True
    for nombre, sacar in (("lugares.json", _lugares_receptores), ("edificios_planta.json", _edificios_planta)):
        if (origen / nombre).is_file():                          # un caso ya guardado: los suyos
            shutil.copy2(origen / nombre, parcial / nombre)
        elif res.get("periodo") is None:
            datos = sacar()
            if datos is not None and nombre == "lugares.json":    # con sus pueblos, cada uno con sus receptores
                with np.load(parcial / res["orden"][0] / "resumen.npz") as z:
                    datos = lugares_al_dia(datos, z["x"], z["y"])
            if datos is not None:
                F.escribir_json(parcial / nombre, datos)
    shutil.rmtree(destino, ignore_errors=True)
    parcial.rename(destino)
    avisa(100, "Guardado")
    log.info(f"Caso «{caso.name}» guardado en {caso}" + ("" if focos else " (sin los focos: han cambiado desde que se simuló)") + ".")
    return {"carpeta": str(caso), "focos": focos}


def _lugares_receptores():
    """El centro y los nombres de los receptores de la serie del reanálisis, o None."""
    carpeta = dir_respuestas()
    if carpeta is None:
        return None
    ind = SR.indice(carpeta)
    return {"centro": ind["centro"], "etiquetas": ind.get("etiquetas", [])}


def _edificios_planta():
    from teodors.operacion import edificios_planta as EP
    try:
        return EP.cargar()
    except (ValueError, OSError):
        return None


def lugares_al_dia(lugares, x, y):
    """Los lugares de los receptores ({«centro», «etiquetas»}) con los pueblos al día (`pueblos.etiquetas`: cada uno con sus receptores, y los
    de la planta), si no lo estaban ya (su «pueblos», la `pueblos.firma` de entonces)."""
    if lugares.get("pueblos") == P.firma():
        return lugares
    return dict(lugares, etiquetas=P.etiquetas(lugares.get("etiquetas", []), x, y), pueblos=P.firma())


def pueblos_al_dia(res, raiz, periodo):
    """Si los pueblos han cambiado desde que se guardó un resultado (`pueblos.firma`: cómo se reparten sus receptores o los de planta.json),
    rehace sus tablas de su resumen y lo vuelve a guardar (y, en un caso, sus lugares), sin volver a calcular la serie. Los lugares, los del
    caso (lugares.json) o los del índice de los receptores; si no hay, se queda como está."""
    if res.get("pueblos") == P.firma():
        return
    raiz = Path(raiz)
    try:
        if (raiz / "lugares.json").is_file():
            lugares = json.loads((raiz / "lugares.json").read_text(encoding="utf-8"))
        else:
            carpeta = dir_respuestas() if periodo is None else periodos.dir_respuestas(periodo)
            if carpeta is None:
                return
            meta = SR.indice(carpeta) if periodo is None else json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
            lugares = {"centro": meta["centro"], "etiquetas": meta.get("etiquetas", [])}
        for k, m in res["magnitudes"].items():
            with np.load(raiz / k / "resumen.npz") as z:
                x, y, clase = z["x"], z["y"], z["clase"]
                campos = {c["clave"]: z[c["clave"]] for c in m["columnas"] if c["clave"] in z.files}
            lugares = lugares_al_dia(lugares, x, y)
            m["filas"] = _tabla(lugares, x, y, clase, campos, m["columnas"], periodo is None)
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning(f"No se pudieron poner al día los pueblos del plan «{res.get('nombre')}»: {e}")
        return
    res["pueblos"] = P.firma()
    limpio = {k: v for k, v in res.items() if k not in ("carpeta", "caso")}
    (raiz / "resultado.json").write_text(json.dumps(limpio, ensure_ascii=False, indent=1), encoding="utf-8")
    if (raiz / "lugares.json").is_file():
        F.escribir_json(raiz / "lugares.json", lugares)
    log.info(f"Plan «{res.get('nombre')}»: tablas de los pueblos al día.")


def cargar_caso(carpeta, progreso=None):
    """Un caso guardado (`guardar_caso`), de su carpeta o de la de «resultados» de dentro, tal cual: sus imágenes e isolíneas, de allí (si
    las franjas de las isolíneas han cambiado, se rehacen). Devuelve el resultado con «carpeta» (la de «resultados») y «caso» ({"nombre",
    "ruta"})."""
    carpeta = Path(carpeta)
    raiz = carpeta if (carpeta / "resultado.json").is_file() else carpeta / "resultados"
    if not (raiz / "resultado.json").is_file():
        raise ValueError(f"«{carpeta.name}» no es un caso guardado: no tiene resultados\\resultado.json.")
    try:
        res = json.loads((raiz / "resultado.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"«{carpeta.name}»: no se puede leer su resultado ({e}).") from None
    if res.get("formato") != FORMATO_RESULTADO:
        raise ValueError(f"«{carpeta.name}» es de otra versión de la app (formato {res.get('formato')}; esta lee el {FORMATO_RESULTADO}).")

    def aqui(url):
        p = Path(url_a_ruta(url))
        nuevo = raiz / p.parent.name / p.name
        return nuevo.as_uri() + f"?v={int(nuevo.stat().st_mtime)}" if nuevo.is_file() else url
    for m in res["magnitudes"].values():
        for c in m["capas"]:
            for i in c["imagenes"]:
                i["url"] = aqui(i["url"])
            if c.get("isolineas"):
                c["isolineas"]["url"] = aqui(c["isolineas"]["url"])
        if m.get("penacho"):
            m["penacho"]["frames"] = [[aqui(u) for u in fotos] for fotos in m["penacho"]["frames"]]
            if m["penacho"].get("frames_iso"):
                m["penacho"]["frames_iso"] = [aqui(u) for u in m["penacho"]["frames_iso"]]
    if not _completo(res):
        raise ValueError(f"«{carpeta.name}»: le faltan imágenes o isolíneas.")
    _isolineas_al_dia(res, raiz, res.get("periodo"))
    _imagenes_al_dia(res, raiz, res.get("periodo"))
    pueblos_al_dia(res, raiz, res.get("periodo"))
    caso = raiz.parent if raiz.name == "resultados" else raiz
    res["carpeta"] = str(raiz)
    res["caso"] = {"nombre": caso.name, "ruta": str(caso)}
    log.info(f"Caso «{caso.name}» cargado: plan «{res['nombre']}», simulado el {res['fecha']}.")
    return res


def estado_respuestas(catalogo):
    """{id: «ok», «sin_calcular» o «cambiado»} de cada foco: si la serie del reanálisis tiene su respuesta y si es de su geometría de ahora
    (`focos.huella`). Lo enseña la ventana de los focos: uno nuevo o modificado está pendiente de simular."""
    carpeta = dir_respuestas()
    meta = SR.indice(carpeta)["focos"] if carpeta is not None else {}
    salida = {}
    for f in catalogo.get("focos", []):
        c = meta.get(f["id"])
        salida[f["id"]] = ("sin_calcular" if c is None or c.get("dias") == {} else
                           "cambiado" if c.get("huella") != F.huella(f) else "ok")
    return salida


def _focos_calculables(esc, catalogo, meta, fines):
    """{id: F(t), plan × parte del tiempo si es por eventos} de los focos que se pueden calcular, y {id: motivo} de
    los demás."""
    factores, fuera = {}, {}
    inicios = fines - pd.Timedelta(hours=1)                # el periodo con fin T emite de T − 1 h a T
    for f in catalogo["focos"]:
        duty, calc = F.fraccion_eventos(f), meta["focos"].get(f["id"])
        if duty is None:
            fuera[f["id"]] = "sin frecuencia o duración de sus eventos"
        elif calc is None or calc.get("dias") == {}:
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


def _dia_foco(m, v, forma, W):
    """X(t, r) = Σ_h W[h, t] · R[h, t, r] de un foco en un día, sin pasar por R entero (`serie_respuestas.decodificar`)."""
    idx, val = SR.decodificar(m, v, forma)
    plano = forma[1] * forma[2]
    h, resto = np.divmod(idx, plano)
    return np.bincount(resto, weights=val * W[h, resto // forma[2]], minlength=plano).reshape(forma[1:])


def calcular(esc, catalogo, progreso=None, cancelado=None, paralelo=None):
    """La serie del reanálisis con el plan, en todas sus magnitudes, y guarda el resultado: los días con respuesta de todos los
    focos que entran (`serie_respuestas`), y de ellos las horas del plan. Devuelve lo que necesita la interfaz.
    Los estadísticos de cada receptor se ACUMULAN mientras se resuelve cada día (`reanalisis_paralelo`), sin la serie hora a hora entera
    (hasta la v0.1.8, en ficheros temporales de `trabajo`: ~18 GB con 5 años). `paralelo`: False, en este proceso (lo mismo, bit a bit, que
    con la serie entera); True o un número de procesos, repartido entre ellos (lo mismo, salvo las medias en la cifra 14-15); None, el de la
    planta (`reanalisis_paralelo.de_la_planta`: False si no dice nada)."""
    from teodors.operacion import reanalisis_paralelo as RP
    t0 = time.time()
    n_procesos = RP.procesos(RP.de_la_planta() if paralelo is None else paralelo)
    avisa = progreso or (lambda *_: None)
    carpeta = dir_respuestas()
    if carpeta is None:
        raise RuntimeError("Aún no hay respuestas de los focos para la serie del reanálisis (operacion.serie_respuestas).")
    meta = SR.indice(carpeta)
    rec = SR.receptores(carpeta)
    x, y, clase = rec["x"], rec["y"], rec["clase"]
    todos = sorted({d for i in meta["focos"] for d in SR.dias_foco(meta, i)})
    if not todos:
        raise RuntimeError(f"{carpeta}: no tiene ningún día.")
    eje = pd.date_range(todos[0] - pd.Timedelta(days=1), todos[-1] + pd.Timedelta(hours=23), freq="h")
    factores, fuera = _focos_calculables(esc, catalogo, meta, eje)   # la emisión de cada foco en cada hora, desde el día antes del 1.º
    mags = _emisiones(catalogo, fuera)
    if not mags:
        raise RuntimeError("Ningún foco se puede calcular:\n" + "\n".join(
            f"{f.get('nombre') or f['id']}: {fuera.get(f['id'], 'sin emisión de olor ni de gases')}"
            for f in catalogo["focos"]))
    emisiones = {k: m["emisiones"] for k, m in mags.items()}
    usados = sorted({i for q in emisiones.values() for i in q})
    dias = SR.dias(meta, usados)
    if not dias:
        raise RuntimeError("No hay ningún día con respuesta de todos los focos que entran: " + ", ".join(usados))
    activos = [i for i in usados if factores[i].any()]           # un foco apagado no aporta nada
    fines = _horas(dias)
    mascara = E.horas_del_plan(esc, fines)
    if not mascara.any():
        raise RuntimeError(f"El plan no tiene ninguna hora entre el {dias[0]:%d/%m/%Y} y el {dias[-1]:%d/%m/%Y}.")
    fines_h = fines[mascara]
    pos = np.cumsum(mascara) - 1                                  # fila de cada hora en la serie de las horas del plan
    n, nrec, forma = int(mascara.sum()), len(x), SR.forma(meta)
    shutil.rmtree(config.DIR_TRABAJO / "reanalisis", ignore_errors=True)   # lo que dejara un cálculo cortado de la v0.1.8 o antes (~17 GB)
    series = RP.series_sin_disco(mags, n, nrec, clase, BLOQUE)             # nada en disco: solo la hora a hora de las viviendas del olor
    lugares = lugares_al_dia({"centro": meta["centro"], "etiquetas": meta.get("etiquetas", [])}, x, y)
    grupos = {"olor": _grupos_pueblos(lugares)} if "olor" in mags else {}
    campos, cols, horarias = RP.sumar_serie(dias, mascara, pos, activos, factores, emisiones, mags, carpeta, eje, forma, nrec, fines_h, series,
                                            avisa, cancelado, grupos, procesos=n_procesos)
    vivienda = _vivienda_horaria(series["olor"], clase, campos["olor"], cols["olor"]) if "olor" in grupos else None
    series.clear()
    seg_serie = time.time() - t0
    raiz = carpeta_resultados(esc)
    for k in mags:
        (raiz / k).mkdir(parents=True, exist_ok=True)
        np.savez_compressed(raiz / k / "resumen.npz", x=x, y=y, clase=clase, **campos[k])
    if "olor" in grupos:
        _guardar_horas_pueblos(raiz / "olor" / HORAS_PUEBLOS, fines_h, grupos["olor"], horarias["olor"], vivienda)
    rejillas = _rejillas(x, y, meta["centro"])
    capas = {k: _capas(campos[k], cols[k], rejillas, raiz / k, avisa, m, 80 + 20 * j // len(mags), "plan")
             for j, (k, m) in enumerate(mags.items())}
    magnitudes = {k: _magnitud(m, factores, cols[k], capas[k], campos[k], _tabla(lugares, x, y, clase, campos[k], cols[k], True), None, [])
                  for k, m in mags.items()}
    res = {"formato": FORMATO_RESULTADO, "firma": firma(esc, catalogo), "nombre": esc.get("nombre"), "fecha": time.strftime("%Y-%m-%d %H:%M"),
           "pueblos": P.firma(),
           "esc": esc, "periodo": None, "largo": "anios", "serie": meta["serie"], "horas": n, "datos": _cobertura(dias, fines_h),
           "orden": list(mags), "magnitudes": magnitudes, "segundos": round(time.time() - t0, 1), "segundos_serie": round(seg_serie, 1)}
    (raiz / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    avisa(100, "Hecho")
    log.info(f"Plan «{res['nombre']}» calculado en {res['segundos']:.0f} s: {len(usados)} focos, {len(mags)} magnitudes, "
             f"{res['horas']} horas, {nrec} receptores" + (f", en {n_procesos} procesos." if n_procesos > 1 else "."))
    return res


def _grupos_pueblos(lugares):
    """Los pueblos como los de la tabla del reanálisis (`_tabla`), uno por nombre, con todos los receptores de todas sus partes:
    [(nombre, índices)]."""
    juntos = {}
    for e in lugares.get("etiquetas", []):
        if e["clase"] == "nucleo" and e.get("familia") == "residencial":
            juntos.setdefault(e["nombre"], set()).update(e.get("receptores") or [e["i"]])
    return [(nombre, np.array(sorted(r), dtype=np.int64)) for nombre, r in juntos.items()]


def _vivienda_horaria(serie, clase, campos, cols):
    """La hora a hora de la peor vivienda (la de la tabla: por el estadístico de su capa o, si no tiene, por el máximo): (nombre, C) o None."""
    viv = np.flatnonzero(clase == "vivienda")
    if not len(viv):
        return None
    peor = next((c["clave"] for c in cols if c["capa"] == "norma"), "maximo")
    i = int(viv[np.argmax(campos[peor][viv])])
    return f"Peor vivienda (< {config.RADIO_EDIFICIOS_KM:g} km)", np.array(serie[i // BLOQUE, :, i % BLOQUE], np.float32)


def _guardar_horas_pueblos(ruta, fines_h, grupos, C, vivienda):
    """olor/horas_pueblos.npz: «horas» (el fin de cada hora del plan, UTC, en horas desde 1970), «nombres» y «C» [hora, lugar] (ou_E/m³)."""
    nombres = [nombre for nombre, _ in grupos]
    if vivienda is not None:
        nombres.append(vivienda[0])
        C = np.column_stack([C, vivienda[1]])
    horas = np.asarray(pd.DatetimeIndex(fines_h).values.astype("datetime64[h]").astype(np.int64))
    np.savez_compressed(ruta, horas=horas, nombres=np.array(nombres), C=np.asarray(C, np.float32))


def _magnitud(m, factores, cols, capas, campos, filas, penacho, horas_txt):
    salen = {c: m[c] for c in ("clave", "nombre", "unidad", "escala", "ref", "emisiones")}
    salen.update(focos=sum(1 for i in m["emisiones"] if factores[i].any()), fuera=m["fuera"], estimados=m["estimados"], columnas=cols,
                 capas=capas, penacho=penacho, horas_txt=horas_txt, maximos={c: float(v.max()) for c, v in campos.items()}, filas=filas)
    return salen


def calcular_periodo_preparando(esc, catalogo, periodo, progreso=None, cancelado=None):
    """Como `calcular_periodo`, pero si las RESPUESTAS (puff) del periodo no están, las calcula antes (puff, paralelo por foco; 0-60 %) y
    luego los estadísticos + el penacho (60-100 %). Es lo que lanza el botón «Simular episodio»."""
    if not periodos.listo(periodo):
        periodos.preparar_respuestas(periodo, progreso=(lambda pct, m: progreso(int(pct * 0.6), m)) if progreso else None,
                                     cancelado=cancelado)
    return calcular_periodo(esc, catalogo, periodo,
                            progreso=(lambda pct, m: progreso(int(60 + pct * 0.4), m)) if progreso else None, cancelado=cancelado)


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
    lugares = lugares_al_dia({"centro": meta["centro"], "etiquetas": meta.get("etiquetas", [])}, x, y)
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
        # isolíneas del penacho hora a hora (usuario, 2026-11-13): como las de media/máximo y como en el informe. Solo para el OLOR (la magnitud
        # principal y la del informe): generarlas para los 8 gases sumaría ~+100 MB por episodio. Los gases mantienen el penacho en degradado.
        quiere_iso = m["clave"] == "olor"
        niveles_iso = niveles_isolineas(m["ref"], m["clave"])
        frames, frames_iso, limites = [], [], None
        for t in range(len(C)):
            if cancelado and cancelado():
                raise RuntimeError("Cálculo cancelado.")
            if t % 6 == 0:
                avisa(base + 90 * t // (len(C) * len(mags)), f"{m['nombre']}: penacho, hora {t + 1} de {len(C)}")
            imagenes = _imagenes(C[t], rejillas, raiz / k / f"penacho_{t:03d}", m["ref"])
            frames.append([i["url"] for i in imagenes])
            limites = [i["limites"] for i in imagenes]
            if quiere_iso:
                ruta_iso = raiz / k / f"penacho_iso_{t:03d}.json"
                _isolineas(C[t], rejillas, ruta_iso, niveles_iso)
                frames_iso.append(ruta_iso.as_uri() + f"?v={int(ruta_iso.stat().st_mtime)}")
        penacho = {"dia": periodo["ini"], "dias": n, "frames": frames,
                   "frames_iso": frames_iso if quiere_iso else None,
                   "niveles_iso": niveles_iso if quiere_iso else None,
                   "leyenda_iso": _leyenda_isolineas("Penacho", m, niveles_iso) if quiere_iso else None,
                   "limites": limites, "leyenda": _leyenda("penacho", m)}
        magnitudes[k] = _magnitud(m, factores, cols, capas, campos, _tabla(lugares, x, y, clase, campos, cols), penacho, horas_txt)
    res = {"formato": FORMATO_RESULTADO, "firma": firma(esc, catalogo, periodo), "nombre": esc.get("nombre"), "fecha": time.strftime("%Y-%m-%d %H:%M"),
           "pueblos": P.firma(),
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


# Las franjas del olor (usuario, 2026-11-09: «en olores tienes que añadir 0,01-0,1 y de 0,1-1, 1-3, 3-5 y de 5-10»): las de los pueblos, abajo, y
# las de los criterios de olor (1, 3 y 5 ou_E/m³), en medio; encima, un orden de magnitud por franja, como antes.
NIVELES_OLOR = (0.01, 0.1, 1.0, 3.0, 5.0, 10.0, 100.0, 1000.0)


def niveles_isolineas(ref=1.0, clave=None):
    """Los límites de las franjas de las isolíneas. Del olor, `NIVELES_OLOR`; de un gas, 4 órdenes de magnitud (usuario, 2026-11-09: «el color
    map de 4 órdenes de magnitud»), uno por franja, en potencias de 10 desde la más cercana a VMIN · `ref`."""
    if clave == "olor":
        return [float(v) for v in NIVELES_OLOR]
    d0 = int(round(np.log10(VMIN * ref)))
    return [float(f"{10.0 ** (d0 + k):.6g}") for k in range(DECADAS + 1)]


def en_rejilla(campo, r, piso):
    """Un campo de los receptores en los puntos de una rejilla de las imágenes (`_rejillas`), interpolando en logaritmos (la concentración cae
    órdenes de magnitud entre receptores), con `piso` donde no llega nada; y la máscara de lo que no se pinta: fuera de los receptores y, en la
    de la zona, el hueco de la cercana."""
    log_c = np.log10(np.maximum(campo, piso))
    v = 10.0 ** (log_c[r["vertices"]] * r["pesos"]).sum(axis=1)
    fuera = r["fuera"] if r["hueco"] is None else r["fuera"] | r["hueco"]
    return v.reshape(r["forma"]), fuera.reshape(r["forma"])


def franjas_geojson(zs, rejillas, franjas, lineas):
    """GeoJSON (lat/lon) de las franjas y las líneas de un campo z dado en cada rejilla (`zs`, enmascarados: lo que no se pinta). `franjas`:
    [(desde, hasta, propiedades)], una MultiPolygon cada una; `lineas`: [(nivel, propiedades)], una MultiLineString cada una. Las de la
    zona acaban justo en el borde de la cercana: no se solapan."""
    import contourpy

    from teodors.planta import geo
    partes = [[] for _ in franjas]
    trazos = [[] for _ in lineas]

    def a_geo(xy):
        lat, lon = geo.a_geo(xy[:, 0], xy[:, 1])
        return np.round(np.c_[lon, lat], 5).tolist()

    for r, z in zip(rejillas, zs):
        cg = contourpy.contour_generator(r["x"], r["y"], z, fill_type="OuterOffset", line_type="Separate")
        for i, (desde, hasta, _) in enumerate(franjas):
            puntos, cortes = cg.filled(desde, hasta)
            for q, c in zip(puntos, cortes):
                partes[i].append([a_geo(q[a:b]) for a, b in zip(c[:-1], c[1:])])
        for i, (nivel, _) in enumerate(lineas):
            trazos[i].extend(a_geo(q) for q in cg.lines(nivel) if len(q) > 1)
    feats = [{"type": "Feature", "geometry": {"type": "MultiPolygon", "coordinates": partes[i]}, "properties": f[2]}
             for i, f in enumerate(franjas) if partes[i]]
    feats += [{"type": "Feature", "geometry": {"type": "MultiLineString", "coordinates": trazos[i]}, "properties": li[1]}
              for i, li in enumerate(lineas) if trazos[i]]
    return {"type": "FeatureCollection", "features": feats}


def _isolineas(campo, rejillas, ruta, niveles):
    """Las isolíneas rellenas de un campo, en GeoJSON (lat/lon) en `ruta`: una franja entre cada dos `niveles` (`niveles_isolineas`; la última,
    también lo que pasa de ella, como el degradado), y las líneas de cada nivel, en cada rejilla de las imágenes. Se interpola en logaritmos,
    como las imágenes. Cada franja, con su sitio en la escala de color repartido a partes iguales («f»): con colores proporcionales al
    logaritmo, 1-3, 3-5 y 5-10 casi no se distinguirían."""
    n = len(niveles) - 1                                   # las franjas
    log_n = np.log10(niveles)
    zs = []
    for r in rejillas:
        v, fuera = en_rejilla(campo, r, niveles[0] / 100.0)
        zs.append(np.ma.masked_array(np.log10(v), mask=fuera))
    franjas = [(log_n[i], log_n[i + 1] if i + 1 < n else 99.0,
                {"tipo": "franja", "f": (i + 0.5) / n, "desde": niveles[i], "hasta": niveles[i + 1] if i + 1 < n else None}) for i in range(n)]
    lineas = [(log_n[i], {"tipo": "linea", "nivel": niveles[i]}) for i in range(n)]
    ruta.write_text(json.dumps(franjas_geojson(zs, rejillas, franjas, lineas), separators=(",", ":")), encoding="utf-8")
    return niveles


def _capa_isolineas(campo, rejillas, ruta, m, nombre):
    """Las isolíneas de una capa de la magnitud `m` y lo que se guarda de ellas en el resultado: su url, sus niveles y su leyenda."""
    niveles = niveles_isolineas(m["ref"], m["clave"])
    _isolineas(campo, rejillas, ruta, niveles)
    return {"url": ruta.as_uri() + f"?v={int(ruta.stat().st_mtime)}", "niveles": niveles, "leyenda": _leyenda_isolineas(nombre, m, niveles)}


def _isolineas_al_dia(res, raiz, periodo):
    """Si las franjas de las isolíneas han cambiado desde que se guardó un resultado (`niveles_isolineas`), las rehace de su resumen y lo
    vuelve a guardar: unas décimas de segundo, sin volver a calcular la serie. Si no se puede (sin la carpeta de las respuestas), se quedan."""
    viejas = [(k, c) for k, m in res["magnitudes"].items() for c in m["capas"]
              if c.get("isolineas") and c["isolineas"]["niveles"] != niveles_isolineas(m["ref"], k)]
    if not viejas:
        return
    try:
        carpeta = dir_respuestas() if periodo is None else periodos.dir_respuestas(periodo)
        meta = SR.indice(carpeta) if periodo is None else json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
        rejillas = None
        for k, c in viejas:
            ruta = Path(url_a_ruta(c["isolineas"]["url"]))
            with np.load(raiz / k / "resumen.npz") as z:
                if rejillas is None:
                    rejillas = _rejillas(z["x"], z["y"], meta["centro"])
                campo = z[ruta.name[:-len("_isolineas.json")]]
            c["isolineas"] = _capa_isolineas(campo, rejillas, ruta, res["magnitudes"][k], c["nombre"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning(f"No se pudieron rehacer las isolíneas del plan «{res.get('nombre')}»: {e}")
        return
    (raiz / "resultado.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info(f"Plan «{res.get('nombre')}»: isolíneas rehechas con las franjas de ahora ({len(viejas)} capas).")


def _imagenes_al_dia(res, raiz, periodo):
    """Si la escala del degradado ha cambiado desde que se guardó un resultado (VMIN y DECADAS: lo de antes del 2026-11-10 no la apunta, y
    era de 0,1), repinta sus imágenes de su resumen, con su leyenda, y lo vuelve a guardar, sin volver a calcular la serie (unos segundos).
    Si no se puede (sin la carpeta de las respuestas), se quedan."""
    viejas = [(k, c) for k, m in res["magnitudes"].items() for c in m["capas"]
              if c.get("imagenes") and (c.get("vmin") != VMIN * m["ref"] or c.get("decadas") != DECADAS)]
    if not viejas:
        return
    try:
        carpeta = dir_respuestas() if periodo is None else periodos.dir_respuestas(periodo)
        meta = SR.indice(carpeta) if periodo is None else json.loads((carpeta / "meta.json").read_text(encoding="utf-8"))
        rejillas = None
        for k, c in viejas:
            m = res["magnitudes"][k]
            clave = Path(url_a_ruta(c["imagenes"][0]["url"])).name.rsplit("_", 1)[0]          # «p98_0.png» → «p98»
            with np.load(Path(raiz) / k / "resumen.npz") as z:
                if rejillas is None:
                    rejillas = _rejillas(z["x"], z["y"], meta["centro"])
                campo = z[clave]
            c.update(imagenes=_imagenes(campo, rejillas, Path(raiz) / k / clave, m["ref"]), leyenda=_leyenda(c["nombre"], m),
                     vmin=VMIN * m["ref"], decadas=DECADAS)
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning(f"No se pudieron repintar las imágenes del plan «{res.get('nombre')}»: {e}")
        return
    limpio = {k: v for k, v in res.items() if k not in ("carpeta", "caso")}
    (Path(raiz) / "resultado.json").write_text(json.dumps(limpio, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info(f"Plan «{res.get('nombre')}»: degradado repintado con la escala de ahora ({len(viejas)} capas).")


def leer_isolineas(capa):
    """El GeoJSON de las isolíneas de una capa (`_capas`), o None si no las tiene o no se pueden leer."""
    iso = capa.get("isolineas")
    if not iso:
        return None
    try:
        return json.loads(Path(url_a_ruta(iso["url"])).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _leyenda(titulo, m):
    return penacho_mapa.leyenda_html({"vmin": VMIN * m["ref"], "decadas": DECADAS, "unidad": m["unidad"],
                                      "escala": m["escala"]}, f"{m['nombre']} · {titulo}")


def _leyenda_isolineas(titulo, m, niveles):
    """Leyenda de las isolíneas: un cuadro por franja con su color en la escala elegida (el degradado de --escala-…, ampliado y desplazado
    hasta ese punto: cambia solo al cambiar de escala) y los niveles en sus bordes, como la del degradado."""
    cuadros = []
    for i in range(len(niveles) - 1):
        f = (i + 0.5) / (len(niveles) - 1)
        cuadros.append(f"<span style='flex:1;height:12px;background:var(--escala-{m['escala']});background-size:20000% 100%;"
                       f"background-position:{100 * f:.2f}% 0;opacity:{(60 + 195 * f) / 255:.2f}'></span>")
    unidad = f" ({m['unidad']})" if m.get("unidad") else ""
    return (f"<h4>{m['nombre']} · {titulo}{unidad}</h4>"
            f"<div style='display:flex;gap:1px'>{''.join(cuadros)}</div>"
            "<div style='display:flex;justify-content:space-between;font-size:11px'>"
            + "".join(f"<span>{penacho_mapa._num(n)}</span>" for n in niveles) + "</div>")


def _capas(campos, cols, rejillas, salida, avisa, m, avance, prefijo):
    """Las capas del mapa de una magnitud: media, máximo y, si lo tiene, el percentil o el estadístico de su límite."""
    capas = []
    for col in cols:
        if col["capa"]:
            avisa(avance, f"{m['nombre']}: imagen de «{col['nombre']}»…")
            capa = {"id": f"{prefijo}_{col['capa']}", "nombre": col["nombre"], "titulo": col["titulo"],
                    "imagenes": _imagenes(campos[col["clave"]], rejillas, salida / col["clave"], m["ref"]),
                    "leyenda": _leyenda(col["nombre"], m), "escala": m["escala"], "vmin": VMIN * m["ref"], "decadas": DECADAS}
            if rejillas:                               # las isolíneas rellenas (usuario, 2026-11-09)
                capa["isolineas"] = _capa_isolineas(campos[col["clave"]], rejillas, salida / f"{col['clave']}_isolineas.json", m, col["nombre"])
            capas.append(capa)
    return capas


def datos_penacho(res, clave):
    """Lo que necesita la capa del penacho de una magnitud: sus imágenes y, si está, el tiempo en la planta ese día."""
    m = res["magnitudes"][clave]
    p = m["penacho"]
    return dict(p, nombre="Penacho", opacidad=penacho_mapa.OPACIDAD, grupo=penacho_mapa.GRUPO, escala=m["escala"],
                **penacho_mapa.tiempo_dia(p["dia"], res["serie"], p["dias"]))


def valores(res, clave):
    """{(x, y): {columna: valor}} de una magnitud del resultado `res`, por receptor (x, y redondeados a 0,1 m)."""
    raiz = Path(res["carpeta"]) if res.get("carpeta") else carpeta_resultados({"nombre": res["nombre"]}, res.get("periodo"))
    with np.load(raiz / clave / "resumen.npz") as z:
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


def _tabla(meta, x, y, clase, campos, cols, todos_los_pueblos=False):
    """Lugares con nombre, cada uno con su «tipo»: los receptores con nombre (salvo los marcados `"en_tabla": false`), la peor vivienda (por el
    estadístico de su capa o, si no tiene, por el máximo) y los pueblos (núcleos urbanos) cercanos, los 10 más cercanos o, con `todos_los_pueblos`
    (el reanálisis, que solo enseña los pueblos: usuario, 2026-11-09), todos, uno por nombre: un pueblo en varias partes, con lo peor de ellas y
    la distancia de la más cercana. Un pueblo con «receptores» (`pueblos.etiquetas`) vale lo que el peor de ellos (usuario, 2026-11-10); su
    distancia, la de su punto."""
    xc, yc = meta["centro"]

    def fila(nombre, i, tipo, suyos=None):
        k = suyos or [i]
        return {"nombre": nombre, "tipo": tipo, "km": round(float(np.hypot(x[i] - xc, y[i] - yc)) / 1000.0, 1),
                **{c: float(np.max(v[k])) for c, v in campos.items()}}
    en_tabla = {r["nombre"] for r in receptores_mapa.con_nombre() if r.get("en_tabla", True)}
    filas = [fila(e["nombre"], e["i"], "nombrado") for e in meta["etiquetas"]
             if e["clase"] == "nombrado" and e["nombre"] in en_tabla]
    viv = np.flatnonzero(clase == "vivienda")
    if len(viv):
        peor = next((c["clave"] for c in cols if c["capa"] == "norma"), "maximo")
        filas.append(fila(f"Peor vivienda (< {config.RADIO_EDIFICIOS_KM:g} km)", viv[np.argmax(campos[peor][viv])], "vivienda"))
    pueblos = sorted((fila(e["nombre"], e["i"], "pueblo", e.get("receptores")) for e in meta["etiquetas"]
                      if e["clase"] == "nucleo" and e.get("familia") == "residencial"), key=lambda f: f["km"])
    if not todos_los_pueblos:
        return filas + pueblos[:10]
    juntos = {}
    for f in pueblos:                                       # de cerca a lejos: la distancia, la de la parte más cercana
        if f["nombre"] in juntos:
            juntos[f["nombre"]].update({c: max(juntos[f["nombre"]][c], f[c]) for c in campos})
        else:
            juntos[f["nombre"]] = f
    return filas + list(juntos.values())
