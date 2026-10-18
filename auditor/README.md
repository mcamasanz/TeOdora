# auditor — la puerta de entrada a `main`

Ningún cambio entra en la rama principal de odora sin pasar el auditor:

```bash
python -m auditor                 # audita lo que cambia respecto a main (confirmado y sin confirmar)
python -m auditor --base v0.1.0   # respecto a otra referencia de git
python -m auditor --solo-pruebas  # solo las pruebas y sus tiempos (R1-R3)
```

El resultado es **APTO** (código 0) o **NO APTO** (código 1), con el detalle de lo que falla.

## Reglas

| Regla | Qué exige | Por qué |
|---|---|---|
| **R1 sintaxis** | todo el código de `core/` y `auditor/` compila | nada roto llega a `main` |
| **R2 pruebas** | pasan **todas** las pruebas: unitarias y de regresión | un cambio no puede romper lo que ya estaba validado |
| **R3 rapidez** | cada prueba dura **≤ 20 s** y el conjunto **≤ 300 s**, medidas en régimen: si una pasa del límite (numba compila la primera vez tras un cambio) se repite una vez con la caché caliente y cuenta la segunda medida. Las marcadas `compilacion` quedan fuera | se auditan todas las veces, así que tienen que ser rápidas |
| **R4 pruebas nuevas** | cada motor (o parte del paquete) con código **añadido o modificado** trae pruebas nuevas o modificadas que lo nombran, o un caso nuevo de regresión | todo código nuevo llega con su prueba |
| **R5 referencias** | si cambia una referencia (`casos/*/*/referencia/` o `caso.json`), `CAMBIOS_REFERENCIA.md` tiene una entrada nueva que nombra el caso y lo justifica | un resultado no cambia sin explicar por qué |
| **R6 sin perder pruebas** | no se borran ficheros de pruebas ni casos, y ningún fichero de pruebas pierde funciones `test_` | el conjunto de pruebas solo crece |

R4, R5 y R6 comparan con la rama `main` (o la referencia que se indique con `--base`).

## Qué hay aquí

```
auditor/
├── README.md               este fichero
├── CAMBIOS_REFERENCIA.md   registro justificado de cada referencia cambiada
├── reglas.py               las reglas R1-R6
├── casos.py                carga y corrida de los casos de regresión
├── comparar.py             comparación de salidas (sin fecha ni hora)
├── referencias.py          crear un caso nuevo o regenerar una referencia
├── hooks/pre-push          hook de git: audita antes de subir a main
├── casos/                  casos de regresión: <motor>/<caso>/{entrada, referencia, caso.json}
└── pruebas/
    ├── conftest.py         marca «compilacion» y registro de tiempos
    ├── unitarias/          el paquete importa, la línea de órdenes responde…
    └── regresion/          cada caso reproduce su referencia
```

## Los casos de regresión

Cada caso es una **entrada pequeña** de un motor (segundos) y sus **salidas de referencia**,
obtenidas con el código de la v0.1.0. Ese código está validado frente al programa original con
baterías completas, y además cada caso recortado se ha contrastado con el original (el resultado
está en el campo `original` de su `caso.json` y en [casos/README.md](casos/README.md)).

La comparación es **byte a byte** salvo la fecha, la hora y la duración de la corrida. Cualquier
otro cambio en una salida es un cambio de resultados y hace fallar la prueba, que dice qué fichero
y qué línea cambian.

Los motores escriben la fecha de la corrida en varios formatos («10/18/26», «20261018 20:25:40»,
«OCTOBER 18, 2026  20:25:40 PM», « DATE :  1/ 5/2027»), que `comparar.py` sustituye por un
marcador. Para no depender de haberlos encontrado todos, `test_no_depende_del_dia_ni_de_la_hora`
vuelve a correr un caso de cada motor con el reloj fijado en otro día y otra hora (05/01/2027 a
las 09:05:03) y exige la misma referencia.

## Cómo trabajar

1. **Rama**: trabaja en una rama (`git switch -c mejora/…`), nunca directamente en `main`.
2. **Pruebas** del código que añades o modificas:
   - si es una función o un módulo, una prueba en `auditor/pruebas/unitarias/test_<motor>_<tema>.py`
     que la llame y compruebe su resultado;
   - si cambia lo que calcula un motor, un **caso nuevo** de regresión:
     ```bash
     python -m auditor --nuevo-caso penacho/mi_caso --desde carpeta_con_entradas \
                       --orden "aermod.inp" --carpeta AERMOD --descripcion "qué comprueba"
     ```
     y su contraste con el programa original en el laboratorio antes de fusionarlo.
3. **Si un cambio altera una referencia a propósito** (p. ej. se corrige un fallo):
   ```bash
   python -m auditor --regenerar penacho/mi_caso
   ```
   y añade a `CAMBIOS_REFERENCIA.md` la fecha, el caso, qué cambia y por qué.
4. **Audita**: `python -m auditor`. Si da APTO, abre el *pull request* hacia `main`.

## Cómo deben ser las pruebas

- **Rápidas**: segundos. Un caso de regresión usa unos pocos receptores y unas horas; la vía
  Python pura del penacho (`AERMOD_NUMBA=0`) evita compilar. `penacho/nucleo_compilado` compila
  el núcleo generado del penacho (minutos sin caché) y lleva la marca `compilacion`; los demás
  motores compilan sus núcleos en segundos y R3 los mide ya con la caché caliente.
- **Limpias**: cada prueba corre en una carpeta temporal propia, no deja ficheros ni depende del
  orden ni de otras pruebas.
- **Claras**: el nombre dice qué se comprueba (`test_reproduce_la_referencia[penacho/deposicion]`)
  y el mensaje de fallo, qué ha cambiado.
- **Completas**: todos los motores tienen al menos un caso (la propia batería lo comprueba), y
  cada opción nueva entra con el suyo.

## Automatización

- **Local**: `python -m auditor --instalar-hook` instala un *hook* `pre-push` que audita antes de
  subir a `main` y cancela el push si el resultado es NO APTO.
- **GitHub**: el flujo `.github/workflows/auditor.yml` audita cada *pull request* hacia `main` y
  cada push a `main`. Para que sea obligatorio, en *Settings → Branches* (o *Rules*) añade una regla
  para `main` que exija el check **auditor** antes de fusionar. En repositorios privados, la regla
  obligatoria requiere un plan GitHub Pro o Team; sin él, el check se ejecuta pero no bloquea.
