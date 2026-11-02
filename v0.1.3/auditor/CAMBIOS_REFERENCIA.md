# Cambios de referencia

Cada vez que cambia la salida de referencia de un caso de regresión (o su `caso.json`), se añade
aquí una entrada **nueva** que nombra el caso y explica el cambio. Sin ella, el auditor (regla R5)
da NO APTO.

Formato:

```
## AAAA-MM-DD · <motor>/<caso>
Qué cambia: …
Por qué: … (fallo corregido, opción nueva, contraste con el original…)
Contraste con el original: … (resultado en el laboratorio)
```

---

## 2026-10-18 · v0.1.0
Referencias iniciales de todos los casos, obtenidas con el código validado de la v0.1.0. Los casos
recortados se han contrastado con el programa original (campo `original` de cada `caso.json`).
