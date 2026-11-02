# Prueba 08: resultados de gases y olor estimado con Nagata

**Pregunta (usuario, 2026-11-01):** cuando por foco nos den los gases, ¿cómo dar resultados de gases y trasladarlos a olores, sin
otra simulación?

**Respuesta:** los gases usan las mismas respuestas de los focos, así que cada gas es solo otra emisión: 89-102 s para el olor y 6 gases,
sin lanzar el motor. Pasar de gas a olor con los umbrales de Nagata (2003) es una estimación orientativa, no una medida (abajo).

⚠️ Los focos, y sobre todo sus gases, son de EJEMPLO, con valores inventados. El viento es el de un día repetido: esto prueba la herramienta, no da resultados.

## Cómo queda
- **Una magnitud por cada cosa que se emite** (`focos.magnitudes`): el olor y cada gas que tenga algún foco. `C = Σ_foco Q · Σ_h R · F`: solo cambia Q
  (ou_E/s o µg/s), así que `planes_calculo` hace el producto de F por R una vez por foco y lo reparte.
- **Olor de un foco** (`focos.olor_ouE_s`): la olfatometría si la hay y, si no, `máx(gas / umbral)`, el gas dominante, elegido solo. Se hace en el foco y no en el receptor: así el
  mismo mapa suma focos medidos y estimados. Sumar umbrales en vez de tomar el mayor daría, con 6 gases, como mucho ×6.
- **Umbrales:** los 15 compuestos de [`olores_metodologia.md`](../../docs/referencias/metodologia/olores_metodologia.md) §F.1 (Nagata 2003). NOx y CO no cuentan: el umbral
  de Nagata es del NO₂, y los NOx de una combustión son sobre todo NO; el CO no está en la tabla.
- **Resultados:** `DATOS/resultados_planes/<plan>/<magnitud>/`. En el panel, un selector cambia capas, penacho, tabla y tooltips sin recalcular, y sigue a la vista lo que se estuviera viendo.
- **Escala de color fija:** de 0,1 a 1000 veces `ref`. Olor: 1 ou_E/m³. Gas con límite: 1/100 del límite. Los demás: su umbral. Un mismo color significa lo mismo.
- **Percentil:** P98, salvo los gases con límite horario del RD 102/2011: NOx P99,8 (18 h al año) y SO₂ P99,7 (24 h). El CO (8 h) se queda en P98: falta su estadístico.

## ⚠️ Lo que el olor estimado NO es
La guía del proyecto ([§F.3](../../docs/referencias/metodologia/olores_metodologia.md)) lo dice sin rodeos: convertir un compuesto en `ou_E/m³` de la mezcla, sustituir la olfatometría
o justificar con ello un criterio en ou_E/m³ son usos **ilegítimos** de la tabla: hay sinergia, enmascaramiento y no aditividad. Es un índice orientativo. El usuario decidió usarlo
sabiéndolo; por eso el panel dice «Estimado por gases: foco (gas)». Además:
- El umbral del H₂S publicado varía casi tres órdenes de magnitud (§F.2) y esa regla pide un análisis de sensibilidad con el rango: **no está hecho**.
- Falta la calibración con olfatometrías hechas a la vez que los gases, por tipo de foco: lo que más la mejoraría.
- Solo cuenta lo medido: si no miden mercaptanos (umbral 6 veces menor que el H₂S), no aparecen.

## Unidades: corregido
Antes, una concentración se pasaba a mg/m³ a 25 °C y se multiplicaba por el caudal REAL: en focos calientes salía de más (×1,34 a 127 °C, ×2,26 a 400 °C, comprobado).
- Ahora, ppm y mg/Nm³ se pasan a la temperatura de salida, y las ou_E/m³ van referidas a 20 °C (UNE-EN 13725).
- Nuevos: la unidad `mg/Nm3` y el campo `caudal_Nm3_h` (y de ahí la velocidad de salida, a su temperatura).
- ⚠️ No se distingue base seca de húmeda ni el O₂ de referencia: hay que dar concentración y caudal en la misma base.
- Formato 2 de `focos.json`: sin `olor.origen`; un gas se guarda una sola vez, en `gases`. El formato 1 se rechaza.

## Comprobado (`prueba_gases.py`)
| Qué | Frente a qué | Resultado |
|---|---|---|
| ppm, mg/Nm³, ou_E/m³ | gases ideales, a mano | iguales; con el mismo caudal normal, la masa no depende de T |
| 15 umbrales de Nagata | µg/m³ de la tabla F.1, copiados a mano | dentro del 5 % |
| Un foco con un gas: `C_H2S = C_olor × umbral` | los dos resultados | dif. máx. 1·10⁻⁷ en media, máximo y P98; PNG idénticos byte a byte |
| Media de H₂S de 4 focos continuos | `Σ Q · Σ R / 24`, a mano con las respuestas | dif. máx. 2·10⁻⁷ |
| P99,8 de NOx | la serie horaria, a mano | 13,052 y 13,052 µg/m³ |

## Coste medido (i7-1255U, 13 focos, 7 magnitudes, 43 800 h, 12 656 receptores)
- **89 s** en la app (58 s las series) y 102 s en la prueba, frente a ~27 s de antes con solo el olor. En disco, 2,2 MB por plan.
- Recorrer el percentil por columnas lo hace 4 veces más rápido (0,29 frente a 1,22 s por bloque); saltarse los receptores sin valor ayuda con este viento (97,5 % de ceros), no con 5 años reales.
- La media en `float32` perdía hasta 2·10⁻⁴; ahora va en `float64`.

## Sin probar
Con la serie real de 5 años, donde R dejará de ser periódica; con datos reales de ENCE; ratón real y PC del operario. Sin química ni deposición: NH₃ y H₂S quedan del lado alto, y los NOx como NO₂ son un tope.

## Reproducir
    C:\e2s\python.exe 99-Test\08_gases\prueba_gases.py

Necesita las respuestas de `gui/tareas/respuestas_dia.py` (en los DATOS locales, si no hay `ENCE_GALERA_DATOS`).
