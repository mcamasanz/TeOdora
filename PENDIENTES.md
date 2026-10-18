# Pendientes

*Estado de la v0.1.0 (2026-10-18). Lo que aquí figura como pendiente no está validado: si un caso
lo pide, el motor se para con un aviso (`NoTraducido` o `NoImplementado`). Nunca da un resultado
sin avisar.*

## 1. Opciones que aún quedan fuera de alcance

### `dispersion.penacho` (≡ AERMOD)
*Ya dentro y validado: varios años y re-arranque (MULTYEAR, SAVEFILE, INITFILE), MAXDAILY y
DAYRANGE, FASTAREA y FASTALL (también con fosos) y la mayoría de los volcados de DEBUGOPT.*
- Procesado por eventos: EVENT, EVENTFIL, EVALFILE.
- SCIM y TTRM2.
- Opciones de viento flojo y estela ALPHA: LOW_WIND, AWMADWNW, ORD_DWNW, AWMAUTURB, AWMAUEFF y
  las ME NOTURB/NOSA/NOSW.
- Fuentes de aeronaves (ARCFTSRC), plataformas marinas (PLATFORM) y HBP.
- Volcados de DEBUGOPT: AREA, RLINE y VBARRIER aún no; el de PRIME se escribe pero todavía difiere
  del original (las concentraciones coinciden).

### `dispersion.puffs` (≡ CALPUFF)
*Ya dentro y validado: deposición seca, húmeda y mixta, malla de receptores, PTEMARB, VOLEMARB y
MDISP 2 y 4 (65/65 casos).*
- Opciones de dispersión MDISP 1 y 5, PDF convectiva (MPDF), TIBL costera (MSGTIBL).
- Slugs (MSLUG) y división de puffs (MSPLIT).
- Química (MCHEM).
- Terreno complejo subrejilla (MCTSG) y ajuste de terreno MCTADJ=2.
- Fuentes de área y de línea con emisión variable (BAEMARB, LNEMARB) y líneas flotantes.
- MSHEAR=1, re-arranque (MRESTART), condiciones de contorno (MBCON), otros formatos
  meteorológicos (METFM ≠ 1) y las opciones MTILT, MSOURCE, MROUGH y MHFTSZ.
- Efecto edificio con MDISP = 2, plataformas elevadas, grupos de especies de salida, unidades de
  emisión distintas de g/s.
- Receptor exactamente en la posición de la chimenea: el original da unas 300 veces menos.

### `meteo.viento3d` (≡ CALMET)
- Entrada directa de campos diagnósticos (IDIOPT1-5).
- Capa caliente y piel fría de COARE (IWARM/ICOOL): a medias.
- Temperatura del agua del pronóstico (ITWPROG=2).
- **No reproducibles** (documentado):
  - estaciones en formato sin formato (IFORMS/IFORMP/IFORMC=1): el binario no está publicado;
  - ICOARE −11/−12: necesita una versión de SEA.DAT no publicada.

### `terreno.*` y `meteo.capa_limite`
- `relieve`: MDT en formato DEM del USGS y NADCON (solo EE. UU.).
- `superficie`: datum NAD27/NADCON y volcado EFFRAD.
- `geofisica`: división de categorías (NSPLIT), segundo fichero de usos, proyecciones distintas de
  UTM.
- `capa_limite`: formatos antiguos de EE. UU. (TD-6201, CD-144, SCRAM, SAMSON, HUSWO) y COARE sobre
  el mar.

## 2. Producto

1. **Sin huella en los textos**: las cabeceras de las salidas y algunos mensajes aún nombran el
   programa original. Pasarán a «<proyecto> · <motor> 0.1». El nombre del proyecto lo fija cada
   proyecto (`identidad.py`).
2. **Velocidad**: llevar al núcleo compilado el bucle horario del penacho, la química GRSM, las
   carreteras (RLINE) y las líneas flotantes, hoy en Python puro.
3. **Núcleos compilados por adelantado**, para no compilar con numba en el equipo del cliente
   (hoy, unos 3 minutos la primera vez).
4. **Ejecutable con Nuitka** y **licencia por localización**:
   - dominio firmado;
   - comprobación en cada motor;
   - datos recortados a la zona del cliente.
5. **Documentación**:
   - ejemplo de uso para las funciones públicas principales de cada módulo;
   - equivalencia funcional en los motores de sala limpia, añadiendo «Equivale a: …» en los
     docstrings.
6. **Más casos de regresión** en el auditor: hoy hay 13 (uno o varios por motor). Conviene
   añadir uno por cada opción validada que aún no tenga el suyo (fosos, RLINE, química GRSM y
   PVMRM, deposición en puffs, observaciones en viento3d…).
7. **Unificar** el lector del fichero de viento, hoy duplicado en `meteo.viento3d` y
   `dispersion.puffs`, y las utilidades comunes (formato fijo, UTM) en `comun/`.

## 3. Proyectos

- digicompost y la planta de La Galera (Tarragona): pasar a usar `odora` como dependencia (hoy
  digicompost usa la copia de trabajo del laboratorio).
- Edificios en la cadena de puffs de los proyectos: pasar las dimensiones de `terreno.edificios`
  al fichero de control de `dispersion.puffs`. El motor ya lo soporta.
