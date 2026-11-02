# -*- coding: utf-8 -*-
"""Proyección cónica equivalente de Albers tal como la implementa AERSURFACE v26135
(mod_Geographic.f: ComputeQ, LATLON2ALBERS, ALBERS2LATLON; Snyder 1987).

Se traduce en vez de usar pyproj porque el original usa constantes REDONDEADAS del
elipsoide (e² = 0.006694380 para NAD83/WGS84, no el valor exacto del GRS80) y la serie
para la latitud inversa: con pyproj saldrían centímetros de diferencia, y eso puede mover
el píxel central (IDNINT) en un caso frontera."""
import math

PI = 3.14159265359                 # el valor de PI del original (no math.pi)
DEG2RAD = PI / 180.0
RAD2DEG = 180.0 / PI

ELIPSOIDE = {                      # datum -> (e², semieje mayor)
    "NAD27": (0.006768658, 6378206.0),
    "NAD83": (0.006694380, 6378137.0),
    "WGS84": (0.006694380, 6378137.0),
}


class Albers:
    def __init__(self, std1, std2, origen_lat, meridiano, datum="NAD83"):
        self.std1, self.std2 = std1, std2
        self.origen, self.cm = origen_lat, meridiano
        self.e2, self.R = ELIPSOIDE[datum]

    def _q(self, xlat):
        e2 = self.e2
        s = math.sin(xlat)
        t1 = s / (1.0 - (e2 * s * s))
        t2 = (1.0 / (2.0 * math.sqrt(e2))) * math.log(
            (1.0 - math.sqrt(e2) * s) / (1.0 + math.sqrt(e2) * s))
        return (1.0 - e2) * (t1 - t2)

    def _constantes(self):
        e2 = self.e2
        q0 = self._q(DEG2RAD * self.origen)
        x1 = DEG2RAD * self.std1
        q1 = self._q(x1)
        m1 = math.cos(x1) / math.sqrt(1.0 - e2 * math.sin(x1) * math.sin(x1))
        x2 = DEG2RAD * self.std2
        q2 = self._q(x2)
        m2 = math.cos(x2) / math.sqrt(1.0 - e2 * math.sin(x2) * math.sin(x2))
        xn = (m1 * m1 - m2 * m2) / (q2 - q1)
        c = m1 * m1 + xn * q1
        rho0 = self.R * math.sqrt(c - xn * q0) / xn
        return xn, c, rho0

    def a_albers(self, lat, lon):
        """LATLON2ALBERS: (lat, lon) grados -> (x, y) m."""
        q = self._q(DEG2RAD * lat)
        xn, c, rho0 = self._constantes()
        theta = xn * (lon - self.cm)
        rho = self.R * math.sqrt(c - xn * q) / xn
        return rho * math.sin(DEG2RAD * theta), rho0 - rho * math.cos(DEG2RAD * theta)

    def a_latlon(self, x, y):
        """ALBERS2LATLON: (x, y) m -> (lat, lon) grados (serie, no iterativo)."""
        e2 = self.e2
        xn, c, rho0 = self._constantes()
        rho = math.sqrt(x ** 2 + (rho0 - y) ** 2)
        q = (c - (rho ** 2) * (xn ** 2) / (self.R ** 2)) / xn
        theta = math.atan(x / (rho0 - y)) * RAD2DEG
        temp = 1.0 - ((1.0 - e2) / (2.0 * math.sqrt(e2))) * math.log(
            (1.0 - math.sqrt(e2)) / (1.0 + math.sqrt(e2)))
        beta = math.asin(q / temp)
        lon = self.cm + theta / xn
        lat = (beta + (1.0 / 3.0 * e2 + 31.0 / 180.0 * e2 ** 2 + 517.0 / 5040.0 * e2 ** 3)
               * math.sin(2.0 * beta)
               + (23.0 / 360.0 * e2 ** 2 + 251.0 / 3780.0 * e2 ** 3) * math.sin(4.0 * beta)
               + (761.0 / 45360.0 * e2 ** 3) * math.sin(6.0 * beta))
        return lat * RAD2DEG, lon
