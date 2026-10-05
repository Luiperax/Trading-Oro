"""La estrategia que va puesta: una sola orden, a la baja, y anulada si sube.

POR QUÉ ESTAS PRUEBAS SON LAS IMPORTANTES
-----------------------------------------
Medido sobre 21 años con el código de producción (`python -m oro.historico`):

    población de días                        n      R/op       t   años +
    rompe abajo primero (se opera)        2131   +0.1143    4.37    17/21
    rompe arriba y LUEGO abajo (se anula)  869   -0.2863   -8.73     2/21
    las dos juntas                        2986   -0.0075   -0.35    10/21

O sea: si la orden de venta se queda puesta cuando el rango se rompe al alza,
la ventaja de la estrategia no baja, DESAPARECE. La anulación no es un
refinamiento, es la estrategia. De ahí que esto se pruebe y no se confíe.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from oro.config import ConfiguracionSistema
from oro.dominio import Direccion
from oro.seguimiento import EstadoPlan, registro_de, seguir
from oro.sesiones import construir_plan, direccion_disparada
from oro.tests.test_ruptura_sesion import ASIA_SUBE, LONDRES, _marco

NY = ZoneInfo("America/New_York")
DIA = "2026-07-15"


def _a_las(hora: int, minuto: int = 0) -> datetime:
    return datetime(2026, 7, 15, hora, minuto, tzinfo=NY).astimezone(timezone.utc)


def _plan(**ruptura):
    cfg = ConfiguracionSistema()
    cfg.riesgo.coste_operacion = 0.30
    for k, v in ruptura.items():
        setattr(cfg.ruptura, k, v)
    velas = {**ASIA_SUBE, **LONDRES}
    return construir_plan(_marco(DIA, velas), cfg, ahora=_a_las(8)).plan, cfg


def _con_sesion(sesion: dict):
    return _marco(DIA, {**ASIA_SUBE, **LONDRES, **sesion})


# El rango de LONDRES es 3998.00 - 4024.00, así que 1R = 26.00 $.


def test_la_configuracion_va_con_solo_ventas_puesto():
    """Si esto cambia sin querer, el sistema vuelve a operar un lastre medido."""
    cfg = ConfiguracionSistema()
    assert cfg.ruptura.solo_ventas is True
    assert cfg.ruptura.anular_si_rompe_arriba is True


def test_el_plan_solo_deja_la_orden_de_venta():
    plan, _ = _plan()
    assert plan.solo_ventas is True
    assert [o.direccion for o in plan.ordenes] == [Direccion.VENTA]
    # La compra sigue calculada porque su nivel es la línea de anulación, pero
    # no es una orden que se deje puesta.
    assert plan.compra.entrada == pytest.approx(4024.0)


def test_con_una_sola_orden_no_hay_favorita():
    """La marca «la mejor si salta» solo tiene sentido entre dos órdenes."""
    plan, _ = _plan()
    assert plan.favorita is None
    assert not plan.es_favorita(plan.venta)


def test_romper_abajo_abre_la_venta():
    plan, cfg = _plan()
    df = _con_sesion({8: (4010, 3990)})     # pierde el mínimo del rango.
    s = seguir(plan, df, ahora=_a_las(9))
    assert s.estado is EstadoPlan.ABIERTA
    assert s.direccion is Direccion.VENTA
    assert s.entrada == pytest.approx(3998.0)


def test_romper_arriba_anula_la_venta_en_vez_de_comprar():
    plan, cfg = _plan()
    df = _con_sesion({8: (4035, 4020)})     # supera el máximo del rango.
    s = seguir(plan, df, ahora=_a_las(9))
    assert s.estado is EstadoPlan.ANULADO
    assert s.direccion is None
    assert not s.hubo_operacion


def test_la_anulacion_manda_un_aviso_que_dice_cancelar():
    """El usuario tiene la orden puesta en el bróker: si no se le avisa, se le
    ejecutará más tarde justo en la población que pierde 0,29 R de media."""
    plan, _ = _plan()
    df = _con_sesion({8: (4035, 4020)})
    s = seguir(plan, df, ahora=_a_las(9))
    assert len(s.avisos) == 1
    aviso = s.avisos[0]
    assert aviso.clave == f"{plan.dia}:anulado"
    assert "CANCELA" in aviso.titulo
    assert "venta" in aviso.titulo
    assert "4024.00" in aviso.cuerpo        # el nivel que la anula.
    assert "no se opera" in aviso.cuerpo.lower()


def test_el_aviso_de_anulacion_no_se_repite():
    plan, _ = _plan()
    df = _con_sesion({8: (4035, 4020)})
    s = seguir(plan, df, ahora=_a_las(9), avisados={f"{plan.dia}:anulado"})
    assert s.estado is EstadoPlan.ANULADO
    assert s.avisos == []


def test_romper_arriba_y_luego_abajo_sigue_anulado():
    """LA PRUEBA QUE SOSTIENE LA ESTRATEGIA.

    Es la población de 869 días que da -0.2863 R/op (t = -8.73) y solo 2 años
    positivos de 21. Si esto devolviera una operación, el sistema volvería a
    tener una ventaja de cero.
    """
    plan, cfg = _plan()
    df = _con_sesion({8: (4035, 4020),      # primero rompe arriba…
                      9: (4030, 3980),      # …y luego se desploma bajo el rango.
                      10: (3985, 3960)})
    s = seguir(plan, df, ahora=_a_las(17))
    assert s.estado is EstadoPlan.ANULADO
    assert s.direccion is None
    ficha = registro_de(plan, s, cfg.riesgo.coste_operacion)
    # Y no deja un resultado falso en el registro de aprendizaje.
    assert ficha["r_neto"] is None
    assert ficha["estado"] == "anulado"


def test_sin_anulacion_la_venta_tardia_si_entra():
    """El interruptor existe, y apagándolo se recupera el comportamiento viejo.
    Sirve para poder volver a medir la diferencia sin tocar código."""
    plan, _ = _plan(anular_si_rompe_arriba=False)
    df = _con_sesion({8: (4035, 4020), 9: (4030, 3980)})
    s = seguir(plan, df, ahora=_a_las(17))
    assert s.estado is not EstadoPlan.ANULADO


def test_los_dos_lados_en_la_misma_vela_siguen_siendo_ambiguos():
    """Dentro de una vela de una hora no se sabe qué pasó primero. Suponerlo
    sería inventar el dato que decide si se opera o no."""
    plan, _ = _plan()
    df = _con_sesion({8: (4035, 3985)})
    s = seguir(plan, df, ahora=_a_las(9))
    assert s.estado is EstadoPlan.AMBIGUA


def test_direccion_disparada_no_devuelve_compra_con_solo_ventas():
    plan, _ = _plan()
    assert direccion_disparada(plan, 4035.0, 4010.0) is None     # rompió arriba.
    assert direccion_disparada(plan, 4020.0, 3990.0) is Direccion.VENTA
    assert direccion_disparada(plan, 4020.0, 4000.0) is None     # dentro del rango.
    assert direccion_disparada(plan, 4035.0, 3985.0) is None     # los dos lados.


def test_el_correo_no_lleva_ninguna_orden_de_compra():
    from oro.notificaciones.plan import mensaje_de_plan, mensaje_html_de_plan

    plan, _ = _plan()
    texto, html = mensaje_de_plan(plan), mensaje_html_de_plan(plan)
    for t in (texto, html):
        assert "BUY STOP" not in t
        assert "SELL STOP" in t
        # Y dice cuándo hay que cancelarla, con el precio.
        assert "4024.00" in t
    assert "LA MEJOR SI SALTA" not in texto
    assert "UNA ORDEN PENDIENTE" in texto


def test_el_correo_da_las_cifras_malas_tambien():
    """Sin el peor año y la peor racha, el correo vende y no informa."""
    from oro.notificaciones.plan import mensaje_de_plan, mensaje_html_de_plan

    plan, _ = _plan()
    for t in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "40 %" in t                       # acierta menos de la mitad.
        assert "peor año" in t and "8,3 R" in t
        assert "23 R" in t                       # la peor racha.
        assert "21" in t                         # los años medidos.


def test_el_asunto_dice_una_orden_y_el_nivel_de_anulacion():
    from oro.notificaciones.base import Evento, Notificador

    plan, _ = _plan()
    capturado = {}

    class Espia(Notificador):
        def enviar(self, titulo, cuerpo, evento=Evento.NUEVA_SENAL, html=None):
            capturado.update(titulo=titulo, evento=evento)
            return True

    assert Espia().notificar_plan(plan) is True
    assert "1 orden" in capturado["titulo"]
    assert "3998.00" in capturado["titulo"]      # la venta.
    assert "4024.00" in capturado["titulo"]      # el nivel que la anula.


def test_el_plan_sobrevive_al_viaje_por_json():
    """EL FALLO QUE ESTO IMPIDE.

    El plan se guarda en `oro_plan.json` y lo recoge otra ejecución 15 minutos
    después. `solo_ventas` vale False por defecto en la clase, así que si no se
    serializa, el plan vuelve del JSON operando compras y sin anular nada: el
    seguimiento haría lo contrario de la estrategia y no daría ningún error.
    """
    from oro.seguir_plan import _rehidratar, serializar

    plan, _ = _plan()
    assert plan.solo_ventas is True

    bruto = serializar(plan)
    assert bruto["solo_ventas"] is True
    assert bruto["anular_si_rompe_arriba"] is True

    from oro.sesiones import PlanRuptura

    vuelta = PlanRuptura(**_rehidratar(bruto))
    assert vuelta.solo_ventas is True
    assert vuelta.anular_si_rompe_arriba is True
    assert [o.direccion for o in vuelta.ordenes] == [Direccion.VENTA]

    # Y el seguimiento del plan rehidratado sigue anulando.
    df = _con_sesion({8: (4035, 4020), 9: (4030, 3980)})
    assert seguir(vuelta, df, ahora=_a_las(17)).estado is EstadoPlan.ANULADO


def test_un_plan_guardado_antes_del_cambio_toma_la_configuracion():
    """Un `oro_plan.json` escrito por la versión anterior no lleva los campos.
    Tomar el defecto de la clase (False) dejaría al seguimiento operando
    compras; hay que tomar la configuración, que es lo que el sistema quiere."""
    from oro.seguir_plan import _rehidratar, serializar
    from oro.sesiones import PlanRuptura

    plan, _ = _plan()
    viejo = serializar(plan)
    del viejo["solo_ventas"]
    del viejo["anular_si_rompe_arriba"]

    vuelta = PlanRuptura(**_rehidratar(viejo))
    assert vuelta.solo_ventas is ConfiguracionSistema().ruptura.solo_ventas is True
    assert vuelta.anular_si_rompe_arriba is True


# ---------------------------------------------------------------------------
# el día completo, por el camino real: plan_sesion -> correo -> seguir_plan
# ---------------------------------------------------------------------------
class _Espia:
    def __init__(self):
        self.planes, self.avisos = [], []

    def notificar_plan(self, plan):
        self.planes.append(plan)
        return True

    def enviar(self, titulo, cuerpo, evento=None, html=None):
        self.avisos.append((titulo, evento))
        return True


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    from oro import plan_sesion, seguir_plan

    monkeypatch.setenv("ORO_PLAN_ESTADO", str(tmp_path / "plan.json"))
    monkeypatch.setenv("ORO_RUTA_RUPTURAS", str(tmp_path / "rupturas.jsonl"))
    monkeypatch.setenv("ORO_COSTE_OPERACION", "0.30")
    espia = _Espia()
    monkeypatch.setattr(plan_sesion, "_construir_notificador", lambda: espia)
    monkeypatch.setattr(seguir_plan, "_construir_notificador", lambda: espia)
    return espia, tmp_path, monkeypatch


def _servir(monkeypatch, df):
    from oro import plan_sesion, seguir_plan

    prov = type("P", (), {"historico": lambda s, n: df})()
    monkeypatch.setattr(plan_sesion, "_proveedor", lambda sintetico: prov)
    monkeypatch.setattr(seguir_plan, "_proveedor", lambda sintetico: prov)


def test_dia_completo_la_venta_salta_llega_a_1r_y_se_cierra(entorno):
    """El camino bueno, de punta a punta y por el código real."""
    from oro import plan_sesion, seguir_plan

    espia, tmp, monkeypatch = entorno
    _servir(monkeypatch, _marco(DIA, {**ASIA_SUBE, **LONDRES}))
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    assert len(espia.planes) == 1
    assert espia.planes[0].solo_ventas is True

    # La tarde: pierde el mínimo, cae 1R y se cierra al final de la sesión.
    _servir(monkeypatch, _con_sesion({8: (4010, 3990), 9: (3995, 3965),
                                      10: (3975, 3960), 15: (3970, 3962)}))
    assert seguir_plan.ejecutar(ahora=_a_las(17)) == 0

    import json

    fichas = [json.loads(l) for l in
              (tmp / "rupturas.jsonl").read_text(encoding="utf-8").splitlines() if l]
    assert len(fichas) == 1
    assert fichas[0]["direccion"] == "venta"
    assert fichas[0]["r_neto"] is not None
    assert fichas[0]["r_neto"] > 0


def test_dia_completo_rompe_al_alza_y_solo_llega_la_cancelacion(entorno):
    """El camino que salva la estrategia, de punta a punta.

    Lo que tiene que pasar: llega el plan, llega UN aviso de cancelar, y en el
    registro queda un día anulado SIN resultado. Si en vez de eso se registrara
    una operación, el sistema estaría operando la población que pierde 0,29 R.
    """
    from oro import plan_sesion, seguir_plan

    espia, tmp, monkeypatch = entorno
    _servir(monkeypatch, _marco(DIA, {**ASIA_SUBE, **LONDRES}))
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0

    # Rompe arriba y LUEGO se desploma por debajo del rango.
    _servir(monkeypatch, _con_sesion({8: (4035, 4020), 9: (4030, 3980),
                                      10: (3985, 3950)}))
    assert seguir_plan.ejecutar(ahora=_a_las(17)) == 0

    assert len(espia.avisos) == 1
    titulo, _ = espia.avisos[0]
    assert "CANCELA" in titulo and "venta" in titulo

    import json

    fichas = [json.loads(l) for l in
              (tmp / "rupturas.jsonl").read_text(encoding="utf-8").splitlines() if l]
    assert len(fichas) == 1
    assert fichas[0]["estado"] == "anulado"
    assert fichas[0]["r_neto"] is None


def test_los_avisos_llevan_tarjeta_y_el_dato_en_grande():
    """El aviso de cancelar es el que sostiene la ventaja y hay que leerlo
    deprisa en el móvil. Iba en texto plano, igual de gris que los demás."""
    import re

    plan, _ = _plan()
    df = _con_sesion({8: (4035, 4020)})
    s = seguir(plan, df, ahora=_a_las(9))
    aviso = s.avisos[0]

    assert aviso.destacado == "ha subido de 4024.00"
    html = aviso.html()
    assert "4024.00" in html
    assert "max-width:460px" in html
    # Rojo en la cabecera: es un aviso de cancelar, no de que algo va bien.
    assert "#F04438" in html
    # Solo tablas y estilos en línea, como el resto de correos.
    assert "<style" not in html and "class=" not in html
    for etiqueta in ("table", "tr", "td", "div"):
        abre = len(re.findall(rf"<{etiqueta}[ >]", html))
        cierra = len(re.findall(rf"</{etiqueta}>", html))
        assert abre == cierra, f"{etiqueta}: {abre} abren y {cierra} cierran"


def test_el_aviso_de_mover_el_stop_va_en_verde_con_el_precio():
    plan, _ = _plan()
    df = _con_sesion({8: (4010, 3990), 9: (3995, 3965)})
    s = seguir(plan, df, ahora=_a_las(11))
    mover = [a for a in s.avisos if a.destacado.startswith("stop →")]
    assert mover, "no se mandó el aviso de break-even"
    html = mover[0].html()
    assert "3998.00" in html          # el precio de entrada.
    assert "#12B76A" in html          # verde: la operación va a favor.


def test_el_correo_del_aviso_se_envia_con_html(entorno):
    """Si se enviara sin html, el canal de correo mandaría solo texto plano y la
    tarjeta no serviría de nada."""
    from oro import plan_sesion, seguir_plan

    espia, tmp, monkeypatch = entorno
    recibido = {}

    def enviar(titulo, cuerpo, evento=None, html=None):
        recibido.update(titulo=titulo, html=html)
        return True

    espia.enviar = enviar
    _servir(monkeypatch, _marco(DIA, {**ASIA_SUBE, **LONDRES}))
    assert plan_sesion.ejecutar(ahora=_a_las(8)) == 0
    _servir(monkeypatch, _con_sesion({8: (4035, 4020)}))
    assert seguir_plan.ejecutar(ahora=_a_las(9)) == 0

    assert "CANCELA" in recibido["titulo"]
    assert recibido["html"] is not None
    assert "4024.00" in recibido["html"]


def test_la_cabecera_roja_lleva_el_texto_en_blanco():
    """Sobre #F04438 el texto oscuro se queda por debajo del contraste legible,
    y este es justo el correo que hay que leer de un vistazo en el móvil."""
    from oro.notificaciones.plan import _ORO, _ROJO, mensaje_html_de_aviso

    def cabecera(color):
        h = mensaje_html_de_aviso("T", "cuerpo", "dato", color)
        return h.split("border-radius:18px 18px 0 0")[1].split("</td></tr>")[0]

    assert "#ffffff" in cabecera(_ROJO)
    assert "#0b0e14" in cabecera(_ORO)      # sobre dorado, al revés.
    assert "#ffffff" not in cabecera(_ORO)


def test_el_correo_dice_de_que_instrumento_salen_los_precios():
    """El fallo más caro posible y el único que el sistema no puede detectar.

    El feed en vivo es GC=F, el FUTURO de COMEX, porque Yahoo no sirve XAU/USD
    al contado en velas horarias. En septiembre de 2026 el futuro cotizó 40,17 $
    por encima del contado. Si el bróker de quien opera cotiza el contado, los
    niveles del correo no existen en su pantalla y la orden se ejecutaría al
    instante en vez de esperar a la ruptura. Desde aquí no se puede saber: el
    sistema solo ve un feed. Así que se dice.
    """
    from oro.notificaciones.plan import (aviso_instrumento, mensaje_de_plan,
                                         mensaje_html_de_plan)

    plan, _ = _plan()
    assert "GC=F" in (aviso_instrumento() or "")
    for texto in (mensaje_de_plan(plan), mensaje_html_de_plan(plan)):
        assert "GC=F" in texto
        assert "CONTADO" in texto or "contado" in texto


def test_sin_desajuste_de_instrumento_el_correo_no_mete_ruido(monkeypatch):
    """Si algún día el feed fuera el contado, el aviso sobra."""
    from oro.notificaciones.plan import aviso_instrumento, mensaje_de_plan

    monkeypatch.setenv("ORO_SIMBOLO_VIVO", "XAUUSD")
    assert aviso_instrumento() is None
    plan, _ = _plan()
    assert "GC=F" not in mensaje_de_plan(plan)


def test_el_proveedor_en_vivo_recibe_el_simbolo_configurado():
    """`ProveedorYahoo` tenía su propio GC=F por defecto y nadie le pasaba el
    símbolo: la configuración decía XAUUSD y el sistema operaba otra cosa."""
    import inspect

    from oro import plan_sesion
    from oro.vivo import runner

    for fuente in (inspect.getsource(plan_sesion._proveedor),
                   inspect.getsource(runner.RunnerVivo.__init__)):
        assert "simbolo_vivo" in fuente, (
            "el proveedor en vivo no recibe el símbolo configurado")
