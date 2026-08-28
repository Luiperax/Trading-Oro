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


# El oro (futuro CME) cotiza de 18:00 a 17:00 hora de NUEVA YORK: solo cierra una
# hora al día (17:00-18:00) y el fin de semana.
#
# IMPORTANTE: el horario del mercado se define en la hora de Nueva York, NO en
# UTC. Comprobado sobre las velas reales: la hora sin cotización es las 21:00 UTC
# en verano y las 22:00 UTC en invierno —siempre las 17:00 de Nueva York—. Tener
# las horas fijadas en UTC funcionaba en verano y se habría desajustado una hora
# al llegar el cambio de horario de octubre.
#
# Anclarlo al reloj del mercado resuelve el cambio de hora solo, y de paso encaja
# con el usuario: Madrid y Nueva York cambian la hora casi a la vez, así que el
# cierre cae siempre a la misma hora de Madrid (23:00) todo el año.
ZONA_MERCADO = "America/New_York"
CIERRE_ET = 17      # 17:00 en Nueva York: cierra la sesión.
APERTURA_ET = 18    # 18:00 en Nueva York: abre la siguiente.


def _zona_mercado():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(ZONA_MERCADO)
    except Exception:  # noqa: BLE001 — sin zoneinfo, aproximar con UTC-4.
        return timezone(timedelta(hours=-4))


def hora_mercado(momento: datetime) -> int:
    """Hora del instante en el reloj del mercado (Nueva York)."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(_zona_mercado()).hour


def mercado_cerrado(momento: datetime) -> bool:
    """¿Estamos en la pausa diaria del mercado (17:00-18:00 de Nueva York)?"""
    return CIERRE_ET <= hora_mercado(momento) < APERTURA_ET


def dia_sesion(momento: datetime) -> date:
    """Día de operativa del oro al que pertenece un instante.

    A partir de las 18:00 de Nueva York ya se opera la sesión del día SIGUIENTE.
    """
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    m = momento.astimezone(_zona_mercado())
    if m.hour >= APERTURA_ET:
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
