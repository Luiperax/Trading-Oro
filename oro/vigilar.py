"""Ventana de vigilancia dentro de UNA sola ejecución (para GitHub Actions).

GitHub solo arranca la tarea programada cada 1–2 h (limita las tareas gratuitas),
así que una revisión de un único disparo puede tardar horas en detectar una
salida. Esta orden mantiene el vigilante VIVO una ventana acotada (por defecto
~50 min) revisando el mercado cada pocos minutos con el PRECIO EN VIVO y
guardando el estado tras cada ciclo. Así:

* las SALIDAS (stop, objetivo, cierre intradía) se detectan y avisan en minutos,
  no a la hora siguiente;
* si la máquina termina, el estado ya está guardado en disco (no se pierde nada);
* como este repositorio es público, los minutos de Actions son gratis: se puede
  encadenar una ventana tras otra para una cobertura casi continua.

    python -m oro.vigilar

Variables de entorno:
    ORO_BUCLE_MINUTOS   duración de la ventana en minutos (por defecto 50).
    ORO_BUCLE_CADA_SEG  segundos entre revisiones (por defecto 180 = 3 min).
    ORO_ESTADO          ruta del fichero de estado (por defecto oro_estado.json).
    (más las de oro/config.py y los canales de aviso ORO_SMTP_* / ORO_TELEGRAM_*)
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone

from .alerta import _cargar_modelo, _probar
from .cli import _construir_notificador
from .config import cargar_configuracion
from .datos import ProveedorYahoo
from .vivo import RunnerVivo


def _num_env(nombre: str, defecto: float) -> float:
    """Lee un número del entorno tolerando el vacío.

    OJO: en GitHub Actions, una Variable no definida llega como cadena VACÍA
    (no ausente), así que ``os.getenv(nombre, defecto)`` devolvería "" y
    ``float("")`` reventaría. Aquí, vacío o inválido -> valor por defecto.
    """
    bruto = os.getenv(nombre, "")
    try:
        return float(bruto) if bruto.strip() else defecto
    except ValueError:
        return defecto


def _guardar_en_repo(ruta: str) -> bool:
    """Sube el estado AHORA (ver oro/persistencia: a prueba de conflictos)."""
    from .persistencia import guardar_en_repo
    return guardar_en_repo(ruta)


def _toca_relevo(cfg) -> bool:
    """¿Hay que ceder el turno al trabajo de CIERRE de sesión?

    El vigilante (ventana de ~50 min) y el cierre corren en máquinas distintas,
    cada una con SU copia del estado. Si se solapan, los dos gestionan la MISMA
    operación: la cierran por duplicado —dos correos y dos registros— y el push
    del vigilante puede pisar el estado del cierre.

    Se decide con la hora LOCAL del usuario, no en UTC, porque el mercado del oro
    cierra siempre a las 23:00 de Madrid pero eso son las 21:00 UTC en verano y
    las 22:00 en invierno. El vigilante se aparta desde las 21:30 locales (antes
    del aviso de cierre de las 21:50) y vuelve pasada la medianoche, cuando ya
    ha abierto la sesión siguiente.
    """
    from datetime import datetime, timezone

    from .tiempo import a_local

    local = a_local(datetime.now(timezone.utc))
    if local.hour == 21:
        return local.minute >= 30
    return local.hour in (22, 23)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--probar" in argv:
        return _probar()

    minutos = _num_env("ORO_BUCLE_MINUTOS", 50.0)
    cada = max(30.0, _num_env("ORO_BUCLE_CADA_SEG", 180.0))

    cfg = cargar_configuracion()
    modelo = _cargar_modelo(cfg)
    runner = RunnerVivo(
        cfg,
        proveedor=ProveedorYahoo(timeframe=cfg.timeframe),
        notificador=_construir_notificador(),
        modelo=modelo,
    )
    if modelo is not None:
        print("Modelo aprendido cargado: la confianza usa el modelo validado.")

    ruta = os.getenv("ORO_ESTADO", "oro_estado.json")
    runner.cargar_estado(ruta)

    print(f"▶ Vigilancia iniciada: ventana {minutos:.0f} min, revisión cada "
          f"{cada:.0f}s, cierre intradía {cfg.riesgo.hora_cierre_utc}:00 UTC.")
    fin = time.monotonic() + minutos * 60.0
    n = 0
    while True:
        n += 1
        try:
            r = runner.ciclo()
            # Guardar tras CADA ciclo: si la máquina termina, no se pierde estado.
            runner.guardar_estado(ruta)
            print(f"[{datetime.now(timezone.utc):%H:%M:%S}] ciclo {n} | "
                  f"oro={r.precio:.2f} | abiertas={r.abiertas} "
                  f"señales_hoy={r.senales_hoy}/{cfg.riesgo.operaciones_max_dia}")
            if r.nueva_senal:
                print("  → NUEVA ENTRADA:", r.nueva_senal.resumen())
            for ev in r.eventos_salida:
                print("  → SALIDA:", ev)
            # Novedad = hay que asegurarla YA. Si esta máquina muere, la próxima
            # ejecución debe encontrar la operación abierta para poder cerrarla.
            if r.nueva_senal or r.eventos_salida:
                if _guardar_en_repo(ruta):
                    print("  ✔ estado guardado en el repositorio (a salvo).")
        except Exception as e:  # noqa: BLE001 — el bucle no debe caerse por un fallo puntual.
            print("  ! error en el ciclo:", type(e).__name__, str(e)[:100])

        if time.monotonic() >= fin or _toca_relevo(cfg):
            break
        time.sleep(cada)

    print(f"■ Ventana de vigilancia completada ({n} ciclos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
