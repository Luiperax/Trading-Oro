"""Ruptura del rango de sesión: la estrategia que SÍ aguanta el coste.

QUÉ HACE
--------
Cada día, a las 8:00 de Nueva York (14:00 en Madrid casi todo el año), mira el
rango que ha dejado la mañana de Londres —el máximo y el mínimo entre las 3:00 y
las 8:00 de Nueva York— y deja dos órdenes preparadas:

    · una COMPRA justo por encima del máximo, con el stop en el mínimo;
    · una VENTA  justo por debajo del mínimo,  con el stop en el máximo.

La que salte primero es la operación del día; la otra se cancela. Si a las 10:00
de Nueva York no ha saltado ninguna, se cancelan las dos y no hay operación.

POR QUÉ ESTA Y NO OTRA
----------------------
Se midieron tres reglas de sesión sobre 19,6 años de velas horarias reales
(Dukascopy, 118.452 velas). Dos murieron en la prueba de robustez y esta
sobrevivió. Resultados con un spread de 0.60 $/operación, en R por operación:

    regla                          ops/año   R/op      t   1ª mitad  2ª mitad
    rango de Londres roto en NY        207  +0.0687  3.38   +0.0816   +0.0575
    apertura de NY (1ª hora)           223  +0.0480  2.45   +0.0241   +0.0691
    rango asiático roto en Londres     247  +0.0079  0.32   +0.0275   -0.0088

Las mitades son 2006-2016 y 2016-2026, elegidas ANTES de mirar y no tocadas
después. Solo la primera regla es positiva en las dos: la del rango asiático
—que era la candidata inicial— pierde dinero en la segunda mitad, y la de la
apertura de Nueva York solo funciona en la segunda. Una regla que solo brilla en
la mitad que le conviene no es una regla, es una casualidad encontrada mirando.

También se perturbaron las horas (10 variantes: 2-8, 3-7, 4-8, cerrar a las 15,
etc.). Las 10 dan resultado positivo, así que no depende de acertar la hora
exacta. Y el walk-forward —elegir el filtro con los 5 años anteriores y operar
el sexto, sin mirar el futuro— da +0.1350 R/op con 10 de 15 años en positivo.

POR QUÉ EL COSTE AQUÍ NO LA MATA
--------------------------------
El sistema intradía arriesga 1.5 × ATR, que hoy son unos 27 $ pero de media
histórica solo 7.4 $: un spread de 1.45 $ se come 0.195 R, seis veces la ventaja
bruta. Aquí el riesgo es el rango ENTERO de la mañana de Londres: 10.3 $ de
media histórica y unos 24-30 $ hoy. El mismo spread pesa la mitad o menos.

Aun así, hay que decirlo claro: **con 1.45 $ esto tampoco gana.** Medido:

    spread   R/op      t       R/año   acierto   años+
    0.30 $  +0.1123   5.58     +23.3    46.2 %   18/20
    0.60 $  +0.0673   3.34     +14.0    44.7 %   14/20
    1.45 $  -0.0604  -2.99     -12.5    40.8 %    7/20

Y filtrar por "que el spread no se coma más de X R" no lo arregla: a 1.45 $ deja
33 operaciones al año con t = 0.63, o sea indistinguible de cero. Por eso el
plan NO se emite si ``coste_operacion`` supera ``coste_max`` (0.60 $ por
defecto): es preferible no operar a operar sabiendo que se pierde por costes.

LA SALIDA
---------
No hay objetivo cercano: la operación se CIERRA A MANO al final de la sesión
(21:50 en la hora del usuario). Medido, neto de 0.60 $:

    sin objetivo cercano              +0.0685 R/op   t 3.37
    objetivo a 3R (versión anterior)  +0.0501        t 2.77

El objetivo a 3R cortaba las ganadoras grandes y costaba un tercio de la
ventaja. Queda un objetivo a 10R como red de seguridad: se ejecuta 1 de cada
1.000 veces y cuesta 0.0012 R, así que no estorba y cubre el día en que el
precio se dispara y nadie está mirando.

Mover el stop a la entrada al llegar a 1R sube la ventaja a +0.0768 (t 3.91).
Va como paso OPCIONAL en el correo, porque exige mirar el móvil una vez.

LO QUE NO SE PUEDE OCULTAR
--------------------------
* 14 de 20 años en positivo, no 20. Hubo una racha mala larga: de 2017 a 2020
  pierde cuatro años seguidos incluso con spread de 0.60 $. Quien no pueda
  aguantar eso, que no la use.
* Acierta el 44.7 % de las veces. Gana porque las ganadoras son mayores, no
  porque acierte mucho. La mayoría de los días la operación pierde.
* 1R son 24-30 $ por onza hoy. Con 0.01 lotes (1 onza), eso es 24-30 € de
  riesgo por operación, un 0.8-1 % de 3.000 €. Es el lote mínimo: no se puede
  arriesgar menos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import List, Optional

from .config import ConfiguracionSistema
from .dominio import Direccion
# La zona del mercado (Nueva York) se resuelve donde ya estaba resuelta, con su
# respaldo para sistemas sin base de datos de zonas horarias. Duplicar aquí ese
# respaldo habría creado dos verdades que pueden separarse con el tiempo.
from .dominio.mercado import _zona_mercado, dia_sesion


@dataclass(frozen=True, slots=True)
class RangoSesion:
    """El máximo y el mínimo de la ventana previa (la mañana de Londres)."""

    alto: float
    bajo: float
    desde: datetime
    hasta: datetime
    velas: int

    @property
    def amplitud(self) -> float:
        """Alto menos bajo, en dólares por onza. Es el riesgo de la operación."""
        return self.alto - self.bajo


@dataclass(frozen=True, slots=True)
class OrdenPendiente:
    """Una de las dos órdenes del plan: precio de disparo, stop y objetivo."""

    direccion: Direccion
    entrada: float
    stop: float
    objetivo: float

    @property
    def riesgo(self) -> float:
        return abs(self.entrada - self.stop)


@dataclass(frozen=True, slots=True)
class SesgoAsiatico:
    """Lo que hizo la sesión asiática antes de que abriera Londres.

    Es el único dato disponible a las 8:00 de Nueva York que separa de verdad las
    dos rupturas: la que acompaña a Asia gana +0.0883 R por operación y la que va
    en contra +0.0133, o sea nada (ver `ConfiguracionRuptura`). Cuando la sesión
    asiática no se decide —cuerpo pequeño respecto a su rango— `direccion` es
    None y no hay favorita, que es lo que dicen los datos de esos días.
    """

    direccion: Optional[Direccion]
    cuerpo: float                   # cierre menos apertura, en dólares (con signo).
    rango: float                    # rango de la sesión asiática, en dólares.

    @property
    def fuerza(self) -> float:
        """Cuánto pesa el cuerpo dentro del rango, de 0 a 1."""
        return abs(self.cuerpo) / self.rango if self.rango > 0 else 0.0


@dataclass(frozen=True, slots=True)
class PlanRuptura:
    """El plan del día: dos órdenes, una ventana de validez y una hora de cierre."""

    dia: date
    rango: RangoSesion
    compra: OrdenPendiente
    venta: OrdenPendiente
    sesion_desde: datetime          # antes de esta hora no puede saltar ninguna orden.
    valido_hasta: datetime          # a esta hora se cancelan las que no hayan saltado.
    cierre_forzoso: datetime        # a esta hora se cierra lo que siga abierto.
    # Tamaño TEÓRICO en onzas: el que arriesgaría exactamente el % configurado.
    # NO es el que se teclea: el bróker no acepta menos de 0.01 lotes (1 onza),
    # así que el real puede ser mayor y con él la pérdida. Quien enseña una cifra
    # al usuario la recalcula sobre el lote real, en `oro.notificaciones.plan`.
    onzas: float
    coste_r: float                  # cuánto se come el spread, en múltiplos de R.
    r_objetivo: float               # objetivo en R (el mismo para las dos órdenes).
    sesgo: SesgoAsiatico            # qué hizo Asia, y por tanto cuál es la favorita.

    @property
    def favorita(self) -> Optional[Direccion]:
        """Cuál de las dos órdenes tiene más respaldo histórico, si alguna."""
        return self.sesgo.direccion

    def es_favorita(self, orden: "OrdenPendiente") -> bool:
        return self.favorita is not None and orden.direccion is self.favorita


@dataclass(slots=True)
class ResultadoPlan:
    """Lo que devuelve :func:`construir_plan`: el plan, o el motivo de que no haya."""

    plan: Optional[PlanRuptura] = None
    motivos_no: List[str] = field(default_factory=list)

    @property
    def hay_plan(self) -> bool:
        return self.plan is not None


def _en_hora_mercado(df, hora_ini: int, hora_fin: int, dia: date):
    """Filas del marco cuyo reloj de NUEVA YORK cae en [hora_ini, hora_fin) del día dado.

    Se filtra por la hora del MERCADO y no por UTC a propósito: el desfase entre
    UTC y Nueva York cambia dos veces al año, y con horas fijadas en UTC el rango
    se desplazaría una hora cada cambio de horario sin que nadie lo notase.
    """
    idx = df.index
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize(timezone.utc)
    local = idx.tz_convert(_zona_mercado())
    mascara = (local.hour >= hora_ini) & (local.hour < hora_fin) & (local.date == dia)
    return df[mascara]


def rango_previo(df, cfg: ConfiguracionSistema, dia: date) -> Optional[RangoSesion]:
    """Rango de la ventana previa (por defecto 3:00-8:00 de Nueva York) de ese día.

    Devuelve ``None`` si faltan velas: con la mitad de la mañana sin datos el
    rango sería más estrecho de lo real y las órdenes se pondrían demasiado
    cerca, así que es preferible no operar ese día.
    """
    c = cfg.ruptura
    trozo = _en_hora_mercado(df, c.rango_desde_et, c.rango_hasta_et, dia)
    if len(trozo) < c.velas_minimas:
        return None
    alto = float(trozo["high"].max())
    bajo = float(trozo["low"].min())
    if not (alto > bajo):
        return None
    return RangoSesion(
        alto=alto, bajo=bajo,
        desde=trozo.index[0].to_pydatetime(),
        hasta=trozo.index[-1].to_pydatetime(),
        velas=len(trozo),
    )


def sesgo_asiatico(df, cfg: ConfiguracionSistema, dia: date) -> SesgoAsiatico:
    """Dirección de la sesión asiática (por defecto 0:00-3:00 de Nueva York).

    Se mide como cierre menos apertura, y solo cuenta si ese cuerpo vale al menos
    ``sesgo_cuerpo_minimo`` de su propio rango. Sin ese requisito, media hora de
    ruido decidiría cuál de las dos órdenes se anuncia como la buena: los 885
    días de cuerpo pequeño miden -0.0162 R/op y sus dos lados se parecen, así que
    ahí lo honesto es no señalar ninguna.
    """
    c = cfg.ruptura
    trozo = _en_hora_mercado(df, c.sesgo_desde_et, c.sesgo_hasta_et, dia)
    if len(trozo) < 2:
        return SesgoAsiatico(direccion=None, cuerpo=0.0, rango=0.0)
    cuerpo = float(trozo["close"].iloc[-1]) - float(trozo["open"].iloc[0])
    rango = float(trozo["high"].max()) - float(trozo["low"].min())
    sesgo = SesgoAsiatico(direccion=None, cuerpo=cuerpo, rango=rango)
    if sesgo.fuerza < c.sesgo_cuerpo_minimo or cuerpo == 0:
        return sesgo
    return SesgoAsiatico(
        direccion=Direccion.COMPRA if cuerpo > 0 else Direccion.VENTA,
        cuerpo=cuerpo, rango=rango,
    )


def _a_las(dia: date, hora_et: int) -> datetime:
    """Instante UTC correspondiente a esa hora en punto de Nueva York, ese día."""
    local = datetime(dia.year, dia.month, dia.day, hora_et, tzinfo=_zona_mercado())
    return local.astimezone(timezone.utc)


def construir_plan(df, cfg: ConfiguracionSistema,
                   ahora: Optional[datetime] = None) -> ResultadoPlan:
    """Construye el plan de ruptura del día, o explica por qué no lo hay.

    ``df`` es el histórico de velas horarias con índice UTC. ``ahora`` permite
    fijar el instante en las pruebas; por defecto es la hora real.
    """
    from .riesgo import dimensionar_posicion

    c = cfg.ruptura
    r = cfg.riesgo
    ahora = ahora or datetime.now(timezone.utc)
    res = ResultadoPlan()

    if not c.activa:
        res.motivos_no.append("La ruptura de sesión está desactivada en la configuración.")
        return res

    # El coste manda. Por encima del umbral la ventaja medida es negativa, así
    # que emitir el plan sería mandar a alguien a perder dinero con buenos modales.
    if r.coste_operacion > c.coste_max:
        res.motivos_no.append(
            f"Tu coste por operación ({r.coste_operacion:.2f} $/oz) supera el máximo "
            f"al que esta estrategia gana ({c.coste_max:.2f} $/oz). Medido: a 0.60 $ "
            f"da +0.069 R por operación, y a 1.45 $ da -0.059 R. No se emite el plan.")
        return res

    dia = dia_sesion(ahora)
    rango = rango_previo(df, cfg, dia)
    if rango is None:
        res.motivos_no.append(
            f"No hay velas suficientes de la mañana de Londres ({c.rango_desde_et}:00-"
            f"{c.rango_hasta_et}:00 de Nueva York) para medir el rango del día.")
        return res

    riesgo = rango.amplitud
    coste_r = r.coste_operacion / riesgo if riesgo > 0 else 1.0
    if coste_r > c.coste_r_max:
        res.motivos_no.append(
            f"Con un rango de {riesgo:.2f} $, tu spread se llevaría {coste_r:.1%} de "
            f"lo que arriesgas (máximo {c.coste_r_max:.0%}): el rango de hoy es "
            f"demasiado estrecho para lo que cuesta operar. Hoy no compensa.")
        return res

    # ¿Ha empezado ya la sesión y el rango YA se ha roto? Pasa cuando GitHub
    # retrasa la tarea, cuando se lanza a mano a media tarde, o cuando el propio
    # correo llega tarde. Mandar entonces las órdenes sería mandarlas a un precio
    # que el mercado ya ha dejado atrás: la orden se ejecutaría al instante y muy
    # lejos del borde del rango, que es justo lo contrario de lo que se busca.
    ya_abierta = _en_hora_mercado(df, c.sesion_desde_et, 24, dia)
    if len(ya_abierta):
        alto_ses = float(ya_abierta["high"].max())
        bajo_ses = float(ya_abierta["low"].min())
        if alto_ses > rango.alto or bajo_ses < rango.bajo:
            res.motivos_no.append(
                f"El rango ({rango.bajo:.2f}-{rango.alto:.2f}) ya se ha roto desde "
                f"que abrió Nueva York. Las órdenes llegarían tarde y se "
                f"ejecutarían muy lejos del borde: hoy no se manda plan.")
            return res

    onzas = dimensionar_posicion(riesgo, cfg)
    plan = PlanRuptura(
        dia=dia,
        rango=rango,
        compra=OrdenPendiente(
            direccion=Direccion.COMPRA,
            entrada=rango.alto,
            stop=rango.bajo,
            objetivo=rango.alto + c.r_objetivo * riesgo,
        ),
        venta=OrdenPendiente(
            direccion=Direccion.VENTA,
            entrada=rango.bajo,
            stop=rango.alto,
            objetivo=rango.bajo - c.r_objetivo * riesgo,
        ),
        sesion_desde=_a_las(dia, c.sesion_desde_et),
        valido_hasta=_a_las(dia, c.sesion_desde_et + c.horas_validez),
        cierre_forzoso=_a_las(dia, c.cierre_et),
        onzas=onzas,
        coste_r=coste_r,
        r_objetivo=c.r_objetivo,
        sesgo=sesgo_asiatico(df, cfg, dia),
    )
    res.plan = plan
    return res


def direccion_disparada(plan: PlanRuptura, alto: float, bajo: float) -> Optional[Direccion]:
    """¿Qué orden habría saltado con ese máximo y mínimo? ``None`` si ninguna.

    Si el precio ha tocado los DOS lados no se puede saber cuál saltó primero sin
    bajar de marco temporal, así que se devuelve ``None``: mejor no registrar una
    operación inventada que adivinar el orden.
    """
    arriba = alto > plan.compra.entrada
    abajo = bajo < plan.venta.entrada
    if arriba and abajo:
        return None
    if arriba:
        return Direccion.COMPRA
    if abajo:
        return Direccion.VENTA
    return None


__all__ = [
    "RangoSesion",
    "SesgoAsiatico",
    "sesgo_asiatico",
    "OrdenPendiente",
    "PlanRuptura",
    "ResultadoPlan",
    "rango_previo",
    "construir_plan",
    "direccion_disparada",
]
