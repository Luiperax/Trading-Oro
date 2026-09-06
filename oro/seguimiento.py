"""Qué pasa DESPUÉS de mandar el plan: seguir la operación y registrar el final.

El plan deja dos órdenes puestas y se va. Este módulo es lo que ocurre luego:
mira las velas de la sesión, decide si alguna orden ha saltado, avisa cuando toca
mover el stop y cuando toca cerrar, y guarda el resultado para que el sistema
aprenda de sus propias operaciones.

POR QUÉ SE RECALCULA TODO EN CADA CICLO
---------------------------------------
El estado no se acumula: en cada ejecución se vuelve a reproducir el día entero
desde las velas. Es más caro y es deliberado. Con estado acumulado, una
ejecución que falle —GitHub cancela tareas, la red se cae, el runner muere— se
salta un tramo del día y esa operación queda mal para siempre. Recalculando,
la ejecución siguiente ve el día completo y llega a la misma conclusión.

Lo único que se guarda entre ejecuciones es QUÉ AVISOS SE HAN MANDADO YA, que es
lo único que no se puede deducir de las velas.

LO QUE ESTE MÓDULO NO PUEDE SABER
---------------------------------
Trabaja con velas de una hora. Si dentro de la misma vela el precio toca el stop
Y el objetivo, no hay forma de saber cuál fue primero: se asume el STOP, que es
el supuesto conservador. Y si en el primer tramo de la sesión el precio ha salido
del rango por los DOS lados, no se sabe qué orden saltó antes: no se registra
ninguna operación, porque inventarse un dato sería peor que perderlo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from .dominio import Direccion
from .notificaciones.base import Evento
from .sesiones import PlanRuptura


class EstadoPlan(str, Enum):
    ESPERANDO = "esperando"      # las dos órdenes puestas, ninguna ha saltado.
    ABIERTA = "abierta"          # una saltó y sigue viva.
    CERRADA = "cerrada"          # tocó stop u objetivo.
    CADUCADO = "caducado"        # pasó la ventana sin saltar ninguna.
    AMBIGUA = "ambigua"          # rompió por los dos lados: no se sabe cuál fue.


@dataclass(slots=True)
class AvisoSeguimiento:
    """Un aviso que hay que mandar (o que ya se mandó)."""

    clave: str                   # identifica el aviso para no repetirlo.
    tipo: Evento
    momento: datetime
    precio: float
    titulo: str
    cuerpo: str
    r: float


@dataclass(slots=True)
class Seguimiento:
    """El resultado de reproducir el día: estado, resultado y avisos pendientes."""

    estado: EstadoPlan
    direccion: Optional[Direccion] = None
    entrada: float = 0.0
    stop_actual: float = 0.0
    salida: Optional[float] = None
    momento_entrada: Optional[datetime] = None
    momento_salida: Optional[datetime] = None
    r: float = 0.0               # resultado en R (0 si sigue abierta o no hubo).
    r_maximo: float = 0.0        # lo más lejos que ha llegado a favor, en R.
    motivo_cierre: str = ""
    avisos: List[AvisoSeguimiento] = field(default_factory=list)

    @property
    def hubo_operacion(self) -> bool:
        return self.estado in (EstadoPlan.ABIERTA, EstadoPlan.CERRADA)


def _velas_de_sesion(df, plan: PlanRuptura):
    """Velas desde que abre la ventana de disparo hasta el cierre de la sesión."""
    idx = df.index
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize(timezone.utc)
    mascara = (idx >= plan.sesion_desde) & (idx <= plan.cierre_forzoso)
    return df[mascara]


def seguir(plan: PlanRuptura, df, ahora: Optional[datetime] = None,
           avisados: Optional[set] = None,
           r_break_even: float = 1.0) -> Seguimiento:
    """Reproduce el día desde las velas y devuelve el estado y los avisos nuevos.

    ``avisados`` son las claves de los avisos ya enviados en ejecuciones
    anteriores; los que ya están no se vuelven a incluir.
    """
    ahora = ahora or datetime.now(timezone.utc)
    avisados = avisados or set()
    velas = _velas_de_sesion(df, plan)
    riesgo = plan.rango.amplitud

    # --- 1) ¿Ha saltado alguna orden dentro de la ventana de validez? ---
    en_ventana = velas[velas.index < plan.valido_hasta]
    disparo = None
    for momento, v in en_ventana.iterrows():
        arriba = float(v["high"]) > plan.compra.entrada
        abajo = float(v["low"]) < plan.venta.entrada
        if arriba and abajo:
            # Dentro de la misma vela no se sabe cuál fue primero. Registrar una
            # dirección inventada envenenaría el aprendizaje con datos falsos.
            return Seguimiento(estado=EstadoPlan.AMBIGUA)
        if arriba:
            disparo = (momento, plan.compra); break
        if abajo:
            disparo = (momento, plan.venta); break

    if disparo is None:
        if len(en_ventana) == 0 and ahora >= plan.valido_hasta:
            # Sin velas no se sabe NADA: puede que el proveedor haya fallado.
            # Dar el día por caducado grabaría un "no hubo operación" que quizá
            # es falso, y ese registro luego alimenta el aprendizaje.
            return Seguimiento(estado=EstadoPlan.ESPERANDO)
        if ahora >= plan.valido_hasta:
            s = Seguimiento(estado=EstadoPlan.CADUCADO)
            _añadir(s, avisados, AvisoSeguimiento(
                clave=f"{plan.dia}:caducado", tipo=Evento.CIERRE,
                momento=plan.valido_hasta, precio=0.0, r=0.0,
                titulo="🚫 CANCELA las dos órdenes de XAU/USD",
                cuerpo=("Se ha acabado la ventana y el precio no ha salido del "
                        "rango de la mañana. Hoy no hay operación: cancela las "
                        "dos órdenes pendientes en el bróker.")))
            return s
        return Seguimiento(estado=EstadoPlan.ESPERANDO)

    momento_ent, orden = disparo
    s = Seguimiento(estado=EstadoPlan.ABIERTA, direccion=orden.direccion,
                    entrada=orden.entrada, stop_actual=orden.stop,
                    momento_entrada=momento_ent)
    signo = orden.direccion.signo

    # --- 2) Reproducir la vida de la operación vela a vela ---
    movido_a_be = False
    for momento, v in velas[velas.index >= momento_ent].iterrows():
        mejor = float(v["high"]) if signo > 0 else float(v["low"])
        peor = float(v["low"]) if signo > 0 else float(v["high"])
        s.r_maximo = max(s.r_maximo, signo * (mejor - orden.entrada) / riesgo)

        # Conservador: dentro de la vela, primero el stop. No se puede saber el
        # orden real y suponer lo favorable inflaría el resultado del registro.
        toca_stop = peor <= s.stop_actual if signo > 0 else peor >= s.stop_actual
        if toca_stop:
            _cerrar(s, plan, s.stop_actual, momento, riesgo,
                    "break-even" if movido_a_be else "stop")
            break
        toca_obj = mejor >= orden.objetivo if signo > 0 else mejor <= orden.objetivo
        if toca_obj:
            _cerrar(s, plan, orden.objetivo, momento, riesgo, "objetivo")
            break
        if not movido_a_be and s.r_maximo >= r_break_even:
            movido_a_be = True
            s.stop_actual = orden.entrada
            _añadir(s, avisados, AvisoSeguimiento(
                clave=f"{plan.dia}:break-even", tipo=Evento.MOVER_STOP,
                momento=momento, precio=float(v["close"]), r=s.r_maximo,
                titulo="🛡 MUEVE EL STOP a la entrada (XAU/USD)",
                cuerpo=(f"La operación te lleva {s.r_maximo:.1f}R de beneficio. "
                        f"Mueve el stop loss a {orden.entrada:.2f}, tu precio de "
                        f"entrada: a partir de ahí ya no puede perder dinero. "
                        f"Medido, este movimiento sube la ventaja de +0,067 a "
                        f"+0,077 R por operación.")))

    # --- 3) ¿Toca cerrar a mano? ---
    if s.estado is EstadoPlan.ABIERTA and ahora >= plan.cierre_forzoso:
        ultimo = float(velas["close"].iloc[-1]) if len(velas) else orden.entrada
        # El resultado del cierre a mano ES el resultado de la operación. Sin
        # esto, todas las operaciones cerradas al final del día se registraban
        # con 0.00R —ni ganadas ni perdidas— y el aprendizaje se quedaba solo
        # con las que tocan stop u objetivo, que son las peores y las mejores.
        # Se marca CERRADA: para el registro el día ya no puede cambiar. Dejarla
        # como ABIERTA hacía que `ganada` saliera nulo en una operación que sí
        # tuvo resultado, y el marcador se quedaba sin ella.
        _cerrar(s, plan, ultimo, plan.cierre_forzoso, riesgo, "cierre de sesión")
        _añadir(s, avisados, AvisoSeguimiento(
            clave=f"{plan.dia}:cierre", tipo=Evento.CIERRE,
            momento=plan.cierre_forzoso, precio=ultimo,
            r=signo * (ultimo - orden.entrada) / riesgo,
            titulo="⏱ CIERRA la operación de XAU/USD, gane o pierda",
            cuerpo=(f"Se acaba la sesión. Cierra la posición a mercado: la "
                    f"estrategia no deja operaciones abiertas de un día para "
                    f"otro. Vas {signo * (ultimo - orden.entrada) / riesgo:+.2f}R.")))
    return s


def _cerrar(s: Seguimiento, plan: PlanRuptura, precio: float, momento: datetime,
            riesgo: float, motivo: str) -> None:
    s.estado = EstadoPlan.CERRADA
    s.salida = precio
    s.momento_salida = momento
    s.motivo_cierre = motivo
    s.r = s.direccion.signo * (precio - s.entrada) / riesgo


def _añadir(s: Seguimiento, avisados: set, aviso: AvisoSeguimiento) -> None:
    if aviso.clave not in avisados:
        s.avisos.append(aviso)


def registro_de(plan: PlanRuptura, s: Seguimiento, coste: float) -> dict:
    """La ficha que se guarda para aprender: condiciones + resultado real.

    El resultado va NETO del coste de operar, porque es lo que de verdad pasa en
    la cuenta. Un registro en bruto haría creer que la estrategia gana cuando el
    spread se la está comiendo, que es justo el error que este proyecto lleva
    toda su historia intentando no cometer.
    """
    riesgo = plan.rango.amplitud
    return {
        "dia": plan.dia.isoformat(),
        "estrategia": "ruptura_sesion",
        "rango_alto": round(plan.rango.alto, 2),
        "rango_bajo": round(plan.rango.bajo, 2),
        "amplitud": round(riesgo, 2),
        "estado": s.estado.value,
        "direccion": s.direccion.value if s.direccion else None,
        "entrada": round(s.entrada, 2) if s.entrada else None,
        "salida": round(s.salida, 2) if s.salida is not None else None,
        "motivo_cierre": s.motivo_cierre,
        # Sin operación no hay resultado. Poner 0.0 (o peor, -coste/R) haría que
        # los días en que no se opera contasen como perdedores en el marcador.
        "r_bruto": round(s.r, 3) if s.hubo_operacion else None,
        "r_neto": (round(s.r - coste / riesgo, 3)
                   if s.hubo_operacion and riesgo > 0 else None),
        "r_maximo": round(s.r_maximo, 3),
        "coste_r": round(coste / riesgo, 4) if riesgo > 0 else None,
        # Condiciones del día: es lo que permitirá responder «¿por qué salió
        # bien o mal?» cuando haya suficientes operaciones.
        "sesgo_cuerpo": round(plan.sesgo.cuerpo, 2),
        "sesgo_rango": round(plan.sesgo.rango, 2),
        "favorita": plan.favorita.value if plan.favorita else None,
        "acompaña_al_sesgo": (
            None if plan.favorita is None or s.direccion is None
            else s.direccion is plan.favorita),
        "hora_entrada": (s.momento_entrada.isoformat() if s.momento_entrada else None),
        "ganada": s.r > 0 if s.estado is EstadoPlan.CERRADA else None,
    }


__all__ = ["EstadoPlan", "AvisoSeguimiento", "Seguimiento", "seguir", "registro_de"]
