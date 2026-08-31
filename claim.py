"""
Candidate claim flow — blueprint.

Split from api.py (already 500+ lines) rather than appended. Follows the same
conventions: db.query/query_one/execute with tuples zipped against explicit
column tuples, jsonify responses, a constant lang envelope.

Endpoints
  GET  /candidates/<uuid>/claim   screen-selection payload for the claim page
  POST /candidates/<uuid>/claim   the masked-hint challenge
  POST /claim/exchange            token -> scoped edit session

Contract reference: task-3-endpoint-contracts.md, as amended by migration 003's
token semantics (durable multi-use link, not single-use).

THE LOAD-BEARING RULE
    The typed address is a knowledge challenge. It is compared in memory and
    discarded. It is never stored and never a delivery destination. Mail goes
    to raw_candidates.email and nowhere else. A correct guess causes an email
    to arrive in the real candidate's inbox and nothing to the guesser.
"""

import datetime as dt
import logging
import os
import secrets
import threading
import uuid as uuid_lib

import requests
import db
from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from claim_mask import addresses_match, mask_email

logger = logging.getLogger(__name__)

claim_bp = Blueprint("claim", __name__)

LANG = "en"


# ── Config ───────────────────────────────────────────────────────────────────
APP_BASE_URL = os.getenv("APP_BASE_URL", "https://parliamentapp.ca").rstrip("/")
CLAIM_CUTOFF = os.getenv("CLAIM_CUTOFF", "2026-10-26T23:59:00-04:00")

POSTMARK_SERVER_TOKEN = os.getenv("POSTMARK_SERVER_TOKEN")
POSTMARK_ENDPOINT = "https://api.postmarkapp.com/email"
FROM_ADDRESS = os.getenv("CLAIM_FROM_ADDRESS", "Parliament <claims@send.parliamentapp.ca>")
REPLY_TO_ADDRESS = os.getenv("CLAIM_REPLY_TO", "info@parliamentapp.ca")

# Sliding edit session. The claim link is durable; this is what actually limits
# an unattended browser or a stale forwarded link.
SESSION_MAX_AGE_SECONDS = 30 * 60
SESSION_COOKIE_NAME = "claim_session"
SESSION_SALT = "claim-edit-session"
SUBMISSIONS_ENABLED = os.getenv("SUBMISSIONS_ENABLED", "false").lower() == "true"

# Cookie domain: api.parliamentapp.ca and parliamentapp.ca share a registrable
# domain, so a dot-prefixed domain keeps SameSite=Lax workable. Unset in local
# dev, where host-only cookies on localhost are correct.
SESSION_COOKIE_DOMAIN = os.getenv("SESSION_COOKIE_DOMAIN")  # e.g. ".parliamentapp.ca"


# ── Rate limits ──────────────────────────────────────────────────────────────
# Every limit returns the standard 200 body. Never 429 — a 429 confirms to a
# prober that they have found something worth hammering, which is exactly the
# signal the identical-response design removes.
LIMIT_CANDIDATE_ATTEMPTS_PER_HOUR = 15
LIMIT_CANDIDATE_SENDS_PER_DAY = 5
LIMIT_IP_ATTEMPTS_PER_HOUR = 20
LIMIT_IP_ATTEMPTS_PER_DAY = 60


# ── office column ────────────────────────────────────────────────────────────
# Flip to True once the schema chat's migration lands, and add "office" to
# CANDIDATE_COLS below. Until then role-scoped candidates get office=None,
# because a mayor and an at-large councillor are the same row shape today.
OFFICE_COLUMN_AVAILABLE = False


CANDIDATE_COLS = (
    "uuid", "jurisdiction_slug", "first_name", "last_name", "email",
    "role_scope", "district_id", "district_name",
)
CANDIDATE_SELECT = ", ".join(CANDIDATE_COLS)

CANDIDATE_BY_UUID_SQL = f"""
    SELECT {CANDIDATE_SELECT}
    FROM raw_candidates
    WHERE uuid = %s;
"""

JURISDICTION_LABELS_SQL = """
    SELECT name, role_label_singular
    FROM jurisdictions
    WHERE slug = %s;
"""

CLAIM_STATUS_SQL = """
    SELECT 1
    FROM submissions
    WHERE candidate_uuid = %s;
"""

INVITATION_BY_UUID_SQL = """
    SELECT token, expires_at
    FROM invitations
    WHERE candidate_uuid = %s;
"""

INVITATION_INSERT_SQL = """
    INSERT INTO invitations (candidate_uuid, email, token, expires_at, status)
    VALUES (%s, %s, %s, %s, 'pending')
    ON CONFLICT (candidate_uuid) DO NOTHING;
"""

INVITATION_MARK_SENT_SQL = """
    UPDATE invitations
    SET status = 'sent',
        sent_at = NOW(),
        provider_message_id = %s
    WHERE candidate_uuid = %s;
"""

INVITATION_MARK_FAILED_SQL = """
    UPDATE invitations
    SET status = 'failed',
        sent_at = COALESCE(sent_at, NOW())
    WHERE candidate_uuid = %s;
"""

CANDIDATE_BY_TOKEN_SQL = """
    SELECT candidate_uuid, expires_at
    FROM invitations
    WHERE token = %s;
"""

ATTEMPT_INSERT_SQL = """
    INSERT INTO claim_attempts (candidate_uuid, ip_address, matched, email_sent)
    VALUES (%s, %s, %s, %s);
"""

COUNT_CANDIDATE_ATTEMPTS_SQL = """
    SELECT COUNT(*) FROM claim_attempts
    WHERE candidate_uuid = %s AND created_at >= NOW() - INTERVAL '1 hour';
"""

COUNT_CANDIDATE_SENDS_SQL = """
    SELECT COUNT(*) FROM claim_attempts
    WHERE candidate_uuid = %s AND email_sent AND created_at >= NOW() - INTERVAL '24 hours';
"""

COUNT_IP_ATTEMPTS_HOUR_SQL = """
    SELECT COUNT(*) FROM claim_attempts
    WHERE ip_address = %s AND created_at >= NOW() - INTERVAL '1 hour';
"""

COUNT_IP_ATTEMPTS_DAY_SQL = """
    SELECT COUNT(*) FROM claim_attempts
    WHERE ip_address = %s AND created_at >= NOW() - INTERVAL '24 hours';
"""


# ── Standard responses ───────────────────────────────────────────────────────
# One body for every outcome of the challenge: match, no match, rate-limited,
# no address on file, unknown uuid. The frontend never learns which occurred.
OK_BODY = {"status": "ok"}


def _not_found():
    return jsonify({"error": "not_found", "message": "Candidate not found."}), 404


# ── Helpers ──────────────────────────────────────────────────────────────────
def _client_ip():
    """
    Resolve the caller's IP. Requires ProxyFix in api.py — without it this is
    Render's proxy address and per-IP limiting silently no-ops.

    Returns None rather than raising: a missing or unparseable header must not
    lock out a real candidate.
    """
    ip = request.remote_addr
    return ip if ip else None


def _record_attempt(candidate_uuid, ip, matched, email_sent):
    """
    Append to the rate-limit ledger. Never raises — a logging failure must not
    fail the request.

    The typed address is deliberately not a parameter. Storing it would build
    exactly the harvested-address list this design exists to prevent.
    """
    try:
        db.execute(ATTEMPT_INSERT_SQL, (candidate_uuid, ip, matched, email_sent))
    except Exception:
        logger.exception("Failed to record claim attempt")


def _count(sql, param):
    row = db.query_one(sql, (param,))
    return row[0] if row else 0


def _ip_limited(ip):
    if ip is None:
        return False
    return (
        _count(COUNT_IP_ATTEMPTS_HOUR_SQL, ip) >= LIMIT_IP_ATTEMPTS_PER_HOUR
        or _count(COUNT_IP_ATTEMPTS_DAY_SQL, ip) >= LIMIT_IP_ATTEMPTS_PER_DAY
    )


def _office_label(candidate: dict, role_label_singular: str):
    if OFFICE_COLUMN_AVAILABLE:
        return candidate.get("office")
    if candidate["role_scope"] == "district":
        return role_label_singular or None
    return None


def _claim_status(candidate_uuid: str) -> str:
    """
    'unclaimed' | 'claimed' — drives "Is this your page?" vs "Manage this page".

    A submissions row exists from the candidate's first save, so its presence
    is the claim signal. Deliberately not gated on status='ready' or
    is_published: a candidate mid-processing, or one an operator has
    unpublished, has still claimed the page.
    """
    return "claimed" if db.query_one(CLAIM_STATUS_SQL, (candidate_uuid,)) else "unclaimed"


def _full_name(c: dict) -> str:
    return " ".join(p for p in (c["first_name"], c["last_name"]) if p).strip()


# ── Invitation / token ───────────────────────────────────────────────────────
def _get_or_create_invitation(candidate_uuid: str, email: str) -> str:
    """
    Return the candidate's claim token, minting one only if none exists.

    Per migration 003 the token is DURABLE and MULTI-USE: candidates re-record,
    return days later, and forward the link to a campaign manager. Because
    invitations.candidate_uuid is the primary key, a re-request resends the
    SAME link rather than minting a second one — one row, one token, no
    proliferation and no two-live-links problem.

    The 5/day cap is therefore a resend cap, not a token-issuance cap.
    """
    existing = db.query_one(INVITATION_BY_UUID_SQL, (candidate_uuid,))
    if existing:
        return existing[0]

    token = secrets.token_urlsafe(32)
    db.execute(INVITATION_INSERT_SQL, (candidate_uuid, email, token, CLAIM_CUTOFF))

    # ON CONFLICT DO NOTHING means a concurrent request may have won. Re-read
    # so both callers mail the same link.
    row = db.query_one(INVITATION_BY_UUID_SQL, (candidate_uuid,))
    return row[0] if row else token


def _claim_url(token: str) -> str:
    return f"{APP_BASE_URL}/claim/{token}"


# ── Email ────────────────────────────────────────────────────────────────────
def _email_body(name: str, office: str, jurisdiction: str, url: str) -> str:
    """
    Plain text. Civic tone, no urgency language, no countdown.

    The name/office/jurisdiction line matters: a recipient who receives this in
    error can see immediately that it is not theirs.
    """
    who = name
    if office:
        who = f"{name}, {office}"
    if jurisdiction:
        who = f"{who}, {jurisdiction}"

    return (
        f"Hello,\n\n"
        f"Someone asked to claim the Parliament candidate page for {who}.\n\n"
        f"If that was you, you can add your website and a short video here:\n\n"
        f"{url}\n\n"
        f"Your link stays valid through election day, and you can come back and "
        f"change what you have submitted at any time.\n\n"
        f"If this is not you, or you did not expect this message, you can ignore "
        f"it. Nothing has been added to your page.\n\n"
        f"Parliament is an independent, non-commercial project. It is not "
        f"affiliated with any party, campaign, or level of government.\n\n"
        f"Questions: {REPLY_TO_ADDRESS}\n"
    )


def _send_claim_email(candidate_uuid, to_address, name, office, jurisdiction, token):
    """
    Dispatch via Postmark and stamp the invitations row.

    Runs on a background thread. MUST NOT be called inside the request: a
    Postmark round-trip is 200-800ms while a no-match returns in ~5ms, and that
    difference is an enumeration oracle regardless of identical response copy.
    """
    if not POSTMARK_SERVER_TOKEN:
        logger.error("POSTMARK_SERVER_TOKEN not set; cannot send claim email")
        return

    payload = {
        "From": FROM_ADDRESS,
        "To": to_address,
        "ReplyTo": REPLY_TO_ADDRESS,
        "Subject": "Your Parliament claim link",
        "TextBody": _email_body(name, office, jurisdiction, _claim_url(token)),
        "MessageStream": "outbound",
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
            db.execute(INVITATION_MARK_SENT_SQL, (data.get("MessageID"), candidate_uuid))
            logger.info("Claim email sent for candidate_uuid=%s", candidate_uuid)
        else:
            # Log the code, never the address.
            logger.error(
                "Postmark rejected claim send for candidate_uuid=%s (HTTP %s, code %s)",
                candidate_uuid, resp.status_code, data.get("ErrorCode"),
            )
            db.execute(INVITATION_MARK_FAILED_SQL, (candidate_uuid,))
    except Exception:
        logger.exception("Claim email dispatch failed for candidate_uuid=%s", candidate_uuid)
        try:
            db.execute(INVITATION_MARK_FAILED_SQL, (candidate_uuid,))
        except Exception:
            logger.exception("Also failed to mark invitation failed")


def _dispatch_async(app, *args):
    """Fire the send outside the request/response cycle."""
    def run():
        with app.app_context():
            _send_claim_email(*args)

    threading.Thread(target=run, daemon=True).start()


# ── Session ──────────────────────────────────────────────────────────────────
# itsdangerous ships with Flask, so no new dependency. The session is a signed,
# timestamped token scoped to exactly one candidate_uuid.
def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=SESSION_SALT)


def issue_session(candidate_uuid: str) -> str:
    return _serializer().dumps({"candidate_uuid": str(candidate_uuid), "purpose": "edit"})


def read_session(raw):
    """
    Validate a session token. Returns candidate_uuid or None.

    Sliding: callers re-issue on every authenticated request so a candidate
    re-recording on a phone connection does not expire mid-upload.
    """
    if not raw:
        return None
    try:
        data = _serializer().loads(raw, max_age=SESSION_MAX_AGE_SECONDS)
    except (SignatureExpired, BadSignature):
        return None
    if data.get("purpose") != "edit":
        return None
    return data.get("candidate_uuid")


def set_session_cookie(response, candidate_uuid):
    """Attach a freshly-stamped session cookie. Call on every authenticated response."""
    kwargs = dict(
        httponly=True,
        secure=True,
        samesite="Lax",
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )
    if SESSION_COOKIE_DOMAIN:
        kwargs["domain"] = SESSION_COOKIE_DOMAIN
    response.set_cookie(SESSION_COOKIE_NAME, issue_session(candidate_uuid), **kwargs)
    return response


# ── GET /candidates/<uuid>/claim ─────────────────────────────────────────────
@claim_bp.route("/candidates/<candidate_uuid>/claim", methods=["GET"])
def claim_info(candidate_uuid: str):
    """
    Screen-selection payload for the claim page.

    Intentionally public and unauthenticated: candidate pages are public, and
    the no-email holding screen has to render before anyone has proven
    anything. The masked hint is deliberately retrievable by anyone — which is
    why the mask is hard.
    """
    try:
        parsed = uuid_lib.UUID(candidate_uuid)
    except (ValueError, AttributeError, TypeError):
        return _not_found()

    rows = db.query(CANDIDATE_BY_UUID_SQL, (str(parsed),))
    if not rows:
        return _not_found()

    c = dict(zip(CANDIDATE_COLS, rows[0]))

    j_row = db.query_one(JURISDICTION_LABELS_SQL, (c["jurisdiction_slug"],))
    jurisdiction_name = j_row[0] if j_row else c["jurisdiction_slug"]
    role_label_singular = (j_row[1] if j_row else "") or ""

    masked = mask_email(c["email"])
    if c["email"] and masked is None:
        logger.warning(
            "Unusable on-file email for candidate uuid=%s; rendering holding screen",
            candidate_uuid,
        )

    return jsonify({
        "lang": LANG,
        "candidate_uuid": str(parsed),
        "name": _full_name(c),
        "office": _office_label(c, role_label_singular),
        "jurisdiction": jurisdiction_name,
        "jurisdiction_slug": c["jurisdiction_slug"],
        "district": c["district_name"] or "",
        "claimable": masked is not None,
        "masked_hint": masked,
        "claim_status": _claim_status(str(parsed)),
    })


# ── POST /candidates/<uuid>/claim ────────────────────────────────────────────
@claim_bp.route("/candidates/<candidate_uuid>/claim", methods=["POST"])
def claim_challenge(candidate_uuid: str):
    """
    The masked-hint challenge.

    Returns 200 {"status": "ok"} for EVERY outcome — match, no match,
    rate-limited, no address on file, unknown uuid. The only non-200 is a
    malformed body, which is a client bug carrying no signal about a candidate.
    """
    body = request.get_json(silent=True) or {}
    if "email" not in body:
        return jsonify({"error": "invalid_request", "message": "Missing email."}), 400

    typed = body.get("email")
    ip = _client_ip()

    # 1. IP limits first — cheapest, and independent of whether the uuid is real.
    try:
        if _ip_limited(ip):
            _record_attempt(None, ip, False, False)
            return jsonify(OK_BODY)
    except Exception:
        # Fail closed on a limiter error: the failure mode is a candidate
        # retrying, not an unbounded send.
        logger.exception("Rate-limiter read failed; refusing send")
        return jsonify(OK_BODY)

    # 2. Resolve the candidate. Unknown uuid still counts against the IP.
    try:
        parsed = uuid_lib.UUID(candidate_uuid)
    except (ValueError, AttributeError, TypeError):
        _record_attempt(None, ip, False, False)
        return jsonify(OK_BODY)

    rows = db.query(CANDIDATE_BY_UUID_SQL, (str(parsed),))
    if not rows:
        _record_attempt(None, ip, False, False)
        return jsonify(OK_BODY)

    c = dict(zip(CANDIDATE_COLS, rows[0]))
    cuuid = str(parsed)

    # 3. Per-candidate attempt limit (guess detection).
    try:
        if _count(COUNT_CANDIDATE_ATTEMPTS_SQL, cuuid) >= LIMIT_CANDIDATE_ATTEMPTS_PER_HOUR:
            _record_attempt(cuuid, ip, False, False)
            return jsonify(OK_BODY)
    except Exception:
        logger.exception("Rate-limiter read failed; refusing send")
        return jsonify(OK_BODY)

    # 4. No usable address on file -> holding-screen territory. Nothing to send.
    on_file = c["email"]
    if not on_file or mask_email(on_file) is None:
        _record_attempt(cuuid, ip, False, False)
        return jsonify(OK_BODY)

    # 5. Compare, then discard. Constant-time; never stored.
    matched = addresses_match(typed, on_file)
    if not matched:
        _record_attempt(cuuid, ip, False, False)
        return jsonify(OK_BODY)

    # 6. Correct answer, but the daily resend cap is the anti-mailbombing
    #    control and applies to correct answers specifically.
    try:
        if _count(COUNT_CANDIDATE_SENDS_SQL, cuuid) >= LIMIT_CANDIDATE_SENDS_PER_DAY:
            _record_attempt(cuuid, ip, True, False)
            return jsonify(OK_BODY)
    except Exception:
        logger.exception("Send-cap read failed; refusing send")
        _record_attempt(cuuid, ip, True, False)
        return jsonify(OK_BODY)
    if not SUBMISSIONS_ENABLED:
        _record_attempt(cuuid, ip, True, False)
        return jsonify(OK_BODY)
    # 7. Mint or reuse the durable token, then dispatch off-thread.
    try:
        token = _get_or_create_invitation(cuuid, on_file)
    except Exception:
        logger.exception("Failed to mint invitation for candidate_uuid=%s", cuuid)
        _record_attempt(cuuid, ip, True, False)
        return jsonify(OK_BODY)

    j_row = db.query_one(JURISDICTION_LABELS_SQL, (c["jurisdiction_slug"],))
    jurisdiction_name = j_row[0] if j_row else ""
    role_label_singular = (j_row[1] if j_row else "") or ""

    _dispatch_async(
        current_app._get_current_object(),
        cuuid,
        on_file,
        _full_name(c),
        _office_label(c, role_label_singular) or "",
        jurisdiction_name,
        token,
    )

    _record_attempt(cuuid, ip, True, True)
    return jsonify(OK_BODY)


# ── POST /claim/exchange ─────────────────────────────────────────────────────
@claim_bp.route("/claim/exchange", methods=["POST"])
def claim_exchange():
    """
    Trade a claim token for a scoped edit session.

    The emailed link points at the frontend (parliamentapp.ca/claim/<token>),
    which posts the token here. Keeping the exchange same-site avoids a
    cross-domain redirect that would drop the cookie.

    The token is durable and multi-use per migration 003, so this does NOT
    consume it. The 30-minute sliding session is what expires.
    """
    body = request.get_json(silent=True) or {}
    token = (body.get("token") or "").strip()

    if not token:
        return jsonify({"error": "invalid_token", "message": "This link is not valid."}), 400

    row = db.query_one(CANDIDATE_BY_TOKEN_SQL, (token,))
    if not row:
        # Do not distinguish forged from expired from revoked.
        return jsonify({"error": "invalid_token", "message": "This link is not valid."}), 400

    cuuid, expires_at = row[0], row[1]

    now = dt.datetime.now(dt.timezone.utc)
    if expires_at is not None and expires_at <= now:
        return jsonify({"error": "invalid_token", "message": "This link has expired."}), 400

    rows = db.query(CANDIDATE_BY_UUID_SQL, (str(cuuid),))
    if not rows:
        logger.error("Token resolved to missing candidate uuid=%s", cuuid)
        return jsonify({"error": "invalid_token", "message": "This link is not valid."}), 400

    c = dict(zip(CANDIDATE_COLS, rows[0]))
    j_row = db.query_one(JURISDICTION_LABELS_SQL, (c["jurisdiction_slug"],))
    jurisdiction_name = j_row[0] if j_row else c["jurisdiction_slug"]
    role_label_singular = (j_row[1] if j_row else "") or ""

    response = jsonify({
        "lang": LANG,
        "candidate_uuid": str(cuuid),
        "name": _full_name(c),
        "office": _office_label(c, role_label_singular),
        "jurisdiction": jurisdiction_name,
        "district": c["district_name"] or "",
    })
    return set_session_cookie(response, cuuid)


# ── Session guard (for task #4's portal writes) ──────────────────────────────
def require_claim_session(fn):
    """
    Decorator for portal write routes. Resolves the session, enforces that it
    matches the candidate_uuid in the path, and re-stamps the cookie so the
    30-minute window slides.

    Not used by anything in this file — exported for task #4.
    """
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        session_uuid = read_session(request.cookies.get(SESSION_COOKIE_NAME))
        if not session_uuid:
            return jsonify({
                "error": "session_expired",
                "message": "Your editing session has expired. Open your link again.",
            }), 401

        path_uuid = kwargs.get("candidate_uuid")
        if path_uuid and str(path_uuid) != str(session_uuid):
            # Never trust the path over the session.
            return jsonify({"error": "forbidden", "message": "Not permitted."}), 403

        kwargs["candidate_uuid"] = session_uuid
        result = fn(*args, **kwargs)

        response = current_app.make_response(result)
        return set_session_cookie(response, session_uuid)

    return wrapper


# ═════════════════════════════════════════════════════════════════════════════
# 3.7 — Contact endpoint
# ═════════════════════════════════════════════════════════════════════════════
# Backs two screens: the no-email-on-file holding state, and the standing
# "Didn't receive it? Contact us" fallback on every claim confirmation. Without
# it both dead-end — and they dead-end for the warmest users we have, the ones
# actively trying to claim.

CONTACT_TO_ADDRESS = os.getenv("CONTACT_TO_ADDRESS", "info@parliamentapp.ca")

MAX_NAME_LEN = 200
MAX_EMAIL_LEN = 320
MAX_MESSAGE_LEN = 5000

# In-memory, per-process rate limiting. Deliberately not a database table: the
# contact form is low-volume and adding a migration for it is not worth the
# churn. The honest limitations — resets on deploy, and each Render worker
# counts separately, so effective limits are (workers x these numbers).
# Acceptable because the honeypot catches the bulk of automated abuse and the
# blast radius of a miss is email volume, not data exposure. Revisit if it
# actually gets abused.
LIMIT_CONTACT_PER_HOUR = 5
LIMIT_CONTACT_PER_DAY = 20

_contact_hits: dict = {}
_contact_lock = threading.Lock()


def _contact_rate_limited(ip):
    """True if this IP is over either window. Prunes as it goes."""
    if ip is None:
        return False

    now = dt.datetime.now(dt.timezone.utc)
    hour_ago = now - dt.timedelta(hours=1)
    day_ago = now - dt.timedelta(days=1)

    with _contact_lock:
        hits = [t for t in _contact_hits.get(ip, []) if t > day_ago]

        if len(hits) >= LIMIT_CONTACT_PER_DAY:
            _contact_hits[ip] = hits
            return True
        if len([t for t in hits if t > hour_ago]) >= LIMIT_CONTACT_PER_HOUR:
            _contact_hits[ip] = hits
            return True

        hits.append(now)
        _contact_hits[ip] = hits

        # Bound the dict so a long-running process can't grow it without limit.
        if len(_contact_hits) > 5000:
            for k in [k for k, v in _contact_hits.items() if not v or max(v) < day_ago]:
                _contact_hits.pop(k, None)

    return False


def _header_safe(value: str) -> str:
    """
    Strip CR/LF before any value reaches an email header.

    Header injection is the one real vulnerability in a contact form: a newline
    in a submitted address lets an attacker append their own Bcc or Subject.
    Applied to everything that lands in a header, never to the body.
    """
    return (value or "").replace("\r", " ").replace("\n", " ").strip()


def _send_contact_email(subject, reply_to, body):
    """Deliver the contact message. Runs off-thread like the claim send."""
    if not POSTMARK_SERVER_TOKEN:
        logger.error("POSTMARK_SERVER_TOKEN not set; cannot send contact email")
        return

    payload = {
        "From": FROM_ADDRESS,
        "To": CONTACT_TO_ADDRESS,
        "Subject": subject,
        "TextBody": body,
        "MessageStream": "outbound",
    }
    if reply_to:
        payload["ReplyTo"] = reply_to

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
        if resp.status_code != 200:
            data = resp.json() if resp.content else {}
            logger.error(
                "Postmark rejected contact send (HTTP %s, code %s)",
                resp.status_code, data.get("ErrorCode"),
            )
    except Exception:
        logger.exception("Contact email dispatch failed")


@claim_bp.route("/contact", methods=["POST"])
def contact():
    """
    Contact form. Always 200 unless the body is malformed.

    Carries a hidden candidate_uuid when submitted from a candidate page. The
    uuid is what makes the message actionable — without it an operator has to
    work out which of 400+ municipalities' rosters a name belongs to, across
    wards where names repeat.
    """
    body = request.get_json(silent=True) or {}

    # Honeypot. A real browser leaves this empty; bots fill every field they
    # find. Return 200 so the bot believes it succeeded and doesn't retry.
    if (body.get("website") or "").strip():
        logger.info("Contact honeypot triggered")
        return jsonify(OK_BODY)

    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    message = (body.get("message") or "").strip()
    candidate_uuid = (body.get("candidate_uuid") or "").strip()

    if not message:
        return jsonify({
            "error": "invalid_request",
            "message": "A message is required.",
        }), 400

    if (len(name) > MAX_NAME_LEN
            or len(email) > MAX_EMAIL_LEN
            or len(message) > MAX_MESSAGE_LEN):
        return jsonify({
            "error": "invalid_request",
            "message": "That message is too long. Please shorten it and try again.",
        }), 400

    if _contact_rate_limited(_client_ip()):
        # Same 200 as success: a rate-limit response is a signal worth denying.
        return jsonify(OK_BODY)

    # Resolve the uuid rather than trusting it. An unresolved uuid is dropped,
    # never interpolated into the email — otherwise the endpoint becomes a way
    # to inject arbitrary text into a message an operator will read as fact.
    candidate_line = None
    tag = "[CONTACT]"
    subject_detail = "General inquiry"

    if candidate_uuid:
        try:
            parsed = uuid_lib.UUID(candidate_uuid)
            rows = db.query(CANDIDATE_BY_UUID_SQL, (str(parsed),))
        except (ValueError, AttributeError, TypeError):
            rows = None
        except Exception:
            logger.exception("Contact candidate lookup failed")
            rows = None

        if rows:
            c = dict(zip(CANDIDATE_COLS, rows[0]))
            j_row = db.query_one(JURISDICTION_LABELS_SQL, (c["jurisdiction_slug"],))
            jurisdiction_name = j_row[0] if j_row else c["jurisdiction_slug"]
            role_label_singular = (j_row[1] if j_row else "") or ""
            office = _office_label(c, role_label_singular) or ""
            district = c["district_name"] or ""

            where = ", ".join(p for p in (office, district, jurisdiction_name) if p)
            tag = "[CLAIM-SUPPORT]"
            subject_detail = f"{_full_name(c)} — {where}" if where else _full_name(c)

            candidate_line = (
                f"Candidate: {_full_name(c)}\n"
                f"Office:    {office or '—'}\n"
                f"District:  {district or '—'}\n"
                f"Area:      {jurisdiction_name}\n"
                f"UUID:      {c['uuid']}\n"
                f"Claim:     {_claim_status(str(c['uuid']))}\n"
            )
        else:
            logger.info("Contact submitted with unresolved candidate_uuid")

    subject = _header_safe(f"{tag} {subject_detail}")[:200]
    reply_to = _header_safe(email) if "@" in email else None

    lines = []
    if candidate_line:
        lines.append(candidate_line)
        lines.append("-" * 40 + "\n")
    lines.append(f"From:   {name or '(no name given)'}")
    lines.append(f"Email:  {email or '(none given)'}")
    lines.append("")
    lines.append(message)

    _dispatch_async_generic(
        current_app._get_current_object(),
        _send_contact_email,
        subject,
        reply_to,
        "\n".join(lines),
    )

    return jsonify(OK_BODY)


def _dispatch_async_generic(app, fn, *args):
    """Run any sender off the request thread."""
    def run():
        with app.app_context():
            fn(*args)

    threading.Thread(target=run, daemon=True).start()
