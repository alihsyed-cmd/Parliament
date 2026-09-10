# Election reminders

Voters give an email address and a postal code, confirm by email, and then
receive one reminder seven days before every election they can vote in and one
on the morning of the vote. Federal, provincial, and municipal — for as long as
they want them.

Built to capture every future election, not one campaign. The scheduling data
lives in its own table keyed by date, so a newly announced election is a row in
a CSV rather than a code change.

---

## Shape

| Piece | Where | What it does |
|---|---|---|
| Election dates | `data/elections.csv` → `elections` | One row per jurisdiction per polling day |
| Loader | `scripts/export_elections.py` | Validates the CSV and upserts it |
| API | `reminders.py` (blueprint) | Subscribe, confirm, manage, unsubscribe, webhook |
| Sender | `scripts/send_election_reminders.py` | The daily cron that mails both waves |
| Mail | `mailer.py` | Postmark delivery, unsubscribe headers, shared footer |
| Geo | `geo.py` | Postal code → jurisdictions, shared with `/lookup` |
| Frontend | `frontend/components/ReminderToggle.tsx`, `frontend/app/reminders/*` | Signup form and the three linked pages |
| Schema | `migrations/004_elections_reminders.sql` | `elections`, `reminder_subscriptions`, `reminder_sends` |

Three ideas carry the design, and each is written up at length in the migration:

1. **Elections are their own table.** `jurisdictions.next_election` holds one
   date, is overwritten by any pipeline refresh, and loses the election the day
   after it happens. Reminders need dates that persist and accumulate.
2. **A subscription stores a postal code, not a list of jurisdictions.** The
   jurisdictions are resolved fresh on every send, so a subscriber in a city we
   have not registered yet starts receiving that city's reminders the moment its
   boundaries load. No backfill.
3. **`reminder_sends` is claimed before anything is mailed.** Its composite
   primary key, not the cron schedule, is what makes duplicate reminders
   impossible. See below.

---

## Adding an election

Append a row to `data/elections.csv`, then:

```bash
python3 scripts/export_elections.py --fix-ids   # derive the id for the new row
python3 scripts/export_elections.py --dry-run   # validate, write nothing
python3 scripts/export_elections.py             # load
```

`id` is a UUID5 of `<jurisdiction_slug>|<election_date>|<election_type>`, the
same convention politicians and candidates use. `--fix-ids` computes it so it
never has to be done by hand.

**`is_confirmed` is the field that matters.** The sender refuses to mail an
unconfirmed date. Set it `true` only when the date is fixed by statute or
formally called. The 34 projected rows in the seeded file are arithmetic on term
length — they exist so every jurisdiction has a row, and they wait to be
confirmed before anyone is told about them.

A corrected date mints a new `id`, so it inserts rather than updates. Delete the
stale row with `--prune`, which reports each deletion before making it.

### What shipped in the seed

120 rows, one per registered jurisdiction: 86 carried from
`jurisdictions.next_election` and marked confirmed, 34 projected from
`last_election + term_duration_years` and marked unconfirmed.

---

## Deploying

### 1. Migration

```bash
psql "$SUPABASE_DB_URL" -f migrations/004_elections_reminders.sql
python3 scripts/export_elections.py
```

Additive only. Nothing in migrations 001 to 003 is altered.

### 2. Environment

On the API service and the cron job both:

| Variable | Purpose |
|---|---|
| `POSTMARK_SERVER_TOKEN` | Already set for candidate claim mail |
| `POSTMARK_WEBHOOK_SECRET` | Shared secret in the webhook URL. **Without it the webhook refuses everything** |
| `REMINDER_FROM_ADDRESS` | Default `Parliament <reminders@send.parliamentapp.ca>` |
| `APP_BASE_URL` | Where confirm and unsubscribe links point |
| `REMINDER_UNSUBSCRIBE_MAILTO` | Address in the `List-Unsubscribe` header |
| `REMINDER_TIMEZONE` | Defaults to `America/Toronto`; defines "today" |
| `SUPABASE_DB_URL`, `GOOGLE_MAPS_API_KEY` | As elsewhere |

### 3. Postmark

- Create a **broadcast** message stream. Reminders send on it; the confirmation
  email sends on `outbound` because it is transactional. Mixing them would put
  the candidate claim links, which must arrive, behind a mailing list's
  reputation.
- Point Bounce, SpamComplaint, and Delivery webhooks at
  `https://<api-host>/reminders/webhook/postmark?secret=<POSTMARK_WEBHOOK_SECRET>`.
- Confirm SPF and DKIM on the sending domain.

### 4. Render cron job

New cron service in the same repo, daily, early morning Eastern:

```
Schedule: 0 11 * * *        # 11:00 UTC = 07:00 EDT / 06:00 EST
Command:  python3 scripts/send_election_reminders.py
```

Both waves go out in one run. On a day with no election on either offset the run
sends nothing and exits, which is nearly every day.

---

## Operating the sender

```bash
python3 scripts/send_election_reminders.py --dry-run          # print, send nothing
python3 scripts/send_election_reminders.py --date 2026-10-19  # pretend it is this day
python3 scripts/send_election_reminders.py --requeue-pending  # after a crash
```

### Why it cannot double-send

The obvious shape — check whether we sent, then send — double-mails whenever two
runs overlap, because both read "not sent" before either writes. Instead the run
inserts the ledger row first with `ON CONFLICT DO NOTHING`. The composite primary
key means exactly one caller wins that insert, and a caller that wins zero rows
knows another run owns the send and skips it.

So the cron is safe to run twice, re-run after a failure, and run alongside
itself. The cost is a row that claims a send which then fails to happen, from a
crash between the claim and the Postmark call. Those sit in `pending`, are
reported at the end of every run, and `--requeue-pending` clears ones older than
six hours so the next run re-sends them.

That direction of failure is the deliberate one. A missed reminder is visible in
the ledger and recoverable; a duplicate reminder is neither.

### Bundling

A voter with a municipal and a provincial election on the same day gets one
email covering both, while the ledger still records each election separately.

### By-elections

Scoped to the district being filled. Set `election_type` to `by_election` and
give `district_id` the ward's `districts.external_id`. Only subscribers whose
postal code lands in that district are mailed.

---

## Consent and CASL

- **Double opt-in.** A subscription starts at `pending` and receives exactly one
  thing: the confirmation. Nothing else is ever sent to an unconfirmed address.
- **The confirm link is a GET that POSTs.** Mail scanners fetch every URL in an
  inbound message; a GET that confirmed directly would let a scanner establish
  the consent the human never gave. The emailed link opens a page that POSTs on
  the visitor's behalf, and bots do not run its JavaScript.
- **Consent is recorded.** `confirmed_at` plus `created_at` is the audit trail,
  and a database constraint refuses to mark a row active without it.
- **Unsubscribe is one click**, in every email footer, plus the
  `List-Unsubscribe` header Gmail and Yahoo require on bulk mail.
- **Opt-outs are kept, not deleted.** CASL requires honouring one for 60 days,
  and a deleted row would be silently re-created by the next signup.
- **A spam complaint is terminal.** A complained address is never mailed again,
  including if someone re-submits the signup form for it.
- **Re-subscribing starts consent over.** An unsubscribed address that signs up
  again goes back to `pending` with fresh tokens, which also invalidates any old
  link still sitting in an inbox.

---

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/reminders/subscribe` | `{email, postal_code, website}` — `website` is a honeypot |
| POST | `/reminders/confirm` | `{token}` from the confirmation link |
| GET | `/reminders/subscription?token=` | Manage-page payload; address returned masked |
| POST | `/reminders/subscription` | `{token, postal_code}` — move a subscription |
| POST | `/reminders/unsubscribe` | Token in body or query; query form serves one-click |
| GET | `/reminders/preview?postal_code=` | What an area would be reminded about |
| POST | `/reminders/webhook/postmark?secret=` | Bounce, complaint, delivery |

`/reminders/subscribe` returns one identical body for every outcome — new,
already pending, already active, rate-limited, previously complained. The
endpoint is public and unauthenticated, so a response that varied would be a
free oracle for testing whether an address is subscribed. The confirmation is
also dispatched off-thread, because a Postmark round-trip is 200-800ms against a
5ms no-op and that difference is an oracle of its own. The two exceptions are a
malformed address and a malformed postal code, which are properties of the
submitted text alone and reveal nothing.

Only a hard bounce stops a subscription. A soft bounce is a full mailbox or a
greylist and will likely deliver next time.

---

## Tests

```bash
pytest tests/test_reminders.py -v
```

42 offline tests: cohort matching including by-election scoping, email
composition for both waves, the unsubscribe footer, address masking, and the
shipped `data/elections.csv` passing the loader's own validation.

The no-duplicate guarantee is not tested there. It lives in a composite primary
key and an `ON CONFLICT` clause rather than in Python, so testing it means a
real Postgres; it is asserted in the schema instead of mocked into a false pass.
