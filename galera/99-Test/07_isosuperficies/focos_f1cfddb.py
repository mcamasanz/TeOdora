# -*- coding: utf-8 -*-
"""Focos de emisión de la planta: tipos, fichero y paso a las unidades del modelo.

Los focos los define CIRCE tras la primera visita (decisión del usuario, 2026-10-25): una
ficha por unidad emisora. El operario solo los CONSULTA y crea escenarios de operación
(gui/escenarios.py), nunca focos: un foco nuevo o modificado es una actualización de CIRCE.

Fichero: `planta/focos.json` (config.FOCOS_JSON). JSON porque es el formato más limpio y rápido
de leer y escribir con Python solo (sin librerías), se lee a ojo y se compara con un diff
(decisión del usuario, 2026-10-26). Las coordenadas van en UTM (config.EPSG_UTM), las del
modelo; cada magnitud lleva su unidad en el nombre del campo.

    {"formato": 1, "planta": "...", "epsg": "EPSG:25831", "actualizado": "aaaa-mm-dd",
     "ejemplo": false, "focos": [foco, ...]}

    foco = {
      "id": "F01",                  fijo: escenarios y respuestas del modelo lo usan
      "nombre", "unidad",           nombre y unidad de la planta (texto libre)
      "tipo": "biofiltro",          clave de TIPOS
      "modelo": "superficie",       "punto" | "superficie" | "volumen"
      "ubicacion": {"x", "y"}       punto y volumen (centro), en m
                   {"poligono": [[x, y], ...]}    superficie
      "altura_m",                   altura de emisión sobre el suelo
      "salida": {"diametro_m", "velocidad_m_s", "caudal_m3_h", "temperatura_C"}   punto
      "edificio": {"nombre", "altura_m"}      punto: el edificio cercano, con su altura REAL
      "dimensiones": {"largo_m", "ancho_m", "alto_m"}                              volumen
      "funcionamiento": {"modo": "continuo" | "horario" | "eventos",
                         "horas": "8-16", "fuera_pct": 0,     horario (hora oficial)
                         "veces_mes", "duracion_min"},         eventos
      "olor": {"origen": "medido" | "estimado", "valor", "unidad", "caudal_m3_h", "gas",
               "fecha", "referencia"},
      "gases": [{"gas", "valor", "unidad"}],
      "material": "...",            solo pilas: material y fase
      "observaciones": "..."}

El perfil de 24 h no se guarda: sale de «funcionamiento» (`perfil`). La emisión de olor y de
gases se guarda COMO SE MIDE (con su unidad) y se pasa a lo que pide el modelo en un solo sitio
(`olor_ouE_s`, `gases_g_s`, `por_m2`; regla 1: en las áreas, por METRO CUADRADO).
"""
import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
from pathlib import Path

from galera.gui import config

FORMATO = 1
MODELOS = {"punto": "Punto", "superficie": "Superficie", "volumen": "Volumen"}

# clave: (nombre, modelos posibles: el primero por defecto, funcionamiento por defecto).
# Lista aprobada por el usuario el 2026-10-25.
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

# gas: (masa molar g/mol, umbral olfativo ppb, nombre). Umbrales de Nagata (2003), los de
# docs/emisiones/olor_fuentes.py. 1 ou_E/m³ = el umbral (UNE-EN 13725), así que 1 ou_E equivale
# a «umbral» µg del gas. Estimar el olor solo con el gas dominante NO ve las mezclas que se
# potencian (texto de la oferta, 2026-10-24).
GASES = {
    "H2S": (34.08, 0.41, "sulfuro de hidrógeno"),
    "CH3SH": (48.11, 0.07, "metilmercaptano"),
    "DMS": (62.13, 3.0, "dimetilsulfuro"),
    "DMDS": (94.20, 2.2, "dimetildisulfuro"),
    "NH3": (17.03, 1500.0, "amoniaco"),
    "TMA": (59.11, 0.032, "trimetilamina"),
}
VM_25C = 24.45                      # L/mol a 25 °C y 1 atm (ppm ↔ mg/m³)

# Unidades admitidas. Las de concentración necesitan el caudal; las «por m²», la superficie.
UNIDADES_OLOR = ("ou_E/m3", "ou_E/(s·m2)", "ou_E/s")
UNIDADES_GAS = ("ppm", "mg/m3", "mg/(s·m2)", "g/s")

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
                         f"{config.EPSG_UTM} (regla 3)")
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
def nuevo(datos, tipo, modelo=None):
    """Foco nuevo de ese tipo (sin ubicación ni emisiones: se rellenan tras la visita)."""
    nombre, modelos, func = TIPOS[tipo]
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
    foco.update(funcionamiento={"modo": func}, olor={"origen": "medido"}, gases=[],
                observaciones="")
    return foco


def nombre_tipo(foco):
    return TIPOS.get(foco.get("tipo"), (foco.get("tipo", "?"),))[0]


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


def caudal_m3_s(foco):
    """Caudal de la salida (m³/s): el medido o, si no, velocidad × sección. En superficies con
    extracción (biofiltro), el caudal tratado que acompaña al olor."""
    s = foco.get("salida") or {}
    q = s.get("caudal_m3_h") or (foco.get("olor") or {}).get("caudal_m3_h")
    if q:
        return q / 3600.0
    if s.get("velocidad_m_s") and s.get("diametro_m"):
        return s["velocidad_m_s"] * math.pi * s["diametro_m"] ** 2 / 4
    return None


def ug_por_ouE(gas):
    """µg del gas que equivalen a 1 ou_E (su umbral olfativo en µg/m³, a 25 °C)."""
    M, ppb, _ = GASES[gas]
    return ppb * M / VM_25C


def mg_m3(valor, unidad, gas):
    """Concentración en mg/m³ (25 °C, 1 atm)."""
    if unidad == "mg/m3":
        return valor
    if unidad == "ppm":
        return valor * GASES[gas][0] / VM_25C
    raise ValueError(unidad)


def _total(valor, unidad, foco, por_ou):
    """Emisión TOTAL de la fuente, por segundo, en la unidad base (ou_E o µg) a partir de una
    medida en su unidad. por_ou: µg por unidad base (1 para el olor)."""
    if unidad in ("ou_E/m3", "ppm", "mg/m3"):
        q = caudal_m3_s(foco)
        if not q:
            return None
        c = valor if unidad == "ou_E/m3" else mg_m3(valor, unidad, por_ou[1]) * 1000.0
        return c * q / (1.0 if unidad == "ou_E/m3" else por_ou[0])
    if unidad in ("ou_E/(s·m2)", "mg/(s·m2)"):
        a = area_m2(foco)
        if not a:
            return None
        return valor * a * (1.0 if unidad == "ou_E/(s·m2)" else 1000.0 / por_ou[0])
    if unidad == "ou_E/s":
        return valor
    if unidad == "g/s":
        return valor * 1e6 / por_ou[0]
    raise ValueError(unidad)


def olor_ouE_s(foco):
    """Emisión de olor de referencia del foco (ou_E/s, perfil = 1), medida u estimada por el gas
    dominante (concentración en la salida o flujo por m²); None si faltan datos."""
    o = foco.get("olor") or {}
    if o.get("valor") in (None, ""):
        return None
    if o.get("origen") == "estimado":
        gas = o.get("gas")
        if gas not in GASES:
            return None
        return _total(o["valor"], o.get("unidad", "ppm"), foco, (ug_por_ouE(gas), gas))
    return _total(o["valor"], o.get("unidad", "ou_E/m3"), foco, (1.0, None))


def gases_g_s(foco):
    """{gas: g/s} de los gases con dato completo."""
    salida = {}
    for g in foco.get("gases") or []:
        if g.get("gas") in GASES and g.get("valor") not in (None, ""):
            ug = _total(g["valor"], g.get("unidad", "ppm"), foco, (1.0, g["gas"]))
            if ug is not None:
                salida[g["gas"]] = ug * 1e-6
    return salida


def por_m2(foco, total):
    """Lo que entra en las fuentes de ÁREA del modelo: el total entre la superficie (regla 1)."""
    a = area_m2(foco)
    return total / a if (total is not None and a) else None


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
        if not (s.get("velocidad_m_s") or s.get("caudal_m3_h")):
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
    if olor_ouE_s(foco) is None:
        falta.append("emisión de olor")
    return falta


def copia(foco):
    return copy.deepcopy(foco)
