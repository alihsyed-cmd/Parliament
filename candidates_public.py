"""
Public, unauthenticated read surface for candidate profiles.

Separate from claim.py (which owns the challenge) and portal.py (which owns the
session-guarded editor) because this is the only candidate module a voter's
browser talks to without proving anything. Keeping it apart makes the exposure
rule reviewable in one file.

Two invariants are load-bearing here.

1. Contact details never leave the server. `raw_candidates` holds email and
   phone for outreach; 1,334 candidates carry an address. This module selects an
   explicit column allowlist that omits both, rather than SELECT * minus a
   blocklist, so a future column is excluded by default instead of leaked by
   default.

2. No voter-facing video processing state. A video that is mid-encode or failed
   is reported exactly as "no video": the payload carries no status field at
   all, so there is nothing for a client to render a spinner from. Public
   visibility is `status = 'ready' AND is_published` — the two-column rule from
   migration 003, where the automated Stream lifecycle and the human kill switch
   are deliberately orthogonal.

Deliberately NOT gated on SUBMISSIONS_ENABLED. That flag governs whether
candidates may submit; certified profiles are public from certification day
whether or not claiming is open, which is the whole point of shipping vacant
pages first.
"""

import logging
import uuid as uuid_lib

from flask import Blueprint, jsonify

import db
# Imported rather than reimplemented: the office label a voter sees on a profile
# must match the one on the claim screen. Two copies of this logic would drift.
from claim import (
    LANG,
    JURISDICTION_LABELS_SQL,
    _claim_status,
    _full_name,
    _not_found,
    _office_label,
)

logger = logging.getLogger(__name__)

public_bp = Blueprint("candidates_public", __name__)


# ── Column allowlist ─────────────────────────────────────────────────────────
# Every column a voter-facing response may contain. `email` and `phone` are
# absent by construction. Add to this tuple only after asking whether a stranger
# should see the value for all 1,617 candidates.
PUBLIC_CANDIDATE_COLS = (
    "uuid", "jurisdiction_slug", "first_name", "last_name",
    "role_scope", "district_id", "district_name",
)
PUBLIC_CANDIDATE_SELECT = ", ".join(PUBLIC_CANDIDATE_COLS)

PUBLIC_CANDIDATE_BY_UUID_SQL = f"""
    SELECT {PUBLIC_CANDIDATE_SELECT}
    FROM raw_candidates
    WHERE uuid = %s;
"""

# status and is_published are read to DECIDE visibility, never returned.
PUBLIC_SUBMISSION_SQL = """
    SELECT website, stream_video_uid, status, is_published
    FROM submissions
    WHERE candidate_uuid = %s;
"""


# ── Helpers ──────────────────────────────────────────────────────────────────
def _public_submission(candidate_uuid: str):
    """
    The publicly visible half of a submission, or None.

    Returns None when there is no submissions row, when the human kill switch
    is off, or when the candidate has published nothing yet — so a claimed page
    with nothing on it renders identically to an unclaimed one rather than as an
    empty "submitted by the candidate" shell.

    Website and video are independent: a website publishes the moment it is
    saved, regardless of what the video is doing.
    """
    row = db.query_one(PUBLIC_SUBMISSION_SQL, (candidate_uuid,))
    if not row:
        return None

    website, video_uid, status, is_published = row

    # The kill switch hides everything a candidate supplied. It is written only
    # by a human and must outrank any automated state.
    if not is_published:
        return None

    website = (website or "").strip() or None

    # 'ready' is the only status a voter ever sees the effect of. The schema
    # guarantees ready implies a UID, but this does not lean on that.
    visible_video = video_uid if (status == "ready" and video_uid) else None

    if website is None and visible_video is None:
        return None

    return {"website": website, "video_uid": visible_video}


# ── GET /candidates/<uuid> ───────────────────────────────────────────────────
@public_bp.route("/candidates/<candidate_uuid>", methods=["GET"])
def candidate_profile(candidate_uuid: str):
    """
    The public profile for one certified candidate.

    Unauthenticated by design: every certified candidate has a page from
    certification day, claimed or not, and an unclaimed page must look complete
    rather than broken. The unclaimed response is the full certified record —
    name, office, ward, municipality — with `submission: null`.
    """
    try:
        parsed = uuid_lib.UUID(candidate_uuid)
    except (ValueError, AttributeError, TypeError):
        return _not_found()

    rows = db.query(PUBLIC_CANDIDATE_BY_UUID_SQL, (str(parsed),))
    if not rows:
        return _not_found()

    c = dict(zip(PUBLIC_CANDIDATE_COLS, rows[0]))

    j_row = db.query_one(JURISDICTION_LABELS_SQL, (c["jurisdiction_slug"],))
    jurisdiction_name = j_row[0] if j_row else c["jurisdiction_slug"]
    role_label_singular = (j_row[1] if j_row else "") or ""

    return jsonify({
        "lang": LANG,
        "uuid": str(parsed),
        "first_name": c["first_name"] or "",
        "last_name": c["last_name"] or "",
        "name": _full_name(c),
        "office": _office_label(c, role_label_singular),
        "role_scope": c["role_scope"],
        "jurisdiction": jurisdiction_name,
        "jurisdiction_slug": c["jurisdiction_slug"],
        "district_id": c["district_id"] or "",
        "district_name": c["district_name"] or "",
        "claim_status": _claim_status(str(parsed)),
        "submission": _public_submission(str(parsed)),
    })
