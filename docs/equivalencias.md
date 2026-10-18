# Equivalencias con los programas originales

Cada motor de lagaus equivale a un programa de referencia. Los de la EPA se han **traducido** de su código (dominio público); los demás se han **reescrito en sala limpia** desde su documentación publicada, sin abrir su código. El detalle por función está en el README de cada motor.

| Motor | Programa | Vía | Funciones | Con equivalencia |
|---|---|---|---|---|
| [`terreno.superficie`](../lagaus/terreno/superficie/README.md) | AERSURFACE | traducción | 44 | 17 |
| [`terreno.relieve`](../lagaus/terreno/relieve/README.md) | AERMAP | traducción | 151 | 126 |
| [`terreno.edificios`](../lagaus/terreno/edificios/README.md) | BPIPPRM | traducción | 59 | 35 |
| [`terreno.geofisica`](../lagaus/terreno/geofisica/README.md) | MAKEGEO | sala limpia | 27 | 0 |
| [`meteo.capa_limite`](../lagaus/meteo/capa_limite/README.md) | AERMET | traducción | 219 | 168 |
| [`meteo.viento3d`](../lagaus/meteo/viento3d/README.md) | CALMET | sala limpia | 98 | 0 |
| [`dispersion.penacho`](../lagaus/dispersion/penacho/README.md) | AERMOD | traducción | 850 | 740 |
| [`dispersion.puffs`](../lagaus/dispersion/puffs/README.md) | CALPUFF | sala limpia | 157 | 0 |

## `terreno.superficie` ≡ AERSURFACE

| Fichero | Módulo de la traducción |
|---|---|
| `__init__.py` | `__init__.py` |
| `__main__.py` | `__main__.py` |
| `albers.py` | `albers.py` |
| `control.py` | `control.py` |
| `corine.py` | `corine.py` |
| `formato.py` | `fortran.py` |
| `geotiff.py` | `geotiff.py` |
| `nucleo.py` | `nucleo.py` |
| `salida.py` | `salida.py` |
| `tablas.py` | `tablas.py` |
| `utm.py` | `utm.py` |

## `terreno.relieve` ≡ AERMAP

| Fichero | Módulo de la traducción |
|---|---|
| `__init__.py` | `__init__.py` |
| `__main__.py` | `__main__.py` |
| `colina.py` | `colina.py` |
| `control.py` | `control.py` |
| `cotas.py` | `elev.py` |
| `dominio.py` | `dominio.py` |
| `estado.py` | `estado.py` |
| `formato.py` | `fortran.py` |
| `mdt_externo.py` | `ned.py` |
| `mensajes.py` | `mensajes.py` |
| `salida.py` | `salida.py` |
| `tiff.py` | `tiff.py` |
| `utm.py` | `utm.py` |

## `terreno.edificios` ≡ BPIPPRM

| Fichero | Módulo de la traducción |
|---|---|
| `__init__.py` | `__init__.py` |
| `__main__.py` | `__main__.py` |
| `formato.py` | `fortran.py` |
| `gep_rapido.py` | `gep_rapido.py` |
| `nucleo.py` | `nucleo.py` |

## `terreno.geofisica` ≡ MAKEGEO

| Fichero | Módulo de la traducción |
|---|---|
| `__init__.py` | `__init__.py` |
| `__main__.py` | `__main__.py` |
| `calculo.py` | `geo.py` |
| `control.py` | `control.py` |
| `corine.py` | `corine.py` |
| `principal.py` | `principal.py` |

## `meteo.capa_limite` ≡ AERMET

| Fichero | Módulo de la traducción |
|---|---|
| `__init__.py` | `__init__.py` |
| `__main__.py` | `__main__.py` |
| `calculo_cl.py` | `pbl.py` |
| `comun.py` | `comun.py` |
| `control.py` | `control.py` |
| `control_cl.py` | `pbl_control.py` |
| `estacion_local.py` | `onsite.py` |
| `estado.py` | `estado.py` |
| `formato.py` | `fortran.py` |
| `informes.py` | `informes.py` |
| `obs_superficie.py` | `surface.py` |
| `sondeos.py` | `upperair.py` |
| `tablas.py` | `tablas.py` |

## `meteo.viento3d` ≡ CALMET

| Fichero | Módulo de la traducción |
|---|---|
| `__init__.py` | `__init__.py` |
| `__main__.py` | `__main__.py` |
| `control.py` | `control.py` |
| `entradas.py` | `entradas.py` |
| `fichero_viento.py` | `calmetdat.py` |
| `lluvia.py` | `lluvia.py` |
| `malla.py` | `malla.py` |
| `mar.py` | `mar.py` |
| `micromet.py` | `micromet.py` |
| `observaciones.py` | `observ.py` |
| `principal.py` | `principal.py` |
| `prognostico.py` | `prognostico.py` |
| `proyeccion.py` | `proyeccion.py` |
| `sol.py` | `sol.py` |
| `viento.py` | `viento.py` |

## `dispersion.penacho` ≡ AERMOD

| Fichero | Módulo de la traducción |
|---|---|
| `__init__.py` | `__init__.py` |
| `bucle_horario.py` | `horas.py` |
| `calculo_area.py` | `calc1.py` |
| `calculo_punto_volumen.py` | `calc1_pv.py` |
| `contribuciones.py` | `maxdcont.py` |
| `control.py` | `control.py` |
| `depura.py` | `depura.py` |
| `emisiones.py` | `emisiones.py` |
| `entrada_control.py` | `coset.py` |
| `entrada_fuentes.py` | `soset.py` |
| `entrada_meteo.py` | `meset.py` |
| `entrada_no2.py` | `no2set.py` |
| `entrada_receptores.py` | `reset.py` |
| `entrada_salidas.py` | `ouset.py` |
| `estado.py` | `estado.py` |
| `estela_edificio.py` | `prime.py` |
| `fondo.py` | `fondo.py` |
| `formato.py` | `fortran.py` |
| `fuente_carretera.py` | `rline.py` |
| `fuente_foso.py` | `openpit.py` |
| `fuente_linea_flotante.py` | `bline.py` |
| `fuente_sidewash.py` | `sidewash.py` |
| `funciones_dispersion.py` | `calc2.py` |
| `integracion_area.py` | `pitarea.py` |
| `meteo_horaria.py` | `metext.py` |
| `nucleo.py` | `nucleo.py` |
| `parametros_efectivos.py` | `iblval.py` |
| `perfiles.py` | `perfiles.py` |
| `principal.py` | `principal.py` |
| `quimica_cinetica.py` | `grsm.py` |
| `quimica_no2.py` | `no2.py` |
| `reinicio.py` | `reinicio.py` |
| `resultados.py` | `resultados.py` |
| `resumen_entrada.py` | `inpsum.py` |
| `salida.py` | `salida.py` |
| `sigmas.py` | `sigmas.py` |
| `tablas.py` | `tablas.py` |

## `dispersion.puffs` ≡ CALPUFF

| Fichero | Módulo de la traducción |
|---|---|
| `__init__.py` | `__init__.py` |
| `control.py` | `control.py` |
| `deposicion.py` | `deposicion.py` |
| `edificios.py` | `edificios.py` |
| `emisiones.py` | `emisiones.py` |
| `entrada.py` | `entrada.py` |
| `estela_edificio.py` | `prime.py` |
| `fichero_conc.py` | `concdat.py` |
| `fichero_viento.py` | `calmetdat.py` |
| `muestreo.py` | `muestreo.py` |
| `nucleo.py` | `nucleo.py` |
| `principal.py` | `principal.py` |
| `sigmas.py` | `sigmas.py` |
| `sobreelevacion.py` | `sobreelevacion.py` |
