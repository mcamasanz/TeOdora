# Prueba 09: las tres modalidades (reanálisis, episodio de queja, predicción)

**Pedido del usuario (2026-11-01):** que Simular y sus resultados dependan de la opción de Meteorología, y un visor 3D donde cargar los penachos de las tres.
La normativa es **preliminar**: aún no se conocen los gases ni las emisiones de la planta, así que vive en un fichero que se cambia sin tocar el código, `lib/galera/gui/planta/normativa.json`.

⚠️ Focos y gases de EJEMPLO, y los «5 años» son un día repetido hasta que vuelva Z: y se termine la serie: esto prueba la herramienta, no da resultados.

## La idea
Las tres modalidades son lo mismo: un periodo de viento más las respuestas de cada foco en ese periodo. Un plan o un gas se calculan sin lanzar el motor.

| | Reanálisis | Episodio de queja | Predicción |
|---|---|---|---|
| Periodo | 5 años y, si se quiere, un día | 1-3 días | 1-5 días, 3 por defecto |
| Preparar | Lo deja CIRCE calculado | Viento y respuestas, una vez | Lo mismo |
| Olor y gases sin límite | Media, máximo, P98 | Media, máximo, hora del máximo | Igual que el episodio |
| Gases con límite | Media, máximo y cada criterio, en el peor año civil | Media, máximo, hora del máximo, horas por encima, media diaria o de 8 h | Igual que el episodio |

## `prueba_normativa.py`: los estadísticos, con series hechas a mano
Cuentan lo que dice el RD 102/2011: por **año civil**. Una serie con 30 horas por encima en un solo año pasa de las 18 que admite, pero el percentil de dos años juntos, como se hacía antes, decía que cumplía. También: 4.º día más alto, media móvil de 8 h, media del peor año, horas por encima y hora del máximo. Y que al cambiar el fichero cambian las columnas, la escala de color y el percentil, sin tocar el código.

## `prueba_periodo.py`: un periodo de varios días, a mano con las respuestas
Episodio del 23 al 25/10/2026 (GFS + 8 estaciones):
- Foco continuo, `C(t, r) = Q · Σ_h R[h, t, r]`: diferencia 5,8·10⁻⁸ sobre 67 ou_E/m³; también la media, el máximo y la hora del máximo.
- Un plan que solo emite el día central: nada antes, empieza a la 01:00 oficial del día (primera hora con fin en él) y, al acabar, 15,5 ou_E/m³ que a las 6 h ya son 0.
- Los 7 días de la semana suman el continuo: 1,7·10⁻⁷. No se pierde ni se duplica emisión al cruzar los días.
- Lo simulado se lee si no ha cambiado nada; con otro plan u otro periodo, no.

## Coste medido (i7-1255U, 4 procesos, 13 focos, 12 653 receptores, 7 magnitudes)
| Paso | Tiempo |
|---|---|
| Preparar el episodio de 3 días | 16,5 min: 8,4 de descargas, 1,5 de viento y 6,6 de respuestas |
| Preparar la predicción de 2 días | 9,0 min: 2,4 de descargas, 0,5 de viento y 6,1 de respuestas |
| Simular el episodio de 3 días | 147 s, casi todo imágenes (1 008 de 72 horas y 7 magnitudes) |
| Simular los 5 años (día repetido) | 97 s |

Con los 5 años reales, sin medir: 15-18 GB de respuestas y unos 10 min (estimado desde la prueba 02).

## Lo que se ha encontrado
- ⚠️ **Los datos abiertos de Meteocat acababan el 26/10/2026 a las 17:30**, consultados el 1/11, en las 8 estaciones a la vez. `CLAUDE.md` decía «hasta ~2 h antes de ahora». Una hora sin ninguna temperatura para el motor. Ahora, si las estaciones no cubren todo el periodo, se calcula solo con el modelo y Meteorología lo dice. Afecta a los episodios recientes: mirar si es un retraso puntual del dataset.
- `viento_dia_local` sobrescribía `meteocat/<estación>/<año>.csv` con solo esos días: en DATOS está el año entero. Ahora suma.

## Sin comprobar
Ratón real, Z:, el PC del operario, la serie de 5 años y la predicción con su MOS: hoy va con GFS tal cual, sin estaciones (sin la mejora de la dirección que da el MOS en cada estación).

## Reproducir
    C:\e2s\python.exe 99-Test\09_modalidades\prueba_normativa.py
    C:\e2s\python.exe 99-Test\09_modalidades\prueba_periodo.py queja 2026-10-23 3      (con el periodo ya preparado)
