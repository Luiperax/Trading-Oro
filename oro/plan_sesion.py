"""El plan de ruptura del día, para ejecutar de forma programada.

    python -m oro.plan_sesion

Se lanza a las 8:00 de Nueva York (14:00 en Madrid casi todo el año), mide el
rango que ha dejado la mañana de Londres y manda un correo con las dos órdenes
pendientes que hay que dejar puestas. La estrategia, con lo que se midió y lo
que falló, está documentada en :mod:`oro.sesiones`.

Opciones:
    --forzar     Manda el plan aunque no sea la hora (para probarlo a mano).
    --sintetico  Usa datos generados, sin salir a internet (para probar el correo).

Variables de entorno:
    ORO_PLAN_ESTADO   ruta del fichero que recuerda el último plan enviado
                      (por defecto oro_plan.json). Evita mandarlo dos veces
                      cuando GitHub encola la tarea más de una vez.
    ORO_RUPTURA_*     parámetros de la estrategia (ver oro/config.py).
    ORO_SMTP_*, ORO_TELEGRAM_*   canales de aviso (ver oro/notificaciones).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .cli import _construir_notificador
from .config import cargar_configuracion
from .dominio.mercado import dia_sesion, hora_mercado
from .sesiones import construir_plan

RUTA_ESTADO_POR_DEFECTO = "oro_plan.json"


def _ruta_estado() -> Path:
    return Path(os.getenv("ORO_PLAN_ESTADO", RUTA_ESTADO_POR_DEFECTO))


def _ultimo_dia_enviado() -> date | None:
    """Día de la última vez que el plan se ENTREGÓ (no solo se intentó)."""
    p = _ruta_estado()
    if not p.exists():
        return None
    try:
        bruto = json.loads(p.read_text(encoding="utf-8")).get("ultimo_plan")
        return date.fromisoformat(bruto) if bruto else None
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        # Un estado ilegible no puede dejar el sistema mudo para siempre. Se
        # arranca limpio: como mucho llega un plan repetido, que es mucho menos
        # grave que no llegar ninguno nunca más.
        print("⚠️  Estado del plan ilegible; se continúa como si no hubiera.")
        return None


def _anotar_dia(dia: date) -> None:
    p = _ruta_estado()
    try:
        if p.parent != Path(""):
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"ultimo_plan": dia.isoformat()}, ensure_ascii=False,
                                indent=2), encoding="utf-8")
    except OSError as e:  # noqa: BLE001 — no poder anotar no invalida el envío.
        print(f"⚠️  No se pudo guardar el estado del plan ({e}).")


def _proveedor(sintetico: bool):
    cfg = cargar_configuracion()
    if sintetico:
        from .datos import ProveedorSintetico
        return ProveedorSintetico(velas=2000, semilla=7)
    from .datos import ProveedorYahoo
    return ProveedorYahoo(timeframe=cfg.timeframe)


def ejecutar(forzar: bool = False, sintetico: bool = False,
             ahora: datetime | None = None) -> int:
    cfg = cargar_configuracion()
    ahora = ahora or datetime.now(timezone.utc)
    c = cfg.ruptura

    # 1) ¿Es la hora? Antes de las 8:00 de Nueva York el rango aún no está
    #    completo, así que no se puede calcular. Después sí se admite, hasta que
    #    caduca la ventana de disparo: las colas gratuitas de GitHub retrasan las
    #    tareas con frecuencia, y perder el plan del día por 20 minutos de cola
    #    sería absurdo. Lo que protege de mandar órdenes tarde no es esta hora
    #    sino `construir_plan`, que comprueba si el rango ya se ha roto.
    hora = hora_mercado(ahora)
    limite = c.sesion_desde_et + c.horas_validez
    if not forzar and not (c.sesion_desde_et <= hora < limite):
        motivo = ("el rango de la mañana aún no ha cerrado"
                  if hora < c.sesion_desde_et else "la ventana de disparo ya ha caducado")
        print(f"No es la hora del plan: son las {hora}:00 en Nueva York, se "
              f"calcula entre las {c.sesion_desde_et}:00 y las {limite}:00 "
              f"({motivo}). Nada que hacer.")
        return 0

    # 2) ¿Ya se envió hoy? GitHub encola la misma tarea varias veces y hay dos
    #    horarios programados (uno para cada mitad del año, por el cambio de
    #    hora): sin esta comprobación llegarían dos o tres correos iguales.
    dia = dia_sesion(ahora)
    if not forzar and _ultimo_dia_enviado() == dia:
        print(f"El plan de {dia} ya se envió. No se repite.")
        return 0

    # 3) Construirlo.
    proveedor = _proveedor(sintetico)
    df = proveedor.historico(400)
    resultado = construir_plan(df, cfg, ahora=ahora)
    if not resultado.hay_plan:
        print("Hoy no hay plan de ruptura:")
        for m in resultado.motivos_no:
            print(f"  · {m}")
        return 0

    plan = resultado.plan
    print(f"Plan de {plan.dia}: rango {plan.rango.bajo:.2f}-{plan.rango.alto:.2f} "
          f"({plan.rango.amplitud:.2f} $ de riesgo por onza), "
          f"compra {plan.compra.entrada:.2f} / venta {plan.venta.entrada:.2f}, "
          f"objetivo {plan.r_objetivo:.0f}R.")

    # 4) Enviarlo. Igual que con las señales: el día solo se marca como enviado
    #    si el aviso LLEGÓ. Si el correo falla, la siguiente ejecución lo
    #    reintenta en vez de dar por hecho que el usuario lo recibió.
    if not _construir_notificador().notificar_plan(plan):
        print("⚠️  EL PLAN NO SE PUDO ENVIAR. No se marca como enviado: se "
              "reintentará. Revisa los secretos ORO_SMTP_* / ORO_TELEGRAM_*.")
        return 1
    _anotar_dia(plan.dia)
    print("✔ Plan enviado.")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Plan de ruptura de sesión de XAU/USD.")
    p.add_argument("--forzar", action="store_true",
                   help="enviar aunque no sea la hora ni haya cambiado el día")
    p.add_argument("--sintetico", action="store_true",
                   help="usar datos generados, sin salir a internet")
    args = p.parse_args(argv)
    return ejecutar(forzar=args.forzar, sintetico=args.sintetico)


if __name__ == "__main__":
    sys.exit(main())
