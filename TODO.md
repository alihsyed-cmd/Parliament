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

## Data Quality

### [Phase 2.6 or 2.7] Federal name-join Unicode mismatch (7 ridings affected)
**Reported:** 2026-04-26 (Milestone 2.3)
**Context:** 2 federal reps (Luc Berthold, Bienvenu-Olivier Ntumba) and 5 federal districts (Mégantic—L'Érable—Lotbinière, Mont-Saint-Bruno—L'Acadie, Terrebonne, University—Rosedale, Scarborough Southwest) failed to link during Supabase migration. The boundary shapefile and the ourcommons.ca XML use different Unicode characters for apostrophes (U+0027 vs U+2019) and dashes (- vs —), causing string-based joins to fail silently.
**Pattern:** Name-based joins are fragile to typography. Long-term fix should be either (a) Unicode normalization (NFKC) on both sides before join, (b) switch federal join to use riding numerical codes if available in both data sources, or (c) fuzzy match for federal as fallback.
**Action:** Address during API-first ingestion (2.6) when we revisit data sources, or during expansion (2.7) when adding cities forces a normalization layer.
**Workaround:** None needed for v1 — the affected ridings still appear in the database, lookups for those postal codes return the district but no representative.
