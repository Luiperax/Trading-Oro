"""Seguimiento de la operación del día, para ejecutar cada pocos minutos.

    python -m oro.seguir_plan

Se lanza durante la sesión de Nueva York. En cada ejecución vuelve a reproducir
el día entero desde las velas (ver :mod:`oro.seguimiento`), manda los avisos que
toquen —mover el stop a break-even, cancelar las órdenes, cerrar a mano— y, en
cuanto la operación termina, guarda la ficha para que el sistema aprenda.

Es la otra mitad de `oro.plan_sesion`: aquel manda el plan por la mañana, este
sigue lo que pasa después. Sin él, el plan se enviaba y nadie sabía si funcionó.

Variables de entorno:
    ORO_PLAN_ESTADO         estado del plan (por defecto oro_plan.json).
    ORO_RUTA_RUPTURAS       registro de operaciones (oro_rupturas.jsonl).
    ORO_SMTP_*, ORO_TELEGRAM_*   canales de aviso.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from .cli import _construir_notificador
from .config import cargar_configuracion
from .plan_sesion import _proveedor, _ruta_estado
from .seguimiento import EstadoPlan, registro_de, seguir
from .sesiones import PlanRuptura

RUTA_RUPTURAS = "oro_rupturas.jsonl"


def _estado() -> dict:
    p = _ruta_estado()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print("⚠️  Estado del plan ilegible; no se puede seguir la operación.")
        return {}


def _guardar_estado(datos: dict) -> None:
    p = _ruta_estado()
    try:
        if p.parent != Path(""):
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:  # noqa: BLE001
        print(f"⚠️  No se pudo guardar el estado ({e}).")


def _anotar(registro: dict) -> None:
    """Guarda la ficha de la operación. Append-only, una línea por día."""
    ruta = Path(os.getenv("ORO_RUTA_RUPTURAS", RUTA_RUPTURAS))
    try:
        if ruta.parent != Path(""):
            ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError as e:  # noqa: BLE001 — un fallo de registro no rompe el ciclo.
        print(f"⚠️  No se pudo guardar el registro ({e}).")


def ejecutar(sintetico: bool = False, ahora: datetime | None = None) -> int:
    cfg = cargar_configuracion()
    ahora = ahora or datetime.now(timezone.utc)
    datos = _estado()
    bruto = datos.get("plan")
    if not bruto:
        print("No hay plan guardado hoy: nada que seguir.")
        return 0

    plan = PlanRuptura(**_rehidratar(bruto))
    if datos.get("registrado") == plan.dia.isoformat():
        print(f"La operación de {plan.dia} ya está registrada. Nada que hacer.")
        return 0
    # Un plan de otro día no se sigue. Sin esto, un plan que nunca llegó a
    # registrarse (porque faltaron velas, por ejemplo) se seguiría reproduciendo
    # cada 15 minutos para siempre, mandando avisos de una operación de la
    # semana pasada.
    from .dominio.mercado import dia_sesion

    if plan.dia != dia_sesion(ahora):
        print(f"El plan guardado es de {plan.dia} y hoy la sesión es "
              f"{dia_sesion(ahora)}: no se sigue un plan de otro día.")
        return 0

    df = _proveedor(sintetico).historico(400)
    avisados = set(datos.get("avisados", []))
    s = seguir(plan, df, ahora=ahora, avisados=avisados)
    print(f"{plan.dia}: estado {s.estado.value}"
          + (f", {s.direccion.value} desde {s.entrada:.2f}" if s.direccion else "")
          + (f", cerrada en {s.salida:.2f} ({s.r:+.2f}R, {s.motivo_cierre})"
             if s.salida is not None else "")
          + f", {len(s.avisos)} aviso(s) nuevo(s).")

    # Los avisos SOLO se marcan como enviados si llegaron. Si el correo falla, la
    # ejecución siguiente lo reintenta: es la misma disciplina que las señales.
    if s.avisos:
        notificador = _construir_notificador()
        for aviso in s.avisos:
            if notificador.enviar(aviso.titulo, aviso.cuerpo, aviso.tipo):
                avisados.add(aviso.clave)
            else:
                print(f"⚠️  AVISO NO ENVIADO ({aviso.clave}): se reintentará.")
    datos["avisados"] = sorted(avisados)

    # La ficha se guarda cuando el día ya no puede cambiar.
    # `seguir` ya cierra la operación al llegar la hora, así que aquí basta con
    # mirar el estado: no hace falta repetir la condición de la hora, que sería
    # una segunda fuente de verdad sobre lo mismo.
    if s.estado in (EstadoPlan.CERRADA, EstadoPlan.CADUCADO, EstadoPlan.AMBIGUA):
        _anotar(registro_de(plan, s, cfg.riesgo.coste_operacion))
        datos["registrado"] = plan.dia.isoformat()
        print(f"Registrada la operación de {plan.dia}.")
    _guardar_estado(datos)
    return 0


def _rehidratar(d: dict) -> dict:
    """Reconstruye el plan guardado en JSON (fechas y objetos anidados)."""
    from datetime import date

    from .dominio import Direccion
    from .sesiones import OrdenPendiente, RangoSesion, SesgoAsiatico

    def _dt(v):
        return datetime.fromisoformat(v) if v else None

    r = d["rango"]
    sg = d["sesgo"]
    return dict(
        dia=date.fromisoformat(d["dia"]),
        rango=RangoSesion(alto=r["alto"], bajo=r["bajo"], desde=_dt(r["desde"]),
                          hasta=_dt(r["hasta"]), velas=r["velas"]),
        compra=OrdenPendiente(direccion=Direccion.COMPRA, **d["compra"]),
        venta=OrdenPendiente(direccion=Direccion.VENTA, **d["venta"]),
        sesion_desde=_dt(d["sesion_desde"]),
        valido_hasta=_dt(d["valido_hasta"]),
        cierre_forzoso=_dt(d["cierre_forzoso"]),
        onzas=d["onzas"], coste_r=d["coste_r"], r_objetivo=d["r_objetivo"],
        sesgo=SesgoAsiatico(
            direccion=Direccion(sg["direccion"]) if sg["direccion"] else None,
            cuerpo=sg["cuerpo"], rango=sg["rango"]),
    )


def serializar(plan: PlanRuptura) -> dict:
    """El plan en JSON, para que la ejecución siguiente pueda seguirlo."""
    return {
        "dia": plan.dia.isoformat(),
        "rango": {"alto": plan.rango.alto, "bajo": plan.rango.bajo,
                  "desde": plan.rango.desde.isoformat(),
                  "hasta": plan.rango.hasta.isoformat(), "velas": plan.rango.velas},
        "compra": {"entrada": plan.compra.entrada, "stop": plan.compra.stop,
                   "objetivo": plan.compra.objetivo},
        "venta": {"entrada": plan.venta.entrada, "stop": plan.venta.stop,
                  "objetivo": plan.venta.objetivo},
        "sesion_desde": plan.sesion_desde.isoformat(),
        "valido_hasta": plan.valido_hasta.isoformat(),
        "cierre_forzoso": plan.cierre_forzoso.isoformat(),
        "onzas": plan.onzas, "coste_r": plan.coste_r, "r_objetivo": plan.r_objetivo,
        "sesgo": {"direccion": plan.sesgo.direccion.value if plan.sesgo.direccion
                  else None,
                  "cuerpo": plan.sesgo.cuerpo, "rango": plan.sesgo.rango},
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seguimiento del plan de ruptura.")
    p.add_argument("--sintetico", action="store_true",
                   help="usar datos generados, sin salir a internet")
    return ejecutar(sintetico=p.parse_args(argv).sintetico)


if __name__ == "__main__":
    sys.exit(main())
