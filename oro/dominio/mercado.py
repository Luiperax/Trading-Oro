"""Modelos de mercado: vela (OHLCV), instantánea y sesiones de negociación."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Optional


@dataclass(frozen=True, slots=True)
class Candle:
    """Una vela OHLCV.

    Los precios se expresan en dólares por onza (XAU/USD). ``timestamp`` debe ser
    *timezone-aware* en UTC para evitar ambigüedades entre sesiones.
    """

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    spread: float = 0.0  # spread medio observado en la vela, en dólares.

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("Candle.timestamp debe ser timezone-aware (UTC).")
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValueError(
                f"Vela OHLC incoherente: O={self.open} H={self.high} "
                f"L={self.low} C={self.close}"
            )

    @property
    def rango(self) -> float:
        """Rango total (high - low)."""
        return self.high - self.low

    @property
    def cuerpo(self) -> float:
        """Tamaño del cuerpo (|close - open|)."""
        return abs(self.close - self.open)

    @property
    def alcista(self) -> bool:
        return self.close >= self.open


class Sesion(str, Enum):
    """Sesión de negociación (aprox., en UTC). El oro es más líquido en el
    solape Londres–Nueva York; la sesión asiática suele ser más lateral."""

    ASIA = "asia"
    LONDRES = "londres"
    NUEVA_YORK = "nueva_york"
    SOLAPE_LDN_NY = "solape_ldn_ny"
    CIERRE = "cierre"


# El oro (futuro CME) cotiza de 22:00 a 21:00 UTC: solo cierra una hora al día
# (21:00-22:00) y el fin de semana. Comprobado sobre las velas reales: hay datos
# en todas las horas UTC salvo las 21:00, y tras el fin de semana la primera vela
# es la del domingo a las 22:00.
#
# Por tanto el "día de operativa" NO es el día de calendario: va de las 22:00 de
# un día a las 21:00 del siguiente. Usar el calendario provocaba dos disparates:
# bloquear entradas a las 22:00 y 23:00 "por ser tarde" cuando en realidad acaba
# de empezar una sesión de 22 horas, y cerrar a medianoche una operación abierta
# hora y media antes.
HORA_APERTURA_UTC = 22   # abre la sesión siguiente.
HORA_CIERRE_UTC = 21     # cierra la sesión (y empieza la pausa diaria).


def dia_sesion(momento: datetime) -> date:
    """Día de operativa del oro al que pertenece un instante.

    A partir de las 22:00 UTC ya se está operando la sesión del día SIGUIENTE.
    """
    m = momento.astimezone(timezone.utc)
    if m.hour >= HORA_APERTURA_UTC:
        return (m + timedelta(days=1)).date()
    return m.date()


def sesion_de(momento: datetime) -> Sesion:
    """Clasifica un instante UTC en su sesión de mercado dominante.

    Horas aproximadas (UTC): Asia 00–07, Londres 07–12, solape 12–16,
    Nueva York 16–21, cierre 21–24. Son aproximaciones deliberadamente simples;
    la ventaja real se calcula por sesión a partir del histórico, no de horarios
    fijos.
    """
    t = momento.astimezone(timezone.utc).time()

    def entre(a: int, b: int) -> bool:
        return time(a, 0) <= t < time(b, 0)

    if entre(0, 7):
        return Sesion.ASIA
    if entre(7, 12):
        return Sesion.LONDRES
    if entre(12, 16):
        return Sesion.SOLAPE_LDN_NY
    if entre(16, 21):
        return Sesion.NUEVA_YORK
    return Sesion.CIERRE


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Fotografía del estado del mercado en un instante, tal y como la ve el
    motor de señales. Reúne el precio actual y el contexto que rodea la decisión.
    """

    momento: datetime
    precio: float
    spread: float
    atr: float                      # volatilidad reciente (ATR), en dólares.
    sesion: Sesion
    dxy: Optional[float] = None     # índice del dólar, si se dispone.
    rendimiento_10y: Optional[float] = None  # Treasury 10 años (%), si se dispone.
    riesgo_noticia_alta: bool = False        # evento macro de alto impacto próximo.
    sentimiento: Optional[float] = None      # [-1, 1] agregado de fundamentales/RRSS.
    metadatos: dict = field(default_factory=dict)
