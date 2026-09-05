"""Gestor de una operación abierta: decide y notifica las SALIDAS.

Es la pieza que responde a «¿cuándo salgo?». Dada una señal ejecutada, sigue el
precio y va generando eventos de gestión conforme se cumplen las condiciones:

1. Se alcanza un objetivo parcial (TP): se cierra su fracción.
2. Tras el primer objetivo, el stop se mueve a *break-even* (entrada): la
   operación pasa a riesgo cero.
3. Si el precio toca el stop vigente: se cierra el resto (en pérdida, o a
   break-even si ya se movió).
4. Cuando se cierran todas las fracciones, la operación termina.

El gestor es determinista y se prueba sin red ni tiempo real.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List

from ..dominio.mercado import APERTURA_ET, dia_sesion, hora_mercado
from ..dominio import Direccion, EstadoOperacion, Signal
from ..notificaciones.base import Evento


@dataclass(slots=True)
class EventoGestion:
    tipo: Evento
    momento: datetime
    precio: float
    mensaje: str
    r_acumulado: float          # resultado acumulado de la operación, en R.
    cierra_operacion: bool = False


@dataclass(slots=True)
class _NivelTP:
    precio: float
    fraccion: float
    r_multiple: float
    alcanzado: bool = False


_HORA_CIERRE_POR_DEFECTO = 16      # 16:00 en Nueva York (reloj del mercado).


def _hora_cierre_de(d: dict) -> int:
    """Hora de cierre operativo, en el reloj de NUEVA YORK, desde un estado guardado.

    Aquí había DOS asignaciones seguidas y la segunda pisaba a la primera, así
    que la migración desde el nombre antiguo era código muerto y el valor por
    defecto quedaba en 21 —la hora UTC de la época anterior—.

    Un 21 leído como hora de Nueva York rompe el cierre de fin de sesión EN
    SILENCIO: la condición ``21 <= hora_mercado < 18`` no se cumple nunca, así
    que la operación no se cierra al acabar la sesión y aguanta hasta el cambio
    de día, ya con el mercado cerrado. Es exactamente el síntoma que llevamos
    persiguiendo.

    Los estados anteriores a la migración guardaban una hora UTC, y convertirla
    no es fiable (depende del horario de verano). Se descarta y se aplica la
    política actual: es más seguro que arrastrar un número con el significado
    equivocado.
    """
    valor = d.get("hora_cierre_et")
    if valor is None:
        return _HORA_CIERRE_POR_DEFECTO
    try:
        hora = int(valor)
    except (TypeError, ValueError):
        return _HORA_CIERRE_POR_DEFECTO
    return hora if 0 <= hora < 24 else _HORA_CIERRE_POR_DEFECTO


class GestorOperaciones:
    def __init__(
        self,
        signal: Signal,
        entrada_real: float | None = None,
        cerrar_intradia: bool = True,
        hora_cierre_et: int = 16,
        trailing_activo: bool = True,
        trailing_r: float = 1.0,
        trailing_desde_entrada: bool = True,
    ) -> None:
        self.signal = signal
        self.direccion = signal.direccion
        self.entrada = entrada_real if entrada_real is not None else signal.entrada
        self._riesgo = abs(self.entrada - signal.stop_loss)
        self.stop_actual = signal.stop_loss
        self._en_breakeven = False
        self.niveles = [
            _NivelTP(tp.precio, tp.fraccion, tp.r_multiple) for tp in signal.take_profits
        ]
        self.restante = 1.0
        self.r_acumulado = 0.0
        self.estado = EstadoOperacion.ABIERTA
        self.abierta_en = signal.momento
        self._cerrar_intradia = cerrar_intradia
        self._hora_cierre = hora_cierre_et
        self._trailing = trailing_activo
        self._trailing_r = max(0.1, float(trailing_r))
        self._trailing_desde_entrada = bool(trailing_desde_entrada)
        self._peak = self.entrada  # máximo (compra) / mínimo (venta) favorable.
        # Datos de la señal, para el registro histórico y el aprendizaje al cerrar.
        self.probabilidad = signal.probabilidad if signal else 0.0
        self.confianza = signal.confianza if signal else 0.0
        self.stop_inicial = signal.stop_loss if signal else self.stop_actual
        self.features = dict(signal.features) if signal else {}
        # Los MOTIVOS por los que se mandó la señal, en el mismo lenguaje que
        # leyó el usuario. Sin guardarlos, al cerrarse la operación ya no se
        # puede responder "¿por qué mandé esta señal?": quedan las features
        # numéricas, que no se leen, y se pierde el porqué.
        self.motivos = list(signal.motivos_entrada) if signal else []

    def _trailing_stop(self, precio: float) -> None:
        """Tras el break-even, el stop persigue al precio desde el máximo favorable.

        La distancia (``trailing_r``, en múltiplos de R) decide el equilibrio:
        apretar mucho protege beneficio pero corta las ganadoras pronto; aflojar
        da recorrido a cambio de devolver más desde el pico.
        """
        arrancado = self._en_breakeven or self._trailing_desde_entrada
        if not (self._trailing and arrancado and self.restante > 0):
            return
        signo = self.direccion.signo
        self._peak = max(self._peak, precio) if signo > 0 else min(self._peak, precio)
        nuevo = self._peak - signo * self._riesgo * self._trailing_r
        # El stop solo se aprieta a favor, nunca se afloja.
        if signo > 0:
            self.stop_actual = max(self.stop_actual, nuevo)
        else:
            self.stop_actual = min(self.stop_actual, nuevo)
        # `_en_breakeven` significa "el stop ya no puede perder dinero". Con el
        # trailing corriendo desde la entrada hay que deducirlo del stop, no
        # darlo por hecho: si no, un stop inicial se anunciaría como "cierre en
        # break-even" cuando en realidad es una pérdida completa.
        if not self._en_breakeven:
            protegido = (self.stop_actual >= self.entrada if signo > 0
                         else self.stop_actual <= self.entrada)
            if protegido:
                self._en_breakeven = True

    def _r_en(self, precio: float) -> float:
        if self._riesgo <= 0:
            return 0.0
        return self.direccion.signo * (precio - self.entrada) / self._riesgo

    def _debe_cerrar_intradia(self, momento: datetime) -> bool:
        """True si hay que cerrar por ser intradía: cambió el día o llegó la hora."""
        if not self._cerrar_intradia:
            return False
        # Se razona por DÍA DE SESIÓN del oro (22:00->21:00 UTC), no por día de
        # calendario. Con el calendario, una operación abierta a las 22:30 —con
        # la sesión recién abierta y 22 h por delante— se cerraba a medianoche.
        sesion_ahora = dia_sesion(momento)
        sesion_apertura = dia_sesion(self.abierta_en)
        cambio_sesion = sesion_ahora > sesion_apertura
        # Fin de la sesión en curso: entre la hora de cierre y la reapertura.
        # En hora de MERCADO: entre el cierre operativo y la reapertura.
        h_mercado = hora_mercado(momento)
        fin_sesion = (sesion_ahora == sesion_apertura
                      and self._hora_cierre <= h_mercado < APERTURA_ET)
        return cambio_sesion or fin_sesion

    def cerrar_ahora(self, precio: float, momento: datetime,
                     motivo: str = "Cierre forzoso") -> List[EventoGestion]:
        """Cierra la operación YA al precio dado, pase lo que pase.

        Lo usa el cierre garantizado de fin de sesión: el aviso de salida no
        puede depender de que justo en ese minuto haya una ventana de vigilancia
        viva. Si ya está cerrada, no hace nada.
        """
        if self.estado is not EstadoOperacion.ABIERTA:
            return []
        self.r_acumulado += self.restante * self._r_en(precio)
        self.restante = 0.0
        self.estado = EstadoOperacion.CERRADA_MANUAL
        return [EventoGestion(
            Evento.CIERRE, momento, precio,
            f"{motivo} a {precio:.2f}. Resultado total: {self.r_acumulado:+.2f}R.",
            self.r_acumulado, cierra_operacion=True)]

    def actualizar(self, precio: float, momento: datetime) -> List[EventoGestion]:
        """Procesa un nuevo precio y devuelve los eventos de gestión generados."""
        if self.estado is not EstadoOperacion.ABIERTA:
            return []

        eventos: List[EventoGestion] = []
        signo = self.direccion.signo

        # 0) Cierre intradía forzado: nunca se mantiene una operación de un día
        #    para otro. Prioridad máxima (antes que stop/objetivos).
        if self._debe_cerrar_intradia(momento):
            self.r_acumulado += self.restante * self._r_en(precio)
            self.restante = 0.0
            self.estado = EstadoOperacion.CERRADA_MANUAL
            eventos.append(EventoGestion(
                Evento.CIERRE, momento, precio,
                f"Cierre INTRADÍA a {precio:.2f} (no se mantiene de un día para otro). "
                f"Resultado total: {self.r_acumulado:+.2f}R.",
                self.r_acumulado, cierra_operacion=True))
            return eventos

        # 1) ¿Toca el stop vigente? (comprobación pesimista, antes que los TP).
        toca_stop = (precio <= self.stop_actual) if signo > 0 else (precio >= self.stop_actual)
        if toca_stop:
            r_cierre = self._r_en(self.stop_actual)
            self.r_acumulado += self.restante * r_cierre
            self.restante = 0.0
            if self._en_breakeven:
                self.estado = EstadoOperacion.CERRADA_MANUAL
                if r_cierre > 0.01:
                    msg = (f"Cierre por STOP DINÁMICO a {self.stop_actual:.2f} "
                           f"(beneficio asegurado). Resultado total: {self.r_acumulado:+.2f}R.")
                else:
                    msg = (f"Cierre en BREAK-EVEN a {self.stop_actual:.2f}. "
                           f"Operación protegida. Resultado total: {self.r_acumulado:+.2f}R.")
                tipo = Evento.CIERRE
            else:
                self.estado = EstadoOperacion.CERRADA_SL
                msg = (f"STOP alcanzado a {self.stop_actual:.2f}. "
                       f"Salir. Resultado total: {self.r_acumulado:+.2f}R.")
                tipo = Evento.CIERRE
            eventos.append(EventoGestion(tipo, momento, self.stop_actual, msg,
                                         self.r_acumulado, cierra_operacion=True))
            return eventos

        # 2) ¿Se alcanzan objetivos? (en orden).
        for i, nivel in enumerate(self.niveles, start=1):
            if nivel.alcanzado:
                continue
            alcanzado = (precio >= nivel.precio) if signo > 0 else (precio <= nivel.precio)
            if not alcanzado:
                break
            nivel.alcanzado = True
            self.r_acumulado += nivel.fraccion * nivel.r_multiple
            self.restante -= nivel.fraccion
            # Si este objetivo cierra TODA la posición, el aviso de cierre que
            # viene justo después ya lo cuenta. Emitir además un "cierra parte"
            # mandaría DOS correos por el mismo hecho, y el primero diría "cierra
            # parte" de algo que se cierra entero: quien lo reciba cerrará y luego
            # verá un segundo aviso pidiéndole cerrar lo que ya no tiene.
            if self.restante > 1e-9:
                etiqueta = f"TP{i}" if len(self.niveles) > 1 else "Objetivo"
                eventos.append(EventoGestion(
                    Evento.TP_ALCANZADO, momento, nivel.precio,
                    f"{etiqueta} alcanzado a {nivel.precio:.2f} "
                    f"({nivel.r_multiple:.1f}R). Cerrar {nivel.fraccion:.0%} "
                    f"de la posición.",
                    self.r_acumulado,
                ))
            # Tras el primer objetivo: proteger a break-even. Solo tiene sentido si
            # queda posición viva: con un único objetivo que cierra el 100%, mandar
            # "mueve el stop" sobre una operación ya cerrada confunde a quien lo
            # recibe y le hace tocar el bróker sin motivo.
            if not self._en_breakeven and self.restante > 1e-9:
                self._en_breakeven = True
                self.stop_actual = self.entrada
                eventos.append(EventoGestion(
                    Evento.MOVER_STOP, momento, self.entrada,
                    f"Mover STOP a break-even ({self.entrada:.2f}). "
                    f"Operación sin riesgo a partir de ahora.",
                    self.r_acumulado,
                ))

        # 3) Salida dinámica: tras el break-even, el stop persigue al precio.
        self._trailing_stop(precio)

        # 4) ¿Se cerró toda la posición con los objetivos?
        if self.restante <= 1e-9 and self.estado is EstadoOperacion.ABIERTA:
            self.estado = EstadoOperacion.CERRADA_TP
            eventos.append(EventoGestion(
                Evento.CIERRE, momento, precio,
                f"Todos los objetivos alcanzados. Operación cerrada. "
                f"Resultado total: {self.r_acumulado:+.2f}R.",
                self.r_acumulado, cierra_operacion=True))

        return eventos

    @property
    def abierta(self) -> bool:
        return self.estado is EstadoOperacion.ABIERTA

    def a_dict(self) -> dict:
        """Serializa TODO el estado interno para poder reanudar en otra ejecución."""
        return {
            "direccion": self.direccion.value,
            "entrada": self.entrada,
            "riesgo": self._riesgo,
            "stop_actual": self.stop_actual,
            "en_breakeven": self._en_breakeven,
            "restante": self.restante,
            "r_acumulado": self.r_acumulado,
            "estado": self.estado.value,
            "abierta_en": self.abierta_en.isoformat(),
            "resumen": self.signal.resumen() if self.signal else "",
            "cerrar_intradia": self._cerrar_intradia,
            "hora_cierre_et": self._hora_cierre,
            "hora_cierre": self._hora_cierre,
            "trailing": self._trailing,
            "trailing_r": self._trailing_r,
            "trailing_desde_entrada": self._trailing_desde_entrada,
            "peak": self._peak,
            "probabilidad": self.probabilidad,
            "confianza": self.confianza,
            "stop_inicial": self.stop_inicial,
            "features": self.features,
            "motivos": self.motivos,
            "niveles": [
                [n.precio, n.fraccion, n.r_multiple, n.alcanzado] for n in self.niveles
            ],
        }

    @classmethod
    def desde_dict(cls, d: dict) -> "GestorOperaciones":
        """Reconstruye un gestor desde su estado serializado (sin necesitar la Signal)."""
        g = object.__new__(cls)
        g.signal = None
        g.direccion = Direccion(d["direccion"])
        g.entrada = d["entrada"]
        g._riesgo = d["riesgo"]
        g.stop_actual = d["stop_actual"]
        g._en_breakeven = d["en_breakeven"]
        g.restante = d["restante"]
        g.r_acumulado = d["r_acumulado"]
        g.estado = EstadoOperacion(d["estado"])
        g.abierta_en = datetime.fromisoformat(d["abierta_en"])
        g._cerrar_intradia = d.get("cerrar_intradia", True)
        # Hora de cierre operativo, en el reloj de NUEVA YORK. Ojo con el orden:
        # aquí había DOS asignaciones y la segunda pisaba a la primera, así que
        # la migración desde el nombre antiguo era código muerto y el valor por
        # defecto era 21 —la hora UTC de la época anterior—. Un 21 leído como
        # hora de Nueva York rompe en silencio el cierre de fin de sesión, porque
        # la condición "21 <= hora_mercado < 18" no se cumple NUNCA: la operación
        # se quedaría abierta hasta el cambio de sesión, ya con el mercado
        # cerrado. Es justo el síntoma que perseguimos. Una sola asignación, y el
        # defecto es 16 (16:00 en Nueva York).
        g._hora_cierre = _hora_cierre_de(d)
        g._trailing = d.get("trailing", True)
        g._trailing_r = float(d.get("trailing_r", 1.0))
        g._trailing_desde_entrada = bool(d.get("trailing_desde_entrada", True))
        g._peak = d.get("peak", d["entrada"])
        g.probabilidad = d.get("probabilidad", 0.0)
        g.confianza = d.get("confianza", 0.0)
        g.stop_inicial = d.get("stop_inicial", d["stop_actual"])
        g.features = d.get("features", {})
        g.motivos = list(d.get("motivos", []))
        g.niveles = [_NivelTP(p, f, r, alc) for p, f, r, alc in d["niveles"]]
        return g

    def resumen_estado(self, precio_actual: float | None = None) -> dict:
        """Estado serializable de la operación para el panel/API en vivo."""
        r_flotante = self._r_en(precio_actual) * self.restante if precio_actual else None
        return {
            "direccion": self.direccion.value,
            "entrada": round(self.entrada, 2),
            "stop_actual": round(self.stop_actual, 2),
            "en_breakeven": self._en_breakeven,
            "restante": round(self.restante, 2),
            "r_asegurado": round(self.r_acumulado, 2),
            "r_flotante": round(r_flotante, 2) if r_flotante is not None else None,
            "estado": self.estado.value,
            "objetivos": [
                {"precio": round(n.precio, 2), "r": n.r_multiple,
                 "fraccion": n.fraccion, "alcanzado": n.alcanzado}
                for n in self.niveles
            ],
        }
