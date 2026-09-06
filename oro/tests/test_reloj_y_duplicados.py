"""Pruebas de los dos fallos detectados en la auditoría del 24-ago-2026.

1. RELOJ: con datos en vivo, las decisiones de tiempo (cierre intradía) deben
   usar la hora REAL. Antes usaban la marca de la última vela, que se congela
   cuando el mercado cierra -> una operación abierta el viernes seguía abierta
   todo el fin de semana (observado: 07-ago 17:00 -> 09-ago 22:00, 53 h).

2. DUPLICADOS: el vigilante revisa cada pocos minutos; sobre la MISMA vela
   cerrada volvía a emitir la MISMA señal -> operación y aviso duplicados
   (observado: 11 registros para solo 6 setups reales).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from oro.config import cargar_configuracion
from oro.datos import ProveedorSintetico
from oro.dominio import Direccion, EstadoOperacion, Signal, TakeProfit
from oro.sentimiento import AnalizadorSentimiento
from oro.vivo import GestorOperaciones, RunnerVivo


# Hora fija en la que el mercado admite abrir intradía (10:00 en Nueva York).
# Sin fijarla, estas pruebas fallan o pasan según la hora a la que se lancen:
# a partir de las 15:00 de Nueva York el runner contesta "demasiado tarde para
# abrir una operación intradía" y la prueba se cae sin que nada esté roto.
_FIN_FIJO = datetime(2026, 6, 10, 14, 0, tzinfo=timezone.utc)   # 10:00 en Nueva York


def _runner(en_vivo: bool):
    prov = ProveedorSintetico(velas=1200, semilla=7, fin=_FIN_FIJO)
    prov.en_vivo = en_vivo
    return RunnerVivo(
        cargar_configuracion(), proveedor=prov,
        analizador=AnalizadorSentimiento(fuente_titulares=lambda: [],
                                         fuente_eventos=lambda: []),
        usar_sentimiento=False,
    )


def _signal(entrada=2000.0):
    return Signal(momento=datetime(2020, 1, 2, 12, tzinfo=timezone.utc),
                  direccion=Direccion.COMPRA, entrada=entrada, stop_loss=entrada - 10,
                  take_profits=[TakeProfit(entrada + 10, 0.5, 1.0),
                                TakeProfit(entrada + 20, 0.5, 2.0)],
                  probabilidad=0.6, confianza=0.7, riesgo_recompensa=1.5,
                  tamano_posicion=5.0)


# ---------- 1) reloj ----------
def test_reloj_en_vivo_usa_hora_real():
    r = _runner(en_vivo=True)
    vela = r.proveedor.historico(1).index[-1].to_pydatetime()
    ahora = r._reloj(vela)
    assert (datetime.now(timezone.utc) - ahora) < timedelta(seconds=5)


def test_reloj_sintetico_usa_la_vela():
    r = _runner(en_vivo=False)
    vela = r.proveedor.historico(1).index[-1].to_pydatetime()
    assert r._reloj(vela) == vela


def test_en_vivo_cierra_operacion_de_un_dia_anterior():
    """La operación abierta OTRO día se cierra (no aguanta el fin de semana)."""
    r = _runner(en_vivo=True)
    g = GestorOperaciones(_signal(), cerrar_intradia=True, hora_cierre_et=16)
    # Abierta en 2020: con el reloj real (hoy) el día ha cambiado -> debe cerrar.
    r.abiertas.append(g)
    res = r.ciclo()
    assert g.estado is not EstadoOperacion.ABIERTA
    assert res.eventos_salida and "INTRADÍA" in res.eventos_salida[0]
    assert len(r.abiertas) == 0


def test_sin_reloj_real_la_vela_congelada_no_cerraria():
    """Comprobación del fallo original: con la marca de vela, no cerraba."""
    g = GestorOperaciones(_signal(), cerrar_intradia=True, hora_cierre_et=16)
    congelado = g.abierta_en + timedelta(hours=3)   # misma marca "congelada"
    assert not g._debe_cerrar_intradia(congelado)
    # Con el reloj real (día siguiente) sí cierra.
    assert g._debe_cerrar_intradia(g.abierta_en + timedelta(days=1))


# ---------- 2) duplicados ----------
def test_no_repite_senal_en_la_misma_vela():
    r = _runner(en_vivo=False)
    vela = r.proveedor.historico(1).index[-1].to_pydatetime()
    r._ultima_vela_senal = vela           # esa vela ya avisó
    res = r.ciclo()
    assert res.nueva_senal is None
    assert "ya generó" in res.motivo_sin_entrada


def test_una_sola_posicion_simultanea_por_defecto():
    """Dos posiciones a la vez sobre el mismo activo = riesgo duplicado."""
    r = _runner(en_vivo=False)
    assert r.max_concurrentes == 1
    # Sin cierre intradía para que siga abierta al evaluar el tope.
    r.abiertas.append(GestorOperaciones(_signal(), cerrar_intradia=False))
    res = r.ciclo()
    assert res.nueva_senal is None
    assert "simultáneas" in res.motivo_sin_entrada


def test_la_guarda_sobrevive_al_reinicio(tmp_path):
    """Si no persiste, cada arranque duplicaría la última señal."""
    ruta = tmp_path / "estado.json"
    r1 = _runner(en_vivo=False)
    marca = datetime(2026, 8, 19, 4, tzinfo=timezone.utc)
    r1._ultima_vela_senal = marca
    r1.guardar_estado(ruta)

    r2 = _runner(en_vivo=False)
    r2.cargar_estado(ruta)
    assert r2._ultima_vela_senal == marca


# ---------- 3) operación fantasma ----------
class _NotificadorCaido:
    """Simula un canal de aviso que falla (SMTP caído, secreto mal puesto)."""

    def notificar_senal(self, signal):
        return False

    def enviar(self, titulo, cuerpo, evento=None, html=None):
        return False


def test_si_el_aviso_falla_no_se_abre_la_operacion(monkeypatch):
    """Sin aviso entregado el usuario no entra: abrirla crearía una fantasma.

    Una operación fantasma mandaría luego avisos de SALIDA de algo que nunca se
    abrió y falsearía el registro que alimenta el aprendizaje.
    """
    from oro.dominio import Signal as _S

    r = _runner(en_vivo=False)
    r.notificador = _NotificadorCaido()

    # Forzar que el motor encuentre siempre una señal.
    sig = _signal(entrada=2000.0)

    class _Analisis:
        hay_operacion = True
        signal = sig
        motivos_no: list = []
        mensaje = ""

    monkeypatch.setattr(r.motor, "analizar", lambda df, snap: _Analisis())

    res = r.ciclo()
    assert res.nueva_senal is None
    assert len(r.abiertas) == 0
    assert r._senales_hoy == 0
    assert "no se pudo enviar" in res.motivo_sin_entrada
    # No se marca la vela: así se reintenta el mismo aviso en el próximo ciclo.
    assert r._ultima_vela_senal is None


def test_las_pruebas_no_dependen_de_la_hora_a_la_que_se_lancen():
    """Una prueba que pasa por la mañana y falla por la tarde no vale nada.

    El proveedor sintético termina la serie AHORA, así que la última vela cae a
    la hora del reloj. A partir de las 15:00 de Nueva York el runner contesta
    "demasiado tarde para abrir una operación intradía" y varias pruebas se
    caían sin que nada estuviera roto. Se comprueba en las 24 horas del día.
    """
    from oro.dominio.mercado import hora_mercado

    horas_ok = []
    for h in range(24):
        fin = datetime(2026, 6, 10, h, 0, tzinfo=timezone.utc)
        prov = ProveedorSintetico(velas=300, semilla=7, fin=fin)
        ultima = prov.historico(1).index[-1].to_pydatetime()
        assert ultima.hour == h, f"el final fijado no se respeta: {ultima} != {h}h"
        horas_ok.append(hora_mercado(ultima))
    assert len(set(horas_ok)) == 24, "el final fijado no recorre todas las horas"

    # Y la hora elegida para las pruebas del reloj debe permitir abrir.
    cfg = cargar_configuracion()
    h_mercado = hora_mercado(_FIN_FIJO)
    assert not (cfg.riesgo.hora_cierre_et - 1 <= h_mercado < 18), (
        f"_FIN_FIJO cae en la ventana de no-abrir ({h_mercado}h en Nueva York)")
