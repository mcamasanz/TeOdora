# -*- coding: utf-8 -*-
"""El aspecto del informe: sus colores y su hoja de estilos, para A4 e impresión. Sin Qt."""
from teodors.comun import escalas

# toda la planta y cada foco (usuario, 2026-11-10: con todo en verdes «apenas se ven cambios»): de amarillo claro (lo que menos emite) a
# granate (lo que más), estirada entre lo menos y lo más de cada cosa
RAMPA = ("#fff3c4", "#fdd26e", "#fca44a", "#f0702e", "#d43d27", "#9c1d2b")
COLOR_MODELO = {"superficie": "#5f9fbb", "volumen": "#9a83cc", "punto": "#d9963f"}
ESCALAS_DEFECTO = {"olor": "turbo", "gases": "viridis"}         # las de la app sin tocar la configuración


def mezcla(a, b, t):
    """El color entre `a` y `b` (#rrggbb) en la fracción `t` (de 0 a 1)."""
    a, b = (tuple(int(x[i:i + 2], 16) for i in (1, 3, 5)) for x in (a, b))
    t = max(0.0, min(1.0, float(t)))
    return "#%02x%02x%02x" % tuple(int(round(p + (q - p) * t)) for p, q in zip(a, b))


def rampa(t):
    """El color de `t` (de 0 a 1) en RAMPA."""
    t = max(0.0, min(1.0, float(t))) * (len(RAMPA) - 1)
    k = min(int(t), len(RAMPA) - 2)
    return mezcla(RAMPA[k], RAMPA[k + 1], t - k)


def estirada(lo, hi):
    """valor → color con RAMPA de `lo` a `hi`; si no cambia, un tono intermedio."""
    if hi - lo < 1e-6:
        return lambda v: rampa(0.6)
    return lambda v: rampa((v - lo) / (hi - lo))


def paradas(colores, t):
    """El color en `t` (de 0 a 1) de un degradado de colores #rrggbb repartidos por igual (el de la leyenda de la elevación)."""
    t = max(0.0, min(1.0, float(t))) * (len(colores) - 1)
    k = min(int(t), len(colores) - 2)
    return mezcla(colores[k], colores[k + 1], t - k)


def gradiente():
    return "linear-gradient(90deg, " + ", ".join(RAMPA) + ")"


def color_escala(clave, f):
    """El color de la fracción `f` en la escala `clave` (`comun.escalas`), como en el mapa."""
    t = escalas.lut(clave)[int(round(max(0.0, min(1.0, f)) * 255))]
    return "#%02x%02x%02x" % tuple(int(round(255 * x)) for x in t[:3])


def bandas(niveles, escala):
    """El color de cada franja entre dos `niveles`, repartidas a partes iguales en la escala (como las isolíneas del mapa)."""
    n = len(niveles) - 1
    return [color_escala(escala, (i + 0.5) / n) for i in range(n)]


CSS = """
@page { size: A4; margin: 0 }
* { box-sizing: border-box }
html, body { margin: 0; background: #fff }
body { font-family: "Segoe UI", "Inter", Arial, sans-serif; color: #17201c; -webkit-print-color-adjust: exact; print-color-adjust: exact }
.pag { width: 210mm; height: 297mm; padding: 13mm 14mm 16mm; position: relative; page-break-after: always; overflow: hidden }
.pag:last-child { page-break-after: auto }
.cab { display: flex; justify-content: space-between; font-size: 8pt; color: #6b7a72; border-bottom: 1px solid #dfe5e1; padding-bottom: 2.5mm; margin-bottom: 6mm }
.pie { position: absolute; bottom: 8mm; left: 14mm; right: 14mm; display: flex; justify-content: space-between; font-size: 7.5pt; color: #87928b }
h2 { font-size: 16pt; margin: 0 0 1mm; color: #17201c }
.sec { font-size: 8pt; letter-spacing: .14em; text-transform: uppercase; color: #2f9e7e; font-weight: 700; margin-bottom: 1mm }
h3 { font-size: 10.5pt; margin: 5mm 0 2mm; color: #17201c }
p { font-size: 9pt; line-height: 1.45; margin: 0 0 3mm; color: #2b3631 }
.intro { font-size: 9.5pt; color: #515e57; margin-bottom: 5mm }
.nota { font-size: 7.6pt; color: #6b7a72 }
figure { margin: 0 } figure img { width: 100%; display: block; border-radius: 2.5mm; object-fit: cover }
figcaption { font-size: 7.8pt; color: #515e57; margin-top: 1.4mm; line-height: 1.35 }
.mapa img { height: auto }
.falta { display: flex; align-items: center; justify-content: center; aspect-ratio: 1.46; border-radius: 2.5mm; background: #f1f4f2;
         color: #87928b; font-size: 8pt; text-align: center; padding: 4mm }
.dos { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm }
.etq { position: relative } .etq .marca { position: absolute; top: 2mm; left: 2mm; z-index: 2; background: rgba(255,255,255,.9); font-size: 7.5pt;
       font-weight: 700; padding: .5mm 2mm; border-radius: 1.5mm }
table { width: 100%; border-collapse: collapse; font-size: 8pt }
th { text-align: left; color: #515e57; font-weight: 600; border-bottom: 1.5px solid #c9d2cc; padding: 1.1mm 1.4mm }
td { border-bottom: 1px solid #edf1ee; padding: .8mm 1.4mm } .n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap }
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3.5mm; margin: 4mm 0 5mm }
.kpis.compacto { margin: 3mm 0 4mm; gap: 3mm } .kpis.compacto .kpi { padding: 2.6mm 3.5mm } .kpis.compacto .v { font-size: 15pt }
.kpis.tres3 { margin: 2mm 0 4mm } .kpi.mini { padding: 2.5mm 3.5mm } .kpi.mini .v { font-size: 15pt }
.kpi { background: #f2f7f4; border-radius: 3mm; padding: 3.5mm 4mm; border-left: 3px solid #59c9a5 }
.kpi .v { font-size: 18pt; font-weight: 700; color: #1f7a60; line-height: 1.1 } .kpi .u { font-size: 9pt; font-weight: 600; color: #1f7a60 }
.kpi .t { font-size: 8pt; color: #515e57; margin-top: 1mm }
.kpi .mx { font-size: 7.6pt; color: #515e57; margin-top: 1.2mm; padding-top: 1.2mm; border-top: 1px solid #d9e6df }
.narra { columns: 2; column-gap: 7mm; margin-top: 5mm; padding-top: 3.5mm; border-top: 1px solid #d9e6df }
.narra p { font-size: 8.6pt; line-height: 1.45; margin: 0 0 2.4mm; break-inside: avoid-column }
.rosas { display: grid; grid-template-columns: repeat(3, 1fr); gap: 2.6mm; margin: 2mm 0 1.5mm }
.rosa { background: #f4f8f6; border-radius: 2.5mm; padding: 2mm 2.4mm 1.6mm; text-align: center; min-width: 0 }
.rosa.destacada { background: #e6f4ed; box-shadow: inset 0 0 0 1.4px #59c9a5 }
.rosa .rt { font-size: 8.6pt; font-weight: 700; color: #1d2723; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
.rosa .rs { font-size: 6.9pt; color: #6b7a72; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
.rosa figure img { width: 35mm; height: 35mm; margin: .6mm auto 0; border-radius: 0; object-fit: contain }
.rosa .rp { font-size: 7.2pt; color: #2b3631; margin-top: .4mm; white-space: nowrap }
.leyenda_rosa img { height: 5mm; width: auto; border-radius: 0; margin: 0 auto }
/* el mapa de las estaciones, con la rosa de la planta y la leyenda al lado; debajo, las de las estaciones de 4 en 4 */
.est_arriba { display: grid; grid-template-columns: 2.05fr 1fr; gap: 2.6mm; align-items: stretch; margin: 1mm 0 2.6mm }
.est_lado { display: grid; grid-template-rows: auto 1fr; gap: 2.6mm; min-width: 0 }
.est_lado .rosa figure img { width: 38mm; height: 38mm }
.rosa.ley { display: flex; align-items: center; gap: 3mm; text-align: left; padding: 2.4mm 3mm }
.rosa.ley .leyenda_rosa img { height: auto; width: 19mm; margin: 0 }
.rosa.ley p { font-size: 7pt; line-height: 1.35; margin: 0; color: #515e57 }
.rosas.cuatro { grid-template-columns: repeat(4, 1fr); margin-top: 0 }
.rosas.cuatro .rosa figure img { width: 30mm; height: 30mm }
.rosas.cuatro .rosa .rt { font-size: 7.8pt } .rosas.cuatro .rosa .rs, .rosas.cuatro .rosa .rp { font-size: 6.6pt }
.rosa .rt .cod { display: inline-block; font-size: 6.8pt; font-weight: 700; color: #0f766e; border: 1.2px solid #0f766e; border-radius: 1.2mm;
                 padding: 0 .9mm; margin-right: 1.2mm; line-height: 1.35; vertical-align: .2mm }
/* el tiempo en la planta, día a día: 3 columnas de gráficas */
.graficas { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3.2mm 3.5mm; margin-top: 1mm }
.graf { min-width: 0 }
.graf .gt { font-size: 7.8pt; color: #1d2723; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
.graf .gs { font-size: 6.7pt; color: #6b7a72; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: .5mm }
.graf svg.grafica { width: 100%; height: auto; display: block; font-family: inherit; font-variant-numeric: tabular-nums }
.graf.clave { background: #f4f8f6; border-radius: 2.5mm; padding: 2.4mm 3mm; font-size: 7pt; color: #515e57 }
.graf.clave b { color: #1d2723; font-size: 7.6pt } .graf.clave div { display: flex; align-items: center; gap: 2mm; margin: .9mm 0 }
.graf.clave svg.muestra { width: 7mm; height: 3.2mm; flex: none } .graf.clave .nota { margin-top: 1.4mm; font-size: 6.6pt }
/* cuándo se huele en los pueblos: la tabla, los mapas de calor (mes × hora) y los peores días */
table.horas { font-size: 7.6pt; margin: 1mm 0 .5mm } table.horas td { padding: .6mm 1.4mm } table.horas th { padding: .8mm 1.4mm }
.calores { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3.5mm; margin-top: 3mm }
.calores.ep { grid-template-columns: 1fr; gap: 2mm } .calores.ep .calor_c { max-width: 150mm }
.calor_c .gt { font-size: 7.8pt; color: #1d2723; margin-bottom: .6mm } .calor_c svg { width: 100%; height: auto; display: block }
.ley_calor { margin: 1.2mm 0 0 } .ley_calor span:first-child { white-space: normal }
/* la comparación de dos escenarios: la operación de los dos, los focos que cambian y la página final */
.chip { display: inline-block; width: 2.6mm; height: 2.6mm; border-radius: .6mm; margin: 0 1.2mm 0 1.6mm; vertical-align: -.3mm }
.dos_cal { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; margin-top: 1mm }
.dos_cal .calendario { grid-template-columns: 3.5mm repeat(31, 1fr); gap: .35mm; font-size: 6pt }
.dos_cal .calendario .mes { line-height: 2.7mm; padding-right: .8mm } .dos_cal .calendario .dia { height: 2.7mm; border-radius: .45mm }
.grafica.dia2 { width: 100%; height: auto; display: block; margin-top: 1mm }
table.comp_op tr.cambia td { font-weight: 700; color: #17201c } table.comp_op em { font-style: normal; color: #87928b; font-size: 6.8pt; font-weight: 400 }
.fichas.comp { grid-template-columns: 1fr }
.ficha.comp { display: block } .ficha.comp .fh { display: flex; align-items: center; gap: 2mm; margin-bottom: 1.5mm }
.ficha.comp .fh b { display: inline; font-size: 9pt }
.ficha.comp .lados { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm } .ficha.comp .lt { font-size: 7.4pt; color: #2b3631; margin-bottom: 1mm }
.ficha.comp .pl { color: #fff; font-size: 6.6pt; padding: .3mm 1.6mm; border-radius: 1mm }
.leyenda.cambio .lc span.vacio { background: #fff; box-shadow: inset 0 0 0 1px #c9d2cc }
table.comp_crit, table.comp_pueblos { margin-top: 3mm }
.vientos { display: grid; grid-template-columns: 1fr 1fr; gap: 3mm 3.5mm }
.vientos figure img { height: auto }
.kpi .debajo { margin-top: 1.6mm; padding-top: 1.6mm; border-top: 1px solid #d9e6df }
.portada { padding: 0; color: #fff } .portada > img, .portada > .falta { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; border-radius: 0 }
.portada .velo { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(8,18,14,.55) 0%, rgba(8,18,14,.05) 30%, rgba(8,18,14,.10) 55%, rgba(8,18,14,.92) 100%) }
.portada .arriba { position: absolute; top: 16mm; left: 16mm; right: 16mm; font-size: 9pt; letter-spacing: .18em; text-transform: uppercase; opacity: .9 }
.portada .texto { position: absolute; left: 16mm; right: 16mm; bottom: 20mm }
.portada h1 { font-size: 30pt; margin: 0 0 3mm; line-height: 1.08 } .portada .sub { font-size: 13pt; opacity: .92; margin-bottom: 8mm }
.portada .datos { display: grid; grid-template-columns: repeat(4, auto); gap: 2mm 9mm; font-size: 8.5pt } .portada .datos b { display: block; font-size: 10pt }
.chip { display: inline-block; width: 2.6mm; height: 2.6mm; border-radius: .7mm; margin-right: 1.3mm; vertical-align: -.25mm }
.chip.vacio { border: 1px solid #c9d2cc }
.leyenda { margin: 2mm 0 1mm } .leyenda .lt { font-size: 7.8pt; color: #515e57; margin-bottom: 1mm }
.leyenda .lc { display: flex; gap: 1px } .leyenda .lc span { flex: 1; height: 3.2mm } .leyenda .lc span:first-child { border-radius: 1mm 0 0 1mm }
.leyenda .lc span:last-child { border-radius: 0 1mm 1mm 0 }
.leyenda .lm { display: flex; justify-content: space-between; font-size: 7.4pt; color: #515e57; margin-top: .6mm }
.barras .fila { display: flex; align-items: center; gap: 2.5mm; margin: 1.1mm 0; font-size: 8.3pt }
.barras .nom { flex: none; white-space: nowrap; overflow: hidden; text-overflow: ellipsis } .barras .nom em { font-style: normal; color: #87928b; font-size: 7.5pt }
.barras .barra { flex: 1; height: 3.4mm; background: #eef2ef; border-radius: 1.7mm; overflow: hidden; position: relative }
.barras .barra i { display: block; height: 100%; border-radius: 1.7mm; position: absolute; left: 0; top: 0 }
.barras .val { width: 15mm; text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap }
.barras .val em { font-style: normal; font-weight: 400; color: #87928b; font-size: 7pt }
.conmax .barras .val { width: 30mm } .conmax .barras .fila { margin: .9mm 0 }
.barras2 { margin-top: 2.5mm; gap: 6mm } .barras2 .barras .fila { margin: .8mm 0 }
.subt { font-size: 8.3pt; font-weight: 600; color: #2b3631; margin-bottom: 1.5mm }
.apilada { display: flex; height: 4.5mm; border-radius: 2.2mm; overflow: hidden; margin: 2.5mm 0 1mm } .apilada i { display: block; height: 100% }
.lista { display: grid; grid-template-columns: repeat(auto-fit, minmax(0, 1fr)); gap: 4mm } .lista table { font-size: 7.3pt; table-layout: fixed }
.lista td { padding: .5mm 1mm; white-space: nowrap; overflow: hidden; text-overflow: ellipsis } .lista td.n { width: 13mm }
.focos .grande img { height: 107mm; object-fit: cover }
.focos .peques { display: grid; grid-template-columns: repeat(4, 1fr); grid-auto-rows: 52mm; gap: 2.5mm; margin-top: 3mm }
.focos .peques.solos { grid-auto-rows: 60mm }
.peque { position: relative; overflow: hidden; border-radius: 2mm; background: #eef3ef }
.peque img { width: 100%; height: 100%; object-fit: cover; border-radius: 2mm }
.peque span { position: absolute; left: 1.5mm; bottom: 1.5mm; font-size: 7pt; background: rgba(255,255,255,.88); padding: .4mm 1.6mm; border-radius: 1.5mm; font-weight: 600 }
.fichas { display: grid; grid-template-columns: 1fr 1fr; gap: 3.5mm }
.ficha { border: 1px solid #dfe5e1; border-radius: 3mm; padding: 2.6mm 3mm; background: #fbfcfb; break-inside: avoid;
         display: grid; grid-template-columns: 23mm 1fr; gap: 2.6mm; align-items: start }
.ficha .fimg { width: 23mm; height: 29mm; overflow: hidden; border-radius: 2mm; background: #eef3ef }
.ficha .fimg img { width: 150%; margin: -14% 0 0 -25%; display: block; border-radius: 0 }
.ficha .fh b { display: block; font-size: 9.6pt } .ficha .fh span { font-size: 7pt; color: #6b7a72 }
.ficha .fc { display: flex; flex-wrap: wrap; gap: .7mm 1mm; margin: 1.3mm 0 1.2mm }
.ficha .ci { display: inline-flex; align-items: center; gap: .9mm; background: #f1f5f2; padding: .25mm 1.3mm; border-radius: 1.3mm }
.ficha .ci > div { display: flex; align-items: baseline; gap: .9mm } .ficha .ci img { width: 3.2mm; height: 3.2mm; flex: none; border-radius: 0 }
.ficha .ci b { display: inline; font-size: 7.1pt; line-height: 1.15 } .ficha .ci span { display: inline; font-size: 6.2pt; color: #6b7a72; line-height: 1.15 }
.ficha .fe { font-size: 7.8pt; color: #2b3631; line-height: 1.3 } .ficha .fe span { font-size: 6.8pt; color: #6b7a72 } .ficha .fe b { color: #1f7a60 }
.ficha .fg { font-size: 6.8pt; color: #515e57; margin-top: .8mm; line-height: 1.35 }
.ficha.op { padding: 2.6mm 2.8mm } .ficha.op .fimg { height: 31mm }
.ficha .ol { font-size: 7.2pt; color: #2b3631; margin: 1mm 0 1.4mm } .ficha .ol b { color: #1f7a60 }
.ficha .ol .pl { color: #fff; font-size: 6.4pt; font-weight: 700; border-radius: 1mm; padding: .2mm 1.3mm; margin-right: 1.4mm; text-transform: uppercase; letter-spacing: .03em }
.sem .sr { display: flex; align-items: center; gap: .2mm; height: 2.5mm; margin: .3mm 0 }
.sem .sr span { width: 3mm; flex: none; font-size: 6pt; color: #87928b; line-height: 1 } .sem .sr i { flex: 1; height: 100%; border-radius: .2mm }
.sem .ejes { display: flex; font-size: 5.4pt; color: #87928b; margin-top: .3mm } .sem .ejes span { width: 3mm; flex: none }
.sem .ejes em { font-style: normal; flex: 1 } .sem .ejes em:last-child { flex: none }
.anio_f { display: flex; gap: .3mm; margin-top: 1.3mm } .anio_f i { flex: 1; height: 3.6mm; border-radius: .4mm; display: flex; align-items: center; justify-content: center }
.anio_f i b { font-size: 5.4pt; font-weight: 700 } .anio_f i.fuera { background: repeating-linear-gradient(45deg, #f1f4f2 0 1mm, #e3e8e4 1mm 2mm) }
.anio_f i.fuera b { color: #87928b }
.ley_f { display: flex; align-items: center; gap: 1.2mm; font-size: 5.8pt; color: #87928b; margin-top: 1mm }
.ley_f i { display: block; width: 18mm; height: 1.8mm; border-radius: .9mm }
.calendario { display: grid; grid-template-columns: 9mm repeat(31, 1fr); gap: .6mm; font-size: 7pt; color: #515e57 }
.calendario .mes { text-align: right; padding-right: 1.5mm; line-height: 4.2mm } .calendario .dia { height: 4.2mm; border-radius: .7mm }
.calendario .nada { background: transparent } .calendario .fuera { background: repeating-linear-gradient(45deg, #f1f4f2 0 .8mm, #e3e8e4 .8mm 1.6mm) }
.calendario .marcado { outline: 1.4px solid #17201c; outline-offset: -.2mm }
.calendario_ep { display: flex; gap: 2.5mm; margin: 1mm 0 }
.calendario_ep .dia_ep { flex: 1; padding: 3mm 2mm; border-radius: 1.4mm; text-align: center; color: #17201c; line-height: 1.5 }
.calendario_ep .dia_ep b { display: block; font-size: 8pt; font-weight: 600 } .calendario_ep .dia_ep em { font-size: 13pt; font-weight: 700; font-style: normal }
.pen_rej { display: flex; flex-direction: column; gap: 2mm; margin-top: 1.5mm }
.pen_fila { display: grid; grid-template-columns: 12mm 78mm 78mm; gap: 3mm; justify-content: center; align-items: center }
.pen_fila .pen_hora { font-weight: 700; font-size: 11pt; text-align: right; color: #2b3631; font-variant-numeric: tabular-nums }
.pen_fila figure.pen_cel { margin: 0; width: 78mm; height: 33mm; overflow: hidden; border-radius: 1mm }
.pen_fila figure.pen_cel img { width: 100%; height: 100%; object-fit: cover; display: block }
.pen_fila.pen_cab { font-size: 8.5pt; color: #515e57; font-weight: 600 }
.pen_fila.pen_cab > div { text-align: center } .pen_fila.pen_cab .pen_hora { text-align: right; color: #515e57; font-weight: 600 }
.escala_cal { display: flex; align-items: center; gap: 2mm; font-size: 7.4pt; color: #515e57; margin-top: 1.5mm }
.escala_cal i { display: block; width: 40mm; height: 2.6mm; border-radius: 1.3mm } .escala_cal span { white-space: nowrap }
.perfil { display: flex; gap: 1mm; height: 24mm; align-items: flex-end; padding: 3mm 0 4mm; position: relative }
.perfil .h { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; position: relative }
.perfil .h i { display: block; width: 100%; border-radius: 1mm 1mm 0 0; flex: none }
.perfil .h b { flex: none; font-size: 5.8pt; font-weight: 600; color: #515e57; margin-bottom: .4mm; font-variant-numeric: tabular-nums }
.perfil .h span { position: absolute; bottom: -4mm; font-size: 6.6pt; color: #87928b }
/* lo que no cabe en su página se aprieta, por niveles (`pdf.AJUSTAR_JS`) */
.apretada-1 p, .apretada-1 .intro { font-size: 8.5pt; line-height: 1.36; margin-bottom: 2mm } .apretada-1 h3 { margin: 3.5mm 0 1.5mm }
.apretada-1 .barras .fila { margin: .45mm 0 } .apretada-1 .kpis { margin: 2mm 0 3mm } .apretada-1 figcaption { font-size: 7.2pt; margin-top: .8mm }
.apretada-1 .apilada { margin: 1.5mm 0 .5mm } .apretada-1 .fichas { gap: 2.5mm }
.apretada-2 .mapa img { max-height: 56mm; object-fit: cover } .apretada-2 .barras .fila { margin: .25mm 0; font-size: 7.8pt }
.apretada-2 .barras .barra { height: 2.8mm } .apretada-2 .ficha { padding: 1.8mm 2.4mm } .apretada-2 .sem .sr { height: 2.1mm; margin: .2mm 0 }
.apretada-3 p, .apretada-3 .intro { font-size: 7.9pt } .apretada-3 .mapa img { max-height: 48mm } .apretada-3 h2 { font-size: 14pt }
.apretada-3 .lista table, .apretada-3 table { font-size: 7pt } .apretada-3 td { padding: .35mm 1mm }
.bq { height: 2.8mm; background: #eef2ef; border-radius: 1.4mm; overflow: hidden; width: 30mm; display: inline-block; vertical-align: middle }
"""
# las fotos del viento, más apaisadas que las de los otros mapas (`capturas` las hace así): tres situaciones, en la zona y de cerca, y su
# texto en una página; si una no lo es, se recorta por arriba y por abajo, y la página cabe igual
PROPORCION_VIENTO = 1.7
CSS += f".vientos figure img {{ aspect-ratio: {PROPORCION_VIENTO}; object-fit: cover }}\n"
