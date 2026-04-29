# Parliament — Deferred Work Log

Captures known issues, enhancements, and follow-ups that aren't blocking current work but should be addressed at the right time.

## Active — Phase 3

Currently in progress. See dedicated entries below for details.

- CORS lockdown to specific Vercel origins (Security)
- .DS_Store cleanup (Repo hygiene)

## Display & Output Format

### [Phase 3] Toronto ward display: append ward name to ward number
**Reported:** 2026-04-26 (Milestone 2.2)
**Context:** Toronto's official council site primarily references wards by name (e.g., "Humber River–Black Creek") rather than number. Currently the API returns ward as `"7"`. Should display as `"Ward 7 Humber River-Black Creek"` or similar.
**Why deferred:** Display formatting is frontend concern (Phase 3). Backend correctly returns the canonical ward number; the frontend should compose the human-readable label.
**Action:** When building the React components in Phase 3, format Toronto's `ward` field as `"Ward {number} {name}"` using available data. May need to expose ward name in the API response.

## Data Quality

### [Phase 2.6 or 2.7] Federal name-join Unicode mismatch (7 ridings affected)
**Reported:** 2026-04-26 (Milestone 2.3)
**Context:** 2 federal reps (Luc Berthold, Bienvenu-Olivier Ntumba) and 5 federal districts (Mégantic—L'Érable—Lotbinière, Mont-Saint-Bruno—L'Acadie, Terrebonne, University—Rosedale, Scarborough Southwest) failed to link during Supabase migration. The boundary shapefile and the ourcommons.ca XML use different Unicode characters for apostrophes (U+0027 vs U+2019) and dashes (- vs —), causing string-based joins to fail silently.
**Pattern:** Name-based joins are fragile to typography. Long-term fix should be either (a) Unicode normalization (NFKC) on both sides before join, (b) switch federal join to use riding numerical codes if available in both data sources, or (c) fuzzy match for federal as fallback.
**Action:** Address during API-first ingestion (2.6) when we revisit data sources, or during expansion (2.7) when adding cities forces a normalization layer.
**Workaround:** None needed for v1 — the affected ridings still appear in the database, lookups for those postal codes return the district but no representative.

### [Phase 2.3+] Investigate 3 missing federal MPs
**Reported:** 2026-04-25 (Milestone 2.1)
**Context:** Federal adapter loads 343 ridings but only 340 reps after migration. Canada has 343 ridings. The 3 missing are likely vacant seats awaiting by-elections, or name-mismatch edge cases between shapefile and XML (some overlap with the Unicode issue above).
**Action:** Likely resolved by the Unicode normalization fix in 2.6/2.7. If gap remains after that, investigate vacant seat data.

## Security

### [Phase 3] Lock down CORS allowed origins
**Reported:** 2026-04-28
**Context:** ALLOWED_ORIGINS on Render is currently set to "*" because frontend URL is in flux during Vercel preview deploys. Acceptable for staging, but production must restrict to specific domains.
**Action:** When wiring frontend to call API, set ALLOWED_ORIGINS to the production Vercel domain plus any preview URL pattern needed (e.g., regex-based handling, or use Vercel's deployment URL conventions). Update before soft launch.

## Performance & Cost

### [Phase 3] Geocoding cache for postal codes
**Reported:** 2026-04-28 (Phase 3 kickoff)
**Context:** Every /lookup call currently hits Google's Geocoding API, even for postal codes already seen. Postal codes are immutable, so cached results stay valid indefinitely. Without a cache, cost scales linearly with request volume and the API is exposed to scraping (~850k Canadian postal codes × $5/1000 = ~$4,250 to enumerate the entire space).
**Action:** Add geocode_cache table to Supabase (postal_code PK, lat, lon, retrieved_at). Modify api.py geocode() to check cache first, call Google on miss, store result. Log cache hit/miss for observability.
**Status:** Complete (Task 4, deployed 2026-04-28). Verified MISS → HIT pattern with H3A0G4 fresh postal code on staging.

### [Phase 3 launch prep] Upgrade Render to Starter plan ($7/month)
**Reported:** 2026-04-28
**Context:** Free tier sleeps after 15 min idle, causing 10-15s cold starts on first request. Acceptable for development, unacceptable for real users.
**Action:** Upgrade before soft launch.

### [Future / Optional] Render Static Outbound IPs ($5/month)
**Reported:** 2026-04-28
**Context:** Would let us re-enable IP allowlisting on the Google Maps API key for defense in depth. Currently key is restricted by API (Geocoding only) and quota only.
**Action:** Evaluate if we ever want belt-and-suspenders cost protection beyond what API restriction + quota + cache provides.

## Architecture / Technical Debt

### [Phase 2.6] Remove legacy_loader.py once API-first ingestion lands
**Reported:** 2026-04-26 (Milestone 2.3)
**Context:** `scripts/legacy_loader.py` exists solely to support the one-time migration script. It duplicates the file-loading logic that used to live in WardBasedAdapter. It is not used at runtime.
**Action:** When milestone 2.6 introduces API-first ingestion (CKAN, OpenDataSoft, etc.), the new ingestion pipeline replaces both the legacy loader and the migration script. Delete both at that point.

### [Phase 3 launch prep] Replace single shared psycopg2 connection with connection pool
**Reported:** 2026-04-28 (Task 4)
**Context:** scripts/db.py uses one shared `_connection` object. Safe under WEB_CONCURRENCY=1 (Render's current default for free/Starter tier on a 1-CPU instance) but unsafe under concurrent requests — two requests sharing one cursor can corrupt each other's state. A working ThreadedConnectionPool implementation exists locally in `git stash` under "task-4-fix-with-pool-refactor"; was deferred to keep Task 4 (geocoding cache) scoped.
**Action:** Revisit as its own task before increasing Render worker count or before launch. Either apply the stash on a fresh branch, or rewrite the pool module from scratch with intentional concurrency testing.

## Ecosystem / Maintenance

### [Background] pyogrio DeprecationWarning about shapely.geos
**Reported:** 2026-04-26 (Milestone 2.2)
**Context:** `pyogrio` imports the deprecated `shapely.geos` module. Pure ecosystem issue, not our code.
**Action:** No action needed. Will resolve when pyogrio releases a version compatible with Shapely 2.0's namespace changes. Re-check periodically when updating dependencies.

## Repo hygiene

### [Phase 3] Remove tracked .DS_Store from data/municipal/
**Reported:** 2026-04-28
**Context:** data/municipal/.DS_Store was committed before .gitignore excluded it. Should be removed from version control and verified absent from all data/ subdirectories.
**Action:** `git rm --cached data/municipal/.DS_Store && git commit -m "chore: untrack .DS_Store"`. Audit other directories for similar leftovers.

## Lessons Learned

### Multi-polygon districts must be unioned, not deduplicated
**Discovered:** 2026-04-26 (Milestone 2.3)
**Context:** During migration to PostGIS, the Halifax federal riding's mainland portion was silently discarded because it shared a name with the Sable Island portion. The original migration treated multi-polygon districts as duplicates and kept only the first. Halifax users got 0 federal reps because the only Halifax polygon in the database was on Sable Island, 290 km offshore.
**Resolution:** Migration script now uses `shapely.ops.unary_union` to merge multiple polygons per district into a single MultiPolygon.
**Application:** This pattern applies broadly. Many Canadian ridings span multiple polygons (Vancouver Island, Newfoundland, coastal Quebec, the Toronto Islands). Any future ingestion logic that touches geometry must preserve all polygons per district, not deduplicate by name.

## Display & Output Format

### [Phase 3] Sort leadership in canonical order, not alphabetically
**Reported:** 2026-04-27 (Milestone 2.4.5)
**Context:** Currently leadership arrays are sorted by `start_date ASC NULLS LAST`. For display purposes, users expect Premier first, Deputy Premier second, then ministers in order of precedence. The federal cabinet CSV has a `Precedence` column we could use; the Ontario CSV doesn't, so a manual sort or a small mapping table would be needed.
**Why deferred:** Display ordering is frontend concern. Backend correctly returns all data; the frontend should sort by role hierarchy if desired.
**Action:** When rendering leadership in Phase 3, apply a sort: Premier/PM/Mayor first, then Deputy/Vice-, then alphabetical by role.

### [Future] Federal cabinet "Title" field contains compound roles
**Reported:** 2026-04-27 (Milestone 2.4.5)
**Context:** Some federal cabinet members hold multiple roles in a single CSV row, concatenated with " and " (e.g., Joël Lightbound: "Minister of Government Transformation, Public Works and Procurement and Quebec Lieutenant"). The current loader treats this as one role title.
**Action:** When backend supports multi-role display per minister, parse compound titles into separate role rows. Low priority for v1.


### [Phase 3 — when frontend has real code] Wire Sentry into Next.js
**Reported:** 2026-04-28 (Task 5)
**Context:** Backend Sentry is live and verified end-to-end. Frontend Sentry was deferred because the current Next.js scaffold is empty — wiring it now would mean maintaining a dependency for no signal. Sentry account already exists; second project (`parliament-frontend`) is created with a DSN ready to use.
**Action:** Add `@sentry/nextjs` package, run `npx @sentry/wizard@latest -i nextjs`, set `SENTRY_DSN` env var on Vercel for production and preview environments. Verify with a deliberate test error like we did for Flask.
**Trigger:** Add this when starting Task 7 (lookup UI) — once real components exist that could throw real errors.


### [Phase 3 — when needed] Add narrow RLS policies if frontend ever queries Supabase directly
**Reported:** 2026-04-28 (Task 6)
**Context:** RLS is enabled on all five public tables (jurisdictions, districts, representatives, representations, geocode_cache) with zero policies, meaning the anon role has no access. Flask uses SUPABASE_DB_URL (direct Postgres) which bypasses RLS, so the API works normally.
**Trigger:** If we later decide to let the frontend query Supabase directly (e.g., for read-only public data not routed through Flask), add narrowly-scoped SELECT policies for the anon role on the specific tables and columns needed.


### [Phase 3] Reject vague Google geocoding results
**Reported:** 2026-04-29 (discovered during frontend testing)
**Context:** Google Maps Geocoding API returns Canada's geographic centroid (~56.13, -106.35, near La Ronge, Saskatchewan) when it can't resolve a postal code. Currently scripts/api.py geocode() accepts any "OK" status response without checking precision, so a typo'd postal code resolves to the middle of nowhere and the spatial lookup silently returns empty results. User sees a coverage-gap-style empty response with no indication that the postal code was invalid.
**Action:** In scripts/api.py geocode(), check `data["results"][0]["geometry"]["location_type"]`. Treat "APPROXIMATE" as a failed geocode (return None, None). "GEOMETRIC_CENTER" is the expected precision for postal codes. May also want to verify the result's `address_components` includes the queried postal code as a postal_code component, to catch cases where Google maps a typo'd code to a different valid one.
**Trigger:** Before Phase 3 launch. Currently masking real validation failures behind coverage-gap UI.


### [Phase 3.5] Dedicated representative pages
**Reported:** 2026-04-29 (Task 7 design)
**Context:** Currently representative details surface in modals on the lookup results page. For shareability, SEO, and civic-tech values around discoverability, individual representatives should have their own URLs (e.g., parliament.app/representative/ca/mark-carney). Search engines indexing per-rep pages would be powerful — "who is my MP" type queries should land on Parliament.
**Action:** (1) Backend: add /representative/:jurisdiction_id/:rep_id endpoint. (2) Frontend: add /representative/[jurisdiction]/[id] route. (3) Decide URL slug strategy (id vs name-based slug). (4) Open Graph / Twitter Card metadata so shared links preview well.
**Trigger:** After Phase 3 lookup UI is shipped and validated. Modal-based detail view is acceptable for v1.


### [Phase 3] Photo URL fallback when image fails to load
**Reported:** 2026-04-29 (Task 7 testing — Fraser Tolmie federal MP photo)
**Context:** Some federal MP photo URLs from ourcommons.ca return 404 or are broken. Currently the broken-image icon displays. Should fall back to the same gray placeholder used when photo_url is null.
**Action:** In RepresentativeCard and RepresentativeModal, add onError handler to swap to the placeholder. Could also be addressed at ingestion time (validate photo URLs and store null on 404), but frontend handling is simpler and handles future breakage too.
