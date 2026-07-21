"""Configuración central del sistema de trading de XAU/USD.

Todos los parámetros sensibles (riesgo, umbrales de calidad, límites de
operación) están aquí y pueden ajustarse sin tocar la lógica. Los valores por
defecto son conservadores a propósito: la prioridad es proteger el capital.

Se pueden sobreescribir mediante variables de entorno con prefijo ``ORO_``
(p. ej. ``ORO_RIESGO_POR_OPERACION=0.005``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import List


@dataclass(slots=True)
class ConfiguracionRiesgo:
    riesgo_por_operacion: float = 0.0025  # 0.25 % del capital por operación (riesgo mínimo).
    riesgo_diario_max: float = 0.01       # tope de riesgo/pérdida diaria (1 %).
    # Tamaño escalado por convicción: a menor confianza, posición más pequeña.
    # El riesgo efectivo va de este mínimo (baja confianza) al total (alta confianza).
    sizing_por_confianza: bool = True
    factor_sizing_min: float = 0.35       # con confianza en el umbral, arriesga el 35% del riesgo base.
    operaciones_max_dia: int = 4          # 2–4 oportunidades A+ al día.
    operaciones_min_dia: int = 0          # nunca se fuerza: puede ser 0.
    r_recompensa_min: float = 1.5         # R:R medio ponderado mínimo aceptable.
    atr_stop_mult: float = 1.5            # stop = 1.5 x ATR desde la entrada.
    # Reparto de la posición entre objetivos parciales (TP1, TP2, TP3).
    reparto_tp: tuple = (0.5, 0.3, 0.2)
    r_objetivos: tuple = (1.0, 2.0, 3.0)  # cada TP en múltiplos de R.
    # Intradía: la operación se abre y se cierra el MISMO día (sin riesgo overnight).
    cerrar_intradia: bool = True
    hora_cierre_utc: int = 21             # cierre forzado a las 21:00 UTC (cierre NY).
    # Salida dinámica: tras el primer objetivo, el stop persigue al precio (a 1R
    # del máximo/mínimo favorable) para proteger beneficio y capturar el movimiento.
    trailing_activo: bool = True


@dataclass(slots=True)
class ConfiguracionCalidad:
    """Umbrales del filtro de calidad. Solo se emite señal si se superan.

    Perfil «selectivo» (prioriza el ACIERTO sobre la frecuencia): solo pasan los
    setups de mayor convicción. Salen menos señales (típicamente ~1–3/día, y
    algunos días 0), pero de más calidad. Es el perfil recomendado para maximizar
    el porcentaje de acierto y proteger el capital.

    Ajustable por entorno (ORO_PROB_MINIMA, ORO_CONFIANZA_MINIMA,
    ORO_PUNTUACION_MINIMA). Bajar estos valores = más señales, menos acierto medio
    (p. ej. 0.55 / 0.55 / 0.58 = perfil «equilibrado»).

    OJO: los guardas de seguridad de abajo (spread, volatilidad, lateral) NO son
    filtros de calidad sino de PROTECCIÓN del capital; no se relajan.
    """

    prob_minima: float = 0.60        # probabilidad estimada mínima.
    confianza_minima: float = 0.62   # convicción/confluencia mínima.
    puntuacion_minima: float = 0.66  # puntuación de confluencia normalizada.
    # Confirmación: solo se emite la señal si la última vela CERRADA confirma la
    # dirección (cierra a favor). Reduce entradas en falso.
    exigir_confirmacion: bool = True
    spread_max: float = 0.6          # spread máximo tolerado (USD/oz).
    # Volatilidad como FRACCIÓN del precio (ATR/precio), no en dólares absolutos,
    # para que funcione igual en cualquier marco temporal (M15, H4, D1) y a
    # cualquier nivel de precio del oro. Ej.: ATR 33 con oro a 4020 = 0,8% -> OK.
    atr_pct_min: float = 0.0003      # por debajo (0,03%): mercado demasiado plano.
    atr_pct_max: float = 0.020       # por encima (2%): volatilidad extrema, no operar.
    adx_lateral: float = 18.0        # ADX por debajo => mercado lateral.


@dataclass(slots=True)
class ConfiguracionSistema:
    simbolo: str = "XAUUSD"
    capital: float = 3_000.0             # capital de la cuenta (divisa base). Configurable por ORO_CAPITAL.
    # Marco temporal de trabajo. H1 (1 hora) para operativa INTRADÍA (abrir y
    # cerrar el mismo día). Nota honesta: los marcos intradía tienen un borde más
    # fino que H4/D1; se compensa cerrando siempre el mismo día (sin riesgo
    # overnight). Configurable por ORO_TIMEFRAME.
    timeframe: str = "H1"
    zona_horaria: str = "UTC"

    riesgo: ConfiguracionRiesgo = field(default_factory=ConfiguracionRiesgo)
    calidad: ConfiguracionCalidad = field(default_factory=ConfiguracionCalidad)

    # Fuentes de datos y ML. El modelo se guarda en la raíz para poder versionarlo
    # en el repo (así el aprendizaje persiste entre ejecuciones en la nube).
    directorio_datos: str = "datos_oro"
    ruta_modelo: str = "modelo_oro.pkl"
    ruta_operaciones: str = "operaciones_oro.jsonl"

    def validar(self) -> List[str]:
        """Devuelve una lista de problemas de configuración (vacía si todo OK)."""
        problemas: List[str] = []
        r = self.riesgo
        if not 0 < r.riesgo_por_operacion <= 0.05:
            problemas.append("riesgo_por_operacion debe estar en (0, 0.05].")
        if r.riesgo_diario_max < r.riesgo_por_operacion:
            problemas.append("riesgo_diario_max no puede ser menor que el de una operación.")
        if abs(sum(r.reparto_tp) - 1.0) > 1e-6:
            problemas.append("reparto_tp debe sumar 1.0.")
        if len(r.reparto_tp) != len(r.r_objetivos):
            problemas.append("reparto_tp y r_objetivos deben tener la misma longitud.")
        if r.r_recompensa_min <= 0:
            problemas.append("r_recompensa_min debe ser positivo.")
        return problemas


def cargar_configuracion() -> ConfiguracionSistema:
    """Crea la configuración aplicando sobreescrituras desde el entorno.

    Solo se sobreescriben los campos escalares de primer nivel y los del bloque
    de riesgo/calidad más habituales, que es lo que se ajusta en producción.
    """
    cfg = ConfiguracionSistema()

    def _num(nombre: str, actual: float) -> float:
        bruto = os.getenv(nombre)
        if bruto is None:
            return actual
        try:
            return type(actual)(bruto)
        except (TypeError, ValueError):
            return actual

    cfg.capital = _num("ORO_CAPITAL", cfg.capital)
    cfg.simbolo = os.getenv("ORO_SIMBOLO", cfg.simbolo)
    cfg.timeframe = os.getenv("ORO_TIMEFRAME", cfg.timeframe)  # H4 (rec.), D1, H1, M15…
    cfg.riesgo.riesgo_por_operacion = _num(
        "ORO_RIESGO_POR_OPERACION", cfg.riesgo.riesgo_por_operacion
    )
    cfg.riesgo.operaciones_max_dia = int(
        _num("ORO_OPERACIONES_MAX_DIA", cfg.riesgo.operaciones_max_dia)
    )
    cfg.riesgo.operaciones_min_dia = int(
        _num("ORO_OPERACIONES_MIN_DIA", cfg.riesgo.operaciones_min_dia)
    )
    # Umbrales de calidad, ajustables sin tocar código (subir = más selectivo).
    cfg.calidad.prob_minima = _num("ORO_PROB_MINIMA", cfg.calidad.prob_minima)
    cfg.calidad.confianza_minima = _num("ORO_CONFIANZA_MINIMA", cfg.calidad.confianza_minima)
    cfg.calidad.puntuacion_minima = _num("ORO_PUNTUACION_MINIMA", cfg.calidad.puntuacion_minima)
    return cfg


__all__ = [
    "ConfiguracionRiesgo",
    "ConfiguracionCalidad",
    "ConfiguracionSistema",
    "cargar_configuracion",
]
