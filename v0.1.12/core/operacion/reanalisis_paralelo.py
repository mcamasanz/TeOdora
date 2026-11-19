# -*- coding: utf-8 -*-
"""El reanálisis (`simulacion.calcular`): la suma día a día de las respuestas de los focos, en un proceso o, con `paralelo`, repartida en
tramos de meses seguidos entre varios, y los estadísticos de cada receptor ACUMULADOS a medida que se resuelve cada día, sin guardar la serie
hora a hora entera (con 5 años y miles de receptores, decenas de GB en ficheros temporales de `trabajo`: así se hacía hasta la v0.1.8):

  · media y media anual: sumas en float64, hora a hora;
  · máximo;
  · el percentil (P98): las K horas más altas de cada receptor (`_Altas`: lo que no pasa de la más baja de las K ni se mira) y, al final,
    la misma cuenta que `np.percentile` con las dos que caen en su sitio, que están entre esas K (`percentil_de_las_altas`);
  · la (N+1)-ésima hora más alta del peor año (normas de 1 h): las N+1 más altas de cada año;
  · la (N+1)-ésima media diaria más alta del peor año (normas de 24 h): la media de cada día (por la fecha del fin de la hora) con
    `np.add.reduceat`, como `normativa._medias_diarias`;
  · lo peor de cada pueblo en cada hora (la tabla de horas) y la hora a hora de las viviendas (para «la peor vivienda»), que se guardan.

En un proceso, todo sale idéntico bit a bit a la serie entera (medido con 5 años; más rápido y sin el disco). En varios, también, salvo las
medias: las de cada tramo se juntan al final, en otro orden de suma, y cambian en la cifra 14-15 (medido: ≤ 2·10⁻¹⁴ relativo).
"""
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, wait

import numpy as np

from teodors import planta as config

MAX_PROCESOS = 8          # medido: con más no baja el tiempo (la memoria no da para más) y se gasta el doble de CPU
_G = {}                   # lo común en cada proceso hijo (`_iniciar`)


def de_la_planta():
    """El interruptor del cálculo en paralelo, el `paralelo` por defecto de `simulacion.calcular` y de `calcular_periodo` (y cuántos focos a
    la vez en las respuestas de un periodo, `periodos`): la variable <prefijo>_PARALELO o, si no está, `operacion.paralelo` de planta.json
    (true, false o cuántos procesos); sin ninguna, False (1 proceso)."""
    v = os.environ.get(config.nombre_env("PARALELO"))
    if v is None:
        return config.bloque("operacion").get("paralelo", False)
    v = v.strip().lower()
    if v in ("", "0", "no", "false"):
        return False
    if v in ("si", "sí", "true", "auto"):
        return True
    return int(v)


def procesos(paralelo):
    """Cuántos procesos para un `paralelo`: False o None, uno; True, los núcleos de la máquina menos uno, hasta
    MAX_PROCESOS; un número, ese."""
    if paralelo is True:
        return max(1, min(MAX_PROCESOS, (os.cpu_count() or 2) - 1))
    if not paralelo:
        return 1
    return max(1, int(paralelo))


# ── lo que `calcular` lee de la serie después: la hora a hora de la peor vivienda ──
class Viviendas:
    """En vez de la serie del olor: solo sus viviendas (`simulacion._vivienda_horaria` lee serie[i // BLOQUE, :, i % BLOQUE])."""

    def __init__(self, n, nrec, indices, bloque):
        self.shape = (-(-nrec // bloque), n, bloque)
        self.bloque, self.indices = bloque, np.asarray(indices, np.int64)
        self.pos = {int(i): j for j, i in enumerate(self.indices)}
        self.datos = np.zeros((n, len(self.indices)), np.float32)

    def __getitem__(self, clave):
        b, sl, j = clave
        return self.datos[sl, self.pos[int(b) * self.bloque + int(j)]]


def series_sin_disco(mags, n, nrec, clase, bloque):
    """Las «series» de `calcular` en paralelo: nada en disco; para el olor, la hora a hora de sus viviendas."""
    return {k: Viviendas(n, nrec, np.flatnonzero(np.asarray(clase) == "vivienda"), bloque) if k == "olor" else None for k in mags}


# ── los acumuladores de una magnitud ──
def _fusionar(top, L):
    """Las K más altas de cada receptor (`top`, [receptor, K]) con las horas nuevas `L` ([hora, receptor]), exactas. Solo se tocan los
    receptores con alguna hora nueva por encima de la más baja de sus K (igual o por debajo, el conjunto de valores no cambia)."""
    K = top.shape[1]
    hace = L.max(0) > top.min(1)
    if hace.any():
        comb = np.concatenate([top[hace], L[:, hace].T], axis=1)
        top[hace] = np.partition(comb, comb.shape[1] - K, axis=1)[:, -K:]
    return top


class _Altas:
    """Las K horas más altas de cada receptor, al día y exactas, sin reordenar las K cada vez. Una hora que no pasa del umbral del
    receptor (la más baja de sus K, que solo sube) no puede estar entre las K más altas del final: ni se guarda. Las que pasan esperan
    aparte (`cand`) y se juntan con las K cuando a su receptor no le caben más o al final (`final`)."""
    CAP = 1024                    # candidatas que esperan, por receptor (un mes son ~744 horas)

    def __init__(self, nrec, K):
        self.top = np.zeros((nrec, K), np.float32)
        self.umbral = np.zeros(nrec, np.float32)
        self.cand = np.zeros((nrec, self.CAP), np.float32)
        self.cuenta = np.zeros(nrec, np.int64)

    def anadir(self, L):
        """Las horas nuevas L [hora, receptor] (float32)."""
        M = L > self.umbral
        c = M.sum(axis=0)
        if not c.any():
            return
        lleno = self.cuenta + c > self.CAP
        if lleno.any():                                                  # a esos, se les junta todo ya: sus candidatas y estas horas
            r = np.flatnonzero(lleno)
            self._juntar_en_top(r, L[:, r])
            M[:, r] = False
            c[r] = 0
        jj, tt = np.nonzero(M.T)                                         # por receptor y, dentro, por hora
        if len(jj):
            inicio = np.cumsum(c) - c
            self.cand[jj, self.cuenta[jj] + (np.arange(len(jj)) - inicio[jj])] = L[tt, jj]
            self.cuenta += c

    def _juntar_en_top(self, r, extra=None):
        """Las candidatas de los receptores `r` (y sus horas `extra` [hora, receptor de r], si se dan), a sus K más altas."""
        K = self.top.shape[1]
        cmax = int(self.cuenta[r].max())
        partes = [self.top[r], self.cand[r, :cmax]] + ([] if extra is None else [extra.T])
        comb = np.concatenate(partes, axis=1)                            # lo que pasa de cmax en cada receptor son ceros: no estorban
        nuevo = np.partition(comb, comb.shape[1] - K, axis=1)[:, -K:]
        self.top[r] = nuevo
        self.umbral[r] = nuevo.min(axis=1)
        self.cand[r, :cmax] = 0
        self.cuenta[r] = 0

    def final(self):
        """Las K más altas de cada receptor [receptor, K], con todo lo que había esperando; luego ya no admite más horas."""
        if self.cand is not None:
            r = np.flatnonzero(self.cuenta)
            if len(r):
                self._juntar_en_top(r)
            self.cand = None                                             # ~50 MB menos (y menos que mandar entre procesos)
        return self.top

    def juntar(self, otra):
        """Las de otro tramo de la serie."""
        self.top = _fusionar(self.final(), otra.final().T)
        self.umbral = self.top.min(axis=1)


def percentil_de_las_altas(top, n, p):
    """El percentil `p` de cada receptor, como `np.percentile` (método lineal) sobre sus `n` horas, sabiendo solo sus K más altas (`top`,
    [receptor, K], float32): las dos horas entre las que cae, y la misma cuenta que numpy (`numpy.lib._function_base_impl._quantile` y
    `_lerp`, con peso «débil»). None si no caen entre esas K. Lo comprueba una prueba frente a `np.percentile`."""
    v = (n - 1) * np.true_divide(p, 100)
    i0 = int(np.floor(v))
    g = float(np.asanyarray(v - np.floor(v), dtype=np.float64))
    K = top.shape[1]
    j0 = i0 - (n - K)
    if j0 < 0 or i0 + 1 > n - 1:
        return None
    part = np.partition(top, [j0, j0 + 1], axis=1)
    a, b = part[:, j0], part[:, j0 + 1]
    d = b - a
    return b - d * (1 - g) if g >= 0.5 else a + d * g


class Acum:
    """Los estadísticos de una magnitud (`normativa.columnas(k, "anios")`) sin la serie entera: se le dan las horas en orden (`anadir`), las
    K más altas se ponen al día una vez al mes (`cerrar_lote`), dos tramos seguidos se juntan (`juntar`) y al final, `resultado`."""

    def __init__(self, cols, n, nrec, anio_fila, fecha_fila):
        self.cols, self.n, self.nrec = cols, n, nrec
        self.anio_fila, self.fecha_fila = anio_fila, fecha_fila          # de cada fila de la serie (hora del plan): su año y su fecha
        raras = [c["clave"] for c in cols if c["clave"] not in ("media", "maximo") and "percentil" not in c
                 and c.get("promedio") not in ("hora", "dia", "anio")]
        if raras:
            raise NotImplementedError(f"el reanálisis en paralelo aún no acumula: {raras}; simúlalo sin paralelo")
        claves = {c["clave"] for c in cols}
        self.media = np.zeros(nrec) if "media" in claves else None
        self.maximo = np.zeros(nrec, np.float32) if "maximo" in claves else None
        self.K = {c["clave"]: n - int(np.floor((n - 1) * c["percentil"] / 100.0)) + 1 for c in cols if "percentil" in c}
        self.altas = {cl: _Altas(nrec, K) for cl, K in self.K.items()}         # para el percentil: las K horas más altas
        self.kk = {c["clave"]: c.get("n", 0) + 1 for c in cols if c.get("promedio") == "hora"}
        self.top_anio = {cl: {} for cl in self.kk}                       # clave → {año: [receptor, N+1]}
        self.cuenta_anio = {}                                            # año → horas de la serie de ese año
        self.anual = any(c.get("promedio") == "anio" for c in cols)
        self.suma_anio = {}                                              # año → suma (float64)
        self.diario = any(c.get("promedio") == "dia" for c in cols)
        # cada día: [fecha, año de su 1.ª hora, media o None, sus horas]. La media, con `np.add.reduceat` sobre sus horas, como el original
        # (que no suma hora a hora: da otra última cifra). El primero y el último de un tramo se quedan con sus horas: pueden seguir al lado.
        self.dias = []
        self.lote_f, self.lote_C = [], []

    @staticmethod
    def _cerrar_dia(d):
        if d[3] is not None:
            d[2] = np.add.reduceat(np.stack(d[3]), [0], axis=0, dtype=np.float64)[0] / len(d[3])
            d[3] = None

    def anadir(self, filas, C):
        """Las horas `filas` de la serie, con sus valores C [hora, receptor] (float32), en orden."""
        if self.maximo is not None:
            np.maximum(self.maximo, C.max(0), out=self.maximo)
        anios = self.anio_fila[filas]
        for y, c in zip(*np.unique(anios, return_counts=True)):
            self.cuenta_anio[int(y)] = self.cuenta_anio.get(int(y), 0) + int(c)
        if self.media is not None or self.anual or self.diario:
            for t in range(len(filas)):                                  # hora a hora: el mismo orden de suma que la serie entera
                fila = C[t]
                if self.media is not None:
                    self.media += fila
                if self.anual:
                    s = self.suma_anio.get(int(anios[t]))
                    if s is None:
                        s = self.suma_anio[int(anios[t])] = np.zeros(self.nrec)
                    s += fila
                if self.diario:
                    f = int(self.fecha_fila[filas[t]])
                    if not self.dias or self.dias[-1][0] != f:
                        if len(self.dias) > 1:                           # el anterior ya está entero (el 1.º, no: puede seguir atrás)
                            self._cerrar_dia(self.dias[-1])
                        self.dias.append([f, int(anios[t]), None, []])
                    self.dias[-1][3].append(fila)
        if self.altas or self.top_anio:
            self.lote_f.append(filas)
            self.lote_C.append(C)

    def cerrar_lote(self):
        """Las horas del lote (un mes) a las K más altas de cada receptor y a las N+1 más altas de cada año."""
        if not self.lote_C:
            return
        L, F = np.concatenate(self.lote_C), np.concatenate(self.lote_f)
        self.lote_C, self.lote_f = [], []
        for a in self.altas.values():
            a.anadir(L)
        if self.top_anio:
            anios = self.anio_fila[F]
            for y in np.unique(anios):
                Ly = L[anios == y]
                for cl, por in self.top_anio.items():
                    t = por.get(int(y))
                    por[int(y)] = _fusionar(np.zeros((self.nrec, self.kk[cl]), np.float32) if t is None else t, Ly)

    def juntar(self, otro):
        """Los acumuladores del tramo SIGUIENTE de la serie (`otro`), con los de este."""
        if self.media is not None:
            self.media += otro.media
        if self.maximo is not None:
            np.maximum(self.maximo, otro.maximo, out=self.maximo)
        for cl, a in self.altas.items():
            a.juntar(otro.altas[cl])
        for cl, por in self.top_anio.items():
            for y, t in otro.top_anio[cl].items():
                por[y] = t if y not in por else _fusionar(por[y], t.T)
        for y, c in otro.cuenta_anio.items():
            self.cuenta_anio[y] = self.cuenta_anio.get(y, 0) + c
        for y, s in otro.suma_anio.items():
            if y in self.suma_anio:
                self.suma_anio[y] += s
            else:
                self.suma_anio[y] = s
        for i, d in enumerate(otro.dias):
            if i == 0 and self.dias and self.dias[-1][0] == d[0]:         # un día partido entre los dos tramos: sus horas, juntas y en orden
                self.dias[-1][3] = self.dias[-1][3] + d[3]
                continue
            if self.dias:
                self._cerrar_dia(self.dias[-1])                          # el de antes ya está entero
            self.dias.append(d)

    def resultado(self, fines_h, bloque):
        """{columna: valor en cada receptor}, como `normativa.estadistico` sobre la serie entera."""
        from teodors.operacion import normativa
        salen = {}
        for col in self.cols:
            cl = col["clave"]
            if cl == "media":
                salen[cl] = self.media / self.n
            elif cl == "maximo":
                salen[cl] = self.maximo.astype(np.float64)
            elif "percentil" in col:
                top, K = self.altas[cl].final(), self.K[cl]
                v = percentil_de_las_altas(top, self.n, col["percentil"])
                if v is None:                                            # no cae entre las K (no pasa con un percentil alto): la serie, rellena
                    v = np.zeros(self.nrec)
                    for r0 in range(0, self.nrec, bloque):
                        r1 = min(r0 + bloque, self.nrec)
                        C = np.zeros((self.n, r1 - r0), np.float32)
                        C[self.n - K:] = top[r0:r1].T
                        v[r0:r1] = normativa.estadistico(col, C, fines_h)
                salen[cl] = np.asarray(v, np.float64)
            elif col["promedio"] == "hora":
                kk = self.kk[cl]
                por = [t.min(1) if self.cuenta_anio.get(y, 0) >= kk else np.zeros(self.nrec, np.float32)
                       for y, t in sorted(self.top_anio[cl].items())]
                salen[cl] = np.max(por, axis=0).astype(np.float64)
            elif col["promedio"] == "dia":
                por_anio = {}
                for d in self.dias:
                    self._cerrar_dia(d)
                    por_anio.setdefault(d[1], []).append(d[2])
                salen[cl] = np.max([normativa._kesimo(np.array(m), col.get("n", 0) + 1) for _, m in sorted(por_anio.items())], axis=0)
            elif col["promedio"] == "anio":
                salen[cl] = np.max([s / self.cuenta_anio[y] for y, s in sorted(self.suma_anio.items())], axis=0)
        return salen


# ── el recorrido de los días (en un proceso, o un tramo de meses en cada uno) ──
def _recorrer(js, g, hechos=None, parar=None, avisa=None, cancelado=None):
    """Los días `js` (índices de `dias`, seguidos): sus acumuladores, lo peor de cada pueblo en sus horas y la hora a hora de las viviendas
    en sus horas. `hechos`, `parar`: el contador de días hechos y el aviso de cancelar, compartidos con el proceso que reparte; `avisa`,
    `cancelado`: los de `calcular`, cuando se hace aquí mismo (en un proceso)."""
    from teodors.operacion import serie_respuestas as SR, simulacion as S
    dias, mascara, pos, lags, nrec = g["dias"], g["mascara"], g["pos"], g["lags"], g["nrec"]
    est = {k: Acum(g["cols"][k], g["n"], nrec, g["anio_fila"], g["fecha_fila"]) for k in g["mags"]}
    hor = {k: ([], []) for k in g["grupos"]}
    viv, viv_f, viv_v = g["viviendas"], [], []
    mes, cache = None, {}
    for n_hechos, j in enumerate(js):
        if (parar is not None and parar.value) or (cancelado and cancelado()):
            raise RuntimeError("Cálculo cancelado.")
        d = dias[j]
        sel = mascara[24 * j: 24 * j + 24]
        if sel.any():
            if (d.year, d.month) != mes:
                for e in est.values():
                    e.cerrar_lote()
                mes = (d.year, d.month)
                cache = {i: SR.leer_mes(g["carpeta"], i, *mes) for i in g["activos"]}
                if avisa:
                    avisa(int(75 * n_hechos / len(js)), f"Sumando las respuestas: {d:%m/%Y}")
            te = (24 * (d - g["eje0"]).days + np.arange(24)[:, None]) - lags
            dia = {k: np.zeros((24, nrec), np.float32) for k in g["mags"]}
            for i in g["activos"]:
                X = S._dia_foco(*cache[i][d.day], g["forma"], g["factores"][i][te].T)
                for k, q in g["emisiones"].items():
                    if i in q:
                        dia[k] += q[i] * X
            filas = pos[24 * j: 24 * j + 24][sel]
            for k, C in dia.items():
                C = C[sel]
                est[k].anadir(filas, C)
                if k in hor:
                    picos = np.zeros((len(filas), len(g["grupos"][k])), np.float32)
                    for gi, (_, idx) in enumerate(g["grupos"][k]):
                        if len(idx):
                            picos[:, gi] = C[:, idx].max(axis=1)
                    hor[k][0].append(filas)
                    hor[k][1].append(picos)
                if k == "olor" and viv is not None:
                    viv_f.append(filas)
                    viv_v.append(C[:, viv])
        if hechos is not None:
            with hechos.get_lock():
                hechos.value += 1
    for e in est.values():
        e.cerrar_lote()
        for a in e.altas.values():
            a.final()                                                    # sin las candidatas que esperan: menos que mandar
    return est, hor, (viv_f, viv_v)


def _iniciar(comun, hechos, parar):
    _G.update(comun, _hechos=hechos, _parar=parar)


def _tramo(js):
    return _recorrer(js, _G, _G["_hechos"], _G["_parar"])


def sumar_serie(dias, mascara, pos, activos, factores, emisiones, mags, carpeta, eje, forma, nrec, fines_h, series, avisa, cancelado,
                grupos=None, procesos=2):
    """La serie del reanálisis acumulando, sin la serie entera, en `procesos` procesos (1: aquí mismo): (campos, columnas, horarias), los
    estadísticos de cada magnitud por receptor y lo peor de cada pueblo hora a hora. La hora a hora de las viviendas del olor va a
    `series["olor"]` (`series_sin_disco`)."""
    from teodors.operacion import normativa, simulacion as S
    cols = {k: normativa.columnas(k, "anios") for k in mags}
    grupos = grupos or {}
    n = len(fines_h)
    viv = series.get("olor") if isinstance(series.get("olor"), Viviendas) else None
    g = {"dias": list(dias), "mascara": mascara, "pos": pos, "lags": (np.arange(24)[:, None] - (np.arange(24)[None, :] + 1)) % 24,
         "activos": list(activos), "factores": {i: factores[i] for i in activos}, "emisiones": emisiones, "mags": list(mags),
         "carpeta": carpeta, "eje0": eje[0], "forma": forma, "nrec": nrec, "n": n, "cols": cols, "grupos": grupos,
         "anio_fila": np.asarray(fines_h.year), "fecha_fila": np.asarray(fines_h.normalize().asi8),
         "viviendas": None if viv is None else viv.indices}
    meses = {}
    for j, d in enumerate(dias):
        meses.setdefault((d.year, d.month), []).append(j)
    lista = list(meses.values())
    tramos = [t for t in (sum(lista[i * len(lista) // procesos:(i + 1) * len(lista) // procesos], []) for i in range(procesos)) if t]
    if len(tramos) <= 1:
        partes = [_recorrer(range(len(dias)), g, avisa=avisa, cancelado=cancelado)]
    else:
        ctx = mp.get_context("spawn")
        hechos, parar = ctx.Value("i", 0), ctx.Value("b", 0)
        with ProcessPoolExecutor(max_workers=len(tramos), mp_context=ctx, initializer=_iniciar, initargs=(g, hechos, parar)) as ex:
            futuros = [ex.submit(_tramo, t) for t in tramos]
            pendientes = set(futuros)
            while pendientes:
                _, pendientes = wait(pendientes, timeout=0.5)
                avisa(int(75 * hechos.value / len(dias)), f"Sumando las respuestas: {hechos.value} de {len(dias)} días ({len(tramos)} procesos)")
                if cancelado and cancelado():
                    parar.value = 1
                    wait(pendientes)
                    raise RuntimeError("Cálculo cancelado.")
            partes = [f.result() for f in futuros]
    est = partes[0][0]
    for p in partes[1:]:
        for k in mags:
            est[k].juntar(p[0][k])
    horarias = {}
    for k, gr in grupos.items():
        h = np.zeros((n, len(gr)), np.float32)
        for p in partes:
            for filas, picos in zip(*p[1][k]):
                h[filas] = np.maximum(h[filas], picos)
        horarias[k] = h
    if viv is not None:
        for p in partes:
            for filas, v in zip(*p[2]):
                viv.datos[filas] = v
    avisa(75, "Los estadísticos de cada receptor")
    campos = {k: est[k].resultado(fines_h, S.BLOQUE) for k in mags}
    return campos, cols, horarias
