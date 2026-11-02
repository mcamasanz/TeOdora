# -*- coding: utf-8 -*-
"""Focos de emisión de una planta: tipos, fichero y paso a las unidades del modelo.

Una ficha por unidad emisora. El operario solo los CONSULTA y crea planes de operación (`operacion.planes`), nunca focos: un foco nuevo o modificado
es cosa de quien mantiene la planta, en su modo de edición (`planta.MODO_EDICION`).

Fichero: `focos.json`, en la carpeta de la planta (config.FOCOS_JSON). JSON porque se lee y se escribe con Python solo (sin librerías), se lee a ojo y se
compara con un diff. Las coordenadas van en el UTM de la planta (config.EPSG_UTM), las del modelo; cada magnitud lleva su unidad en el nombre del campo.

    {"formato": 2, "planta": "...", "epsg": "EPSG:…", "actualizado": "aaaa-mm-dd",
     "ejemplo": false, "focos": [foco, ...]}

    foco = {
      "id": "F01",                  fijo: planes y respuestas del modelo lo usan
      "nombre", "unidad",           nombre y unidad de la planta (texto libre)
      "tipo": "biofiltro",          clave de `tipos()`
      "modelo": "superficie",       "punto" | "superficie" | "volumen"
      "ubicacion": {"x", "y"}       punto y volumen (centro), en m
                   {"poligono": [[x, y], ...]}    superficie
      "altura_m",                   altura de emisión sobre el suelo
      "salida": {"diametro_m", "velocidad_m_s", "caudal_m3_h", "caudal_Nm3_h", "temperatura_C"}   punto;
                                    caudal_m3_h a la temperatura de salida, caudal_Nm3_h a 0 °C
      "edificio": {"nombre", "altura_m"}      punto: el edificio cercano, con su altura REAL
      "dimensiones": {"largo_m", "ancho_m", "alto_m"}                              volumen
      "funcionamiento": {"modo": "continuo" | "horario" | "eventos",
                         "horas": "8-16", "fuera_pct": 0,     horario (hora oficial)
                         "veces_mes", "duracion_min"},         eventos
      "olor": {"valor", "unidad", "caudal_m3_h", "fecha", "referencia"},    por olfatometría
      "gases": [{"gas", "valor", "unidad"}],     cada gas una sola vez; sin olfatometría, el olor sale de aquí
      "material": "...",            solo pilas: material y fase
      "observaciones": "..."}

El perfil de 24 h no se guarda: sale de «funcionamiento» (`perfil`). La emisión de olor y de
gases se guarda COMO SE MIDE (con su unidad) y se pasa a lo que pide el modelo en un solo sitio
(`olor_ouE_s`, `gases_g_s`, `por_m2`: en las áreas, por METRO CUADRADO).

La simulación da una MAGNITUD por cada cosa que se emite (`magnitudes`): el olor y cada gas, con las mismas respuestas
de los focos. Una concentración medida se multiplica por el caudal a la temperatura a la que está ese dato: un gas
caliente pesa menos por m³.
⚠️ No se distingue base seca de húmeda ni el O₂ de referencia: un dato en base seca con un caudal húmedo se pasa por
la fracción de agua. Hay que dar los dos en la misma base.
"""
import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
from pathlib import Path

import numpy as np

from teodors import planta as config
from teodors.operacion import normativa

FORMATO = 2
MODELOS = {"punto": "Punto", "superficie": "Superficie", "volumen": "Volumen"}

# clave: (nombre, modelos posibles: el primero por defecto, funcionamiento por defecto).
# Una planta añade los suyos en `operacion.tipos_foco_extra` de planta.json: ver `tipos`.
TIPOS = {
    "pila": ("Pila o hilera de compostaje", ("superficie",), "horario"),
    "tunel": ("Túnel o trinchera de compostaje", ("superficie", "punto"), "continuo"),
    "biofiltro": ("Biofiltro", ("superficie",), "continuo"),
    "lavador": ("Lavador químico", ("punto",), "continuo"),
    "soplador": ("Soplador o extractor", ("punto",), "continuo"),
    "venteo": ("Venteo (digestores, gasómetro, tanques)", ("punto",), "eventos"),
    "upgrading": ("Salida del upgrading", ("punto",), "continuo"),
    "antorcha": ("Antorcha", ("punto",), "eventos"),
    "motor": ("Motor de cogeneración o caldera", ("punto",), "continuo"),
    "recepcion": ("Recepción y descarga", ("superficie", "volumen"), "horario"),
    "pretratamiento": ("Pretratamiento y triturado", ("volumen",), "horario"),
    "digestato": ("Digestato: balsa, tanque o separador", ("superficie", "volumen"), "continuo"),
    "lixiviados": ("Balsa de lixiviados", ("superficie",), "continuo"),
    "fugitivas": ("Fugitivas de nave", ("superficie", "volumen"), "continuo"),
    "cribado": ("Cribado y almacén de compost", ("superficie", "volumen"), "horario"),
}
FUNCIONAMIENTO = {"continuo": "Continuo", "horario": "Por horario", "eventos": "Por eventos"}

# gas: (masa molar g/mol, umbral olfativo ppb o None, nombre). De gas a olor con Nagata (2003).
# 1 ou_E/m³ = el umbral (UNE-EN 13725), así que
# 1 ou_E equivale a «umbral» µg del gas. Sin umbral: no cuentan para el olor.
# ⚠️ Esto es un índice de olor orientativo, NO son ou_E de la mezcla (sinergia, enmascaramiento,
# no aditividad), no sustituye a la olfatometría y no sirve para justificar un criterio en ou_E/m³. El umbral del H2S
# publicado varía casi tres órdenes de magnitud. Por eso el resultado dice qué focos están estimados.
GASES = {
    "H2S": (34.08, 0.41, "sulfuro de hidrógeno"),
    "CH3SH": (48.11, 0.07, "metilmercaptano"),
    "DMS": (62.13, 3.0, "dimetilsulfuro"),
    "DMDS": (94.20, 2.2, "dimetildisulfuro"),
    "NH3": (17.03, 1500.0, "amoniaco"),
    "TMA": (59.11, 0.032, "trimetilamina"),
    "ESCATOL": (131.18, 0.0056, "escatol (3-metilindol)"),
    "INDOL": (117.15, 0.30, "indol"),
    "AC_VALERICO": (102.13, 0.037, "ácido n-valérico"),
    "AC_ISOVALERICO": (102.13, 0.078, "ácido isovalérico"),
    "AC_BUTIRICO": (88.11, 0.19, "ácido n-butírico"),
    "AC_PROPIONICO": (74.08, 5.7, "ácido propiónico"),
    "AC_ACETICO": (60.05, 6.0, "ácido acético"),
    "SO2": (64.07, 870.0, "dióxido de azufre"),
    "NO2": (46.01, 120.0, "dióxido de nitrógeno"),
    # El umbral de Nagata es del NO₂, y los NOx de una combustión son sobre todo NO: su olor no se estima con él
    "NOx": (46.01, None, "óxidos de nitrógeno, como NO₂"),
    "CO": (28.01, None, "monóxido de carbono"),
}
NOMBRES = {"H2S": "H₂S", "CH3SH": "CH₃SH", "NH3": "NH₃", "NOx": "NOₓ", "SO2": "SO₂", "NO2": "NO₂", "ESCATOL": "Escatol",
           "INDOL": "Indol", "AC_VALERICO": "Ác. valérico", "AC_ISOVALERICO": "Ác. isovalérico",
           "AC_BUTIRICO": "Ác. butírico", "AC_PROPIONICO": "Ác. propiónico", "AC_ACETICO": "Ác. acético"}
# ⚠️ El motor no tiene química: los NOx calculados como NO₂ son un tope del NO₂.
VM_25C = 24.45                      # L/mol a 25 °C y 1 atm: el umbral del gas en µg/m³
VM_0C = 22.414                      # L/mol a 0 °C y 1 atm
T_NORMAL_K = 273.15
T_OLFATOMETRIA_K = 293.15           # las ou_E/m³ van referidas a 20 °C (UNE-EN 13725); sin dato, esa temperatura

# Unidades admitidas. Las de concentración necesitan el caudal; las «por m²», la superficie.
UNIDADES_OLOR = ("ou_E/m3", "ou_E/(s·m2)", "ou_E/s")
UNIDADES_GAS = ("ppm", "mg/m3", "mg/Nm3", "mg/(s·m2)", "g/s")
UNIDADES_CONCENTRACION = ("ou_E/m3", "ppm", "mg/m3", "mg/Nm3")

# Lo que cambia la RESPUESTA del modelo (posición, altura y sobreelevación): si cambia, hay
# que recalcular ese foco. Emisiones, gases y horario no: entran por superposición.
CAMPOS_RECALCULA = ("tipo", "modelo", "ubicacion", "altura_m", "salida", "edificio",
                    "dimensiones")


# ── fichero ──────────────────────────────────────────────────────────────────────────────
def vacio():
    emp = config.cargar_emplazamiento()
    return {"formato": FORMATO, "planta": emp["nombre"], "epsg": config.EPSG_UTM,
            "actualizado": dt.date.today().isoformat(), "ejemplo": False, "focos": []}


def cargar(ruta=None):
    """Catálogo de focos; si no hay fichero, uno vacío (aún no se ha hecho la visita)."""
    ruta = Path(ruta or config.FOCOS_JSON)
    if not ruta.is_file():
        return vacio()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if datos.get("formato") != FORMATO:
        raise ValueError(f"{ruta.name}: formato {datos.get('formato')!r}; esta versión lee el "
                         f"{FORMATO}")
    if datos.get("epsg") != config.EPSG_UTM:
        raise ValueError(f"{ruta.name}: coordenadas en {datos.get('epsg')}, no en "
                         f"{config.EPSG_UTM}")
    return datos


def guardar(datos, ruta=None):
    """Escribe el catálogo de una vez (fichero temporal + reemplazo: nunca queda a medias)."""
    ruta = Path(ruta or config.FOCOS_JSON)
    datos = dict(datos, formato=FORMATO, epsg=config.EPSG_UTM,
                 actualizado=dt.date.today().isoformat())
    escribir_json(ruta, datos)
    return ruta


def escribir_json(ruta, datos):
    """JSON legible: un campo por línea, pero listas de números (perfiles, vértices) y fichas
    cortas ({"x": …, "y": …}) en una."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(_texto(datos) + "\n", encoding="utf-8")
    os.replace(tmp, ruta)


def _texto(v, sangria=0):
    pad, pad1 = " " * sangria, " " * (sangria + 2)
    if isinstance(v, dict):
        corto = json.dumps(v, ensure_ascii=False)
        if not v or (all(not isinstance(x, (dict, list)) for x in v.values()) and len(corto) <= 96):
            return corto
        filas = [f"{pad1}{json.dumps(k, ensure_ascii=False)}: {_texto(x, sangria + 2)}"
                 for k, x in v.items()]
        return "{\n" + ",\n".join(filas) + "\n" + pad + "}"
    if isinstance(v, list):
        if all(not isinstance(x, (dict, list)) or
               (isinstance(x, list) and all(not isinstance(y, (dict, list)) for y in x))
               for x in v):
            return json.dumps(v, ensure_ascii=False)
        return "[\n" + ",\n".join(pad1 + _texto(x, sangria + 2) for x in v) + "\n" + pad + "]"
    return json.dumps(v, ensure_ascii=False)


# ── focos ────────────────────────────────────────────────────────────────────────────────
def tipos():
    """Los tipos de foco: los de `TIPOS` y los de la planta (`operacion.tipos_foco_extra` de planta.json: {clave: [nombre, [modelos], funcionamiento]})."""
    extra = config.bloque("operacion").get("tipos_foco_extra", {})
    return {**TIPOS, **{k: (v[0], tuple(v[1]), v[2]) for k, v in extra.items()}}


def nuevo(datos, tipo, modelo=None):
    """Foco nuevo de ese tipo (sin ubicación ni emisiones: se rellenan tras la visita)."""
    nombre, modelos, func = tipos()[tipo]
    modelo = modelo or modelos[0]
    if modelo not in modelos:
        raise ValueError(f"{nombre}: modelo {modelo!r} no previsto ({', '.join(modelos)})")
    usados = {f["id"] for f in datos["focos"]}
    k = 1
    while f"F{k:02d}" in usados:
        k += 1
    foco = {"id": f"F{k:02d}", "nombre": nombre, "unidad": "", "tipo": tipo, "modelo": modelo,
            "ubicacion": {}, "altura_m": None}
    if modelo == "punto":
        foco["salida"] = {"diametro_m": None, "velocidad_m_s": None, "caudal_m3_h": None,
                          "temperatura_C": None}
        foco["edificio"] = {"nombre": "", "altura_m": None}
    elif modelo == "volumen":
        foco["dimensiones"] = {"largo_m": None, "ancho_m": None, "alto_m": None}
    if tipo == "pila":
        foco["material"] = ""
    foco.update(funcionamiento={"modo": func}, olor={}, gases=[],
                observaciones="")
    return foco


def nombre_tipo(foco):
    return tipos().get(foco.get("tipo"), (foco.get("tipo", "?"),))[0]


def huella(foco):
    """Resumen de lo que fija la respuesta del modelo: si cambia, hay que recalcular el foco."""
    parte = {k: foco.get(k) for k in CAMPOS_RECALCULA}
    return hashlib.sha1(json.dumps(parte, sort_keys=True).encode()).hexdigest()[:12]


def horas(texto):
    """Horas (0-23, hora oficial) de un texto como «8-16» (de 8:00 a 16:00), «8, 16» o
    «7-9, 15-17». Un tramo «a-b» son las horas que EMPIEZAN de a a b − 1."""
    salida = set()
    for trozo in re.split(r"[;,]", texto or ""):
        trozo = trozo.strip()
        if not trozo:
            continue
        m = re.fullmatch(r"(\d{1,2})(?::00)?\s*[-–]\s*(\d{1,2})(?::00)?", trozo)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if not (0 <= a <= 24 and 0 <= b <= 24):
                raise ValueError(f"hora fuera de 0-24: {trozo!r}")
            salida |= set(range(a, b)) if a < b else set(range(a, 24)) | set(range(0, b))
        elif re.fullmatch(r"\d{1,2}(?::00)?", trozo):
            h = int(trozo.split(":")[0])
            if not 0 <= h <= 23:
                raise ValueError(f"hora fuera de 0-23: {trozo!r}")
            salida.add(h)
        else:
            raise ValueError(f"no se entiende {trozo!r} (p. ej. «8-16» o «8, 16»)")
    return sorted(salida)


def perfil(foco):
    """24 factores (hora oficial, 0-1) sobre la emisión de referencia. Continuo y por eventos:
    1 todo el día (los eventos se reparten aparte con su frecuencia y duración); por horario: 1
    en sus horas y «fuera_pct» / 100 en las demás."""
    f = foco.get("funcionamiento") or {}
    if f.get("modo") != "horario":
        return [1.0] * 24
    fuera = (f.get("fuera_pct") or 0.0) / 100.0
    activas = set(horas(f.get("horas", "")))
    if not activas:
        return [1.0] * 24
    return [1.0 if h in activas else fuera for h in range(24)]


def fraccion_eventos(foco):
    """Parte del tiempo que emite un foco por eventos (veces al mes × duración); 1 si no es por eventos;
    None si faltan esos datos. Reparte el evento en todo el mes: da bien la media, no sus picos."""
    f = foco.get("funcionamiento") or {}
    if f.get("modo") != "eventos":
        return 1.0
    if not (f.get("veces_mes") and f.get("duracion_min")):
        return None
    return min(f["veces_mes"] * f["duracion_min"] / (365.25 / 12 * 24 * 60), 1.0)


# ── geometría y unidades del modelo ──────────────────────────────────────────────────────
def area_m2(foco):
    """Superficie de emisión: la del polígono (superficie) o largo × ancho (volumen)."""
    u = foco.get("ubicacion") or {}
    if foco.get("modelo") == "superficie" and len(u.get("poligono") or []) >= 3:
        x0, y0 = u["poligono"][0]                     # respecto al 1.er vértice: sin
        p = [(x - x0, y - y0) for x, y in u["poligono"]]   # restar números de 10⁶ m
        return abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p)))) / 2
    if foco.get("modelo") == "volumen":
        d = foco.get("dimensiones") or {}
        if d.get("largo_m") and d.get("ancho_m"):
            return d["largo_m"] * d["ancho_m"]
    if foco.get("modelo") == "punto":
        d = (foco.get("salida") or {}).get("diametro_m")
        return math.pi * d * d / 4 if d else None
    return None


def temperatura_K(foco):
    """Temperatura de la salida; sin dato (superficies, biofiltros), la de referencia de la olfatometría."""
    t = (foco.get("salida") or {}).get("temperatura_C")
    return T_OLFATOMETRIA_K if t in (None, "") else t + 273.15


def caudal_m3_s(foco):
    """Caudal REAL de la salida, a su temperatura (m³/s): el medido o, si no, velocidad × sección. En superficies con
    extracción (biofiltro), el caudal tratado que acompaña al olor."""
    s = foco.get("salida") or {}
    q = s.get("caudal_m3_h") or (foco.get("olor") or {}).get("caudal_m3_h")
    if q:
        return q / 3600.0
    if s.get("caudal_Nm3_h"):
        return s["caudal_Nm3_h"] / 3600.0 * temperatura_K(foco) / T_NORMAL_K
    if s.get("velocidad_m_s") and s.get("diametro_m"):
        return s["velocidad_m_s"] * math.pi * s["diametro_m"] ** 2 / 4
    return None


def ug_por_ouE(gas):
    """µg del gas que equivalen a 1 ou_E (su umbral olfativo en µg/m³, a 25 °C); None si no tiene umbral."""
    M, ppb, _ = GASES[gas]
    return None if ppb is None else ppb * M / VM_25C


def mg_m3(valor, unidad, gas, T_K=T_OLFATOMETRIA_K):
    """Concentración en mg/m³ a la temperatura T_K: la que se multiplica por el caudal real. «mg/m3» se entiende ya a
    esa temperatura; ppm es una proporción en volumen y mg/Nm3 está a 0 °C."""
    if unidad == "mg/m3":
        return valor
    if unidad == "mg/Nm3":
        return valor * T_NORMAL_K / T_K
    if unidad == "ppm":
        return valor * GASES[gas][0] / (VM_0C * T_K / T_NORMAL_K)
    raise ValueError(unidad)


def _gas_ug_s(g, foco):
    """Emisión TOTAL de un gas de la ficha (µg/s) a partir de su medida; None si falta el caudal o la superficie."""
    valor, unidad = g["valor"], g.get("unidad", "ppm")
    if unidad in ("ppm", "mg/m3", "mg/Nm3"):
        q = caudal_m3_s(foco)
        return mg_m3(valor, unidad, g["gas"], temperatura_K(foco)) * 1000.0 * q if q else None
    if unidad == "mg/(s·m2)":
        a = area_m2(foco)
        return valor * 1000.0 * a if a else None
    if unidad == "g/s":
        return valor * 1e6
    raise ValueError(unidad)


def gases_g_s(foco):
    """{gas: g/s} de los gases con dato completo."""
    salida = {}
    for g in foco.get("gases") or []:
        if g.get("gas") in GASES and g.get("valor") not in (None, ""):
            ug = _gas_ug_s(g, foco)
            if ug is not None:
                salida[g["gas"]] = ug * 1e-6
    return salida


def olor_medido(foco):
    """Emisión de olor por olfatometría (ou_E/s); None si no hay medida o le falta el caudal o la superficie."""
    o = foco.get("olor") or {}
    if o.get("valor") in (None, ""):
        return None
    unidad = o.get("unidad", "ou_E/m3")
    if unidad == "ou_E/m3":
        q = caudal_m3_s(foco)
        return o["valor"] * q * T_OLFATOMETRIA_K / temperatura_K(foco) if q else None
    if unidad == "ou_E/(s·m2)":
        a = area_m2(foco)
        return o["valor"] * a if a else None
    if unidad == "ou_E/s":
        return o["valor"]
    raise ValueError(unidad)


def gas_dominante(foco):
    """El gas con más veces su umbral olfativo en este foco, y esas ou_E/s: (ou_E/s, gas), o None."""
    veces = [(g_s * 1e6 / ug_por_ouE(gas), gas) for gas, g_s in gases_g_s(foco).items() if ug_por_ouE(gas)]
    return max(veces) if veces else None


def olor_ouE_s(foco):
    """Emisión de olor de referencia del foco (ou_E/s, perfil = 1): la de la olfatometría si la hay y, si no, la estimada
    por su gas dominante. Se pasa a olor en el foco, no en el receptor: así el mismo mapa suma focos medidos y estimados
    (y sale la misma cuenta de superposición). None si no hay datos."""
    if (foco.get("olor") or {}).get("valor") not in (None, ""):
        return olor_medido(foco)
    d = gas_dominante(foco)
    return d[0] if d else None


def emision(foco, clave):
    """Emisión de referencia de una magnitud: ou_E/s para «olor», µg/s para un gas (None si no emite o faltan datos).
    Con las respuestas de los focos, en s/m³, dan ou_E/m³ y µg/m³."""
    if clave == "olor":
        return olor_ouE_s(foco)
    q = gases_g_s(foco).get(clave)
    return None if q is None else q * 1e6


def magnitud(clave):
    """Lo que hace falta para enseñar una magnitud. `ref` es su nivel de referencia: la escala de color va siempre de
    0,1 a 1000 veces `ref`, de modo que un color significa lo mismo con todas. Olor: 1 ou_E/m³; gas con límite: 1/100 del
    primer límite de la normativa, que así cae dentro de la escala; los demás: su umbral."""
    if clave == "olor":
        return {"clave": "olor", "nombre": "Olor", "unidad": "ou_E/m³", "escala": "olor", "ref": 1.0}
    limites = normativa.criterios(clave)
    return {"clave": clave, "nombre": NOMBRES.get(clave, clave), "unidad": "µg/m³", "escala": "gases",
            "ref": float(limites[0]["valor"]) / 100.0 if limites else ug_por_ouE(clave)}


def magnitudes(catalogo):
    """Las magnitudes que puede dar la simulación con estos focos: el olor y, en orden, los gases que alguno emite."""
    claves = (["olor"] if any(olor_ouE_s(f) is not None for f in catalogo["focos"]) else [])
    claves += [g for g in GASES if any(g in gases_g_s(f) for f in catalogo["focos"])]
    return [magnitud(k) for k in claves]


def por_m2(foco, total):
    """Lo que entra en las fuentes de ÁREA del modelo: el total entre la superficie."""
    a = area_m2(foco)
    return total / a if (total is not None and a) else None


def geometria(foco, cota):
    """(modelo, fuente sin emisiones, q0) de un foco, como las pide `preparacion.puffs.control_fuentes`; `cota(x, y)` da la del terreno.
    q0 pasa la emisión TOTAL del foco a lo que pide el motor: en las áreas, POR m²."""
    u, m = foco["ubicacion"], foco["modelo"]
    d = {"id": foco["id"], "h": float(foco["altura_m"])}
    if m == "superficie":
        v = [tuple(p) for p in u["poligono"]]
        d.update(verts=v, cota=cota(*np.mean(v, axis=0)))
        return m, d, 1.0 / area_m2(foco)
    d.update(x=u["x"], y=u["y"], cota=cota(u["x"], u["y"]))
    if m == "punto":
        s = foco["salida"]
        d.update(d=s["diametro_m"], t=s["temperatura_C"] + 273.15,
                 w=s.get("velocidad_m_s") or caudal_m3_s(foco) / area_m2(foco))
    else:                                                              # como un volumen sobre el suelo
        z = foco["dimensiones"]
        d.update(sy0=math.sqrt(z["largo_m"] * z["ancho_m"]) / 4.3, sz0=z["alto_m"] / 2.15)
    return m, d, 1.0


def pendientes(foco):
    """Datos que faltan para poder calcular el foco (lista de textos)."""
    falta, m = [], foco.get("modelo")
    u = foco.get("ubicacion") or {}
    if m == "superficie":
        if len(u.get("poligono") or []) < 3:
            falta.append("dibujar la superficie en el mapa")
    elif not ("x" in u and "y" in u):
        falta.append("marcar la posición en el mapa")
    if foco.get("altura_m") in (None, ""):
        falta.append("altura de emisión")
    if m == "punto":
        s = foco.get("salida") or {}
        if not s.get("diametro_m"):
            falta.append("diámetro de la salida")
        if not (s.get("velocidad_m_s") or s.get("caudal_m3_h") or s.get("caudal_Nm3_h")):
            falta.append("velocidad o caudal de salida")
        if s.get("temperatura_C") in (None, ""):
            falta.append("temperatura de salida")
        b = foco.get("edificio") or {}
        if b.get("nombre") and not b.get("altura_m"):        # sin edificio cerca, nada que pedir
            falta.append("altura real del edificio cercano")
    if m == "volumen":
        d = foco.get("dimensiones") or {}
        if not all(d.get(k) for k in ("largo_m", "ancho_m", "alto_m")):
            falta.append("dimensiones del volumen")
    f = foco.get("funcionamiento") or {}
    if f.get("modo") == "horario":
        try:
            if not horas(f.get("horas", "")):
                falta.append("horas de funcionamiento")
        except ValueError as e:
            falta.append(f"horas de funcionamiento ({e})")
    if f.get("modo") == "eventos" and not (f.get("veces_mes") and f.get("duracion_min")):
        falta.append("frecuencia y duración de los eventos")
    if olor_ouE_s(foco) is None and not gases_g_s(foco):
        falta.append("emisión de olor o de gases")
    return falta


def copia(foco):
    return copy.deepcopy(foco)
