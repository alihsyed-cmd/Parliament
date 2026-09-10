"""
Postmark delivery and shared email furniture for election reminders.

Shared because the reminder emails have two senders that must produce identical
headers: reminders.py sends the confirmation from inside a request, and
scripts/send_election_reminders.py sends the advance and day-of waves from a
cron. If those two composed their own headers, the unsubscribe link would work
in one and not the other.

Reminders go out on the `broadcast` message stream, not `outbound`. Postmark
requires bulk mail to be separated from transactional mail, and mixing them
puts the candidate claim links — which must arrive — behind the reputation of a
mailing list. The confirmation email is the one exception: it is transactional
by any definition (a direct reply to an action the recipient just took) and is
sent on `outbound`.
"""

import logging
import os

import requests

logger = logging.getLogger(__name__)

POSTMARK_ENDPOINT = "https://api.postmarkapp.com/email"
POSTMARK_SERVER_TOKEN = os.getenv("POSTMARK_SERVER_TOKEN")

APP_BASE_URL = os.getenv("APP_BASE_URL", "https://parliamentapp.ca").rstrip("/")
FROM_ADDRESS = os.getenv("REMINDER_FROM_ADDRESS", "Parliament <reminders@send.parliamentapp.ca>")
REPLY_TO_ADDRESS = os.getenv("CLAIM_REPLY_TO", "info@parliamentapp.ca")
UNSUBSCRIBE_MAILTO = os.getenv("REMINDER_UNSUBSCRIBE_MAILTO", "unsubscribe@parliamentapp.ca")


def header_safe(value: str) -> str:
    """
    Strip CR/LF before any value reaches an email header.

    Same guard as claim.py's: a newline in an attacker-supplied address turns
    into an injected Bcc or Subject. Applied to headers only, never the body.
    """
    return (value or "").replace("\r", " ").replace("\n", " ").strip()


def confirm_url(token: str) -> str:
    return f"{APP_BASE_URL}/reminders/confirm?token={token}"


def manage_url(token: str) -> str:
    return f"{APP_BASE_URL}/reminders/manage?token={token}"


def unsubscribe_url(token: str) -> str:
    return f"{APP_BASE_URL}/reminders/unsubscribe?token={token}"


def footer(manage_token: str) -> str:
    """The identical footer on every reminder. Required by CASL, which wants a
    working unsubscribe mechanism and a real identification of the sender."""
    return (
        "\n"
        "—\n"
        "You are receiving this because you asked Parliament to remind you about\n"
        "elections where you live, and confirmed that request by email.\n\n"
        f"Stop these reminders: {unsubscribe_url(manage_token)}\n"
        f"Change your postal code: {manage_url(manage_token)}\n\n"
        "Parliament is an independent, non-commercial project. It is not affiliated\n"
        "with any party, campaign, election authority, or level of government.\n"
        f"Questions: {REPLY_TO_ADDRESS}\n"
    )


def send(to_address: str, subject: str, text_body: str, manage_token: str,
         stream: str = "broadcast"):
    """
    Deliver one email. Returns the Postmark MessageID on success, None on any
    failure — callers stamp their own ledger from that return value.

    Never raises. Every caller is either inside a request that must not 500 or
    inside a loop over thousands of subscribers that must not abort on one bad
    address.
    """
    if not POSTMARK_SERVER_TOKEN:
        logger.error("POSTMARK_SERVER_TOKEN not set; cannot send reminder email")
        return None

    payload = {
        "From": FROM_ADDRESS,
        "To": header_safe(to_address),
        "ReplyTo": REPLY_TO_ADDRESS,
        "Subject": header_safe(subject)[:200],
        "TextBody": text_body,
        "MessageStream": stream,
        # One-click unsubscribe. Gmail and Yahoo require this on bulk mail, and
        # without it their users' only way to stop the mail is the spam button —
        # which costs the sending domain far more than an unsubscribe does.
        "Headers": [
            {
                "Name": "List-Unsubscribe",
                "Value": f"<{unsubscribe_url(manage_token)}>, <mailto:{UNSUBSCRIBE_MAILTO}>",
            },
            {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"},
        ],
    }

    try:
        resp = requests.post(
            POSTMARK_ENDPOINT,
            json=payload,
            headers={
                "X-Postmark-Server-Token": POSTMARK_SERVER_TOKEN,
                "Accept": "application/json",
            },
            timeout=15,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200:
            return data.get("MessageID")
        # Log the code, never the address.
        logger.error("Postmark rejected send (HTTP %s, code %s)",
                     resp.status_code, data.get("ErrorCode"))
        return None
    except Exception:
        logger.exception("Postmark dispatch failed")
        return None
