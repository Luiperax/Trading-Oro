"""El aviso para SUBIR el objetivo cuando el precio se acerca sin llegar.

La idea que lo motiva: el objetivo está puesto en el bróker como red de
seguridad, para cuando no se puede estar pendiente. Si el precio se acerca y da
tiempo a leer el correo, se sube y la operación tiene más recorrido; si no da
tiempo, el objetivo original se ejecuta igual. Por eso el aviso no tiene
contrapartida: nunca deja al usuario peor que sin él.

Medido sobre las 4.410 entradas de 19,6 años, estando ya en el disparador de
1.5R la esperanza es 1.574 R quedándose en el objetivo de 2R y 1.621 R ampliando
a 3R: ampliar sale a cuenta pese a renunciar a la salida segura, porque el stop
dinámico ya protege buena parte de lo ganado.

El disparo va en 1.5R por TIEMPO, no por rentabilidad: desde ahí el precio llega
a 2R en la misma vela el 54 % de las veces; desde 1.8R, el 78 %. Cuanto más
arriba se dispare, menos margen hay para reaccionar.
"""

from __future__ import annotations

import datetime as dt

import pytest

from oro.config import cargar_configuracion
from oro.dominio import Direccion, Signal
from oro.notificaciones.base import Evento
from oro.riesgo import calcular_niveles
from oro.vivo.gestor import GestorOperaciones


def _partes():
    cfg = cargar_configuracion()
    n = calcular_niveles(4451.90, Direccion.COMPRA, atr=8.4, cfg=cfg)
    sig = Signal(momento=dt.datetime.now(dt.timezone.utc), direccion=Direccion.COMPRA,
                 entrada=n.entrada, stop_loss=n.stop_loss, take_profits=n.take_profits,
                 probabilidad=0.6, confianza=0.8, riesgo_recompensa=n.riesgo_recompensa,
                 tamano_posicion=1.0, motivos_entrada=["x"], riesgos=[],
                 contexto_tecnico="", puntuacion=0.7)
    r = cfg.riesgo
    g = GestorOperaciones(sig, cerrar_intradia=False, trailing_activo=True,
                          trailing_r=r.trailing_r, trailing_desde_entrada=True,
                          r_ampliacion_objetivo=r.r_ampliacion_objetivo,
                          r_disparo_ampliacion=r.r_disparo_ampliacion)
    return cfg, sig, g, abs(sig.entrada - sig.stop_loss)


def _ampliaciones(g, sig, riesgo, hasta):
    salida = []
    for k in range(1, int(hasta * 20) + 1):
        for ev in g.actualizar(sig.entrada + riesgo * k / 20.0,
                               dt.datetime.now(dt.timezone.utc)):
            if ev.tipo is Evento.AMPLIAR_OBJETIVO:
                salida.append(ev)
        if g.estado.value != "abierta":
            break
    return salida


def test_el_disparo_deja_margen_antes_del_objetivo():
    # Si se dispara pegado al objetivo no da tiempo a mover nada: el 78% de las
    # veces el precio recorre de 1.8R a 2R dentro de la misma vela.
    r = cargar_configuracion().riesgo
    if r.r_disparo_ampliacion <= 0:
        pytest.skip("ampliación desactivada")
    assert r.r_disparo_ampliacion < r.r_objetivos[0], "el disparo debe ir ANTES del objetivo"
    margen = r.r_objetivos[0] - r.r_disparo_ampliacion
    assert margen >= 0.4, f"solo {margen:.2f}R de margen: no da tiempo a reaccionar"
    assert r.r_ampliacion_objetivo > r.r_objetivos[-1], "la ampliación debe ir más lejos"


def test_avisa_una_sola_vez_y_con_el_precio_correcto():
    cfg, sig, g, riesgo = _partes()
    avisos = _ampliaciones(g, sig, riesgo, sig.take_profits[0].r_multiple - 0.05)
    assert len(avisos) == 1, f"{len(avisos)} avisos de ampliación; debe ser uno"
    ev = avisos[0]
    esperado = sig.entrada + riesgo * cfg.riesgo.r_ampliacion_objetivo
    assert ev.precio == pytest.approx(esperado)
    assert f"{esperado:.2f}" in ev.mensaje, "no dice a qué precio subirlo"
    assert f"{sig.take_profits[0].precio:.2f}" in ev.mensaje, "no dice cuál es el objetivo actual"


def test_deja_claro_que_es_opcional():
    # Es lo que hace que el aviso no tenga contrapartida. Si se leyera como una
    # orden, quien no llegue a tiempo creería haber hecho algo mal.
    _, sig, g, riesgo = _partes()
    ev = _ampliaciones(g, sig, riesgo, sig.take_profits[0].r_multiple - 0.05)[0]
    assert "si no llegas a tiempo" in ev.mensaje.lower()
    assert "no pasa nada" in ev.mensaje.lower()


def test_no_avisa_si_el_objetivo_ya_se_alcanzo():
    # Proponer subir un objetivo ya ejecutado haría tocar el bróker sin motivo.
    _, sig, g, _ = _partes()
    eventos = g.actualizar(sig.take_profits[0].precio + 0.01,
                           dt.datetime.now(dt.timezone.utc))
    assert not [e for e in eventos if e.tipo is Evento.AMPLIAR_OBJETIVO]


def test_no_repite_el_aviso_al_reiniciar_el_proceso():
    # GitHub Actions arranca el proceso de cero en cada ejecución: si el estado no
    # recordase que ya se avisó, llegaría el mismo correo cada 15 minutos.
    _, sig, g, riesgo = _partes()
    assert _ampliaciones(g, sig, riesgo, 1.7)
    revivido = GestorOperaciones.desde_dict(g.a_dict())
    repetidos = [e for e in revivido.actualizar(sig.entrada + riesgo * 1.8,
                                                dt.datetime.now(dt.timezone.utc))
                 if e.tipo is Evento.AMPLIAR_OBJETIVO]
    assert not repetidos, "el aviso se repite tras reiniciar el proceso"


def test_la_tarjeta_no_lo_presenta_como_una_salida():
    """Sin maqueta propia caía en la rama del cierre: mostraba "Salida" y
    "Resultado total" en un aviso donde no se vende nada."""
    from oro.datos.sintetico import ProveedorSintetico
    from oro.vivo.runner import RunnerVivo

    cfg, sig, g, riesgo = _partes()
    capturado = []

    class _Falso:
        entrega = True

        def enviar(self, titulo, cuerpo, evento=None, datos=None, html=None):
            capturado.append((titulo, html))
            return True

    runner = RunnerVivo(cfg, ProveedorSintetico(semilla=1), _Falso())
    for ev in _ampliaciones(g, sig, riesgo, 1.7):
        runner._notificar_evento(ev, g)

    assert capturado, "no se envió el aviso"
    titulo, html = capturado[-1]
    assert "SUBE EL OBJETIVO" in titulo
    assert ">Salida<" not in html, "no se sale de nada al subir el objetivo"
    assert "Resultado total" not in html, "la operación sigue abierta"
    assert "Súbelo a" in html and "Objetivo ahora" in html
    assert "+0.00" not in html, "la cifra grande debe ser el objetivo, no lo realizado"


def test_los_pasos_avisan_de_que_llegara_la_propuesta():
    from oro.notificaciones.base import pasos_operacion

    cfg, sig, _, riesgo = _partes()
    if cfg.riesgo.r_ampliacion_objetivo <= cfg.riesgo.r_objetivos[-1]:
        pytest.skip("ampliación desactivada")
    texto = " ".join(pasos_operacion(sig))
    destino = sig.entrada + riesgo * cfg.riesgo.r_ampliacion_objetivo
    assert f"{destino:.2f}" in texto, "los pasos no anuncian a dónde se propondrá subirlo"
    assert "opcional" in texto.lower()
