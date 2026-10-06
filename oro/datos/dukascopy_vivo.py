"""XAU/USD **al contado** en vivo, armado desde los ticks de Dukascopy.

POR QUÉ EXISTE
--------------
El feed en vivo era Yahoo, y Yahoo no sirve XAU/USD al contado en velas
horarias: ``XAUUSD=X``, ``XAU=X`` y ``GCUSD=X`` devuelven 404, y ``^XAU`` es el
índice de mineras. Lo único disponible allí es ``GC=F``, el FUTURO de COMEX, que
en septiembre de 2026 cotizó 40,17 $ por encima del contado.

Eso dejaba dos agujeros:

1. Toda la investigación del proyecto está medida sobre el contado, así que
   ninguna ventaja estaba validada sobre el instrumento que se operaba.
2. Si el bróker de quien opera cotiza el contado —lo normal en minorista—, los
   niveles del correo no existen en su pantalla.

Dukascopy sí da el contado, y además da lo que ninguna otra fuente gratuita da:
**bid y ask reales**. El coste de operar es la restricción que decide todas las
estrategias de este proyecto, y hasta ahora era un número elegido (0.30 $) en
vez de medido.

EL RETRASO, MEDIDO
------------------
El fichero mensual de velas H1 NO existe para el mes en curso (404), así que
para operar en vivo hay que armar las velas desde los ficheros de ticks, que van
por hora. Sondeado el 5-oct-2026: la hora que cierra a las 11:00 estuvo
disponible **a los 2,2 minutos** (con un 503 y un 404 por el camino, que es la
intermitencia conocida de este servidor).

Lo que NO da: la hora EN CURSO. El fichero aparece cuando la hora termina, así
que dentro de la hora no hay precio nuevo. Yahoo sí servía la vela en curso a
medias. Es la única cosa en la que Yahoo era mejor, y conviene tenerlo presente
en los avisos que dependen de reaccionar rápido.

FORMATO DEL FICHERO DE TICKS
-----------------------------
``…/XAUUSD/AAAA/MM/DD/HHh_ticks.bi5`` — LZMA crudo; registros de 20 bytes
``>3I2f`` = (milisegundos desde el inicio de la hora, ask, bid, volumen de ask,
volumen de bid). Los dos precios son enteros en puntos: para XAU/USD hay que
dividir entre 1000. El mes va indexado de 0 a 11, como en los ficheros
mensuales.
"""

from __future__ import annotations

import datetime as dt
import logging
import lzma
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

from .base import ProveedorDatos

log = logging.getLogger(__name__)

URL = ("https://datafeed.dukascopy.com/datafeed/{sim}/{anio}/{mes:02d}/{dia:02d}/"
       "{hora:02d}h_ticks.bi5")

_REGISTRO = struct.Struct(">3I2f")
_NUEVA_YORK = ZoneInfo("America/New_York")
PUNTO = {"XAUUSD": 1000.0, "XAGUSD": 1000.0, "EURUSD": 100000.0}


class ProveedorDukascopyVivo(ProveedorDatos):
    """Velas H1 del contado, armadas desde los ticks de la última hora cerrada.

    ``en_vivo`` es True porque sí sirve para operar: el retraso medido es de
    ~2 minutos sobre el cierre de cada hora. Lo que no tiene es la hora en
    curso, y eso lo dice :meth:`ultima`.
    """

    en_vivo = True

    def __init__(self, simbolo: str = "XAUUSD", intentos: int = 6,
                 tiempo_espera: int = 20, hilos: int = 3) -> None:
        self._simbolo = simbolo.upper()
        self._punto = PUNTO.get(self._simbolo, 1000.0)
        self._intentos = max(1, intentos)
        self._tiempo_espera = tiempo_espera
        self._hilos = max(1, hilos)
        # Caché en memoria por hora. Las horas CERRADAS no cambian nunca, así
        # que una ejecución que pida 400 velas varias veces (el vigilante la
        # pide cada tres minutos) baja cada fichero una sola vez.
        self._memoria: dict[dt.datetime, Optional[pd.DataFrame]] = {}
        # Horas de mercado abierto que faltaron en la última llamada a
        # `historico`, tras la segunda pasada. Para diagnóstico.
        self.horas_perdidas: list[dt.datetime] = []

    # -- descarga ----------------------------------------------------------
    @staticmethod
    def mercado_cerrado(hora: dt.datetime) -> bool:
        """¿Esa hora UTC cae con el oro al contado cerrado por horario?

        El contado cierra el viernes a las 17:00 de Nueva York, abre el domingo
        a las 18:00 y para una hora cada día entre las 17:00 y las 18:00. Se
        calcula en hora de Nueva York para que los cambios de hora no muevan
        nada. En esas horas no hay fichero y no tiene sentido insistir: era lo
        que hacía que un ciclo del vigilante tardara 23 minutos los lunes, con
        el fin de semana entero reintentado seis veces hora a hora.
        """
        if hora.tzinfo is None:
            hora = hora.replace(tzinfo=dt.timezone.utc)
        local = hora.astimezone(_NUEVA_YORK)
        dia, h = local.weekday(), local.hour       # lunes = 0 … domingo = 6
        if dia == 5:                               # sábado
            return True
        if dia == 4 and h >= 17:                   # viernes desde el cierre
            return True
        if dia == 6 and h < 18:                    # domingo antes de abrir
            return True
        return h == 17                             # la parada diaria

    def _ticks_de(self, hora: dt.datetime) -> Optional[pd.DataFrame]:
        """Los ticks de esa hora UTC, o ``None`` si no hay (fin de semana…)."""
        if hora in self._memoria:
            return self._memoria[hora]
        import requests

        url = URL.format(sim=self._simbolo, anio=hora.year, mes=hora.month - 1,
                         dia=hora.day, hora=hora.hour)
        # Con el mercado cerrado se pregunta UNA vez: si por lo que sea hay
        # fichero (festivos con horario raro, un cambio de horario del bróker),
        # se usa; si no, no se pierde medio minuto reintentando lo que no
        # existe. Con el mercado abierto se insiste: 404 puede ser «aún no
        # publicado» y 503 es la intermitencia conocida del servidor, y un
        # hueco que se cuela en una serie temporal no falla, miente.
        cerrado = self.mercado_cerrado(hora)
        # Una hora que acaba de cerrar (Dukascopy la publica ~2 minutos después)
        # se pide UNA vez: si aún no está, la pasada siguiente del vigilante, a
        # los 3 minutos, la vuelve a pedir. Insistir aquí bloqueaba el ciclo:
        # el 6-oct el plan, que tocaba a las 14:00, salió a las 14:10 por diez
        # minutos de reintentos sobre la hora de 13:00 aún sin publicar.
        reciente = (dt.datetime.now(dt.timezone.utc) - hora) < dt.timedelta(minutes=66)
        intentos = 1 if (cerrado or reciente) else self._intentos
        datos, codigos = None, []
        for intento in range(intentos):
            try:
                r = requests.get(url, timeout=self._tiempo_espera,
                                 headers={"User-Agent": "Mozilla/5.0 oro/0.1"})
                codigos.append(r.status_code)
                if r.status_code == 200 and r.content:
                    datos = r.content
                    break
            except Exception as exc:  # noqa: BLE001
                codigos.append(type(exc).__name__)
                log.debug("Dukascopy ticks %s: %s", hora, exc)
            if intento + 1 < intentos:
                # 429 es «demasiadas peticiones». Medido el 5-oct-2026: tras
                # pedir unas decenas de horas seguidas el servidor contesta 429
                # a casi todo durante más de un minuto, y sin cabecera
                # Retry-After. Reintentar al segundo solo alarga el castigo;
                # hay que esperar de verdad.
                if codigos and codigos[-1] == 429:
                    time.sleep(min(5 * 2 ** intento, 30))
                else:
                    time.sleep(min(2 ** intento, 8))
        if datos is None:
            # Solo se memoriza el vacío cuando es seguro que no hay nada: hora
            # cerrada por horario y el servidor respondió (no se cayó). Una hora
            # de mercado abierto que no llegó NO se memoriza nunca. Antes sí
            # (si tenía más de 3 horas), y como el proveedor del vigilante vive
            # cinco horas, una descarga fallida dejaba ese hueco fijo toda la
            # tarde: el rango de Londres salía más estrecho en cada pasada.
            if cerrado and codigos and all(isinstance(c, int) for c in codigos):
                self._memoria[hora] = None
            elif not cerrado:
                log.warning("Dukascopy %s %s: sin fichero tras %d intento(s) (%s).",
                         self._simbolo, hora.strftime("%d-%m %Hh"), len(codigos),
                         ",".join(str(c) for c in codigos))
            return None
        df = self._decodificar(datos, hora)
        self._memoria[hora] = df
        return df

    def _decodificar(self, crudo: bytes, hora: dt.datetime) -> Optional[pd.DataFrame]:
        try:
            datos = lzma.LZMADecompressor().decompress(crudo)
        except lzma.LZMAError:
            return None
        n = len(datos) // _REGISTRO.size
        if n == 0:
            return None
        p = self._punto
        momentos, bids, asks = [], [], []
        for i in range(n):
            ms, ask, bid, _, _ = _REGISTRO.unpack_from(datos, i * _REGISTRO.size)
            momentos.append(hora + dt.timedelta(milliseconds=ms))
            asks.append(ask / p)
            bids.append(bid / p)
        return pd.DataFrame({"bid": bids, "ask": asks},
                            index=pd.DatetimeIndex(momentos, tz=dt.timezone.utc))

    # -- agregación --------------------------------------------------------
    @staticmethod
    def _vela(ticks: pd.DataFrame) -> dict:
        """Una vela H1 a partir de sus ticks.

        OHLC va sobre el **bid**, igual que los ficheros mensuales de velas
        (``BID_candles_hour_1``) con los que está medida toda la investigación.
        Mezclar bid aquí y medio allí descuadraría los niveles justo en los
        bordes del rango, que es donde la estrategia entra.
        """
        b = ticks["bid"]
        return {
            "open": float(b.iloc[0]), "high": float(b.max()),
            "low": float(b.min()), "close": float(b.iloc[-1]),
            "volume": float(len(b)),
            # El spread REAL de esa hora, que es lo que nadie más da gratis.
            "spread": float((ticks["ask"] - ticks["bid"]).median()),
        }

    def _horas(self, cuantas: int) -> list[dt.datetime]:
        """Las últimas ``cuantas`` horas CERRADAS, de más antigua a más nueva."""
        ahora = dt.datetime.now(dt.timezone.utc).replace(
            minute=0, second=0, microsecond=0)
        # La hora en curso no está publicada; se empieza por la anterior.
        return [ahora - dt.timedelta(hours=i) for i in range(cuantas, 0, -1)]

    # Tope de horas que se piden de una vez. Cada hora es una petición, y el
    # servidor tarda entre 1 y 8 segundos por fichero.
    #
    # La ruptura de sesión necesita el día de sesión en curso: el sesgo asiático
    # (0-3 ET), el rango de Londres (3-8 ET) y la sesión (8-16 ET). Son 17
    # horas; con 48 se cubre eso y el hueco del fin de semana. Medido sobre el
    # código real: con 8 velas del día ya sale el MISMO plan y el MISMO
    # resultado que con el marco entero.
    #
    # El motor de señales intradía sí pedía 400 velas (necesita EMA 200 de
    # calentamiento), y con 400 esto no sería viable: 628 horas de calendario,
    # más de media hora por ciclo. Está apagado; si se vuelve a encender, hay
    # que dejarle Yahoo.
    MAX_HORAS = 48

    def historico(self, velas: int) -> pd.DataFrame:
        """Las últimas ``velas`` velas H1 cerradas, sin huecos dentro del rango.

        Si falta una hora que debería tener mercado, se avisa en el log: un
        hueco silencioso en una serie temporal es el peor error posible, porque
        no falla, solo miente. La estrategia mide máximos y mínimos de ventanas
        horarias, así que una hora perdida estrecha el rango y coloca las
        órdenes más cerca de lo que toca.
        """
        if velas > self.MAX_HORAS:
            raise ValueError(
                f"Este proveedor arma las velas hora a hora y no sirve para "
                f"pedir {velas}: cada hora es una petición. El máximo es "
                f"{self.MAX_HORAS}. Para históricos largos está "
                f"`ProveedorDukascopy`, que baja ficheros mensuales.")
        # Se piden ``velas`` horas de CALENDARIO, no ``velas`` velas: cada hora
        # es una petición, y el servidor corta con 429 si se le piden muchas
        # seguidas. Un lunes salen menos velas que horas (el fin de semana no
        # tiene), y no importa: lo que se necesita es el día de sesión en curso.
        horas = self._horas(max(velas, 6))
        with ThreadPoolExecutor(max_workers=self._hilos) as ex:
            obtenidas = dict(zip(horas, ex.map(self._ticks_de, horas)))
            # Segunda pasada para las horas de mercado ABIERTO que no llegaron.
            # Los fallos de este servidor son sueltos y distintos en cada
            # ciclo: lo que falla ahora suele llegar un momento después. La
            # hora en curso menos uno se excluye porque puede no estar
            # publicada todavía y eso no es un fallo.
            reciente = horas[-1]
            perdidas = [h for h, t in obtenidas.items()
                        if (t is None or t.empty) and h != reciente
                        and not self.mercado_cerrado(h)]
            if perdidas:
                obtenidas.update(zip(perdidas, ex.map(self._ticks_de, perdidas)))
        filas, indice, vacias = [], [], []
        for hora in horas:
            ticks = obtenidas[hora]
            if ticks is None or ticks.empty:
                vacias.append(hora)
                continue
            filas.append(self._vela(ticks))
            indice.append(hora)
        self.horas_perdidas = [h for h in vacias if h != reciente
                               and not self.mercado_cerrado(h)]
        if not filas:
            raise RuntimeError(
                f"Dukascopy no devolvió ticks de {self._simbolo} en las últimas "
                f"{len(horas)} horas.")
        df = pd.DataFrame(filas, index=pd.DatetimeIndex(indice)).sort_index()
        df = df[~df.index.duplicated(keep="last")]
        self._avisar_de_huecos(df, [h for h in vacias if not self.mercado_cerrado(h)])
        self.validar(df)
        return df.tail(velas).copy()

    @staticmethod
    def _avisar_de_huecos(df: pd.DataFrame, vacias: list) -> None:
        """Distingue "mercado cerrado" de "se perdió una hora".

        Un hueco entre dos velas buenas no es fin de semana: es una descarga
        fallida. El fin de semana queda FUERA del rango de velas obtenidas, no
        en medio.
        """
        if df.empty or not vacias:
            return
        dentro = [h for h in vacias if df.index.min() < h < df.index.max()]
        if dentro:
            log.warning("Dukascopy en vivo: faltan %d horas DENTRO del rango "
                        "(%s). El rango medido puede salir más estrecho de lo "
                        "real.", len(dentro),
                        ", ".join(h.strftime("%d-%m %Hh") for h in dentro[:6]))

    def vela_de(self, hora: dt.datetime) -> Optional[dict]:
        """La vela H1 de una hora concreta (UTC, en punto), o ``None``.

        Una sola petición. La usa el árbitro del LBMA, que necesita la vela de
        la subasta de días concretos y no las últimas horas seguidas.
        """
        if hora.tzinfo is None:
            hora = hora.replace(tzinfo=dt.timezone.utc)
        ticks = self._ticks_de(hora.astimezone(dt.timezone.utc))
        return self._vela(ticks) if ticks is not None and not ticks.empty else None

    def velas_minuto(self, hora: dt.datetime) -> Optional[pd.DataFrame]:
        """Velas de 1 minuto de esa hora, armadas desde sus ticks (bid).

        Para los días en que una vela horaria cruza el techo y el suelo del
        rango: con los ticks se sabe qué se cruzó primero. Sin ninguna petición
        nueva, porque los ticks de esa hora ya están en la caché.
        """
        if hora.tzinfo is None:
            hora = hora.replace(tzinfo=dt.timezone.utc)
        ticks = self._ticks_de(hora.astimezone(dt.timezone.utc))
        if ticks is None or ticks.empty:
            return None
        b = ticks["bid"].resample("1min")
        df = pd.DataFrame({"open": b.first(), "high": b.max(), "low": b.min(),
                           "close": b.last(), "volume": b.count().astype(float)})
        return df.dropna()

    def ultima(self) -> Optional[pd.Series]:
        """La última vela cerrada. ``None`` si no hay ninguna reciente."""
        df = self.historico(2)
        return df.iloc[-1] if len(df) else None

    def precio_actual(self) -> float:
        """El último precio conocido: el cierre de la última hora CERRADA.

        No es el precio de ahora mismo —la hora en curso no está publicada— y
        quien lo use tiene que saberlo. Puede estar hasta 60 minutos viejo.
        """
        return float(self.historico(1)["close"].iloc[-1])

    def spread_actual(self) -> float:
        """El spread real de la última hora, en dólares por onza.

        Esto es lo que ninguna otra fuente gratuita da, y es el número del que
        depende si una estrategia es viable o no.
        """
        return float(self.historico(1)["spread"].iloc[-1])

    def refrescar(self) -> None:
        """Olvida la caché de la hora más reciente, por si acaba de publicarse."""
        if not self._memoria:
            return
        ultima = max(self._memoria)
        self._memoria.pop(ultima, None)
