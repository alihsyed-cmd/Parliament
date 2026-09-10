#!/usr/bin/env python3
"""
Send the advance (7-day) and day-of election reminder waves.

Runs once a day on a Render cron job. Safe to run more than once a day, to
re-run after a failure, and to run while another copy is running — see the
claim-before-send note below. Sends nothing on a day with no matching election,
which is most days.

    python3 scripts/send_election_reminders.py
    python3 scripts/send_election_reminders.py --dry-run
    python3 scripts/send_election_reminders.py --date 2026-10-19   # pretend it is this day
    python3 scripts/send_election_reminders.py --requeue-pending   # after a crash

HOW IT DECIDES WHO GETS WHAT

  1. Find confirmed elections landing on today (day_of) or today + 7 (advance).
  2. Resolve every active subscriber's postal code to its jurisdictions, once
     per distinct postal code, using the same PostGIS query /lookup uses.
  3. Match subscribers to elections by jurisdiction — and for a by-election, by
     district, because a by-election fills one seat and mailing a whole province
     about it is how a list loses its subscribers.
  4. Claim each (subscriber, election, kind) in reminder_sends, then send.

WHY CLAIM BEFORE SEND

The obvious shape — check whether we sent, then send — double-mails whenever
two runs overlap, because both read "not sent" before either writes. Instead the
run INSERTs the ledger row first with ON CONFLICT DO NOTHING. The composite
primary key means exactly one caller can win that insert, and a caller that wins
zero rows knows another run owns the send and skips it. The database, not the
schedule, is what makes this idempotent.

The cost is a row that claims a send which then fails to happen — a crash
between the claim and the Postmark call. Such a row sits in 'pending' and is
reported at the end of every run; --requeue-pending clears rows older than the
grace window so the next run re-sends them. That direction of failure is the
deliberate one: a missed reminder is visible here and recoverable, a duplicate
reminder is neither.

WHAT IT REFUSES TO SEND

Elections with is_confirmed = false. Most 2029 and 2030 dates in
data/elections.csv are arithmetic on term length, not announced dates. A
reminder is a promise about a specific day; sending an estimate would train
people to distrust the ones that are right.
"""

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os  # noqa: E402

import db  # noqa: E402
import geo  # noqa: E402
import mailer  # noqa: E402

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("send_election_reminders")

ADVANCE_DAYS = 7

# "Today" needs one definition, and Canada spans six zones. Eastern is the
# reference: it is where most registered jurisdictions are, and it is the
# earliest populated zone, so a day-of email composed against it reaches every
# other zone on the correct morning rather than the night before.
DEFAULT_TZ = os.getenv("REMINDER_TIMEZONE", "America/Toronto")

# How long a 'pending' ledger row must sit before --requeue-pending clears it.
# Comfortably longer than any Postmark call plus retry, so a send in flight is
# never cleared out from under itself.
PENDING_GRACE_HOURS = 6


# How a level is named to a voter. "provincial" is what the schema stores;
# "Provincial election" is what belongs in a sentence someone reads at breakfast.
LEVEL_LABEL = {
    "municipal": "Municipal",
    "provincial": "Provincial",
    "territorial": "Territorial",
    "federal": "Federal",
    "state": "State",
}


ELECTIONS_ON_DATES_SQL = """
    SELECT e.id, e.jurisdiction_slug, j.name, j.level, e.election_date,
           e.election_type, e.name, e.advance_voting_starts, e.info_url, e.district_id
    FROM elections e
    JOIN jurisdictions j ON j.slug = e.jurisdiction_slug
    WHERE e.is_confirmed
      AND e.election_date = ANY(%s)
    ORDER BY e.election_date, j.name;
"""

ACTIVE_SUBSCRIPTIONS_SQL = """
    SELECT id, email, postal_code, manage_token
    FROM reminder_subscriptions
    WHERE status = 'active'
    ORDER BY postal_code;
"""

# The claim. Zero rows back means another run owns this send.
CLAIM_SEND_SQL = """
    INSERT INTO reminder_sends (subscription_id, election_id, kind, status)
    VALUES (%s, %s, %s, 'pending')
    ON CONFLICT (subscription_id, election_id, kind) DO NOTHING
    RETURNING subscription_id;
"""

MARK_SENT_SQL = """
    UPDATE reminder_sends
    SET status = 'sent', sent_at = NOW(), provider_message_id = %s
    WHERE subscription_id = %s AND election_id = %s AND kind = %s;
"""

MARK_FAILED_SQL = """
    UPDATE reminder_sends
    SET status = 'failed'
    WHERE subscription_id = %s AND election_id = %s AND kind = %s;
"""

COUNT_PENDING_SQL = """
    SELECT COUNT(*) FROM reminder_sends
    WHERE status = 'pending' AND created_at < NOW() - (%s || ' hours')::INTERVAL;
"""

DELETE_PENDING_SQL = """
    DELETE FROM reminder_sends
    WHERE status = 'pending' AND created_at < NOW() - (%s || ' hours')::INTERVAL;
"""


class Election:
    """One row of the elections table, with the display logic the email needs."""

    def __init__(self, row):
        (self.id, self.slug, self.jurisdiction_name, self.level, self.date,
         self.election_type, self.name, self.advance_start, self.info_url,
         self.district_id) = row

    @property
    def label(self) -> str:
        """A usable name whether or not the CSV supplied one."""
        if self.name:
            return self.name
        kind = "by-election" if self.election_type == "by_election" else "election"
        return f"{self.date.year} {self.jurisdiction_name} {kind}"

    def matches(self, matched_districts: dict) -> bool:
        """
        True when a subscriber whose postal code resolved to `matched_districts`
        can vote in this election.

        A by-election is scoped to its one district; everything else covers the
        whole jurisdiction.
        """
        districts = matched_districts.get(self.slug)
        if districts is None:
            return False
        if self.election_type == "by_election":
            return self.district_id in districts
        return True


def _format_date(d: dt.date) -> str:
    """'Monday, 26 October 2026'. Spelled out because a reminder's entire job is
    to put an unambiguous date in front of someone."""
    return f"{d.strftime('%A')}, {d.day} {d.strftime('%B %Y')}"


def compose(kind: str, elections: list, postal_code: str, manage_token: str):
    """Return (subject, body) for one subscriber's email covering `elections`."""
    date = elections[0].date
    multiple = len(elections) > 1

    if kind == "day_of":
        if multiple:
            subject = f"Today is election day — {len(elections)} elections where you live"
        else:
            subject = f"Today is election day: {elections[0].label}"
        opening = ["Today is election day.", ""]
    else:
        when = "in one week"
        if multiple:
            subject = f"{len(elections)} elections where you live are {when}"
        else:
            subject = f"{elections[0].label} is {when}"
        opening = [f"An election you can vote in is {when}.", ""]

    lines = list(opening)
    lines.append(f"  {_format_date(date)}")
    lines.append("")

    for e in elections:
        lines.append(f"  • {e.label}")
        lines.append(f"    {e.jurisdiction_name} — {LEVEL_LABEL.get(e.level, e.level.title())}")
        if kind == "advance" and e.advance_start and e.advance_start <= date:
            lines.append(f"    Advance voting starts {_format_date(e.advance_start)}")
        if e.info_url:
            lines.append(f"    Where and how to vote: {e.info_url}")
        lines.append("")

    if not any(e.info_url for e in elections):
        # Never invent a polling-place URL. Point at the authority generically
        # rather than at a Parliament page that cannot tell them where to vote.
        lines += [
            "Your local election office publishes your polling place, hours, and",
            "the identification you need to bring.",
            "",
        ]

    lines += [
        f"See who is running where you live: {mailer.APP_BASE_URL}/?postal={postal_code}",
        "",
    ]

    return subject, "\n".join(lines) + mailer.footer(manage_token)


def load_targets(today: dt.date):
    """{kind: [Election, ...]} for the two dates that matter today."""
    advance_date = today + dt.timedelta(days=ADVANCE_DAYS)
    rows = db.query(ELECTIONS_ON_DATES_SQL, ([today, advance_date],))

    by_kind = {"day_of": [], "advance": []}
    for row in rows:
        e = Election(row)
        by_kind["day_of" if e.date == today else "advance"].append(e)
    return by_kind


def resolve_all(subscriptions):
    """
    {postal_code: {slug: {district ids}}}, resolved once per distinct code.

    allow_remote=False on purpose: this loop is unattended and may cover
    thousands of subscribers, so an uncached postal code is logged and skipped
    rather than silently billed to the Maps account. In practice everything here
    is cached, because looking a postal code up in the app is how a subscriber
    reached the signup form.
    """
    resolved, misses = {}, []
    for postal_code in sorted({s[2] for s in subscriptions}):
        matched = geo.resolve_districts(postal_code, allow_remote=False)
        resolved[postal_code] = matched
        if not matched:
            misses.append(postal_code)

    if misses:
        logger.warning(
            "%d postal code(s) resolved to no registered jurisdiction; "
            "their subscribers get nothing this run: %s",
            len(misses), ", ".join(misses[:20]) + (" ..." if len(misses) > 20 else ""),
        )
    return resolved


def run(today: dt.date, dry_run: bool):
    targets = load_targets(today)
    total_elections = sum(len(v) for v in targets.values())

    for kind, elections in targets.items():
        for e in elections:
            logger.info("%s wave: %s on %s", kind, e.label, e.date)

    if total_elections == 0:
        logger.info("No confirmed election on %s or %s. Nothing to send.",
                    today, today + dt.timedelta(days=ADVANCE_DAYS))
        return 0

    subscriptions = db.query(ACTIVE_SUBSCRIPTIONS_SQL)
    logger.info("%d active subscription(s)", len(subscriptions))
    if not subscriptions:
        return 0

    resolved = resolve_all(subscriptions)

    sent = failed = skipped = 0

    for kind, elections in targets.items():
        if not elections:
            continue

        for sub_id, email, postal_code, manage_token in subscriptions:
            matched = resolved.get(postal_code) or {}
            eligible = [e for e in elections if e.matches(matched)]
            if not eligible:
                continue

            # Claim every election in this subscriber's email before composing
            # it, and drop the ones another run already owns. One email covers
            # everything claimed, so a voter with a municipal and a provincial
            # vote on the same day gets one message, not two — while the ledger
            # still records each election separately.
            claimed = []
            for e in eligible:
                if dry_run:
                    claimed.append(e)
                    continue
                if db.query_one(CLAIM_SEND_SQL, (sub_id, e.id, kind)):
                    claimed.append(e)
                else:
                    skipped += 1

            if not claimed:
                continue

            subject, textbody = compose(kind, claimed, postal_code, manage_token)

            if dry_run:
                print(f"\n--- {kind} -> {email} ({postal_code})")
                print(f"Subject: {subject}")
                print(textbody)
                sent += 1
                continue

            message_id = mailer.send(email, subject, textbody, manage_token)

            for e in claimed:
                if message_id:
                    db.execute(MARK_SENT_SQL, (message_id, sub_id, e.id, kind))
                else:
                    db.execute(MARK_FAILED_SQL, (sub_id, e.id, kind))

            if message_id:
                sent += 1
            else:
                failed += 1
                logger.error("Send failed for subscription_id=%s kind=%s", sub_id, kind)

    logger.info("%s: %d email(s) sent, %d failed, %d ledger row(s) already owned.",
                "DRY RUN" if dry_run else "Done", sent, failed, skipped)

    stranded = db.query_one(COUNT_PENDING_SQL, (PENDING_GRACE_HOURS,))[0]
    if stranded:
        logger.warning(
            "%d ledger row(s) stranded in 'pending' for over %dh — a claim whose "
            "send never completed. Re-run with --requeue-pending to clear them.",
            stranded, PENDING_GRACE_HOURS,
        )

    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the emails that would be sent; write nothing, send nothing")
    ap.add_argument("--date", help="treat this ISO date as today (testing, or catching up)")
    ap.add_argument("--requeue-pending", action="store_true",
                    help=f"clear ledger rows stuck in 'pending' for over {PENDING_GRACE_HOURS}h "
                         "so the next run re-sends them")
    args = ap.parse_args()

    if not os.getenv("SUPABASE_DB_URL"):
        raise SystemExit("SUPABASE_DB_URL is not set.")

    if args.date:
        today = dt.date.fromisoformat(args.date)
    else:
        try:
            today = dt.datetime.now(ZoneInfo(DEFAULT_TZ)).date()
        except ZoneInfoNotFoundError:
            # A slim container with no tzdata. Fall back rather than crash: UTC
            # is at most a few hours off Eastern, and a reminder sent on a
            # slightly odd schedule beats a cron that dies on election week.
            logger.error("Timezone %s unavailable (no tzdata installed); using UTC. "
                         "Add tzdata to the cron image to fix the send hour.", DEFAULT_TZ)
            today = dt.datetime.now(dt.timezone.utc).date()
    logger.info("Reminder run for %s (%s)", today, DEFAULT_TZ)

    if args.requeue_pending:
        cleared = db.execute(DELETE_PENDING_SQL, (PENDING_GRACE_HOURS,))
        logger.info("Cleared %d stranded 'pending' ledger row(s).", cleared)

    return run(today, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
