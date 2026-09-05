"""La posición se deja correr y la cierra el stop dinámico.

Medido re-simulando LAS MISMAS 4.410 entradas de 19,6 años con ocho gestiones
distintas (así el efecto es de la salida y no de un cambio de señal):

    escalera 1R/2R/3R      bruto -0.0016 R/op, mejor operación +1.70 R
    stop dinámico          bruto +0.0527 R/op, mejor operación +9.57 R  (t = 3.32)

La escalera no protegía de las pérdidas —la peor operación es -1.00 R en las
dos— sino que capaba las ganancias. Gana en 12 de 12 ventanas temporales, y un
walk-forward que elige con el pasado y cobra en la ventana siguiente da
+0.0517 R/op (t = 4.33, 10/10). El precio medido: el acierto baja del 48% al 40%.

Estas pruebas fijan lo que puede romperse en silencio: que no vuelva a aparecer
un objetivo cercano, que el filtro de R:R no rechace todas las señales al quedarse
sin objetivos, y que el correo no mande poner un take profit que no existe.
"""

from __future__ import annotations

import datetime as dt

import pytest

from oro.config import cargar_configuracion
from oro.dominio import Direccion, Signal
from oro.riesgo import calcular_niveles, dimensionar_posicion


def _senal():
    cfg = cargar_configuracion()
    n = calcular_niveles(4451.90, Direccion.COMPRA, atr=8.4, cfg=cfg)
    return Signal(momento=dt.datetime.now(dt.timezone.utc), direccion=Direccion.COMPRA,
                  entrada=n.entrada, stop_loss=n.stop_loss, take_profits=n.take_profits,
                  probabilidad=0.67, confianza=0.86, riesgo_recompensa=n.riesgo_recompensa,
                  tamano_posicion=dimensionar_posicion(n.riesgo_por_unidad, cfg),
                  motivos_entrada=["Estructura alcista"], riesgos=[],
                  contexto_tecnico="alcista", puntuacion=0.71)


def test_no_hay_objetivos_que_capen_las_ganadoras():
    r = cargar_configuracion().riesgo
    assert r.r_objetivos == (), "un objetivo fijo vuelve a capar las ganadoras"
    assert r.reparto_tp == ()


def test_el_stop_dinamico_arranca_desde_la_entrada():
    # Sin objetivos, el trailing antiguo (que solo despertaba al tocar un TP) no
    # se activaría NUNCA y la posición quedaría sin gestión ninguna.
    r = cargar_configuracion().riesgo
    assert r.trailing_activo is True
    assert r.trailing_desde_entrada is True


def test_el_filtro_de_rr_no_rechaza_todas_las_senales():
    # riesgo_recompensa vale 0 sin objetivos. Si la guarda siguiera aplicándose,
    # el motor no emitiría ni una señal y el sistema quedaría mudo en silencio.
    from oro.datos.sintetico import ProveedorSintetico
    from oro.senales import MotorSenales

    cfg = cargar_configuracion()
    df = ProveedorSintetico(semilla=7).historico(900)
    motor = MotorSenales(cfg)
    rechazos = 0
    for i in range(500, 900, 25):
        from oro.dominio import MarketSnapshot, sesion_de
        from oro.indicadores import atr as _atr
        momento = df.index[i].to_pydatetime()
        a = float(_atr(df.iloc[: i + 1], 14).iloc[-1])
        if a <= 0:
            continue
        snap = MarketSnapshot(momento=momento, precio=float(df["close"].iloc[i]),
                              spread=0.2, atr=a, sesion=sesion_de(momento))
        res = motor.analizar(df.iloc[max(0, i - 400): i + 1], snap)
        rechazos += any("R:R insuficiente" in m for m in res.motivos_no)
    assert rechazos == 0, "la guarda de R:R está rechazando señales sin objetivos"


def test_el_gestor_en_vivo_persigue_el_precio_desde_el_principio():
    from oro.vivo.gestor import GestorOperaciones

    sig = _senal()
    g = GestorOperaciones(sig, trailing_activo=True, trailing_r=1.0,
                        trailing_desde_entrada=True)
    riesgo = abs(sig.entrada - sig.stop_loss)
    inicial = g.stop_actual
    g.actualizar(sig.entrada + riesgo * 2, dt.datetime.now(dt.timezone.utc))
    assert g.stop_actual > inicial, "el stop no siguió al precio"
    assert g.stop_actual >= sig.entrada, "a +2R el stop debería haber pasado la entrada"


def test_un_stop_inicial_no_se_anuncia_como_break_even():
    # `_en_breakeven` decide el texto del aviso. Si se diera por cierto solo
    # porque el trailing está activo, una pérdida completa se anunciaría como
    # "operación protegida", que es exactamente lo contrario de lo que pasó.
    from oro.vivo.gestor import GestorOperaciones

    sig = _senal()
    g = GestorOperaciones(sig, trailing_activo=True, trailing_r=1.0,
                        trailing_desde_entrada=True)
    eventos = g.actualizar(sig.stop_loss - 1.0, dt.datetime.now(dt.timezone.utc))
    texto = " ".join(e.mensaje for e in eventos)
    assert "BREAK-EVEN" not in texto.upper(), texto
    assert "STOP" in texto.upper()
    assert g.r_acumulado < 0


def test_el_aviso_explica_la_salida_y_no_manda_poner_un_take_profit():
    from oro.notificaciones.base import mensaje_de_senal, mensaje_html_de_senal

    sig = _senal()
    for texto in (mensaje_de_senal(sig), mensaje_html_de_senal(sig)):
        assert "TP1" not in texto and "Take Profit" not in texto
        assert ("te aviso" in texto) or ("te avisaré" in texto) or ("aviso al salir" in texto)
    assert "No pongas take profit" in mensaje_de_senal(sig)
    # Y que no anuncie un R:R inventado a partir de una configuración vacía.
    assert "0.00" not in mensaje_de_senal(sig)
