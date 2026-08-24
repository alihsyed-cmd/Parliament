"""
Candidate claim flow — blueprint.

Split from api.py (which is already 500+ lines) rather than appended. Follows
the same conventions: db.query/query_one returning tuples zipped against an
explicit column tuple, jsonify responses, a constant lang envelope.

Endpoints
  GET /candidates/<uuid>/claim   screen-selection payload for the claim page

Still to come (blocked on the migration 003 schema for `invitations`):
  POST /candidates/<uuid>/claim  the challenge itself
  GET  /claim/<token>            token exchange -> edit session
  POST /contact                  contact endpoint (3.7)

Contract reference: task-3-endpoint-contracts.md §1.
"""

import logging
import uuid as uuid_lib

import db
from flask import Blueprint, jsonify

from claim_mask import mask_email

logger = logging.getLogger(__name__)

claim_bp = Blueprint("claim", __name__)

LANG = "en"


# ── office column ────────────────────────────────────────────────────────────
# The `office` column is being added by the schema chat this week (it is what
# distinguishes a mayoral candidate from an at-large councillor, since both
# carry role_scope='role' with a NULL district_id).
#
# Until it lands, role-scoped candidates get office=None and the frontend
# renders the jurisdiction name alone. Flip this to True after the migration
# and add "office" to CANDIDATE_COLS/SELECT below — no other change needed.
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

# role_label_singular gives the display office for district-scoped candidates
# ("Councillor", "Trustee") without hardcoding vocabulary in the API.
JURISDICTION_LABELS_SQL = """
    SELECT name, role_label_singular
    FROM jurisdictions
    WHERE slug = %s;
"""


def _office_label(candidate: dict, role_label_singular: str):
    """
    Display office for the claim screen.

    district-scoped -> the jurisdiction's own label for a district seat.
    role-scoped     -> ambiguous until the office column exists (mayor and
                       at-large councillor are indistinguishable today), so
                       return None rather than guess wrong on a candidate's
                       own page.
    """
    if OFFICE_COLUMN_AVAILABLE:
        return candidate.get("office")
    if candidate["role_scope"] == "district":
        return role_label_singular or None
    return None


CLAIM_STATUS_SQL = """
    SELECT 1
    FROM submissions
    WHERE candidate_uuid = %s;
"""

def _claim_status(candidate_uuid: str) -> str:
    """
    'unclaimed' | 'claimed' — drives "Is this your page?" vs "Manage this page".

    A submissions row exists from the candidate's first save, so its presence is
    the claim signal. Deliberately not gated on status='ready' or is_published:
    a candidate mid-processing, or one an operator has unpublished, has still
    claimed the page and should see "Manage this page" rather than be invited
    to claim it again.
    """
    return "claimed" if db.query_one(CLAIM_STATUS_SQL, (candidate_uuid,)) else "unclaimed"


@claim_bp.route("/candidates/<candidate_uuid>/claim", methods=["GET"])
def claim_info(candidate_uuid: str):
    """
    Screen-selection payload for the claim page.

    Intentionally public and unauthenticated: candidate pages are public, and
    the no-email holding screen has to render before anyone has proven
    anything. The masked hint is deliberately retrievable by anyone — which is
    why the mask is hard (see claim_mask.mask_email).
    """
    # Reject malformed uuids before they reach the database. Without this a
    # probe with junk in the path raises a psycopg2 error and returns 500,
    # which is both noisy in Sentry and a weak signal about input handling.
    try:
        parsed = uuid_lib.UUID(candidate_uuid)
    except (ValueError, AttributeError, TypeError):
        return jsonify({"error": "not_found", "message": "Candidate not found."}), 404

    rows = db.query(CANDIDATE_BY_UUID_SQL, (str(parsed),))
    if not rows:
        return jsonify({"error": "not_found", "message": "Candidate not found."}), 404

    c = dict(zip(CANDIDATE_COLS, rows[0]))

    j_row = db.query_one(JURISDICTION_LABELS_SQL, (c["jurisdiction_slug"],))
    jurisdiction_name = j_row[0] if j_row else c["jurisdiction_slug"]
    role_label_singular = (j_row[1] if j_row else "") or ""

    # mask_email returns None for anything unusable — missing, malformed, a
    # clerk typo. That degrades to the no-email holding screen, which routes
    # the candidate to the contact form so an operator can fix the row. It must
    # never raise: a 500 here is a candidate who never claims.
    masked = mask_email(c["email"])
    if c["email"] and masked is None:
        logger.warning(
            "Unusable on-file email for candidate uuid=%s; rendering holding screen",
            candidate_uuid,
        )

    full_name = " ".join(p for p in (c["first_name"], c["last_name"]) if p).strip()

    return jsonify({
        "lang": LANG,
        "candidate_uuid": str(parsed),
        "name": full_name,
        "office": _office_label(c, role_label_singular),
        "jurisdiction": jurisdiction_name,
        "jurisdiction_slug": c["jurisdiction_slug"],
        "district": c["district_name"] or "",
        "claimable": masked is not None,
        "masked_hint": masked,
        "claim_status": _claim_status(str(parsed)),
    })
