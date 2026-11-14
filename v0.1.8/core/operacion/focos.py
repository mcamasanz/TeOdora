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
      "salida": {"diametro_m", "velocidad_m_s", "caudal_m3_h", "caudal_Nm3_h", "caudal_kg_h", "temperatura_C", "orientacion",
                 "composicion": {"CO2": %, "CH4": %, …}}   punto; caudal_m3_h a la temperatura de salida, caudal_Nm3_h a 0 °C,
                                    caudal_kg_h con la densidad del gas; orientacion, una de `ORIENTACIONES`; composicion, % en volumen
                                    de `GAS_SALIDA`, que suman el 100 %: su densidad (`densidad_salida`)
      "edificios": {"hb", "hw", "hl", "xadj", "yadj", "gep_m", "edificios"}   punto: la estela de los edificios de alrededor en
                                    las 36 direcciones, calculada con los edificios descargados (`operacion.estela`), no escrita
      "dimensiones": {"largo_m", "ancho_m", "alto_m", "orientacion_deg"}           volumen; orientacion_deg, el rumbo de su largo (0 N, 90 E)
      "emision_viento": {"exponente", "viento_ref_m_s"}   superficie y volumen: lo que emite crece con el viento, (u / u_ref)^β, la
                                    corrección de lo medido con túnel de viento (u_ref, el viento de la medida); sin el campo, constante
      "volumen": {"clase", "seccion"}   volumen: su clase, una de `CLASES_VOLUMEN`, y la sección de una pila (`SECCIONES_PILA`)
      "salida" de una superficie: {"caudal_m3_m2_h", "caudal_m3_h", "caudal_Nm3_h", "caudal_kg_h", "temperatura_C", "composicion"}: como
                                    la de un punto, con el caudal por m² (m³/(m²·h), su velocidad en m/h) en lugar de la velocidad: el aire
                                    que la atraviesa (un biofiltro) o el que la barre en la medida (cámara de flujo o túnel de viento)
      "superficie": {"clase", "sobre"}   superficie: su clase, una de `CLASES_SUPERFICIE`, y, si es la boca de un edificio de la planta (un
                                    tanque abierto), su id (`edificios_planta`): su contorno y su altura siguen a los del edificio
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
# Sin antorcha ni motor o caldera (usuario, 2026-11-08): son de combustión, fuera como sus gases (NOx, CO).
TIPOS = {
    "pila": ("Pila o hilera de compostaje", ("superficie",), "horario"),
    "tunel": ("Túnel o trinchera de compostaje", ("superficie", "punto"), "continuo"),
    "biofiltro": ("Biofiltro", ("superficie",), "continuo"),
    "lavador": ("Lavador químico", ("punto",), "continuo"),
    "soplador": ("Soplador o extractor", ("punto",), "continuo"),
    "venteo": ("Venteo (digestores, gasómetro, tanques)", ("punto",), "eventos"),
    "upgrading": ("Salida del upgrading", ("punto",), "continuo"),
    "recepcion": ("Recepción y descarga", ("superficie", "volumen"), "horario"),
    "pretratamiento": ("Pretratamiento y triturado", ("volumen",), "horario"),
    "digestato": ("Digestato: balsa, tanque o separador", ("superficie", "volumen"), "continuo"),
    "lixiviados": ("Balsa de lixiviados", ("superficie",), "continuo"),
    "fugitivas": ("Fugitivas de nave", ("superficie", "volumen"), "continuo"),
    "cribado": ("Cribado y almacén de compost", ("superficie", "volumen"), "horario"),
}
FUNCIONAMIENTO = {"continuo": "Continuo", "horario": "Por horario", "eventos": "Por eventos"}
# la clase de una superficie (usuario, 2026-11-08: «focos de superficies, desde piscinas, superficies de tanques abiertos»), como en AERMOD y
# CALPUFF una fuente de área: su contorno, su altura de emisión y lo que emite por m², sin sobreelevación ni efecto edificio. clave: (nombre,
# altura de emisión por defecto, m; None: la del tanque). Una balsa o piscina emite a ras de suelo; un tanque abierto, por su borde; un
# biofiltro, por su lecho, con el aire tratado que lo atraviesa (su olor, en ou_E/m³ por el caudal tratado).
CLASES_SUPERFICIE = {"balsa": ("Balsa o piscina", 0.0), "tanque": ("Tanque abierto", None), "biofiltro": ("Biofiltro", 1.5)}
# la clase de un volumen (usuario, 2026-11-08: «pasamos a volúmenes donde añadiremos las pilas de compostaje»), como en AERMOD y CALPUFF una
# fuente de volumen: su centro, su altura de emisión (sin dato, la mitad de su alto: apoya en el suelo) y sus σ iniciales (σz0 = alto/2,15;
# σy0 = lado/4,3 en un volumen solo y lado/2,15 en una fila de volúmenes contiguos), sin sobreelevación. Una pila o hilera de compost emite
# por su piel (sus taludes y su cima, no su planta) y, alargada, va al motor como una fila de volúmenes (`partes_volumen`); una nave, por
# sus puertas y su ventilación, como un volumen solo.
CLASES_VOLUMEN = {"pila": "Pila o hilera", "nave": "Nave"}
SECCIONES_PILA = {"hilera": "Hilera", "meseta": "Meseta"}           # triangular; trapezoidal, con la cima plana (taludes a 45°)
MAX_PARTES = 20                                                      # los volúmenes de una pila larga, como mucho
# lo que emite una lámina líquida o una pila al aire libre crece con el viento sobre ella (usuario, 2026-11-08: «tenemos que dejar una
# correlación en función del viento, en superficies y en volúmenes»): OER(u) = OER_medida · (u / u_ref)^β, hora a hora (Regione
# Lombardia, DGR IX/3018 de 2012, §3.5). β = 0,5 sale de la capa límite laminar sobre un LÍQUIDO (Bliss et al. 1995; Capelli et al.
# 2013); en un sólido (una pila) es experimental, entre 0 y 0,5: 0,5 queda del lado de la seguridad. u_ref, la velocidad del aire en el
# túnel al medir (0,3 m/s en uno tipo UNSW: Jiang y Kaye; Bliss et al. 1995); u, la del viento junto a la superficie (con el perfil del
# viento, no la de 10 m: Lucernoni et al. 2016). Un foco activo (un biofiltro, una pila aireada) no la lleva: lo que emite no depende del
# viento. Lo de partida al activarla; cada foco lleva los suyos (`emision_viento`)
VIENTO_EXPONENTE = 0.5
VIENTO_REF_M_S = 0.3
# hacia dónde sale el gas de una chimenea, y su factor de cantidad de movimiento en el motor: con sombrerete, horizontal o hacia abajo, el
# chorro no sube por su velocidad (solo por su temperatura)
ORIENTACIONES = {"vertical": ("Vertical", 1.0), "sombrerete": ("Sombrerete", 0.0), "horizontal": ("Horizontal", 0.0),
                 "abajo": ("Hacia abajo", 0.0)}
# lo que lleva el gas de salida de un punto, para su densidad (usuario, 2026-11-08: «para el gas de salida poner CO₂, CO, metano, H₂, etano y
# su composición para calcular la densidad»; «añade O₂ y N₂ en la lista de gases de salida, no aire»): clave: (nombre, masa molar g/mol). Suma
# el 100 % (± `TOLERANCIA_COMPOSICION`); sin composición, la de un aire de ventilación (`COMPOSICION_DEFECTO`)
GAS_SALIDA = {"CO2": ("CO₂", 44.009), "CO": ("CO", 28.010), "CH4": ("CH₄", 16.043), "H2": ("H₂", 2.016), "C2H6": ("C₂H₆", 30.069),
              "O2": ("O₂", 31.998), "N2": ("N₂", 28.014)}
COMPOSICION_DEFECTO = {"N2": 79.0, "O2": 21.0}
TOLERANCIA_COMPOSICION = 1.0        # puntos de %: lo que puede faltar o sobrar (se reparte)
M_REF = sum(v / 100.0 * GAS_SALIDA[k][1] for k, v in COMPOSICION_DEFECTO.items())   # la del gas por defecto: el motor lo trata como aire
R_GAS = 8.314462618                 # J/(mol·K)
P_ATM = 101.325 * 1000.0            # Pa (1 atm)

# gas: (masa molar g/mol, umbral olfativo ppb o None, nombre). De gas a olor con Nagata (2003): sus 223 sustancias, de la tabla 2 del
# artículo (`gases_nagata.json`, con la fuente y las masas molares de PubChem; usuario, 2026-11-08: «los gases que se permiten son los que
# producen olor, es decir los de Nagata: añade todos los del artículo»; «la app se centra en dispersión de olores, no de gases de
# combustión: quítalos»). Un gas que no está en la tabla (el CO o los NOx de una combustión) no cuenta y `pendientes` lo dice.
# 1 ou_E/m³ = el umbral (UNE-EN 13725), así que
# 1 ou_E equivale a «umbral» µg del gas. Sin umbral: no cuentan para el olor.
# ⚠️ Esto es un índice de olor orientativo, NO son ou_E de la mezcla (sinergia, enmascaramiento,
# no aditividad), no sustituye a la olfatometría y no sirve para justificar un criterio en ou_E/m³. El umbral del H2S
# publicado varía casi tres órdenes de magnitud. Por eso el resultado dice qué focos están estimados.
RUTA_NAGATA = Path(__file__).with_name("gases_nagata.json")
N_NAGATA = 223                      # las sustancias de la tabla 2 del artículo


def _nagata():
    """La tabla de Nagata; vacía si no se puede leer, para que el programa arranque y «Comprobar la herramienta» lo diga (INS-31/32)."""
    try:
        return json.loads(RUTA_NAGATA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"gases": []}


NAGATA = _nagata()
GASES = {g["clave"]: (g["masa_molar"], g["umbral_ppm"] * 1000.0, g["nombre"]) for g in NAGATA.get("gases", [])}
NOMBRES = {"H2S": "H₂S", "CH3SH": "CH₃SH", "NH3": "NH₃", "SO2": "SO₂", "NO2": "NO₂", "DMS": "DMS", "DMDS": "DMDS",
           "TMA": "TMA", "ESCATOL": "Escatol", "INDOL": "Indol", "AC_VALERICO": "Ác. valérico", "AC_ISOVALERICO": "Ác. isovalérico",
           "AC_BUTIRICO": "Ác. butírico", "AC_PROPIONICO": "Ác. propiónico", "AC_ACETICO": "Ác. acético"}
NOMBRES |= {k: v[2] for k, v in GASES.items() if k not in NOMBRES}       # los demás de Nagata, con su nombre del artículo
VM_25C = 24.45                      # L/mol a 25 °C y 1 atm: el umbral del gas en µg/m³
VM_0C = 22.414                      # L/mol a 0 °C y 1 atm
T_NORMAL_K = 273.15
T_OLFATOMETRIA_K = 293.15           # las ou_E/m³ van referidas a 20 °C (UNE-EN 13725); sin dato, esa temperatura

# Unidades admitidas. Las de concentración necesitan el caudal; las «por m²», la superficie.
UNIDADES_OLOR = ("ou_E/m3", "ou_E/(s·m2)", "ou_E/s")
UNIDADES_GAS = ("ppm", "mg/m3", "mg/Nm3", "mg/(m2·h)", "g/(m2·d)", "mg/(s·m2)", "g/s")
# lo que se emite por m² (una superficie, con cámara de flujo o túnel de viento), en µg/(s·m²) por unidad
POR_M2 = {"mg/(s·m2)": 1000.0, "mg/(m2·h)": 1000.0 / 3600.0, "g/(m2·d)": 1e6 / 86400.0}
# los gases que dan el olor de cada clase de superficie (usuario, 2026-11-08: «quiero que definas los focos de superficie no por olor sino
# por gases»): la lámina de digestato (amoniaco, los compuestos de azufre y el p-cresol) y, en un biofiltro, lo que se escapa de ellos y lo
# que suelta su propio lecho de corteza (los terpenos). Las cantidades, las de cada planta
GASES_TIPICOS = {"balsa": ("NH3", "H2S", "CH3SH", "DMS", "DMDS", "P_CRESOL"),
                 "tanque": ("NH3", "H2S", "CH3SH", "DMS", "DMDS", "P_CRESOL"),
                 "biofiltro": ("H2S", "NH3", "CH3SH", "DMS", "DMDS", "ALFA_PINENE", "LIMONENE"),
                 "pila": ("NH3", "H2S", "CH3SH", "DMS", "DMDS", "LIMONENE", "ALFA_PINENE"),     # el compost: su amoniaco, su azufre y sus terpenos
                 "nave": ("NH3", "H2S", "CH3SH", "DMS", "DMDS", "AC_BUTIRICO", "P_CRESOL")}     # la recepción: además, ácidos grasos y fenoles
UNIDADES_CONCENTRACION = ("ou_E/m3", "ppm", "mg/m3", "mg/Nm3")

# Lo que cambia la RESPUESTA del modelo (posición, altura y sobreelevación): si cambia, hay
# que recalcular ese foco. Emisiones, gases y horario no: entran por superposición.
CAMPOS_RECALCULA = ("tipo", "modelo", "ubicacion", "altura_m", "salida", "edificio", "edificios",
                    "dimensiones", "volumen")          # «volumen»: una pila larga va al motor como una fila de volúmenes


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


def nuevo(datos, tipo=None, modelo=None):
    """Foco nuevo (sin ubicación ni emisiones: se rellenan tras la visita). Sin `tipo` (el editor; usuario, 2026-11-08: la actividad es su
    nombre, que no se repite), sin nombre y del `modelo` que se diga (punto, si no); con `tipo`, el de `tipos()`, con su nombre."""
    nombre, modelos, _ = tipos()[tipo] if tipo else ("", tuple(MODELOS), "continuo")
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
                          "temperatura_C": None, "orientacion": "vertical", "composicion": dict(COMPOSICION_DEFECTO)}
    elif modelo == "superficie" and not tipo:                       # el editor: una balsa, a ras de suelo, hasta que se diga otra cosa
        foco["superficie"] = {"clase": "balsa"}
        foco["altura_m"] = CLASES_SUPERFICIE["balsa"][1]
        foco["salida"] = {"caudal_m3_m2_h": None, "temperatura_C": None, "composicion": dict(COMPOSICION_DEFECTO)}
    elif modelo == "volumen":
        foco["dimensiones"] = {"largo_m": None, "ancho_m": None, "alto_m": None, "orientacion_deg": 90.0}
        if not tipo:                                                 # el editor: una hilera de compost, que emite a media altura
            foco["volumen"] = {"clase": "pila", "seccion": "hilera"}
            foco["salida"] = {"caudal_m3_m2_h": None, "temperatura_C": None, "composicion": dict(COMPOSICION_DEFECTO)}
    if tipo == "pila":
        foco["material"] = ""
    foco.update(funcionamiento=funcionamiento_defecto(foco), olor={"unidad": unidad_olor(foco)}, gases=[],
                observaciones="")
    return foco


def funcionamiento_defecto(foco):
    """La operación con la que nace un foco (usuario, 2026-11-09: «cada vez que se crea un foco debe crearse una operabilidad por defecto,
    que luego se modifica en la configuración de la operación»): la de su tipo (`tipos`) y, sin tipo (el editor), continuo, todo el día al
    100 %. De ella salen su plan en la Base (`planes.base`) y en los planes guardados antes de crearlo (`planes.plan_foco`)."""
    t = tipos().get(foco.get("tipo"))
    return {"modo": t[2] if t else "continuo"}


def clase_superficie(foco):
    """La clase de una superficie (`CLASES_SUPERFICIE`); sin ella, la de su tipo (un biofiltro) o una balsa."""
    c = (foco.get("superficie") or {}).get("clase")
    return c if c in CLASES_SUPERFICIE else ("biofiltro" if foco.get("tipo") == "biofiltro" else "balsa")


def clase_volumen(foco):
    """La clase de un volumen (`CLASES_VOLUMEN`); sin ella, la de su tipo (una pila) o una nave."""
    c = (foco.get("volumen") or {}).get("clase")
    return c if c in CLASES_VOLUMEN else ("pila" if foco.get("tipo") == "pila" else "nave")


def clase(foco):
    """La clase de una superficie o de un volumen; None en un punto."""
    m = foco.get("modelo")
    return clase_superficie(foco) if m == "superficie" else (clase_volumen(foco) if m == "volumen" else None)


def mismo_tipo(a, b):
    """¿Dos focos del mismo tipo, para llevar la operación de uno al otro (usuario, 2026-11-09: «copiar una operabilidad de un foco, del mismo
    tipo, a otro: por ejemplo, pila 1 a pila 2»)? Con tipo los dos, el mismo; si no (los del editor), el mismo modelo y la misma clase: dos
    pilas, dos balsas o dos puntos, pero no una balsa y un tanque abierto."""
    if a.get("tipo") and b.get("tipo"):
        return a["tipo"] == b["tipo"]
    return a.get("modelo") == b.get("modelo") and clase(a) == clase(b)


def nombre_clase(foco):
    """El nombre de lo que es, en corto: el de su tipo y, sin tipo, el de su clase («Pila o hilera», «Balsa o piscina») o su modelo."""
    if foco.get("tipo"):
        return nombre_tipo(foco)
    m = foco.get("modelo")
    if m == "superficie":
        return CLASES_SUPERFICIE[clase_superficie(foco)][0]
    return CLASES_VOLUMEN[clase_volumen(foco)] if m == "volumen" else MODELOS.get(m, "")


def seccion(foco):
    """La sección de un volumen, a lo ancho: [(u, z)] con u de −ancho/2 a +ancho/2 y z de 0 al alto. Una pila, un triángulo (hilera) o un
    trapecio (meseta: taludes a 45° y la cima plana, al menos un 30 % del ancho); una nave, un rectángulo. None sin sus medidas."""
    d = foco.get("dimensiones") or {}
    w, h = d.get("ancho_m"), d.get("alto_m")
    if not (w and h):
        return None
    if clase_volumen(foco) != "pila":
        return [(-w / 2, 0.0), (w / 2, 0.0), (w / 2, h), (-w / 2, h)]
    if (foco.get("volumen") or {}).get("seccion") == "meseta":
        cima = max(w - 2 * h, 0.3 * w)
        return [(-w / 2, 0.0), (w / 2, 0.0), (cima / 2, h), (-cima / 2, h)]
    return [(-w / 2, 0.0), (w / 2, 0.0), (0.0, h)]


def piel_m2(foco):
    """Lo que emite de una pila: sus taludes, su cima y sus dos testeros (no la planta, que apoya en el suelo); None sin sus medidas."""
    s, largo = seccion(foco), (foco.get("dimensiones") or {}).get("largo_m")
    if not (s and largo):
        return None
    lados = sum(math.dist(s[i], s[(i + 1) % len(s)]) for i in range(1, len(s)))           # menos la base (del 1.er al 2.º punto)
    testero = abs(sum(s[i][0] * s[i - 1][1] - s[i - 1][0] * s[i][1] for i in range(len(s)))) / 2
    return largo * lados + 2 * testero


def rumbo(foco):
    """El rumbo del largo de un volumen, en grados (0 N, 90 E); sin él, 90: el largo de este a oeste, como se dibujaban antes."""
    v = (foco.get("dimensiones") or {}).get("orientacion_deg")
    return 90.0 if v in (None, "") else float(v)


def planta_volumen(foco):
    """Las cuatro esquinas de la planta de un volumen, con su rumbo: [(x, y)]; None sin su centro."""
    u, d = foco.get("ubicacion") or {}, foco.get("dimensiones") or {}
    if "x" not in u or "y" not in u:
        return None
    lx, ly = (d.get("largo_m") or 6.0) / 2, (d.get("ancho_m") or 6.0) / 2
    t = math.radians(rumbo(foco))
    ex, ey, nx, ny = math.sin(t), math.cos(t), -math.cos(t), math.sin(t)          # el largo y, a su izquierda, el ancho
    return [(u["x"] + a * lx * ex + b * ly * nx, u["y"] + a * lx * ey + b * ly * ny) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def altura_emision(foco):
    """La altura de emisión: la escrita; en un volumen sin ella, la mitad de su alto (apoya en el suelo, como pide AERMOD)."""
    h = foco.get("altura_m")
    if h in (None, "") and foco.get("modelo") == "volumen":
        alto = (foco.get("dimensiones") or {}).get("alto_m")
        return alto / 2 if alto else None
    return h


def partes_volumen(foco):
    """Los volúmenes del motor de un volumen: [(x, y, σy0)]. Una pila alargada, una fila de volúmenes contiguos a lo largo de su eje, de
    lado cerca de su ancho (σy0 = lado/2,15, AERMOD); lo demás, un volumen solo (σy0 = √(largo·ancho)/4,3)."""
    u, d = foco["ubicacion"], foco["dimensiones"]
    largo, ancho = d["largo_m"], d["ancho_m"]
    n = min(MAX_PARTES, max(1, round(max(largo, ancho) / min(largo, ancho)))) if clase_volumen(foco) == "pila" else 1
    if n == 1:
        return [(u["x"], u["y"], math.sqrt(largo * ancho) / 4.3)]
    t = math.radians(rumbo(foco))
    ex, ey = (math.sin(t), math.cos(t)) if largo >= ancho else (math.cos(t), -math.sin(t))      # el eje largo
    lado = max(largo, ancho) / n
    return [(u["x"] + (k + 0.5 - n / 2) * lado * ex, u["y"] + (k + 0.5 - n / 2) * lado * ey, lado / 2.15) for k in range(n)]


def es_biofiltro(foco):
    """¿Un biofiltro? Su olor se mide en el aire tratado (ou_E/m³) y se multiplica por el caudal tratado."""
    return foco.get("tipo") == "biofiltro" or (foco.get("modelo") == "superficie" and clase_superficie(foco) == "biofiltro")


def poner_sobre(foco, edificio):
    """Una superficie en la boca de un edificio de la planta (un tanque abierto; `edificio`, uno de `edificios_planta`): su contorno, su
    altura y el enlace, para que sigan al edificio. True si ha cambiado algo."""
    pol = [[round(float(x), 1), round(float(y), 1)] for x, y in edificio["poligono"]]
    h = round(float(edificio["altura_m"]), 1)
    s = foco.setdefault("superficie", {})
    antes = (foco.get("ubicacion"), foco.get("altura_m"), s.get("sobre"))
    foco["ubicacion"], foco["altura_m"], s["sobre"] = {"poligono": pol}, h, edificio["id"]
    return antes != ({"poligono": pol}, h, edificio["id"])


def unidades_gas(foco):
    """Las unidades en que tiene sentido dar un gas de este foco: concentración a la salida (un punto, que lleva su caudal), lo que emite por
    m² (una superficie: cámara de flujo o túnel de viento), las dos (un biofiltro: lo de su salida, con el caudal tratado) o el total."""
    m = foco.get("modelo")
    if m == "punto":
        return ("ppm", "mg/m3", "mg/Nm3", "g/s")
    if m == "superficie":                     # como un punto, con su caudal (o el de la medida), o lo que emite por m²
        return ("ppm", "mg/m3", "mg/Nm3", "mg/(m2·h)", "g/(m2·d)", "mg/(s·m2)", "g/s")
    return UNIDADES_GAS


def unidad_gas(foco):
    """La de un gas nuevo de la ficha: ppm, la concentración que se multiplica por su caudal (usuario, 2026-11-08: «la configuración del
    foco debe seguir la misma lógica que los puntos»)."""
    return "ppm"


def poner_gases_tipicos(foco):
    """Añade, sin valor, los gases típicos de su clase (de superficie o de volumen) que aún no tenga (`GASES_TIPICOS`); devuelve cuántos."""
    tiene = {g.get("gas") for g in foco.get("gases") or []}
    nuevos = [k for k in GASES_TIPICOS.get(clase(foco), ()) if k in GASES and k not in tiene]
    foco.setdefault("gases", []).extend({"gas": k, "valor": None, "unidad": unidad_gas(foco)} for k in nuevos)
    return len(nuevos)


def factor_viento(foco, u):
    """El factor de lo que emite con un viento de `u` m/s: (u / u_ref)^β; 1 si su emisión es constante (sin `emision_viento`)."""
    ev = foco.get("emision_viento") or {}
    beta, ref = ev.get("exponente"), ev.get("viento_ref_m_s")
    if not ev or beta in (None, "") or not ref:
        return 1.0
    return (max(float(u), 0.0) / float(ref)) ** float(beta)


def unidad_olor(foco):
    """La de su olfatometría: la concentración a la salida (ou_E/m³) en un punto o una superficie, que lleva su caudal, como sus gases
    (usuario, 2026-11-08: «la misma lógica que los puntos»); el total en un volumen."""
    return "ou_E/m3" if foco.get("modelo") in ("punto", "superficie", "volumen") or es_biofiltro(foco) else "ou_E/s"


def nombre_tipo(foco):
    """El nombre de su tipo; sin tipo (los del editor), el de su modelo."""
    if not foco.get("tipo"):
        return MODELOS.get(foco.get("modelo"), "")
    return tipos().get(foco["tipo"], (foco["tipo"],))[0]


def subtitulo(foco):
    """«Tipo · Modelo · F01»; sin tipo, «Modelo · F01», y una superficie, con su clase delante («Tanque abierto · Superficie · F02»)."""
    delante = [nombre_tipo(foco)] if foco.get("tipo") else []
    if not delante and foco.get("modelo") == "superficie" and foco.get("superficie"):
        delante = [CLASES_SUPERFICIE[clase_superficie(foco)][0]]
    if not delante and foco.get("modelo") == "volumen" and foco.get("volumen"):
        delante = [CLASES_VOLUMEN[clase_volumen(foco)]]
    return " · ".join(delante + [MODELOS.get(foco.get("modelo"), ""), foco["id"]])


def _normal(nombre):
    return " ".join(str(nombre or "").split()).casefold()


def nombre_repetido(datos, foco):
    """El otro foco del catálogo que ya se llama como este (sin distinguir mayúsculas ni espacios), o None (usuario, 2026-11-08: «que no se
    pisen los nombres al crear nuevos equipos»)."""
    n = _normal(foco.get("nombre"))
    return next((f for f in datos["focos"] if f["id"] != foco["id"] and n and _normal(f.get("nombre")) == n), None)


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
    """Superficie de emisión: la del polígono (superficie), la piel de una pila (`piel_m2`) o largo × ancho (otro volumen)."""
    u = foco.get("ubicacion") or {}
    if foco.get("modelo") == "superficie" and len(u.get("poligono") or []) >= 3:
        x0, y0 = u["poligono"][0]                     # respecto al 1.er vértice: sin
        p = [(x - x0, y - y0) for x, y in u["poligono"]]   # restar números de 10⁶ m
        return abs(sum(p[i][0] * p[i - 1][1] - p[i - 1][0] * p[i][1] for i in range(len(p)))) / 2
    if foco.get("modelo") == "volumen":
        d = foco.get("dimensiones") or {}
        if clase_volumen(foco) == "pila" and foco.get("volumen"):
            return piel_m2(foco)
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


def composicion(foco):
    """{componente: % en volumen} del gas de salida de un punto; si no tiene el campo, `COMPOSICION_DEFECTO` (vacía, vacía: no suma 100)."""
    c = (foco.get("salida") or {}).get("composicion")
    if c is None:
        return dict(COMPOSICION_DEFECTO)
    return {k: float(v) for k, v in c.items() if k in GAS_SALIDA and v not in (None, "", 0)}


def masa_molar_salida(foco):
    """Masa molar del gas de salida (g/mol), de su composición; None si no suma el 100 % (± `TOLERANCIA_COMPOSICION`)."""
    c = composicion(foco)
    suma = sum(c.values())
    if abs(suma - 100.0) > TOLERANCIA_COMPOSICION:
        return None
    return sum(v * GAS_SALIDA[k][1] for k, v in c.items()) / suma


def densidad_salida(foco):
    """Densidad del gas a la salida (kg/m³), con su masa molar y su temperatura, a 1 atm (gas ideal); None sin composición válida."""
    m = masa_molar_salida(foco)
    return None if m is None else P_ATM * m / 1000.0 / (R_GAS * temperatura_K(foco))


def temperatura_equivalente_K(foco):
    """La temperatura de un gas como el aire con la misma densidad que el de salida: la que recibe el motor, que solo mira la temperatura
    para la flotación y la cantidad de movimiento (un gas más pesado que el aire, p. ej. el CO₂, sube menos). Con la composición por defecto
    (o una que no suma el 100 %), la suya."""
    m = masa_molar_salida(foco)
    return temperatura_K(foco) * (M_REF / m if m else 1.0)


def caudal_m3_s(foco):
    """Caudal REAL de la salida, a su temperatura (m³/s): el medido (en m³/h, en Nm³/h a 0 °C o en kg/h, con la densidad del gas) o, si no,
    velocidad × sección. En superficies con extracción (biofiltro), el caudal tratado que acompaña al olor."""
    s = foco.get("salida") or {}
    q = s.get("caudal_m3_h") or (foco.get("olor") or {}).get("caudal_m3_h")
    if q:
        return q / 3600.0
    if s.get("caudal_Nm3_h"):
        return s["caudal_Nm3_h"] / 3600.0 * temperatura_K(foco) / T_NORMAL_K
    if s.get("caudal_kg_h"):
        rho = densidad_salida(foco)
        return s["caudal_kg_h"] / 3600.0 / rho if rho else None
    if s.get("caudal_m3_m2_h") and foco.get("modelo") in ("superficie", "volumen"):     # por m² de lo que emite (su velocidad, en m/h)
        a = area_m2(foco)
        return s["caudal_m3_m2_h"] * a / 3600.0 if a else None
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
    if unidad in POR_M2:
        a = area_m2(foco)
        return valor * POR_M2[unidad] * a if a else None
    if unidad == "g/s":
        return valor * 1e6
    raise ValueError(unidad)


def gases_g_s(foco):
    """{gas: g/s} de los gases de la tabla de Nagata con dato completo."""
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
    d = {"id": foco["id"], "h": float(altura_emision(foco))}
    if m == "superficie":
        v = [tuple(p) for p in u["poligono"]]
        d.update(verts=v, cota=cota(*np.mean(v, axis=0)))
        return m, d, 1.0 / area_m2(foco)
    d.update(x=u["x"], y=u["y"], cota=cota(u["x"], u["y"]))
    if m == "punto":
        from teodors.operacion import estela
        s = foco["salida"]
        d.update(d=s["diametro_m"], t=temperatura_equivalente_K(foco),               # con la densidad de su composición
                 w=s.get("velocidad_m_s") or caudal_m3_s(foco) / area_m2(foco),
                 fmfac=ORIENTACIONES.get(s.get("orientacion") or "vertical", ORIENTACIONES["vertical"])[1],
                 edif=estela.para_motor(foco.get("edificios")))
    else:                                                              # como un volumen sobre el suelo
        z = foco["dimensiones"]
        d.update(sy0=math.sqrt(z["largo_m"] * z["ancho_m"]) / 4.3, sz0=z["alto_m"] / 2.15)
    return m, d, 1.0


def fuentes_motor(foco, cota):
    """Las fuentes del motor de un foco: [(modelo, fuente, q0)]. Una, salvo una pila alargada: una fila de volúmenes contiguos
    (`partes_volumen`), «F05_01», «F05_02»…, que se reparten lo que emite (q0 / n) y suman su respuesta."""
    m, d, q0 = geometria(foco, cota)
    if m != "volumen":
        return [(m, d, q0)]
    partes = partes_volumen(foco)
    if len(partes) == 1:
        return [(m, d, q0)]
    n = len(partes)
    return [(m, dict(d, id=f"{foco['id']}_{k + 1:02d}", x=x, y=y, sy0=sy, cota=cota(x, y)), q0 / n) for k, (x, y, sy) in enumerate(partes)]


def pendientes(foco, operacion=True):
    """Datos que faltan para poder calcular el foco (lista de textos). Sin `operacion`, no mira el funcionamiento (las horas, los eventos):
    la ventana de los focos no lo enseña, se configura en la operación (usuario, 2026-11-08)."""
    falta, m = [], foco.get("modelo")
    u = foco.get("ubicacion") or {}
    if not str(foco.get("nombre") or "").strip():
        falta.append("nombre")
    if m == "superficie":
        if len(u.get("poligono") or []) < 3:
            falta.append("dibujar la superficie en el mapa")
    elif not ("x" in u and "y" in u):
        falta.append("marcar la posición en el mapa")
    if altura_emision(foco) in (None, ""):
        falta.append("altura de emisión")
    if m == "punto":
        s = foco.get("salida") or {}
        if not s.get("diametro_m"):
            falta.append("diámetro de la salida")
        if not (s.get("velocidad_m_s") or s.get("caudal_m3_h") or s.get("caudal_Nm3_h") or s.get("caudal_kg_h")):
            falta.append("velocidad o caudal de salida")
        if masa_molar_salida(foco) is None:
            falta.append(f"composición del gas de salida (suma {sum(composicion(foco).values()):.0f} %, no 100 %)")
        if s.get("temperatura_C") in (None, ""):
            falta.append("temperatura de salida")
    if m == "volumen":
        d = foco.get("dimensiones") or {}
        if not all(d.get(k) for k in ("largo_m", "ancho_m", "alto_m")):
            falta.append("dimensiones del volumen")
    ev = foco.get("emision_viento")
    if ev is not None and (ev.get("exponente") in (None, "") or not ev.get("viento_ref_m_s")):
        falta.append("exponente y viento de la medida de su emisión con el viento")
    if m in ("superficie", "volumen"):        # sus gases en concentración, como los de un punto, piden su caudal y su temperatura
        unidades = [g.get("unidad") for g in foco.get("gases") or [] if g.get("valor") not in (None, "")]
        if (foco.get("olor") or {}).get("valor") not in (None, ""):
            unidades.append((foco.get("olor") or {}).get("unidad"))
        if set(unidades) & set(UNIDADES_CONCENTRACION):
            if caudal_m3_s(foco) is None:
                falta.append("caudal por m² o caudal de salida (sus gases van en concentración)" if m == "superficie" or clase_volumen(foco) == "pila"
                             else "caudal de salida (sus gases van en concentración)")
            if (foco.get("salida") or {}).get("temperatura_C") in (None, ""):
                falta.append("temperatura de salida")
    f = (foco.get("funcionamiento") or {}) if operacion else {}       # sin la operación: se configura aparte (la ventana de focos)
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
    fuera = [str(g.get("gas")) for g in foco.get("gases") or [] if g.get("gas") not in GASES]
    if fuera:
        falta.append(f"quitar los gases que no están en la tabla de Nagata (no se pasan a olor): {', '.join(fuera)}")
    return falta


def copia(foco):
    return copy.deepcopy(foco)
