"""
Email notifications via Resend — Lambda's copy of backend/app/services/notifications.py.
Same recipient-resolution logic: notify the rule/watchlist item's owner if they
have an email on file, otherwise fall back to the admin NOTIFICATION_EMAIL.
"""

import os
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
NOTIFICATION_EMAIL = os.environ.get("NOTIFICATION_EMAIL", "")
RESEND_URL = "https://api.resend.com/emails"
FROM_ADDRESS = "Polymarket Trader <alerts@polymarket-trader.com>"


def get_user_email(user_id: int, db: Session) -> str | None:
    row = db.execute(text("SELECT email FROM users WHERE id = :id"), {"id": user_id}).fetchone()
    return row[0] if row else None


def get_recipient_email(user_id, db: Session) -> str | None:
    if user_id is not None:
        email = get_user_email(user_id, db)
        if email:
            return email
    return NOTIFICATION_EMAIL or None


def send_notification(to_email: str, subject: str, body: str) -> bool:
    if not RESEND_API_KEY:
        print("⚠️  RESEND_API_KEY not configured — skipping notification")
        return False
    try:
        resp = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={"from": FROM_ADDRESS, "to": [to_email], "subject": subject, "text": body},
            timeout=10,
        )
        resp.raise_for_status()
        print(f"📧 Notification sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"⚠️  Failed to send notification to {to_email}: {e}")
        return False


def notify_rule_event(user_id, subject: str, body: str, db: Session) -> None:
    to_email = get_recipient_email(user_id, db)
    if to_email:
        send_notification(to_email, subject, body)
