"""La salida: stop dinámico + un objetivo lejano, todo puesto al abrir.

Medido re-simulando LAS MISMAS 4.410 entradas de 19,6 años con ocho gestiones
distintas (así el efecto es de la salida y no de un cambio de señal):

    escalera 1R/2R/3R      bruto -0.0016 R/op, mejor operación +1.70 R
    stop dinámico + TP 5R  bruto +0.0481 R/op (t = 3.12), gana 12/12 ventanas

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


def test_hay_un_unico_objetivo_y_esta_lejos():
    # Quien recibe el aviso no gestiona la salida: necesita un TP que poner. Pero
    # cerca vuelve a capar las ganadoras, que es lo que hundía a la escalera:
    # a 2R cuesta 0.0228 R y corta el 12% de las operaciones; a 5R cuesta
    # 0.0045 R y corta el 0.9%.
    r = cargar_configuracion().riesgo
    assert len(r.r_objetivos) == 1, "una sola orden de TP, para no exigir cierres parciales"
    assert r.reparto_tp == (1.0,), "el TP debe cubrir toda la posición"
    assert r.r_objetivos[0] >= 4.0, "un objetivo cercano vuelve a capar las ganadoras"


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


def test_el_aviso_da_las_tres_ordenes_que_hay_que_poner():
    # Entrada, stop, TP y la distancia del trailing. Sin la distancia, quien lo
    # recibe se queda con un stop fijo —la gestión peor medida— sin enterarse.
    from oro.notificaciones.base import mensaje_de_senal, mensaje_html_de_senal

    sig = _senal()
    riesgo = abs(sig.entrada - sig.stop_loss)
    for texto in (mensaje_de_senal(sig), mensaje_html_de_senal(sig)):
        assert f"{sig.entrada:.2f}" in texto
        assert f"{sig.stop_loss:.2f}" in texto
        assert f"{sig.take_profits[0].precio:.2f}" in texto, "falta el precio del TP"
        assert f"{riesgo:.2f}" in texto, "falta la distancia del trailing stop"


def test_la_distancia_del_trailing_coincide_con_la_configurada():
    from oro.notificaciones.base import _trailing

    cfg = cargar_configuracion()
    sig = _senal()
    dist, activo = _trailing(sig)
    assert activo is True
    esperado = abs(sig.entrada - sig.stop_loss) * cfg.riesgo.trailing_r
    assert dist == pytest.approx(esperado)


def test_los_pasos_no_contradicen_el_cierre_intradia():
    # El pie del aviso anuncia un correo de cierre a las 21:50. Un paso que diga
    # "no hay que vigilar nada más" lo contradice, y quien lo lea se dejará la
    # posición abierta de noche convencido de que se cerraba sola.
    from oro.notificaciones.base import pasos_operacion

    cfg = cargar_configuracion()
    pasos = pasos_operacion(_senal())
    ultimo = pasos[-1].lower()
    if cfg.riesgo.cerrar_intradia:
        assert "aviso" in ultimo and ("21:50" in ultimo or "cerrarla" in ultimo)
        assert "no hay que vigilar nada más" not in ultimo
    else:
        assert "no hay que vigilar" in ultimo


def test_los_pasos_cubren_todas_las_ordenes_del_aviso():
    from oro.notificaciones.base import pasos_operacion, _trailing

    sig = _senal()
    texto = " ".join(pasos_operacion(sig))
    assert f"{sig.stop_loss:.2f}" in texto, "los pasos no dicen dónde poner el stop"
    assert f"{sig.take_profits[0].precio:.2f}" in texto, "los pasos no dicen dónde poner el TP"
    assert f"{_trailing(sig)[0]:.2f}" in texto, "los pasos no dicen la distancia del trailing"
    assert "COMPRA" in texto or "VENTA" in texto, "los pasos no dicen en qué dirección"


def test_los_motivos_se_entienden_sin_saber_de_mercado():
    # Los motivos van al correo tal cual. Escritos solo en jerga, quien no conoce
    # el mercado no entiende por qué se le manda la señal.
    import warnings; warnings.filterwarnings("ignore")
    from oro.datos.sintetico import ProveedorSintetico
    from oro.dominio import MarketSnapshot, sesion_de
    from oro.indicadores import atr as _atr
    from oro.senales import MotorSenales

    cfg = cargar_configuracion()
    df = ProveedorSintetico(semilla=3).historico(900)
    motor = MotorSenales(cfg)
    motivos = []
    for i in range(600, 900, 7):
        a = float(_atr(df.iloc[: i + 1], 14).iloc[-1])
        if a <= 0:
            continue
        mom = df.index[i].to_pydatetime()
        snap = MarketSnapshot(momento=mom, precio=float(df["close"].iloc[i]),
                              spread=0.2, atr=a, sesion=sesion_de(mom))
        res = motor.analizar(df.iloc[max(0, i - 400): i + 1], snap)
        if res.hay_operacion:
            motivos = res.signal.motivos_entrada
            break
    assert motivos, "no se generó ninguna señal en la muestra"
    for m in motivos:
        # Cada motivo debe ser una frase, no una etiqueta técnica suelta.
        assert len(m.split()) >= 6, f"motivo demasiado telegráfico: {m!r}"
    crudos = ("OB/FVG", "zona institucional", "Momentum (MACD/DI) a favor",
              "lado correcto del VWAP", "Barrido de liquidez a favor.")
    for m in motivos:
        assert m not in crudos, f"motivo en jerga sin traducir: {m!r}"
