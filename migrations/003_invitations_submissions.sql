-- Parliament — Migration 003: invitations, submissions
--
-- The candidate-facing half of the 2026 municipal candidate feature. Migration 002
-- gave us the roster (who is on the ballot); this gives us the two things that
-- attach to a roster row: the invitation we send them, and the profile they send
-- back. Additive only — nothing in 001 or 002 is altered.
--
-- Both tables key on `raw_candidates.uuid` as their own PRIMARY KEY. That is the
-- whole design in one line: one candidate gets at most one invitation and at most
-- one submission, so the candidate uuid is the natural key for both, no surrogate
-- id, and the one-per-candidate rule is enforced by the primary key itself rather
-- than a separate UNIQUE. It also depends on the property that makes 002 unusual —
-- raw_candidates.uuid is deterministic (UUID5) and stable across the pre-cert beta
-- run and the certified run — so a token issued in August still points at the same
-- row in October. This is the FK that forces candidate-export to UPSERT on uuid
-- rather than delete-then-insert.
--
-- The two tables are split rather than merged because they have different owners
-- and different populations. `invitations` is outbound and machine-written: one row
-- per candidate we mail, written by the send script and by Postmark webhooks.
-- `submissions` is inbound and candidate-written: one row per candidate who
-- actually responds, expected to be a minority of the roster. Merging them would
-- mean thousands of mostly-NULL rows and a single status column trying to express
-- two unrelated lifecycles (email delivery vs. video processing).


-- ── Invitations ──────────────────────────────────────────────────────
-- One row per candidate we have mailed or are about to mail. Rows are minted at
-- SEND time by the send script, not at import by candidate-export — export runs
-- twice (beta roster, then certified roster) and minting at import would issue live
-- tokens to candidates who never get certified. The invariant is therefore:
-- a row exists iff we intended to email this person, which makes the reminder-wave
-- cohort a simple anti-join against this table.
CREATE TABLE invitations (
    candidate_uuid       UUID PRIMARY KEY REFERENCES raw_candidates(uuid) ON DELETE CASCADE,

    -- The address actually mailed, snapshotted at send. Deliberately not read
    -- through to raw_candidates.email: a later export run can correct that value,
    -- and a bounce has to be attributable to the address that actually bounced.
    email                TEXT NOT NULL,

    -- secrets.token_urlsafe(32) — 256 bits, 43 URL-safe chars. Authenticates the
    -- candidate's portal page at parliamentapp.ca/candidate/<token>.
    --
    -- Stored in plaintext, and the reason is functional rather than convenience:
    -- the ~Sep 5 reminder wave must re-send the SAME link. A hash cannot be
    -- reversed to rebuild the URL, so hashing would force a fresh token per wave —
    -- two live tokens per candidate and a first link that silently stops working.
    -- Accepted exposure: a database read leak permits impersonation of a candidate
    -- submission. Low stakes, and is_published on submissions is the remedy.
    token                TEXT NOT NULL UNIQUE,

    -- Durable until the submission cutoff, unlimited uses — NOT single-use.
    -- Candidates re-record, return days later, and forward the link to a campaign
    -- manager. Single-use would generate support mail we have no capacity for.
    expires_at           TIMESTAMPTZ NOT NULL,

    status               TEXT NOT NULL DEFAULT 'pending',

    -- Postmark MessageID from the send call. The join key for inbound Delivery /
    -- Bounce / SpamComplaint webhooks, which carry the MessageID but not our uuid.
    provider_message_id  TEXT,

    sent_at              TIMESTAMPTZ,
    reminder_sent_at     TIMESTAMPTZ,

    -- Timestamp of the most recent Postmark webhook applied to this row.
    last_event_at        TIMESTAMPTZ,

    -- CASL requires honouring an opt-out for 60 days, and the Postmark broadcast
    -- stream requires the unsubscribe link. Postmark maintains its own suppression
    -- list, but we keep our own copy because the reminder cohort is built by our
    -- query, not by Postmark's — without this column we would re-mail an opt-out
    -- and earn a complaint against a 0.1% ceiling.
    unsubscribed_at      TIMESTAMPTZ,

    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 'pending' exists because minting and sending cannot be atomic: insert row,
    -- call Postmark, update to 'sent'. A crash between steps leaves a 'pending'
    -- row, which is safely retryable — the token is already durable and unsent.
    -- 'failed' is a Postmark API rejection at call time; 'bounced' and 'complained'
    -- arrive later by webhook. 'complained' is terminal for reminder purposes.
    CONSTRAINT invitations_status_check CHECK (
        status IN ('pending', 'sent', 'delivered', 'bounced', 'failed', 'complained')
    ),

    -- A row past 'pending' must record when it was sent. Guards against a webhook
    -- or a manual fix advancing status without the send ever being stamped.
    CONSTRAINT invitations_sent_at_consistency CHECK (
        status = 'pending' OR sent_at IS NOT NULL
    )
);

-- The reminder wave's cohort scan (~Sep 5): invited-and-delivered, not opted out,
-- no submission yet. The table is small enough that nothing else warrants an index;
-- token already has a unique index, and candidate_uuid is the primary key.
CREATE INDEX idx_invitations_status ON invitations(status);

-- Reuses set_updated_at() from migration 001.
CREATE TRIGGER invitations_updated_at BEFORE UPDATE ON invitations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ── Submissions ──────────────────────────────────────────────────────
-- One row per candidate who responds, holding the three things a profile is made
-- of and that raw_candidates deliberately lacks: the website link, the Cloudflare
-- Stream video, and the state that decides whether the public sees them. Rows are
-- created by the portal on the candidate's first save — not pre-created at
-- invitation time, which would leave thousands of empty rows for non-responders.
--
-- ON DELETE RESTRICT, deliberately different from invitations' CASCADE. A token is
-- regenerable and worthless, so cascading it away is free. A submission is content
-- a real person recorded and handed us. RESTRICT makes a stale-roster cleanup fail
-- loudly on any candidate who responded, forcing a human look — because a candidate
-- who submitted a video and then appeared to vanish from the roster is far more
-- likely a pipeline fault (name variant, ward renumber, extraction miss) than a
-- genuine withdrawal. This is the decision candidate-export.md is waiting on: its
-- stale-row report becomes a scoped orphan-delete, which will succeed for
-- non-responders and refuse for responders.
CREATE TABLE submissions (
    candidate_uuid    UUID PRIMARY KEY REFERENCES raw_candidates(uuid) ON DELETE RESTRICT,

    website           TEXT,

    -- Cloudflare Stream video UID. Embedded via iframe / @cloudflare/stream-react;
    -- thumbnails come free from /thumbnails/thumbnail.jpg on the same UID.
    stream_video_uid  TEXT,

    status            TEXT NOT NULL DEFAULT 'draft',

    -- The manual kill switch. Written only by a human; never by a webhook.
    -- The UI for it ships later — the column exists now so nothing has to be
    -- migrated under time pressure during the campaign.
    is_published      BOOLEAN NOT NULL DEFAULT TRUE,

    -- First time the candidate saved anything. Distinct from created_at only in
    -- intent, but it is the number we will actually want to report on.
    submitted_at      TIMESTAMPTZ,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- `status` is the AUTOMATED lifecycle, owned end-to-end by Cloudflare Stream's
    -- video-ready webhook: draft (no video yet) → processing (upload accepted,
    -- encoding) → ready | failed. The webhook flips a submission live with no
    -- human step, which is the requirement.
    CONSTRAINT submissions_status_check CHECK (
        status IN ('draft', 'processing', 'ready', 'failed')
    ),

    -- 'ready' without a video UID is incoherent — the webhook that sets 'ready'
    -- is the same event that supplies the UID.
    CONSTRAINT submissions_ready_requires_video CHECK (
        status <> 'ready' OR stream_video_uid IS NOT NULL
    )
);

-- Public visibility is `status = 'ready' AND is_published` — two columns, not one
-- enum, and this separation is load-bearing. If unpublishing were a status value,
-- a Stream webhook retry would silently republish a candidate we had just pulled
-- down. Automated state and human state are orthogonal, so they get orthogonal
-- columns and the webhook can never overwrite the kill switch.
--
-- No index: every read path reaches this table by candidate_uuid, either from a
-- ward's candidate list joining raw_candidates, or from the portal resolving a
-- token through invitations. The primary key serves both.

CREATE TRIGGER submissions_updated_at BEFORE UPDATE ON submissions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
