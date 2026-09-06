"""Histórico profundo de XAU/USD **spot** desde Dukascopy.

Existe por una limitación concreta: Yahoo solo sirve **730 días** de velas H1.
Con ese tope, un backtest de la estrategia da ~500 operaciones, y con 500
operaciones no se distingue una ventaja real y débil de una casualidad. Medido:
un efecto que parecía sólido con 494 operaciones (diferencia +0.135 R, robusta
al umbral y presente dentro y fuera de la sesión de Nueva York) se desvaneció a
-0.024 R (p = 0.40) al repetirlo aquí con 4.346 operaciones de 19,6 años.

Es una fuente **de investigación**, no de operativa en vivo (``en_vivo`` sigue a
False): los ficheros son mensuales y no dan el precio del último tick, que es lo
que el runner necesita para gestionar salidas. Para eso sigue estando
:class:`~oro.datos.adaptadores.ProveedorYahoo`.

Formato del fichero ``.bi5``: LZMA crudo; una vez descomprimido, registros de 24
bytes ``>5if`` = (segundos desde el inicio del mes, open, close, low, high,
volumen). Los cuatro precios son **enteros en puntos**: para XAU/USD hay que
dividir entre 1000. El mes va indexado de 0 a 11, no de 1 a 12.

Validado contra Yahoo (GC=F) sobre 483 horas solapadas de 2025:

* correlación de los **movimientos** horarios: 0.9958;
* 0,00 % de velas con ``high < max(open, close)`` o ``low > min(open, close)``;
* diferencia de nivel de -18,9 $, que es la prima del futuro sobre el spot y no
  un error: Dukascopy da spot, que es justo lo que se opera.

El servidor es **intermitente**: el mismo mes puede devolver 404 y, al segundo
intento, sus 744 registros. Sin reintentos se cuelan huecos silenciosos, que en
una serie temporal es el peor error posible porque no falla, solo miente. Con 5
intentos se perdió el 1,3 % de los meses; con 12 no se perdió ninguno.
"""

from __future__ import annotations

import datetime as dt
import logging
import lzma
import struct
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from .base import ProveedorDatos

log = logging.getLogger(__name__)

URL = "https://datafeed.dukascopy.com/datafeed/{sim}/{anio}/{mes:02d}/BID_candles_hour_1.bi5"

# Divisor para pasar de puntos a precio. Solo XAUUSD está verificado contra otra
# fuente; el resto se deja documentado pero sin validar.
PUNTO = {"XAUUSD": 1000.0, "XAGUSD": 1000.0, "EURUSD": 100000.0, "GBPUSD": 100000.0}

# Velas reales por mes: ~22 días hábiles x 23 h (el mercado para una hora al día).
# Sirve para estimar cuántos meses hay que bajar para reunir N velas.
VELAS_MES = 505

_REGISTRO = struct.Struct(">5if")


class ProveedorDukascopy(ProveedorDatos):
    """Velas H1 de Dukascopy, con caché en disco y reintentos.

    La caché es **por mes** a propósito: bajar 20 años son ~236 peticiones y
    varios minutos, así que interesa que una descarga interrumpida se pueda
    reanudar sin repetir lo ya hecho. El mes en curso nunca se cachea, porque
    todavía está creciendo.
    """

    en_vivo = False

    def __init__(
        self,
        simbolo: str = "XAUUSD",
        cache: Optional[Path | str] = None,
        intentos: int = 12,
        tiempo_espera: int = 60,
    ) -> None:
        self._simbolo = simbolo.upper()
        self._punto = PUNTO.get(self._simbolo, 1000.0)
        self._intentos = max(1, intentos)
        self._tiempo_espera = tiempo_espera
        self._cache = Path(cache) if cache else Path.home() / ".cache" / "oro" / "dukascopy"
        self._memoria: dict[tuple[int, int], pd.DataFrame] = {}

    # -- descarga ----------------------------------------------------------
    def _descargar(self, anio: int, mes: int,
                   intentos: Optional[int] = None) -> Optional[pd.DataFrame]:
        """Baja un mes con reintentos y espera creciente. ``None`` si no existe.

        ``intentos`` permite bajar la insistencia cuando un 404 es la respuesta
        esperada y no un fallo (ver ``_mes`` y el mes en curso).
        """
        import requests

        intentos = self._intentos if intentos is None else max(1, intentos)
        url = URL.format(sim=self._simbolo, anio=anio, mes=mes - 1)
        for intento in range(intentos):
            try:
                r = requests.get(url, timeout=self._tiempo_espera,
                                 headers={"User-Agent": "Mozilla/5.0 oro/0.1"})
                if r.status_code == 200 and r.content:
                    return self._decodificar(r.content, anio, mes)
                # 404 puede ser "aún no publicado" o intermitencia: se reintenta.
            except Exception as exc:  # red inestable: reintentar, no abortar.
                log.debug("Dukascopy %s-%02d intento %d: %s", anio, mes, intento + 1, exc)
            if intento + 1 < intentos:
                time.sleep(min(2 ** intento, 16))
        log.warning("Dukascopy: %s-%02d no disponible tras %d intentos",
                    anio, mes, intentos)
        return None

    def _decodificar(self, crudo: bytes, anio: int, mes: int) -> pd.DataFrame:
        datos = lzma.LZMADecompressor().decompress(crudo)
        inicio = dt.datetime(anio, mes, 1, tzinfo=dt.timezone.utc)
        p = self._punto
        filas = []
        for off in range(0, len(datos) - _REGISTRO.size + 1, _REGISTRO.size):
            t, o, c, l, h, v = _REGISTRO.unpack_from(datos, off)
            filas.append((inicio + dt.timedelta(seconds=t), o / p, h / p, l / p, c / p, v))
        df = pd.DataFrame(filas, columns=["t", "open", "high", "low", "close", "volume"])
        df = df.set_index("t")
        # Los fines de semana y festivos vienen RELLENOS con una vela plana a
        # precio de cierre anterior y volumen 0. Hay que quitarlos: si no, el ATR
        # se hunde y la estrategia "vería" un mercado quieto que no existió.
        df = df[(df["close"] > 0) & (df["high"] > df["low"])]
        df["spread"] = 0.2  # Dukascopy da solo BID; se asume igual que en Yahoo.
        return df

    # -- caché -------------------------------------------------------------
    def _mes(self, anio: int, mes: int) -> Optional[pd.DataFrame]:
        clave = (anio, mes)
        if clave in self._memoria:
            return self._memoria[clave]

        hoy = dt.datetime.now(dt.timezone.utc)
        en_curso = (anio, mes) >= (hoy.year, hoy.month)
        fichero = self._cache / self._simbolo / f"{anio}-{mes:02d}.csv"

        if not en_curso and fichero.exists():
            df = pd.read_csv(fichero, index_col=0, parse_dates=True)
        else:
            # Un 404 del mes en curso suele ser "todavía no publicado", no un
            # fallo del servidor: insistir doce veces con espera creciente
            # gastaría minutos en algo que no existe. Los meses cerrados sí
            # merecen toda la insistencia, porque ahí un 404 es intermitencia.
            df = self._descargar(anio, mes, intentos=2 if en_curso else None)
            if df is not None and not en_curso:
                fichero.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(fichero)

        if df is not None:
            self._memoria[clave] = df
        return df

    # -- interfaz pública --------------------------------------------------
    def rango(self, desde: dt.date, hasta: dt.date) -> pd.DataFrame:
        """Todas las velas entre dos fechas (ambas inclusive, por meses)."""
        trozos, anio, mes = [], desde.year, desde.month
        while (anio, mes) <= (hasta.year, hasta.month):
            df = self._mes(anio, mes)
            if df is not None and not df.empty:
                trozos.append(df)
            anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
        if not trozos:
            raise RuntimeError(
                f"Dukascopy no devolvió ninguna vela de {self._simbolo} "
                f"entre {desde} y {hasta}.")
        return self._unir(trozos)

    def historico(self, velas: int) -> pd.DataFrame:
        """Últimas ``velas`` velas cerradas, bajando solo los meses necesarios."""
        hoy = dt.datetime.now(dt.timezone.utc)
        anio, mes = hoy.year, hoy.month
        trozos: list[pd.DataFrame] = []
        reunidas = 0
        # Margen: los meses con festivos traen menos velas de las estimadas.
        limite = velas // VELAS_MES + 3
        while reunidas < velas and len(trozos) < limite + 12:
            df = self._mes(anio, mes)
            if df is not None and not df.empty:
                trozos.append(df)
                reunidas += len(df)
            anio, mes = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
            if anio < 2003:  # Dukascopy no tiene XAU/USD antes de esa época.
                break
        if not trozos:
            raise RuntimeError(f"Dukascopy no devolvió velas de {self._simbolo}.")
        return self._unir(trozos).tail(velas).copy()

    def _unir(self, trozos: list[pd.DataFrame]) -> pd.DataFrame:
        df = pd.concat(trozos).sort_index()
        df = df[~df.index.duplicated(keep="last")]
        self.validar(df)
        return df
