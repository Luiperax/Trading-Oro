"""Resumen del registro real de señales: cuántas se cumplieron y con qué resultado.

Lee el histórico permanente de operaciones (``operaciones_oro.jsonl``, que el
vigilante va rellenando al cerrar cada operación) y calcula las métricas reales:
acierto, Profit Factor, expectativa, resultado total y rachas.

Uso:
    python -m oro.informe
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import cargar_configuracion


def _cargar(ruta: Path) -> list:
    if not ruta.exists():
        return []
    registros = []
    for linea in ruta.open(encoding="utf-8"):
        linea = linea.strip()
        if linea:
            try:
                registros.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return registros


def _filtrar_mes(ops: list, aaaa_mm: str | None) -> list:
    """Filtra las operaciones cuyo cierre cae en el mes ``AAAA-MM`` (o todas)."""
    if not aaaa_mm:
        return ops
    return [o for o in ops if str(o.get("cierre", ""))[:7] == aaaa_mm]


def construir_resumen(ops: list, titulo: str = "REGISTRO REAL DE SEÑALES — XAU/USD") -> str:
    """Construye el texto del resumen (acierto, Profit Factor, rachas…)."""
    lineas = ["=" * 52, f"  {titulo}", "=" * 52]
    if not ops:
        lineas.append("Todavía no hay operaciones cerradas registradas.")
        return "\n".join(lineas)

    erres = [o.get("resultado_r", 0.0) for o in ops]
    ganadas = [r for r in erres if r > 0]
    perdidas = [r for r in erres if r <= 0]
    n = len(erres)
    win = len(ganadas) / n if n else 0.0
    suma_g, suma_p = sum(ganadas), abs(sum(perdidas))
    pf = (suma_g / suma_p) if suma_p > 0 else float("inf")
    expectancy = sum(erres) / n if n else 0.0
    max_g = max_p = act_g = act_p = 0
    for r in erres:
        act_g, act_p = (act_g + 1, 0) if r > 0 else (0, act_p + 1)
        max_g, max_p = max(max_g, act_g), max(max_p, act_p)

    lineas += [
        f"Operaciones cerradas : {n}",
        f"Se cumplieron (ganadas): {len(ganadas)}   |   Fallaron: {len(perdidas)}",
        f"% de ACIERTO         : {win:.1%}",
        "Profit Factor        : ∞" if pf == float("inf") else f"Profit Factor        : {pf:.2f}",
        f"Expectancy (R media) : {expectancy:+.3f}R",
        f"Resultado total      : {sum(erres):+.2f}R",
        f"Racha ganadora máx   : {max_g}   | perdedora máx: {max_p}",
        "-" * 52,
        "Últimas operaciones:",
    ]
    for o in ops[-8:]:
        marca = "✓ CUMPLIDA" if o.get("ganada") else "✗ fallida"
        lineas.append(f"  {str(o.get('apertura',''))[:16]}  {o.get('direccion','').upper():6} "
                      f"@ {o.get('entrada')}  -> {o.get('resultado_r'):+.2f}R  {marca}")
    lineas += ["", "Datos reales de tus señales. Herramienta de análisis, no asesoramiento."]
    return "\n".join(lineas)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = cargar_configuracion()
    ops = _cargar(Path(cfg.ruta_operaciones))

    # --mes AAAA-MM filtra un mes concreto; --email envía el resumen por los canales.
    mes = None
    if "--mes" in argv:
        i = argv.index("--mes")
        mes = argv[i + 1] if i + 1 < len(argv) else None
    ops_mes = _filtrar_mes(ops, mes)
    titulo = f"RESUMEN DEL MES {mes}" if mes else "REGISTRO REAL DE SEÑALES — XAU/USD"
    texto = construir_resumen(ops_mes, titulo)
    print(texto)

    if "--email" in argv:
        from .cli import _construir_notificador
        from .notificaciones.base import Evento
        notif = _construir_notificador()
        notif.enviar(f"📊 {titulo} — XAU/USD", texto, Evento.CAMBIO_MERCADO)
        print("\n(Resumen enviado por los canales configurados.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
