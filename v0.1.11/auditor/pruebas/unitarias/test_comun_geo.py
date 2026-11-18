# -*- coding: utf-8 -*-
"""comun.geo · huso y EPSG del UTM, ida y vuelta de coordenadas, convergencia de meridianos,
distancia y rumbo, y cuadrados de dominio. Valores de control en la planta de La Galera (Montsià),
medidos con pyproj en el proyecto: UTM 31 (286 763, 4 507 474) m, γ = −1,65° en EPSG:25831 y
+2,26° en EPSG:25830."""
import math

import pytest

from teodors.comun import geo

LAT, LON = 40.6905923, 0.4764197


def test_huso_y_epsg_del_utm():
    assert geo.huso_utm(LON) == 31 and geo.huso_utm(-3.7) == 30 and geo.huso_utm(-8.5) == 29
    assert geo.epsg_utm(LON) == "EPSG:25831"
    assert geo.epsg_utm(-3.7) == "EPSG:25830"
    assert geo.epsg_utm(-70.0) == "EPSG:32619"                 # fuera de ETRS89: WGS-84
    assert geo.epsg_utm(LON, datum="WGS84") == "EPSG:32631"
    assert geo.epsg_utm(LON, norte=False) == "EPSG:32731"


def test_utm_ida_y_vuelta():
    x, y = geo.a_utm(LAT, LON)                                  # huso de la longitud
    assert abs(x - 286763) < 1.0 and abs(y - 4507474) < 1.0
    assert (x, y) == geo.a_utm(LAT, LON, "EPSG:25831")
    la, lo = geo.a_geo(x, y, "EPSG:25831")
    assert abs(la - LAT) < 1e-9 and abs(lo - LON) < 1e-9


def test_convergencia_de_meridianos():
    assert geo.convergencia_deg(LAT, LON, "EPSG:25831") == pytest.approx(-1.65, abs=0.01)
    assert geo.convergencia_deg(LAT, LON, "EPSG:25830") == pytest.approx(2.26, abs=0.01)
    # en el meridiano central del huso 31 (3° E) no hay giro
    assert geo.convergencia_deg(LAT, 3.0, "EPSG:25831") == pytest.approx(0.0, abs=1e-6)
    a = geo.acimut_norte_en_rejilla(LAT, LON, "EPSG:25831")
    assert geo.dir_geo_a_rejilla(350.0, LAT, LON, "EPSG:25831") == pytest.approx((350.0 + a) % 360)


def test_distancia_rumbo_y_desvio_lateral():
    d, r = geo.distancia_rumbo(LAT, LON, LAT + 0.01, LON)
    assert d == pytest.approx(1110.0, rel=0.01) and r == "N"
    assert geo.distancia_rumbo(LAT, LON, LAT, LON + 0.02)[1] == "E"
    assert geo.distancia_rumbo(LAT, LON, LAT - 0.01, LON - 0.01)[1] == "SO"
    assert geo.desvio_lateral_m(7000.0, -1.65) == pytest.approx(7000 * math.sin(math.radians(1.65)))
    assert 195 < geo.desvio_lateral_m(7000.0, -1.65) < 210              # ≈ 200 m a 7 km


def test_cuadrado_utm():
    vertices, ext = geo.cuadrado_utm(LAT, LON, 50.0)
    cx, cy = geo.a_utm(LAT, LON)
    assert ext == pytest.approx((cx - 25000, cx + 25000, cy - 25000, cy + 25000))
    assert len(vertices) == 32
    assert geo.a_utm(*vertices[0], "EPSG:25831") == pytest.approx((ext[0], ext[2]), abs=1e-3)
