"""Reconstruir TODAS las operaciones que el sistema habría planteado.

Esto es lo que faltaba para poder aprender del pasado. Antes, el aprendizaje
solo veía las operaciones enviadas en vivo —dos docenas— mientras había más de
cuatro mil en el histórico, y por eso nunca llegaba al mínimo estadístico.

LA REGLA QUE HACE QUE ESTO VALGA ALGO
-------------------------------------
No reimplementa la estrategia. Llama a :func:`oro.sesiones.construir_plan` y a
:func:`oro.seguimiento.seguir`, que son las MISMAS funciones que deciden en
producción. Si mañana cambia la estrategia, la reconstrucción cambia con ella
sin que nadie tenga que acordarse.

Esto no es un detalle de estilo. La auditoría de este proyecto encontró que las
cifras documentadas se habían medido con una configuración que ya no era la que
se enviaba al correo: la ventaja bruta coincidía, pero la contabilidad del coste
no, y la estrategia real rendía la mitad de lo que decía su propia
documentación. Con investigación y producción compartiendo código eso no puede
volver a pasar.

CÓMO SE EVITA MIRAR EL FUTURO
-----------------------------
El plan de cada día se construye con las velas disponibles HASTA que abre la
ventana de disparo, nunca con las de después. Si se le pasara el día completo,
la guarda de "el rango ya se ha roto" vería la sesión entera y descartaría
todos los días; y lo que es peor, el sesgo y el rango podrían calcularse con
información que a esa hora no existía.

Uso:
    python -m oro.historico --desde 2006 --salida historico_ruptura.jsonl
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from typing import Iterator, Optional

from .config import ConfiguracionSistema, cargar_configuracion
from .dominio.mercado import dia_sesion, hora_mercado
from .seguimiento import deslizamiento_de, registro_de, seguir
from .spread import spread_de
from .sesiones import construir_plan


def _por_dia_de_sesion(df) -> Iterator[tuple[dt.date, "object"]]:
    """Parte el histórico en días de sesión del oro, en orden.

    Se agrupa una sola vez y se recorren los trozos, en lugar de filtrar el
    marco completo por cada día: con 125.000 velas y 5.700 días, filtrar cada
    vez convierte el trabajo en cuadrático y la reconstrucción pasa de segundos
    a horas.
    """
    dias = [dia_sesion(t.to_pydatetime()) for t in df.index]
    inicio = 0
    for i in range(1, len(dias) + 1):
        if i == len(dias) or dias[i] != dias[inicio]:
            yield dias[inicio], df.iloc[inicio:i]
            inicio = i


def reconstruir(df, cfg: Optional[ConfiguracionSistema] = None) -> list[dict]:
    """Las fichas de todos los días del histórico, en el formato del registro.

    Cada ficha es exactamente la que `oro_rupturas.jsonl` guarda en vivo, así
    que el aprendizaje puede juntar histórico y real sin traducir nada.
    """
    cfg = cfg or cargar_configuracion()
    c = cfg.ruptura
    fichas: list[dict] = []
    for dia, velas in _por_dia_de_sesion(df):
        horas = [hora_mercado(t.to_pydatetime()) for t in velas.index]
        # Lo que se sabía cuando se manda el plan: solo hasta que abre la
        # ventana de disparo. Pasarle más seria mirar el futuro.
        antes = velas[[h < c.sesion_desde_et for h in horas]]
        if antes.empty:
            continue
        # `construir_plan` usa `dia_sesion(ahora)` para saber de qué día habla.
        ahora = antes.index[-1].to_pydatetime()
        if dia_sesion(ahora) != dia:
            continue
        res = construir_plan(antes, cfg, ahora=ahora)
        if not res.hay_plan:
            continue
        plan = res.plan
        # Y ahora sí, el día entero, para ver qué pasó con el plan.
        s = seguir(plan, velas, ahora=plan.cierre_forzoso)
        # El coste de CADA AÑO, no el de hoy. Un coste fijo para 21 años es
        # falso en los dos extremos: cobrarle a 2016 el spread de 2026 (0.63 $
        # frente a 0.295 real) baja el resultado histórico de +0.1029 a +0.0680
        # R por operación e inventa una estrategia peor de lo que fue.
        coste = spread_de(dia.year) + deslizamiento_de(plan, cfg)
        ficha = registro_de(plan, s, coste)
        ficha["origen"] = "historico"
        # Los dos componentes por separado: si mañana se vuelve a medir uno,
        # hay que poder saber con qué se calculó cada R de hace meses.
        ficha["spread_usado"] = round(spread_de(dia.year), 3)
        ficha["deslizamiento_usado"] = round(deslizamiento_de(plan, cfg), 3)
        fichas.append(ficha)
    return fichas


def main(argv: Optional[list[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    desde = 2006
    salida = "historico_ruptura.jsonl"
    for i, a in enumerate(argv):
        if a == "--desde" and i + 1 < len(argv):
            desde = int(argv[i + 1])
        if a == "--salida" and i + 1 < len(argv):
            salida = argv[i + 1]

    cfg = cargar_configuracion()
    from .datos.dukascopy import ProveedorDukascopy

    print(f"Descargando XAU/USD desde {desde} (Dukascopy, con caché en disco)…")
    df = ProveedorDukascopy().rango(dt.date(desde, 1, 1), dt.date.today())
    print(f"  {len(df)} velas  {df.index.min()} → {df.index.max()}")

    print("Reconstruyendo con construir_plan() + seguir(), las mismas de producción…")
    fichas = reconstruir(df, cfg)
    with open(salida, "w", encoding="utf-8") as fh:
        for f in fichas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    cerradas = [f for f in fichas if f.get("r_neto") is not None]
    print(f"  {len(fichas)} días con plan, {len(cerradas)} con operación")
    if cerradas:
        rs = [f["r_neto"] for f in cerradas]
        media = sum(rs) / len(rs)
        print(f"  R neto medio {media:+.4f}   acumulado {sum(rs):+.1f} R")
    print(f"Guardado en {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
