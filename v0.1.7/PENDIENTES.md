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
- **Desde la v0.1.1** (ver su README §Transiciones): volver a correr la batería de laboratorio
  de 51 casos con las reglas nuevas de las transiciones; la altura convectiva de la tarde se
  separa poco a poco del original (|ΔZI| relativo medio 0,6 %) y, con ITPROG = 1 y
  estaciones, la ZI y la temperatura de día (2,3 %), igual que en la v0.1.0.
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
   proyecto (bloque `identidad` de `planta.json`, ver `core/planta/README.md`).
2. **Velocidad**: llevar al núcleo compilado el bucle horario del penacho, la química GRSM, las
   carreteras (RLINE) y las líneas flotantes, hoy en Python puro.
3. **Núcleos compilados por adelantado**, para no compilar con numba en el equipo del cliente
   (hoy, unos 3 minutos la primera vez).
4. **Ejecutable con Nuitka** y **licencia por localización** (⚠️ PySide6 es LGPL: en modo carpeta, no en un único fichero, con las DLL de Qt sustituibles, el texto de la LGPL y el enlace a su código fuente):
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
   `dispersion.puffs` (desde la v0.1.2 el de viento3d ya lee por capas y campos: `leer_campos`), y
   las utilidades de formato fijo en `comun/` (el UTM ya está en `comun.geo`).

## 3. Revisión tras la migración a 0.1.3

Fallos heredados que se vieron al mover el código función a función. Se movieron tal cual para no cambiar resultados durante la migración, y siguen ahí:

- `metricas`: `rosas_dia` da 23 h el 1 de enero; en `_rosa_clases`, una velocidad NaN cuenta como ≥ 8 m/s.
- `fuentes.meteocat.para_mapa` lee `era5_vs_meteocat.json`, que no escribe nadie.
- `fuentes.terreno`: juntas de hasta 0,26 m entre bloques del MDT (96 de 19 023 celdas en un plano al 2 %); su efecto real está sin medir.
- `dispersion.puffs` toma NZ y ZFACE del viento sin avisar si no coinciden con su control.
- `operacion.ejemplo_configuracion` no puede rehacer el ejemplo con los datos actuales.
- `operacion`: un NOx o un CO sin límite en la normativa hace fallar la simulación.
- `operacion.viento_mapa._mes`: un `.cmz` nuevo del mismo mes no se ve hasta reiniciar.
- `operacion.planes`: un plan mensual pierde 2 h en enero.
- `casos.gfs_columnas`: `xr.concat` sin `join`.
- `casos.viento3d`: restos de `_reservado_gb`; `preparar_mes` arranca en frío sin avisar.
- `mos`: `anemometro_m` sale siempre 10 en la tabla; los modelos se guardan y nada los aplica.
- `gui.web._descarga`: hasta 40 s en el hilo de la interfaz si no hay red.
- `gui.web`: en un equipo nuevo, las librerías del mapa se bajan la primera vez que se abre. Al crear una planta de prueba, la de jQuery falló por el certificado SSL (2026-11-02) y la aplicación funcionó igual. Hay que probarlo en el PC del operario.
- `planta`: en el PC del operario, la carpeta de la planta tiene que poder escribirse: ahí guarda sus planes. Tenerlo en cuenta al instalarla (no en `Archivos de programa`).

## 4. Proyectos

- digicompost y la planta de La Galera (Tarragona): pasar a usar `teodors` como dependencia (hoy
  digicompost usa la copia de trabajo del laboratorio).
- `meteo.viento_local`, **sin validar**: comparar con medidas de una planta (sensores cerca de los edificios), y que deje de
  enseñar la estela lejana por fórmula. Sin estabilidad ni concentraciones. Los umbrales de `obstaculos` salen de una sola planta.
- Edificios en la cadena de puffs de los proyectos: pasar las dimensiones de `terreno.edificios`
  al fichero de control de `dispersion.puffs`. El motor ya lo soporta.
- `fuentes` (0.1.3): son servicios de España, salvo ERA5 y GFS. Una planta fuera de España, o fuera de Cataluña para las estaciones,
  necesita otros. La caja de `gfs_noaa` admite el oeste de Greenwich, sin usar aún allí. En `terreno.descargar_mdt`, en la costura entre
  tramos gana la celda del primero aunque su ventana bilineal quede incompleta (medido: 0,26 m sobre un plano del 2 %).
- `metricas` (0.1.3): las estaciones son las de `fuentes.meteocat`. Una planta con otra red necesita otro proveedor; `rosas_dia` da por hecho
  la convención horaria de ese servicio. En `calidad`, las figuras se reparten pensando en 5 años (`list(rosas)[:6]`).
- `casos` (0.1.3): el mes de viento 3D se prepara solo con ERA5 y estaciones de `fuentes.meteocat`. `_reservado_gb` aún mira carpetas de estudios de
  una planta. `gfs_columnas.niveles` junta plazos distintos con `xr.concat` sin `join`: fallará en una versión futura de xarray. `dispersion.puffs` no
  compara NZ y ZFACE del control con los del viento: los toma del viento, y solo aborta si no coinciden NX y NY.
- `operacion.focos` (0.1.7), **emisión que depende del viento** (usuario, 2026-11-08: «buscaremos correlaciones para esto más adelante»):
  lo que emite una lámina líquida al aire libre (una balsa, un tanque abierto) o una pila de compost crece con el viento sobre ella; con
  túnel de viento se suele llevar como ∝ (u / u_túnel)^0,5. **Desde 2026-11-08 se configura** en la ficha de superficies y volúmenes
  (`emision_viento`: exponente y viento de la medida; `focos.factor_viento`), pero **aún no entra en la simulación**: llevarla al motor
  como variación horaria de la emisión con el viento de cada hora (las respuestas por hora del día de `operacion.respuestas` juntan todos
  los días: no la admiten tal cual). Afinar los valores de partida por clase de foco con la bibliografía.
- La Galera (0.1.7): las cantidades de sus focos de superficie son **valores típicos de bibliografía** (con su fuente en las observaciones de
  cada foco) hasta la visita: sustituirlos por lo medido.
- `operacion` (0.1.3): los límites son PRELIMINARES, y lo que da es lo que aporta la planta, sin el fondo de la zona. Las respuestas de un foco se calculan con un día o un periodo: con una
  serie de varios años habrá que cambiar su formato. `ejemplo_configuracion` lee lo que ya no se escribe: no funciona hasta adaptarlo a los resultados de hoy. Un gas sin límite y sin umbral
  (NOx o CO, si una planta les quita el límite) da `ref` None y la simulación falla. `viento_periodo` guarda cada día de una serie en el .cmz de su mes: otro día del mismo mes lo sustituye.
