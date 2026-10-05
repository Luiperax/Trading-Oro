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
from .referencia import comprobar_fuente
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


def fuente_actual(sintetico: bool = False) -> str:
    """De dónde salen las velas con la configuración actual, como texto.

    Se guarda con el plan y el seguimiento la compara antes de seguirlo. El
    5-oct-2026 el plan lo calculó el código anterior sobre el futuro de COMEX
    (GC=F) y el seguimiento nuevo lo siguió con el contado, 43 $ más abajo: vio
    una venta «abierta» que nunca existió y mandó un aviso falso de
    break-even. Unos niveles solo tienen sentido contra el precio del que
    salieron.
    """
    if sintetico:
        return "sintetico"
    cfg = cargar_configuracion()
    if cfg.fuente_vivo == "dukascopy":
        return f"dukascopy:{cfg.simbolo.upper()}"
    return f"yahoo:{cfg.simbolo_vivo}"


def horas_que_faltan(df, cfg, dia: date) -> list[datetime]:
    """Horas de la mañana de Londres de ``dia`` que NO están en ``df``.

    ``construir_plan`` admite el rango con ``velas_minimas`` de las cinco
    horas, y con datos históricos es lo correcto: si falta una hora es que no
    existe. En vivo no: Dukascopy pierde ficheros sueltos de forma transitoria
    (en Actions, dos o tres horas por ciclo, distintas cada vez), y un rango con
    una hora perdida sale más estrecho de lo real. La orden quedaría más cerca
    del precio y saltaría con ruido. Esa hora aparece al reintentar.
    """
    import pandas as pd

    from .sesiones import _a_las

    c = cfg.ruptura
    idx = df.index if getattr(df.index, "tz", None) else df.index.tz_localize("UTC")
    presentes = set(idx)
    esperadas = [_a_las(dia, h) for h in range(c.rango_desde_et, c.rango_hasta_et)]
    return [h for h in esperadas if pd.Timestamp(h) not in presentes]


# Hasta cuándo se espera a que aparezcan las horas perdidas del rango, en horas
# de Nueva York. El vigilante lo reintenta cada tres minutos; pasado esto se
# manda con lo que haya, porque la ventana de disparo se está consumiendo y
# `construir_plan` sigue exigiendo `velas_minimas`.
ESPERA_HUECOS_HASTA_ET = 9


def _anotar_dia(dia: date, plan=None, fuente: str | None = None) -> None:
    """Guarda el día enviado y el PLAN entero.

    El plan se guarda porque `oro.seguir_plan` lo necesita para seguir la
    operación durante la tarde: sin él, el correo se manda y nadie sabe nunca si
    la operación salió bien, que es justo lo que este sistema debe aprender.
    """
    from .seguir_plan import serializar

    p = _ruta_estado()
    datos = {"ultimo_plan": dia.isoformat(), "avisados": []}
    if plan is not None:
        datos["plan"] = serializar(plan)
    if fuente is not None:
        datos["fuente"] = fuente
    try:
        if p.parent != Path(""):
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:  # noqa: BLE001 — no poder anotar no invalida el envío.
        print(f"⚠️  No se pudo guardar el estado del plan ({e}).")


# Velas que se piden en vivo. Las 400 de antes eran del motor de señales
# intradía, que necesita 200 de calentamiento para la EMA. La ruptura solo mira
# el día de sesión en curso —sesgo asiático (0-3 ET), rango de Londres (3-8 ET)
# y sesión (8-16 ET)— y está medido sobre el código real que con 8 velas ya da
# el MISMO plan y el MISMO resultado que con el marco entero.
#
# 24 y no 48: con Dukascopy son horas de calendario y cada una es una petición.
# A las 16:00 de Nueva York, 24 horas atrás siguen cubriendo las 0:00 del día
# de sesión, y un lunes a las 8:00 llegan hasta el domingo a mediodía, antes de
# que abra el mercado. Pedir 48 era pedir el doble para tirar la mitad, y el
# servidor corta con 429 cuando se le pide mucho seguido.
VELAS_EN_VIVO = 24


_DUKASCOPY = None


def _proveedor(sintetico: bool):
    cfg = cargar_configuracion()
    if sintetico:
        from .datos import ProveedorSintetico
        return ProveedorSintetico(velas=2000, semilla=7)
    if cfg.fuente_vivo == "dukascopy":
        # XAU/USD al contado, armado desde los ticks de la última hora cerrada.
        # Mismo instrumento que la investigación y con el spread real.
        #
        # UNO POR PROCESO. El vigilante llama al plan y al seguimiento cada tres
        # minutos durante cinco horas; con un proveedor nuevo en cada llamada
        # serían 48 peticiones cada vez, unas 4.800 por ejecución, para horas
        # cerradas que no cambian nunca. Así cada hora se pide una vez.
        global _DUKASCOPY
        if _DUKASCOPY is None or _DUKASCOPY._simbolo != cfg.simbolo.upper():
            from .datos.dukascopy_vivo import ProveedorDukascopyVivo
            _DUKASCOPY = ProveedorDukascopyVivo(simbolo=cfg.simbolo)
        return _DUKASCOPY
    from .datos import ProveedorYahoo
    return ProveedorYahoo(simbolo=cfg.simbolo_vivo, timeframe=cfg.timeframe)


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
    df = proveedor.historico(VELAS_EN_VIVO)

    # ¿Esto es oro al contado? Durante semanas los niveles salieron del FUTURO
    # de COMEX mientras el correo pedía operar XAU/USD, y nadie se enteró
    # porque el sistema solo ve un feed y un feed no puede contradecirse a sí
    # mismo. El LBMA Gold Price es el árbitro de fuera.
    # Con datos sintéticos el precio es inventado: no hay oro que contrastar.
    if sintetico:
        vale, explicacion = True, "Datos sintéticos: sin árbitro."
    else:
        vale, explicacion = comprobar_fuente(proveedor)
    print(f"  {explicacion}")
    if not vale:
        print("⚠️  NO SE MANDA EL PLAN. Unas órdenes con el instrumento "
              "equivocado se ejecutarían al instante en vez de esperar a la "
              "ruptura: es el fallo más caro de esta estrategia, y es peor que "
              "quedarse un día sin plan.")
        return 1

    faltan = [] if sintetico else horas_que_faltan(df, cfg, dia)
    if faltan:
        lista = ", ".join(h.strftime("%H:00") for h in faltan)
        if hora < ESPERA_HUECOS_HASTA_ET and not forzar:
            print(f"⚠️  Faltan {len(faltan)} hora(s) de la mañana de Londres "
                  f"({lista} UTC). Un rango incompleto sale más estrecho de lo "
                  f"real y pondría la orden demasiado cerca: no se manda todavía, "
                  f"se reintenta en la próxima pasada.")
            return 1
        print(f"⚠️  Siguen faltando {len(faltan)} hora(s) del rango ({lista} UTC) "
              f"y son más de las {ESPERA_HUECOS_HASTA_ET}:00 en Nueva York: se "
              f"calcula con las que hay.")

    resultado = construir_plan(df, cfg, ahora=ahora)
    if not resultado.hay_plan:
        print("Hoy no hay plan de ruptura:")
        for m in resultado.motivos_no:
            print(f"  · {m}")
        return 0

    plan = resultado.plan
    ordenes = " / ".join(f"{o.direccion.value} {o.entrada:.2f}" for o in plan.ordenes)
    print(f"Plan de {plan.dia}: rango {plan.rango.bajo:.2f}-{plan.rango.alto:.2f} "
          f"({plan.rango.amplitud:.2f} $ de riesgo por onza), {ordenes}, "
          f"objetivo {plan.r_objetivo:.0f}R."
          + (f" Se anula si sube de {plan.compra.entrada:.2f}."
             if plan.solo_ventas and plan.anular_si_rompe_arriba else ""))

    # 4) Enviarlo. Igual que con las señales: el día solo se marca como enviado
    #    si el aviso LLEGÓ. Si el correo falla, la siguiente ejecución lo
    #    reintenta en vez de dar por hecho que el usuario lo recibió.
    if not _construir_notificador().notificar_plan(plan):
        print("⚠️  EL PLAN NO SE PUDO ENVIAR. No se marca como enviado: se "
              "reintentará. Revisa los secretos ORO_SMTP_* / ORO_TELEGRAM_*.")
        return 1
    _anotar_dia(plan.dia, plan, fuente_actual(sintetico))
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
