# -*- coding: utf-8 -*-
"""Unidades de olor, conversiones y AGRUPACIÓN de fuentes de área. Autónomo: numpy, pyproj
(+ shapely para agrupar).

LO QUE COSTÓ ERRORES REALES EN CIERZOFLOW (no repetir):
  1. Los modelos trabajan SIEMPRE en masa: AERMOD AREA/AREAPOLY quiere g/(s·m²) POR METRO
     CUADRADO, no el total. Meter 234 «µg/s» como si fuera g/s·m² dio 49 MILLONES de µg/m³.
  2. Si la fuente está en ou_E hay que convertir ANTES de escribir el .inp, con el factor
     (µg/m³ que equivalen a 1 ou_E de ESE compuesto = su umbral olfativo). En el worker de
     CALPUFF se perdió el campo `factor` y entró el 32 crudo: ×1,75 millones.
  3. Al fusionar pilas se conserva la EMISIÓN TOTAL Q = Σ(flujo_i·área_i), no la suma de
     flujos. Y las fuentes de área de CALPUFF son de 4 VÉRTICES (rectángulo).
  4. El umbral olfativo del H2S en la literatura va de 0,4 a 13 ppb (×30). El de la tabla
     es un punto de partida; en un expediente se usa el que diga la normativa/olfatometría
     y se deja escrito.

Convenios: 1 ou_E/m³ = umbral olfativo (UNE-EN 13725). ppm = µg/m³ · 24,45 / (M · 1000)
(25 °C, 1 atm).
"""
import numpy as np

VM_25C = 24.45                      # L/mol a 25 °C y 1 atm

# gas: (masa molar g/mol, umbral olfativo ppb, nombre) — referencia (mayoría Nagata 2003)
UMBRAL_OLFATIVO = {
    "H2S": (34.08, 0.41, "sulfuro de hidrógeno"),
    "CH3SH": (48.11, 0.07, "metilmercaptano"),
    "DMS": (62.13, 3.0, "dimetilsulfuro"),
    "DMDS": (94.20, 2.2, "dimetildisulfuro"),
    "NH3": (17.03, 1500.0, "amoniaco"),
    "TMA": (59.11, 0.032, "trimetilamina"),
}


def umbral_ug_m3(gas):
    """µg/m³ que equivalen a 1 ou_E/m³ del gas puro (= el «factor» de las fuentes)."""
    M, ppb, _ = UMBRAL_OLFATIVO[gas.upper()]
    return ppb * M / VM_25C


def ppm_por_ug_m3(gas):
    return VM_25C / (UMBRAL_OLFATIVO[gas.upper()][0] * 1000.0)


def ou_a_gramos(q_ou, factor_ug_por_ou):
    """ou_E/s (o ou_E/s·m²) -> g/s (o g/s·m²)."""
    return q_ou * factor_ug_por_ou * 1e-6


def caudal_area_g_s_m2(total, unidad, area_m2, factor=None):
    """Caudal de una fuente de ÁREA en lo que pide AERMOD/CALPUFF (g/s·m²) a partir del
    TOTAL de la fuente. unidad: 'g/s', 'ug/s' o 'ou_E/s' (este último exige factor)."""
    if unidad == "g/s":
        g = total
    elif unidad == "ug/s":
        g = total * 1e-6
    elif unidad == "ou_E/s":
        if not factor:
            raise ValueError("ou_E/s sin factor de conversión (µg/m³ por ou_E)")
        g = ou_a_gramos(total, factor)
    else:
        raise ValueError(unidad)
    return g / area_m2


def area_poligono_m2(verts_latlon, epsg=None):
    """Área (m²) de [(lat, lon), ...] por la fórmula del zapato en UTM (huso automático)."""
    from pyproj import Transformer
    lat0 = np.mean([v[0] for v in verts_latlon])
    lon0 = np.mean([v[1] for v in verts_latlon])
    epsg = epsg or f"EPSG:{25800 + int((lon0 + 180) // 6) + 1}"
    tr = Transformer.from_crs("EPSG:4258", epsg, always_xy=True)
    xy = np.array([tr.transform(v[1], v[0]) for v in verts_latlon])
    x, y = xy[:, 0], xy[:, 1]
    return abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0


def agrupar_areas(fuentes_utm):
    """Fusiona N fuentes de área en UNA colectiva conservando la emisión total.
    fuentes_utm: [{"verts": [(x, y), ...], "q": flujo por m², ...}] en las mismas unidades.
    Devuelve {"verts": 4 vértices del rectángulo orientado de área mínima, "area_m2",
    "q": Q_total/área_rect, "Q_total"}. Válido en CAMPO LEJANO (P98 en casas a km): diluye
    el pico pegado a la planta. Si quedan pilas sueltas lejos del grupo, mejor 2-3 bloques."""
    from shapely.geometry import MultiPolygon, Polygon
    polys = [Polygon(f["verts"]) for f in fuentes_utm]
    Q = sum(p.area * f["q"] for p, f in zip(polys, fuentes_utm))
    rect = MultiPolygon(polys).minimum_rotated_rectangle
    verts = list(rect.exterior.coords)[:4]
    return {"verts": verts, "area_m2": rect.area, "q": Q / rect.area, "Q_total": Q}


def perfil_volteo(base, pico, horas_volteo, duracion_min=60):
    """Perfil de 24 factores (hora 0..23) para EMISFACT HROFDY (AERMOD) / IVARY=1 (CALPUFF).
    Un volteo que dura menos de una hora se PROMEDIA en la hora: poner el pico entero
    durante 60 min cuando dura 20 multiplica la masa emitida."""
    f = np.full(24, float(base))
    w = min(1.0, duracion_min / 60.0)
    for h in horas_volteo:
        f[int(h) % 24] = base + (pico - base) * w
    return f / f.max(), f.max()          # factores 0-1 y el caudal de referencia


if __name__ == "__main__":
    f = umbral_ug_m3("H2S")
    print(f"H2S: 1 ou_E/m³ = {f:.6f} µg/m³ · 1 µg/m³ = {ppm_por_ug_m3('H2S'):.3e} ppm")
    assert abs(f - 0.571485) < 1e-5                   # el factor de las 17 pilas
    # una pila de 490 m² a 32 ou_E/(s·m²) de H2S
    q = ou_a_gramos(32.0, f)
    print(f"32 ou_E/(s·m²) = {q:.4e} g/(s·m²)  (AERMOD SRCPARAM de las pilas: 1.8288e-05)")
    assert abs(q - 1.8288e-5) < 1e-8
    a = [(0, 0), (40, 0), (40, 10), (0, 10)]
    b = [(60, 0), (100, 0), (100, 10), (60, 10)]
    g = agrupar_areas([{"verts": a, "q": 32.0}, {"verts": b, "q": 32.0}])
    assert abs(g["Q_total"] - 800 * 32) < 1e-6 and abs(g["area_m2"] - 1000) < 1e-6
    print(f"2 pilas de 400 m² -> rectángulo de {g['area_m2']:.0f} m² a {g['q']:.2f} "
          f"ou_E/(s·m²) (Q conservada = {g['Q_total']:.0f} ou_E/s)")
    fac, ref = perfil_volteo(34, 234, [8, 16], duracion_min=20)
    print(f"perfil con volteo de 20 min a las 8 y 16 h: ref {ref:.1f}, factor base "
          f"{fac[0]:.3f}")
    print("olor_fuentes: autoprueba OK")
