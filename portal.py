"""
Candidate portal — blueprint (task 4).

The write half of the claim flow. Task 3 takes a candidate as far as a valid
edit session; this is what sits behind it.

Endpoints
  GET    /candidates/<uuid>/portal      state on load
  POST   /candidates/<uuid>/upload-url  signed one-time Cloudflare upload URL
  PATCH  /candidates/<uuid>             website field
  DELETE /candidates/<uuid>/video       candidate self-removal
  POST   /webhooks/cloudflare-stream    ready promotes, error reverts

All but the webhook sit behind require_claim_session from claim.py.

TWO LOAD-BEARING RULES
    1. Video bytes never touch this server. The browser uploads directly to
       Cloudflare against a signed one-time URL.
    2. A failed replacement must not destroy the working video. New uploads
       write to the pending slot (migration 006) and promote only on `ready`.
"""

import datetime as dt
import hashlib
import hmac
import logging
import os
import uuid as uuid_lib

import requests
import db
from flask import Blueprint, jsonify, request

from claim import (
    CANDIDATE_BY_UUID_SQL,
    CANDIDATE_COLS,
    JURISDICTION_LABELS_SQL,
    LANG,
    _full_name,
    _office_label,
    require_claim_session,
)

logger = logging.getLogger(__name__)

portal_bp = Blueprint("portal", __name__)


# ── Config ───────────────────────────────────────────────────────────────────
# Master gate. False until the upload loop AND frontend #4/#5 land together.
# This is the BACKEND half — a frontend flag cannot stop a direct POST to a
# deployed endpoint, so the guarantee "no claim email sends while false" is
# only true if it is enforced here.
SUBMISSIONS_ENABLED = os.getenv("SUBMISSIONS_ENABLED", "false").lower() == "true"

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_STREAM_TOKEN = os.getenv("CLOUDFLARE_STREAM_TOKEN")
CLOUDFLARE_WEBHOOK_SECRET = os.getenv("CLOUDFLARE_WEBHOOK_SECRET")

CF_API_BASE = "https://api.cloudflare.com/client/v4"
STREAM_DELIVERY_BASE = os.getenv("STREAM_DELIVERY_BASE", "https://videodelivery.net")

# Comma-separated so preview origins can be added without a deploy. An origin
# missing here fails playback in a way that reads as a broken video rather than
# a config error, which is why it is env-driven.
STREAM_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "STREAM_ALLOWED_ORIGINS",
        "parliamentapp.ca,www.parliamentapp.ca,localhost:3000",
    ).split(",")
    if o.strip()
]

MAX_VIDEO_SECONDS = 60
MAX_WEBSITE_LEN = 500

# An upload pending longer than this is treated as abandoned. Far beyond real
# encode time for a 60-second video; the point is to stop the portal showing
# "processing" forever to a candidate who closed the tab mid-upload.
PENDING_STALE_MINUTES = 30

# Replay window for webhook signatures.
WEBHOOK_MAX_AGE_SECONDS = 300


# ── SQL ──────────────────────────────────────────────────────────────────────
SUBMISSION_COLS = (
    "candidate_uuid", "website", "stream_video_uid", "status", "is_published",
    "submitted_at", "pending_video_uid", "pending_started_at",
)
SUBMISSION_SELECT = ", ".join(SUBMISSION_COLS)

SUBMISSION_BY_UUID_SQL = f"""
    SELECT {SUBMISSION_SELECT}
    FROM submissions
    WHERE candidate_uuid = %s;
"""

SUBMISSION_UPSERT_WEBSITE_SQL = """
    INSERT INTO submissions (candidate_uuid, website, status, submitted_at)
    VALUES (%s, %s, 'draft', NOW())
    ON CONFLICT (candidate_uuid) DO UPDATE
        SET website = EXCLUDED.website;
"""

SUBMISSION_UPSERT_PENDING_SQL = """
    INSERT INTO submissions (candidate_uuid, status, pending_video_uid,
                             pending_started_at, submitted_at)
    VALUES (%s, 'processing', %s, NOW(), NOW())
    ON CONFLICT (candidate_uuid) DO UPDATE
        SET pending_video_uid  = EXCLUDED.pending_video_uid,
            pending_started_at = NOW(),
            status             = 'processing';
"""

SUBMISSION_CLEAR_PENDING_SQL = """
    UPDATE submissions
    SET pending_video_uid  = NULL,
        pending_started_at = NULL,
        status = CASE WHEN stream_video_uid IS NOT NULL THEN 'ready' ELSE 'draft' END
    WHERE candidate_uuid = %s;
"""

SUBMISSION_PROMOTE_SQL = """
    UPDATE submissions
    SET stream_video_uid   = pending_video_uid,
        pending_video_uid  = NULL,
        pending_started_at = NULL,
        status             = 'ready'
    WHERE candidate_uuid = %s;
"""

SUBMISSION_REMOVE_VIDEO_SQL = """
    UPDATE submissions
    SET stream_video_uid = NULL,
        status = CASE WHEN pending_video_uid IS NOT NULL THEN 'processing' ELSE 'draft' END
    WHERE candidate_uuid = %s;
"""

SUBMISSION_BY_PENDING_UID_SQL = """
    SELECT candidate_uuid FROM submissions WHERE pending_video_uid = %s;
"""

SUBMISSION_BY_VIDEO_UID_SQL = """
    SELECT candidate_uuid FROM submissions WHERE stream_video_uid = %s;
"""


# ── Helpers ──────────────────────────────────────────────────────────────────
def _gate_closed():
    """503 while SUBMISSIONS_ENABLED is false. The webhook bypasses this."""
    return jsonify({
        "error": "not_open",
        "message": "Candidate submissions are not open yet.",
    }), 503


def _submission(candidate_uuid):
    row = db.query_one(SUBMISSION_BY_UUID_SQL, (candidate_uuid,))
    return dict(zip(SUBMISSION_COLS, row)) if row else None


def _sweep_stale_pending(candidate_uuid, sub):
    """
    Clear an abandoned upload. Called on portal load — the only place the state
    is ever observed, so a lazy sweep needs no scheduler.

    Returns the (possibly refreshed) submission dict.
    """
    if not sub or not sub["pending_video_uid"]:
        return sub

    started = sub["pending_started_at"]
    if started is None:
        return sub

    age = dt.datetime.now(dt.timezone.utc) - started
    if age <= dt.timedelta(minutes=PENDING_STALE_MINUTES):
        return sub

    logger.info(
        "Sweeping stale pending upload for candidate_uuid=%s (age %s)",
        candidate_uuid, age,
    )
    _cf_delete_video(sub["pending_video_uid"])
    db.execute(SUBMISSION_CLEAR_PENDING_SQL, (candidate_uuid,))
    return _submission(candidate_uuid)


def _thumbnail_url(uid, duration=None):
    """
    Derived at render time, never stored.

    time=3s is a better frame than the first, but a video shorter than three
    seconds returns an error image, so fall back when we know the duration.
    """
    at = "0s" if (duration is not None and duration < 3) else "3s"
    return f"{STREAM_DELIVERY_BASE}/{uid}/thumbnails/thumbnail.jpg?time={at}"


def _candidate_or_none(candidate_uuid):
    rows = db.query(CANDIDATE_BY_UUID_SQL, (candidate_uuid,))
    return dict(zip(CANDIDATE_COLS, rows[0])) if rows else None


def _portal_payload(candidate_uuid, sub, c):
    j_row = db.query_one(JURISDICTION_LABELS_SQL, (c["jurisdiction_slug"],))
    jurisdiction_name = j_row[0] if j_row else c["jurisdiction_slug"]
    role_label_singular = (j_row[1] if j_row else "") or ""

    has_video = bool(sub and sub["stream_video_uid"])
    pending = bool(sub and sub["pending_video_uid"])

    if has_video:
        video_status = "ready"
    elif pending:
        video_status = "processing"
    elif sub and sub["status"] == "failed":
        video_status = "failed"
    else:
        video_status = "none"

    return {
        "lang": LANG,
        "candidate_uuid": str(candidate_uuid),
        "name": _full_name(c),
        "office": _office_label(c, role_label_singular),
        "jurisdiction": jurisdiction_name,
        "district": c["district_name"] or "",
        "website": (sub["website"] if sub else None) or "",
        "has_video": has_video,
        "video_status": video_status,
        "pending": pending,
        "thumbnail_url": _thumbnail_url(sub["stream_video_uid"]) if has_video else None,
    }


def _normalize_website(raw):
    """
    Returns (value, error). Empty clears the field.

    A bare 'janedoe.ca' gets https:// prepended rather than rejected —
    candidates will type it that way and a validation error there is a
    submission we lose for no reason.
    """
    v = (raw or "").strip()
    if not v:
        return None, None
    if len(v) > MAX_WEBSITE_LEN:
        return None, "That address is too long."
    if not v.lower().startswith(("http://", "https://")):
        v = "https://" + v
    rest = v.split("://", 1)[1]
    if not rest or "." not in rest.split("/")[0] or " " in v:
        return None, "That doesn't look like a valid web address."
    return v, None


# ── Cloudflare Stream ────────────────────────────────────────────────────────
def _cf_headers():
    return {
        "Authorization": f"Bearer {CLOUDFLARE_STREAM_TOKEN}",
        "Content-Type": "application/json",
    }


def _cf_direct_upload():
    """
    Request a signed one-time upload URL. Returns (upload_url, uid) or
    (None, None).

    maxDurationSeconds is what enforces the 60-second limit — Cloudflare
    rejects a longer file at the edge, so no server-side duration check exists
    or is needed.
    """
    if not (CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_STREAM_TOKEN):
        logger.error("Cloudflare Stream credentials not configured")
        return None, None

    expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1))
    payload = {
        "maxDurationSeconds": MAX_VIDEO_SECONDS,
        "allowedOrigins": STREAM_ALLOWED_ORIGINS,
        "requireSignedURLs": False,
        "expiry": expiry.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }

    try:
        resp = requests.post(
            f"{CF_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/stream/direct_upload",
            json=payload,
            headers=_cf_headers(),
            timeout=15,
        )
        data = resp.json() if resp.content else {}
        if resp.status_code == 200 and data.get("success"):
            result = data.get("result", {})
            return result.get("uploadURL"), result.get("uid")
        logger.error(
            "Cloudflare direct_upload failed (HTTP %s): %s",
            resp.status_code, data.get("errors"),
        )
    except Exception:
        logger.exception("Cloudflare direct_upload request failed")

    return None, None


def _cf_delete_video(uid):
    """
    Delete a video from Cloudflare. Best-effort; never raises.

    Matters beyond storage cost: a video left on Stream stays publicly playable
    at its delivery URL. A candidate who removed their video asked for it to be
    gone, and leaving it retrievable breaks that quietly.
    """
    if not uid or not (CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_STREAM_TOKEN):
        return False
    try:
        resp = requests.delete(
            f"{CF_API_BASE}/accounts/{CLOUDFLARE_ACCOUNT_ID}/stream/{uid}",
            headers=_cf_headers(),
            timeout=15,
        )
        if resp.status_code in (200, 404):
            return True
        logger.error("Cloudflare delete failed for uid=%s (HTTP %s)", uid, resp.status_code)
    except Exception:
        logger.exception("Cloudflare delete request failed for uid=%s", uid)
    return False


# ── Routes ───────────────────────────────────────────────────────────────────
@portal_bp.route("/candidates/<candidate_uuid>/portal", methods=["GET"])
@require_claim_session
def portal_state(candidate_uuid):
    if not SUBMISSIONS_ENABLED:
        return _gate_closed()

    c = _candidate_or_none(candidate_uuid)
    if not c:
        return jsonify({"error": "not_found", "message": "Candidate not found."}), 404

    sub = _sweep_stale_pending(candidate_uuid, _submission(candidate_uuid))
    return jsonify(_portal_payload(candidate_uuid, sub, c))


@portal_bp.route("/candidates/<candidate_uuid>/upload-url", methods=["POST"])
@require_claim_session
def upload_url(candidate_uuid):
    if not SUBMISSIONS_ENABLED:
        return _gate_closed()

    c = _candidate_or_none(candidate_uuid)
    if not c:
        return jsonify({"error": "not_found", "message": "Candidate not found."}), 404

    # An existing pending upload means the candidate restarted. Delete the old
    # one from Cloudflare before replacing it, or abandoned uploads accumulate
    # as billed storage no row references.
    sub = _submission(candidate_uuid)
    if sub and sub["pending_video_uid"]:
        _cf_delete_video(sub["pending_video_uid"])

    upload, uid = _cf_direct_upload()
    if not upload:
        return jsonify({
            "error": "upload_unavailable",
            "message": "Video upload is temporarily unavailable. Please try again shortly.",
        }), 503

    # stream_video_uid is deliberately untouched: during a replacement the
    # existing video stays live to voters until the new one is ready.
    db.execute(SUBMISSION_UPSERT_PENDING_SQL, (candidate_uuid, uid))

    return jsonify({"upload_url": upload, "video_uid": uid})


@portal_bp.route("/candidates/<candidate_uuid>", methods=["PATCH"])
@require_claim_session
def update_profile(candidate_uuid):
    if not SUBMISSIONS_ENABLED:
        return _gate_closed()

    c = _candidate_or_none(candidate_uuid)
    if not c:
        return jsonify({"error": "not_found", "message": "Candidate not found."}), 404

    body = request.get_json(silent=True) or {}
    if "website" not in body:
        return jsonify({"error": "invalid_request", "message": "Nothing to update."}), 400

    website, err = _normalize_website(body.get("website"))
    if err:
        return jsonify({"error": "invalid_request", "message": err}), 400

    # Creates the row on first save, which is what flips claim_status to
    # "claimed". Publishes immediately — the website is independent of video
    # status by design.
    db.execute(SUBMISSION_UPSERT_WEBSITE_SQL, (candidate_uuid, website))

    return jsonify(_portal_payload(candidate_uuid, _submission(candidate_uuid), c))


@portal_bp.route("/candidates/<candidate_uuid>/video", methods=["DELETE"])
@require_claim_session
def remove_video(candidate_uuid):
    if not SUBMISSIONS_ENABLED:
        return _gate_closed()

    c = _candidate_or_none(candidate_uuid)
    if not c:
        return jsonify({"error": "not_found", "message": "Candidate not found."}), 404

    sub = _submission(candidate_uuid)
    if not sub or not sub["stream_video_uid"]:
        return jsonify(_portal_payload(candidate_uuid, sub, c))

    # Clear our columns regardless of whether Cloudflare cooperates — the
    # candidate's intent outranks our bookkeeping. A failed remote delete is a
    # logged orphan, not a video that stays on the page.
    _cf_delete_video(sub["stream_video_uid"])
    db.execute(SUBMISSION_REMOVE_VIDEO_SQL, (candidate_uuid,))

    return jsonify(_portal_payload(candidate_uuid, _submission(candidate_uuid), c))


# ── Webhook ──────────────────────────────────────────────────────────────────
def _verify_signature(raw_body: bytes, header: str) -> bool:
    """
    Cloudflare signs with `Webhook-Signature: time=<unix>,sig1=<hex>`, the HMAC
    input being `<time>.<raw body>` keyed with the registration secret.

    NOTE: this format could not be confirmed against current Cloudflare docs at
    time of writing. A wrong format looks exactly like a working endpoint that
    rejects everything, so failures log the raw header and the computed digest
    — the first real webhook is self-diagnosing.

    The raw body is required. Re-serialised JSON changes bytes and breaks the
    digest.
    """
    if not header:
        return False

    parts = {}
    for chunk in header.split(","):
        if "=" in chunk:
            k, _, v = chunk.partition("=")
            parts[k.strip()] = v.strip()

    ts, sig = parts.get("time"), parts.get("sig1")
    if not ts or not sig:
        logger.error("Webhook signature header malformed: %r", header)
        return False

    try:
        age = abs(dt.datetime.now(dt.timezone.utc).timestamp() - int(ts))
    except ValueError:
        logger.error("Webhook signature timestamp unparseable: %r", header)
        return False

    if age > WEBHOOK_MAX_AGE_SECONDS:
        logger.warning("Webhook rejected as replay (age %ss)", int(age))
        return False

    expected = hmac.new(
        CLOUDFLARE_WEBHOOK_SECRET.encode(),
        ts.encode() + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, sig):
        logger.error(
            "Webhook signature mismatch. header=%r computed=%s",
            header, expected,
        )
        return False

    return True


@portal_bp.route("/webhooks/cloudflare-stream", methods=["POST"])
def stream_webhook():
    """
    Not session-guarded. Signature verification is the only thing between this
    endpoint and a public 'publish any video to any candidate' button.

    Deliberately NOT gated on SUBMISSIONS_ENABLED: an upload already in flight
    must still be able to complete.
    """
    if not CLOUDFLARE_WEBHOOK_SECRET:
        logger.error("CLOUDFLARE_WEBHOOK_SECRET not set; rejecting webhook")
        return jsonify({"error": "not_configured"}), 503

    raw = request.get_data()
    if not _verify_signature(raw, request.headers.get("Webhook-Signature", "")):
        return jsonify({"error": "invalid_signature"}), 401

    body = request.get_json(silent=True) or {}
    uid = body.get("uid")
    state = (body.get("status") or {}).get("state")

    if not uid:
        return jsonify({"status": "ignored"}), 200

    # Pending first — a ready event almost always concerns an upload still in
    # the pending slot.
    row = db.query_one(SUBMISSION_BY_PENDING_UID_SQL, (uid,))

    if state == "ready":
        if row:
            db.execute(SUBMISSION_PROMOTE_SQL, (row[0],))
            logger.info("Video promoted for candidate_uuid=%s uid=%s", row[0], uid)
            return jsonify({"status": "promoted"}), 200

        # Already promoted — duplicate delivery. Not an error.
        if db.query_one(SUBMISSION_BY_VIDEO_UID_SQL, (uid,)):
            return jsonify({"status": "already_promoted"}), 200

        # Unknown uid: deleted mid-encode, or from another environment.
        logger.info("Ready webhook for unrecognised uid=%s", uid)
        return jsonify({"status": "ignored"}), 200

    if state == "error":
        if row:
            # Clears the pending slot only. stream_video_uid is untouched, so a
            # failed replacement leaves the live video exactly as it was.
            db.execute(SUBMISSION_CLEAR_PENDING_SQL, (row[0],))
            _cf_delete_video(uid)
            logger.info("Video failed for candidate_uuid=%s uid=%s", row[0], uid)
        return jsonify({"status": "reverted"}), 200

    # inprogress / queued — nothing to do. 200 so Cloudflare doesn't retry.
    return jsonify({"status": "ignored"}), 200
