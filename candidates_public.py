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

# One municipality's whole certified roster, with each candidate's publicly
# visible submission fields joined on. LEFT JOIN because the overwhelming
# majority of candidates have no submissions row at all — a row is created on
# first save, not at import.
#
# Ordering is done in SQL so every race renders in a stable, alphabetical order
# without the API caring: district first so races group, then surname. Sorting
# by name in Postgres rather than JS also keeps accented surnames ordered the
# same way for every client.
ROSTER_BY_JURISDICTION_SQL = f"""
    SELECT {", ".join("c." + col for col in PUBLIC_CANDIDATE_COLS)},
           s.website, s.stream_video_uid, s.status, s.is_published
    FROM raw_candidates c
    LEFT JOIN submissions s ON s.candidate_uuid = c.uuid
    WHERE c.jurisdiction_slug = %s
    ORDER BY c.role_scope DESC, c.district_id, COALESCE(c.district_name, ''),
             c.last_name, c.first_name;
"""

JURISDICTION_EXISTS_SQL = """
    SELECT 1 FROM jurisdictions WHERE slug = %s;
"""

# What this jurisdiction calls its head of government — "Mayor" here, but the
# tree also holds Reeve, Premier and Prime Minister. Read from the sitting
# executive rather than assumed, so the mayoral race is titled by the same
# authority that titles the incumbent sitting in the seat. ORDER BY only to
# make the pick deterministic where a jurisdiction records more than one.
JURISDICTION_EXECUTIVE_TITLE_SQL = """
    SELECT specific_title
    FROM politicians
    WHERE jurisdiction_slug = %s AND standard_role = 'executive'
    ORDER BY specific_title
    LIMIT 1;
"""


# ── Helpers ──────────────────────────────────────────────────────────────────
def _visible_submission(website, video_uid, status, is_published):
    """
    The publicly visible half of a submission, or None.

    THE one place the exposure rule lives. Both endpoints call it — the profile
    from its own row, the roster from a joined row — so the rule cannot drift
    between a candidate's page and their race listing.

    Returns None when the human kill switch is off, or when the candidate has
    published nothing yet, so a claimed page with nothing on it renders
    identically to an unclaimed one rather than as an empty "submitted by the
    candidate" shell.

    Website and video are independent: a website publishes the moment it is
    saved, regardless of what the video is doing.
    """
    # The kill switch hides everything a candidate supplied. It is written only
    # by a human and must outrank any automated state.
    if not is_published:
        return None

    website = (website or "").strip() or None

    # 'ready' is the only status a voter ever sees the effect of. Anything else
    # — draft, processing, failed — is reported as simply no video, with no
    # status field for a client to build a spinner from. The schema guarantees
    # ready implies a UID, but this does not lean on that.
    visible_video = video_uid if (status == "ready" and video_uid) else None

    if website is None and visible_video is None:
        return None

    return {"website": website, "video_uid": visible_video}


def _public_submission(candidate_uuid: str):
    """Per-candidate lookup for the profile endpoint."""
    row = db.query_one(PUBLIC_SUBMISSION_SQL, (candidate_uuid,))
    if not row:
        return None
    website, video_uid, status, is_published = row
    return _visible_submission(website, video_uid, status, is_published)


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


# ── GET /jurisdictions/<slug>/races ──────────────────────────────────────────
#
# Deliberately NOT /races/<key>/candidates, which the frontend brief named.
# Two findings drove the change, both discovered in the certified data:
#
#   1. district_id is not URL-safe. Real values include "Ward 1",
#      "CURRENT RIVER" and "Ashburnham Ward 4". A composite key embedded in a
#      path segment would need percent-encoding that proxies and clients mangle
#      differently, and a mis-encoded key is a silent empty race.
#
#   2. A whole municipality is small. The largest roster is Toronto at 243
#      candidates, so one response covers every race in the city. The ward card,
#      the race chooser and the race list are three views of the same data, and
#      serving them from one cacheable call avoids both a key format and a
#      request per race.
#
# The race `key` is still returned, in the exact shape the frontend already
# builds, so raceByKey() and racePath() keep working. It is a client-side lookup
# handle, never a URL, which is what makes the unsafe characters harmless.
def _race_key(
    slug: str, role_scope: str, district_id: str, office, district_name: str = "",
) -> str:
    """
    Mirror of the frontend's raceKey(). Kept identical so neither side has to
    translate; office is currently always None, per the declined column.

    The third field is whatever separates one ballot line from another within
    the jurisdiction. For a ward race that is the district_id. For a
    jurisdiction-wide race it is the label the clerk published — "Regional
    Councillor", "Councillor at Large", "Wards 1 & 5" — and empty for the head
    of government's own race. Without it every jurisdiction-wide candidate
    collapses into one race: Markham's three mayoral candidates and eleven
    regional-councillor candidates were being served as a single fourteen-name
    contest, under whichever label happened to be read first.
    """
    if role_scope == "district":
        return f"{slug}|{office or 'district'}|{district_id}"
    return f"{slug}|{office or 'citywide'}|{district_name}"


def _race_title(
    district_name: str, office, jurisdiction_name: str, executive_title=None,
) -> str:
    """
    Mirror of the frontend's allRaces() title rule.

    A jurisdiction-wide race with no label is the head of government's, so it
    takes that jurisdiction's own word for the office. Falling back to
    "<place> — citywide" keeps a jurisdiction whose executive is not yet
    registered readable rather than mistitled.
    """
    if district_name:
        return f"{district_name} {office}" if office else district_name
    if office:
        return f"{office} of {jurisdiction_name}"
    if executive_title:
        return f"{executive_title} of {jurisdiction_name}"
    return f"{jurisdiction_name} — citywide"


@public_bp.route("/jurisdictions/<slug>/races", methods=["GET"])
def jurisdiction_races(slug: str):
    """
    Every race in one municipality, each with its certified candidates.

    Public and unauthenticated for the same reason as the profile endpoint: the
    certified roster is public record from certification day.
    """
    if not db.query_one(JURISDICTION_EXISTS_SQL, (slug,)):
        return jsonify({"error": "not_found", "message": "Jurisdiction not found."}), 404

    j_row = db.query_one(JURISDICTION_LABELS_SQL, (slug,))
    jurisdiction_name = j_row[0] if j_row else slug
    role_label_singular = (j_row[1] if j_row else "") or ""

    exec_row = db.query_one(JURISDICTION_EXECUTIVE_TITLE_SQL, (slug,))
    executive_title = (exec_row[0] if exec_row else "") or ""

    rows = db.query(ROSTER_BY_JURISDICTION_SQL, (slug,))

    races: dict = {}
    order: list = []
    for row in rows:
        c = dict(zip(PUBLIC_CANDIDATE_COLS, row[:len(PUBLIC_CANDIDATE_COLS)]))
        website, video_uid, status, is_published = row[len(PUBLIC_CANDIDATE_COLS):]

        office = _office_label(c, role_label_singular)
        district_name = c["district_name"] or ""
        key = _race_key(
            slug, c["role_scope"], c["district_id"] or "", office, district_name,
        )

        if key not in races:
            order.append(key)
            races[key] = {
                "key": key,
                "office": office,
                "role_scope": c["role_scope"],
                "district_id": c["district_id"] or "",
                "district_name": district_name,
                "title": _race_title(
                    district_name, office, jurisdiction_name, executive_title,
                ),
                "candidates": [],
            }

        races[key]["candidates"].append({
            "uuid": str(c["uuid"]),
            "first_name": c["first_name"] or "",
            "last_name": c["last_name"] or "",
            "name": _full_name(c),
            # Same visibility rule as the profile endpoint, applied to the
            # joined row so this needs no extra query per candidate.
            "submission": _visible_submission(website, video_uid, status, is_published),
        })

    out = [races[k] for k in order]
    for r in out:
        r["candidate_count"] = len(r["candidates"])

    return jsonify({
        "lang": LANG,
        "jurisdiction": jurisdiction_name,
        "jurisdiction_slug": slug,
        "race_count": len(out),
        "candidate_count": sum(r["candidate_count"] for r in out),
        "races": out,
    })
