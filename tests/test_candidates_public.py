"""
Exposure rules for the public candidate profile endpoint.

These tests exist for one reason: this is the only candidate endpoint a stranger
can call, and the table behind it holds 1,334 email addresses. Everything here
asserts what must NOT come out.
"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test")
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost:5432/none")

import candidates_public as cp  # noqa: E402


# ── The allowlist ────────────────────────────────────────────────────────────
def test_allowlist_omits_contact_columns():
    """email/phone must be absent by construction, not filtered downstream."""
    assert "email" not in cp.PUBLIC_CANDIDATE_COLS
    assert "phone" not in cp.PUBLIC_CANDIDATE_COLS


def test_query_never_selects_contact_columns():
    sql = cp.PUBLIC_CANDIDATE_BY_UUID_SQL.lower()
    assert "email" not in sql
    assert "phone" not in sql
    assert "*" not in sql, "must be an explicit allowlist, never SELECT *"


# ── Submission visibility ────────────────────────────────────────────────────
@pytest.fixture
def sub(monkeypatch):
    """Drive _public_submission off a fake submissions row."""
    def _run(row):
        monkeypatch.setattr(cp.db, "query_one", lambda sql, params: row)
        return cp._public_submission("00000000-0000-5000-8000-000000000000")
    return _run


def test_no_submissions_row_is_none(sub):
    assert sub(None) is None


def test_ready_published_video_is_visible(sub):
    assert sub(("ex.ca", "vid123", "ready", True)) == {
        "website": "ex.ca", "video_uid": "vid123",
    }


def test_processing_video_reads_as_no_video(sub):
    """The core invariant: mid-encode is indistinguishable from no video."""
    out = sub(("ex.ca", "vid123", "processing", True))
    assert out == {"website": "ex.ca", "video_uid": None}


def test_failed_video_reads_as_no_video(sub):
    out = sub(("ex.ca", "vid123", "failed", True))
    assert out["video_uid"] is None


def test_no_processing_state_leaks(sub):
    """No status field may reach the client under any status value."""
    for status in ("draft", "processing", "ready", "failed"):
        out = sub(("ex.ca", "vid123", status, True))
        assert out is None or "status" not in out
        assert out is None or "pending" not in out


def test_website_publishes_independently_of_video(sub):
    """A website is live even while the video is still encoding."""
    out = sub(("ex.ca", None, "processing", True))
    assert out["website"] == "ex.ca"


def test_kill_switch_hides_everything(sub):
    """is_published=False outranks a ready video."""
    assert sub(("ex.ca", "vid123", "ready", False)) is None


def test_claimed_but_empty_reads_as_vacant(sub):
    """A claimed page with nothing published must not render an empty shell."""
    assert sub((None, None, "draft", True)) is None
    assert sub(("   ", None, "draft", True)) is None


def test_ready_without_uid_does_not_crash(sub):
    """Schema forbids it; the code must not lean on that."""
    assert sub((None, None, "ready", True)) is None


# ── Race grouping ────────────────────────────────────────────────────────────
def test_race_key_matches_frontend_shape():
    """The key is a client-side lookup handle; both sides must build it alike."""
    assert cp._race_key("ca_on_toronto", "district", "01", "Councillor") == \
        "ca_on_toronto|Councillor|01"
    assert cp._race_key("ca_on_toronto", "role", "", None) == "ca_on_toronto|citywide|"
    # office is currently always None for district rows lacking a role label
    assert cp._race_key("s", "district", "7", None) == "s|district|7"


def test_race_key_tolerates_unsafe_district_ids():
    """Real ids contain spaces; the key holds them because it is never a URL."""
    assert cp._race_key("ca_on_thunder_bay", "district", "CURRENT RIVER", "Councillor") == \
        "ca_on_thunder_bay|Councillor|CURRENT RIVER"


def test_race_title_rules():
    assert cp._race_title("Ward 4", "Councillor", "Guelph") == "Ward 4 Councillor"
    assert cp._race_title("", "Mayor", "Guelph") == "Mayor of Guelph"
    assert cp._race_title("", None, "Guelph") == "Guelph — citywide"
    assert cp._race_title("Ward 4", None, "Guelph") == "Ward 4"


def test_roster_query_never_selects_contact_columns():
    sql = cp.ROSTER_BY_JURISDICTION_SQL.lower()
    assert "email" not in sql
    assert "phone" not in sql
    assert "select *" not in sql


def test_roster_selects_visibility_columns_but_allowlist_stays_clean():
    """status/is_published are read to decide visibility, never returned."""
    sql = cp.ROSTER_BY_JURISDICTION_SQL.lower()
    assert "is_published" in sql and "status" in sql
    assert "email" not in cp.PUBLIC_CANDIDATE_COLS
