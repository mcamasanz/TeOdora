# Documentación de la herramienta

Lo que se rescató del antiguo `cajon_reutilizable/` (material de CIERZOFLOW, olores de compostaje
en Gimenells) antes de borrarlo el 2026-10-22, más lo que se vaya escribiendo para ENCE.

| Carpeta | Qué hay | Cuándo mirarlo |
|---|---|---|
| `contexto_quejas_olores.md` | quejas vecinales, auditoría de 2024, otras fuentes cercanas, distancias y viento por hora medidos, qué pedir a ENCE (INTERNO) | receptores sensibles, validación, preparar la visita |
| `referencias/normativa/` | criterios de olor (Cataluña, UE, Italia…) y marco normativo ES/UE | P98, límites de inmisión, qué criterio acordar con ENCE |
| `referencias/olores/`, `referencias/metodologia/` | fichas bibliográficas por actividad (compostaje, EDAR, vertederos…) y metodología | factores de emisión, comparar con otras plantas |
| `emisiones/` | catálogo y tipos de pilas de compostaje, ejemplo de 17 pilas y `olor_fuentes.py` (comprobación de unidades ou_E ↔ g de AERMOD/CALPUFF; regla 1 de CLAUDE.md) | al definir los focos de la planta |
| `guias_cajon/` | arranque para ENCE (focos y qué pedir), guía 06 (emisiones y criterios), 09 (lecciones aprendidas), 10 (licencias y precios), guías de teoría y de usuario | dudas de teoría, licencias o errores ya vistos |

⚠️ Las guías del cajón son HISTÓRICAS: hablan de los .exe de la EPA y de Lakes, de rutas que ya
no existen y de una app anterior. Si una guía y el código discrepan, manda el código (regla 6).

Fuera de esta carpeta:
- Ejecutables de terceros (AERMOD, AERMAP, BPIPPRM, CALMET, CALPUFF, CALPOST, MAKEGEO), solo para
  validaciones secundarias y SIN entregar al cliente (EULA de Lakes):
  `%LOCALAPPDATA%\CIRCE\terceros\`.
- Plantillas `CMET.INP` y `CPUF.INP` (las necesita odora): `lib/galera/planta/plantillas/`.
