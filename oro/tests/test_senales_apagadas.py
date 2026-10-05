"""El motor de señales intradía va apagado, y apagarlo no puede romper nada más.

POR QUÉ ESTÁ APAGADO
--------------------
Reconstruidas sus 4.891 operaciones sobre 21 años con la configuración de
producción: -0.0314 R bruto (t = -2.43), -0.0899 R neto (t = -6.94), 2 años
positivos de 21, -439.5 R acumulados. A 0.25 % de riesgo, -157 € al año.

Lo que estas pruebas protegen es lo de alrededor: que apagarlo NO apague la
ruptura de sesión —van en el mismo bucle del vigilante— y que una operación ya
abierta se siga gestionando hasta cerrarla. Apagar la entrada no es abandonar
una posición.
"""

from __future__ import annotations

from datetime import datetime, timezone

from oro.config import ConfiguracionSistema, cargar_configuracion
from oro.datos.sintetico import ProveedorSintetico
from oro.vivo import RunnerVivo

_FIN = datetime(2026, 6, 10, 14, 0, tzinfo=timezone.utc)   # 10:00 en Nueva York.


def _runner(activas: bool):
    cfg = cargar_configuracion()
    cfg.senales_activas = activas
    return RunnerVivo(cfg, proveedor=ProveedorSintetico(velas=1200, semilla=7, fin=_FIN),
                      usar_sentimiento=False)


def test_por_defecto_va_apagado():
    """Si esto cambia sin querer, el sistema vuelve a operar un motor que está
    medido en -157 € al año."""
    assert ConfiguracionSistema().senales_activas is False


def test_apagado_no_abre_operaciones_y_dice_por_que():
    r = _runner(False).ciclo()
    assert r.nueva_senal is None
    assert "apagado" in r.motivo_sin_entrada.lower()
    # El motivo tiene que llevar la cifra: dentro de un año nadie se acordará de
    # por qué se apagó, y el log es donde se mira.
    assert "0.09 R" in r.motivo_sin_entrada
    assert "ruptura sigue activo" in r.motivo_sin_entrada


def test_el_interruptor_se_puede_volver_a_encender(monkeypatch):
    monkeypatch.setenv("ORO_SENALES_ACTIVAS", "1")
    assert cargar_configuracion().senales_activas is True
    monkeypatch.setenv("ORO_SENALES_ACTIVAS", "0")
    assert cargar_configuracion().senales_activas is False


def test_una_variable_vacia_deja_el_motor_apagado(monkeypatch):
    """Una Variable de Actions sin definir llega VACÍA, no ausente. Si eso
    encendiera el motor, el interruptor no serviría de nada en producción —que
    es exactamente el fallo que tumbó el vigilante en septiembre."""
    monkeypatch.setenv("ORO_SENALES_ACTIVAS", "")
    assert cargar_configuracion().senales_activas is False


def test_apagar_las_senales_no_apaga_la_ruptura():
    """Van en el mismo bucle del vigilante. Si apagar una apagara la otra, el
    sistema se quedaría sin su única estrategia con ventaja."""
    cfg = cargar_configuracion()
    cfg.senales_activas = False
    assert cfg.ruptura.activa is True
    assert cfg.ruptura.solo_ventas is True


def test_una_operacion_abierta_se_sigue_gestionando_con_el_motor_apagado():
    """Apagar la ENTRADA no puede dejar huérfana una posición ya abierta: habría
    que cerrarla a mano sin que el sistema avise."""
    import inspect

    from oro.vivo import runner as modulo

    fuente = inspect.getsource(modulo.RunnerVivo.ciclo)
    corte = fuente.find("self.cfg.senales_activas")
    assert corte > 0, "la compuerta ha desaparecido"
    # La gestión de las abiertas tiene que ocurrir ANTES de la compuerta.
    gestion = fuente.find("self.abiertas")
    assert 0 < gestion < corte, (
        "la compuerta de entrada está por delante de la gestión de las "
        "operaciones abiertas: una posición viva se quedaría sin cerrar")
