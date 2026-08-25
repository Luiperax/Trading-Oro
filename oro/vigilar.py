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
    """Sube el estado a GitHub AHORA, sin esperar al final de la ventana.

    Es crítico para no perder operaciones. El aviso por correo se envía nada más
    detectar la señal, pero el estado solo se subía al terminar la ventana (~50
    min después). Si la máquina moría en ese hueco —GitHub cancela y recicla
    ejecuciones— el correo de ENTRADA ya había salido y la operación se perdía:
    ninguna ejecución posterior sabía que estaba abierta y el aviso de SALIDA no
    llegaba nunca. Guardando en cuanto hay novedad, ese hueco desaparece.

    Devuelve True si se subió algo. Fuera de un repo con remoto (uso local) no
    hace nada y no molesta.
    """
    import subprocess

    def _git(*args) -> subprocess.CompletedProcess:
        return subprocess.run(("git",) + args, capture_output=True, text=True, timeout=60)

    try:
        if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
            return False
        _git("config", "user.name", "oro-alertas-bot")
        _git("config", "user.email", "actions@users.noreply.github.com")
        # Cada fichero por separado: si uno no existe aún, no debe abortar el otro.
        _git("add", "-f", ruta)
        _git("add", "-f", "operaciones_oro.jsonl")
        if _git("diff", "--cached", "--quiet").returncode == 0:
            return False  # nada que guardar
        if _git("commit", "-m", "Estado XAU/USD tras señal [skip ci]").returncode != 0:
            return False
        for _ in range(3):
            if _git("push").returncode == 0:
                return True
            _git("fetch", "origin", "main")
            if _git("rebase", "origin/main").returncode != 0:
                _git("rebase", "--abort")
            time.sleep(2)
        print("  ⚠️  no se pudo subir el estado ahora; se reintenta al cerrar la ventana.")
        return False
    except Exception as e:  # noqa: BLE001 — guardar no debe tumbar el vigilante.
        print("  ! error guardando el estado:", type(e).__name__, str(e)[:80])
        return False


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

        if time.monotonic() >= fin:
            break
        time.sleep(cada)

    print(f"■ Ventana de vigilancia completada ({n} ciclos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
