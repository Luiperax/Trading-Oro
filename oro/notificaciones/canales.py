"""Canales concretos de notificación.

Ninguno guarda credenciales en el código: se leen de variables de entorno o se
pasan explícitamente. Los envíos de red usan ``requests`` con tiempo de espera
corto para que la alerta llegue en segundos.
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .base import Evento, Notificador


class NotificadorConsola(Notificador):
    """Imprime por consola. Útil en desarrollo, backtesting y como respaldo."""

    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL,
               html: Optional[str] = None) -> bool:
        print(f"\n=== [{evento.value}] {titulo} ===\n{cuerpo}\n")
        return True


class NotificadorTelegram(Notificador):
    """Envía por la Bot API de Telegram (con formato HTML básico y emojis)."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None) -> None:
        self._token = token or os.getenv("ORO_TELEGRAM_TOKEN", "")
        self._chat_id = chat_id or os.getenv("ORO_TELEGRAM_CHAT_ID", "")

    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL,
               html: Optional[str] = None) -> bool:
        if not self._token or not self._chat_id:
            return False
        import requests

        # Telegram admite un HTML muy limitado; enviamos el título en negrita y
        # el cuerpo de texto (que ya lleva emojis), no la tarjeta HTML del email.
        texto = f"<b>{titulo}</b>\n\n{cuerpo}"
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        try:
            resp = requests.post(
                url,
                json={"chat_id": self._chat_id, "text": texto,
                      "parse_mode": "HTML", "disable_web_page_preview": True},
                timeout=5,
            )
            return resp.ok
        except Exception:  # noqa: BLE001
            return False


class NotificadorWebhook(Notificador):
    """POST JSON a una URL. Base para push (FCM), WhatsApp Business API, Slack…"""

    def __init__(self, url: Optional[str] = None) -> None:
        self._url = url or os.getenv("ORO_WEBHOOK_URL", "")

    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL,
               html: Optional[str] = None) -> bool:
        if not self._url:
            return False
        import requests

        try:
            resp = requests.post(
                self._url,
                json={"titulo": titulo, "cuerpo": cuerpo, "evento": evento.value, "html": html},
                timeout=5,
            )
            return resp.ok
        except Exception:  # noqa: BLE001
            return False


class NotificadorEmail(Notificador):
    """Envía por SMTP. Credenciales por parámetro o variables ``ORO_SMTP_*``.

    Si se proporciona ``html``, envía un correo multiparte con la tarjeta HTML
    elegante y el texto plano como respaldo (para clientes sin HTML)."""

    def __init__(
        self,
        host: Optional[str] = None,
        puerto: int = 587,
        usuario: Optional[str] = None,
        clave: Optional[str] = None,
        destino: Optional[str] = None,
    ) -> None:
        self._host = host or os.getenv("ORO_SMTP_HOST", "")
        self._puerto = int(os.getenv("ORO_SMTP_PUERTO", puerto))
        self._usuario = usuario or os.getenv("ORO_SMTP_USUARIO", "")
        self._clave = clave or os.getenv("ORO_SMTP_CLAVE", "")
        self._destino = destino or os.getenv("ORO_SMTP_DESTINO", "")

    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL,
               html: Optional[str] = None) -> bool:
        if not (self._host and self._usuario and self._destino):
            return False
        if html:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(cuerpo, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))
        else:
            msg = MIMEText(cuerpo, "plain", "utf-8")
        msg["Subject"] = titulo
        msg["From"] = self._usuario
        msg["To"] = self._destino
        try:
            with smtplib.SMTP(self._host, self._puerto, timeout=10) as s:
                s.starttls()
                if self._clave:
                    s.login(self._usuario, self._clave)
                s.send_message(msg)
            return True
        except Exception:  # noqa: BLE001
            return False
