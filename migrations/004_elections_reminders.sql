-- Parliament — Migration 004: elections, reminder_subscriptions, reminder_sends
--
-- The voter-facing counterpart to 003. Where 002/003 serve candidates (who is on
-- the ballot, and the profile they send back), this serves the voter: tell me
-- before an election I can vote in. Additive only — nothing in 001–003 is altered.
--
-- Three tables, and the split is the design:
--
--   elections              WHAT is coming up. One row per jurisdiction per polling
--                          day. Owned by the repo (data/elections.csv), not by users.
--   reminder_subscriptions WHO wants telling. One row per (email, postal code).
--   reminder_sends         WHAT WE ALREADY SENT. One row per email actually owed
--                          or delivered, and the sole guarantee against duplicates.
--
-- ── Why elections is its own table ───────────────────────────────────────────
-- jurisdictions.next_election already holds a date, and it is tempting to reminder
-- off that column directly. It does not work, for two reasons that both bite in
-- the same week:
--
--   1. It holds exactly one date. The day after an election it is either stale or
--      overwritten, and in both cases the election that just happened is gone. A
--      reminder system needs to know that Toronto votes in Oct 2026 AND Oct 2030,
--      and it needs the 2026 row to survive the day after polls close so the
--      send ledger still resolves.
--   2. It is a property of a jurisdiction refresh. It gets rewritten by the
--      metadata stage of any incumbent-pipeline run, so a reminder cohort built
--      on it would silently change under a routine data refresh.
--
-- So next_election stays as the human-facing "when do these people next face
-- voters" display field, and elections becomes the scheduling table. They are
-- seeded from the same values and are expected to agree; they are not
-- constrained to, because a by-election makes them legitimately differ.
--
-- ── Why subscriptions store a postal code, not a jurisdiction list ───────────
-- A subscriber is subscribed to a POINT ON THE MAP, and the set of jurisdictions
-- covering that point is resolved fresh on every send (geo.resolve_jurisdiction_slugs).
-- Snapshotting the slug list at signup would freeze the subscription against the
-- data we happened to have that day: someone in a city we have not registered yet
-- would be subscribed to nothing forever. Resolving live means they start getting
-- their city's reminders the moment its boundaries load, with no backfill.


-- ── Elections ────────────────────────────────────────────────────────────────
-- One row per jurisdiction per polling day. Loaded from data/elections.csv by
-- scripts/export_elections.py, which upserts on the primary key — so correcting a
-- date is an edit to a tracked CSV and a re-run, reviewable in git like every
-- other dataset in this repo.
CREATE TABLE elections (
    -- Deterministic UUID5 of <jurisdiction_slug>|<election_date>|<election_type>,
    -- matching the convention politicians and raw_candidates already use. Stable
    -- across re-exports, which is what lets reminder_sends reference an election
    -- by id and still be correct after the CSV is corrected and re-loaded. A
    -- surrogate gen_random_uuid() would mint a new id on every export and orphan
    -- the ledger, re-sending every reminder.
    id                      UUID PRIMARY KEY,

    jurisdiction_slug       TEXT NOT NULL REFERENCES jurisdictions(slug) ON DELETE CASCADE,

    -- Polling day. The single date every reminder offset is computed from.
    election_date           DATE NOT NULL,

    -- 'general' is the scheduled whole-jurisdiction vote. 'by_election' fills a
    -- single vacant seat and so is district-scoped — see district_id below.
    -- 'referendum' and 'special' exist so a plebiscite does not have to be
    -- mislabelled as a general election to get reminded.
    election_type           TEXT NOT NULL DEFAULT 'general',

    -- Display name for the email subject and body, e.g. "2026 Ontario Municipal
    -- Election". Optional: the sender composes a serviceable name from the
    -- jurisdiction and the year when this is empty.
    name                    TEXT,

    -- For a by-election, the districts.external_id of the single seat being
    -- filled. NULL for jurisdiction-wide votes. The sender narrows the cohort to
    -- subscribers whose postal code lands in this district, because reminding an
    -- entire province about one riding's by-election is how a mailing list dies.
    district_id             TEXT,

    -- true when the date is fixed by statute or formally called; false when it is
    -- our projection from term length (the four-year arithmetic that fills most of
    -- 2029). The sender REFUSES to mail an unconfirmed date — a reminder is a
    -- promise about a specific day, and being wrong about it is worse than silence.
    -- Projected rows are still stored, because they are what makes "all future
    -- elections" true; they simply wait to be confirmed before anyone is told.
    is_confirmed            BOOLEAN NOT NULL DEFAULT false,

    -- First day of advance voting, where published. Included in the advance
    -- reminder when present, which is most of that email's practical value: the
    -- 7-day reminder usually lands while advance polls are already open.
    advance_voting_starts   DATE,

    -- Where the voter should go to act on the reminder — the election authority's
    -- own page. Never a Parliament page: the reminder's job is to hand the voter
    -- to the returning officer.
    info_url                TEXT,

    source_url              TEXT,
    last_verified           DATE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT elections_type_check CHECK (
        election_type IN ('general', 'by_election', 'referendum', 'special')
    ),

    -- A district-scoped election must name its district, and a jurisdiction-wide
    -- one must not. Mirrors the scope/district consistency rule in 001 and 002.
    CONSTRAINT elections_by_election_district_check CHECK (
        election_type <> 'by_election' OR district_id IS NOT NULL
    ),

    -- Advance voting cannot start after polling day.
    CONSTRAINT elections_advance_before_election_check CHECK (
        advance_voting_starts IS NULL OR advance_voting_starts <= election_date
    ),

    -- The natural key, kept as an explicit constraint even though id is derived
    -- from exactly these three columns. It is what stops a hand-written INSERT
    -- that skipped the UUID5 derivation from creating a second row for one
    -- election — which would double every reminder for that date.
    CONSTRAINT elections_natural_key UNIQUE (jurisdiction_slug, election_date, election_type)
);

-- The cron's daily scan: "confirmed elections whose date is one of today's
-- offsets". Date-leading, because the date is the selective predicate — a given
-- day matches a handful of rows out of the whole table.
CREATE INDEX idx_elections_date ON elections(election_date) WHERE is_confirmed;
CREATE INDEX idx_elections_jurisdiction ON elections(jurisdiction_slug);


-- ── Reminder subscriptions ───────────────────────────────────────────────────
-- One row per (email address, postal code). A voter who wants reminders for both
-- home and a parent's address subscribes twice and confirms twice; each row
-- unsubscribes independently.
CREATE TABLE reminder_subscriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Stored lowercased and trimmed by the API. The lowercasing is what makes the
    -- unique constraint below actually mean "one subscription per person per
    -- address" rather than one per capitalisation.
    email               TEXT NOT NULL,

    -- Normalized A1A1A1, no space. Joined to nothing: it is resolved to
    -- jurisdictions at send time by a PostGIS point-in-polygon query, so there is
    -- deliberately no FK here and no jurisdiction column to go stale.
    postal_code         TEXT NOT NULL,

    -- 'pending'  — created, confirmation mailed, NOT yet confirmed. Receives
    --              nothing. This is the double opt-in holding state.
    -- 'active'   — clicked the confirmation link. The only state that gets mail.
    -- 'unsubscribed' — asked to stop. Kept rather than deleted, because CASL
    --              requires honouring an opt-out for 60 days and a deleted row
    --              would be silently re-created by the next signup form.
    -- 'bounced' / 'complained' — set by Postmark webhooks. 'complained' is
    --              terminal; re-mailing a complainant is what costs a sending
    --              domain its reputation, and this domain also carries the
    --              candidate invitations.
    status              TEXT NOT NULL DEFAULT 'pending',

    -- secrets.token_urlsafe(32). Single-purpose and consumed at confirmation.
    confirm_token       TEXT NOT NULL UNIQUE,

    -- The durable link in the footer of every reminder: unsubscribe, and manage.
    -- Separate from confirm_token and outliving it, because the unsubscribe link
    -- must keep working for the life of the subscription. Stored in plaintext for
    -- the same functional reason invitations.token is (003): every future email
    -- must carry the SAME working link, and a hash cannot be reversed to rebuild
    -- a URL. Exposure on a database read leak is the ability to unsubscribe
    -- someone from election reminders, which is the least damaging capability in
    -- this schema.
    manage_token        TEXT NOT NULL UNIQUE,

    -- Set when the confirmation link is clicked. The audit trail for consent:
    -- CASL requires being able to show when and how consent was obtained, and
    -- this column plus created_at is that record.
    confirmed_at        TIMESTAMPTZ,
    unsubscribed_at     TIMESTAMPTZ,

    -- Most recent Postmark webhook applied to this row.
    last_event_at       TIMESTAMPTZ,

    -- Rate-limits confirmation re-sends: re-submitting the form for a pending
    -- address re-mails the link, and this column is what stops that being an
    -- unmetered way to mail a stranger repeatedly.
    confirmation_sent_at TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT reminder_subscriptions_status_check CHECK (
        status IN ('pending', 'active', 'unsubscribed', 'bounced', 'complained')
    ),

    -- An active row must record when consent was given. Guards against a manual
    -- fix or a bad code path activating a subscription with no consent trail,
    -- which is precisely the record CASL asks for.
    CONSTRAINT reminder_subscriptions_confirmed_consistency CHECK (
        status <> 'active' OR confirmed_at IS NOT NULL
    ),

    -- One subscription per person per address. This is what makes a repeat
    -- signup an idempotent no-op instead of a second row that doubles every
    -- future reminder.
    CONSTRAINT reminder_subscriptions_email_postal_key UNIQUE (email, postal_code)
);

-- The cron's cohort scan starts from status = 'active', then groups by postal
-- code so each distinct code is resolved to jurisdictions exactly once per run.
CREATE INDEX idx_reminder_subscriptions_active
    ON reminder_subscriptions(postal_code)
    WHERE status = 'active';

CREATE INDEX idx_reminder_subscriptions_email ON reminder_subscriptions(email);


-- ── Reminder sends ───────────────────────────────────────────────────────────
-- The idempotency ledger, and the most important table here. One row per email
-- this system has decided to send.
--
-- The composite primary key IS the no-duplicate guarantee. The cron does not ask
-- "have I sent this?" and then send — that read-then-write race double-mails on
-- any overlapping run. It INSERTs the intent first with ON CONFLICT DO NOTHING;
-- an insert that affects zero rows means someone already owns that send and this
-- run must skip it. Only after winning the insert does it call Postmark. The
-- database, not the schedule, is what makes the cron safe to run twice an hour,
-- re-run after a crash, or run concurrently with itself.
--
-- The cost of that design is the 'pending' state: a crash between the insert and
-- the Postmark call leaves a row claiming a send that never happened. That is the
-- deliberate trade — a silently missed reminder is recoverable and visible in this
-- table, while a duplicate reminder is neither. requeue_pending() in the send
-- script sweeps rows left pending past a grace window.
CREATE TABLE reminder_sends (
    subscription_id     UUID NOT NULL REFERENCES reminder_subscriptions(id) ON DELETE CASCADE,

    -- ON DELETE CASCADE: removing an election from data/elections.csv (a date
    -- entered in error, a vote cancelled) takes its ledger rows with it. Correct,
    -- because a cancelled election's reminders should not be suppressed by a
    -- ledger for an election that no longer exists.
    election_id         UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,

    -- 'advance' — the 7-day-out email. 'day_of' — polling day itself.
    -- 'confirmation' is NOT here: it belongs to the subscription, not to any
    -- election, and is stamped on reminder_subscriptions.confirmation_sent_at.
    kind                TEXT NOT NULL,

    status              TEXT NOT NULL DEFAULT 'pending',

    -- Postmark MessageID. The join key for inbound Delivery/Bounce/SpamComplaint
    -- webhooks, which carry the MessageID but not our ids.
    provider_message_id TEXT,

    sent_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (subscription_id, election_id, kind),

    CONSTRAINT reminder_sends_kind_check CHECK (kind IN ('advance', 'day_of')),

    CONSTRAINT reminder_sends_status_check CHECK (
        status IN ('pending', 'sent', 'delivered', 'bounced', 'failed', 'complained')
    ),

    -- Anything past 'pending' or 'failed' must record when it was sent.
    CONSTRAINT reminder_sends_sent_at_consistency CHECK (
        status IN ('pending', 'failed') OR sent_at IS NOT NULL
    )
);

-- Sweeping rows stranded in 'pending' by a crash between the claim and the send.
CREATE INDEX idx_reminder_sends_pending
    ON reminder_sends(created_at)
    WHERE status = 'pending';

-- Webhook lookups arrive by MessageID.
CREATE INDEX idx_reminder_sends_message_id
    ON reminder_sends(provider_message_id)
    WHERE provider_message_id IS NOT NULL;


-- ── updated_at triggers ──────────────────────────────────────────────────────
-- Reuses set_updated_at() from migration 001.
CREATE TRIGGER elections_updated_at BEFORE UPDATE ON elections
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER reminder_subscriptions_updated_at BEFORE UPDATE ON reminder_subscriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER reminder_sends_updated_at BEFORE UPDATE ON reminder_sends
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
