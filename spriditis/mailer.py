from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from spriditis.config import AppSettings


def send_html_report(
    settings: AppSettings,
    html: str,
    *,
    subject: str,
    enabled: bool,
):
    if not enabled:
        print("📧 E-pasta nosūtīšana izslēgta.")
        return

    missing = []
    if not settings.smtp_user:
        missing.append("SMTP_USER")
    if not settings.smtp_app_password:
        missing.append("SMTP_APP_PASSWORD")
    if not settings.report_to:
        missing.append("REPORT_TO")

    if missing:
        raise RuntimeError(".env trūkst: " + ", ".join(missing))

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = settings.report_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(
        settings.smtp_host,
        settings.smtp_port,
        context=context,
    ) as server:
        server.login(settings.smtp_user, settings.smtp_app_password)
        server.sendmail(
            settings.smtp_user,
            [settings.report_to],
            msg.as_string(),
        )

    print(f"✅ Atskaite nosūtīta uz {settings.report_to}")
