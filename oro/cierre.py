"""Cierre garantizado de fin de sesión: no dejar nada abierto al cerrar el mercado.

El aviso de "sal de la operación" NO puede depender de que justo a esa hora haya
una ventana de vigilancia viva. Las ventanas duran ~50 min y GitHub las encola y
cancela a su antojo, así que puede no haber ninguna corriendo a las 21:00 UTC —y
entonces la operación se quedaría abierta de un día para otro, que es justo lo
que el modo intradía debe impedir.

Esta orden es un trabajo corto e independiente que se ejecuta poco antes del
cierre del mercado:

1. Carga el estado y hace un ciclo normal (avisa de stop/objetivos si toca).
2. Lo que siga abierto, lo CIERRA y te avisa, con margen para que te dé tiempo
   a cerrarlo en el bróker antes de que el mercado cierre.
3. Guarda y sube el estado inmediatamente.

    python -m oro.cierre            # cierra lo que quede abierto y avisa
    python -m oro.cierre --revisar  # solo informa, sin cerrar nada
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from .alerta import _cargar_modelo
from .cli import _construir_notificador
from .config import cargar_configuracion
from .datos import ProveedorYahoo
from .vigilar import _guardar_en_repo
from .vivo import RunnerVivo


HORA_AVISO_LOCAL = 21        # 21:5x en la hora del usuario, antes del cierre.


def _toca_cerrar(ahora: datetime) -> tuple[bool, str]:
    """¿Estamos en la franja de cierre (21:5x en la hora del usuario)?

    Se mira la hora LOCAL, no la UTC: el mercado del oro cierra siempre a las
    23:00 de Madrid, pero eso son las 21:00 UTC en verano y las 22:00 en
    invierno. Con dos pares de citas (una para cada horario) y esta guarda, el
    aviso cae a las 21:50 locales todo el año, con ~70 min de margen.
    """
    from .tiempo import a_local

    local = a_local(ahora)
    if local.hour != HORA_AVISO_LOCAL or local.minute < 40:
        return False, f"fuera de la franja de cierre (son las {local:%H:%M} en tu hora)."
    return True, ""


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    solo_revisar = "--revisar" in argv

    # Modo programado: solo actúa en la franja de cierre local.
    if "--si-toca" in argv:
        toca, motivo = _toca_cerrar(datetime.now(timezone.utc))
        if not toca:
            print(f"No toca cerrar: {motivo}")
            return 0

    cfg = cargar_configuracion()
    runner = RunnerVivo(
        cfg,
        proveedor=ProveedorYahoo(timeframe=cfg.timeframe),
        notificador=_construir_notificador(),
        modelo=_cargar_modelo(cfg),
    )
    ruta = os.getenv("ORO_ESTADO", "oro_estado.json")
    runner.cargar_estado(ruta)

    abiertas_antes = len(runner.abiertas)
    print(f"Cierre de sesión: {abiertas_antes} operación(es) abierta(s).")

    # 1) Ciclo normal: puede cerrar por stop/objetivo/intradía y avisar.
    try:
        r = runner.ciclo()
        for ev in r.eventos_salida:
            print("  → SALIDA:", ev)
    except Exception as e:  # noqa: BLE001 — aun así hay que intentar cerrar.
        print("  ! error en el ciclo:", type(e).__name__, str(e)[:100])

    # 2) Lo que siga abierto se cierra AHORA (es intradía: no se mantiene).
    if runner.abiertas and not solo_revisar:
        ahora = datetime.now(timezone.utc)
        precio = None
        obtener = getattr(runner.proveedor, "precio_actual", None)
        if callable(obtener):
            precio = obtener()
        if not precio:
            try:
                precio = float(runner.proveedor.historico(1)["close"].iloc[-1])
            except Exception:  # noqa: BLE001
                precio = None

        if precio:
            for gestor in list(runner.abiertas):
                for ev in gestor.cerrar_ahora(
                        precio, ahora,
                        "🚪 CIERRE DE SESIÓN: sal de la operación (intradía)"):
                    runner._notificar_evento(ev, gestor)
                    print("  → CIERRE FORZOSO:", ev.mensaje)
                    runner._registrar_historial({
                        "tipo": ev.tipo.value, "momento": ahora.isoformat(),
                        "precio": round(ev.precio, 2), "mensaje": ev.mensaje,
                        "r": round(ev.r_acumulado, 2)})
                if not gestor.abierta:
                    if gestor.r_acumulado < 0:
                        runner._perdida_r_hoy += abs(gestor.r_acumulado)
                    runner._registrar_operacion(gestor, ahora)
                    runner.abiertas.remove(gestor)
        else:
            print("  ⚠️  sin precio disponible: NO se cierra a ciegas. "
                  "Revisa tus operaciones a mano.")

    runner.guardar_estado(ruta)
    if abiertas_antes:
        _guardar_en_repo(ruta)
    print(f"Quedan {len(runner.abiertas)} operación(es) abierta(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
