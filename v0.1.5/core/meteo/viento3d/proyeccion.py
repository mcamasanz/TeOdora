# -*- coding: utf-8 -*-
"""Proyección de la malla (grupo 2 del fichero de control): UTM, LCC y TTM.

[UG] y [V6] tabla 8-3 (grupo 2): PMAP, IUTMZN, UTMHEM, RLAT0, RLON0, XLAT1, XLAT2, FEAST, FNORTH y
DATUM. calmet.exe 5.8.5 solo acepta UTM, LCC (cónica conforme de Lambert con dos paralelos) y TTM
(transversa de Mercator tangente, escala 1 en el meridiano RLON0 y origen en RLAT0); con PS, EM o
LAZA se detiene («PMAP must be UTM,LCC,TTM») [caja negra]. Las coordenadas se calculan con pyproj
sobre el elipsoide WGS-84 (el DATUM de digicompost).
"""

PROYECCIONES = ("UTM", "LCC", "TTM")


def grados(s, defecto=0.0):
    """'41.5N', '3.2W', '90W', '-3.2' -> grados con signo (N y E positivos)."""
    if s is None:
        return defecto
    s = str(s).strip().upper()
    if not s:
        return defecto
    signo = 1.0
    if s[-1] in "NSEW":
        signo = -1.0 if s[-1] in "SW" else 1.0
        s = s[:-1]
    return signo * float(s)


class Proyeccion:
    """Parámetros de la proyección leídos del fichero de control y cadena PROJ (en metros)."""

    def __init__(self, control):
        c = control
        self.pmap = (c.cadena("PMAP", "UTM") or "UTM").strip().upper()
        self.zona = c.entero("IUTMZN", 0) or 0
        self.hem = (c.cadena("UTMHEM", "N") or "N").strip().upper()[:1]
        self.lat0 = grados(c.cadena("RLAT0"))
        self.lon0 = grados(c.cadena("RLON0"))
        self.lat1 = grados(c.cadena("XLAT1"))
        self.lat2 = grados(c.cadena("XLAT2"))
        self.feast = c.real("FEAST", 0.0)
        self.fnorth = c.real("FNORTH", 0.0)
        if self.pmap == "UTM":
            self.proj = "EPSG:%d" % ((32600 if self.hem == "N" else 32700) + self.zona)
        elif self.pmap == "LCC":
            self.proj = ("+proj=lcc +lat_0=%.10g +lon_0=%.10g +lat_1=%.10g +lat_2=%.10g +x_0=%.10g "
                         "+y_0=%.10g +ellps=WGS84 +units=m +no_defs"
                         % (self.lat0, self.lon0, self.lat1, self.lat2, self.feast * 1000.0,
                            self.fnorth * 1000.0))
        elif self.pmap == "TTM":
            self.proj = ("+proj=tmerc +lat_0=%.10g +lon_0=%.10g +k=1 +x_0=%.10g +y_0=%.10g "
                         "+ellps=WGS84 +units=m +no_defs"
                         % (self.lat0, self.lon0, self.feast * 1000.0, self.fnorth * 1000.0))
        else:
            self.proj = None
        # hemisferio para el giro del viento con la altura: UTMHEM en UTM, el de RLAT0 en el resto
        self.hem_giro = self.hem if self.pmap == "UTM" else ("N" if self.lat0 >= 0 else "S")

    def a_lonlat(self):
        from pyproj import Transformer
        return Transformer.from_crs(self.proj, "EPSG:4326", always_xy=True)

    def desde_lonlat(self):
        from pyproj import Transformer
        return Transformer.from_crs("EPSG:4326", self.proj, always_xy=True)
