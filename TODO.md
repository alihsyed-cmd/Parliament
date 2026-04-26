# Parliament — Deferred Work Log

Captures known issues, enhancements, and follow-ups that aren't blocking current work but should be addressed at the right time.

## Display & Output Format

### [Phase 3] Toronto ward display: append ward name to ward number
**Reported:** 2026-04-26 (Milestone 2.2)
**Context:** Toronto's official council site primarily references wards by name (e.g., "Humber River–Black Creek") rather than number. Currently the API returns ward as `"7"`. Should display as `"Ward 7 Humber River-Black Creek"` or similar.
**Why deferred:** Display formatting is frontend concern (Phase 3). Backend correctly returns the canonical ward number; the frontend should compose the human-readable label.
**Action:** When building the React components in Phase 3, format Toronto's `ward` field as `"Ward {number} {name}"` using the GeoJSON's `AREA_NAME` field. May need to expose ward name in the API response.

## Data Quality

### [Phase 2.3+] Investigate 3 missing federal MPs
**Reported:** 2026-04-25 (Milestone 2.1)
**Context:** Federal adapter loads 352 boundaries but only 340 reps. Canada has 343 ridings. The 3 missing are likely vacant seats awaiting by-elections, or name-mismatch edge cases between shapefile and XML.
**Action:** During Supabase migration, add validation that flags ridings with no representative.

## Ecosystem / Maintenance

### [Background] pyogrio DeprecationWarning about shapely.geos
**Reported:** 2026-04-26 (Milestone 2.2)
**Context:** `pyogrio` imports the deprecated `shapely.geos` module. Pure ecosystem issue, not our code.
**Action:** No action needed. Will resolve when pyogrio releases a version compatible with Shapely 2.0's namespace changes. Re-check periodically when updating dependencies.
