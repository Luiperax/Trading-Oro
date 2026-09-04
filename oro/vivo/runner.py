"""Bucle de ejecución en vivo.

En cada ciclo:

1. Refresca los datos de precio y calcula el estado de mercado (ATR, sesión).
2. Consulta el sentimiento de prensa y el calendario macro (riesgo de noticia).
3. **Gestiona las operaciones abiertas** y notifica sus salidas (TP, break-even,
   stop, cierre).
4. Si procede (tope diario de 2–4 no alcanzado y hay hueco), busca una **nueva
   entrada A+** y la notifica.

El bucle está pensado para ejecutarse en la máquina del usuario (o un servidor).
Cada evento se envía por los canales configurados (Telegram, push, email…).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import List, Optional

from ..config import ConfiguracionSistema, cargar_configuracion
from ..datos import ProveedorDatos, ProveedorYahoo
from ..dominio import MarketSnapshot, Signal, sesion_de
from ..dominio.mercado import APERTURA_ET, dia_sesion, hora_mercado
from ..indicadores import atr as _atr
from ..notificaciones import Notificador, NotificadorConsola
from ..notificaciones.base import Evento
from ..senales import MotorSenales
from ..sentimiento import AnalizadorSentimiento, ContextoInformativo
from .gestor import GestorOperaciones


@dataclass(slots=True)
class CicloResultado:
    momento: datetime
    precio: float
    resumen_sentimiento: str
    eventos_salida: List[str] = field(default_factory=list)
    nueva_senal: Optional[Signal] = None
    motivo_sin_entrada: str = ""
    abiertas: int = 0
    senales_hoy: int = 0


class RunnerVivo:
    def __init__(
        self,
        cfg: Optional[ConfiguracionSistema] = None,
        proveedor: Optional[ProveedorDatos] = None,
        notificador: Optional[Notificador] = None,
        analizador: Optional[AnalizadorSentimiento] = None,
        modelo=None,
        max_concurrentes: int = 1,
        usar_sentimiento: bool = True,
    ) -> None:
        self.cfg = cfg or cargar_configuracion()
        self.proveedor = proveedor or ProveedorYahoo(timeframe=self.cfg.timeframe)
        self.notificador = notificador or NotificadorConsola()
        self.analizador = analizador or AnalizadorSentimiento()
        self.motor = MotorSenales(self.cfg, modelo=modelo)
        self.max_concurrentes = max_concurrentes
        self.usar_sentimiento = usar_sentimiento

        self.abiertas: List[GestorOperaciones] = []
        self._senales_hoy = 0
        self._perdida_r_hoy = 0.0                 # pérdida acumulada hoy, en R (tope diario).
        # Marca de la última vela que YA generó señal. Evita que el vigilante,
        # que revisa cada pocos minutos, vuelva a emitir la MISMA señal sobre la
        # misma vela cerrada (duplicaba la operación y el aviso).
        self._ultima_vela_senal: Optional[datetime] = None
        self._fecha: Optional[date] = None
        self.historial: List[dict] = []          # eventos recientes (entradas y salidas).
        self._ultimo_ciclo: Optional[CicloResultado] = None

    # ---- un ciclo del bucle ----
    def ciclo(self, velas: int = 500) -> CicloResultado:
        if hasattr(self.proveedor, "refrescar"):
            try:
                self.proveedor.refrescar()
            except Exception:  # noqa: BLE001 — un fallo de red no debe romper el bucle.
                pass
        df = self.proveedor.historico(velas)
        ultima = df.iloc[-1]
        momento = ultima.name.to_pydatetime()
        precio = float(ultima["close"])
        # Precio EN VIVO para GESTIONAR salidas (stop/objetivo) sin esperar al
        # cierre de la vela; si no está disponible, se usa el cierre. Las ENTRADAS
        # siguen decidiéndose con velas cerradas (df), para no repintar.
        precio_gestion = precio
        obtener_pa = getattr(self.proveedor, "precio_actual", None)
        if callable(obtener_pa):
            pa = obtener_pa()
            if pa is not None and pa > 0:
                precio_gestion = float(pa)
        # RELOJ para las decisiones de TIEMPO (cierre intradía, cambio de día,
        # "demasiado tarde para abrir"). Con datos en vivo hay que usar la hora
        # REAL: cuando el mercado cierra (noche/fin de semana) dejan de llegar
        # velas, la marca de la última vela se CONGELA y una operación se
        # quedaría abierta el fin de semana entero. Con datos sintéticos o de
        # backtest se usa la marca de la vela (determinista).
        ahora = self._reloj(momento)
        self._reset_diario(ahora)

        # Contexto informativo (sentimiento + riesgo de noticia). Es un
        # COMPLEMENTO: se nutre de fuentes externas (RSS, calendario macro) que
        # pueden caerse o tardar. Si falla, se sigue sin él. Lo contrario sería
        # grave: un RSS caído dejaría de gestionar las operaciones ABIERTAS, que
        # es lo único verdaderamente crítico.
        contexto = ContextoInformativo(None, 0, 0, False)
        if self.usar_sentimiento:
            try:
                contexto = self.analizador.analizar(momento)
            except Exception as e:  # noqa: BLE001
                print(f"⚠️  sentimiento no disponible ({type(e).__name__}); "
                      f"se continúa sin él.")

        resultado = CicloResultado(
            momento=momento, precio=precio,
            resumen_sentimiento=contexto.resumen(),
        )

        # 1) Gestionar salidas de las operaciones abiertas (con el precio EN VIVO).
        for gestor in list(self.abiertas):
            for ev in gestor.actualizar(precio_gestion, ahora):
                self._notificar_evento(ev, gestor)
                resultado.eventos_salida.append(ev.mensaje)
                self._registrar_historial({
                    "tipo": ev.tipo.value, "momento": ahora.isoformat(),
                    "precio": round(ev.precio, 2), "mensaje": ev.mensaje,
                    "r": round(ev.r_acumulado, 2),
                })
            if not gestor.abierta:
                # Tope de pérdida diaria: acumular las pérdidas del día (en R).
                if gestor.r_acumulado < 0:
                    self._perdida_r_hoy += abs(gestor.r_acumulado)
                self._registrar_operacion(gestor, ahora)
                self.abiertas.remove(gestor)
        resultado.abiertas = len(self.abiertas)

        # 2) ¿Buscar nueva entrada?
        r_cfg = self.cfg.riesgo
        # Intradía: no abrir cerca del cierre (no daría tiempo a cerrar el mismo día).
        # No se abre desde una hora antes del cierre hasta medianoche UTC.
        # Ojo: técnicamente a partir de las 22:00 ya hay sesión nueva con 22 h por
        # delante, así que podrían tomarse. Se midió sobre 874 días reales y NO
        # compensa: incluirlas empeora el resultado (PF 1.00 y -5.6R, frente a
        # PF 1.04 y +3.5R dejándolas fuera). Son horas de poca liquidez.
        tarde_para_intradia = (
            r_cfg.cerrar_intradia
            and r_cfg.hora_cierre_et - 1 <= hora_mercado(ahora) < APERTURA_ET
        )
        # Tope de pérdida diaria: si ya se ha perdido el máximo del día, no más operaciones.
        cap_perdida_r = (r_cfg.riesgo_diario_max / r_cfg.riesgo_por_operacion
                         if r_cfg.riesgo_por_operacion > 0 else 1e9)
        if self._perdida_r_hoy >= cap_perdida_r:
            resultado.motivo_sin_entrada = (
                f"Tope de pérdida diaria alcanzado ({self._perdida_r_hoy:.1f}R ≥ "
                f"{cap_perdida_r:.1f}R). No se abren más operaciones hoy.")
        elif len(self.abiertas) >= self.max_concurrentes:
            resultado.motivo_sin_entrada = "Máximo de operaciones simultáneas alcanzado."
        elif self._senales_hoy >= r_cfg.operaciones_max_dia:
            resultado.motivo_sin_entrada = "Tope diario de señales alcanzado."
        elif tarde_para_intradia:
            resultado.motivo_sin_entrada = "Demasiado tarde para abrir una operación intradía hoy."
        elif self._ultima_vela_senal is not None and momento <= self._ultima_vela_senal:
            resultado.motivo_sin_entrada = (
                "Esta vela ya generó su señal (no se repite la misma entrada).")
        else:
            snapshot = self._snapshot(df, momento, precio, contexto)
            analisis = self.motor.analizar(df, snapshot)
            if analisis.hay_operacion and analisis.signal is not None:
                gestor = GestorOperaciones(
                    analisis.signal, entrada_real=precio,
                    cerrar_intradia=r_cfg.cerrar_intradia,
                    hora_cierre_et=r_cfg.hora_cierre_et,
                    trailing_activo=r_cfg.trailing_activo,
                    trailing_r=r_cfg.trailing_r,
                )
                # La operación SOLO existe si el aviso llegó. Si no se pudo
                # enviar, el usuario no habría entrado: darla por abierta crearía
                # una operación fantasma que luego mandaría avisos de salida de
                # algo que nunca se abrió y falsearía el registro de aprendizaje.
                # No se marca la vela como avisada, así que se reintenta en el
                # ciclo siguiente (unos minutos después) sobre la misma señal.
                if not self.notificador.notificar_senal(analisis.signal):
                    print("⚠️  AVISO NO ENVIADO (entrada): NO se abre la operación; "
                          "se reintenta en el próximo ciclo. Revisa los secretos "
                          "ORO_SMTP_* / ORO_TELEGRAM_*.")
                    resultado.motivo_sin_entrada = (
                        "Señal encontrada pero el aviso no se pudo enviar: no se abre "
                        "la operación (se reintenta en el próximo ciclo).")
                else:
                    self.abiertas.append(gestor)
                    self._senales_hoy += 1
                    self._ultima_vela_senal = momento
                    resultado.nueva_senal = analisis.signal
                    s = analisis.signal
                    self._registrar_historial({
                        "tipo": "entrada", "momento": momento.isoformat(),
                        "direccion": s.direccion.value, "entrada": round(precio, 2),
                        "stop": round(s.stop_loss, 2),
                        "mensaje": s.resumen(), "prob": round(s.probabilidad, 2),
                    })
            else:
                resultado.motivo_sin_entrada = "; ".join(analisis.motivos_no) or analisis.mensaje

        resultado.senales_hoy = self._senales_hoy
        resultado.abiertas = len(self.abiertas)
        self._ultimo_ciclo = resultado
        return resultado

    def _registrar_historial(self, entrada: dict) -> None:
        self.historial.insert(0, entrada)
        del self.historial[50:]  # conservar solo los 50 eventos más recientes.

    def _registrar_operacion(self, gestor: "GestorOperaciones", momento) -> None:
        """Guarda un registro COMPLETO y permanente de la operación al cerrarse:
        datos de la señal + si se cumplió o no (resultado en R). Append-only JSONL.
        """
        import json
        from pathlib import Path

        registro = {
            "apertura": gestor.abierta_en.isoformat(),
            "cierre": momento.isoformat(),
            "direccion": gestor.direccion.value,
            "entrada": round(gestor.entrada, 2),
            "stop_inicial": round(gestor.stop_inicial, 2),
            "objetivos": [round(n.precio, 2) for n in gestor.niveles],
            "probabilidad": round(gestor.probabilidad, 3),
            "confianza": round(gestor.confianza, 3),
            "resultado_r": round(gestor.r_acumulado, 3),
            "ganada": gestor.r_acumulado > 0,
            "estado": gestor.estado.value,
            # Condiciones de la señal + etiqueta real: esto es lo que el sistema
            # usa para APRENDER por qué salió bien o mal.
            "features": getattr(gestor, "features", {}),
            "label": 1 if gestor.r_acumulado > 0 else 0,
        }
        try:
            ruta = Path(self.cfg.ruta_operaciones)
            if ruta.parent != Path(""):
                ruta.parent.mkdir(parents=True, exist_ok=True)
            with open(ruta, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001 — un fallo de registro no debe romper el ciclo.
            pass

    # ---- persistencia del estado entre ejecuciones (para GitHub Actions/cron) ----
    def guardar_estado(self, ruta) -> None:
        """Guarda operaciones abiertas, contador diario e historial en un JSON."""
        import json
        from pathlib import Path

        datos = {
            "fecha": self._fecha.isoformat() if self._fecha else None,
            "senales_hoy": self._senales_hoy,
            "perdida_r_hoy": round(self._perdida_r_hoy, 3),
            # Sin esto, cada nueva ejecución volvería a emitir la señal de la
            # última vela ya avisada (aviso y operación duplicados).
            "ultima_vela_senal": (self._ultima_vela_senal.isoformat()
                                  if self._ultima_vela_senal else None),
            "historial": self.historial,
            "abiertas": [g.a_dict() for g in self.abiertas],
        }
        p = Path(ruta)
        if p.parent != Path(""):
            p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def cargar_estado(self, ruta) -> None:
        """Carga el estado previo si el fichero existe (si no, empieza limpio)."""
        import json
        from datetime import date
        from pathlib import Path

        p = Path(ruta)
        if not p.exists():
            return
        try:
            datos = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            # Un estado ilegible no puede dejar el sistema muerto para siempre:
            # se arranca limpio y se avisa. El fichero está versionado en el
            # repositorio, así que la versión buena se puede recuperar.
            print(f"⚠️  ESTADO ILEGIBLE ({type(e).__name__}): se arranca sin "
                  f"operaciones. Si tenías alguna abierta, revísala en el bróker.")
            return
        self._fecha = date.fromisoformat(datos["fecha"]) if datos.get("fecha") else None
        self._senales_hoy = int(datos.get("senales_hoy", 0))
        self._perdida_r_hoy = float(datos.get("perdida_r_hoy", 0.0))
        uvs = datos.get("ultima_vela_senal")
        self._ultima_vela_senal = datetime.fromisoformat(uvs) if uvs else None
        self.historial = list(datos.get("historial", []))
        self.abiertas = [GestorOperaciones.desde_dict(x) for x in datos.get("abiertas", [])]

    def estado(self) -> dict:
        """Instantánea serializable del estado en vivo (para el panel/API)."""
        r = self._ultimo_ciclo
        precio = r.precio if r else None
        return {
            "actualizado": r.momento.isoformat() if r else None,
            "precio": round(precio, 2) if precio else None,
            "sentimiento": r.resumen_sentimiento if r else "sin datos aún",
            "senales_hoy": self._senales_hoy,
            "tope_diario": self.cfg.riesgo.operaciones_max_dia,
            "motivo_sin_entrada": r.motivo_sin_entrada if r else "",
            "abiertas": [g.resumen_estado(precio) for g in self.abiertas],
            "historial": list(self.historial),
        }

    # ---- bucle continuo (para la máquina del usuario) ----
    def ejecutar(self, intervalo_seg: int = 900, max_ciclos: Optional[int] = None) -> None:
        """Ejecuta el bucle indefinidamente (o ``max_ciclos`` veces).

        ``intervalo_seg`` por defecto 15 min (coincide con el timeframe M15).
        """
        import time

        ciclos = 0
        print(f"▶ Runner en vivo iniciado (intervalo {intervalo_seg}s, "
              f"máx {self.cfg.riesgo.operaciones_max_dia} señales/día).")
        while max_ciclos is None or ciclos < max_ciclos:
            try:
                r = self.ciclo()
                print(f"[{r.momento:%Y-%m-%d %H:%M}] oro={r.precio:.2f} | "
                      f"{r.resumen_sentimiento} | abiertas={r.abiertas} señales_hoy={r.senales_hoy}")
                if r.nueva_senal:
                    print("   → NUEVA ENTRADA:", r.nueva_senal.resumen())
                for ev in r.eventos_salida:
                    print("   → SALIDA:", ev)
            except Exception as e:  # noqa: BLE001 — el bucle no debe caerse.
                print("   ! error en el ciclo:", type(e).__name__, str(e)[:80])
            ciclos += 1
            if max_ciclos is not None and ciclos >= max_ciclos:
                break
            time.sleep(intervalo_seg)

    # ---- helpers ----
    def _reloj(self, momento: datetime) -> datetime:
        """Hora que manda en las decisiones de TIEMPO.

        Con una fuente EN VIVO se usa la hora real UTC. Es imprescindible: al
        cerrar el mercado dejan de publicarse velas, así que la marca de la
        última vela se queda congelada (un viernes a las 21:00 sigue diciendo
        "viernes 21:00" todo el fin de semana) y el cierre intradía nunca se
        dispararía. Con fuentes sintéticas o de backtest se respeta la marca de
        la vela para que el comportamiento sea determinista.
        """
        if getattr(self.proveedor, "en_vivo", False):
            return datetime.now(timezone.utc)
        return momento

    def _reset_diario(self, momento: datetime) -> None:
        # Por día de SESIÓN: los topes diarios deben acompañar a la sesión real
        # del oro (22:00->21:00 UTC), no reiniciarse a medianoche en mitad de ella.
        hoy = dia_sesion(momento)
        if self._fecha != hoy:
            self._fecha = hoy
            self._senales_hoy = 0
            self._perdida_r_hoy = 0.0

    def _snapshot(self, df, momento, precio, contexto: ContextoInformativo) -> MarketSnapshot:
        atr_val = float(_atr(df, 14).iloc[-1])
        spread = float(df.iloc[-1].get("spread", 0.2))
        return MarketSnapshot(
            momento=momento, precio=precio, spread=spread, atr=atr_val,
            sesion=sesion_de(momento),
            sentimiento=contexto.sentimiento,
            riesgo_noticia_alta=contexto.riesgo_noticia_alta,
        )

    def _notificar_evento(self, ev, gestor: GestorOperaciones) -> None:
        # Títulos claros y accionables para las SALIDAS.
        titulos = {
            Evento.TP_ALCANZADO: "🎯 CIERRA PARTE — objetivo alcanzado (XAU/USD)",
            Evento.MOVER_STOP: "🛡 MUEVE EL STOP a break-even (XAU/USD)",
            Evento.CIERRE: "🚪 SAL DE LA OPERACIÓN — cierre (XAU/USD)",
        }
        titulo = titulos.get(ev.tipo, "Actualización — XAU/USD")
        from ..tiempo import etiqueta_zona, hora_local
        hora = f"{hora_local(ev.momento)} {etiqueta_zona(ev.momento)}"
        cuerpo_txt = (f"{ev.mensaje}\n\nQué hacer: {self._instruccion(ev.tipo)}\n"
                      f"Hora: {hora}\n"
                      f"Dirección: {gestor.direccion.value.upper()} | Entrada: {gestor.entrada:.2f}")
        # El cuerpo se compone como HTML a propósito (negritas, saltos). Las
        # piezas de texto se escapan AQUÍ, que es donde se sabe cuáles lo son.
        from ..notificaciones.base import _esc
        cuerpo_html = (f"<b>{_esc(self._instruccion(ev.tipo))}</b><br>{_esc(ev.mensaje)}<br><br>"
                       f"<span style='color:#8A93A3;'>Hora: <b>{_esc(hora)}</b> · Dirección: "
                       f"<b>{gestor.direccion.value.upper()}</b> · Entrada: <b>{gestor.entrada:.2f}</b></span>")
        # Datos estructurados para que la tarjeta se pueda MAQUETAR (resultado
        # grande y a color, entrada -> salida, chips de contexto) en vez de ser
        # un párrafo de texto corrido.
        datos = {
            "accion": self._instruccion(ev.tipo),
            "motivo": ev.mensaje.split(".")[0].strip(),
            "r": round(ev.r_acumulado, 2),
            "etiqueta_r": ("Asegurado hasta ahora" if ev.tipo is Evento.TP_ALCANZADO
                           else "Resultado total"),
            "entrada": gestor.entrada,
            "salida": ev.precio,
            "direccion": gestor.direccion.value.upper(),
            "hora": hora,
            "restante": (f"{gestor.restante:.0%}"
                         if gestor.abierta and gestor.restante > 0 else None),
        }
        from ..notificaciones.base import mensaje_html_evento
        ok = self.notificador.enviar(
            titulo, cuerpo_txt, ev.tipo,
            html=mensaje_html_evento(titulo, cuerpo_html, ev.tipo, datos))
        if not ok:
            print(f"⚠️  AVISO NO ENVIADO (salida): {titulo}. Revisa la configuración de email/Telegram.")

    @staticmethod
    def _instruccion(tipo: Evento) -> str:
        return {
            Evento.TP_ALCANZADO: "Cierra la parte indicada de la posición y asegura beneficio.",
            Evento.MOVER_STOP: "Mueve el stop al punto de entrada (break-even): riesgo cero.",
            Evento.CIERRE: "Cierra la operación completa AHORA.",
        }.get(tipo, "Revisa la operación.")
