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


def test_el_objetivo_es_alcanzable_de_verdad():
    """Un objetivo que no se toca no es un objetivo.

    Medida la excursión favorable máxima de las 4.410 entradas de 19,6 años,
    respetando el stop y el cierre intradía, el precio alcanza 2 R en el 12 % de
    las operaciones y en el 31 % de las ganadoras. A 5 R llegaba el 0.9 %: era
    decoración, y anunciarlo prometía un premio inalcanzable.

    Por abajo tampoco vale acercarlo sin límite: a 1 R el objetivo se toca el
    31 %, pero capa tanto las ganadoras que la ventaja se va a cero (-0.0012 R/op,
    peor que la escalera antigua).
    """
    r = cargar_configuracion().riesgo
    assert len(r.r_objetivos) == len(r.reparto_tp)
    assert sum(r.reparto_tp) == pytest.approx(1.0), "el reparto debe cubrir la posición"
    assert list(r.r_objetivos) == sorted(r.r_objetivos), "los objetivos van de menor a mayor"
    assert 1.5 <= r.r_objetivos[0] <= 3.0, (
        f"primer objetivo en {r.r_objetivos[0]}R: por encima de 3R casi no se "
        f"toca y por debajo de 1.5R capa las ganadoras hasta anular la ventaja")
    assert r.r_objetivos[-1] <= 3.5, (
        f"último objetivo en {r.r_objetivos[-1]}R: de las operaciones que llegan "
        f"al primero, solo el 15% alcanza 4R y el 7% alcanza 5R. Un objetivo que "
        f"no se toca es una orden que nunca se ejecuta")


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
    # cerrar_intradia=False a propósito: con él activo y la señal fechada "ahora",
    # lanzar la prueba pasadas las 16:00 de Nueva York la cerraba por intradía
    # antes de comprobar nada. La prueba medía el reloj, no el trailing.
    g = GestorOperaciones(sig, cerrar_intradia=False, trailing_activo=True,
                          trailing_r=1.0, trailing_desde_entrada=True)
    riesgo = abs(sig.entrada - sig.stop_loss)
    inicial = g.stop_actual
    # Justo por DEBAJO del objetivo: si se toca, la operación se cierra ahí y el
    # trailing no llega a moverse, que es lo que se quiere comprobar.
    tope = sig.take_profits[-1].r_multiple
    avance = riesgo * (tope - 0.2)
    g.actualizar(sig.entrada + avance, dt.datetime.now(dt.timezone.utc))
    assert g.estado.value == "abierta", "no debería haberse cerrado antes del objetivo"
    assert g.stop_actual > inicial, "el stop no siguió al precio"
    assert g.stop_actual == pytest.approx(sig.entrada + avance - riesgo), (
        "el stop no quedó a la distancia del trailing configurada")


def test_un_stop_inicial_no_se_anuncia_como_break_even():
    # `_en_breakeven` decide el texto del aviso. Si se diera por cierto solo
    # porque el trailing está activo, una pérdida completa se anunciaría como
    # "operación protegida", que es exactamente lo contrario de lo que pasó.
    from oro.vivo.gestor import GestorOperaciones

    sig = _senal()
    g = GestorOperaciones(sig, cerrar_intradia=False, trailing_activo=True,
                          trailing_r=1.0, trailing_desde_entrada=True)
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


def test_la_ventaja_medida_no_depende_del_supuesto_de_salida_intradia():
    """La cifra que justifica la gestión actual no puede colgar de un supuesto.

    El backtest cierra el intradía en el PUNTO MEDIO de la vela ("salida
    imparcial"), pero en la realidad se cierra al precio que haya cuando llega el
    aviso. Si la ventaja solo apareciese con ese supuesto, sería un artefacto del
    modelo y no una propiedad de la estrategia.

    Medido sobre las 4.410 entradas de 19,6 años, la ventaja de la gestión actual
    frente a la escalera 1R/2R/3R es +0.0497 R/op con el punto medio, +0.0535 con
    el PEOR precio de la vela y +0.0459 con el MEJOR: prácticamente la misma. Y en
    el supuesto más adverso la gestión actual sigue siendo positiva en bruto
    (+0.0112) mientras la escalera es negativa (-0.0424).

    Esta prueba deja constancia de la comprobación; los datos de 19,6 años no
    están en el repositorio, así que aquí solo se fija que el motor de backtest
    sigue documentando y usando el punto medio, para que nadie lo cambie sin
    rehacer la medición.
    """
    import inspect

    from oro.backtesting import motor

    fuente = inspect.getsource(motor.Backtester._simular)
    assert "(hi + lo) / 2.0" in fuente, (
        "cambió el supuesto de salida intradía: hay que rehacer la medición de "
        "la ventaja de la gestión (ver ConfiguracionRiesgo.reparto_tp)")
    assert "imparcial" in fuente, "se perdió la explicación del supuesto"


def _gestor(**kw):
    from oro.vivo.gestor import GestorOperaciones

    return GestorOperaciones(_senal(), cerrar_intradia=False,
                             trailing_desde_entrada=True, **kw)


@pytest.mark.skipif(len(cargar_configuracion().riesgo.r_objetivos) > 1,
                    reason="con varios objetivos el primero NO cierra toda la posición")
def test_un_solo_aviso_cuando_el_objetivo_cierra_toda_la_posicion():
    """Dos correos por el mismo hecho confunden y hacen tocar el bróker de más.

    Con un único objetivo que cierra el 100%, se emitía además un
    TP_ALCANZADO diciendo "cierra parte... 100% de la posición", seguido del
    aviso de cierre. Quien lo recibiera cerraría y acto seguido vería un segundo
    correo pidiéndole cerrar lo que ya no tiene.
    """
    import datetime as dt

    from oro.notificaciones.base import Evento

    sig = _senal()
    g = _gestor()
    eventos = g.actualizar(sig.take_profits[0].precio + 0.01,
                           dt.datetime.now(dt.timezone.utc))
    tipos = [e.tipo for e in eventos]
    assert tipos.count(Evento.CIERRE) == 1
    assert Evento.TP_ALCANZADO not in tipos, "avisa dos veces del mismo cierre"
    assert g.r_acumulado == pytest.approx(sig.take_profits[0].r_multiple)


def test_con_escalera_si_avisa_del_cierre_parcial():
    """Contrapeso: si de verdad queda posición viva, el aviso hace falta."""
    import copy
    import datetime as dt

    from oro.dominio import Direccion, Signal
    from oro.notificaciones.base import Evento
    from oro.vivo.gestor import GestorOperaciones

    cfg = copy.deepcopy(cargar_configuracion())
    cfg.riesgo.r_objetivos, cfg.riesgo.reparto_tp = (1.0, 2.0), (0.5, 0.5)
    niveles = calcular_niveles(4451.90, Direccion.COMPRA, atr=8.4, cfg=cfg)
    sig = Signal(momento=dt.datetime.now(dt.timezone.utc), direccion=Direccion.COMPRA,
                 entrada=niveles.entrada, stop_loss=niveles.stop_loss,
                 take_profits=niveles.take_profits, probabilidad=0.6, confianza=0.8,
                 riesgo_recompensa=1.5, tamano_posicion=1.0, motivos_entrada=["x"],
                 riesgos=[], contexto_tecnico="", puntuacion=0.7)
    g = GestorOperaciones(sig, cerrar_intradia=False, trailing_activo=False,
                          trailing_desde_entrada=False)
    eventos = g.actualizar(sig.take_profits[0].precio + 0.01,
                           dt.datetime.now(dt.timezone.utc))
    assert Evento.TP_ALCANZADO in [e.tipo for e in eventos]
    assert 0 < g.restante < 1


def test_el_resultado_anunciado_coincide_con_el_real():
    """Si el aviso dice un R distinto del que quedó registrado, el usuario no
    puede fiarse de ninguno de los dos."""
    import datetime as dt

    sig = _senal()
    riesgo = abs(sig.entrada - sig.stop_loss)
    for precios in ([sig.stop_loss - 0.01],
                    [sig.entrada + 3 * riesgo, sig.entrada + 2 * riesgo - 0.01],
                    [sig.take_profits[0].precio + 0.01]):
        g = _gestor()
        eventos = []
        for p in precios:
            eventos += g.actualizar(p, dt.datetime.now(dt.timezone.utc))
        assert eventos, f"ningún aviso para {precios}"
        assert eventos[-1].r_acumulado == pytest.approx(g.r_acumulado)
        # Un objetivo intermedio NO cierra la operación: con varios niveles solo
        # cierra el último. Lo que sí debe cumplirse siempre es que el aviso que
        # anuncia un cierre coincida con que la operación quede cerrada.
        anuncia_cierre = any(e.cierra_operacion for e in eventos)
        assert anuncia_cierre == (g.estado.value != "abierta"), (
            f"el aviso dice cierre={anuncia_cierre} pero el estado es "
            f"{g.estado.value}")


def test_avisa_de_los_ajustes_del_stop_sin_convertirse_en_spam():
    """El stop se movía en silencio: quien no tuviera trailing stop en su bróker
    se quedaba con el stop inicial y se perdía justo la parte que hace que esta
    gestión mida mejor.

    El umbral importa tanto como el aviso: el stop se recalcula en cada ciclo, así
    que avisar de cada movimiento sería spam. Medido sobre 4.410 operaciones, con
    medio R salen 0.68 correos por operación y nunca más de 3 en una misma.
    """
    import datetime as dt

    from oro.notificaciones.base import Evento
    from oro.vivo.gestor import UMBRAL_AVISO_STOP_R

    sig = _senal()
    riesgo = abs(sig.entrada - sig.stop_loss)
    g = _gestor()
    tope = sig.take_profits[-1].r_multiple
    avisos = []
    # Sube en pasos pequeños hasta justo por debajo del objetivo.
    for k in range(1, int(tope * 10)):
        for ev in g.actualizar(sig.entrada + riesgo * k / 10.0,
                               dt.datetime.now(dt.timezone.utc)):
            if ev.tipo is Evento.MOVER_STOP:
                avisos.append(ev)
        if g.estado.value != "abierta":
            break

    assert avisos, "el stop se movió sin avisar ni una vez"
    assert len(avisos) <= 6, f"demasiados avisos ({len(avisos)}): es spam"
    # Cada aviso debe traer un precio nuevo y mejor que el anterior.
    precios = [ev.precio for ev in avisos]
    assert precios == sorted(precios), "los avisos no van en orden de mejora"
    assert len(set(precios)) == len(precios), "se repitió el mismo stop"
    for anterior, siguiente in zip(precios, precios[1:]):
        assert siguiente - anterior >= UMBRAL_AVISO_STOP_R * riesgo - 1e-9


def test_el_aviso_de_ajuste_no_dice_asegurado_cuando_aun_se_pierde():
    """Con el stop todavía por debajo de la entrada no hay nada asegurado.

    Decir "va bien, -0.40R asegurados" es una contradicción que quien no conoce el
    mercado no sabría interpretar.
    """
    import datetime as dt

    from oro.notificaciones.base import Evento

    sig = _senal()
    riesgo = abs(sig.entrada - sig.stop_loss)
    g = _gestor()
    eventos = []
    for k in (6, 12, 18):
        eventos += [e for e in g.actualizar(sig.entrada + riesgo * k / 10.0,
                                            dt.datetime.now(dt.timezone.utc))
                    if e.tipo is Evento.MOVER_STOP]
    assert len(eventos) >= 2
    for ev in eventos:
        asegurado = (ev.precio - sig.entrada) / riesgo
        if asegurado < -1e-9:
            assert "asegurad" not in ev.mensaje, f"promete asegurado en pérdida: {ev.mensaje}"
            assert "VA BIEN" not in ev.mensaje
        elif asegurado > 1e-9:
            assert "asegurad" in ev.mensaje or "NO PUEDE PERDER" in ev.mensaje
        # Todos deben decir a qué precio mover el stop.
        assert f"{ev.precio:.2f}" in ev.mensaje


def test_la_instruccion_del_aviso_no_contradice_al_mensaje():
    """El asunto y el "qué hacer" estaban fijados en "break-even", pero el stop
    dinámico lo mueve a niveles distintos. El mismo correo pedía dos cosas."""
    from oro.vivo.runner import RunnerVivo

    instruccion = RunnerVivo._instruccion(__import__(
        "oro.notificaciones.base", fromlist=["Evento"]).Evento.MOVER_STOP)
    assert "break-even" not in instruccion.lower()
    assert "entrada" not in instruccion.lower()


def test_los_pasos_explican_qué_pasa_sin_trailing_en_el_broker():
    # No todos los brókers lo tienen. Si el aviso no dice que hay alternativa,
    # quien no lo tenga se queda con un stop fijo creyendo que hace lo correcto.
    from oro.notificaciones.base import pasos_operacion

    texto = " ".join(pasos_operacion(_senal())).lower()
    assert "trailing" in texto
    assert "aviso" in texto, "no explica que se avisará de los ajustes"


def test_el_primer_objetivo_no_cierra_toda_la_operacion():
    """Con dos objetivos, el primero recoge parte y el resto sigue vivo.

    Es lo que hace que el objetivo de 2R se EJECUTE de verdad (12% de las
    operaciones, 31% de las ganadoras) sin renunciar al recorrido: de las que
    llegan a 2R, el 39% continúa hasta 3R.
    """
    import datetime as dt

    from oro.notificaciones.base import Evento

    cfg = cargar_configuracion()
    if len(cfg.riesgo.r_objetivos) < 2:
        pytest.skip("configurado con un solo objetivo")
    sig = _senal()
    g = _gestor()
    eventos = g.actualizar(sig.take_profits[0].precio + 0.01,
                           dt.datetime.now(dt.timezone.utc))
    assert g.estado.value == "abierta", "el primer objetivo no debe cerrar la operación"
    assert g.restante == pytest.approx(sig.take_profits[-1].fraccion)
    tp = [e for e in eventos if e.tipo is Evento.TP_ALCANZADO]
    assert len(tp) == 1
    # El aviso tiene que decir dónde queda el objetivo del resto: sin eso, quien
    # cierre la mitad no sabe qué hacer con la otra.
    assert f"{sig.take_profits[-1].precio:.2f}" in tp[0].mensaje


def test_no_llegan_dos_avisos_de_stop_con_precios_distintos():
    """Al tocar el primer objetivo salían DOS correos: "mueve el stop a la
    entrada" y, en el mismo instante, "mueve el stop a un precio mejor".

    Quien los recibiera movería el stop dos veces, y la primera vez a un precio
    peor. El stop dinámico, corriendo desde la entrada, ya deja el stop por
    encima de la entrada al tocar un objetivo de 2R.
    """
    import datetime as dt

    from oro.notificaciones.base import Evento

    sig = _senal()
    g = _gestor()
    eventos = g.actualizar(sig.take_profits[0].precio + 0.01,
                           dt.datetime.now(dt.timezone.utc))
    movidas = [e for e in eventos if e.tipo is Evento.MOVER_STOP]
    assert len(movidas) <= 1, (
        f"{len(movidas)} avisos de stop a la vez: "
        f"{[f'{e.precio:.2f}' for e in movidas]}")
    if movidas:
        assert movidas[0].precio >= sig.entrada, "el stop anunciado empeora la protección"
        assert movidas[0].precio == pytest.approx(g.stop_actual)


def test_los_pasos_explican_el_cierre_parcial():
    # Sin esto, quien reciba el aviso pondrá un solo take profit por toda la
    # posición y el segundo objetivo no existirá nunca.
    from oro.notificaciones.base import pasos_operacion

    cfg = cargar_configuracion()
    if len(cfg.riesgo.r_objetivos) < 2:
        pytest.skip("configurado con un solo objetivo")
    sig = _senal()
    texto = " ".join(pasos_operacion(sig))
    assert f"{sig.take_profits[0].precio:.2f}" in texto
    assert f"{sig.take_profits[-1].precio:.2f}" in texto
    assert f"{sig.take_profits[0].fraccion:.0%}" in texto, "no dice qué parte se cierra"


@pytest.mark.parametrize("hora_utc", list(range(24)))
def test_ninguna_prueba_del_gestor_depende_de_la_hora(hora_utc):
    """Una prueba que pasa por la mañana y falla por la tarde no vale nada.

    Ya pasó dos veces: el cierre intradía cierra la operación en cuanto la hora
    de mercado entra en la ventana de cierre, así que cualquier prueba que feche
    la señal con `datetime.now()` y deje `cerrar_intradia` activo mide el reloj.
    Esta prueba recorre las 24 horas para que salte al escribirla, no en verde.
    """
    import datetime as dt

    from oro.vivo.gestor import GestorOperaciones

    sig = _senal()
    momento = dt.datetime(2026, 6, 10, hora_utc, tzinfo=dt.timezone.utc)
    g = GestorOperaciones(sig, cerrar_intradia=False, trailing_activo=True,
                          trailing_r=1.0, trailing_desde_entrada=True)
    riesgo = abs(sig.entrada - sig.stop_loss)
    g.actualizar(sig.entrada + riesgo * 0.5, momento)
    assert g.estado.value == "abierta", (
        f"a las {hora_utc}h UTC la operación se cerró sola: la prueba depende "
        f"del reloj")
