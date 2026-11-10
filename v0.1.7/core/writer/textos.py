# -*- coding: utf-8 -*-
"""Los textos del informe que salen solos de los datos (`datos.reunir`): «Lo esencial del caso», con una redacción para cada situación
(ningún pueblo por encima de 1 ou_E/m³, por encima de 1, de 3 o de 5; sin pueblos; sin olor), y el relieve y los usos del suelo, que solo
dependen del terreno. Lo que el terreno no sabe decir, el nombre de los sitios, lo pone la planta en su planta.json («informe»). Sin Qt."""
import html
import json

import numpy as np

from teodors import planta as config
from teodors.comun.formato import num as _num
from teodors.operacion import focos as F, simulacion as S

RUMBOS8 = ("N", "NE", "E", "SE", "S", "SO", "O", "NO")
RUMBOS16 = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO")
NOMBRE_RUMBO = {"N": "norte", "NE": "noreste", "E": "este", "SE": "sureste", "S": "sur", "SO": "suroeste", "O": "oeste", "NO": "noroeste"}
GRUPO_FRASE = {"Agrícola": "lo agrícola", "Forestal y matorral": "el bosque y el matorral", "Mar y aguas costeras": "el mar",
               "Urbano residencial": "lo urbano", "Industrial y comercial": "lo industrial", "Zonas húmedas": "las zonas húmedas",
               "Aguas continentales": "los ríos y embalses", "Espacios abiertos (playas, roquedo…)": "los espacios abiertos",
               "Otras superficies artificiales": "otras superficies artificiales"}
UMBRALES = "1, 3 y 5 ou_E/m³ de P98, de más a menos exigente según lo sensible que sea la zona"
PLANES_TXT = {"diario": "diario", "semanal": "semanal", "mensual": "de un mes"}
MESES_LARGOS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def e(x):
    return html.escape(str(x))


def ci(v):
    """Una concentración como en la app (`simulacion.cifra`: dos cifras significativas), con el espacio de miles del resto del informe: «1 719»."""
    return _num(v, 0) if v >= 1000 else S.cifra(v)


def rumbo8(dx, dy):
    """El rumbo (de 8) de un desplazamiento en UTM: hacia dónde."""
    return RUMBOS8[int(((np.degrees(np.arctan2(dx, dy)) % 360) + 22.5) // 45) % 8]


def rumbo16(grados):
    return RUMBOS16[int(round(grados / 22.5)) % 16]


def y_lista(cosas, y=" y "):
    cosas = [c for c in cosas if c]
    if not cosas:
        return ""
    return cosas[0] if len(cosas) == 1 else ", ".join(cosas[:-1]) + y + cosas[-1]



def _min(nombre):
    """Un nombre en medio de una frase: «Balsa de digestato 1» → «balsa de digestato 1»."""
    return nombre[:1].lower() + nombre[1:]


def hacia(rumbos):
    return y_lista([f"el {NOMBRE_RUMBO[x]}" for x in rumbos])


def km_txt(km):
    return f"{_num(km * 1000, 0)} m" if km < 1 else f"{_num(km, 1)} km"


def pct_txt(x):
    return f"{_num(x, 1)} %" if x < 10 else f"{_num(x, 0)} %"


def fecha(iso):
    return f"{int(iso[8:10])}/{int(iso[5:7])}/{iso[:4]}"


def texto_planta(clave):
    """Lo que la planta añade con el nombre de sus sitios (planta.json, «informe»: «relieve» y «usos»), o ""."""
    try:
        return (json.loads((config.PLANTA / "planta.json").read_text(encoding="utf-8")).get("informe") or {}).get(clave, "")
    except (OSError, ValueError):
        return ""


# ── el terreno ──────────────────────────────────────────────────────────────────────────────────────────
def terreno(t, xc, yc):
    """(relieve, usos): lo que dicen el relieve y los usos del suelo de `t` (`datos._terreno`), dónde está lo alto y el mar y qué usos
    predominan en la zona y alrededor de la planta, para cualquier planta; y lo que añade la suya. ("", "") sin terreno."""
    from teodors.fuentes import terreno as T
    if not t:
        return "", ""
    Z, U, tr, info, res_t = t["Z"], t["U"], t["tr"], t["info"], t["resumen"]
    ny, nx = Z.shape
    X = tr.c + (np.arange(nx) + 0.5) * tr.a
    Y = tr.f + (np.arange(ny) + 0.5) * tr.e
    DX, DY = np.meshgrid(X - xc, Y - yc)
    dist = np.hypot(DX, DY)
    sector = ((np.degrees(np.arctan2(DX, DY)) % 360 + 22.5) // 45).astype(int) % 8
    mar = np.isin(U, (521, 522, 523, T.NODATA_USO))
    tierra = ~mar
    zp = (info.get("planta") or {}).get("z") or 0.0
    relieve = ""
    if tierra.any():
        i, j = np.unravel_index(np.argmax(np.where(tierra, Z, -1e9)), Z.shape)
        zmax, dmax, rmax = float(Z[i, j]), float(dist[i, j]) / 1000, RUMBOS8[sector[i, j]]
        medias = []
        for s in range(8):
            sel = (sector == s) & tierra & (dist > 3000)
            medias.append(float(Z[sel].mean()) if sel.any() else -1e9)
        altos = [RUMBOS8[s] for s in np.argsort(medias)[::-1][:2] if medias[s] > zp + 150]
        cerca = tierra & (dist <= 2000)
        if cerca.any():
            z_a, z_b = float(Z[cerca].min()), float(Z[cerca].max())
            relieve = (f"La planta está a {_num(zp)} m, en un terreno {'suave' if z_b - z_a < 120 else 'con desnivel'}: a menos de 2 km, la cota va "
                       f"de {_num(z_a)} a {_num(z_b)} m. ")
        if altos:
            relieve += (f"El terreno sube hacia {hacia(altos)}, donde está lo más alto de la zona de cálculo, {_num(zmax)} m, a {_num(dmax, 1)} km "
                        f"al {NOMBRE_RUMBO[rmax]}. ")
        else:
            relieve += f"Es una zona sin grandes desniveles: lo más alto, {_num(zmax)} m, está a {_num(dmax, 1)} km al {NOMBRE_RUMBO[rmax]}. "
    con_mar = [RUMBOS8[s] for s in range(8) if (sector == s).any() and mar[sector == s].mean() >= 0.2]
    if con_mar:
        relieve += f"Hacia {hacia(con_mar)} baja hasta el mar, que ocupa el {pct_txt(float(mar.mean() * 100))} de la zona. "
    bandas = res_t.get("bandas", [])
    if len(bandas) >= 4:
        relieve += (f"El {pct_txt(sum(b['pct'] for b in bandas[:2]))} de la zona está por debajo de 200 m, y el "
                    f"{pct_txt(sum(b['pct'] for b in bandas[3:]))}, por encima de 500 m. ")
    relieve += texto_planta("relieve")
    grupos = sorted((g for g in res_t.get("grupos", []) if g["pct"] >= 0.5), key=lambda g: -g["pct"])
    usos = ""
    if grupos:
        g0 = grupos[0]
        clases0 = [c for c in g0.get("clases", []) if c["pct"] >= 3][:2]
        usos = (f"Los usos del suelo {'son variados' if len(grupos) >= 4 and g0['pct'] < 60 else 'están poco repartidos'}. Predomina "
                f"{GRUPO_FRASE.get(g0['nombre'], g0['nombre'].lower())} ({pct_txt(g0['pct'])})"
                + (", sobre todo " + y_lista(f"{c['nombre'].lower()} ({pct_txt(c['pct'])})" for c in clases0) if clases0 else ""))
        siguen = [f"{GRUPO_FRASE.get(g['nombre'], g['nombre'].lower())} ({pct_txt(g['pct'])})" for g in grupos[1:3]]
        usos += ((", seguido de " + y_lista(siguen)).replace("de el ", "del ") if siguen else "") + ". "
    codigos, cuentas = np.unique(U[dist <= 2000], return_counts=True)
    locales = [(T.CLC_NOMBRES.get(int(codigos[k]), "?").lower(), 100.0 * cuentas[k] / cuentas.sum()) for k in np.argsort(cuentas)[::-1][:2]
               if int(codigos[k]) != T.NODATA_USO]
    if locales:
        usos += "Alrededor de la planta, a menos de 2 km, hay sobre todo " + y_lista(f"{nm} ({pct_txt(p_)})" for nm, p_ in locales) + ". "
    humedo = np.isin(U, (213, 411, 412, 421, 422, 423))
    if humedo.mean() >= 0.02:
        cuenta = [humedo[sector == s].sum() for s in range(8)]
        usos += (f"Los arrozales y las zonas húmedas ({pct_txt(float(humedo.mean() * 100))}) se concentran al "
                 f"{NOMBRE_RUMBO[RUMBOS8[int(np.argmax(cuenta))]]}. ")
    urb = sum(g["pct"] for g in res_t.get("grupos", []) if g["nombre"] == "Urbano residencial")
    if urb:
        usos += f"Los núcleos urbanos ocupan el {pct_txt(urb)} de la zona. "
    usos += texto_planta("usos")
    return relieve.strip(), usos.strip()


# ── lo esencial del caso ────────────────────────────────────────────────────────────────────────────────
def frase_umbral(v):
    if v > 5:
        return "por encima de 5 ou_E/m³"
    if v > 3:
        return "entre 3 y 5 ou_E/m³"
    if v > 1:
        return "entre 1 y 3 ou_E/m³"
    return "por debajo de 1 ou_E/m³"


def _peor_hora(pueblos, crit):
    """Lo que el P98 no dice (usuario, 2026-11-10: «aunque indique que el P98 cumple, también se ve que algún día llegó a umbrales de
    molestia»): los pueblos que en su peor hora pasan de 1, 3 y 5 ou_E/m³. Si ninguno pasa de 1 ni en su peor hora, se dice; si son los
    mismos que por el P98, no hace falta."""
    por = {c["umbral"]: [f for f in pueblos if f.get("maximo", 0.0) > c["umbral"]] for c in crit}
    if not por.get(1):
        return " Ni en su peor hora del reanálisis pasa ningún pueblo de 1 ou_E/m³."
    if all(len(por[c["umbral"]]) <= c["pueblos"] for c in crit):
        return ""
    lista = sorted(por[1], key=lambda f: -f["maximo"])
    nombres = "; ".join(f"{e(f['nombre'])}, {ci(f['maximo'])}" for f in lista[:4]) + (f"; y {len(lista) - 4} más" if len(lista) > 4 else "")
    n1 = len(lista)
    mas = [f"{len(por[u])} de {_num(u)}" for u in (3, 5) if por.get(u)]
    sin_p98 = [f for f in lista if f["p98"] <= 1]
    if not sin_p98:
        final = "."
    elif len(sin_p98) == n1:
        final = f": aunque su P98 no pase de 1, algún día el olor puede llegar a notarse en {'él' if n1 == 1 else 'ellos'}."
    else:
        final = f": en {len(sin_p98)} de ellos, con el P98 por debajo de 1, algún día el olor puede llegar a notarse."
    return (" Pero el P98 deja fuera el 2 % de las horas más altas, unas 175 al año: en su peor hora, "
            + y_lista([f"<b>{n1} {'pueblo pasa' if n1 == 1 else 'pueblos pasan'} de 1 ou_E/m³</b> ({nombres})"] + mas) + final)


def _juntos(nombres):
    """Nombres en medio de una frase, juntos los que solo cambian en su última palabra: «Hilera de compost 1» … «Hilera de compost 4» →
    «hileras de compost 1, 2, 3 y 4»; los demás, tal cual (en minúscula)."""
    grupos = {}
    for n in nombres:
        partes = n.split()
        grupos.setdefault(" ".join(partes[:-1]) if len(partes) > 1 else n, []).append(n)
    salen = []
    for prefijo, ns in grupos.items():
        if len(ns) > 1 and prefijo not in ns:
            p = prefijo.split()
            p[0] = p[0] + ("s" if p[0][-1].lower() in "aeiouáéíóú" else "es")
            salen.append(_min(" ".join(p)) + " " + y_lista([n.split()[-1] for n in ns]))
        else:
            salen += [_min(n) for n in ns]
    return y_lista(salen)


def _bajan(focos):
    """Los focos por debajo del 100 % con el plan, juntos por su %: «balsas de digestato 1 y 2, al 50 %; hileras de compost 1, 2, 3 y 4, sin
    emitir»."""
    grupos = {}
    for f in sorted((f for f in focos if f["media"] < 1.0), key=lambda f: (f["media"], -f["q"])):
        grupos.setdefault(_num(100 * f["media"], 0), []).append(f["nombre"])
    return "; ".join(f"{e(_juntos(n))}, " + ("sin emitir" if p == "0" else f"al {p} %") for p, n in grupos.items())


def _dias(fechas):
    """Días en tramos: «del 25 al 31 de julio», «el 3 de marzo»."""
    tramos = []
    for f in sorted(fechas):
        if tramos and (f - tramos[-1][1]).days == 1:
            tramos[-1][1] = f
        else:
            tramos.append([f, f])
    return y_lista((f"el {a.day} de {MESES_LARGOS[a.month - 1]}" if a == b else
                    f"del {a.day}{'' if a.month == b.month else ' de ' + MESES_LARGOS[a.month - 1]} al {b.day} de {MESES_LARGOS[b.month - 1]}")
                   for a, b in tramos)


def _tramos(horas):
    """Horas (las que empiezan a esa hora) en tramos: {8, …, 13} → «de 8 a 14 h»; por la noche, «de 22 a 6 h»."""
    hs, tramos = sorted(horas), []
    for h in hs:
        if tramos and h == tramos[-1][1] + 1:
            tramos[-1][1] = h
        else:
            tramos.append([h, h])
    if len(tramos) > 1 and tramos[0][0] == 0 and tramos[-1][1] == 23:
        tramos[0][0] = tramos.pop()[0]
    return y_lista(f"de {a} a {(b + 1) % 24} h" for a, b in tramos)


def operacion(d):
    """Lo que cuenta la página de la operación (usuario, 2026-11-10: «queda espacio por rellenar… texto narrativo»), de los datos: cómo
    funciona la planta con el plan; quién emite el olor; cómo entra el plan en el cálculo; y de dónde sale el olor de cada foco (medido o
    estimado por sus gases). [(título, HTML)]; con muchos focos, solo los dos primeros (la página va llena)."""
    op, r = d["operacion"], d["res"]
    focos = op["focos"]
    n = len(focos)
    uno = n == 1
    Q = op["q"] or 1.0
    salen = []
    cuando = f"todos los días de {MESES_LARGOS[op['mes'] - 1]} (el plan es de un mes: los demás no cuentan)" if op["mes"] else "todos los días del año"
    # 1. cómo funciona
    if op["al_100"]:
        t = (f"{'El foco funciona' if uno else f'Los {n} focos funcionan'} las 24 horas, {cuando}, al 100 %: la planta a plena carga y sin "
             "paradas, el caso más desfavorable para el olor.")
    elif op["constante"]:
        t = (f"Con este plan, la planta emite el {_num(100 * op['media'], 0)} % de lo que emitiría con todos los focos al 100 % "
             f"({_num(Q * op['media'])} ou_E/s), igual todas las horas, {cuando}: {_bajan(focos)}"
             + ("" if all(f["media"] < 1.0 for f in focos) else "; el otro, al 100 %" if sum(f["media"] >= 1.0 for f in focos) == 1 else
                "; los demás, al 100 %") + ".")
    else:
        h = np.asarray(op["horas"], float)
        alto, bajo = float(h.max()), float(h.min())
        t = (f"Con este plan, la planta emite de media el {_num(100 * op['media'], 0)} % de lo que emitiría con todos los focos al 100 % "
             f"({_num(Q * op['media'])} ou_E/s)" + (f", {cuando}" if op["mes"] else "") + ".")
        cambian = [f for f in focos if not f.get("constante", False)]
        fijos = [f for f in focos if f.get("constante", False)]
        planes_c = y_lista(sorted({PLANES_TXT.get(f["plan"], f["plan"]) for f in cambian if f["plan"] != "mensual"}))
        t += (f" Cambia el plan de {'un foco' if len(cambian) == 1 else f'{len(cambian)} focos'}: {e(_juntos(f['nombre'] for f in cambian))}"
              + (f" ({planes_c})" if planes_c else "") + (f"; el {'del otro' if len(fijos) == 1 else 'de los demás'}, siempre igual." if fijos else "."))
        if alto - bajo < 0.005 * max(alto, 1e-9):
            t += f" En su día medio, igual todas las horas ({_num(100 * alto, 0)} %)."
        elif alto - bajo < 0.05 * max(alto, 1e-9):
            t += f" En su día medio apenas cambia de una hora a otra (del {_num(100 * bajo, 0)} al {_num(100 * alto, 0)} %)."
        else:
            margen = 0.1 * (alto - bajo)
            t += (f" En su día medio, lo más es {_tramos(np.flatnonzero(h >= alto - margen))} ({_num(100 * alto, 0)} %) y lo menos, "
                  f"{_tramos(np.flatnonzero(h <= bajo + margen))} ({_num(100 * bajo, 0)} %).")
        dia = np.zeros(7)
        for f in focos:
            for w, perfil in f["semana"]:
                dia[w] += f["q"] * float(np.mean(perfil)) / Q
        if not op["mes"] and dia.max() - dia.min() > 0.02:
            t += f" De lunes a viernes, el {_num(100 * dia[:5].mean(), 0)} % de media; el fin de semana, el {_num(100 * dia[5:].mean(), 0)} %."
        por_dia = [(fecha, v) for fecha, v in op["dias"] if v is not None]
        d_hi, d_lo = max(v for _, v in por_dia), min(v for _, v in por_dia)
        if op["mes"] and d_hi - d_lo > 0.02:
            t += (f" Por días, el {_num(100 * d_hi, 0)} %, salvo {_dias(f for f, v in por_dia if v <= d_lo + 0.1 * (d_hi - d_lo))} "
                  f"({_num(100 * d_lo, 0)} %).")
    salen.append(("Cómo funciona la planta con este plan", t))
    # 2. quién emite
    con_plan = {f["id"]: f["q"] * f["media"] for f in focos}
    Qp = sum(con_plan.values()) or 1.0
    por_modelo = {}
    for f in focos:
        por_modelo.setdefault(f.get("modelo") or "", []).append(f)
    partes = []
    for mod, fs in sorted(por_modelo.items(), key=lambda x: -sum(con_plan[f["id"]] for f in x[1])):
        fs = [f for f in fs if con_plan[f["id"]] > 0]           # los que no emiten con el plan no cuentan
        q = sum(con_plan[f["id"]] for f in fs)
        if q <= 0:
            continue
        nombre = F.MODELOS.get(mod, mod or "sin modelo").lower()
        if q >= Qp * 0.9999:                                    # todo de un tipo: «sale de los 4 focos de superficie»
            solo = f"de los {len(fs)} focos de {nombre}" if len(fs) > 1 else f"del foco de {nombre} ({e(_min(fs[0]['nombre']))})"
        pct = '< 1' if 0 < q / Qp < 0.005 else _num(100 * q / Qp, 0)
        if not partes:                                          # el primero, con su verbo: «los 4 focos de superficie dan el 88 %»
            partes.append(f"los {len(fs)} focos de {nombre} dan el {pct} %" if len(fs) > 1 else
                          f"el foco de {nombre} ({e(_min(fs[0]['nombre']))}) da el {pct} %")
        else:                                                   # los demás, sin él: «y los 4 de volumen, el 12 %»
            partes.append(f"los {len(fs)} de {nombre}, el {pct} %" if len(fs) > 1 else f"el de {nombre} ({e(_min(fs[0]['nombre']))}), el {pct} %")
    if len(partes) == 1 and not uno:
        t = f"Todo el olor que emite la planta con el plan sale {solo}. "
    else:
        t = "" if uno else f"Del olor que emite la planta con el plan, {y_lista(partes)}. "
    top, suma = [], 0.0
    for f in sorted(focos, key=lambda f: -con_plan[f["id"]]):
        top.append(f)
        suma += con_plan[f["id"]]
        if suma / Qp > 0.5:
            break
    cat = {f["id"]: f for f in d["focos"]["focos"]}
    alturas = [float(cat.get(f["id"], {}).get("altura_m") or 0.0) for f in top]
    if uno or (len(top) == 1 and suma >= Qp * 0.9999):        # uno solo emite: ya está dicho quién
        quien = f"{e(top[0]['nombre'])} lo da todo" if uno else ""
    else:
        quien = (f"{e(y_lista(f['nombre'] if k == 0 else _min(f['nombre']) for k, f in enumerate(top)))} "
                 f"{'dan' if len(top) > 1 else 'da'} el {_num(100 * suma / Qp, 0)} %")
    t += quien
    if all(cat.get(f["id"], {}).get("modelo") != "punto" for f in top) and max(alturas) <= 10.0:
        if max(alturas) <= 0.5:
            alto_txt = "a ras de suelo"
        elif min(alturas) <= 0.5:
            alto_txt = f"a ras de suelo o a poca altura (hasta {_num(max(alturas), 1)} m)"
        else:
            alto_txt = f"a poca altura (hasta {_num(max(alturas), 1)} m)"
        frase = (f"{'sale' if len(top) == 1 else 'salen'} {alto_txt}, sin la elevación ni el empuje de una chimenea, y su olor suele ser el que "
                 "más pesa en los receptores cercanos.")
        t += f": {frase}" if quien else frase[:1].upper() + frase[1:]
    elif quien:
        t += "."
    salen.append(("Quién emite el olor", t))
    if n > 10:
        return salen
    # 3. cómo entra en el cálculo
    dd = r["datos"]
    anios = dd["ini"][:4] if dd["ini"][:4] == dd["fin"][:4] else f"{dd['ini'][:4]}–{dd['fin'][:4]}"
    t = (f"La simulación aplica el plan hora a hora a las {_num(dd['horas'])} horas del reanálisis ({anios}): en cada hora, "
         f"cada foco emite lo que dice su plan, en hora oficial, y su olor se reparte con el viento de esa hora. El calendario de arriba es el de "
         f"{op['anio']}; los demás años siguen el mismo plan.")
    salen.append(("Cómo entra en el cálculo", t))
    # 4. de dónde sale el olor de cada foco
    con_olor = [cat[f["id"]] for f in focos if f["id"] in cat and F.olor_ouE_s(cat[f["id"]])]
    medidos = [f for f in con_olor if F.olor_medido(f) is not None]
    estimados = [f for f in con_olor if F.olor_medido(f) is None]
    gases = sorted({F.NOMBRES.get(g[1], g[1]) for f in estimados if (g := F.gas_dominante(f))})
    if not estimados:
        t = f"El olor {'del foco' if len(con_olor) == 1 else f'de los {len(con_olor)} focos'} es el medido por olfatometría, en ou_E."
    else:
        de = (f"El {'del foco' if len(estimados) == 1 else f'de los {len(estimados)} focos'}" if not medidos else
              f"El de {len(medidos)} {'foco' if len(medidos) == 1 else 'focos'} es el medido por olfatometría; el de {'el otro' if len(estimados) == 1 else f'los otros {len(estimados)}'}")
        t = (f"{de} está estimado por sus gases ({e(y_lista(gases, ' o '))}) con su umbral de olor (Nagata, 2003), no medido por olfatometría: "
             "cuando haya medidas, basta con ponerlas en cada foco y volver a simular.")
    salen.append(("De dónde sale el olor de cada foco", t))
    return salen


def hora_local(hora):
    """«aaaa-mm-dd HH» de la serie del viento (UTC) → («d/m/aaaa», «H:00»), en hora oficial."""
    import pandas as pd
    from teodors.operacion import planes as E
    t = pd.Timestamp(hora[:13] + ":00").tz_localize("UTC").tz_convert(E.zona())
    return f"{t.day}/{t.month}/{t.year}", f"{t.hour}:00"


def a_las(hora):
    """«a las 5:00», «a la 1:00»."""
    return f"a la {hora}" if hora.startswith("1:") else f"a las {hora}"


def _r8(grados):
    """Grados (de dónde sopla) → uno de los 8 rumbos."""
    return ("N", "NE", "E", "SE", "S", "SO", "O", "NO")[int(((float(grados) + 22.5) % 360.0) // 45.0)]


def _grados(rumbo16):
    from teodors.operacion import viento_mapa as VM
    return VM.RUMBOS.index(rumbo16) * 22.5


def meteo_estaciones(d):
    """Lo que cuenta la página de las rosas: el viento en la planta (el del reanálisis) frente a la estación más cercana, y el de las
    estaciones de la zona: de dónde sopla en cada una, sus calmas y dónde hay más viento fuerte. [(título, HTML)]."""
    me = d["meteo"]
    p = me["planta"]
    est = (me.get("estaciones") or {}).get("lista", [])
    salen = []
    t = (f"El viento del reanálisis ({p['desde'][:4]}–{p['hasta'][:4]}, el de la capa más baja del viento 3D) sopla en la planta sobre todo "
         f"del <b>{p['dominante']}</b>: el {_num(p['dominante_pct'], 0)} % de las horas con viento. De media, "
         f"{_num(p['media'], 1)} m/s; calmas (menos de 0,5 m/s), el {_num(p['calmas'], 0)} % de las horas; la hora de más viento, "
         f"{_num(p['maxima'], 1)} m/s.")
    if est:
        c = est[0]
        igual = _r8(c["dominante_grados"]) == _r8(_grados(p["dominante"]))
        t += (f" La estación más cercana, {e(c['nombre'])}, a {km_txt(c['km'])} al {c['desde_planta']}, lo mide sobre todo del {c['dominante']}"
              + (": como en la planta." if igual else ": no es el mismo sitio, y el relieve de cada uno lo encauza a su manera."))
    salen.append(("El viento en la planta", t))
    if est:
        n = len(est)
        grupos = {}
        for s in est:
            grupos.setdefault(_r8(s["dominante_grados"]), []).append(s)
        orden = sorted(grupos.items(), key=lambda x: -len(x[1]))
        partes = [f"en {len(ss)}, del {r} ({e(y_lista(s['nombre'] for s in ss))})" if len(ss) > 1 else f"en {e(ss[0]['nombre'])}, del {r}"
                  for r, ss in orden[:4]]
        if len(orden) > 4:
            partes.append(f"en {sum(len(ss) for _, ss in orden[4:])} más, de otros rumbos")
        alturas = sorted({round(s["altura"]) for s in est if s.get("altura")})
        a_txt = ("" if not alturas else f" a {_num(alturas[0])} m del suelo" if len(alturas) == 1 else
                 f" a entre {_num(alturas[0])} y {_num(alturas[-1])} m del suelo")
        t = (f"{'La estación' if n == 1 else f'Las {n} estaciones'} de la zona, de {km_txt(min(s['km'] for s in est))} a "
             f"{km_txt(max(s['km'] for s in est))} de la planta, miden el viento{a_txt}. El más frecuente sopla {y_lista(partes, '; y ').replace(', en ', '; en ')}.")
        if n > 1:
            calma_lo, calma_hi = min(est, key=lambda s: s["calmas"]), max(est, key=lambda s: s["calmas"])
            fuerte = max(est, key=lambda s: s["fuerte"])
            t += (f" Las calmas van del {_num(calma_lo['calmas'], 0)} % de las horas en {e(calma_lo['nombre'])} al {_num(calma_hi['calmas'], 0)} % en "
                  f"{e(calma_hi['nombre'])}, la más resguardada; el viento de 8 m/s o más es más frecuente en {e(fuerte['nombre'])} "
                  f"({_num(fuerte['fuerte'], 1)} % de las horas).")
        salen.append(("El viento en las estaciones", t))
    return salen


ORDINALES = ("", "segunda ", "tercera ", "cuarta ")
NUMEROS = {2: "dos", 3: "tres", 4: "cuatro"}


def situaciones(eventos):
    """Las situaciones del viento de `datos.eventos_viento`, en el orden del informe (las frecuentes, de la que más a la que menos, y la
    extrema): [(clave de sus imágenes, título, evento)]."""
    fr = eventos["frecuentes"]
    return ([(f"frecuente{k + 1}", f"La {ORDINALES[k] if k < len(ORDINALES) else f'{k + 1}.ª '}más frecuente", f) for k, f in enumerate(fr)]
            + [("extremo", "La más extrema", eventos["extremo"])])


def _frecuentes(fr):
    """El párrafo de las situaciones más frecuentes: de qué rumbos sopla más, qué día se eligió cada una y hacia dónde va el olor."""
    f = fr[0]
    if len(fr) == 1:
        fd, fh = hora_local(f["hora"])
        return (f"El viento del {f['rumbo_dominante']} es el que más sopla en la planta ({_num(f['pct'], 0)} % de las horas con viento), con "
                f"{_num(f['tipica'], 1)} m/s de velocidad típica. El {fd} sopló así {f['horas_dia']} de las 24 horas; {a_las(fh)}, "
                f"{_num(f['ws'], 1)} m/s del {f['rumbo']}. Es la situación más habitual: el olor de la planta va hacia el "
                f"{_r8((f['wd'] + 180.0) % 360.0)}.")
    t = (f"El viento del {f['rumbo_dominante']} es el que más sopla en la planta ({_num(f['pct'], 0)} % de las horas con viento, con "
         f"{_num(f['tipica'], 1)} m/s de velocidad típica); después, "
         + y_lista([f"el del {g['rumbo_dominante']} ({_num(g['pct'], 0)} %, {_num(g['tipica'], 1)} m/s)" for g in fr[1:]]) + ". ")
    cuando = [hora_local(g["hora"]) for g in fr]
    t += (y_lista([f"El {cuando[0][0]} sopló del {f['rumbo_dominante']} {f['horas_dia']} de las 24 horas"]
                  + [f"el {c[0]}, del {g['rumbo_dominante']}, {g['horas_dia']}" for c, g in zip(cuando[1:], fr[1:])], ", y ")
          + "; en los mapas, " + y_lista([f"{a_las(c[1])} ({_num(g['ws'], 1)} m/s)" for c, g in zip(cuando, fr)]) + ". ")
    hacia = list(dict.fromkeys(_r8((_grados(g["rumbo_dominante"]) + 180.0) % 360.0) for g in fr))
    entre = "los dos" if len(fr) == 2 else f"los {NUMEROS.get(len(fr), len(fr))}"
    t += (f"Entre {entre}, el {_num(sum(g['pct'] for g in fr), 0)} % de las horas con viento: lo más habitual es que el olor de la planta vaya "
          f"hacia el {y_lista(hacia, ' o el ')}.")
    if len(fr) == 2:
        lento, rapido = sorted(fr, key=lambda g: g["tipica"])
        if rapido["tipica"] >= 1.5 * lento["tipica"]:
            t += (f" El del {rapido['rumbo_dominante']} sopla más fuerte y diluye antes el olor; con el del {lento['rumbo_dominante']}, más flojo, "
                  "llega más concentrado.")
    return t


def meteo_situaciones(d):
    """Lo que cuenta la página del viento en el mapa: las situaciones más frecuentes y la más extrema, y de cerca. [(título, HTML)]."""
    me = d["meteo"]
    fr, x = me["eventos"]["frecuentes"], me["eventos"]["extremo"]
    xd, xh = hora_local(x["hora"])
    anios = f"{me['planta']['desde'][:4]}–{me['planta']['hasta'][:4]}"
    return [
        ("Arriba, la más frecuente" if len(fr) == 1 else f"Arriba, las {NUMEROS.get(len(fr), len(fr))} más frecuentes", _frecuentes(fr)),
        ("Abajo, la más extrema",
         f"La hora de más viento en la planta en {anios}: el {xd} {a_las(xh)}, {_num(x['ws'], 1)} m/s del {x['rumbo']}. Con tanto viento el "
         "olor se diluye enseguida; lo que más suele molestar es lo contrario: viento flojo y aire estable, de noche."),
        ("A la derecha, de cerca",
         "Alrededor de la planta, el viento es el de su propio cálculo, que tiene en cuenta sus edificios: el aire los rodea y deja estelas "
         "detrás. Más lejos, el viento 3D de la zona, que sigue el relieve. Las líneas van hacia donde sopla el viento; abajo a la izquierda de "
         "cada mapa, su velocidad media y máxima en lo que se ve, a esa hora."),
    ]


def _decenas(x):
    """«unos 170 m», «unos 830 m»: a la decena (a la unidad, por debajo de 100)."""
    return _num(round(x, -1) if x >= 100 else round(x), 0)


def _h(par):
    return f"de {par[0]} a {par[1]} h"


def clima_cifras(r):
    """Lo que dice cada gráfica del tiempo en la planta, bajo su título (`datos.clima`, su resumen): {clave: texto}."""
    t, ll, n, rad, pr, m, v = r["t"], r["lluvia"], r["nubes"], r["radiacion"], r["presion"], r["mezcla"], r.get("viento")
    por = ll["por_anio"]
    mx, mn = int(np.nanargmax(rad["por_mes"])), int(np.nanargmin(rad["por_mes"]))
    salen = {"temperatura": f"media {_num(t['media'], 1)} °C · de {_num(t['min'], 1)} a {_num(t['max'], 1)} °C",
             "humedad": f"media {_num(r['humedad'], 0)} %",
             "nubes": f"media {_num(n['media'], 0)} % · el {_num(n['despejados'], 0)} % de los días, despejado",
             "lluvia": f"{_num(sum(por.values()) / max(len(por), 1), 0)} mm al año · {_num(ll['dias_anio'], 0)} días de lluvia al año",
             "radiacion": (f"media {_num(rad['media'], 0)} W/m² · en {MESES_LARGOS[mx]}, {_num(rad['por_mes'][mx], 0)}; en {MESES_LARGOS[mn]}, "
                           f"{_num(rad['por_mes'][mn], 0)}"),
             "presion": f"media {_num(pr['media'], 0)} hPa · la más baja, {_num(pr['min'], 0)}",
             "friccion": f"media {_num(m['friccion'], 2)} m/s · de noche {_num(m['friccion_noche'], 2)}, de día {_num(m['friccion_dia'], 2)}",
             "calor": f"negativo (aire estable) el {_num(m['estable'], 0)} % de las horas",
             "mezcla": f"de noche, unos {_decenas(m['noche'])} m; de día, unos {_decenas(m['dia'])} m"}
    if v:
        salen["viento"] = f"media {_num(v['media'], 1)} m/s · de noche {_num(v['noche'], 1)}, de día {_num(v['dia'], 1)}"
        if v["dom_noche"] and v["dom_dia"]:
            salen["direccion"] = f"de noche, sobre todo del {v['dom_noche']['rumbo']}; de día, del {v['dom_dia']['rumbo']}"
    return salen


def meteo_clima(d):
    """El texto final de la meteorología (usuario, 2026-11-10: «un texto final describiendo toda esta meteo, narrativa»), de `datos.clima`: el
    tiempo en la planta, su viento de día y de noche, la mezcla del aire y las horas que más pesan para el olor. [(título, HTML)]."""
    c = d["meteo"]["era5"]
    r, p = c["resumen"], c.get("punto")
    hs = r["horas"]
    anios = f"{r['desde'].year}–{r['hasta'].year}"
    salen = []
    # 1. el tiempo
    t, ll, n, pr = r["t"], r["lluvia"], r["nubes"], r["presion"]
    mf, mc = int(np.nanargmin(t["por_mes"])), int(np.nanargmax(t["por_mes"]))
    donde = (f", en su celda más cercana a la planta (a {km_txt(p['dist_planta_m'] / 1000.0)} al {p['rumbo_desde_planta']}, con el suelo del "
             f"modelo a {_num(p['cota_modelo_m'], 0)} m)" if p else "")
    por = ll["por_anio"]
    seco, humedo = min(por, key=por.get), max(por, key=por.get)
    tx = (f"Según el ERA5{donde}, en {anios} la temperatura media es de {_num(t['media'], 1)} °C: de {_num(t['por_mes'][mf], 1)} °C de media en "
          f"{MESES_LARGOS[mf]} a {_num(t['por_mes'][mc], 1)} °C en {MESES_LARGOS[mc]}, con extremos de {_num(t['min'], 1)} °C (el {t['min_dia']}) y "
          f"{_num(t['max'], 1)} °C (el {t['max_dia']}); la humedad relativa, del {_num(r['humedad'], 0)} % de media. Llueven de media "
          f"{_num(sum(por.values()) / len(por), 0)} mm al año, en unos {_num(ll['dias_anio'], 0)} días con 1 mm o más")
    if len(por) > 1 and por[humedo] > 1.5 * por[seco]:
        tx += f", pero cambia mucho de un año a otro: {_num(por[seco], 0)} mm en {seco} y {_num(por[humedo], 0)} mm en {humedo}"
    tx += (f"; el día de más lluvia, el {ll['max_dia']}, {_num(ll['max'], 0)} mm. Las nubes cubren de media el {_num(n['media'], 0)} % del cielo: "
           f"el {_num(n['despejados'], 0)} % de los días está casi despejado, y el {_num(n['cubiertos'], 0)} %, casi cubierto. La presión en el suelo "
           f"es de {_num(pr['media'], 0)} hPa de media; la más baja, {_num(pr['min'], 0)} hPa, el {pr['min_dia']}.")
    salen.append(("El tiempo en la planta", tx))
    # 2. el viento, de día y de noche
    v = r.get("viento")
    if v and v["dom_noche"] and v["dom_dia"]:
        dn, dd = v["dom_noche"], v["dom_dia"]
        tx = (f"El viento de la planta (el del viento 3D, el de las rosas) sopla de noche ({_h(hs['noche'])}) sobre todo del {dn['rumbo']} "
              f"({_num(dn['pct'], 0)} % de esas horas con viento), y de día ({_h(hs['dia'])}), del {dd['rumbo']} ({_num(dd['pct'], 0)} %)")
        giro = abs((dn["grados"] - dd["grados"] + 180.0) % 360.0 - 180.0)
        tx += (": gira con el día, como una brisa que cambia de sentido de la noche al día." if giro >= 112.5 else ".")
        vd, vn = v.get("dom_verano_dia"), v.get("dom_invierno_noche")
        if vd and vn:
            tx += (f" En verano, de día, el del {vd['rumbo']} llega al {_num(vd['pct'], 0)} % de las horas; en invierno, de noche, el del "
                   f"{vn['rumbo']}, al {_num(vn['pct'], 0)} %.")
        tx += (f" De media, {_num(v['invierno'], 1)} m/s en invierno y {_num(v['verano'], 1)} m/s en verano; {_num(v['noche'], 1)} m/s de noche y "
               f"{_num(v['dia'], 1)} m/s de día.")
        salen.append(("El viento, de día y de noche", tx))
    # 3. la mezcla del aire
    m, rad = r["mezcla"], r["radiacion"]["por_mes"]
    mx, mn = int(np.nanargmax(rad)), int(np.nanargmin(rad))
    tx = (f"De día el sol calienta el suelo (la radiación solar es de {_num(rad[mx], 0)} W/m² de media en {MESES_LARGOS[mx]} y de "
          f"{_num(rad[mn], 0)} en {MESES_LARGOS[mn]}), el aire sube y se mezcla hasta unos {_decenas(m['dia'])} m de altura (la media "
          f"{_h(hs['dia'])}). De noche el suelo se enfría y el aire queda estable el {_num(m['estable_noche'], 0)} % de las horas "
          f"({_h(hs['noche'])}): la capa de mezcla baja a unos {_decenas(m['noche'])} m (la mediana), y la velocidad de fricción, la "
          f"turbulencia que hace el viento al rozar el suelo, pasa de {_num(m['friccion_dia'], 2)} m/s de día a {_num(m['friccion_noche'], 2)} de "
          "noche. Cuanto más baja la capa y más estable el aire, menos se diluye el olor.")
    salen.append(("La mezcla del aire", tx))
    # 4. lo que pesa para el olor
    f = r.get("dificil")
    if f:
        pm = f["por_mes"]
        mx, mn = int(np.nanargmax(pm)), int(np.nanargmin(pm))
        noche = (f"casi todas de noche (el {_num(f['noche'], 0)} %, {_h(hs['noche_larga'])})" if f["noche"] >= 75 else
                 f"sobre todo de noche (el {_num(f['noche'], 0)} %, {_h(hs['noche_larga'])})" if f["noche"] >= 50 else
                 f"de día y de noche (de noche, el {_num(f['noche'], 0)} %)")
        tx = (f"Las horas más difíciles para el olor son las de viento flojo (menos de {_num(f['viento'], 1)} m/s), aire estable y capa de "
              f"mezcla baja (menos de {_num(f['mezcla'], 0)} m): el olor apenas se diluye y se queda cerca del suelo. Son el "
              f"{_num(f['pct'], 0)} % de las horas, {noche}, y hay más en {MESES_LARGOS[mx]} (el {_num(pm[mx], 0)} % de sus horas) que en "
              f"{MESES_LARGOS[mn]} ({_num(pm[mn], 0)} %).")
        if f.get("dominante"):
            dm = f["dominante"]
            tx += (f" En esas horas el viento sopla sobre todo del {dm['rumbo']} ({_num(dm['pct'], 0)} % de ellas): el olor de la planta va "
                   f"entonces hacia el {rumbo16((dm['grados'] + 180.0) % 360.0)}.")
        salen.append(("Lo que más pesa para el olor", tx))
    return salen


# ── 4 · Resultados ──
ESTADISTICOS = (("media", "Media"), ("maximo", "Máximo horario"), ("p98", "P98"))


AIRE_ESTABLE, AIRE_INESTABLE = -1.0, 25.0          # W/m² de calor sensible (hacia arriba): por debajo, estable; por encima, inestable


def aire_txt(H):
    """El aire por su calor sensible hacia arriba (W/m²): «estable», «casi neutro» o «inestable»."""
    return "estable" if H < AIRE_ESTABLE else "inestable" if H > AIRE_INESTABLE else "casi neutro"


def horas_txt(h):
    """«unas 85 horas», «1,5 horas», «menos de una hora», «ninguna»."""
    if h <= 0:
        return "ninguna"
    if h < 1:
        return "menos de una hora"
    return f"unas {_num(round(h))} horas" if h >= 10 else f"{_num(h, 1)} horas"


def resultados_mapas(d):
    """Lo que cuenta la página de los mapas del olor: hasta dónde llega cada estadístico por encima de cada umbral, y lo que vale en el
    pueblo más afectado y en la vivienda más expuesta. [(título, HTML)]."""
    m, al, horas = d["mag"], d["alcances"], d["res"]["datos"]["horas"]
    u = e(m["unidad"])
    pueblos, viv = d["pueblos"], d.get("vivienda")
    que = {"media": f"La media de las {_num(horas)} horas", "maximo": "El máximo horario, lo peor de una sola hora en cada sitio,",
           "p98": f"El P98, lo que se pasa el 2 % de las horas (unas {_num(round(0.02 * 8766))} al año),"}
    salen = []
    for clave, titulo in ESTADISTICOS:
        a = al.get(clave)
        if not a:
            continue
        partes = [f"de {_num(c['umbral'])} {u} en {_num(c['km2'], 2)} km², hasta {km_txt(c['hasta_km'])} al {c['rumbo']}" for c in a
                  if c["hasta_km"] is not None]
        junto = "; ".join(partes[:-1]) + "; y " + partes[-1] if len(partes) > 1 else "".join(partes)
        t = (f"{que[clave]} pasa {junto}." if partes else
             f"{que[clave]} no pasa de {_num(a[0]['umbral'])} {u} en ningún sitio de la zona de cálculo.")
        if pueblos:
            p = max(pueblos, key=lambda f: f.get(clave, 0.0))
            t += f" En el pueblo donde más, {e(p['nombre'])}, {ci(p[clave])} {u}"
            t += f"; en la vivienda más expuesta, {ci(viv[clave])} {u}." if viv and clave in viv else "."
        salen.append((titulo, t))
    salen.append(("Cómo se leen", "Cada franja de color, un tramo de concentración (la leyenda, debajo de los mapas). La media es el olor de fondo; "
                  "el máximo, lo peor que llega a pasar en una hora suelta, y el que más lejos llega; el P98, el criterio habitual para el olor. "
                  f"1 {u} es el umbral de detección; 3 y 5 {u}, las referencias habituales para valorar la molestia."))
    return salen


def cuando(d):
    """Lo que cuenta la página de cuándo se huele en los pueblos (`datos.horas_pueblos`): cuántas horas y días, cuándo (de noche, en qué
    meses, a qué hora) y los peores días con su viento y su aire. [(título, HTML)]."""
    h = d["horas"]
    lug = h["lugares"]
    pueblos = [f for f in lug if f["tipo"] == "pueblo"]
    con = [f for f in pueblos if f["horas"][0] > 0]
    salen = []
    if con:
        p = con[0]
        km = f" (a {km_txt(p['km'])})" if p.get("km") is not None else ""
        t = (f"En {e(p['nombre'])}{km} el olor pasa de 1 ou_E/m³ {horas_txt(p['horas'][0])} al año, en unos {_num(p['dias'], 0 if p['dias'] >= 10 else 1)} "
             f"días; de 3, {horas_txt(p['horas'][1])}, y de 5, {horas_txt(p['horas'][2])}.")
        if len(con) > 1:
            t += " Le " + ("sigue " if len(con) == 2 else "siguen ") + y_lista([f"{e(f['nombre'])} ({horas_txt(f['horas'][0])})" for f in con[1:4]]) + "."
        sin = len(pueblos) - len(con)
        if sin:
            t += f" En {'el otro pueblo' if sin == 1 else f'los otros {sin} pueblos'} no pasa de 1 ou_E/m³ ni una hora."
    else:
        t = "En ningún pueblo pasa el olor de 1 ou_E/m³, ni una sola hora."
    viv = next((f for f in lug if f["tipo"] == "vivienda"), None)
    if viv:
        t += (f" En la vivienda más expuesta, {horas_txt(viv['horas'][0])} al año por encima de 1 ou_E/m³; su peor hora, "
              f"{ci(viv['peor']['valor'])} ou_E/m³, el {viv['peor']['dia']} {a_las(viv['peor']['hora'])}.")
    salen.append(("Cuántas horas", t))
    todos = h.get("todos")
    if todos and todos["horas"] > 0:
        M = np.array(todos["M"])
        por_mes, por_hora = M.sum(axis=1), M.sum(axis=0)
        top = sorted(int(k) for k in np.argsort(-por_mes)[:3] if por_mes[k] > 0)          # en el orden del calendario
        pct = 100 * por_mes[top].sum() / por_mes.sum()
        hp = int(np.argmax(por_hora))
        noche = todos["noche"]
        cuando_txt = (f"casi siempre de noche (el {_num(noche, 0)} %, de 20 a 8 h)" if noche >= 75 else
                      f"sobre todo de noche (el {_num(noche, 0)} %, de 20 a 8 h)" if noche >= 50 else
                      f"más de día que de noche (de noche, de 20 a 8 h, el {_num(noche, 0)} %)")
        t = (f"Contando todos los pueblos, alguno pasa de 1 ou_E/m³ {horas_txt(todos['horas'])} al año: {cuando_txt}, y más en "
             f"{y_lista([MESES_LARGOS[k] for k in top])} (el {_num(pct, 0)} % de esas horas). La hora del día en que más, {a_las(f'{hp}:00')}. "
             "Es lo que se ve en los mapas de calor, mes a mes y hora a hora.")
        salen.append(("Cuándo", t))
    peores = h.get("peores") or []
    if peores:
        p0 = peores[0]
        t = f"El peor día, el {p0['dia']}: {ci(p0['valor'])} ou_E/m³ en {e(p0['pueblo'])} {a_las(p0['hora'])}"
        if p0.get("ws") is not None:
            t += f", con viento de {_num(p0['ws'], 1)} m/s del {p0['rumbo']} en la planta"
        if p0.get("H") is not None:
            t += f", aire {aire_txt(p0['H'])}" + (f" y la capa de mezcla a {_decenas(p0['blh'])} m" if p0.get("blh") is not None else "")
        t += "."
        con_v = [p for p in peores if p.get("ws") is not None]
        if len(con_v) > 1:
            flojos = sum(p["ws"] < 1.5 for p in con_v)
            rumbos = {}
            for p in con_v:                                        # en 8 rumbos: con pocos días, 16 los dispersan
                rumbos[_r8(p["wd"])] = rumbos.get(_r8(p["wd"]), 0) + 1
            r0 = max(rumbos, key=rumbos.get)
            de_donde = (f"sopla sobre todo del {r0} ({rumbos[r0]} de ellos)" if 2 * rumbos[r0] >= len(con_v) else
                        f"sopla de rumbos distintos, más del {r0} ({rumbos[r0]})")
            t += f" En los {len(peores)} peores días, el viento en la planta es flojo (menos de 1,5 m/s) en {flojos} y {de_donde}"
            estables = [p for p in con_v if p.get("H") is not None]
            if estables:
                t += f"; el aire, estable en {sum(aire_txt(p['H']) == 'estable' for p in estables)}"
            t += ": las horas difíciles para el olor de la meteorología."
        if any(p.get("origen") for p in peores):
            t += (" La serie es de prueba (unas semanas simuladas, copiadas en los 5 años): cada peor día sale una vez por día simulado, con "
                  "el viento y el aire del simulado del que se copió, el que dio ese olor.")
        salen.append(("Los peores días", t))
    return salen


# ── el informe de la comparación de dos escenarios (usuario, 2026-11-10) ──
def escenario(d, letra):
    """«A · Base»: la letra y el nombre del plan del escenario."""
    return f"{letra} · {d['res']['nombre'] or 'Base'}"


def _cambio_txt(a, b, dec=0, unidad=""):
    """«de 5,12 a 3,40 km² (−34 %)»; si no cambia, «igual (5,12 km²)»."""
    u = f" {unidad}" if unidad else ""
    if abs(b - a) <= 1e-9 * max(abs(a), 1.0):
        return f"igual ({_num(a, dec)}{u})"
    pct = f" ({'+' if b > a else '−'}{_num(abs(100 * (b - a) / a), 0)} %)" if a > 0 else ""
    return f"de {_num(a, dec)} a {_num(b, dec)}{u}{pct}"


def _punto_y_coma(partes):
    """«a; b; y c»."""
    partes = [p for p in partes if p]
    return partes[0] if len(partes) == 1 else "; ".join(partes[:-1]) + "; y " + partes[-1] if partes else ""


def operacion_comparada(dc):
    """Lo que cuenta la página de la operación de los dos escenarios: cuánto emite la planta con cada plan, qué focos cambian y cuánto pesan.
    [(título, HTML)]."""
    a, b, op = dc["a"], dc["b"], dc["op"]
    na, nb = e(a["res"]["nombre"] or "Base"), e(b["res"]["nombre"] or "Base")
    ea, eb = op["a"]["emite"], op["b"]["emite"]
    salen = []
    t = (f"Con el plan «{na}», la planta emite de media {_num(ea)} ou_E/s, el {_num(100 * op['a']['media'], 0)} % de lo que emitiría con "
         f"todos los focos al 100 %; con «{nb}», {_num(eb)} ou_E/s (el {_num(100 * op['b']['media'], 0)} %)")
    if abs(eb - ea) <= 1e-6 * max(ea, 1.0):
        t += ": lo mismo."
    else:
        t += f": un {_num(abs(100 * (eb - ea) / ea), 0)} % {'menos' if eb < ea else 'más'} que con «{na}»." if ea > 0 else "."
    salen.append(("Lo que emite la planta", t))
    cambian = [f for f in op["focos"] if not f["igual"]]
    if not cambian:
        salen.append(("Qué cambia", "Los dos planes hacen lo mismo con todos los focos: la diferencia entre los resultados, si la hay, no "
                      "viene de la operación."))
        return salen
    grupos = {}
    for f in cambian:
        clave = (None if f["a"] is None else round(100 * f["a"]), None if f["b"] is None else round(100 * f["b"]))
        grupos.setdefault(clave, []).append(f["nombre"])
    partes = []
    for (pa, pb), nombres in grupos.items():
        quien = e(_juntos(nombres))
        if pa is None:
            partes.append(f"{quien}, solo en «{nb}» (al {pb} % de media)")
        elif pb is None:
            partes.append(f"{quien}, solo en «{na}» (al {pa} % de media)")
        elif pa == pb:
            partes.append(f"{quien}, con otro reparto en el día o la semana, pero la misma media ({pa} %)")
        else:
            partes.append(f"{quien}, del {pa} % al {pb} % de media")
    iguales = len(op["focos"]) - len(cambian)
    t = (f"{'Cambia' if len(cambian) == 1 else 'Cambian'} {y_lista(partes, '; y ')}." +
         (f" {'El otro foco opera' if iguales == 1 else f'Los otros {iguales} focos operan'} igual en los dos." if iguales else ""))
    salen.append(("Qué cambia", t))
    peso_a = sum(f["q"] * f["a"] for f in cambian if f["a"] is not None)
    if ea > 0 and peso_a > 0:
        salen.append(("Cuánto pesa", f"Con «{na}», {'ese foco da' if len(cambian) == 1 else 'esos focos dan'} el "
                      f"{_num(100 * peso_a / ea, 0)} % del olor que emite la planta: es lo que mueve el cambio de plan. Lo que pase con el olor "
                      "fuera depende además de dónde está cada foco, de su altura y del viento: lo dicen los resultados de cada escenario y la "
                      "comparación, al final."))
    return salen


def comparacion(dc):
    """El texto final de la comparación: la superficie y el alcance por encima de cada umbral, los pueblos, las horas al año y cuántos
    receptores bajan o suben. [(título, HTML)]."""
    a, b, comp = dc["a"], dc["b"], dc["comp"]
    na, nb = e(a["res"]["nombre"] or "Base"), e(b["res"]["nombre"] or "Base")
    u = e(a["mag"]["unidad"])
    salen = []
    ca, cb = a.get("criterios") or [], b.get("criterios") or []
    if ca and cb:
        partes = [f"{'de ' + _num(x['umbral']) + ' ' + u + ' pasa' if k == 0 else 'de ' + _num(x['umbral']) + ','} "
                  f"{_cambio_txt(x['km2'], y['km2'], 2, 'km²')}" for k, (x, y) in enumerate(zip(ca, cb))]
        t = f"La superficie con P98 por encima {_punto_y_coma(partes)}."
        x, y = ca[0], cb[0]
        if x["hasta_km"] is not None and y["hasta_km"] is not None and abs(x["hasta_km"] - y["hasta_km"]) >= 0.05:
            t += f" Por encima de {_num(x['umbral'])} {u}, llega hasta {km_txt(x['hasta_km'])} con «{na}» y hasta {km_txt(y['hasta_km'])} con «{nb}»."
        r = dc.get("receptores")
        if r:
            partes = [(r["bajan"], f"baja más de un 10 %"), (r["suben"], f"sube más de un 10 %"), (r["igual"], "apenas cambia (±10 %)")]
            partes = [(p, x) for p, x in partes if p >= 0.5]
            donde = f"Receptor a receptor, donde hay olor en alguno de los dos (más de {_num(r['umbral'], 2)} {u}), el P98 "
            if len(partes) == 1:
                t += f" {donde}{partes[0][1]} en prácticamente todos"
            else:
                t += f" {donde}" + y_lista([f"{x} en el {_num(p, 0)} %" for p, x in partes])
            t += f"; la mitad, más de un {_num(abs(r['mediana']), 0)} %." if abs(r["mediana"]) > 10 else "."
        salen.append(("En la zona", t))
    filas = (comp["magnitudes"].get("olor") or {}).get("pueblos") or []
    if filas:
        top = max(filas, key=lambda f: max(f["p98"][0], f["p98"][1]))
        t = (f"En el pueblo más afectado, {e(top['nombre'])}, el P98 pasa {_cambio_txt(top['p98'][0], top['p98'][1], 2, u)}, y su máximo horario, "
             f"{_cambio_txt(top['maximo'][0], top['maximo'][1], 1, u)}.")
        if ca and cb:
            def cuantos(clave, que):
                if not any(x[clave] or y[clave] for x, y in zip(ca, cb)):
                    return f"Ningún pueblo pasa de {_num(ca[0]['umbral'])} {u} {que} en ninguno de los dos."
                return (f"Pueblos que pasan de cada umbral {que}, con «{na}» y con «{nb}»: "
                        + _punto_y_coma([f"de {_num(x['umbral'])}, {x[clave]} y {y[clave]}" for x, y in zip(ca, cb)]) + ".")
            t += " " + cuantos("pueblos", "de P98") + " " + cuantos("pueblos_maximo", "en su peor hora")
        salen.append(("En los pueblos", t))
    ha, hb = a.get("horas"), b.get("horas")
    if ha and hb:
        en_b = {f["nombre"]: f for f in hb["lugares"]}
        parejas = [(f, en_b[f["nombre"]]) for f in ha["lugares"] if f["nombre"] in en_b and (f["horas"][0] > 0 or en_b[f["nombre"]]["horas"][0] > 0)]
        if parejas:
            def h(x):
                return "ninguna" if x <= 0 else "menos de una" if x < 1 else _num(x, 0 if x >= 10 else 1)
            partes = [f"en {e(x['nombre']) if x['tipo'] == 'pueblo' else 'la vivienda más expuesta'}, de {h(x['horas'][0])} a {h(y['horas'][0])}"
                      for x, y in parejas[:4]]
            salen.append(("Las horas al año", f"Las horas al año por encima de 1 {u}: {_punto_y_coma(partes)}."))
    return salen


def _nombres(fs, n_max=4):
    fs = list(fs)
    if len(fs) <= n_max:
        return y_lista(e(f["nombre"]) for f in fs)
    return f"{', '.join(e(f['nombre']) for f in fs[:n_max])} y {len(fs) - n_max} más"


def _sitio(d, f):
    dxy = d["donde"].get(f["nombre"])
    return f"a {km_txt(f['km'])} al {NOMBRE_RUMBO[rumbo8(*dxy)]}" if dxy else f"a {km_txt(f['km'])}"


def esencial(d):
    """Los cuatro párrafos de «Lo esencial del caso» (HTML): qué se simula y quién emite; los pueblos frente a los umbrales de olor; hasta
    dónde llega el olor y la vivienda y la zona industrial más expuestas; y los gases."""
    r, m, est, nom_est = d["res"], d["mag"], d["estadistico"], d["estadistico_nombre"]
    dd, caso, plan = r["datos"], r["caso"]["nombre"], r["nombre"] or "Base"
    unidad, es_olor = m["unidad"], m["clave"] == "olor"
    op = d["operacion"]
    # 1. qué se simula y quién emite
    focos = op["focos"]
    uno = len(focos) == 1
    Q = sum(f["q"] for f in focos) or 1.0
    emite = sorted(((f["q"] * f["media"], f) for f in focos), key=lambda x: -x[0])      # con el plan: lo que de verdad se simula
    Qp = sum(q for q, _ in emite) or 1.0
    top, suma = [], 0.0
    for q, f in emite:
        top.append(f)
        suma += q
        if suma / Qp > 0.5:
            break
    nombres_top = y_lista(f["nombre"] if k == 0 else _min(f["nombre"]) for k, f in enumerate(top))
    if op["al_100"]:
        con_plan = f"; con este plan, {'funciona' if uno else 'funcionan'} siempre así."
    elif op["constante"]:                                       # lo mismo todas las horas, pero no todo al 100 %: cuáles bajan y a cuánto
        bajan = [f for f in focos if f["media"] < 1.0]
        grupos = {}
        for f in sorted(bajan, key=lambda f: (f["media"], -f["q"])):
            grupos.setdefault(_num(100 * f["media"], 0), []).append(_min(f["nombre"]))
        cuales = ("" if uno else ": " + "; ".join(f"{e(y_lista(n))}, al {p} %" for p, n in grupos.items()) if len(bajan) <= 4 else
                  f": {len(bajan)} de ellos por debajo del 100 %")
        con_plan = (f"; con este plan, {'emite' if uno else 'emiten'} el {_num(100 * op['media'], 0)} % ({_num(op['q'] * op['media'])} ou_E/s), "
                    f"igual todas las horas{cuales}.")
    else:
        con_plan = f"; con este plan, el {_num(100 * op['media'], 0)} % de media, con cambios a lo largo del día o de la semana."
    p1 = (f"El caso «{e(caso)}» simula el plan de operación «{e(plan)}» en las {_num(dd['horas'])} horas del reanálisis, del {fecha(dd['ini'])} al "
          f"{fecha(dd['fin'])}. {'El foco emite' if uno else f'Los {len(focos)} focos emiten'} {_num(Q)} ou_E/s de olor con "
          f"{'él' if uno else 'todos'} al 100 %" + con_plan
          + ("" if uno else f" {e(nombres_top)} {'dan' if len(top) > 1 else 'da'} el {_num(100 * suma / Qp, 0)} % del olor"
             + ("." if op["al_100"] else " con el plan.")))
    # 2. los pueblos
    pueblos, crit = d["pueblos"], d["criterios"]
    if not pueblos:
        p2 = (f"En la zona de cálculo no hay pueblos: los resultados se dan en los receptores, alrededor de la planta. "
              f"El valor más alto de {e(m['nombre'].lower() if es_olor else m['nombre'])} es {ci(m['maximos'][est])} {e(unidad)} de "
              f"{e(nom_est)}, junto a los focos.")
    elif not es_olor:
        peor = pueblos[0]
        p2 = (f"El caso no tiene emisión de olor: se describe el {e(m['nombre'])}. El pueblo con más es <b>{e(peor['nombre'])}</b>, "
              f"{_sitio(d, peor)}, con {ci(peor[est])} {e(unidad)} de {e(nom_est)} y un máximo horario de {ci(peor['maximo'])}.")
    else:
        peor = pueblos[0]
        n1, n3, n5 = (c["pueblos"] for c in crit)
        maximo = f"y un máximo horario de {ci(peor['maximo'])}"
        siguen = "; le siguen " + y_lista(f"{e(f['nombre'])} ({ci(f['p98'])})" for f in pueblos[1:3]) if len(pueblos) > 2 else ""
        if n1 == 0:
            cerca = ("muy por debajo de 1" if peor["p98"] < 0.1 else "menos de la mitad de 1" if peor["p98"] < 0.5 else "cerca de 1, sin llegar")
            p2 = (f"<b>Ningún pueblo pasa de 1 ou_E/m³</b>, el más exigente de los umbrales de referencia habituales para el olor ({UMBRALES}). "
                  f"El más afectado es <b>{e(peor['nombre'])}</b>, {_sitio(d, peor)}, con {ci(peor['p98'])} ou_E/m³ de P98 ({cerca}) {maximo}{siguen}."
                  + _peor_hora(pueblos, crit))
        else:
            t_, n_t = next((u, n_) for u, n_ in ((5, n5), (3, n3), (1, n1)) if n_ > 0)
            p2 = f"<b>{n_t} {'pueblo pasa' if n_t == 1 else 'pueblos pasan'} de {t_} ou_E/m³ de P98</b>" + (f" ({_nombres(pueblos[:n_t])})" if n_t > 1 else "")
            p2 += {1: f", el más exigente de los umbrales de referencia habituales para el olor ({UMBRALES}), aunque ninguno llega a 3",
                   3: f", el intermedio de los umbrales de referencia habituales para el olor ({UMBRALES}), aunque ninguno llega a 5",
                   5: f", el menos exigente de los umbrales de referencia habituales para el olor ({UMBRALES}): con este plan, el olor de la planta "
                      f"podría molestar en {'él' if n_t == 1 else 'ellos'}"}[t_]
            otros = [f"{n_} de {u}" for u, n_ in ((3, n3), (1, n1)) if u < t_ and n_ > n_t]
            if otros:
                otros[0] = otros[0].replace(" de ", " pasan de " if not otros[0].startswith("1 ") else " pasa de ", 1)
            p2 += (f"; en total, {y_lista(otros)}" if otros else "") + ". "
            p2 += (f"{'Es' if n_t == 1 else 'El más afectado es'} <b>{e(peor['nombre'])}</b>, {_sitio(d, peor)}, con {ci(peor['p98'])} ou_E/m³ de P98 "
                   f"{maximo}" + (siguen if t_ == 1 else "") + "." + _peor_hora(pueblos, crit))
    # 3. hasta dónde llega y hacia dónde; la vivienda y la zona industrial más expuestas
    p3 = ""
    if es_olor and crit:
        c1 = crit[0]
        if c1["hasta_km"] is None:
            p3 = "En ningún sitio de la zona de cálculo se pasa de 1 ou_E/m³ de P98. "
        else:
            viento = d.get("viento")
            sentido = viento is not None and abs((c1["rumbo_grados"] - (viento["de_donde"] + 180) + 180) % 360 - 180) <= 45
            p3 = (f"Por encima de 1 ou_E/m³ quedan <b>{_num(c1['km2'], 2)} km²</b>, hasta {km_txt(c1['hasta_km'])} de la planta hacia el "
                  f"{NOMBRE_RUMBO[c1['rumbo']]}"
                  + (f", hacia donde lleva el olor el viento más frecuente (sopla del {rumbo16(viento['de_donde'])})" if sentido else "") + ". ")
            resto = [f"de {_num(c['umbral'])}, {_num(c['km2'], 2)} km² (hasta {km_txt(c['hasta_km'])})" for c in crit[1:] if c["hasta_km"] is not None]
            nada = [_num(c["umbral"]) for c in crit[1:] if c["hasta_km"] is None]
            if resto:
                p3 += "Por encima " + y_lista(resto) + (f", y de {y_lista(nada)}, nada" if nada else "") + ". "
            elif nada:
                p3 += f"De {y_lista(nada)} ou_E/m³ no se pasa en ningún sitio. "
    viv = d.get("vivienda")
    if viv:
        frase = (f"La vivienda más expuesta, a {km_txt(viv['km'])} de la planta, tiene {ci(viv[est])} {e(unidad)} de {e(nom_est)}"
                 + (f", {frase_umbral(viv[est])}," if es_olor else ",") + f" y un máximo horario de {ci(viv['maximo'])}.")
        p3 += (f"<b>{frase}</b> " if es_olor and viv[est] > 1 else frase + " ")
    if d["industrias"]:
        i0 = d["industrias"][0]
        p3 += f"De las zonas industriales, la más expuesta es {e(i0['nombre'])} ({km_txt(i0['km'])}), con {ci(i0[est])} {e(unidad)} de {e(nom_est)}."
    # 4. los gases
    gases = [k for k in r["orden"] if k != "olor"]
    p4 = ""
    if gases:
        con_limite = [k for k in gases if any(c.get("limite") is not None for c in r["magnitudes"][k]["columnas"])]
        sin = [k for k in gases if k not in con_limite]
        if sin:
            p4 = (f"Se {'ha' if len(sin) == 1 else 'han'} calculado también {len(sin)} {'gas' if len(sin) == 1 else 'gases'} sin límite en la "
                  f"normativa de la planta ({y_lista(r['magnitudes'][k]['nombre'] for k in sin)}). ")
        if con_limite:
            malos = {}
            for k in con_limite:
                mg = r["magnitudes"][k]
                for f in mg["filas"]:
                    if f.get("tipo") == "pueblo" and any(S.supera(c, f[c["clave"]]) for c in mg["columnas"] if c.get("limite") is not None):
                        malos.setdefault(mg["nombre"], []).append(f["nombre"])
            p4 += (f"De los gases con límite en la normativa ({y_lista(r['magnitudes'][k]['nombre'] for k in con_limite)}), "
                   + ("ninguno se supera en los pueblos. " if not malos else
                      "; ".join(f"el {g} se supera en {len(v_)} {'pueblo' if len(v_) == 1 else 'pueblos'}" for g, v_ in malos.items()) + ". "))
    p4 += "Todo es lo que aporta la planta, sin el olor de fondo de la zona."
    return {"que": p1, "pueblos": p2, "alcance": p3.strip(), "gases": p4}
