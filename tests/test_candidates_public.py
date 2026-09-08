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


def test_race_key_separates_jurisdiction_wide_ballot_lines():
    """
    Markham elects a Mayor and eleven Regional Councillors, both jurisdiction-
    wide. Sharing a key merged them into one fourteen-name race.
    """
    mayor = cp._race_key("ca_on_markham", "role", "", None, "")
    regional = cp._race_key("ca_on_markham", "role", "", None, "Regional Councillor")
    assert mayor != regional
    assert mayor == "ca_on_markham|citywide|"
    assert regional == "ca_on_markham|citywide|Regional Councillor"


def test_race_title_rules():
    assert cp._race_title("Ward 4", "Councillor", "Guelph") == "Ward 4 Councillor"
    assert cp._race_title("", "Mayor", "Guelph") == "Mayor of Guelph"
    assert cp._race_title("", None, "Guelph") == "Guelph — citywide"
    assert cp._race_title("Ward 4", None, "Guelph") == "Ward 4"


def test_head_of_government_race_takes_the_executive_title():
    """The unlabelled jurisdiction-wide race is the mayor's, named as the
    jurisdiction names the incumbent — never inferred from candidate names."""
    assert cp._race_title("", None, "Guelph", "Mayor") == "Mayor of Guelph"
    assert cp._race_title("", None, "Norfolk County", "Mayor") == "Mayor of Norfolk County"


def test_labelled_jurisdiction_wide_race_keeps_the_clerks_label():
    """An at-large seat is not the mayor's race and must not borrow its title."""
    assert cp._race_title("Regional Councillor", None, "Markham", "Mayor") == \
        "Regional Councillor"
    assert cp._race_title("Wards 1 & 5", None, "Brampton", "Mayor") == "Wards 1 & 5"


def test_unregistered_executive_falls_back_rather_than_mistitling():
    assert cp._race_title("", None, "Guelph", "") == "Guelph — citywide"
    assert cp._race_title("", None, "Guelph", None) == "Guelph — citywide"


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


# ── GET /candidates/search ───────────────────────────────────────────────────
# The name-search endpoint is cross-jurisdictional and unauthenticated, so it is
# the widest-reaching read in the file. These tests pin the two things that make
# that safe: it returns the same allowlist as every other public read, and a
# caller cannot turn the query into their own LIKE pattern.
def test_search_query_never_selects_contact_columns():
    sql = cp.SEARCH_CANDIDATES_SQL.lower()
    assert "email" not in sql
    assert "phone" not in sql
    assert "select *" not in sql


def test_search_escapes_like_metacharacters():
    """Without this, '%' alone matches all 1,617 rows."""
    assert cp._like_escape("%") == r"\%"
    assert cp._like_escape("_") == r"\_"
    assert cp._like_escape("\\") == "\\\\"
    # The backslash is escaped first, so it cannot double-escape what follows.
    assert cp._like_escape("\\%") == r"\\\%"


def test_search_leaves_ordinary_names_untouched():
    for name in ("Chow", "Erskine-Smith", "D'Amours", "Côté"):
        assert cp._like_escape(name) == name


@pytest.fixture
def search_client(monkeypatch):
    """A test client whose db.query records what it was asked."""
    from flask import Flask

    calls = []

    def fake_query(sql, params=()):
        calls.append((sql, params))
        return []

    monkeypatch.setattr(cp.db, "query", fake_query)
    app = Flask(__name__)
    app.register_blueprint(cp.public_bp)
    return app.test_client(), calls


def test_short_query_answers_empty_without_touching_the_database(search_client):
    """One character is 'keep typing', not a scan and not an error."""
    client, calls = search_client
    for q in ("", " ", "a", "  "):
        res = client.get("/candidates/search", query_string={"q": q})
        assert res.status_code == 200
        assert res.get_json()["results"] == []
    assert calls == []


def test_each_token_becomes_one_anded_condition(search_client):
    """'olivia chow' must match the full name, not either half."""
    client, calls = search_client
    client.get("/candidates/search", query_string={"q": "olivia chow"})
    sql, params = calls[0]
    assert sql.count("ILIKE") == 2
    assert " AND " in sql
    assert params[:2] == ("%olivia%", "%chow%")


def test_limit_is_clamped(search_client):
    client, calls = search_client
    client.get("/candidates/search", query_string={"q": "chow", "limit": "9999"})
    assert calls[-1][1][-1] == cp.SEARCH_MAX_LIMIT

    client.get("/candidates/search", query_string={"q": "chow", "limit": "-3"})
    assert calls[-1][1][-1] == 1

    client.get("/candidates/search", query_string={"q": "chow", "limit": "junk"})
    assert calls[-1][1][-1] == cp.SEARCH_DEFAULT_LIMIT


def test_token_count_is_capped(search_client):
    """A long paste is answered, not turned into an unbounded scan."""
    client, calls = search_client
    client.get("/candidates/search", query_string={"q": "a b c d e f g"})
    assert calls[0][0].count("ILIKE") == cp.SEARCH_MAX_TOKENS


def test_wildcard_query_cannot_match_the_whole_table(search_client):
    client, calls = search_client
    client.get("/candidates/search", query_string={"q": "%%"})
    assert calls[0][1][0] == r"%\%\%%"
