# 99-Test — pruebas

Pruebas y prototipos antes de llevar algo a la herramienta (`lib/galera`) o a odora. **No forman
parte de la herramienta**: nada de `lib/` importa de aquí.

- Una carpeta por prueba, numerada (`01_…`, `02_…`), con su `README.md` (qué se quiere saber,
  cómo se corre y qué salió), sus scripts y sus resultados PEQUEÑOS (json, csv, md, png).
- Los ficheros pesados (viento reconstruido, concentraciones, casos) van FUERA de OneDrive (regla 4
  de CLAUDE.md): `%TEMP%\ence_galera\99-Test\<prueba>\`. Se pueden borrar: los scripts los rehacen.
- Se ejecutan con `C:\e2s\python.exe 99-Test\<prueba>\<script>.py` desde la carpeta del proyecto,
  con `PYTHONIOENCODING=utf-8`.

| Prueba | Qué se quiere saber | Estado |
|---|---|---|
| `01_superposicion` | Alcance 1: ¿se puede obtener cualquier perfil de 24 h de varios focos (olor y gases) sumando respuestas unitarias por hora de emisión, y cuánto cuesta? | HECHA (2026-10-24): exacta; las 24 respuestas de un foco cuestan 1,6-1,8 corridas |
| `02_respuestas_dispersas` | ¿Cuánto ocupan y cuánto cuestan las respuestas guardando solo lo que no es casi cero? | HECHA (2026-10-24): umbral 10⁻⁶, error ≤ 0,4 %, 5 años y 3 focos ≈ 0,8 GB comprimido, escenario en 69 s |
| `04_malla_cercana` | Malla de 5 / 25 / 50 m cerca de la planta: ¿cuánto cuesta y qué aporta cada nivel? | HECHA (2026-10-31): 25 y 50 m aportan; 5 m es lo que menos, dentro de la planta y con un solo viento. Adoptada la malla de 12 652 receptores, +31 % de tiempo |
| `05_planes` | ¿Se pueden sacar planes con días distintos (semanal, mensual) de las mismas respuestas, sin lanzar el motor? | HECHA (2026-10-31): sí, diferencia ≤ 8·10⁻⁸ del máximo; falta repetirla con una calma larga (Z:). «Calcular» comprobado con el viento de un día repetido 5 años: ≈ 45 s |

⚠️ `01_superposicion` usa la malla vigente de `gui/receptores_mapa.py`: sus resultados son de la de 8 011 receptores y, si se repite ahora, sale con otra.
