# Candidate Profile Feature — Brief for Claude Design

## Context

Parliament currently shows voters their **elected** representatives (federal, provincial, municipal) by postal code, sourced from `politicians.csv` → the `politicians` Supabase table.

We're adding a second, parallel dataset: **candidates** running in Ontario's October 26, 2026 municipal elections. This is a distinct concept from an elected official — a candidate has not won a seat, may be one of several people contesting a ward/mayoral race, and their record can disappear or change status as the race resolves. Candidate data is being populated by a new backend pipeline into a `raw_candidates` table (separate from `politicians`), keyed by a deterministic UUID that's scoped to `slug | first_name | last_name | role_scope | district_id` — the `role_scope` split (mayoral vs. councillor) prevents two people who share a UUID otherwise from colliding.

Import trigger: **Certification Day, August 24, 2026** is when we bulk-import each municipality's official candidate list. A second, smaller window (Aug 26–Sep 4) covers wards where nominations were reopened for lack of candidates. So candidate data starts appearing in the app from late August, well before Election Day.

## What frontend needs to design/build

1. **A Stories-style candidate viewer.** Full-screen, one candidate at a time: name, their video playing (max 1 min, so no scrubber/long-form player chrome needed — think Instagram Stories, not YouTube), and a link out to their website. Navigation is tap-left-half / tap-right-half (or swipe) to move backward/forward through the stack — not a scrolling list, not a grid of cards.

2. **Alphabetical ordering within a race.** The candidate stack for a given ward/mayoral race is sorted alphabetically (confirm with Ali: by first or last name) rather than by any other ranking. No featured/sponsored ordering, no randomization.

3. **A "who's running in my ward" entry point**, attached to the existing postal-code lookup flow — when a user looks up their address in a municipality with an active election, this is how they'd launch into the swipeable candidate stack for their ward and/or mayoral race, distinct from the current-officeholder view.

4. **Race grouping / stack boundaries.** A ward has its own candidate stack; the mayoral race is its own stack (role_scope: district vs. role). Design the transition between "end of ward candidates" and "into mayoral candidates" (if they're chained) vs. keeping them as fully separate entry points — open question, flag for Ali.

5. **The responder/non-responder gap (see below).** Since only candidates with a submitted website + video have anything to show in this format, decide how a ward with, say, 2 responders out of 8 total candidates is represented — does the stack only include the 2 responders, with the other 6 invisible in this view? Surfacing "6 more candidates haven't submitted a profile yet" somewhere is worth considering so the stack doesn't quietly imply it's the full field.

6. **Election Day framing** — since the destination event is Oct 26, 2026, some way of anchoring the candidate view to that date would help orient users who land on this outside the immediate pre-election window.

## Data shape today vs. what the profile actually needs

The current `raw_candidates` table (migration 002) holds: `uuid`, `jurisdiction_slug`, `district_id`, `district_name`, `role_scope`, `first_name`, `last_name`, `email`, `phone`. That's the raw roster — every nominated candidate, sourced from official municipal clerk data, whether or not they've engaged with Parliament at all.

**The candidate *profile* itself is a narrower, different thing**, populated only for candidates who go through the (not-yet-built) invitation/submission flow. A finished candidate profile shows exactly three things — nothing else:

1. **Full name**
2. **A link to the candidate's own website**
3. **A self-recorded campaign pitch video, capped at 1 minute**

No photo, no party, no bio text, no phone/email display — even though phone/email exist in the raw table, they're for our outreach use (inviting the candidate), not for display on the profile.

**Schema gap to flag for the backend agent:** `website` and a video reference (`video_url` or similar) don't exist in `raw_candidates` yet. These are submission-flow outputs, not pipeline-extracted fields, so they likely belong on the future `invitations`-adjacent table (or a `candidate_submissions` table) rather than being bolted onto `raw_candidates` — worth raising in the backend chat before Design finalizes anything that assumes a specific field name. A profile only exists/renders once a candidate has actually submitted a website + video; a `raw_candidates` row with no submission has nothing to show beyond "on the ballot."

## The "responders vs. non-responders" wrinkle

The migration's own comment describes `raw_candidates` as "the table the frontend reads to show every candidate in a race — responders and non-responders alike." Combined with the point above: **only responders (candidates who submitted a website + video) get an actual profile.** Non-responders are on the ballot but have nothing to show. Design needs to decide how — or whether — a non-responder appears in the swipeable stack at all (see below), versus being invited/nudged separately outside this flow.

## What happens after the election

Winners get promoted into `politicians` with a **new, different UUID** (the politician-space UUID scheme, not the candidate one) at term start. So a candidate profile is not the permanent home for someone who wins — don't design any deep-linking or persistent-URL assumption that a candidate's page becomes their rep page later; they're separate records with separate identities.

## Explicitly out of scope for this round

- **The submission/invitation flow itself** — how a candidate actually uploads their video and website (recording UI, moderation, review, the table(s) that store it) is a separate, not-yet-designed piece. This brief is about *consuming* a finished profile, not building the intake.
- **Video hosting/playback mechanics** — where the video file lives and how it's served (Supabase storage, external host, etc.) isn't decided; treat it as "a video URL that plays" for design purposes and confirm the real constraint with backend before building custom player chrome.
- **Any additional profile content beyond the three fields** (bios, platforms, photos, endorsements) — explicitly not part of this feature.
- **Comparison/voting-guide tooling** — not in scope; this round is one-at-a-time viewing only.

## Open questions for you (Claude Design)

- How do you want to represent a race where most candidates haven't submitted a profile yet — is a 2-person stack (out of 8 on the ballot) presented as complete, or does it need an explicit "X more haven't submitted" indicator?
- First-name or last-name alphabetical sort — worth confirming with Ali rather than assuming.
- Should the mayoral race and ward race be one continuous swipe sequence, or two separate entry points the voter chooses between?
