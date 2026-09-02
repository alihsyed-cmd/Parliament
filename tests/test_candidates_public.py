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
