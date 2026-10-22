"""
Multi-provider email dispatcher.
Supports SMTP (Gmail, Outlook, custom), Resend API, SendGrid API, and Mock/Dry-Run mode.
"""

import smtplib
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List
import requests

from config import Config, logger, BASE_DIR

MOCK_DELIVERY_LOG = BASE_DIR / "email_deliveries.log"


def parse_recipients(recipient_str: str) -> List[str]:
    """Splits comma or semicolon separated recipients and strips whitespace."""
    delimiters = [",", ";"]
    res = [recipient_str]
    for d in delimiters:
        new_res = []
        for item in res:
            new_res.extend(item.split(d))
        res = new_res
    return [r.strip() for r in res if r.strip()]


def send_via_mock(
    recipients: List[str],
    subject: str,
    body: str,
    is_html: bool,
    from_addr: str,
    reason: str = "Dry run mode / No credentials provided"
) -> Dict[str, Any]:
    """Simulates email delivery by appending to email_deliveries.log."""
    timestamp = datetime.now().isoformat()
    record = {
        "timestamp": timestamp,
        "mode": "MOCK_DRY_RUN",
        "reason": reason,
        "from": from_addr or "mock@localhost",
        "recipients": recipients,
        "subject": subject,
        "is_html": is_html,
        "body_preview": body[:200] + ("..." if len(body) > 200 else "")
    }

    with open(MOCK_DELIVERY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.warning(
        f"[DRY-RUN / MOCK] Email to {recipients} with subject '{subject}' logged to {MOCK_DELIVERY_LOG}. "
        f"Reason: {reason}"
    )

    return {
        "success": True,
        "provider": "mock",
        "message": f"[DRY-RUN] Email simulated successfully. Details recorded in {MOCK_DELIVERY_LOG.name}.",
        "reason": reason
    }


def send_via_smtp(
    recipients: List[str],
    subject: str,
    body: str,
    is_html: bool,
    from_addr: str
) -> Dict[str, Any]:
    """Sends email using standard SMTP (e.g. Gmail App Password, Outlook, etc.)."""
    if not Config.is_smtp_configured():
        raise ValueError("SMTP is not properly configured. Check SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in .env.")

    from_addr = from_addr or Config.SMTP_DEFAULT_FROM or Config.SMTP_USER

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)

    if is_html:
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        msg.attach(MIMEText(body, "plain", "utf-8"))

    if Config.SMTP_USE_SSL:
        # SSL direct connection (usually port 465)
        with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30) as server:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.sendmail(from_addr, recipients, msg.as_string())
    else:
        # Standard connection with optional STARTTLS (usually port 587)
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30) as server:
            if Config.SMTP_USE_TLS:
                server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            server.sendmail(from_addr, recipients, msg.as_string())

    logger.info(f"Email sent via SMTP to {recipients}: '{subject}'")
    return {
        "success": True,
        "provider": "smtp",
        "message": f"Email successfully sent via SMTP ({Config.SMTP_HOST}) to {recipients}."
    }


def send_via_resend(
    recipients: List[str],
    subject: str,
    body: str,
    is_html: bool,
    from_addr: str
) -> Dict[str, Any]:
    """Sends email via Resend REST API."""
    if not Config.is_resend_configured():
        raise ValueError("Resend API key is not configured in .env.")

    from_addr = from_addr or Config.RESEND_DEFAULT_FROM or "onboarding@resend.dev"

    payload = {
        "from": from_addr,
        "to": recipients,
        "subject": subject,
    }
    if is_html:
        payload["html"] = body
    else:
        payload["text"] = body

    headers = {
        "Authorization": f"Bearer {Config.RESEND_API_KEY}",
        "Content-Type": "application/json"
    }

    resp = requests.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=20)
    if resp.status_code in (200, 201):
        data = resp.json()
        logger.info(f"Email sent via Resend API (ID: {data.get('id')}) to {recipients}")
        return {
            "success": True,
            "provider": "resend",
            "message": f"Email successfully sent via Resend API (ID: {data.get('id')}) to {recipients}.",
            "api_response": data
        }
    else:
        raise RuntimeError(f"Resend API error [{resp.status_code}]: {resp.text}")


def send_via_sendgrid(
    recipients: List[str],
    subject: str,
    body: str,
    is_html: bool,
    from_addr: str
) -> Dict[str, Any]:
    """Sends email via SendGrid REST API."""
    if not Config.is_sendgrid_configured():
        raise ValueError("SendGrid API key is not configured in .env.")

    from_addr = from_addr or Config.SENDGRID_DEFAULT_FROM
    if not from_addr:
        raise ValueError("SendGrid requires a verified sender address (SENDGRID_DEFAULT_FROM in .env).")

    payload = {
        "personalizations": [
            {"to": [{"email": r} for r in recipients]}
        ],
        "from": {"email": from_addr},
        "subject": subject,
        "content": [
            {
                "type": "text/html" if is_html else "text/plain",
                "value": body
            }
        ]
    }

    headers = {
        "Authorization": f"Bearer {Config.SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    resp = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers, timeout=20)
    if resp.status_code in (200, 202):
        logger.info(f"Email sent via SendGrid API to {recipients}")
        return {
            "success": True,
            "provider": "sendgrid",
            "message": f"Email successfully accepted by SendGrid API for {recipients}."
        }
    else:
        raise RuntimeError(f"SendGrid API error [{resp.status_code}]: {resp.text}")


def dispatch_email(
    recipient: str,
    subject: str,
    body: str,
    is_html: bool = False,
    requested_provider: str = "auto",
    from_addr: str = ""
) -> Dict[str, Any]:
    """
    Main entry point for dispatching an email.
    Selects the effective provider and executes delivery.
    """
    recipients = parse_recipients(recipient)
    if not recipients:
        raise ValueError("Recipient address cannot be empty.")

    # Force mock mode if dry-run is globally enabled
    if Config.EMAIL_DRY_RUN:
        return send_via_mock(recipients, subject, body, is_html, from_addr, reason="EMAIL_DRY_RUN=true")

    provider = Config.get_effective_provider(requested_provider)

    try:
        if provider == "smtp":
            if not Config.is_smtp_configured():
                return send_via_mock(
                    recipients, subject, body, is_html, from_addr,
                    reason="SMTP selected but credentials (SMTP_HOST/USER/PASSWORD) not filled in .env"
                )
            return send_via_smtp(recipients, subject, body, is_html, from_addr)

        elif provider == "resend":
            if not Config.is_resend_configured():
                return send_via_mock(
                    recipients, subject, body, is_html, from_addr,
                    reason="Resend selected but RESEND_API_KEY not filled in .env"
                )
            return send_via_resend(recipients, subject, body, is_html, from_addr)

        elif provider == "sendgrid":
            if not Config.is_sendgrid_configured():
                return send_via_mock(
                    recipients, subject, body, is_html, from_addr,
                    reason="SendGrid selected but SENDGRID_API_KEY not filled in .env"
                )
            return send_via_sendgrid(recipients, subject, body, is_html, from_addr)

        else:
            # Fallback mock mode
            return send_via_mock(
                recipients, subject, body, is_html, from_addr,
                reason="No email credentials configured in .env (Add SMTP or Resend/SendGrid credentials to send live emails)"
            )

    except Exception as e:
        logger.error(f"Failed to dispatch email via {provider}: {e}")
        raise
