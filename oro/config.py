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
    # DOS objetivos, los dos alcanzables, con cierre parcial en el primero.
    #
    # Medida la excursión favorable máxima de las 4.410 entradas de 19,6 años,
    # respetando el stop dinámico y el cierre intradía —o sea, hasta dónde llega
    # el precio mientras aún estás dentro—, el porcentaje de operaciones que toca
    # cada nivel es:
    #
    #     1.0 R  31 %      2.5 R   8 %
    #     1.5 R  19 %      3.0 R   5 %
    #     2.0 R  12 %      4.0 R   2 %      5.0 R  1 %
    #
    # El PRIMER objetivo va a 2 R: se toca en el 12 % de todas las operaciones y
    # en el 31 % de las ganadoras. El SEGUNDO va a 3 R, que es el nivel más lejos
    # que sigue siendo alcanzable de verdad: de las operaciones que llegan a 2 R,
    # el 39 % continúa hasta 3 R. Más lejos deja de serlo (4 R lo alcanza el 15 %
    # de ellas y 5 R el 7 %), y un objetivo que no se toca no es un objetivo: es
    # una orden en el bróker que nunca se ejecuta.
    #
    # Cerrar la mitad en el primero y dejar correr la otra mitad gana a un único
    # objetivo entero: +0.0343 R/op frente a +0.0298 en el histórico completo, y
    # en walk-forward (elegir con el pasado, cobrar en la ventana siguiente)
    # +0.0395 R/op con t = 4.54 ganando 10 de 10 ventanas, frente a +0.0348 y
    # 9 de 10 del objetivo único.
    #
    # Sigue sin ser el techo: sin ningún objetivo la ventaja sería +0.0527 R/op.
    # Ese 35 % restante es el precio de que los objetivos EXISTAN y se ejecuten.
    # Se comprobó que no hay atajo: mover un objetivo único de 2 R a 3 R cuando el
    # precio se acerca da EXACTAMENTE lo mismo que ponerlo en 3 R desde el
    # principio (+0.0388 en ambos), porque no se llega a 2 R sin pasar por 1.5 R;
    # ese objetivo de 2 R no llegaría a ejecutarse nunca.
    #
    # El acierto es del 40 %: se gana menos veces y más cuando se gana.
    reparto_tp: tuple = (0.5, 0.5)        # mitad en el primero, mitad en el segundo.
    r_objetivos: tuple = (2.0, 3.0)       # en múltiplos de R.
    # Intradía: la operación se abre y se cierra el MISMO día (sin riesgo overnight).
    cerrar_intradia: bool = True
    # Cierre operativo, en hora de NUEVA YORK (red de seguridad del gestor). El
    # aviso de salida lo manda antes el trabajo de cierre, a las 21:50 del
    # usuario. Se define en la hora del mercado —no en UTC— para que el cambio
    # de horario no lo desajuste. 16:00 en Nueva York son las 22:00 en Madrid
    # CASI todo el año: Europa y EE. UU. no cambian la hora el mismo fin de
    # semana (1 semana desfasada en octubre y 3 en marzo) y esas semanas caen a
    # las 21:00. El aviso lo tiene en cuenta y anuncia la hora real.
    # Medido sobre 872 días: adelantarlo una hora no cuesta nada (PF 1.00->1.01).
    hora_cierre_et: int = 16
    # Salida dinámica: el stop persigue al precio desde el máximo/mínimo favorable.
    # Antes solo se activaba tras el primer objetivo; sin objetivos no arrancaría
    # nunca, y es justamente la gestión que mide mejor (ver reparto_tp).
    trailing_activo: bool = True
    # Distancia del stop dinámico, en múltiplos de R desde el máximo favorable.
    # 1.0 aprieta mucho (protege beneficio pero corta las ganadoras pronto);
    # valores mayores dan más recorrido a la operación a cambio de devolver más
    # desde el pico. Ajustable por ORO_TRAILING_R.
    trailing_r: float = 1.0
    # Si el stop dinámico empieza a trabajar desde la entrada (True) o solo
    # tras alcanzar un objetivo parcial (False, comportamiento antiguo).
    trailing_desde_entrada: bool = True
    # Coste real de operar, en $/oz por operación completa (abrir + cerrar).
    # Al comprar pagas el ask y al vender cobras el bid: cruzas el spread. Sin
    # esto el backtest da resultados optimistas, y el efecto crece con el número
    # de operaciones. Ajustable por ORO_COSTE_OPERACION según tu bróker.
    coste_operacion: float = 0.30


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
    # Señales EMITIDAS (aún sin resultado). Fichero aparte a propósito: mezclarlas
    # con las operaciones cerradas ensuciaba el marcador, porque una señal sin
    # `resultado_r` se leía como 0.0 y contaba como perdedora.
    ruta_senales: str = "senales_oro.jsonl"

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


_MARCOS_VALIDOS = ("M15", "H1", "H4", "D1")


def _marco(bruto: str, actual: str) -> str:
    """Valida el marco temporal en el ORIGEN, no al descargar.

    El proveedor cae en silencio a H1 ante un marco desconocido. Con eso, un
    ORO_TIMEFRAME mal escrito ("h4", "4H", o la cadena VACÍA que GitHub manda
    cuando una Variable no está definida) hacía que el sistema operase en H1
    mientras la configuración decía otra cosa: informaba de algo distinto de lo
    que hacía. Aquí se normaliza y, si no se reconoce, se avisa y se mantiene el
    valor actual en vez de aceptar una mentira silenciosa.
    """
    limpio = (bruto or "").strip().upper()
    if not limpio:
        return actual
    if limpio not in _MARCOS_VALIDOS:
        print(f"⚠️  ORO_TIMEFRAME={bruto!r} no es un marco válido "
              f"({', '.join(_MARCOS_VALIDOS)}); se mantiene {actual}.")
        return actual
    return limpio


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
    cfg.timeframe = _marco(os.getenv("ORO_TIMEFRAME", ""), cfg.timeframe)
    cfg.riesgo.riesgo_por_operacion = _num(
        "ORO_RIESGO_POR_OPERACION", cfg.riesgo.riesgo_por_operacion
    )
    cfg.ruta_operaciones = os.getenv("ORO_RUTA_OPERACIONES", cfg.ruta_operaciones)
    cfg.ruta_senales = os.getenv("ORO_RUTA_SENALES", cfg.ruta_senales)
    cfg.ruta_modelo = os.getenv("ORO_RUTA_MODELO", cfg.ruta_modelo)
    cfg.riesgo.trailing_r = _num("ORO_TRAILING_R", cfg.riesgo.trailing_r)
    cfg.riesgo.coste_operacion = _num("ORO_COSTE_OPERACION", cfg.riesgo.coste_operacion)
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
