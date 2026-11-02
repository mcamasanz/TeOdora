# 10 · Licencias y precios de referencia

Resumen de la auditoría del 2026-10-13 sobre CIERZOFLOW (commit e8bdc36). La auditoría completa, con
enlaces a cada licencia, está en el documento [Auditoría de licencias — CIERZOFLOW](https://claude.ai/code/artifact/dd868acd-5643-4c98-8b4f-e9be4a670b74).
**No sustituye a un asesor jurídico.**

**Clave para ENCE:** entregar un **estudio** (informe con resultados) no plantea problemas de
licencia. Entregar la **herramienta** (software) obliga a resolver primero los tres bloqueos.

## Veredicto por componente

| Componente | Veredicto | Qué hay que hacer |
|---|---|---|
| CALMET / CALPUFF / CALPOST / MAKEGEO | **Bloqueante** | Permiso escrito de Lakes Environmental (calpuff@weblakes.com) para redistribuir, o que el cliente los descargue y acepte el EULA, con la app limitándose a llamarlos |
| Esri World Imagery (satélite) | **Bloqueante** | Cuenta de ArcGIS Location Platform con clave de API y «Powered by Esri», o sustituirlo por la ortofoto PNOA |
| Modelo de IA `qwen2.5:3b` | **Bloqueante** | Licencia Qwen Research, solo uso no comercial. Cambiar a `qwen2.5:7b` o `1.5b` (Apache-2.0) |
| Teselas de OpenStreetMap | Restringido | El acceso puede retirarse sin aviso. Usar un proveedor comercial o el mapa base del IGN |
| AERMOD / AERMAP / BPIPPRM (EPA) | Permitido con condiciones | Sin modificar, diciendo que son de la EPA, sin su logo |
| ERA5 / ERA5-Land | Permitido con condiciones | Atribución «Contains modified Copernicus Climate Change Service information» + DOI. **Cada cliente con su cuenta del CDS** |
| GFS (NOAA) | Permitido | «Fuente: NOAA/NCEP GFS» |
| AEMET OpenData | Permitido con condiciones | Atribución; cada cliente con su clave |
| MDT y PNOA (IGN) | Permitido con condiciones | «CC-BY 4.0 scne.es», visible junto al mapa |
| CORINE 2018 | Permitido con condiciones | Atribución + DOI, e indicar la transformación |
| Catastro | Permitido con condiciones | Solo el dato **transformado**; no redistribuir el GML original |
| PySide6 / Qt, GEOS (LGPL) | Permitido con condiciones | PyInstaller en modo carpeta, DLL sustituibles, texto LGPL y enlace al código fuente |
| Resto de librerías (BSD, MIT, Apache) | Permitido con avisos | Fichero THIRD-PARTY-NOTICES |

Para un producto, además:

- ventana «Acerca de / Fuentes» con todas las atribuciones;
- no incluir claves de API propias;
- quitar meteostat y selenium si no se usan;
- no empaquetar Intel MKL.

⚠️ La carpeta `programas/bin/` de este cajón trae los ejecutables de CALPUFF. **Son para uso interno.
No se entregan al cliente.**

## Precio de mercado de las interfaces de AERMOD (para situar una oferta)

El modelo AERMOD es gratuito (EPA). Lo que se vende son las **interfaces**.

| Producto | Precio | Notas |
|---|---|---|
| AERMOD View (Lakes Environmental) | **1.599 US$** por puesto | 1 año de soporte incluido |
| Mantenimiento de AERMOD View | ~700 US$/año desde el 2.º año | — |
| BREEZE AERMOD Pro (Trinity) | ~1.600 US$ | Pro Plus ~2.680 US$. Paquetes de 1.910 a 5.340 US$, también en alquiler |

Los precios de Trinity salieron del resumen de un buscador: son orientativos.
Lakes, que gestiona CALPUFF, es la misma empresa que vende AERMOD View: **es competencia directa**
si se vende una herramienta con CALPUFF dentro.
