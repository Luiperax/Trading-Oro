"""Guardas que dan sensación de proteger sin proteger de nada.

Es peor que no tenerlas: se confía en ellas. Revisando el filtro de calidad
aparecieron tres, y todas se descubren igual —comprobando si el umbral puede
llegar a rechazar algo—, así que la comprobación se automatiza en `validar()`.

  * El R:R ponderado sale de multiplicar CONSTANTES de configuración: no depende
    del precio ni del ATR, así que vale lo mismo en todas las señales. Nunca
    rechazó una aceptando otra.
  * El umbral de probabilidad, sin modelo entrenado, equivale a un umbral de
    puntuación (probabilidad = 0.40 + 0.35*puntuacion, correlación 1.0000). Con
    los valores de fábrica equivale a puntuación 0.571, por debajo del umbral de
    puntuación (0.66): no rechaza nada que el otro no rechace ya.
  * `spread_max = 0.6` frente a un spread que el proveedor escribe fijo en 0.2:
    la condición 0.2 > 0.6 nunca es cierta.
"""

from __future__ import annotations

import copy

from oro.config import cargar_configuracion


def test_avisa_si_el_rr_minimo_rechazaria_todas_las_senales():
    cfg = copy.deepcopy(cargar_configuracion())
    cfg.riesgo.r_objetivos = (1.0,)
    cfg.riesgo.reparto_tp = (1.0,)
    cfg.riesgo.r_recompensa_min = 1.5      # 1.0 < 1.5 -> ninguna señal pasaría
    problemas = cfg.validar()
    assert any("TODAS" in p for p in problemas), problemas


def test_avisa_si_el_umbral_de_probabilidad_no_puede_rechazar_nada():
    cfg = cargar_configuracion()
    equiv = (cfg.calidad.prob_minima - 0.40) / 0.35
    problemas = cfg.validar()
    if equiv < cfg.calidad.puntuacion_minima:
        assert any("no rechaza nada" in p for p in problemas), (
            "la guarda muerta no se está delatando")
    else:
        assert not any("no rechaza nada" in p for p in problemas)


def test_la_configuracion_de_fabrica_no_tiene_guardas_imposibles():
    # Distinto de la anterior: aquí se comprueba que ninguna guarda rechace TODO,
    # que es el fallo que dejaría el sistema mudo sin dar ningún error.
    problemas = cargar_configuracion().validar()
    assert not any("TODAS" in p for p in problemas), problemas


def test_el_aviso_no_llama_probabilidad_a_la_puntuacion():
    """Sin modelo, `probabilidad` es 0.40 + 0.35*puntuacion: correlación 1.0000
    con la puntuación. Anunciarlo como "probabilidad estimada del 67%" promete
    una precisión que no existe."""
    import datetime as dt

    from oro.dominio import Direccion, Signal
    from oro.notificaciones.base import mensaje_de_senal, mensaje_html_de_senal
    from oro.riesgo import calcular_niveles

    cfg = cargar_configuracion()
    n = calcular_niveles(4451.90, Direccion.COMPRA, atr=8.4, cfg=cfg)
    base = dict(momento=dt.datetime.now(dt.timezone.utc), direccion=Direccion.COMPRA,
                entrada=n.entrada, stop_loss=n.stop_loss, take_profits=n.take_profits,
                confianza=0.86, riesgo_recompensa=n.riesgo_recompensa,
                tamano_posicion=1.0, motivos_entrada=["x"], riesgos=[],
                contexto_tecnico="", puntuacion=0.71)

    sin_modelo = Signal(probabilidad=0.6485, probabilidad_de_modelo=False, **base)
    for texto in (mensaje_de_senal(sin_modelo), mensaje_html_de_senal(sin_modelo)):
        assert "Probabilidad" not in texto, "presenta la puntuación como probabilidad"
        assert "Calidad" in texto

    con_modelo = Signal(probabilidad=0.6485, probabilidad_de_modelo=True, **base)
    for texto in (mensaje_de_senal(con_modelo), mensaje_html_de_senal(con_modelo)):
        assert "Probabilidad" in texto, "con modelo sí es una probabilidad"


def test_el_motor_marca_de_donde_viene_la_probabilidad():
    import warnings

    warnings.filterwarnings("ignore")
    from oro.datos.sintetico import ProveedorSintetico
    from oro.dominio import MarketSnapshot, sesion_de
    from oro.indicadores import atr as _atr
    from oro.senales import MotorSenales

    cfg = cargar_configuracion()
    df = ProveedorSintetico(semilla=3).historico(900)
    motor = MotorSenales(cfg)          # sin modelo
    for i in range(500, 900, 5):
        a = float(_atr(df.iloc[: i + 1], 14).iloc[-1])
        if a <= 0:
            continue
        mom = df.index[i].to_pydatetime()
        snap = MarketSnapshot(momento=mom, precio=float(df["close"].iloc[i]),
                              spread=0.2, atr=a, sesion=sesion_de(mom))
        res = motor.analizar(df.iloc[max(0, i - 400): i + 1], snap)
        if res.signal is not None:
            assert res.signal.probabilidad_de_modelo is False
            # Y la relación exacta que lo delata.
            assert abs(res.signal.probabilidad
                       - (0.40 + 0.35 * res.signal.puntuacion)) < 1e-9
            return
    raise AssertionError("no se generó ninguna señal en la muestra")
