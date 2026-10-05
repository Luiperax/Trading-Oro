"""Configuración central del sistema de trading de XAU/USD.

Todos los parámetros sensibles (riesgo, umbrales de calidad, límites de
operación) están aquí y pueden ajustarse sin tocar la lógica. Los valores por
defecto son conservadores a propósito: la prioridad es proteger el capital.

Se pueden sobreescribir mediante variables de entorno con prefijo ``ORO_``
(p. ej. ``ORO_RIESGO_POR_OPERACION=0.005``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from . import entorno


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
    # YA NO ES UN NÚMERO ELEGIDO: ESTÁ MEDIDO.
    #
    # Valía 0.30 $ porque alguien lo puso, y el coste es la restricción que
    # decide todas las estrategias de este proyecto. Medido ahora sobre los
    # ticks de Dukascopy, que dan bid y ask reales —3.189.713 ticks de 230 horas
    # y 20 días de mercado—, el spread de XAU/USD es:
    #
    #     hora UTC   hora ET   mediana $
    #        0          20       0.802
    #        7-11       3-7      0.575
    #        12-13      8-9      0.595    <- ventana en que salta la orden
    #        14         10       0.605
    #        19-20      15-16    0.680    <- cierre de la sesión
    #        22         18       0.810
    #
    # O sea: el doble de lo que se asumía. Se pone 0.60, que es la mediana en la
    # ventana de disparo. Vuelve a medirse con `python -m oro.spread`.
    #
    # Y por años, muestreado en esas mismas horas (el fijo tampoco valía para el
    # pasado): 0.46 $ en 2007-2011, 0.29 en 2013-2016, 0.22-0.39 en 2018-2022,
    # 0.55 en 2025 y 0.63 en 2026. En puntos básicos ha mejorado sin parar
    # (6.9 pb en 2007, 1.35 pb en 2026): el spread sube en dólares solo porque
    # sube el oro.
    #
    # QUÉ LE HACE A LA ESTRATEGIA. Recalculada la ruptura con el spread real de
    # cada año en vez del 0.30 fijo:
    #
    #     modelo de coste              R/op       t   1ª mitad  2ª mitad  R/año
    #     0.30 $ fijo (lo anterior)  +0.1143   4.37    +0.1270   +0.1009  +11.59
    #     spread REAL de cada año    +0.1029   3.93    +0.1067   +0.0990  +10.45
    #     1.5 spreads                +0.0742   2.83    +0.0713   +0.0771   +7.53
    #     2 spreads (cota)           +0.0454   1.73    +0.0360   +0.0553   +4.60
    #     3 spreads                  -0.0122  -0.46    -0.0348   +0.0116   -1.24
    #
    # Aguanta el coste real y aguanta el doble; a tres spreads muere. Las cotas
    # importan porque el nivel del rango se mide sobre BID: la venta entra a bid
    # (sin coste) y el cierre compra a ask (un spread), pero el STOP se dispara
    # cuando el ASK llega al máximo, o sea antes de lo que ve la simulación. Esa
    # segunda media parte no está contada en el modelo de un spread.
    #
    # Ajustable por ORO_COSTE_OPERACION. Si tu bróker te cobra comisión aparte,
    # súmala aquí: lo que importa es el coste total de ida y vuelta.
    coste_operacion: float = 0.60

    # DESLIZAMIENTO AL ENTRAR, medido con ticks. Una orden stop no se llena en el
    # nivel: se llena en el primer precio que lo cruza. En 80 días normales al
    # azar: mediana 0.04 $, media 0.25 $ (0.033 R), máximo 10.32 $. En los 83
    # días de empleo: mediana 0.10 $, media 1.31 $, máximo 34.55 $.
    #
    # Se suma al spread en cada ficha del registro. Sin él la estrategia
    # parecía rendir +0.103 R por operación; con él, +0.065. Es el coste que
    # faltaba y conviene que lo que el sistema apunta sea lo que pasa.
    deslizamiento_entrada: float = 0.25

    # El día del dato de empleo el precio atraviesa el nivel de golpe a las
    # 8:30 ET y el relleno sale peor: media 1.31 $ medida en 83 días. Cobrarle a
    # ese día el deslizamiento de un día normal inflaba su resultado de +0.67 a
    # +0.75 R por operación.
    deslizamiento_empleo: float = 1.30


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
    ORO_RUPTURA_HORAS_VALIDEZ, ORO_RUPTURA_SESGO_CUERPO_MINIMO,
    ORO_RUPTURA_SOLO_VENTAS, ORO_RUPTURA_ANULAR_SI_ROMPE_ARRIBA,
    ORO_RUPTURA_DOS_ORDENES_EN_EMPLEO.
    """

    # Interruptor general. Se apaga con ORO_RUPTURA_ACTIVA=0 sin tocar nada más.
    activa: bool = True

    # SOLO SE OPERA LA ROTURA A LA BAJA, Y SOLO SI ES LA PRIMERA DEL DÍA.
    #
    # Medido sobre 4.646 días con rotura de 2006-2026 (21 años, velas H1 de
    # Dukascopy), neto de 0.30 $ de coste —medio spread más a la compra, porque
    # el nivel se mide sobre BID y se entra al ask—:
    #
    #     lado         n      R/op      t    1ª mitad   2ª mitad   años +
    #     venta     2117   +0.1069   4.02    +0.1339    +0.0789    14/21
    #     compra    2529   -0.0638  -2.56    -0.0549    -0.0714     4/21
    #
    # Las compras no son más débiles: son un lastre medido de -7.7 R al año.
    #
    # Reconstruido después con `python -m oro.historico`, que no reimplementa
    # nada: llama a `construir_plan` y `seguir`, las de producción, y descuenta
    # TODOS los costes medidos con ticks: el spread de cada año (`oro.spread`)
    # y el deslizamiento de la orden stop (0.25 $ un día normal, 1.30 $ el día
    # del dato de empleo). Con las dos órdenes el día de empleo:
    #
    #                           n      R/op       t    R/año
    #     total              2208   +0.0786    3.00    +8.26
    #     días de empleo      160   +0.5815    4.13    +4.43
    #     resto (venta)      2048   +0.0393    1.52    +3.83
    #
    # Mitades +0.0778 / +0.0795, 14 años positivos de 21, peor año -19.6 R,
    # peor racha -45.9 R. Más de la mitad del rendimiento sale de unos 8 días al
    # año; el resto de días la venta es positiva pero NO está demostrada por sí
    # sola (t = 1.52). Conviene saberlo.
    #
    # Las cifras viejas (+0.1143, t = 4.37) suponían 0.30 $ de coste y ningún
    # deslizamiento. Ninguna de las dos cosas se había medido.
    #
    # Y LO DECISIVO: no vale «vender oro». Lo que funciona es la rotura a la
    # baja que ocurre PRIMERA. La misma rotura a la baja, cuando llega después
    # de que el rango se haya roto al alza, es un latigazo que se gira:
    #
    #     población de días                        n      R/op       t   años +
    #     rompe abajo primero (se opera)        2117   +0.1069    4.02    14/21
    #     rompe arriba y LUEGO abajo (se anula)  869   -0.2863   -8.73     2/21
    #     las dos juntas                        2986   -0.0075   -0.35    10/21
    #
    # Por eso `anular_si_rompe_arriba` no es un refinamiento: si la orden de
    # venta se queda puesta cuando el rango se rompe al alza, la ventaja entera
    # desaparece (-1.07 R al año en lugar de +10.78).
    #
    # Sobrevive a 11 perturbaciones de horario (rango 2-8, 4-8, 3-7; validez
    # 1h, 3h, 4h; cierre a las 14 y 15 ET; velas mínimas 3): las 11 positivas,
    # 10 de ellas con las dos mitades positivas. Quitando a la vez el mejor y
    # el peor año quedan +0.0989 R/op con t = 3.84 y 13 de 19 años a favor.
    # Con 31 pruebas acumuladas en el estudio, Bonferroni exige |t| > 3.25.
    solo_ventas: bool = True

    # Al romperse el rango al alza, la orden de venta pendiente se ANULA. Ver
    # arriba: es lo que separa +10.78 R/año de -1.07 R/año.
    anular_si_rompe_arriba: bool = True

    # LA EXCEPCIÓN: EL DÍA DEL DATO DE EMPLEO DE EE. UU. VAN LAS DOS ÓRDENES.
    #
    # El informe sale a las 8:30 ET, dentro de la ventana de disparo, y ese día
    # la rotura es el mercado reaccionando al dato: sigue en la dirección en que
    # sale, en las DOS. Medido con el relleno REAL sacado tick a tick:
    #
    #     días de empleo     n      R/op       t   1ª mitad  2ª mitad
    #     venta             83   +0.5646    2.83    +0.533    +0.594
    #     compra            76   +0.7947    4.01    +0.827    +0.764
    #     las dos          159   +0.6746    4.79    19 años positivos de 21
    #
    # Añade +3.10 R al año en días que hoy se anulan. Detalle y cálculo de la
    # fecha en `oro.calendario`.
    dos_ordenes_en_dia_de_empleo: bool = True

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

    # Objetivo, en múltiplos del rango. YA NO ES LA SALIDA: es una red de
    # seguridad. La salida es el cierre a mano al final de la sesión.
    #
    # Medido sobre 4.065 rupturas de 19,6 años, neto de 0.60 $, con la
    # frecuencia con que cada objetivo llega a ejecutarse:
    #
    #     salida                      R/op       t     lo toca
    #     sin objetivo             +0.0685    3.37       0.0 %
    #     objetivo 10R             +0.0673    3.34       0.1 %   <- actual
    #     objetivo  8R             +0.0642    3.24       0.2 %
    #     objetivo  6R             +0.0626    3.20       0.8 %
    #     objetivo  4R             +0.0513    2.74       2.7 %
    #     objetivo  3R             +0.0501    2.77       6.1 %   <- antes
    #
    # Y con el stop movido a la entrada al llegar a 1R:
    #
    #     sin objetivo + BE en 1R  +0.0768    3.91
    #     objetivo 3R  + BE en 1R  +0.0574    3.30
    #
    # O sea: el objetivo a 3R cortaba las ganadoras grandes y costaba un tercio
    # de la ventaja.
    #
    # ¿Y CUÁNTO SE ALCANZA DE VERDAD EN UN SOLO DÍA? Es la pregunta correcta,
    # porque la operación se abre y se cierra en la misma sesión. Excursión
    # favorable máxima de las 4.065 rupturas, antes de que las cierre el stop:
    #
    #     1R  38.9 %  (81 veces/año)      5R   1.4 %  (3.0/año)
    #     2R  15.0 %  (31/año)            6R   0.8 %  (1.6/año)
    #     3R   6.2 %  (12.8/año)          8R   0.2 %  (0.5/año)
    #     4R   2.7 %  (5.6/año)          10R   0.1 %  (0.3/año)
    #
    # Mediana 0.74 R, percentil 99 en 5.4 R. Con el rango de hoy (~26 $), 10R
    # son 260 $ de recorrido en una sesión: el oro no hace eso ni en sus peores
    # días. Un objetivo que salta 0.3 veces al año no es una red de seguridad,
    # es decoración, y encima queda ridículo en la pantalla del bróker.
    #
    # 6R salta 1.6 veces al año —existe de verdad— y cuesta 0.0059 R, el 8.6 %
    # de la ventaja. Ese es el precio del seguro y es el que se paga.
    r_objetivo: float = 6.0

    # CUÁL DE LAS DOS ÓRDENES ES LA DE FIAR.
    #
    # A las 8:00 de Nueva York ya se sabe qué ha hecho la sesión asiática, y ese
    # dato separa las dos rupturas. Medido sobre 4.064 rupturas de 19,6 años,
    # neto de 0.60 $ y con el objetivo a 3R:
    #
    #     ruptura A FAVOR de lo que hizo Asia   +0.0883 R/op   t 3.32
    #     ruptura EN CONTRA                     +0.0133 R/op   t 0.54
    #
    # O sea: el lado que acompaña a Asia se lleva casi toda la ventaja, y el otro
    # queda en nada. Las dos mitades bloqueadas del histórico coinciden en el
    # signo (+0.1293/+0.0506 a favor, +0.0128/+0.0137 en contra), 15 de 20 años
    # también, y las 5 formas distintas de medir la sesión asiática que se
    # probaron apuntan en la misma dirección.
    #
    # HONESTAMENTE: la DIFERENCIA entre lados da t = 2.07, que NO pasa la
    # corrección de Bonferroni con 5 hipótesis (haría falta 2.81). Es una
    # indicación sólida, no un hecho demostrado, y el correo lo dice así.
    #
    # NO se usa como filtro: quedarse solo con el lado bueno da +9.1 R al año
    # frente a +10.4 R con los dos, porque se pierden la mitad de operaciones.
    # Se usa solo para etiquetar cuál de las dos merece más confianza.
    sesgo_desde_et: int = 0
    sesgo_hasta_et: int = 3
    # El cuerpo de la sesión asiática (cierre - apertura) tiene que valer al
    # menos esta fracción de su rango. Por debajo, la sesión no dice nada: esos
    # 885 días miden -0.0162 R/op y los dos lados se parecen (-0.029 al alza,
    # -0.004 a la baja), así que el correo NO señala favorita.
    sesgo_cuerpo_minimo: float = 0.20

    # (Aquí había un `amplitud_minima` de 1.00 $ como suelo fijo del rango. Se
    # quitó al comprobar que era una GUARDA MUERTA en parte: con el spread por
    # defecto de 0.30 $, "coste > 0.30 R" exige un rango menor de 1.00 $, o sea
    # justo lo que el suelo ya rechazaba, y el umbral de coste no llegaba a
    # dispararse nunca. Dos guardas para lo mismo, una de ellas inútil y las dos
    # dando sensación de protección. Se queda la que se adapta al spread.)



@dataclass(slots=True)
class ConfiguracionSistema:
    # El símbolo del instrumento para la INVESTIGACIÓN (Dukascopy, XAU/USD al
    # contado). No es el que se opera en vivo: ver `simbolo_vivo`.
    simbolo: str = "XAUUSD"

    # EL SÍMBOLO QUE DE VERDAD SE OPERA, y no es el mismo.
    #
    # El feed en vivo gratuito es Yahoo, y Yahoo NO sirve XAU/USD al contado en
    # velas horarias (XAUUSD=X, XAU=X y GCUSD=X dan 404; ^XAU es el índice de
    # mineras). Lo único disponible es `GC=F`: el futuro de oro de COMEX.
    #
    # Medido en septiembre de 2026 sobre 477 horas comunes, el futuro cotizó
    # 40,17 $ por encima del contado de media, y la base se movió de 48,63 el
    # día 1 a 31,70 el día 30. Sus rangos H1 son un 1,5 % más anchos (t = 5,08,
    # mayores en el 72 % de las horas).
    #
    # Consecuencias, y conviene tenerlas claras:
    #
    #   · TODA la investigación de este proyecto está medida sobre el contado de
    #     Dukascopy, así que ninguna ventaja se ha validado nunca sobre el
    #     instrumento que realmente se opera. No hay forma de arreglarlo gratis:
    #     Yahoo da ~45 días de histórico horario de futuros.
    #   · Que la estrategia sea INTRADÍA es lo que lo hace soportable. La base
    #     converge ~0,7 $/día; en las pocas horas que dura una operación son
    #     0,002 R sobre un 1R de 35 $. Si la posición durmiera, la convergencia
    #     se comería las compras sistemáticamente.
    #   · Si el bróker de quien opera cotiza el CONTADO, los niveles del correo
    #     no existen en su pantalla. El correo lo avisa (ver
    #     `oro.notificaciones.plan.aviso_instrumento`), porque desde aquí no se
    #     puede detectar: el sistema solo ve un feed.
    #
    # Antes esto no estaba escrito en ningún sitio: `ProveedorYahoo` usaba su
    # propio `GC=F` por defecto y nadie le pasaba `cfg.simbolo`, así que la
    # configuración decía XAUUSD y el sistema operaba otra cosa.
    simbolo_vivo: str = "GC=F"

    # DE DÓNDE SALEN LOS PRECIOS EN VIVO: "yahoo" o "dukascopy".
    #
    # "yahoo" (lo que va puesto) sirve GC=F, el futuro de COMEX, y sirve también
    # la vela EN CURSO a medias, así que el seguimiento reacciona dentro de la
    # hora.
    #
    # "dukascopy" sirve XAU/USD AL CONTADO —el mismo instrumento sobre el que
    # está medida toda la investigación— y además bid y ask reales. Medido el
    # 5-oct-2026: los ticks de una hora aparecen 2,2 minutos después de que la
    # hora cierre. Lo que NO da es la hora en curso, así que el seguimiento
    # reaccionaría hasta una hora más tarde, y el aviso de cancelar es
    # justamente el que sostiene la ventaja.
    #
    # VA EN "dukascopy", y esto es lo que lo decidió. Contrastadas las dos
    # fuentes contra el LBMA Gold Price —el precio de referencia OFICIAL del
    # oro al contado, que publica el World Gold Council— a la misma hora:
    #
    #     Dukascopy contado  vs fix:   +3.34 $ de media  (|dif| mediana  3.99)
    #     Yahoo GC=F futuro  vs fix:  +43.08 $ de media  (|dif| mediana 44.62)
    #
    # El correo dice «busca XAU/USD (oro)», que ES el contado por definición,
    # mientras los niveles salían del futuro. Las dos cosas no pueden ser
    # correctas: unas órdenes 43 $ por encima del precio del bróker no esperan
    # a la ruptura, se ejecutan al instante.
    #
    # Lo que se pierde: Dukascopy no publica la hora EN CURSO, así que los
    # avisos del seguimiento llegan hasta una hora más tarde. Yahoo servía la
    # vela a medias. Se acepta porque un aviso tardío es un coste ocasional y
    # un instrumento equivocado es un error permanente.
    #
    # `ORO_FUENTE_VIVO=yahoo` lo revierte sin tocar código.
    fuente_vivo: str = "dukascopy"
    capital: float = 3_000.0             # capital de la cuenta (divisa base). Configurable por ORO_CAPITAL.
    # Marco temporal de trabajo. H1 (1 hora) para operativa INTRADÍA (abrir y
    # cerrar el mismo día). Nota honesta: los marcos intradía tienen un borde más
    # fino que H4/D1; se compensa cerrando siempre el mismo día (sin riesgo
    # overnight). Configurable por ORO_TIMEFRAME.
    timeframe: str = "H1"
    zona_horaria: str = "UTC"

    # EL MOTOR DE SEÑALES INTRADÍA ESTÁ APAGADO. No es una decisión de gusto.
    #
    # Reconstruidas sus 4.891 operaciones sobre 21 años (2006-2026) con esta
    # misma configuración —`r_objetivos=(2.0,)`, `atr_stop_mult=1.5`,
    # `trailing_desde_entrada=True`— y la cuenta sale así:
    #
    #     R bruto medio            -0.0314   (t = -2.43)
    #     R neto medio (0.30 $)    -0.0899   (t = -6.94)
    #     años positivos                2 de 21
    #     R acumulado                -439.5
    #
    # A 0.25 % de riesgo son -157 € al año sobre 3.000 €, todos los años menos
    # dos. Y esos dos son 2025 y 2026: la ventana en la que se construyó y se
    # ajustó el sistema.
    #
    # Antes de apagarlo se intentó arreglarlo, y está medido que no se puede:
    #
    #   · seis variantes de salida (sin trailing, sin trailing desde la entrada,
    #     objetivo 3R, stop 2.5xATR…): las seis negativas en BRUTO;
    #   · walk-forward por años sobre 4.294 operaciones fuera de muestra:
    #     AUC 0.5054, y el cuartil "mejor" rinde -0.0900 R frente a -0.0738 del
    #     "peor", o sea que ordena al revés;
    #   · sus 93 motivos de entrada: ninguno pasa Bonferroni, y "ADX 28" da
    #     -0.1724 R mientras "ADX 29" da +0.1826. Un efecto real no cambia de
    #     signo entre dos enteros consecutivos.
    #
    # El vigilante SIGUE ejecutándose: en el mismo bucle atiende el seguimiento
    # de la ruptura, que es la estrategia que sí tiene ventaja. Lo único que no
    # hace es abrir operaciones nuevas del motor de señales.
    #
    # Para volver a encenderlo: ORO_SENALES_ACTIVAS=1.
    senales_activas: bool = False

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
        if b.sesgo_desde_et >= b.sesgo_hasta_et:
            problemas.append(
                f"ruptura: sesgo_desde_et ({b.sesgo_desde_et}) debe ser menor que "
                f"sesgo_hasta_et ({b.sesgo_hasta_et}).")
        if b.sesgo_hasta_et > b.rango_desde_et:
            problemas.append(
                f"ruptura: la ventana del sesgo termina a las {b.sesgo_hasta_et}:00 "
                f"y el rango empieza a las {b.rango_desde_et}:00: se solaparían y "
                f"el sesgo miraría las mismas velas que forman el rango.")
        if not 0.0 <= b.sesgo_cuerpo_minimo < 1.0:
            problemas.append(
                f"ruptura: sesgo_cuerpo_minimo ({b.sesgo_cuerpo_minimo}) debe estar "
                f"en [0, 1): es una fracción del rango de la sesión asiática.")

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

    # La lectura del entorno vive en oro/entorno.py: una variable VACÍA es una
    # variable no definida, siempre. Tener aquí una copia de esas reglas hacía
    # que el resto del código (canales, tiempo, web) usara otras distintas, y
    # ahí es donde apareció el fallo que tumbó el vigilante.
    def _num(nombre: str, actual):
        return (entorno.entero(nombre, actual) if isinstance(actual, int)
                else entorno.decimal(nombre, actual))

    _bool = entorno.booleano

    cfg.capital = _num("ORO_CAPITAL", cfg.capital)
    # Con la variable VACÍA esto dejaba el símbolo en "" y el proveedor pedía
    # un instrumento sin nombre.
    cfg.simbolo = entorno.texto("ORO_SIMBOLO", cfg.simbolo)
    cfg.simbolo_vivo = entorno.texto("ORO_SIMBOLO_VIVO", cfg.simbolo_vivo)
    cfg.fuente_vivo = entorno.texto("ORO_FUENTE_VIVO", cfg.fuente_vivo).lower()
    cfg.timeframe = _marco(entorno.texto("ORO_TIMEFRAME"), cfg.timeframe)
    cfg.riesgo.riesgo_por_operacion = _num(
        "ORO_RIESGO_POR_OPERACION", cfg.riesgo.riesgo_por_operacion
    )
    cfg.ruta_operaciones = entorno.texto("ORO_RUTA_OPERACIONES", cfg.ruta_operaciones)
    cfg.ruta_senales = entorno.texto("ORO_RUTA_SENALES", cfg.ruta_senales)
    cfg.ruta_modelo = entorno.texto("ORO_RUTA_MODELO", cfg.ruta_modelo)
    cfg.riesgo.trailing_r = _num("ORO_TRAILING_R", cfg.riesgo.trailing_r)
    cfg.riesgo.coste_operacion = _num("ORO_COSTE_OPERACION", cfg.riesgo.coste_operacion)
    cfg.riesgo.deslizamiento_entrada = _num(
        "ORO_DESLIZAMIENTO_ENTRADA", cfg.riesgo.deslizamiento_entrada)
    cfg.riesgo.deslizamiento_empleo = _num(
        "ORO_DESLIZAMIENTO_EMPLEO", cfg.riesgo.deslizamiento_empleo)
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
    cfg.ruptura.horas_validez = int(
        _num("ORO_RUPTURA_HORAS_VALIDEZ", cfg.ruptura.horas_validez)
    )
    cfg.ruptura.sesgo_cuerpo_minimo = _num(
        "ORO_RUPTURA_SESGO_CUERPO_MINIMO", cfg.ruptura.sesgo_cuerpo_minimo
    )
    cfg.senales_activas = _bool("ORO_SENALES_ACTIVAS", cfg.senales_activas)
    cfg.ruptura.solo_ventas = _bool("ORO_RUPTURA_SOLO_VENTAS", cfg.ruptura.solo_ventas)
    cfg.ruptura.anular_si_rompe_arriba = _bool(
        "ORO_RUPTURA_ANULAR_SI_ROMPE_ARRIBA", cfg.ruptura.anular_si_rompe_arriba
    )
    cfg.ruptura.dos_ordenes_en_dia_de_empleo = _bool(
        "ORO_RUPTURA_DOS_ORDENES_EN_EMPLEO", cfg.ruptura.dos_ordenes_en_dia_de_empleo
    )
    return cfg


__all__ = [
    "ConfiguracionRiesgo",
    "ConfiguracionCalidad",
    "ConfiguracionRuptura",
    "ConfiguracionSistema",
    "cargar_configuracion",
]
