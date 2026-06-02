# Parliament — Frontend (Next.js)

A clean, from-scratch Next.js frontend for Parliament, built to the **live v2 API contract**. Fully responsive (mobile-first, scales to desktop), self-contained fonts, and structured so it can later be wrapped as a native iOS/Android app.

This package replaces whatever is currently failing to deploy on Vercel (which was built against the old API format).

---

## TL;DR — get it running

```bash
# 1. from the folder you dropped this into:
npm install

# 2. point it at the API (optional — defaults to staging)
cp .env.local.example .env.local

# 3. run it
npm run dev
# → http://localhost:3000
```

You should see the entry screen. Type `M5V 3A8` → your Toronto reps load from the live API.

---

## First: which Next.js setup do you have?

You said you weren't sure about your router. Here's how to check your **existing** repo, and how this package fits.

**App Router vs Pages Router** — look at your repo's top level:
- If there's an **`app/`** directory with a `layout.tsx` → you're on the **App Router**. ✅ This package is App Router. Drop-in.
- If there's a **`pages/`** directory with `_app.tsx` → you're on the **Pages Router**. This package will still run (Next supports both simultaneously), but the cleanest move is to migrate to `app/` or tell me and I'll regenerate for `pages/`.

**TypeScript vs JS** — this package is **TypeScript** (`.ts`/`.tsx`). Next 16 scaffolds TS by default, so you're very likely already there. If your repo is plain JS, the files still compile (Next transpiles TS regardless), you just need the dev-dependencies in `package.json` here.

**Recommendation:** since you're building the frontend from scratch, start a fresh Next.js App Router + TypeScript project and drop these files in — don't fight an old structure. The cleanest path:

```bash
npx create-next-app@latest parliament --ts --app --no-tailwind --no-src-dir
# then copy the folders below into it, overwriting app/ as noted
```

---

## What's in this package

```
app/
  layout.tsx        ← fonts (next/font) + <html>/<body> + metadata. REPLACES your layout.
  page.tsx          ← the app: routing + data fetching orchestration
  globals.css       ← the entire design system (tokens + components). REPLACES your globals.

components/
  Icon.tsx          ← inline SVG icon set
  ui.tsx            ← Avatar, PartyChip, RepRow, Countdown, Skeleton, Spinner, BrandMark
  EntryScreen.tsx   ← postal-code entry (hero)
  LookupScreen.tsx  ← results: 3 levels (accordion on mobile, side-by-side on desktop) + coverage gaps
  RosterScreen.tsx  ← browse a whole jurisdiction (leadership block + searchable list)
  DetailScreen.tsx  ← one representative, contact-first, with multi-role support
  StatusScreens.tsx ← loading skeleton + error states
  ReminderToggle.tsx← election-reminder opt-in (see "Election reminders" below)

lib/
  types.ts          ← TypeScript types mirroring the API contract
  api.ts            ← the API client. ★ The only file that knows about HTTP. ★
  derived.ts        ← client-side derivations (initials, party color, cabinet dedupe, coverage-gap padding)
  reminders.ts      ← localStorage stub for election reminders
  format.ts         ← date / countdown / level-label helpers

.env.local.example  ← API base URL config
next.config.js, tsconfig.json, package.json, .gitignore, next-env.d.ts
```

**If integrating into an existing project:** copy `components/` and `lib/` wholesale, merge `app/layout.tsx` (you need the font setup) and `app/page.tsx`, and replace `app/globals.css`. The `@/*` import alias is set in `tsconfig.json` — make sure yours matches.

---

## How it connects to your API

Everything funnels through **`lib/api.ts`**. It reads the base URL from:

```
NEXT_PUBLIC_PARLIAMENT_API
```

- **Local dev:** set it in `.env.local` (see `.env.local.example`).
- **Vercel:** Project → Settings → Environment Variables → add `NEXT_PUBLIC_PARLIAMENT_API` = your production API URL. Redeploy.
- If unset, it falls back to the staging URL so nothing breaks.

Endpoints consumed:

| Method | Endpoint | Screen |
|---|---|---|
| `api.lookup(postal)` | `GET /lookup?postal_code=` | Entry → Lookup |
| `api.jurisdiction(slug)` | `GET /jurisdiction/<slug>` | Roster ("See all") |
| `api.representative(jur, slug)` | `GET /representative/<jur>/<slug>` | Detail (multi-role) |

### CORS

Your API must allow the frontend's origin. Add these to `ALLOWED_ORIGINS` on Render:
- `http://localhost:3000` (local dev)
- your Vercel preview + production domains (e.g. `https://parliament.vercel.app`, and any custom domain)

---

## Data handling worth knowing

These are decisions baked into `lib/derived.ts` — adjust there if your data shifts.

1. **Initials & party colors are derived client-side.** The API doesn't ship them. `getInitials()` strips honorifics; `getPartyClass()` fuzzy-matches `party_name` to a color slug. **Extend the `PARTY_MAP` table** as you add provincial parties — anything unmatched falls back to a neutral "independent" gray, which is safe but generic.

2. **Cabinet de-duplication.** Your live data repeats a person once per portfolio (e.g. a Deputy Premier who is also Minister of Health appears twice with the same `uuid`). `dedupeByUuid()` collapses these into one card and collects the titles into a `roles[]` array, surfaced on the detail screen. **If you'd rather show every portfolio as its own row, remove the dedupe call** in `enrichLevelArrays()`.

3. **Coverage gaps = missing levels.** The API omits a level when no jurisdiction covers the point. `normalizeLookup()` pads the `levels[]` array up to all three expected levels, flagging stubs with `_gap: true` so the UI can render a "coverage coming soon" card. If you add territorial/other levels, update `EXPECTED_LEVELS`.

4. **Photos.** `photo_url` is rendered via a plain `<img>` with an initials fallback if it 404s. For Next's image optimization, switch `Avatar` in `components/ui.tsx` to `next/image` and whitelist the host domains in `next.config.js` (commented stub included).

---

## Election reminders (the new V1 feature)

There's a **"Remind me before elections"** toggle on the lookup screen (`components/ReminderToggle.tsx`).

**What it does today:** persists the user's consent + postal code to `localStorage` (`lib/reminders.ts`). That's it — the UI exists, consent is captured, expectation is set.

**What it does NOT do:** send notifications. This is deliberate. Web push is unreliable/restricted on iOS, and reminders are inherently a native-app capability. **Wire the actual delivery during the native build:**

1. In `saveReminder()`, request OS notification permission and register for APNs (iOS) / FCM (Android) to get a push token.
2. `POST { postal_code, push_token, locale }` to a new backend endpoint.
3. A scheduled backend job reads each jurisdiction's `next_election` and fires a reminder N days out.

The seams are marked with `NATIVE TODO` comments. Nothing in the UI needs to change.

---

## Desktop / responsive behavior

Fully fluid — there's no fixed phone frame.
- **Entry:** hero goes two-column above 860px.
- **Lookup:** the three levels stack as an accordion on mobile; at ≥920px they render side-by-side as three open panels (a dashboard), no tapping required.
- **Detail:** single column on mobile, two columns (contact/role + term/jurisdiction) above 800px.
- Reading columns are capped (`--maxw`) so text doesn't sprawl on ultrawide monitors.

Tune the breakpoints and max-widths at the top of `globals.css` (`:root` variables).

---

## Path to the app stores

This is a standard React/Next codebase, so the usual wrapping options apply:

- **Capacitor** (recommended for a web-first app like this): `next build` with `output: "export"` for the static shell, wrap with Capacitor, and the `NATIVE TODO` hooks in `reminders.ts` become your push integration. Note: a fully static export means giving up server components/SSR — fine here since the app is client-rendered against your API.
- The component + lib split means none of the UI logic has to be rewritten; only the routing wrapper (`app/page.tsx`) and the native bridges change.

When you're ready for that phase, I can produce the Capacitor config, the static-export adjustments, and the push-notification integration as a follow-up.

---

## Open items / where I made assumptions

- **Politician slugs.** The detail screen calls `/representative/<jur>/<slug>` using `rep.slug`, falling back to `rep.uuid` if the slug is empty. Confirm the slug backfill (the TECH DEBT note in `api.py`) has run, or the detail fetch will rely on UUIDs.
- **`representations[]`.** Used to show every role a person holds on the detail screen. If the endpoint doesn't return it, the screen falls back to the `roles[]` collected during cabinet dedupe.
- **Verified date / source URL.** The detail screen shows `last_verified` and `source_url` from `/representative/...` when present; otherwise it shows a generic "from official sources."
- **"Notify me" / "Help map it"** buttons on the coverage-gap card are not yet wired to a backend — they're the same future endpoint as the reminder feature.
