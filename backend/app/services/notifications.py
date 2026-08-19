"""
Email notifications via Resend, for rule triggers and watchlist alerts.
Recipient resolution: notify the owner of the rule/watchlist item if they have
an email on file; otherwise (legacy/unowned rows, or an owner who registered
before email was required) fall back to the single admin NOTIFICATION_EMAIL,
so nothing fires silently with nowhere to send it.
"""

import httpx
from sqlalchemy.orm import Session
from app.core.config import settings
from app.api.auth import get_user_email

RESEND_URL = "https://api.resend.com/emails"
FROM_ADDRESS = "Polymarket Trader <alerts@polymarket-trader.com>"


def get_recipient_email(user_id: int | None) -> str | None:
    if user_id is not None:
        email = get_user_email(user_id)
        if email:
            return email
    return settings.notification_email or None


def send_notification(to_email: str, subject: str, body: str) -> bool:
    if not settings.resend_api_key:
        print("⚠️  RESEND_API_KEY not configured — skipping notification", flush=True)
        return False
    try:
        resp = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": FROM_ADDRESS, "to": [to_email], "subject": subject, "text": body},
            timeout=10,
        )
        resp.raise_for_status()
        print(f"📧 Notification sent to {to_email}: {subject}", flush=True)
        return True
    except Exception as e:
        print(f"⚠️  Failed to send notification to {to_email}: {e}", flush=True)
        return False


def notify_rule_event(user_id: int | None, subject: str, body: str) -> None:
    to_email = get_recipient_email(user_id)
    if to_email:
        send_notification(to_email, subject, body)
