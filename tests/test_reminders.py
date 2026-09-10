"""
Election reminder tests.

Everything here is offline. The reminder feature's risky parts are not the SQL —
they are the decisions made in Python before the SQL runs: who is in a cohort,
what the email says, and whether data/elections.csv is loadable at all. Those
are what this file pins down.

The one thing deliberately not tested here is the no-duplicate guarantee, which
lives in a composite primary key and an ON CONFLICT clause rather than in
Python. Testing it means a real Postgres, so it is asserted in the schema
instead of mocked into a false pass here.
"""

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import geo                     # noqa: E402
import reminders               # noqa: E402

sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import export_elections as ee  # noqa: E402


def _load_sender():
    """The sender is a script, not a package module; load it by path."""
    spec = importlib.util.spec_from_file_location(
        "send_election_reminders", PROJECT_ROOT / "scripts" / "send_election_reminders.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sender = _load_sender()

ELECTION_DAY = dt.date(2026, 10, 26)


def make_election(**kw):
    row = (
        kw.get("id", "11111111-1111-5111-9111-111111111111"),
        kw.get("slug", "ca_on_toronto"),
        kw.get("jurisdiction_name", "Toronto"),
        kw.get("level", "municipal"),
        kw.get("date", ELECTION_DAY),
        kw.get("election_type", "general"),
        kw.get("name", "2026 Toronto Municipal Election"),
        kw.get("advance_start", None),
        kw.get("info_url", None),
        kw.get("district_id", None),
    )
    return sender.Election(row)


# ── Postal codes ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("k1a 0b1", "K1A0B1"),
    ("  M5V 2T6  ", "M5V2T6"),
    ("M5V2T6", "M5V2T6"),
    ("", ""),
])
def test_postal_normalization(raw, expected):
    assert geo.normalize_postal_code(raw) == expected


@pytest.mark.parametrize("code,valid", [
    ("M5V2T6", True),
    ("M5V 2T6", False),     # normalize first; the validator sees only compact form
    ("M5V2T", False),
    ("12345", False),
    ("", False),
])
def test_postal_validation(code, valid):
    assert geo.validate_postal_code(code) is valid


# ── Email handling ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("email", [
    "a@b.ca", "first.last+tag@sub.example.co.uk", "UPPER@EXAMPLE.COM",
])
def test_email_regex_accepts_real_addresses(email):
    assert reminders.EMAIL_REGEX.match(email.lower())


@pytest.mark.parametrize("email", [
    "no-at-sign", "@example.com", "a@localhost", "a b@example.com", "a@@b.ca",
])
def test_email_regex_rejects_junk(email):
    assert not reminders.EMAIL_REGEX.match(email)


def test_email_normalized_to_lowercase():
    """The (email, postal_code) unique constraint only means one subscription
    per person if case is normalized before it reaches the database."""
    assert reminders._normalize_email("  Voter@Example.COM ") == "voter@example.com"


def test_masked_email_hides_the_local_part():
    masked = reminders._mask_email("alexander@example.com")
    assert masked.endswith("@example.com")
    assert "alexander" not in masked
    assert masked.startswith("a")


def test_masked_email_of_single_character_local_part():
    """A one-character address must not be printed in full by a mask whose
    padding is derived from length."""
    assert reminders._mask_email("a@b.ca") == "a***@b.ca"


# ── Cohort matching ──────────────────────────────────────────────────────────

def test_general_election_matches_anyone_in_the_jurisdiction():
    e = make_election()
    assert e.matches({"ca_on_toronto": {"14"}, "ca_on": {"X"}}) is True


def test_election_does_not_match_a_different_jurisdiction():
    e = make_election()
    assert e.matches({"ca_on_hamilton": {"3"}}) is False


def test_by_election_matches_only_its_own_district():
    """The rule that keeps a one-seat by-election from mailing a whole province."""
    e = make_election(election_type="by_election", district_id="14", name=None)
    assert e.matches({"ca_on_toronto": {"14"}}) is True
    assert e.matches({"ca_on_toronto": {"3"}}) is False


def test_by_election_matches_when_a_point_lands_in_two_districts():
    e = make_election(election_type="by_election", district_id="14", name=None)
    assert e.matches({"ca_on_toronto": {"3", "14"}}) is True


def test_election_label_falls_back_when_the_csv_has_no_name():
    assert make_election(name=None).label == "2026 Toronto election"
    assert make_election(name=None, election_type="by_election",
                         district_id="14").label == "2026 Toronto by-election"


# ── Email composition ────────────────────────────────────────────────────────

def test_advance_email_names_the_date_and_the_election():
    subject, body = sender.compose("advance", [make_election()], "M5V2T6", "TOKEN")
    assert "in one week" in subject
    assert "Monday, 26 October 2026" in body
    assert "2026 Toronto Municipal Election" in body


def test_day_of_email_says_today():
    subject, body = sender.compose("day_of", [make_election()], "M5V2T6", "TOKEN")
    assert "Today is election day" in subject
    assert "Today is election day." in body


def test_advance_email_includes_advance_voting_when_known():
    e = make_election(advance_start=dt.date(2026, 10, 16))
    _subject, body = sender.compose("advance", [e], "M5V2T6", "TOKEN")
    assert "Advance voting starts Friday, 16 October 2026" in body


def test_day_of_email_omits_advance_voting():
    """By polling day the advance window has closed; mentioning it would send
    someone to a poll that is no longer open."""
    e = make_election(advance_start=dt.date(2026, 10, 16))
    _subject, body = sender.compose("day_of", [e], "M5V2T6", "TOKEN")
    assert "Advance voting" not in body


def test_two_elections_on_one_day_become_one_email():
    """A voter with a municipal and a provincial vote on the same day gets one
    message, not two."""
    a = make_election()
    b = make_election(id="2", slug="ca_on", jurisdiction_name="Ontario",
                      level="provincial", name="2026 Ontario Provincial Election")
    subject, body = sender.compose("advance", [a, b], "M5V2T6", "TOKEN")
    assert "2 elections" in subject
    assert "2026 Toronto Municipal Election" in body
    assert "2026 Ontario Provincial Election" in body


def test_every_email_carries_a_working_unsubscribe_link():
    """CASL requires it, and Gmail and Yahoo require it on bulk mail. Asserted
    on both waves because the footer is the one thing neither may omit."""
    for kind in ("advance", "day_of"):
        _subject, body = sender.compose(kind, [make_election()], "M5V2T6", "MANAGETOKEN")
        assert "/reminders/unsubscribe?token=MANAGETOKEN" in body
        assert "/reminders/manage?token=MANAGETOKEN" in body


def test_email_falls_back_to_generic_guidance_without_an_info_url():
    """Never invent a polling-place URL."""
    _subject, body = sender.compose("advance", [make_election()], "M5V2T6", "TOKEN")
    assert "Your local election office" in body

    _subject, body = sender.compose(
        "advance", [make_election(info_url="https://www.toronto.ca/vote")], "M5V2T6", "TOKEN")
    assert "https://www.toronto.ca/vote" in body
    assert "Your local election office" not in body


def test_level_is_written_for_a_human():
    _subject, body = sender.compose("advance", [make_election()], "M5V2T6", "TOKEN")
    assert "Toronto — Municipal" in body


# ── elections.csv and its loader ─────────────────────────────────────────────

def test_election_id_is_deterministic():
    """Regenerating an id must never change it: reminder_sends references these,
    so a changed id orphans the ledger and re-sends every delivered reminder."""
    a = ee.election_id("ca_on_toronto", "2026-10-26", "general")
    b = ee.election_id("ca_on_toronto", "2026-10-26", "general")
    assert a == b
    assert a != ee.election_id("ca_on_toronto", "2026-10-26", "by_election")
    assert a != ee.election_id("ca_on_hamilton", "2026-10-26", "general")


def test_shipped_elections_csv_loads_clean():
    """The file in the repo must pass the loader's own validation, including
    that every id matches its derivation and every slug is registered."""
    import csv
    rows = ee.read_rows(ee.CSV_PATH)
    known = {
        r["slug"] for r in csv.DictReader(open(PROJECT_ROOT / "data" / "jurisdictions.csv"))
    }
    _prepared, errors = ee.validate(rows, known)
    assert errors == [], "\n".join(errors)


def test_shipped_elections_csv_covers_every_jurisdiction():
    import csv
    rows = ee.read_rows(ee.CSV_PATH)
    covered = {r["jurisdiction_slug"] for r in rows}
    registered = {
        r["slug"] for r in csv.DictReader(open(PROJECT_ROOT / "data" / "jurisdictions.csv"))
    }
    assert registered - covered == set()


def test_validator_rejects_an_id_that_does_not_match_its_row():
    rows = [{
        "id": "00000000-0000-5000-8000-000000000000",
        "jurisdiction_slug": "ca_on_toronto", "election_date": "2026-10-26",
        "election_type": "general", "name": "", "district_id": "",
        "is_confirmed": "true", "advance_voting_starts": "", "info_url": "",
        "source_url": "", "last_verified": "",
    }]
    _prepared, errors = ee.validate(rows, {"ca_on_toronto"})
    assert any("does not match UUID5" in e for e in errors)


def test_validator_rejects_an_unregistered_slug():
    rows = [{
        "id": ee.election_id("ca_zz_nowhere", "2026-10-26", "general"),
        "jurisdiction_slug": "ca_zz_nowhere", "election_date": "2026-10-26",
        "election_type": "general", "name": "", "district_id": "",
        "is_confirmed": "true", "advance_voting_starts": "", "info_url": "",
        "source_url": "", "last_verified": "",
    }]
    _prepared, errors = ee.validate(rows, {"ca_on_toronto"})
    assert any("not a registered jurisdiction" in e for e in errors)


def test_validator_requires_a_district_on_a_by_election():
    rows = [{
        "id": ee.election_id("ca_on_toronto", "2026-10-26", "by_election"),
        "jurisdiction_slug": "ca_on_toronto", "election_date": "2026-10-26",
        "election_type": "by_election", "name": "", "district_id": "",
        "is_confirmed": "true", "advance_voting_starts": "", "info_url": "",
        "source_url": "", "last_verified": "",
    }]
    _prepared, errors = ee.validate(rows, {"ca_on_toronto"})
    assert any("by_election requires a district_id" in e for e in errors)


def test_validator_rejects_advance_voting_after_polling_day():
    rows = [{
        "id": ee.election_id("ca_on_toronto", "2026-10-26", "general"),
        "jurisdiction_slug": "ca_on_toronto", "election_date": "2026-10-26",
        "election_type": "general", "name": "", "district_id": "",
        "is_confirmed": "true", "advance_voting_starts": "2026-11-01",
        "info_url": "", "source_url": "", "last_verified": "",
    }]
    _prepared, errors = ee.validate(rows, {"ca_on_toronto"})
    assert any("is after election_date" in e for e in errors)


def test_validator_rejects_a_non_boolean_confirmed_flag():
    """CLAUDE.md's boolean convention: lowercase 'true'/'false' and nothing else."""
    rows = [{
        "id": ee.election_id("ca_on_toronto", "2026-10-26", "general"),
        "jurisdiction_slug": "ca_on_toronto", "election_date": "2026-10-26",
        "election_type": "general", "name": "", "district_id": "",
        "is_confirmed": "TRUE", "advance_voting_starts": "", "info_url": "",
        "source_url": "", "last_verified": "",
    }]
    _prepared, errors = ee.validate(rows, {"ca_on_toronto"})
    assert any("must be lowercase" in e for e in errors)


def test_validator_reports_every_error_not_just_the_first():
    """A partially loaded elections table sends a partially correct set of
    reminders, so the loader collects all failures and refuses the whole file."""
    rows = [{
        "id": "nope", "jurisdiction_slug": "ca_zz_nowhere",
        "election_date": "26/10/2026", "election_type": "plebiscite",
        "name": "", "district_id": "", "is_confirmed": "yes",
        "advance_voting_starts": "", "info_url": "", "source_url": "",
        "last_verified": "",
    }]
    _prepared, errors = ee.validate(rows, {"ca_on_toronto"})
    assert len(errors) >= 4
