# -*- coding: utf-8 -*-
"""Fuentes de datos: de un servicio de internet a los ficheros de la carpeta de DATOS de la planta activa. No son motores.

    terreno        MDT del IGN (WCS), CORINE y nombres de CartoCiudad
    catastro       edificios del Catastro (WFS INSPIRE)
    meteocat       estaciones de Meteocat (datos abiertos)
    era5           reanálisis ERA5 del CDS (hace falta clave)
    gfs_noaa       GFS 0,25° con niveles de presión (GRIB de NOAA en AWS)
    gfs_dynamical  archivo de predicciones de GFS (dynamical.org; Python ≥ 3.12)
    lidar          de una nube de puntos .laz a rejillas de 1 m (se lanza con «python -I»)

Importar cualquiera de ellos no lee la planta ni carga lo opcional. Son servicios de España, salvo los de GFS y ERA5: ver README.md.
"""
