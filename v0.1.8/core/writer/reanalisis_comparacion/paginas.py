# -*- coding: utf-8 -*-
"""Las páginas del informe de un caso del reanálisis, en HTML (A4), de los datos (`datos.reunir`), las fichas de los focos y las imágenes que
haya (`capturas`). Una imagen que falta deja su hueco con lo que es, y lo que no cabe en una página sigue en otra. Sin Qt.

    portada · lo esencial del caso · 1 la planta y su entorno (relieve y usos; edificios y lugares) · 2 focos y operación (los focos en 3D, la
    ficha de cada uno, la operación de la planta y la de cada foco)

La meteorología y los resultados, más adelante.
"""
import datetime as dt
import math

from teodors.comun.formato import num as _num
from teodors.operacion import focos as F
from . import estilo, graficas, textos
from .textos import ci, e, km_txt

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
DIAS_SEM = ("L", "M", "X", "J", "V", "S", "D")
PLANES = {"diario": "diario", "semanal": "semanal", "mensual": "mensual"}
FOCOS_POR_PAGINA = 8                    # fichas y operación: 4 filas de 2
PEQUES_PRIMERA, PEQUES_MAS = 8, 16      # los focos en 3D: bajo la imagen de todos, y en las páginas siguientes
MAX_PUEBLOS, MAX_INDUSTRIAS = 36, 18    # en la página de los lugares
MAX_HORAS = 10                          # lugares en la tabla de cuándo se huele
MAX_ROSAS = 8                           # estaciones con su rosa: 2 filas de 4, bajo el mapa y la de la planta
# el tiempo en la planta, día a día: (clave de `datos.clima`, título, unidad, forma de `graficas.diaria`, desde cero)
GRAFICAS = (("viento", "Velocidad del viento", "m/s", "linea", True), ("direccion", "De dónde sopla el viento", "", "rumbos", False),
            ("temperatura", "Temperatura", "°C", "linea", False), ("humedad", "Humedad relativa", "%", "linea", False),
            ("nubes", "Nubosidad", "%", "linea", True), ("lluvia", "Precipitación", "mm/día", "barras", True),
            ("radiacion", "Radiación solar", "W/m²", "linea", True), ("presion", "Presión en el suelo", "hPa", "linea", False),
            ("friccion", "Velocidad de fricción, u*", "m/s", "linea", True), ("calor", "Calor sensible, hacia arriba", "W/m²", "linea", False),
            ("mezcla", "Altura de la capa de mezcla", "m", "linea", True))


class Informe:
    """Arma las páginas: `imagenes`, {nombre: fichero} de las que hay en img/ (o solo sus nombres, si son .png); `fichas`, {id: lo de la ficha
    de la app} (`capturas.ficha`)."""

    prefijo = ""                                # las imágenes de los resultados: en la comparación, «a_» y «b_»
    seccion = "4 · Resultados"
    pie = "teOdors · informe"                   # cada subclase pone el suyo (reanálisis / episodio / comparación)

    def __init__(self, d, imagenes=(), fichas=None):
        self.d, self.fichas = d, fichas or {}
        self.imagenes = dict(imagenes) if isinstance(imagenes, dict) else {n: f"{n}.png" for n in imagenes}

    def src(self, nombre):
        return f"img/{self.imagenes[nombre]}"
        self.n = 1                                   # la portada es la 1

    # ── piezas ──
    def img(self, nombre, pie=None, clase=""):
        if nombre in self.imagenes:
            cuerpo = f"<img src='{self.src(nombre)}'>"
        else:
            cuerpo = f"<div class='falta'>Sin imagen: {e(nombre.replace('_', ' '))}</div>"
        return f"<figure class='{clase}'>{cuerpo}" + (f"<figcaption>{pie}</figcaption>" if pie else "") + "</figure>"

    def mapa(self, nombre, pie=None, marca=None):
        figura = self.img(nombre, pie, "mapa etq")
        return figura.replace("</figure>", f"<span class='marca'>{marca}</span></figure>") if marca else figura

    def pagina(self, cab, cuerpo):
        self.n += 1
        return (f"<section class='pag'><div class='cab'><span>{e(self.d['planta'])}</span><span>{e(cab)}</span></div>{cuerpo}"
                f"<div class='pie'><span>{e(self.pie)}</span><span>{self.n}</span></div></section>")

    @staticmethod
    def barras(filas, ancho_nombre="38mm", clase=""):
        """[(nombre, detalle, valor, color, texto)] en barras horizontales, la más larga al 100 %."""
        tope = max((f[2] for f in filas), default=1) or 1
        return f"<div class='barras {clase}'>" + "".join(
            f"<div class='fila'><span class='nom' style='width:{ancho_nombre}'>{e(nom)}" + (f" <em>{e(det)}</em>" if det else "") + "</span>"
            f"<span class='barra'><i style='width:{max(1.5, 100 * val / tope):.1f}%;background:{col}'></i></span><span class='val'>{txt}</span></div>"
            for nom, det, val, col, txt in filas) + "</div>"

    def color_banda(self, v):
        niv = self.d["niveles"]
        if v < niv[0]:
            return None
        return self.d["bandas"][max(k for k in range(len(self.d["bandas"])) if v >= niv[k])]

    def leyenda_bandas(self):
        m = self.d["mag"]
        cuadros = "".join(f"<span style='background:{c}'></span>" for c in self.d["bandas"])
        marcas = "".join(f"<span>{f'{x:g}'.replace('.', ',') if x < 1 else _num(x)}</span>" for x in self.d["niveles"])
        return (f"<div class='leyenda'><div class='lt'>Franjas de {e(m['nombre'].lower() if m['clave'] == 'olor' else m['nombre'])} ({e(m['unidad'])}),"
                f" las de los mapas</div><div class='lc'>{cuadros}</div><div class='lm'>{marcas}</div></div>")

    # ── las páginas ──
    def portada(self):
        d, r = self.d, self.d["res"]
        cab, horas = self._portada_cabecera()                       # la cabecera y las horas: cada informe (reanálisis/episodio) la suya
        fondo = f"<img src='{self.src('resultado_entorno')}'>" if "resultado_entorno" in self.imagenes else "<div class='falta'></div>"
        return ("<section class='pag portada'>" + fondo + "<div class='velo'></div>"
                f"<div class='arriba'>{cab}</div>"
                f"<div class='texto'><h1>{e(d['planta'])}</h1><div class='sub'>Caso «{e(r['caso']['nombre'])}» · plan de operación "
                f"«{e(r['nombre'] or 'Base')}»</div><div class='datos'>"
                f"<div><b>{_num(horas)}</b>horas simuladas</div><div><b>{len(d['focos']['focos'])}</b>{'foco' if len(d['focos']['focos']) == 1 else 'focos'}</div>"
                f"<div><b>{len(r['orden'])}</b>{self._magnitudes_txt()}</div><div><b>{d['hoy']:%d/%m/%Y}</b>fecha del informe</div>"
                "</div></div></section>")

    def _magnitudes_txt(self):
        orden = self.d["res"]["orden"]
        gases = len([k for k in orden if k != "olor"])
        if "olor" in orden:
            return "magnitud (olor)" if not gases else f"magnitudes (olor y {gases} {'gas' if gases == 1 else 'gases'})"
        return f"{'gas' if gases == 1 else 'gases'}"

    def esencial(self):
        d, m, est = self.d, self.d["mag"], self.d["estadistico"]
        t = textos.esencial(d)
        pueblos, crit, op = d["pueblos"], d["criterios"], d["operacion"]
        u = e(m["unidad"])
        kpis = []
        if pueblos:
            p0 = pueblos[0]
            kpis.append(f"<div class='kpi'><div class='v'>{ci(p0[est])} <span class='u'>{u}</span></div><div class='t'>{e(d['estadistico_nombre'])} en el "
                        f"pueblo más afectado · {e(p0['nombre'])}</div><div class='mx'>máximo horario: <b>{ci(p0['maximo'])} {u}</b></div></div>")
        if crit:
            kpis += self._kpis_criterios(crit)                      # los KPI de criterios: reanálisis (P98 + peor hora) o episodio (máximo)
        kpis.append(f"<div class='kpi'><div class='v'>{ci(m['maximos'][est])} <span class='u'>{u}</span></div><div class='t'>{e(d['estadistico_nombre'])} "
                    f"más alto de la zona (junto a los focos)</div><div class='mx'>máximo horario: <b>{ci(m['maximos']['maximo'])} {u}</b></div></div>")
        if pueblos:
            kpis.append(f"<div class='kpi'><div class='v'>{len(pueblos)}</div><div class='t'>{'pueblo' if len(pueblos) == 1 else 'pueblos'} en la zona "
                        f"de cálculo, hasta {_num(max(f['km'] for f in pueblos), 0)} km</div></div>")
        modelos = sorted({F.MODELOS.get(f.get("modelo"), f.get("modelo") or "?").lower() for f in d["focos"]["focos"]})
        kpis.append(f"<div class='kpi'><div class='v'>{len(d['focos']['focos'])}</div><div class='t'>{'foco' if len(d['focos']['focos']) == 1 else 'focos'}: "
                    f"{e(', '.join(modelos))} · {_num(op['q'])} ou_E/s al 100 %</div></div>")
        kpis = kpis[:6]
        top = [(f["nombre"], f"{_num(f['km'], 1)} km", f[est], self.color_banda(f[est]) or "#c9d2cc",
                f"{ci(f[est])}<em> · máx. {ci(f['maximo'])}</em>") for f in pueblos[:4]]
        nombre_m = m["nombre"].lower() if m["clave"] == "olor" else m["nombre"]
        cuerpo = (f"<div class='sec'>Resumen</div><h2>Lo esencial del caso</h2><p class='intro'>{t['que']}</p><p>{t['pueblos']}</p>"
                  f"<div class='kpis compacto'>{''.join(kpis)}</div>"
                  f"<div class='dos'>{self.mapa('resultado_zona', f'{e(d['estadistico_nombre'])} de {e(nombre_m)} en la zona de cálculo')}"
                  f"{self.mapa('resultado_entorno', f'{e(d['estadistico_nombre'])} de {e(nombre_m)} alrededor de la planta')}</div>"
                  + (f"<p style='margin-top:3mm'>{t['alcance']}</p>" if t["alcance"] else "")
                  + (f"<div class='subt'>Los pueblos más afectados · {e(d['estadistico_nombre'])} y máximo horario de {e(nombre_m)} ({u})</div>"
                     f"<div class='conmax'>{self.barras(top)}</div>" if top else "")
                  + self.leyenda_bandas() + f"<p class='nota'>{t['gases']}</p>"
                  + "".join(f"<p class='nota'>⚠ {e(a)}</p>" for a in d["avisos"]))
        return self.pagina("Resumen", cuerpo)

    def relieve_usos(self):
        d = self.d
        t = d["terreno"]
        if not t:
            return self.pagina("1 · La planta y su entorno", "<div class='sec'>1 · La planta y su entorno</div><h2>Relieve y usos del suelo</h2>"
                                                            "<p class='intro'>La planta no tiene el terreno descargado: sin relieve ni usos del suelo.</p>")
        from teodors.fuentes import terreno as T
        info, res_t, emp = t["info"], t["resumen"], d["emp"]
        capas = {c["id"]: c for c in info.get("capas_mapa", [])}
        est_t, pl = info.get("estadisticas", {}), info.get("planta", {})
        cap = capas.get("elevacion")
        z0, z1 = (cap["leyenda"]["min"], cap["leyenda"]["max"]) if cap else (est_t.get("z_min", 0), est_t.get("z_max", 1))
        grad = cap["leyenda"]["gradiente"] if cap else ["#59c9a5", "#59c9a5"]
        paradas = [x.strip() for x in grad.split(",")] if isinstance(grad, str) else list(grad)
        limites = [z0, *T.BANDAS_COTA, z1]
        suya = sum(1 for c in T.BANDAS_COTA if pl["z"] >= c) if pl.get("z") is not None else None
        filas_cota = []
        for k, b in enumerate(res_t.get("bandas", [])):
            a_, b_ = limites[k], limites[k + 1]
            txt = f"< {_num(b_)} m" if k == 0 else (f"> {_num(a_)} m" if k == len(limites) - 2 else f"{_num(a_)}–{_num(b_)} m")
            filas_cota.append((txt + (" · la planta" if k == suya else ""), None, b["pct"],
                               estilo.paradas(paradas, ((a_ + b_) / 2 - z0) / max(z1 - z0, 1)), f"{_num(b['pct'], 1)} %"))
        grupos = sorted((g for g in res_t.get("grupos", []) if g["pct"] >= 0.1), key=lambda g: -g["pct"])
        apilada = "".join(f"<i style='width:{g['pct']:.2f}%;background:{g['color']}'></i>" for g in grupos)
        filas_usos = [(g["nombre"], None, g["pct"], g["color"], f"{_num(g['pct'], 1)} %") for g in grupos]
        mc, mu = -(-len(filas_cota) // 2), -(-min(len(filas_usos), 8) // 2)
        uso = (pl.get("uso_nombre") or "").lower()
        relieve, usos = textos.terreno(t, *d["centro"])
        cuerpo = (f"<div class='sec'>1 · La planta y su entorno</div><h2>Relieve y usos del suelo</h2>"
                  f"<p class='intro'>La planta está en {_num(emp['lat'], 5)} N, {_num(emp['lon'], 5)} E, a {_num(pl.get('z') or 0)} m"
                  f"{f', en suelo de {e(uso)}' if uso else ''}. La zona de cálculo es un cuadrado de {_num(info.get('lado_km', 0), 0)} km de lado, con el "
                  f"terreno a {_num(info.get('res_m', 0), 0)} m.</p>"
                  f"<h3>Relieve · de {_num(est_t.get('z_min', 0))} a {_num(est_t.get('z_max', 0))} m</h3><p>{e(relieve)}</p>"
                  f"<div class='dos'>{self.mapa('elevacion', None, 'La zona de cálculo')}{self.mapa('elevacion_entorno', None, 'Alrededor de la planta')}</div>"
                  f"<div class='dos barras2'>{self.barras(filas_cota[:mc], '31mm')}{self.barras(filas_cota[mc:], '31mm')}</div>"
                  f"<h3>Usos del suelo</h3><p>{e(usos)}</p>"
                  f"<div class='dos'>{self.mapa('usos', None, 'La zona de cálculo')}{self.mapa('usos_entorno', None, 'Alrededor de la planta')}</div>"
                  f"<div class='apilada'>{apilada}</div>"
                  f"<div class='dos barras2'>{self.barras(filas_usos[:mu], '37mm')}{self.barras(filas_usos[mu:2 * mu], '37mm')}</div>")
        return self.pagina("1 · La planta y su entorno", cuerpo)

    def edificios_lugares(self):
        d = self.d
        eds = d["edificios"]
        alto = max(eds, key=lambda x: x.get("altura_m") or 0, default=None)
        pueblos = sorted(d["pueblos"], key=lambda f: f["km"])
        ind = sorted(d["industrias"], key=lambda f: f["km"])

        def lista(filas, cols, tope):
            filas = filas[:tope]
            n_ = -(-len(filas) // cols) or 1
            return "<div class='lista'>" + "".join(
                "<table>" + "".join(f"<tr><td>{e(f['nombre'])}</td><td class='n'>{_num(f['km'], 1)} km</td></tr>" for f in filas[i * n_:(i + 1) * n_])
                + "</table>" for i in range(cols)) + "</div>"
        kpis = [f"<div class='kpi mini'><div class='v'>{len(eds)}</div><div class='t'>{'edificio' if len(eds) == 1 else 'edificios'} en la planta"
                + (f" · el más alto, {e(alto.get('nombre') or alto['id'])}, de {_num(alto['altura_m'], 1)} m" if alto and alto.get("altura_m") else "")
                + "</div></div>"]
        kpis.append(f"<div class='kpi mini'><div class='v'>{len(pueblos)}</div><div class='t'>pueblos"
                    + (f" · el más cercano, {e(pueblos[0]['nombre'])}, a {km_txt(pueblos[0]['km'])}" if pueblos else "") + "</div></div>")
        kpis.append(f"<div class='kpi mini'><div class='v'>{len(ind)}</div><div class='t'>zonas industriales"
                    + (f" · la más cercana, {e(ind[0]['nombre'])}, a {km_txt(ind[0]['km'])}" if ind else "") + "</div></div>")
        mas_p = f"<p class='nota'>Y {len(pueblos) - MAX_PUEBLOS} más, hasta {km_txt(pueblos[-1]['km'])}.</p>" if len(pueblos) > MAX_PUEBLOS else ""
        mas_i = f"<p class='nota'>Y {len(ind) - MAX_INDUSTRIAS} más, hasta {km_txt(ind[-1]['km'])}.</p>" if len(ind) > MAX_INDUSTRIAS else ""
        edif = (f"<div class='dos'>{self.mapa('edificios', 'Los edificios junto a la planta')}"
                f"{self.img('edificios_3d', 'En 3D: con ellos se calcula cómo desvían el aire alrededor de los focos', 'mapa')}</div>" if eds else
                f"<div class='dos'>{self.mapa('edificios', 'Junto a la planta')}<p>La planta no tiene edificios definidos: los focos se calculan sin el efecto "
                f"de sus edificios.</p></div>")
        cuerpo = (f"<h3 style='margin-top:0'>Los edificios de la planta</h3>{edif}"
                  "<h3>Los pueblos y las zonas industriales analizados</h3>"
                  "<p class='nota' style='margin:-1mm 0 2mm'>De cerca a lejos de la planta: son los lugares de las tablas de resultados. Un pueblo o una "
                  "zona en varias partes sale una vez, con la distancia de la más cercana.</p>"
                  f"<div class='kpis tres3'>{''.join(kpis)}</div>"
                  f"<div class='dos'><div>{self.mapa('dominio', 'Los núcleos de población (azul) e industriales (amarillo) y las estaciones meteorológicas de la zona de cálculo')}</div>"
                  f"<div><div class='subt'>Pueblos · {len(pueblos)}</div>"
                  + (lista(pueblos, 2, MAX_PUEBLOS) if pueblos else "<p class='nota'>No hay pueblos en la zona de cálculo.</p>") + mas_p + "</div></div>"
                  + (f"<div class='subt' style='margin-top:3mm'>Zonas industriales · {len(ind)}</div>{lista(ind, 3, MAX_INDUSTRIAS)}{mas_i}" if ind else ""))
        return self.pagina("1 · La planta y su entorno", cuerpo)

    def focos_3d(self):
        focos = self.d["focos"]["focos"]
        salen = []

        def peques(fs, clase=""):
            return f"<div class='peques {clase}'>" + "".join(
                f"<div class='peque'>{self._foto_foco(f)}<span>{e(f.get('nombre') or f['id'])}</span></div>" for f in fs) + "</div>"
        primera = focos[:PEQUES_PRIMERA] if len(focos) > 1 else []
        salen.append(self.pagina("2 · Focos y operación", (
            f"<div class='sec'>2 · Focos y operación</div><h2>{'Los focos de olor' if len(focos) != 1 else 'El foco de olor'}</h2>"
            f"<p class='intro'>{len(focos)} {'focos' if len(focos) != 1 else 'foco'}, con los edificios de la planta"
            + (": arriba, todos juntos; debajo, cada uno.</p>" if primera else ".</p>")
            + f"<div class='focos'>{self.img('focos_3d', None, 'grande')}{peques(primera) if primera else ''}</div>")))
        for k in range(PEQUES_PRIMERA, len(focos), PEQUES_MAS):
            salen.append(self.pagina("2 · Focos y operación", "<h2 style='margin-top:0'>Los focos en 3D (sigue)</h2>"
                                     f"<div class='focos'>{peques(focos[k:k + PEQUES_MAS], 'solos')}</div>"))
        return salen

    def fichas_focos(self):
        focos = self.d["focos"]["focos"]
        salen = []
        tarjetas = []
        for f in focos:
            fi = self.fichas.get(f["id"]) or ficha_basica(f)
            cif = "".join(f"<div class='ci'>" + (f"<img src='{self.src(f'ico_{ic}')}'>" if f"ico_{ic}" in self.imagenes else "")
                          + f"<div><b>{e(val)}</b><span>{e(que)}</span></div></div>"
                          for ic, val, que in fi.get("cifras", []) if que not in ("clase", "pila o hilera"))
            gtxt = " · ".join(f"<b>{e(nm)}</b> {caudal(g_s)}" for nm, g_s in gases_por_olor(f)[:5])
            tarjetas.append(f"<div class='ficha'><div class='fimg'>{self._foto_foco(f)}</div><div>"
                            f"<div class='fh'><b>{e(f.get('nombre') or f['id'])}</b><span>{e(fi.get('sub', ''))}</span></div>"
                            f"<div class='fc'>{cif}</div>"
                            f"<div class='fe'>Olor <b>{e(fi.get('olor', '—'))}</b> <span>{e(fi.get('detalle', ''))}</span></div>"
                            + (f"<div class='fg'>{gtxt}</div>" if gtxt else "") + "</div></div>")
        modelos = {}
        for f in focos:
            nm = F.MODELOS.get(f.get("modelo"), f.get("modelo") or "?").lower()
            modelos[nm] = modelos.get(nm, 0) + 1
        for k in range(0, len(tarjetas), FOCOS_POR_PAGINA):
            cab = ("<h2 style='margin-top:0'>Ficha de cada foco</h2>"
                   f"<p class='intro'>{len(focos)} {'focos' if len(focos) != 1 else 'foco'} ({', '.join(f'{v_} de {k_}' for k_, v_ in modelos.items())}), "
                   f"que emiten {_num(self.d['operacion']['q'])} ou_E/s de olor con todos al 100 %: cada uno, como en su ficha de la app.</p>"
                   if k == 0 else "<h2 style='margin-top:0'>Ficha de cada foco (sigue)</h2>")
            salen.append(self.pagina("2 · Focos y operación", cab + f"<div class='fichas'>{''.join(tarjetas[k:k + FOCOS_POR_PAGINA])}</div>"))
        return salen

    def _foto_foco(self, f):
        return f"<img src='{self.src(f'foco_{f['id']}')}'>" if f"foco_{f['id']}" in self.imagenes else ""

    def operacion_planta(self):
        d, op = self.d, self.d["operacion"]
        r = d["res"]
        valores = [v for _, v in op["dias"] if v is not None]
        lo, hi = min(valores), max(valores)
        color_dia = estilo.estirada(lo, hi) if hi - lo > 1e-6 else (lambda v: estilo.rampa(0.6))
        horas = op["horas"]
        h_lo, h_hi = min(horas), max(horas)
        color_h = estilo.estirada(h_lo, h_hi)
        base = max(0.0, h_lo - 0.35 * (h_hi - h_lo)) if h_hi - h_lo > 1e-6 else 0.0
        alto = (lambda x: 18 + 64 * (x - base) / (h_hi - base)) if h_hi - h_lo > 1e-6 else (lambda x: 82)
        perfil = "".join(f"<div class='h'><b>{round(100 * x)}</b><i style='height:{alto(x):.0f}%;background:{color_h(x)}'></i><span>{h:02d}</span></div>"
                         for h, x in enumerate(horas))
        leyenda = (f"<div class='escala_cal'><i style='background:{estilo.rampa(0.6)};width:8mm'></i><span>{_num(100 * lo, 0)} % de lo que emitiría con "
                   "todos los focos al 100 %, igual todos los días</span></div>" if hi - lo < 1e-6 else
                   f"<div class='escala_cal'><span>{_num(100 * lo, 0)} %</span><i style='background:{estilo.gradiente()}'></i><span>{_num(100 * hi, 0)} % · de "
                   "lo que emitiría con todos los focos al 100 %</span></div>")
        if op["mes"]:
            leyenda += f"<p class='nota'>El plan es de {MESES[op['mes'] - 1]}: los demás meses no cuentan (rayados).</p>"
        q_max = max((f["q"] for f in op["focos"]), default=1.0) or 1.0
        focos = sorted(op["focos"], key=lambda f: -f["q"])
        filas = ""
        for f in focos[:16]:
            col = estilo.COLOR_MODELO.get(f["modelo"], "#59c9a5")
            filas += (f"<div class='fila'><span class='nom' style='width:50mm'>{e(f['nombre'])} <em>{e(F.MODELOS.get(f['modelo'], f['modelo'] or '').lower())}</em></span>"
                      f"<span class='barra'><i style='width:{max(1.5, 100 * f['q'] / q_max):.1f}%;background:{estilo.mezcla('#ffffff', col, .35)}'></i>"
                      f"<i style='width:{max(1.0, 100 * f['q'] * f['media'] / q_max):.1f}%;background:{col}'></i></span>"
                      f"<span class='val' style='width:34mm'>{_num(f['q'] * f['media'])} <em>de {_num(f['q'])} ou_E/s</em></span></div>")
        if len(focos) > 16:
            filas += f"<p class='nota'>Y {len(focos) - 16} focos más, que emiten menos.</p>"
        tipos = textos.y_lista(f"{v_} con plan {PLANES.get(k_, k_)}" for k_, v_ in op["tipos"].items())
        cuerpo = (f"<h2 style='margin-top:0'>La operación: plan «{e(r['nombre'] or 'Base')}»</h2>"
                  f"<p class='intro'>{e(r['esc'].get('notas') or 'Cuánto emite cada foco cada día y cada hora, según el plan de operación (en hora oficial).')}</p>"
                  "<div class='kpis tres3'>"
                  f"<div class='kpi mini'><div class='v'>{_num(op['q'])} <span class='u'>ou_E/s</span></div><div class='t'>la planta, con todos los focos al 100 %</div></div>"
                  f"<div class='kpi mini'><div class='v'>{_num(100 * op['media'], 0)} %</div><div class='t'>lo que emite de media con el plan "
                  f"({_num(op['q'] * op['media'])} ou_E/s)</div></div>"
                  f"<div class='kpi mini'><div class='v'>{len(op['focos'])}</div><div class='t'>{'foco' if len(op['focos']) == 1 else 'focos'}: {e(tipos)}</div></div>"
                  "</div>"
                  + self._calendario_planta(op, color_dia, leyenda)  # el calendario de la planta: el año (reanálisis) o los 3 días (episodio)
                  + f"<div class='subt' style='margin-top:4mm'>Toda la planta · el día medio, hora a hora</div><div class='perfil'>{perfil}</div>"
                  "<h3>Lo que emite cada foco</h3>"
                  "<p class='nota' style='margin:-1mm 0 2mm'>De olor, en ou_E/s: la barra clara, con el foco al 100 %; la oscura, de media con el plan.</p>"
                  f"<div class='barras'>{filas}</div>"
                  + "<div class='narra'>" + "".join(f"<p><b>{e(t)}.</b> {h}</p>" for t, h in textos.operacion(d)) + "</div>")
        return self.pagina("2 · Focos y operación", cuerpo)

    def operacion_focos(self):
        op = self.d["operacion"]
        focos_f = {f["id"]: f for f in self.d["focos"]["focos"]}
        tarjetas = []
        for f in sorted(op["focos"], key=lambda f: -f["q"]):
            col = estilo.COLOR_MODELO.get(f["modelo"], "#59c9a5")
            valores = [x for _, perf in f["semana"] for x in perf] + list(f["meses"].values())
            lo, hi = min(valores), max(valores)
            color_f = estilo.estirada(lo, hi)

            def letra(v):
                claro = hi - lo < 1e-6 or (v - lo) / (hi - lo) > 0.45
                return "rgba(255,255,255,.92)" if claro else "#7a5a1e"
            semana = "".join(f"<div class='sr'><span>{DIAS_SEM[w]}</span>" + "".join(f"<i style='background:{color_f(x)}'></i>" for x in perf) + "</div>"
                             for w, perf in f["semana"])
            tira = "".join((f"<i style='background:{color_f(f['meses'][mm])}'><b style='color:{letra(f['meses'][mm])}'>{MESES[mm - 1][0].upper()}</b></i>"
                            if mm in f["meses"] else f"<i class='fuera'><b>{MESES[mm - 1][0].upper()}</b></i>") for mm in range(1, 13))
            ley = (f"<div class='ley_f'><i style='background:{estilo.rampa(0.6)};width:5mm'></i><span>{_num(100 * lo, 0)} % siempre</span></div>"
                   if hi - lo < 1e-6 else
                   f"<div class='ley_f'><span>{_num(100 * lo, 0)} %</span><i style='background:{estilo.gradiente()}'></i><span>{_num(100 * hi, 0)} %</span></div>")
            parte = 100 * f["q"] * f["media"] / (op["q"] * op["media"] or 1)
            fi = self.fichas.get(f["id"]) or ficha_basica(focos_f.get(f["id"], {"id": f["id"], "modelo": f["modelo"]}))
            tarjetas.append(
                f"<div class='ficha op'><div class='fimg'>{self._foto_foco(f)}</div><div>"
                f"<div class='fh'><b>{e(f['nombre'])}</b><span>{e(fi.get('sub', ''))}</span></div>"
                f"<div class='ol'><span class='pl' style='background:{col}'>plan {PLANES.get(f['plan'], f['plan'])}</span><b>{_num(100 * f['media'], 0)} %</b> de "
                f"media · {_num(f['q'] * f['media'])} de {_num(f['q'])} ou_E/s · {'< 1' if 0 < parte < 0.5 else _num(parte, 0)} % del olor de la planta</div>"
                f"<div class='sem'>{semana}<div class='ejes'><span></span><em>0</em><em>6</em><em>12</em><em>18</em><em>23 h</em></div></div>"
                f"<div class='anio_f'>{tira}</div>{ley}</div></div>")
        salen = []
        for k in range(0, len(tarjetas), FOCOS_POR_PAGINA):
            cab = ("<h2 style='margin-top:0'>La operación de cada foco</h2><p class='intro'>Su semana tipo, de lunes a domingo y hora a hora (lo que dice su "
                   "plan, en hora oficial), y su año, mes a mes. Del amarillo al rojo, de lo que menos a lo que más emite cada foco: la escala de cada uno, "
                   "debajo, en % de su emisión al 100 %.</p>" if k == 0 else "<h2 style='margin-top:0'>La operación de cada foco (sigue)</h2>")
            salen.append(self.pagina("2 · Focos y operación", cab + f"<div class='fichas'>{''.join(tarjetas[k:k + FOCOS_POR_PAGINA])}</div>"))
        return salen

    # ── 3 · Meteorología (el reanálisis: usuario, 2026-11-10) ──
    def _tarjeta_rosa(self, img, titulo, sub, pie, destacada=False, codigo=None):
        cod = f"<span class='cod'>{e(codigo)}</span>" if codigo else ""
        return (f"<div class='rosa{' destacada' if destacada else ''}'><div class='rt'>{cod}{e(titulo)}</div><div class='rs'>{e(sub)}</div>"
                + self.img(img) + f"<div class='rp'>{pie}</div></div>")

    def meteo_estaciones(self):
        d, me = self.d, self.d["meteo"]
        p = me["planta"]
        est = (me.get("estaciones") or {}).get("lista", [])
        punto = (me.get("era5") or {}).get("punto")
        planta = self._tarjeta_rosa("rosa_planta", "La planta", self._meteo_sub(p),
                                    f"del {p['dominante']}, {_num(p['dominante_pct'], 0)} % · calmas {_num(p['calmas'], 1)} %", True)
        ley = ("<div class='rosa ley'>" + self.img("rosa_leyenda", clase="leyenda_rosa") + "<p>Cada pétalo, un rumbo: de dónde sopla el viento; "
               "su largo, el % de las horas, y sus colores, la velocidad.</p></div>")
        tarjetas = []
        for s in est[:MAX_ROSAS]:
            sub = f"a {textos.km_txt(s['km'])} al {s['desde_planta']}" + (f" · a {_num(s['altura'])} m" if s.get("altura") else "")
            tarjetas.append(self._tarjeta_rosa(f"rosa_{s['codigo']}", s["nombre"], sub,
                                               f"del {s['dominante']}, {_num(s['dominante_pct'], 0)} % · calmas {_num(s['calmas'], 1)} %",
                                               codigo=s["codigo"]))
        resto = f"<p class='nota'>Y {len(est) - MAX_ROSAS} estaciones más, más lejos.</p>" if len(est) > MAX_ROSAS else ""
        pie = (f"{'La estación' if len(est) == 1 else f'Las {len(est)} estaciones'} de la zona, con su código, y la planta (en verde)"
               + (f"; el rombo, la celda del ERA5, a {textos.km_txt(punto['dist_planta_m'] / 1000.0)} al {punto['rumbo_desde_planta']}." if punto
                  else "."))
        texto = "".join(f"<p><b>{e(t)}.</b> {h}</p>" for t, h in textos.meteo_estaciones(d))
        cuerpo = ("<div class='sec'>3 · Meteorología</div><h2>El viento: la planta y las estaciones</h2>"
                  f"<p class='intro'>{self._meteo_intro()}</p>"
                  f"<div class='est_arriba'>{self.mapa('estaciones', pie, 'Las estaciones')}<div class='est_lado'>{planta}{ley}</div></div>"
                  f"<div class='rosas cuatro'>{''.join(tarjetas)}</div>{resto}<div class='narra'>{texto}</div>")
        return self.pagina("3 · Meteorología", cuerpo)

    def meteo_clima(self):
        """El tiempo en la planta, día a día (`datos.clima`), y el texto final de la meteorología."""
        c = self.d["meteo"]["era5"]
        r, p = c["resumen"], c.get("punto")
        cifras = textos.clima_cifras(r)
        casillas = []
        for clave, nombre, unidad, forma, cero in GRAFICAS:
            s = c["series"].get(clave)
            if not s or not any(math.isfinite(x) for x in s["v"]):
                continue
            svg = graficas.diaria(c["dias"], s["v"], s.get("min"), s.get("max"), forma, desde_cero=cero, titulo=nombre)
            casillas.append(f"<div class='graf'><div class='gt'><b>{e(nombre)}</b>{f' · {e(unidad)}' if unidad else ''}</div>"
                            f"<div class='gs'>{e(cifras.get(clave, ''))}</div>{svg}</div>")
        clave = [("dia", "cada día, su media"), ("media", f"la media de {graficas.MEDIA_DIAS} días"),
                 ("banda", "lo menos y lo más del día (media de 30 días)"), ("barras", "la lluvia de cada día"),
                 ("rumbos", "de dónde sopla cada día (su viento medio)")]
        casillas.append("<div class='graf clave'><b>Cómo se leen</b>" + "".join(f"<div>{graficas.muestra(f)}<span>{t}</span></div>" for f, t in clave)
                        + "<div class='nota'>Los días, en hora oficial.</div></div>")
        anios = f"{r['desde'].year}–{r['hasta'].year}"
        donde = (f"del ERA5 en su celda más cercana, a {textos.km_txt(p['dist_planta_m'] / 1000.0)} al {p['rumbo_desde_planta']} de la planta"
                 if p else "del ERA5")
        texto = "".join(f"<p><b>{e(t)}.</b> {h}</p>" for t, h in textos.meteo_clima(self.d))
        cuerpo = ("<h2 style='margin-top:0'>El tiempo en la planta, día a día</h2>"
                  f"<p class='intro'>Los años del reanálisis ({anios}), día a día. El viento es el de la planta (el del viento 3D, el de las rosas); "
                  f"lo demás, {donde}.</p><div class='graficas'>{''.join(casillas)}</div><div class='narra'>{texto}</div>")
        return self.pagina("3 · Meteorología", cuerpo)

    def meteo_situaciones(self):
        d, me = self.d, self.d["meteo"]
        figs = ""
        for clave, titulo, ev in textos.situaciones(me["eventos"]):
            dia, hora = textos.hora_local(ev["hora"])
            figs += (self.mapa(f"viento_{clave}_zona", f"{titulo} · {dia}, {hora} · {_num(ev['ws'], 1)} m/s del {ev['rumbo']} en la planta", "En la zona")
                     + self.mapa(f"viento_{clave}_planta", "De cerca, con los edificios de la planta", "Alrededor de la planta"))
        n = len(me["eventos"]["frecuentes"])
        cuales = "la situación más frecuente" if n == 1 else f"las {textos.NUMEROS.get(n, n)} situaciones más frecuentes"
        texto = "".join(f"<p><b>{e(t)}.</b> {h}</p>" for t, h in textos.meteo_situaciones(d))
        cuerpo = (f"<h2 style='margin-top:0'>El viento en el mapa: {cuales} y la más extrema</h2>"
                  "<p class='intro'>Las líneas de corriente del viento cerca del suelo, a la hora de cada situación, en la zona de cálculo y "
                  "alrededor de la planta.</p>"
                  f"<div class='vientos'>{figs}</div><div class='narra'>{texto}</div>")
        return self.pagina("3 · Meteorología", cuerpo)

    # ── 4 · Resultados (usuario, 2026-11-10: los mapas del olor y cuándo se huele en los pueblos) ──
    def resultados_mapas(self):
        d = self.d
        figs = ""
        for clave, titulo in textos.ESTADISTICOS:
            a = (d.get("alcances") or {}).get(clave)
            if not a:
                continue
            a1 = a[0]
            pie = (f"{titulo} · más de {_num(a1['umbral'])} {e(d['mag']['unidad'])} en {_num(a1['km2'], 2)} km², hasta "
                   f"{textos.km_txt(a1['hasta_km'])} al {a1['rumbo']}" if a1["hasta_km"] is not None else
                   f"{titulo} · por debajo de {_num(a1['umbral'])} {e(d['mag']['unidad'])} en toda la zona")
            figs += (self.mapa(f"{self.prefijo}resultado_{clave}_zona", pie, "En la zona")
                     + self.mapa(f"{self.prefijo}resultado_{clave}_entorno", "De cerca", "Alrededor de la planta"))
        texto = "".join(f"<p><b>{e(t)}.</b> {h}</p>" for t, h in textos.resultados_mapas(d))
        h2, intro = self._resultados_cabecera()                     # título e intro: reanálisis (3 estadísticos, P98) o episodio (2, sin P98)
        cuerpo = (f"<div class='sec'>{e(self.seccion)}</div><h2>{h2}</h2>"
                  f"<p class='intro'>{intro}</p>"
                  f"<div class='vientos'>{figs}</div>" + self.leyenda_bandas() + f"<div class='narra'>{texto}</div>")
        return self.pagina(self.seccion, cuerpo)

    def resultados_cuando(self):
        h = self.d["horas"]
        lug = [f for f in h["lugares"] if f["horas"][0] > 0][:MAX_HORAS] or h["lugares"][:3]
        filas = "".join(
            f"<tr><td>{e(f['nombre'])}</td><td class='n'>{_num(f['km'], 1) if f.get('km') is not None else ''}</td>"
            + "".join(f"<td class='n'>{_num(x, 0 if x >= 10 or x == 0 else 1)}</td>" for x in f["horas"])
            + f"<td class='n'>{_num(f['dias'], 0 if f['dias'] >= 10 or f['dias'] == 0 else 1)}</td>"
            f"<td class='n'>{textos.ci(f['peor']['valor'])}</td><td>{f['peor']['dia']}, {f['peor']['hora']}</td></tr>" for f in lug)
        tabla = ("<table class='horas'><tr><th>Lugar</th><th class='n'>km</th><th class='n'>&gt; 1</th><th class='n'>&gt; 3</th><th class='n'>&gt; 5</th>"
                 "<th class='n'>días &gt; 1</th><th class='n'>peor hora</th><th>cuándo</th></tr>" + filas + "</table>"
                 "<p class='nota'>Horas al año por encima de 1, 3 y 5 ou_E/m³ y días al año con alguna; la peor hora, en ou_E/m³, en hora oficial. "
                 "Cada pueblo, lo peor de sus casas en cada hora.</p>")
        calores = ""
        if h["calor"]:
            tope = max(max(max(fila) for fila in c["M"]) for c in h["calor"]) or 1.0
            calores = ("<div class='calores'>" + "".join(
                f"<div class='calor_c'><div class='gt'><b>{e(c['nombre'])}</b></div>{graficas.calor(c['M'], tope, c['nombre'])}</div>"
                for c in h["calor"]) + "</div>"
                f"<div class='ley_f ley_calor'><span>Horas al año por encima de 1 ou_E/m³, por mes (filas) y hora del día (columnas): 0</span>"
                f"<i style='background:{estilo.gradiente()}'></i><span>{_num(tope, 1)}</span></div>")
        peores = h.get("peores") or []
        tabla_p = ""
        if peores:
            def viento(p):
                return f"{_num(p['ws'], 1)} m/s del {p['rumbo']}" if p.get("ws") is not None else "—"

            def aire(p):
                if p.get("H") is None:
                    return "—"
                return textos.aire_txt(p["H"]) + (f", mezcla a {textos._decenas(p['blh'])} m" if p.get("blh") is not None else "")
            tabla_p = ("<h3>Los peores días</h3><table class='horas'><tr><th>Día</th><th>Hora</th><th>Pueblo</th><th class='n'>ou_E/m³</th>"
                       "<th class='n'>horas &gt; 1</th><th>Viento en la planta</th><th>Aire</th></tr>"
                       + "".join(f"<tr><td>{p['dia']}</td><td>{p['hora']}</td><td>{e(p['pueblo'])}</td><td class='n'>{textos.ci(p['valor'])}</td>"
                                 f"<td class='n'>{p['horas']}</td><td>{viento(p)}</td><td>{aire(p)}</td></tr>" for p in peores) + "</table>"
                       + ("<p class='nota'>Serie de prueba: el viento y el aire, los del día simulado del que se copió cada uno ("
                          + ", ".join(f"{p['dia']} ← {p['origen']}" for p in peores if p.get("origen")) + ").</p>"
                          if any(p.get("origen") for p in peores) else ""))
        texto = "".join(f"<p><b>{e(t)}.</b> {x}</p>" for t, x in textos.cuando(self.d))
        cuerpo = ("<h2 style='margin-top:0'>Cuándo se huele en los pueblos</h2>"
                  f"<p class='intro'>La hora a hora del olor en cada pueblo y en la vivienda más expuesta, en los {_num(h['anios'], 0)} años del "
                  "reanálisis: cuántas horas pasa de cada umbral, en qué meses y a qué horas, y los peores días con su viento y su aire.</p>"
                  + tabla + calores + tabla_p + f"<div class='narra'>{texto}</div>")
        return self.pagina(self.seccion, cuerpo)

    # ── los puntos donde cada informe (reanálisis / episodio) se diferencia; las subclases los implementan ──
    def _portada_cabecera(self):
        """La cabecera de la portada y las horas simuladas: (texto, nº de horas)."""
        raise NotImplementedError

    def _kpis_criterios(self, crit):
        """Los KPI de los criterios de olor (pueblos y superficie por umbral): [HTML]."""
        raise NotImplementedError

    def _calendario_planta(self, op, color_dia, leyenda):
        """El subtítulo + la rejilla del calendario de emisión de la planta."""
        raise NotImplementedError

    def _meteo_sub(self, p):
        """El subtítulo de la rosa de la planta."""
        raise NotImplementedError

    def _meteo_intro(self):
        """La entradilla de la página de estaciones y rosas."""
        raise NotImplementedError

    def _resultados_cabecera(self):
        """El título y la entradilla de la página de mapas de resultados: (h2, intro)."""
        raise NotImplementedError

    def _paginas_resultados(self):
        """Las páginas de la sección de resultados (mapas y, según el informe, cuándo se huele / el penacho)."""
        raise NotImplementedError

    def html(self):
        """El informe entero."""
        self.n = 1
        paginas = [self.portada(), self.esencial(), self.relieve_usos(), self.edificios_lugares(),
                   *self.focos_3d(), *self.fichas_focos(), self.operacion_planta(), *self.operacion_focos()]
        if self.d.get("meteo"):                                  # detrás: el número de página va por orden
            paginas += [self.meteo_estaciones(), self.meteo_situaciones()]
            if self.d["meteo"].get("era5"):                      # el tiempo en la planta y el texto final de la meteorología
                paginas.append(self.meteo_clima())
        if self.d.get("alcances"):                               # 4 · Resultados: los mapas del olor y, según el informe, cuándo se huele / el penacho
            paginas += self._paginas_resultados()
        return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{e(self.d['res']['caso']['nombre'])}</title>"
                f"<style>{estilo.CSS}</style></head><body>{''.join(paginas)}</body></html>")


class InformeReanalisis(Informe):
    """El informe de un caso del reanálisis (los años completos): el estadístico de referencia es el P98, el calendario es el año entero, y la
    sección de resultados trae los mapas (media, máximo y P98) y el «cuándo se huele» al año."""

    pie = "teOdors · informe de un caso del reanálisis"

    def _portada_cabecera(self):
        dd = self.d["res"]["datos"]
        return f"Informe de dispersión de olores · reanálisis {dd['ini'][:4]}–{dd['fin'][:4]}", dd["horas"]

    def _kpis_criterios(self, crit):
        kpis = [f"<div class='kpi'><div class='v'>{' · '.join(str(c['pueblos']) for c in crit)}</div><div class='t'>pueblos con P98 &gt; "
                f"{' · '.join(_num(c['umbral']) for c in crit)} ou_E/m³</div>"          # y debajo, igual de grande, en su peor hora
                f"<div class='debajo'><div class='v'>{' · '.join(str(c['pueblos_maximo']) for c in crit)}</div><div class='t'>pueblos con "
                f"máximo horario &gt; {' · '.join(_num(c['umbral']) for c in crit)} ou_E/m³</div></div></div>"]
        c3 = next((c for c in crit if c["umbral"] == 3), crit[-1])
        kpis.append(f"<div class='kpi'><div class='v'>{_num(c3['km2'], 2)} <span class='u'>km²</span></div><div class='t'>superficie "
                    f"con P98 &gt; {_num(c3['umbral'])} ou_E/m³</div></div>")
        return kpis

    def _calendario_planta(self, op, color_dia, leyenda):
        por_fecha = dict(op["dias"])
        celdas = ""
        for mes in range(1, 13):
            celdas += f"<div class='mes'>{MESES[mes - 1]}</div>"
            for dia in range(1, 32):
                try:
                    f_ = dt.date(op["anio"], mes, dia)
                except ValueError:
                    celdas += "<div class='dia nada'></div>"
                    continue
                v = por_fecha[f_]
                celdas += ("<div class='dia fuera'></div>" if v is None else
                           f"<div class='dia' style='background:{color_dia(v)}' title='{f_:%d/%m}: {round(100 * v)} %'></div>")
        return (f"<div class='subt'>Toda la planta · el año, día a día ({op['anio']}), en % de lo que emitiría con todos los focos al 100 %</div>"
                f"<div class='calendario'>{celdas}</div>{leyenda}")

    def _meteo_sub(self, p):
        return f"viento del reanálisis · {p['desde'][:4]}–{p['hasta'][:4]}"

    def _meteo_intro(self):
        return ("Dónde están las estaciones de la zona, y la rosa de los vientos de la planta (el viento del reanálisis) y la de cada estación en "
                "esos años: de dónde sopla, cuántas horas y con qué fuerza.")

    def _resultados_cabecera(self):
        return ("El olor en el mapa: la media, el máximo y el P98",
                "Los tres estadísticos del olor en los años del reanálisis, en la zona de cálculo y alrededor de la planta.")

    def _paginas_resultados(self):
        paginas = [self.resultados_mapas()]
        if self.d.get("horas"):                                  # «cuándo se huele en los pueblos» (al año): solo si se guardó la hora a hora
            paginas.append(self.resultados_cuando())
        return paginas


class InformeComparacion(InformeReanalisis):
    """El informe de la comparación de dos escenarios del reanálisis (`datos.reunir_comparacion`; usuario, 2026-11-10: «mantener la estructura
    del informe de las cosas en común (lugar, pueblos, focos, meteo) y comparar la operabilidad entre los dos casos, luego el informe de
    resultados individual de cada uno y por último una página comparativa»): portada; la planta y su entorno, los focos y la meteorología,
    como en el de un escenario (los de A); la operación de los dos; los resultados de A y los de B; y la comparación."""

    pie = "teOdors · informe de la comparación de dos escenarios del reanálisis"

    def __init__(self, dc, imagenes=(), fichas=None):
        super().__init__(dc["a"], imagenes, fichas)
        self.dc = dc
        self.na, self.nb = textos.escenario(dc["a"], "A"), textos.escenario(dc["b"], "B")

    def portada(self):
        a, b = self.dc["a"], self.dc["b"]
        dd = a["res"]["datos"]
        fondo = f"<img src='{self.src('cambio_entorno')}'>" if "cambio_entorno" in self.imagenes else (
            f"<img src='{self.src('resultado_entorno')}'>" if "resultado_entorno" in self.imagenes else "<div class='falta'></div>")
        return ("<section class='pag portada'>" + fondo + "<div class='velo'></div>"
                f"<div class='arriba'>Informe de comparación de escenarios · reanálisis {dd['ini'][:4]}–{dd['fin'][:4]}</div>"
                f"<div class='texto'><h1>{e(a['planta'])}</h1><div class='sub'>«{e(a['res']['nombre'] or 'Base')}» frente a "
                f"«{e(b['res']['nombre'] or 'Base')}»</div><div class='datos'>"
                f"<div><b>{_num(dd['horas'])}</b>horas simuladas</div><div><b>{len(a['focos']['focos'])}</b>"
                f"{'foco' if len(a['focos']['focos']) == 1 else 'focos'}</div>"
                f"<div><b>A</b>{e(a['res']['caso']['nombre'])}</div><div><b>B</b>{e(b['res']['caso']['nombre'])}</div>"
                f"<div><b>{self.dc['hoy']:%d/%m/%Y}</b>fecha del informe</div></div></div></section>")

    def _calendario(self, op, color_dia):
        import datetime as dt
        por_fecha = dict(op["dias"])
        celdas = ""
        for mes in range(1, 13):
            celdas += f"<div class='mes'>{MESES[mes - 1][0].upper()}</div>"
            for dia in range(1, 32):
                try:
                    f_ = dt.date(op["anio"], mes, dia)
                except ValueError:
                    celdas += "<div class='dia nada'></div>"
                    continue
                v = por_fecha[f_]
                celdas += "<div class='dia fuera'></div>" if v is None else f"<div class='dia' style='background:{color_dia(v)}'></div>"
        return f"<div class='calendario'>{celdas}</div>"

    def operacion_comparada(self):
        a, b, op = self.dc["a"], self.dc["b"], self.dc["op"]
        oa, ob = a["operacion"], b["operacion"]
        valores = [v for o in (oa, ob) for _, v in o["dias"] if v is not None]
        lo, hi = min(valores), max(valores)
        color_dia = estilo.estirada(lo, hi)
        ley = (f"<div class='escala_cal'><span>{_num(100 * lo, 0)} %</span><i style='background:{estilo.gradiente()}'></i><span>{_num(100 * hi, 0)} % · "
               "de lo que emitiría con todos los focos al 100 %, la misma escala en los dos</span></div>" if hi - lo > 1e-6 else
               f"<div class='escala_cal'><i style='background:{estilo.rampa(0.6)};width:8mm'></i><span>{_num(100 * lo, 0)} % todos los días, en los "
               "dos</span></div>")
        cal = (f"<div class='dos_cal'><div><div class='subt'><span class='chip' style='background:{graficas.COLOR_A}'></span>{e(self.na)}</div>"
               f"{self._calendario(oa, color_dia)}</div><div><div class='subt'><span class='chip' style='background:{graficas.COLOR_B}'></span>"
               f"{e(self.nb)}</div>{self._calendario(ob, color_dia)}</div></div>")
        ea, eb = op["a"]["emite"], op["b"]["emite"]
        kpis = ("<div class='kpis tres3'>"
                f"<div class='kpi mini'><div class='v'>{_num(ea)} <span class='u'>ou_E/s</span></div><div class='t'>{e(self.na)}: de media, el "
                f"{_num(100 * op['a']['media'], 0)} % de todo al 100 %</div></div>"
                f"<div class='kpi mini'><div class='v'>{_num(eb)} <span class='u'>ou_E/s</span></div><div class='t'>{e(self.nb)}: de media, el "
                f"{_num(100 * op['b']['media'], 0)} % de todo al 100 %</div></div>"
                f"<div class='kpi mini'><div class='v'>{('+' if eb > ea else '−') + _num(abs(100 * (eb - ea) / ea), 0) if ea > 0 and abs(eb - ea) > 1e-6 else '='}"
                f" <span class='u'>%</span></div><div class='t'>lo que emite B frente a A</div></div></div>")
        dia = (f"<div class='subt' style='margin-top:3.5mm'>El día medio, hora a hora, en % de todo al 100 %: "
               f"<span class='chip' style='background:{graficas.COLOR_A}'></span>{e(self.na)} "
               f"<span class='chip' style='background:{graficas.COLOR_B}'></span>{e(self.nb)}</div>"
               + graficas.dia_dos(oa["horas"], ob["horas"], titulo="El día medio de los dos escenarios"))
        filas = ""
        for f in op["focos"][:16]:
            def celda(x):
                return "—" if x is None else f"{_num(100 * x, 0)} % <em>{_num(f['q'] * x)}</em>"
            cambio = ("" if f["igual"] or f["a"] is None or f["b"] is None or f["a"] == 0 else
                      f"{'+' if f['b'] > f['a'] else '−'}{_num(abs(100 * (f['b'] - f['a']) / f['a']), 0)} %")
            filas += (f"<tr class='{'' if f['igual'] else 'cambia'}'><td>{e(f['nombre'])}</td><td class='n'>{_num(f['q'])}</td>"
                      f"<td class='n'>{celda(f['a'])}</td><td class='n'>{celda(f['b'])}</td><td class='n'>{cambio or ('igual' if f['igual'] else '')}</td></tr>")
        tabla = ("<h3>Cada foco</h3><table class='horas comp_op'><tr><th>Foco</th><th class='n'>al 100 % (ou_E/s)</th>"
                 f"<th class='n'>{e(self.na)}</th><th class='n'>{e(self.nb)}</th><th class='n'>cambio</th></tr>{filas}</table>"
                 "<p class='nota'>De media con cada plan: en % de su emisión al 100 % y, en pequeño, en ou_E/s. En negrita, los que cambian.</p>")
        texto = "".join(f"<p><b>{e(t)}.</b> {h}</p>" for t, h in textos.operacion_comparada(self.dc))
        cuerpo = (f"<h2 style='margin-top:0'>La operación: «{e(a['res']['nombre'] or 'Base')}» frente a «{e(b['res']['nombre'] or 'Base')}»</h2>"
                  "<p class='intro'>Cuánto emite la planta cada día y cada hora con cada plan de operación (en hora oficial), y cada foco.</p>"
                  + kpis + f"<div class='subt'>Toda la planta · el año, día a día ({oa['anio']})</div>" + cal + ley + dia + tabla
                  + f"<div class='narra'>{texto}</div>")
        return self.pagina("2 · Focos y operación", cuerpo)

    def _semana(self, f, color_f):
        return ("<div class='sem'>" + "".join(f"<div class='sr'><span>{DIAS_SEM[w]}</span>" + "".join(f"<i style='background:{color_f(x)}'></i>" for x in perf)
                                              + "</div>" for w, perf in f["semana"])
                + "<div class='ejes'><span></span><em>0</em><em>6</em><em>12</em><em>18</em><em>23 h</em></div></div>")

    def operacion_focos_comparada(self):
        """La semana tipo de los focos que cambian, la de A junto a la de B, con la misma escala."""
        cambian = [f for f in self.dc["op"]["focos"] if not f["igual"]]
        if not cambian:
            return []
        tarjetas = []
        for f in cambian:
            lados = [x for x in (f["fa"], f["fb"]) if x is not None]
            valores = [v for x in lados for _, perf in x["semana"] for v in perf]
            lo, hi = min(valores), max(valores)
            color_f = estilo.estirada(lo, hi) if hi - lo > 1e-6 else (lambda v: estilo.rampa(0.6))
            col = estilo.COLOR_MODELO.get(f["modelo"], "#59c9a5")

            def lado(x, nombre, color):
                if x is None:
                    return f"<div class='lado'><div class='lt'><span class='chip' style='background:{color}'></span>{e(nombre)}</div><p class='nota'>No está.</p></div>"
                return (f"<div class='lado'><div class='lt'><span class='chip' style='background:{color}'></span>{e(nombre)} · plan "
                        f"{PLANES.get(x['plan'], x['plan'])} · <b>{_num(100 * x['media'], 0)} %</b></div>{self._semana(x, color_f)}</div>")
            ley = (f"<div class='ley_f'><span>{_num(100 * lo, 0)} %</span><i style='background:{estilo.gradiente()}'></i><span>{_num(100 * hi, 0)} %</span></div>"
                   if hi - lo > 1e-6 else f"<div class='ley_f'><span>{_num(100 * lo, 0)} % siempre</span></div>")
            tarjetas.append(f"<div class='ficha op comp'><div class='fh'><b>{e(f['nombre'])}</b><span class='pl' style='background:{col}'>"
                            f"{e(F.MODELOS.get(f['modelo'], f['modelo'] or '').lower())}</span></div><div class='lados'>"
                            f"{lado(f['fa'], self.na, graficas.COLOR_A)}{lado(f['fb'], self.nb, graficas.COLOR_B)}</div>{ley}</div>")
        salen = []
        for k in range(0, len(tarjetas), 6):
            cab = ("<h2 style='margin-top:0'>Los focos que cambian</h2><p class='intro'>La semana tipo de cada uno con cada plan, de lunes a domingo y "
                   "hora a hora, con la misma escala en los dos: del amarillo al rojo, de lo que menos a lo que más emite.</p>" if k == 0 else
                   "<h2 style='margin-top:0'>Los focos que cambian (sigue)</h2>")
            salen.append(self.pagina("2 · Focos y operación", cab + f"<div class='fichas comp'>{''.join(tarjetas[k:k + 6])}</div>"))
        return salen

    def comparacion(self):
        dc = self.dc
        a, b, comp = dc["a"], dc["b"], dc["comp"]
        u = e(a["mag"]["unidad"])
        mo = comp["magnitudes"].get("olor") or {}
        figs = (self.mapa("cambio_zona", "El cambio del P98, de A a B, en la zona de cálculo", "En la zona")
                + self.mapa("cambio_entorno", "De cerca", "Alrededor de la planta"))
        from teodors.operacion import comparacion as C
        cuadros = "".join(f"<span style='background:{c}'></span>" if c else "<span class='vacio'></span>" for c in C.COLORES)
        marcas = "".join(f"<span>{x}</span>" for x in ["−100"] + [f"{v:+.0f}".replace("-", "−") for v in C.LIMITES] + ["%"])
        ley = (f"<div class='leyenda cambio'><div class='lt'>El cambio del P98 de A a B (%): azul, baja; rojo, sube; sin color, ±10 % o los dos por "
               f"debajo de {_num(mo.get('umbral', 0.01), 2)} {u}</div><div class='lc'>{cuadros}</div><div class='lm'>{marcas}</div></div>")
        ca, cb = a.get("criterios") or [], b.get("criterios") or []
        crit = ""
        if ca and cb:
            def pct(x, y):
                return "" if x <= 0 else f"{'+' if y > x else '−' if y < x else ''}{_num(abs(100 * (y - x) / x), 0)} %"
            crit = ("<table class='horas comp_crit'><tr><th>P98 por encima de</th><th class='n'>km² A</th><th class='n'>km² B</th><th class='n'>cambio</th>"
                    "<th class='n'>hasta A</th><th class='n'>hasta B</th><th class='n'>pueblos A</th><th class='n'>pueblos B</th>"
                    "<th class='n'>peor hora: A</th><th class='n'>B</th></tr>"
                    + "".join(f"<tr><td>{_num(x['umbral'])} {u}</td><td class='n'>{_num(x['km2'], 2)}</td><td class='n'>{_num(y['km2'], 2)}</td>"
                              f"<td class='n'>{pct(x['km2'], y['km2'])}</td><td class='n'>{textos.km_txt(x['hasta_km']) if x['hasta_km'] is not None else '—'}</td>"
                              f"<td class='n'>{textos.km_txt(y['hasta_km']) if y['hasta_km'] is not None else '—'}</td><td class='n'>{x['pueblos']}</td>"
                              f"<td class='n'>{y['pueblos']}</td><td class='n'>{x['pueblos_maximo']}</td><td class='n'>{y['pueblos_maximo']}</td></tr>"
                              for x, y in zip(ca, cb)) + "</table>"
                    "<p class='nota'>«Hasta»: lo más lejos de la planta por encima de ese umbral. Pueblos: con P98 por encima y, a la derecha, con su "
                    "peor hora por encima.</p>")
        horas_a = {f["nombre"]: f for f in (a.get("horas") or {}).get("lugares", [])}
        horas_b = {f["nombre"]: f for f in (b.get("horas") or {}).get("lugares", [])}
        filas = sorted(mo.get("pueblos") or [], key=lambda f: -max(f["p98"][0], f["p98"][1]))[:10]

        def h(dic, nombre):
            f = dic.get(nombre)
            return "—" if f is None else _num(f["horas"][0], 0 if f["horas"][0] >= 10 or f["horas"][0] == 0 else 1)

        def pc(x):
            return "" if x is None else f"{x:+.0f} %".replace("-", "−")
        tabla = ""
        if filas:
            tabla = ("<table class='horas comp_pueblos'><tr><th>Pueblo</th><th class='n'>km</th><th class='n'>P98 A</th><th class='n'>P98 B</th>"
                     "<th class='n'>cambio</th><th class='n'>máx. A</th><th class='n'>máx. B</th><th class='n'>h &gt; 1 A</th><th class='n'>h &gt; 1 B</th></tr>"
                     + "".join(f"<tr><td>{e(f['nombre'])}</td><td class='n'>{_num(f['km'], 1)}</td><td class='n'>{ci(f['p98'][0])}</td>"
                               f"<td class='n'>{ci(f['p98'][1])}</td><td class='n'>{pc(f['p98'][2])}</td><td class='n'>{ci(f['maximo'][0])}</td>"
                               f"<td class='n'>{ci(f['maximo'][1])}</td><td class='n'>{h(horas_a, f['nombre'])}</td><td class='n'>{h(horas_b, f['nombre'])}</td></tr>"
                               for f in filas) + "</table>"
                     f"<p class='nota'>En {u}; «h &gt; 1»: horas al año por encima de 1 {u}. Los pueblos de más olor en alguno de los dos.</p>")
        texto = "".join(f"<p><b>{e(t)}.</b> {x}</p>" for t, x in textos.comparacion(dc))
        avisos = "".join(f"<p class='nota'>⚠ {e(x)}</p>" for x in dc.get("avisos", []))
        cuerpo = (f"<div class='sec'>6 · Comparación</div><h2>De «{e(a['res']['nombre'] or 'Base')}» a «{e(b['res']['nombre'] or 'Base')}»</h2>"
                  "<p class='intro'>Lo que cambia el olor de un escenario al otro: en el mapa, receptor a receptor; en la superficie y el alcance de "
                  "cada umbral; y en los pueblos.</p>"
                  f"<div class='dos'>{figs}</div>{ley}{crit}{tabla}{avisos}<div class='narra'>{texto}</div>")
        return [self.pagina("6 · Comparación", cuerpo)]

    def html(self):
        """El informe entero: lo común (de A), la operación de los dos, los resultados de A y de B, y la comparación."""
        self.n = 1
        a, b = self.dc["a"], self.dc["b"]
        paginas = [self.portada(), self.relieve_usos(), self.edificios_lugares(), *self.focos_3d(), *self.fichas_focos(),
                   self.operacion_comparada(), *self.operacion_focos_comparada()]
        if a.get("meteo"):
            paginas += [self.meteo_estaciones(), self.meteo_situaciones()]
            if a["meteo"].get("era5"):
                paginas.append(self.meteo_clima())
        for letra, d, sec in (("a", a, "4"), ("b", b, "5")):
            self.d, self.prefijo = d, f"{letra}_"
            self.seccion = f"{sec} · Resultados de {self.na if letra == 'a' else self.nb}"
            if d.get("alcances"):
                paginas.append(self.resultados_mapas())
                if d.get("horas"):
                    paginas.append(self.resultados_cuando())
        self.d, self.prefijo, self.seccion = a, "", Informe.seccion
        paginas += self.comparacion()
        titulo = f"{a['res']['nombre'] or 'Base'} frente a {b['res']['nombre'] or 'Base'}"
        return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{e(titulo)}</title>"
                f"<style>{estilo.CSS}</style></head><body>{''.join(paginas)}</body></html>")


def caudal(g_s):
    """Un caudal de gas con la unidad que le va: g/s, mg/s o µg/s."""
    for factor, unidad in ((1.0, "g/s"), (1e3, "mg/s"), (1e6, "µg/s")):
        v = g_s * factor
        if v >= 0.1 or unidad == "µg/s":
            return f"{v:.3g} {unidad}".replace(".", ",")


def gases_por_olor(f):
    """[(nombre, g/s)] de los gases del foco, del que más olor da al que menos."""
    gs = F.gases_g_s(f)
    filas = []
    for g in f.get("gases") or []:
        g_s = gs.get(g.get("gas"))
        if g_s:
            um = F.ug_por_ouE(g["gas"]) if g.get("gas") in F.GASES else None
            filas.append((F.NOMBRES.get(g["gas"], g["gas"]), g_s, g_s * 1e6 / um if um else 0.0))
    return [(nm, g_s) for nm, g_s, _ in sorted(filas, key=lambda x: -x[2])]


def ficha_basica(f):
    """Lo de la ficha de un foco sin la app (sin iconos): su tipo, su superficie, su altura y su olor."""
    a, q = F.area_m2(f), F.olor_ouE_s(f)
    cifras = []
    if a:
        cifras.append(("f_superficie", f"{_num(a, 0)} m²", "superficie"))
    if f.get("altura_m") not in (None, ""):
        cifras.append(("altura", f"{_num(float(f['altura_m']), 1)} m", "altura de emisión"))
    try:
        sub = F.subtitulo(f)
    except (KeyError, TypeError, ValueError):
        sub = F.MODELOS.get(f.get("modelo"), "")
    return {"sub": sub, "cifras": cifras, "olor": f"{_num(q, 0)} ou_E/s" if q is not None else "sin emisión de olor", "detalle": ""}
