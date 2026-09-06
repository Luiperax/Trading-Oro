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
    # UN objetivo alcanzable para toda la posición, AMPLIABLE por aviso.
    #
    # El objetivo se pone en el bróker al abrir y se olvida: si el precio llega
    # mientras no miras, se ejecuta y te llevas 2R. Pero cuando el precio se
    # ACERCA sin haber llegado, llega un correo proponiendo subirlo (ver
    # `r_ampliacion_objetivo`). Si da tiempo a moverlo, la operación puede llegar
    # más lejos; si no da tiempo, se ejecuta el objetivo original. No hay lado
    # malo, y por eso el aviso existe.
    #
    # Dónde va el objetivo, medido sobre las 4.410 entradas de 19,6 años
    # (excursión favorable máxima respetando stop dinámico y cierre intradía):
    #
    #     1.0 R  31 %      2.5 R   8 %
    #     1.5 R  19 %      3.0 R   5 %
    #     2.0 R  12 %      4.0 R   2 %      5.0 R  1 %
    #
    # A 2 R se toca en el 12 % de todas las operaciones y en el 31 % de las
    # ganadoras. Bruto +0.0298 R/op; walk-forward +0.0348 R/op (t = 4.05, gana
    # 9 de 10 ventanas) frente a la escalera anterior. Si el aviso de ampliación
    # se atiende siempre, el techo sube a +0.0388 R/op; si no se atiende nunca,
    # se queda en +0.0298. El resultado real cae entre esos dos.
    #
    # No se usa cierre parcial (mitad a 2R, mitad a 3R, que mediría +0.0343)
    # porque exige poder partir la posición: con el lote mínimo de 0.01 no se
    # puede, y una instrucción que no se puede ejecutar es peor que una peor
    # instrucción. Está medido por si algún día interesa.
    reparto_tp: tuple = (1.0,)            # un único objetivo, toda la posición.
    r_objetivos: tuple = (2.0,)           # en múltiplos de R.
    # A dónde propone subir el objetivo el aviso de ampliación, y a qué altura se
    # manda. Medido: estando ya en 1.5R, la esperanza es 1.574 R quedándose en el
    # objetivo de 2R y 1.621 R ampliando a 3R, así que ampliar sale a cuenta pese
    # a renunciar a la salida segura. El disparo va en 1.5R y no más arriba
    # porque es cuestión de TIEMPO: desde 1.5R el precio llega a 2R en la misma
    # vela el 54 % de las veces (desde 1.8R, el 78 %), y hace falta margen para
    # leer el correo y mover la orden.
    r_ampliacion_objetivo: float = 3.0
    r_disparo_ampliacion: float = 1.5
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
    # Al comprar pagas el ask y al vender cobras el bid: cruzas el spread.
    #
    # ESTE ES EL NÚMERO DEL QUE DEPENDE QUE EL SISTEMA GANE O PIERDA, y por eso
    # merece la pena entenderlo antes de tocar cualquier otra cosa.
    #
    # El coste en R es `spread / (1.5 x ATR)`, así que el mismo spread pesa muy
    # distinto según cuánto se mueva el oro. Medido sobre las 4.410 operaciones
    # de 19,6 años, el SPREAD DE EQUILIBRIO —aquel al que el sistema queda
    # exactamente en cero— es:
    #
    #     2007-2026 (todo)   0.15 $     (0.08 $ descontando un error típico)
    #     2020-2026          0.31 $     (0.12 $)
    #     2024-2026          1.16 $     (0.69 $)
    #
    # Por debajo de esa cifra el sistema gana; por encima, pierde. La diferencia
    # entre épocas no es que la estrategia mejorase: es que 1R pasó de valer 7 $
    # a valer 18 $ porque el oro subió, y un coste fijo en dólares pesa menos.
    #
    # NO HAY AJUSTE QUE COMPENSE UN SPREAD ALTO. Está medido: ensanchar el stop
    # baja el coste en R de 0.058 a 0.022, pero hunde la ventaja bruta de
    # +0.0298 R a +0.0015 R; subir de H1 a H4 baja el coste de 0.195 R a 0.099 R
    # y la ventaja de +0.0277 R a +0.0062 R. Las dos fuerzas se cancelan. Con un
    # spread de 1.45 $, el coste (0.195 R) es SEIS VECES la ventaja bruta
    # (0.0298 R), y ningún cambio de parámetros cierra un factor de seis.
    #
    # Ajustable por ORO_COSTE_OPERACION. Mídelo en tu plataforma en horario
    # normal (no en la reapertura, que es el peor momento del día).
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
class ConfiguracionRuptura:
    """Ruptura del rango de sesión: la segunda estrategia del sistema.

    Es independiente del motor de señales intradía y no comparte parámetros con
    él. Su documentación completa —qué se midió, qué sobrevivió y qué no— está
    en :mod:`oro.sesiones`; aquí solo van los números y por qué valen eso.

    Ajustable por entorno: ORO_RUPTURA_ACTIVA, ORO_RUPTURA_R_OBJETIVO,
    ORO_RUPTURA_COSTE_MAX, ORO_RUPTURA_HORAS_VALIDEZ.
    """

    # Interruptor general. Se apaga con ORO_RUPTURA_ACTIVA=0 sin tocar nada más.
    activa: bool = True

    # La ventana cuyo máximo y mínimo forman el rango, en hora de NUEVA YORK:
    # 3:00-8:00, que es la mañana de Londres. Se probaron 2-8, 3-7 y 4-8: las
    # tres dan resultado positivo, así que la hora exacta no es crítica; 3-8 es
    # la que mejor mide y la que tiene sentido económico (Londres entero).
    rango_desde_et: int = 3
    rango_hasta_et: int = 8

    # Cuándo pueden dispararse las órdenes: desde las 8:00 de Nueva York y
    # durante 2 horas. El límite de 2 horas está medido: rupturas en cualquier
    # momento de la sesión dan +0.0552 R/op (t = 3.01); limitándolo a las 2
    # primeras horas sube a +0.0687 (t = 3.38) Y las dos mitades bloqueadas del
    # histórico mejoran a la vez. Lo que se rompe a las 15:00 ya no es una
    # ruptura del rango de la mañana, es otra cosa.
    sesion_desde_et: int = 8
    horas_validez: int = 2

    # A esta hora de Nueva York se cierra lo que siga abierto. Son las 22:00 de
    # Madrid casi todo el año (21:00 las semanas en que Europa y EE. UU. no han
    # cambiado la hora a la vez). Sin riesgo de dormir con la posición abierta.
    cierre_et: int = 16

    # Velas necesarias para dar el rango por bueno (la ventana tiene 5 horas).
    # Con menos, el rango sale más estrecho de lo real y las órdenes quedarían
    # demasiado cerca del precio.
    velas_minimas: int = 4

    # Objetivo, en múltiplos del rango. Medido sobre 4.064 rupturas de 19,6
    # años, neto de 0.60 $ de spread:
    #
    #     dejar correr hasta el cierre   +0.0687 R/op   t 3.38
    #     objetivo 4R (+ stop a BE)      +0.0602        t 3.34
    #     objetivo 3R (+ stop a BE)      +0.0575        t 3.31
    #     objetivo 3R                    +0.0503        t 2.78
    #     objetivo 2R                    +0.0407        t 2.45
    #
    # Dejar correr mide mejor, pero exige estar delante a las 22:00 para cerrar.
    # El objetivo se pone en el bróker y se olvida, que es justo lo que se pidió.
    # 3R conserva el 73 % de la ventaja de dejar correr sin vigilar nada.
    r_objetivo: float = 3.0

    # (Aquí había un `amplitud_minima` de 1.00 $ como suelo fijo del rango. Se
    # quitó al comprobar que era una GUARDA MUERTA en parte: con el spread por
    # defecto de 0.30 $, "coste > 0.30 R" exige un rango menor de 1.00 $, o sea
    # justo lo que el suelo ya rechazaba, y el umbral de coste no llegaba a
    # dispararse nunca. Dos guardas para lo mismo, una de ellas inútil y las dos
    # dando sensación de protección. Se queda la que se adapta al spread.)

    # EL FRENO IMPORTANTE. Por encima de este coste la ventaja medida es
    # NEGATIVA (a 1.45 $: -0.0590 R/op, t = -2.90), así que el sistema deja de
    # emitir el plan en vez de mandar a operar a pérdida. Se sube con
    # ORO_RUPTURA_COSTE_MAX solo si se sabe lo que se hace.
    coste_max: float = 0.60

    # Además, día a día: si el rango de esa mañana es tan estrecho que el spread
    # se lleva más de esta fracción de lo que se arriesga, ese día no se opera.
    #
    # OJO CON APRETARLO, porque suena prudente y no lo es. Este umbral se puso
    # primero en 0.20 y la medición lo desmintió: con spread de 0.60 $ quitaba
    # 163 operaciones y bajaba la t de 3.38 a 2.78, empeorando las DOS mitades
    # del histórico. Los días de rango estrecho no son los malos —son justo los
    # que mejor miden (ver el filtro de rango estrecho en oro/sesiones.py)—, así
    # que filtrarlos por su coste tira ventaja a la basura.
    #
    #     umbral      spread 0.60 $        ops quitadas
    #     sin umbral  +0.0687  t 3.38               0
    #     0.30 R      +0.0683  t 3.36              19   <- actual: red de seguridad
    #     0.20 R      +0.0550  t 2.78             163
    #     0.15 R      +0.0570  t 2.86             519
    #     0.10 R      +0.0492  t 2.27           1.388
    #
    # Se queda en 0.30: caza los días absurdos (con 0.60 $ de spread, un rango
    # de menos de 2 $) sin tocar la estrategia. Tampoco rescata un spread malo,
    # que era la tentación: a 1.45 $ ningún umbral funciona (deja 33 operaciones
    # al año con t = 0.63, indistinguible de cero). Para eso está `coste_max`.
    coste_r_max: float = 0.30


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
    ruptura: ConfiguracionRuptura = field(default_factory=ConfiguracionRuptura)

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

        # Guardas que NO PUEDEN dispararse. Dan sensación de protección sin
        # protejer de nada, y eso es peor que no tenerlas: se confía en ellas.
        # Encontradas revisando: eran tres de las cinco "filtros de calidad".
        c = self.calidad
        if r.r_objetivos and r.reparto_tp:
            rr = sum(f * o for f, o in zip(r.reparto_tp, r.r_objetivos))
            if rr < r.r_recompensa_min:
                problemas.append(
                    f"r_recompensa_min ({r.r_recompensa_min}) es mayor que el R:R "
                    f"que produce la configuración ({rr:.2f}): se rechazarían TODAS "
                    f"las señales.")
        # El umbral de probabilidad, sin modelo, equivale a un umbral de puntuación
        # (probabilidad = 0.40 + 0.35*puntuacion). Si ese equivalente queda por
        # debajo de `puntuacion_minima`, nunca rechaza nada que el otro no rechace.
        # El spread se come la ventaja. Medido sobre 4.410 operaciones de 19,6
        # años: ventaja bruta +0.0298 R con 1R valiendo 7.4 $ de media, así que
        # el equilibrio ronda 0.15 $ (1.16 $ mirando solo 2024-2026, con el oro
        # mucho más caro). Por encima de 1 $ no hay lectura de los datos con la
        # que el sistema salga positivo, y conviene que lo diga en voz alta.
        if r.coste_operacion > 1.0:
            problemas.append(
                f"coste_operacion = {r.coste_operacion:.2f} $/op: por encima del "
                f"spread de equilibrio con cualquier lectura de los datos "
                f"(0.15 $ en 19,6 años, 1.16 $ solo en 2024-2026). El sistema "
                f"pierde por costes, no por las señales.")

        # Ruptura de sesión: las ventanas tienen que encajar, o el rango se
        # mediría sobre horas que no son.
        b = self.ruptura
        if b.rango_desde_et >= b.rango_hasta_et:
            problemas.append(
                f"ruptura: rango_desde_et ({b.rango_desde_et}) debe ser menor que "
                f"rango_hasta_et ({b.rango_hasta_et}).")
        if b.sesion_desde_et < b.rango_hasta_et:
            problemas.append(
                f"ruptura: sesion_desde_et ({b.sesion_desde_et}) no puede empezar "
                f"antes de que termine el rango ({b.rango_hasta_et}): las órdenes "
                f"se colocarían sobre un rango aún sin cerrar.")
        if b.sesion_desde_et + b.horas_validez > b.cierre_et:
            problemas.append(
                f"ruptura: la ventana de disparo termina a las "
                f"{b.sesion_desde_et + b.horas_validez}:00 de Nueva York, después "
                f"del cierre ({b.cierre_et}:00): habría entradas sin tiempo de salir.")
        if b.velas_minimas > b.rango_hasta_et - b.rango_desde_et:
            problemas.append(
                f"ruptura: velas_minimas ({b.velas_minimas}) es mayor que las horas "
                f"de la ventana ({b.rango_hasta_et - b.rango_desde_et}): nunca "
                f"habría rango suficiente y no se emitiría ningún plan.")
        if b.r_objetivo <= 0:
            problemas.append("ruptura: r_objetivo debe ser positivo.")

        equiv = (c.prob_minima - 0.40) / 0.35
        if equiv < c.puntuacion_minima:
            problemas.append(
                f"prob_minima ({c.prob_minima}) equivale a puntuación {equiv:.3f}, "
                f"por debajo de puntuacion_minima ({c.puntuacion_minima}): sin "
                f"modelo entrenado esa guarda no rechaza nada.")
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

    def _bool(nombre: str, actual: bool) -> bool:
        """Interruptor por entorno. Una Variable de Actions sin definir llega
        como cadena VACÍA, y `bool("")` es falso: eso apagaría la estrategia sin
        que nadie lo hubiera pedido. Vacío = se mantiene el valor actual."""
        bruto = (os.getenv(nombre) or "").strip().lower()
        if not bruto:
            return actual
        if bruto in ("1", "true", "si", "sí", "on", "yes"):
            return True
        if bruto in ("0", "false", "no", "off"):
            return False
        print(f"⚠️  {nombre}={bruto!r} no es sí/no; se mantiene {actual}.")
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
    # Ruptura de sesión (ver ConfiguracionRuptura y el módulo oro.sesiones).
    cfg.ruptura.activa = _bool("ORO_RUPTURA_ACTIVA", cfg.ruptura.activa)
    cfg.ruptura.r_objetivo = _num("ORO_RUPTURA_R_OBJETIVO", cfg.ruptura.r_objetivo)
    cfg.ruptura.coste_max = _num("ORO_RUPTURA_COSTE_MAX", cfg.ruptura.coste_max)
    cfg.ruptura.horas_validez = int(
        _num("ORO_RUPTURA_HORAS_VALIDEZ", cfg.ruptura.horas_validez)
    )
    return cfg


__all__ = [
    "ConfiguracionRiesgo",
    "ConfiguracionCalidad",
    "ConfiguracionRuptura",
    "ConfiguracionSistema",
    "cargar_configuracion",
]
