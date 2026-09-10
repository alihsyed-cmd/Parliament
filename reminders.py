"""
Election reminders — blueprint.

A voter gives us an email address and a postal code; we mail them a
confirmation link, and once they click it we mail them seven days before and on
the morning of every future election they can vote in.

Endpoints
  POST /reminders/subscribe            start a subscription (mails a confirm link)
  POST /reminders/confirm              redeem the confirm link
  GET  /reminders/subscription         manage-page payload for a manage token
  POST /reminders/subscription         change the postal code on a subscription
  POST /reminders/unsubscribe          stop (also serves List-Unsubscribe one-click)
  GET  /reminders/preview              what a postal code would be reminded about
  POST /reminders/webhook/postmark     bounce / complaint / delivery events

Sending is not here. The confirmation is transactional and goes out on this
request's background thread; the advance and day-of waves belong to
scripts/send_election_reminders.py, which runs on a cron.

THE LOAD-BEARING RULES

1. Nothing is mailed to an address that has not confirmed. `pending` receives
   exactly one thing — the confirmation — and the confirmation is the only mail
   an unverified address can ever cause.

2. Every state change that causes an email is claimed with a guarded UPDATE
   whose WHERE clause re-checks the precondition, and only a caller that gets a
   row back does the sending. Two concurrent submissions of the same form
   therefore produce one email, not two. This is the same claim-before-send
   pattern the reminder_sends ledger uses in the cron.

3. /subscribe returns one identical body for every outcome — new, already
   pending, already active, rate-limited, previously complained. The endpoint
   is public and unauthenticated, so a response that varied would be a free
   oracle for testing whether an address is subscribed.
"""

import datetime as dt
import logging
import os
import re
import secrets
import threading

import db
import mailer
from flask import Blueprint, current_app, jsonify, request
from geo import normalize_postal_code, resolve_jurisdiction_slugs, validate_postal_code

logger = logging.getLogger(__name__)

reminders_bp = Blueprint("reminders", __name__)

LANG = "en"

# Deliberately permissive. Its job is to reject obvious junk and anything that
# could not survive an SMTP envelope, not to adjudicate RFC 5322 — the
# confirmation email is the real validator, and a rejected-but-valid address is
# a lost subscriber for no gain.
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

MAX_EMAIL_LEN = 254          # RFC 5321 maximum path length
CONFIRMATION_RESEND_MINUTES = 5

# The identical response. Never varies by outcome — see rule 3 above.
OK_BODY = {
    "status": "ok",
    "lang": LANG,
    "message": "Check your email for a link to confirm your reminders.",
}


# ── Rate limits ──────────────────────────────────────────────────────────────
# In-memory, per worker, same trade-off documented on claim.py's contact limiter:
# resets on deploy and each Render worker counts separately, so the effective
# limit is (workers x these numbers). Acceptable because the honeypot catches
# most automation, the per-address throttle lives in the database where it is
# exact, and the blast radius of a miss is email volume rather than data.
LIMIT_SUBSCRIBE_PER_HOUR = 10
LIMIT_SUBSCRIBE_PER_DAY = 30

_subscribe_hits: dict = {}
_subscribe_lock = threading.Lock()


def _client_ip():
    """Requires ProxyFix in api.py; without it this is Render's proxy address."""
    return request.remote_addr or None


def _rate_limited(ip):
    """True if this IP is over either window. Prunes as it goes."""
    if ip is None:
        return False

    now = dt.datetime.now(dt.timezone.utc)
    hour_ago = now - dt.timedelta(hours=1)
    day_ago = now - dt.timedelta(days=1)

    with _subscribe_lock:
        hits = [t for t in _subscribe_hits.get(ip, []) if t > day_ago]

        if len(hits) >= LIMIT_SUBSCRIBE_PER_DAY:
            _subscribe_hits[ip] = hits
            return True
        if len([t for t in hits if t > hour_ago]) >= LIMIT_SUBSCRIBE_PER_HOUR:
            _subscribe_hits[ip] = hits
            return True

        hits.append(now)
        _subscribe_hits[ip] = hits

        if len(_subscribe_hits) > 5000:
            for k in [k for k, v in _subscribe_hits.items() if not v or max(v) < day_ago]:
                _subscribe_hits.pop(k, None)

    return False


# ── SQL ──────────────────────────────────────────────────────────────────────

# Insert if this (email, postal_code) is new. DO NOTHING on conflict rather than
# DO UPDATE, so an existing row falls through to the branch below where its
# prior status decides what happens — the one thing an upsert cannot express.
INSERT_SUBSCRIPTION_SQL = """
    INSERT INTO reminder_subscriptions
        (email, postal_code, status, confirm_token, manage_token, confirmation_sent_at)
    VALUES (%s, %s, 'pending', %s, %s, NOW())
    ON CONFLICT (email, postal_code) DO NOTHING
    RETURNING id, confirm_token, manage_token;
"""

SELECT_SUBSCRIPTION_SQL = """
    SELECT id, status, confirm_token, manage_token
    FROM reminder_subscriptions
    WHERE email = %s AND postal_code = %s;
"""

# Re-send the SAME confirmation link to a still-pending address. The throttle is
# in the WHERE clause, not in Python: that is what makes it exact across workers
# and what makes two simultaneous submissions send one email.
CLAIM_RESEND_SQL = """
    UPDATE reminder_subscriptions
    SET confirmation_sent_at = NOW()
    WHERE id = %s
      AND status = 'pending'
      AND (confirmation_sent_at IS NULL
           OR confirmation_sent_at < NOW() - (%s || ' minutes')::INTERVAL)
    RETURNING confirm_token, manage_token;
"""

# Someone who unsubscribed (or whose address bounced) signing up again. Consent
# starts over: new tokens, cleared timestamps, back to 'pending'. Reactivating
# them directly would be treating a months-old opt-out as current consent, and
# minting new tokens invalidates any link still sitting in an old inbox.
CLAIM_RESUBSCRIBE_SQL = """
    UPDATE reminder_subscriptions
    SET status = 'pending',
        confirm_token = %s,
        manage_token = %s,
        confirmed_at = NULL,
        unsubscribed_at = NULL,
        confirmation_sent_at = NOW()
    WHERE id = %s AND status IN ('unsubscribed', 'bounced')
    RETURNING confirm_token, manage_token;
"""

# Idempotent by design: 'active' is in the WHERE so a second click on the same
# link succeeds quietly instead of erroring at someone who did nothing wrong.
# 'unsubscribed' and 'complained' are excluded — an old confirmation link must
# not resurrect a subscription that has since been stopped.
CONFIRM_SQL = """
    UPDATE reminder_subscriptions
    SET status = 'active',
        confirmed_at = COALESCE(confirmed_at, NOW())
    WHERE confirm_token = %s AND status IN ('pending', 'active')
    RETURNING id, email, postal_code, manage_token;
"""

UNSUBSCRIBE_SQL = """
    UPDATE reminder_subscriptions
    SET status = 'unsubscribed',
        unsubscribed_at = COALESCE(unsubscribed_at, NOW())
    WHERE manage_token = %s AND status <> 'complained'
    RETURNING id, email, postal_code;
"""

SUBSCRIPTION_BY_MANAGE_TOKEN_SQL = """
    SELECT id, email, postal_code, status, confirmed_at
    FROM reminder_subscriptions
    WHERE manage_token = %s;
"""

UPDATE_POSTAL_CODE_SQL = """
    UPDATE reminder_subscriptions
    SET postal_code = %s
    WHERE manage_token = %s AND status IN ('pending', 'active')
    RETURNING id, postal_code;
"""

# The preview, and the manage page's "what you'll be reminded about" list.
# Unconfirmed dates are excluded for the same reason the sender refuses them: an
# estimate shown as a date is a promise we have not earned.
UPCOMING_ELECTIONS_SQL = """
    SELECT e.id, e.jurisdiction_slug, j.name, j.level, e.election_date,
           e.election_type, e.name, e.advance_voting_starts, e.info_url, e.district_id
    FROM elections e
    JOIN jurisdictions j ON j.slug = e.jurisdiction_slug
    WHERE e.jurisdiction_slug = ANY(%s)
      AND e.election_date >= CURRENT_DATE
      AND e.is_confirmed
    ORDER BY e.election_date, j.name;
"""

MARK_SUBSCRIPTION_EVENT_SQL = """
    UPDATE reminder_subscriptions
    SET status = %s, last_event_at = NOW()
    WHERE id = %s;
"""

SEND_BY_MESSAGE_ID_SQL = """
    SELECT subscription_id, election_id, kind
    FROM reminder_sends
    WHERE provider_message_id = %s;
"""

UPDATE_SEND_STATUS_SQL = """
    UPDATE reminder_sends
    SET status = %s
    WHERE provider_message_id = %s;
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _new_token() -> str:
    """256 bits, 43 URL-safe characters. Same strength as invitations.token."""
    return secrets.token_urlsafe(32)


def _normalize_email(raw: str) -> str:
    """Lowercase and strip. What makes the (email, postal_code) unique
    constraint mean one subscription per person rather than one per
    capitalisation."""
    return (raw or "").strip().lower()


def _upcoming_for_postal(postal_code: str, allow_remote: bool = True) -> list[dict]:
    slugs = resolve_jurisdiction_slugs(postal_code, allow_remote=allow_remote)
    if not slugs:
        return []
    rows = db.query(UPCOMING_ELECTIONS_SQL, (slugs,))
    return [
        {
            "id": str(r[0]),
            "jurisdiction_slug": r[1],
            "jurisdiction_name": r[2],
            "level": r[3],
            "election_date": r[4].isoformat() if r[4] else None,
            "election_type": r[5],
            "name": r[6],
            "advance_voting_starts": r[7].isoformat() if r[7] else None,
            "info_url": r[8],
        }
        for r in rows
    ]


def _confirmation_body(postal_code: str, confirm_token: str, manage_token: str,
                       upcoming: list[dict]) -> str:
    lines = [
        "You asked Parliament to remind you about elections.",
        "",
        f"Postal code: {postal_code}",
        "",
        "Confirm that request by opening this link:",
        "",
        f"  {mailer.confirm_url(confirm_token)}",
        "",
        "Until you do, we will not send you anything else.",
        "",
    ]

    if upcoming:
        lines += ["Once confirmed, we will remind you about:", ""]
        for e in upcoming[:6]:
            label = e["name"] or f"{e['jurisdiction_name']} election"
            lines.append(f"  {e['election_date']}  {label}")
        lines += [
            "",
            "We will email you seven days before each one and again on the morning",
            "of the vote — federal, provincial, and municipal, for as long as you",
            "want them.",
            "",
        ]
    else:
        lines += [
            "We do not have any confirmed election dates for that postal code yet.",
            "Your subscription still works: we will start reminding you as soon as",
            "an election there is called.",
            "",
        ]

    lines += [
        "If you did not ask for this, ignore this email. Nothing further will be",
        "sent and the request expires on its own.",
    ]
    return "\n".join(lines) + "\n" + mailer.footer(manage_token)


def _dispatch_confirmation(app, to_address, postal_code, confirm_token, manage_token):
    """
    Send the confirmation off the request thread.

    Same reasoning as claim.py's async dispatch: a Postmark round-trip is
    200-800ms and an already-subscribed no-op returns in about 5ms. Sending
    inline would make response latency a reliable oracle for whether an address
    is already on the list, which is exactly what the identical response body
    exists to prevent.
    """
    def run():
        with app.app_context():
            try:
                upcoming = _upcoming_for_postal(postal_code)
                body = _confirmation_body(postal_code, confirm_token, manage_token, upcoming)
                message_id = mailer.send(
                    to_address,
                    "Confirm your Parliament election reminders",
                    body,
                    manage_token,
                    stream="outbound",   # transactional: a direct reply to their action
                )
                if message_id:
                    logger.info("Reminder confirmation sent for postal_code=%s", postal_code)
                else:
                    logger.error("Reminder confirmation failed for postal_code=%s", postal_code)
            except Exception:
                logger.exception("Confirmation dispatch failed")

    threading.Thread(target=run, daemon=True).start()


# ── POST /reminders/subscribe ────────────────────────────────────────────────
@reminders_bp.route("/reminders/subscribe", methods=["POST"])
def subscribe():
    body = request.get_json(silent=True) or {}

    # Honeypot, same as the contact form. Return the success body so a bot
    # believes it worked and does not retry.
    if (body.get("website") or "").strip():
        logger.info("Reminder honeypot triggered")
        return jsonify(OK_BODY)

    email = _normalize_email(body.get("email"))
    postal_code = normalize_postal_code(body.get("postal_code"))

    # The two validation failures that DO get a distinct response. They are
    # properties of the submitted text alone, reveal nothing about who is
    # subscribed, and a form that silently swallowed a typo'd address would be
    # worse than the oracle it avoids.
    if not email or len(email) > MAX_EMAIL_LEN or not EMAIL_REGEX.match(email):
        return jsonify({
            "error": "invalid_email",
            "lang": LANG,
            "message": "That does not look like an email address.",
        }), 400

    if not validate_postal_code(postal_code):
        return jsonify({
            "error": "invalid_postal_code",
            "lang": LANG,
            "message": "Enter a Canadian postal code, like K1A 0B1.",
        }), 400

    if _rate_limited(_client_ip()):
        return jsonify(OK_BODY)

    try:
        to_send = _upsert_and_claim(email, postal_code)
    except Exception:
        logger.exception("Reminder subscribe failed")
        return jsonify({
            "error": "server_error",
            "lang": LANG,
            "message": "Something went wrong. Please try again.",
        }), 500

    if to_send:
        confirm_token, manage_token = to_send
        _dispatch_confirmation(
            current_app._get_current_object(), email, postal_code, confirm_token, manage_token
        )

    return jsonify(OK_BODY)


def _upsert_and_claim(email: str, postal_code: str):
    """
    Create or revive the subscription and decide whether this caller owns the
    confirmation send.

    Returns (confirm_token, manage_token) if this caller should send, or None.
    None covers three cases that must all look identical from outside: already
    active (nothing to confirm), throttled (a confirmation went out minutes
    ago), and previously complained (terminal — re-mailing a spam complaint is
    how a sending domain dies, and this one also carries candidate claim links).
    """
    row = db.query_one(
        INSERT_SUBSCRIPTION_SQL, (email, postal_code, _new_token(), _new_token())
    )
    if row:
        return row[1], row[2]          # brand new — send

    existing = db.query_one(SELECT_SUBSCRIPTION_SQL, (email, postal_code))
    if not existing:
        # Lost a race with a concurrent delete. Nothing to do; the caller's
        # identical response is still honest — no mail was owed to them.
        return None

    sub_id, status, _confirm_token, _manage_token = existing

    if status == "pending":
        claimed = db.query_one(CLAIM_RESEND_SQL, (sub_id, CONFIRMATION_RESEND_MINUTES))
        return (claimed[0], claimed[1]) if claimed else None

    if status in ("unsubscribed", "bounced"):
        claimed = db.query_one(
            CLAIM_RESUBSCRIBE_SQL, (_new_token(), _new_token(), sub_id)
        )
        return (claimed[0], claimed[1]) if claimed else None

    return None                        # active, or complained


# ── POST /reminders/confirm ──────────────────────────────────────────────────
@reminders_bp.route("/reminders/confirm", methods=["POST"])
def confirm():
    """
    Redeem a confirmation token.

    POST rather than GET on purpose. Corporate mail scanners and link-preview
    bots fetch every URL in an inbound message; a GET here would let a scanner
    confirm a subscription the human never opened, which is precisely the
    consent that double opt-in exists to establish. The emailed link points at a
    frontend page that POSTs on the visitor's behalf.
    """
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()

    if not token:
        return jsonify({"error": "invalid_token", "lang": LANG,
                        "message": "That confirmation link is not valid."}), 400

    try:
        row = db.query_one(CONFIRM_SQL, (token,))
    except Exception:
        logger.exception("Reminder confirm failed")
        return jsonify({"error": "server_error", "lang": LANG,
                        "message": "Something went wrong. Please try again."}), 500

    if not row:
        return jsonify({
            "error": "invalid_token",
            "lang": LANG,
            "message": "That link has already been used to unsubscribe, or is not valid.",
        }), 404

    _sub_id, _email, postal_code, manage_token = row
    logger.info("Reminder subscription confirmed for postal_code=%s", postal_code)

    return jsonify({
        "status": "confirmed",
        "lang": LANG,
        "postal_code": postal_code,
        "manage_token": manage_token,
        "upcoming": _upcoming_for_postal(postal_code),
    })


# ── GET/POST /reminders/subscription ─────────────────────────────────────────
@reminders_bp.route("/reminders/subscription", methods=["GET"])
def subscription():
    """Manage-page payload. The manage token is the only credential."""
    token = (request.args.get("token") or "").strip()
    if not token:
        return jsonify({"error": "invalid_token", "lang": LANG,
                        "message": "That link is not valid."}), 400

    row = db.query_one(SUBSCRIPTION_BY_MANAGE_TOKEN_SQL, (token,))
    if not row:
        return jsonify({"error": "invalid_token", "lang": LANG,
                        "message": "That link is not valid."}), 404

    _sub_id, email, postal_code, status, confirmed_at = row
    return jsonify({
        "status": status,
        "lang": LANG,
        "email": _mask_email(email),
        "postal_code": postal_code,
        "confirmed_at": confirmed_at.isoformat() if confirmed_at else None,
        "upcoming": _upcoming_for_postal(postal_code) if status == "active" else [],
    })


@reminders_bp.route("/reminders/subscription", methods=["POST"])
def update_subscription():
    """Change the postal code on an existing subscription."""
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()
    postal_code = normalize_postal_code(body.get("postal_code"))

    if not token:
        return jsonify({"error": "invalid_token", "lang": LANG,
                        "message": "That link is not valid."}), 400
    if not validate_postal_code(postal_code):
        return jsonify({"error": "invalid_postal_code", "lang": LANG,
                        "message": "Enter a Canadian postal code, like K1A 0B1."}), 400

    try:
        row = db.query_one(UPDATE_POSTAL_CODE_SQL, (postal_code, token))
    except Exception as exc:
        # The (email, postal_code) unique constraint: this person already has a
        # subscription at the new code. Reported plainly rather than hidden —
        # the caller holds the token, so there is nothing to leak.
        if "reminder_subscriptions_email_postal_key" in str(exc):
            return jsonify({
                "error": "already_subscribed",
                "lang": LANG,
                "message": "You already have reminders set for that postal code.",
            }), 409
        logger.exception("Reminder postal code update failed")
        return jsonify({"error": "server_error", "lang": LANG,
                        "message": "Something went wrong. Please try again."}), 500

    if not row:
        return jsonify({"error": "invalid_token", "lang": LANG,
                        "message": "That link is not valid."}), 404

    return jsonify({
        "status": "updated",
        "lang": LANG,
        "postal_code": row[1],
        "upcoming": _upcoming_for_postal(row[1]),
    })


# ── POST /reminders/unsubscribe ──────────────────────────────────────────────
@reminders_bp.route("/reminders/unsubscribe", methods=["POST"])
def unsubscribe():
    """
    Stop a subscription. Accepts the token in the JSON body or the query string:
    the query form is what Gmail's and Yahoo's one-click unsubscribe posts, and
    it carries no body at all.
    """
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or request.args.get("token") or "").strip()

    if not token:
        return jsonify({"error": "invalid_token", "lang": LANG,
                        "message": "That link is not valid."}), 400

    try:
        row = db.query_one(UNSUBSCRIBE_SQL, (token,))
    except Exception:
        logger.exception("Reminder unsubscribe failed")
        return jsonify({"error": "server_error", "lang": LANG,
                        "message": "Something went wrong. Please try again."}), 500

    # An already-unsubscribed token still returns success. UNSUBSCRIBE_SQL is
    # idempotent, so the only way to reach here is an unknown token — and a
    # person clicking unsubscribe must never be told "no". Reporting success is
    # honest about the end state: this token sends no mail.
    if not row:
        return jsonify({"status": "unsubscribed", "lang": LANG,
                        "message": "You will not receive election reminders."})

    logger.info("Reminder subscription unsubscribed for postal_code=%s", row[2])
    return jsonify({"status": "unsubscribed", "lang": LANG,
                    "message": "You will not receive election reminders."})


# ── GET /reminders/preview ───────────────────────────────────────────────────
@reminders_bp.route("/reminders/preview", methods=["GET"])
def preview():
    """
    What a postal code would be reminded about, before subscribing. Lets the
    signup form name the actual elections instead of promising in the abstract,
    and shows honestly when we have no confirmed date for an area yet.
    """
    postal_code = normalize_postal_code(request.args.get("postal_code"))
    if not validate_postal_code(postal_code):
        return jsonify({"error": "invalid_postal_code", "lang": LANG,
                        "message": "Enter a Canadian postal code, like K1A 0B1."}), 400

    return jsonify({
        "lang": LANG,
        "postal_code": postal_code,
        "upcoming": _upcoming_for_postal(postal_code),
    })


# ── POST /reminders/webhook/postmark ─────────────────────────────────────────
@reminders_bp.route("/reminders/webhook/postmark", methods=["POST"])
def postmark_webhook():
    """
    Bounce, spam-complaint and delivery events.

    Authenticated by a shared secret in the query string, which is what Postmark
    supports — it posts to a URL we configure and offers no signing. Without the
    secret set the endpoint refuses everything: an open webhook would let anyone
    unsubscribe any address by guessing a MessageID.

    A hard bounce or a complaint stops the subscription at the source rather
    than leaving it to Postmark's suppression list, because the cohort is built
    by our query, not Postmark's — an unsuppressed row here is a message we keep
    paying to have rejected.
    """
    expected = os.getenv("POSTMARK_WEBHOOK_SECRET")
    if not expected or not secrets.compare_digest(request.args.get("secret", ""), expected):
        return jsonify({"error": "unauthorized"}), 401

    body = request.get_json(silent=True) or {}
    record_type = (body.get("RecordType") or "").strip()
    message_id = (body.get("MessageID") or "").strip()

    if not message_id:
        return jsonify({"status": "ignored"}), 200

    send_row = db.query_one(SEND_BY_MESSAGE_ID_SQL, (message_id,))

    if record_type == "Delivery":
        db.execute(UPDATE_SEND_STATUS_SQL, ("delivered", message_id))
        return jsonify({"status": "ok"}), 200

    if record_type == "Bounce":
        # Only a hard bounce stops the subscription. A soft bounce is a full
        # mailbox or a greylist and will very likely deliver next time;
        # unsubscribing on one would quietly drop real people.
        # Postmark's own judgement, in two forms: the bounce Type, and Inactive,
        # which it sets true when it has deactivated the address itself.
        hard = body.get("Type") in ("HardBounce", "BadEmailAddress") \
            or body.get("Inactive") is True
        db.execute(UPDATE_SEND_STATUS_SQL, ("bounced", message_id))
        if send_row and hard:
            db.execute(MARK_SUBSCRIPTION_EVENT_SQL, ("bounced", send_row[0]))
            logger.info("Reminder subscription marked bounced from webhook")
        return jsonify({"status": "ok"}), 200

    if record_type == "SpamComplaint":
        db.execute(UPDATE_SEND_STATUS_SQL, ("complained", message_id))
        if send_row:
            db.execute(MARK_SUBSCRIPTION_EVENT_SQL, ("complained", send_row[0]))
            logger.info("Reminder subscription marked complained from webhook")
        return jsonify({"status": "ok"}), 200

    return jsonify({"status": "ignored"}), 200


def _mask_email(email: str) -> str:
    """a***@example.com — enough for the holder to recognise their own address
    without printing it in full on a page reachable from a forwarded link."""
    if not email or "@" not in email:
        return ""
    local, _, domain = email.partition("@")
    if len(local) <= 1:
        return f"{local}***@{domain}"
    return f"{local[0]}{'*' * min(len(local) - 1, 3)}@{domain}"
