# Candidate validation log

## ca_on_hamilton_candidates_20260809T235752 — ca_on_hamilton — 2026-08-10T00:00:00Z

Roster status: registered
Verdict: PASS
Rows: 64  (role-scoped 8, district-scoped 56)  ·  wards represented 15/15
Contact coverage: email 62/64, phone 31/64
Blocking failures: 0   Row failures: 0

## ca_on_brampton_candidates_20260813T143649 — ca_on_brampton — 2026-08-14T11:51:15Z

Roster status: registered
Verdict: PASS WITH ROW FAILURES
Rows: 60  (role-scoped 60, district-scoped 0)  ·  wards represented 0/10
Contact coverage: email 46/60, phone 43/60
Blocking failures: 0   Row failures: 1

Noted condition: this run deliberately binds all candidates jurisdiction-wide (role_scope="role", district_id empty) rather than per-ward, because Brampton pairs its 10 wards into 5 two-ward races and raw_candidates permits only one row/uuid per candidate — a per-ward district_id would have produced two invitation tokens per councillor campaign. The 51 councillor rows carry the human-readable ward-pair label in district_name ("Wards 1 & 5", etc.), which is intentional and outside the scope_district_consistency CHECK (that constraint governs district_id only). No row violated the constraint (no role_scope="role" row had a non-empty district_id). Check 9 (district_id join match) had nothing to run against, as expected for this binding — not a failure.

Namespace note for future readers: the project's candidate UUID namespace was pinned to c4a7d1e2-9f3b-5c6d-8e1a-2b3c4d5e6f7a on 2026-08-13 during this Brampton run and written into .claude/agents/candidate-consolidation.md, which previously carried an unfilled placeholder. All 60 Brampton UUIDs were independently recomputed against this namespace (key = slug|first_name|last_name|role_scope|district_id, NFC-normalized, casefolded, stripped) and verified to match exactly. The earlier Hamilton candidate run (see entry above) used a different namespace that was never persisted and is not recoverable — Hamilton's certified-list rerun after 2026-08-24 must reuse the UUIDs already stored in data/ca_on_hamilton/raw_candidates.csv (matched by name) rather than regenerating them, or it will orphan any invitation already issued for Hamilton.

### Row failures (logged, non-blocking)
- [required_field]  Gursimranjit Singh — ward — — empty required field 'first_name'. The source roster ("Gursimranjit Singh, -") only captured a single name field for this mayoral candidate; flagged for human review, not treated as file corruption.
