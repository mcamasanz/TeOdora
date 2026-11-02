# Prueba 05 · Planes por días (diario, semanal, mensual)

Pedido del usuario (2026-10-31): planes diarios, semanales e incluso mensuales de cada foco.

**Qué se quiere saber.** La superposición de la prueba 01 está validada con UN perfil de 24 h repetido
todos los días. Las respuestas R_h(t, r) mezclan las emisiones de la hora h de cualquier fecha. ¿Se puede
sacar de ellas un plan en el que cada día sea distinto, sin volver a lanzar el motor? Solo si un puff no
dura más de 24 h en el dominio: entonces lo que hay de h en el instante t viene de la ÚLTIMA vez que fue
la hora h, y basta con pesarlo con lo que dice el plan para esa fecha:

    C(t, r) = Σ_h R_h(t, r) · E(te),   te = t − (hora de t − (h + 1)) mód 24

`te` sale de t y h, que el formato de la prueba 02 ya guarda por cada valor: no hay que recalcular nada.

**Referencia directa**, solo con el motor y la linealidad: un foco que emite el 1.er día y se apaga después
es A − B, con A = emisión constante desde el principio y B = la misma desde el momento de apagar.

```
C:\e2s\python.exe 99-Test\05_planes\prueba_planes.py          (5 min)
C:\e2s\python.exe 99-Test\05_planes\prueba_plan_semanal.py    (necesita la anterior)
C:\e2s\python.exe 99-Test\05_planes\prueba_calcular.py         (necesita gui/tareas/respuestas_dia.py)
```
Datos: viento local de 48 h, 42 h desde las 06 del 20-oct-2026, malla de 12 263 receptores (sin viviendas)
y los focos INVENTADOS de la prueba 01, con 1 g/s. Casos en `%TEMP%\ence_galera\99-Test\05_planes`.

## Resultados

**Plan «un día sí, otro no» frente al motor** (pilas, biofiltro, chimenea):

| | Pilas | Biofiltro | Chimenea |
|---|---|---|---|
| Diferencia máxima, respecto al máximo | 6,4·10⁻⁸ | 5,1·10⁻⁸ | 8,1·10⁻⁸ |
| Horas y receptores comparados | 9 669 | 5 423 | 18 201 |
| Olor que queda 1 h después de apagar | 91 % | 92 % | 85 % |
| 2 h | 30 % | 32 % | 29 % |
| 3 h | 4,4 % | 6,8 % | 5,8 % |
| 4 h o más | 0 | 0 | 0 |

(El % es la suma en la malla gruesa frente a la emisión constante en esa misma hora.) Con dos días con
emisión distinta (día 1 × 1, día 2 × 0,25), igual de exacto. También la media, el máximo y el P98.

**La cadena de verdad** (`gui/escenarios.py`): plan SEMANAL en hora oficial, «el martes emite, el miércoles
no» → `factores` → suma, frente al motor: diferencia máxima 6,4·10⁻⁸ del máximo. El día oficial empieza a las
22 UTC en verano, y el apagado cae justo ahí. Además, 21 comprobaciones de calendario (cambio de hora de marzo
y octubre, días de la semana y del mes), conversiones entre planes y guardar y leer: todas bien.

⚠️ Al preparar la referencia: el 1.er periodo del motor lleva fin = hora de inicio y emite la hora ANTERIOR.
Un cálculo que empieza a las 22 UTC ya emite de 21 a 22: para apagar a las 22 hay que empezar B a las 23.

## «Calcular» con el viento de un día repetido 5 años (`prueba_calcular.py`)

Prueba pedida por el usuario: el 21-oct-2026 repetido en 43 824 h y los 13 focos de ejemplo. No da resultados, solo
comprueba las cuentas de `gui/planes_calculo.py`. 43 800 horas, 12 focos (la antorcha no tiene emisión) y 12 656
receptores: 39 s las series, 43 s en total (51-58 s desde la ventana). Frente a cuentas independientes:

| Comprobación | Resultado |
|---|---|
| Foco continuo: media = Q · Σ R / 24 | diferencia máx. 2,3·10⁻⁴ |
| Foco continuo: máximo = hora peor; P98 de la serie horaria | 7,559 y 7,559 |
| Factor × 2 en media, máximo y P98 | exacto |
| Suma de los planes de un solo foco = plan de todos (media) | diferencia máx. 1,8·10⁻⁴ |
| Todo apagado | 0 |
| Solo el lunes: la media cae a 1/7 | 0,1430 frente a 0,1429 |
| Solo el lunes: el máximo no cambia | P99 de la diferencia, 0 |
| Mensual: solo las horas de noviembre | 3 600 h |
| Mensual constante = diario (media) | diferencia máx. 2,3·10⁻⁴ |

## El penacho del plan hora a hora (`prueba_penacho.py`, 2026-10-31)

El penacho que se ve en Simular sale de `gui/planes_calculo.py` (`_penacho`), con el mismo `te` que el resto:

```
C:\e2s\python.exe 99-Test\05_planes\prueba_penacho.py
```

| Comprobación (biofiltro, F03, 21-oct-2026) | Resultado |
|---|---|
| Foco continuo: C(H, r) = Q · Σ_h R[h, H, r] | máx. 8,67; diferencia 2,4·10⁻⁷ |
| Sus 24 h dan la media y el máximo de los 5 años | diferencia 2,4·10⁻⁴ y 1,2·10⁻⁷ |
| Solo emite el día anterior | a las 00 queda 5,6·10⁻⁴; desde las 02, nada |
| Solo emite el día siguiente | 0 hasta las 22 UTC: el plan va en hora oficial |
| Día anterior + ese día + siguiente = continuo | diferencia 2,4·10⁻⁷ |

⚠️ Comprueba las cuentas, no el fondo: es el día de viento repetido y los focos de ejemplo.

## Límites
- **Una sola situación meteorológica**, con viento (medias horarias de 2,9-5,8 m/s): el olor sale del dominio
  en 4 h. El caso difícil es una calma larga, donde un puff podría durar más de 24 h y parte de su emisión
  se atribuiría al día equivocado. Hay que repetirlo con la peor calma de la serie, cuando vuelva Z:. Solo
  afecta a planes cuyos días consecutivos sean distintos.
- Aún no se ha medido cuánto tarda con los 5 años (la prueba 02 tardó 69 s con un perfil fijo por foco).
