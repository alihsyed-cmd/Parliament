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

## ca_on_toronto_candidates_20260817T152415 — ca_on_toronto — 2026-08-17T15:30:10+00:00

Roster status: registered
Verdict: PASS
Rows: 190  (role-scoped 42, district-scoped 148)  ·  wards represented 25/25
Contact coverage: email 121/190, phone 50/190
Blocking failures: 0   Row failures: 0

## ca_on_london_candidates_20260817T152415 — ca_on_london — 2026-08-17T15:32:35+00:00

Roster status: registered
Verdict: PASS
Rows: 72  (role-scoped 10, district-scoped 62)  ·  wards represented 14/14
Contact coverage: email 59/72, phone 43/72
Blocking failures: 0   Row failures: 0

## ca_on_mississauga_candidates_20260817T152415 — ca_on_mississauga — 2026-08-17T15:32:56+00:00

Roster status: registered
Verdict: PASS
Rows: 70  (role-scoped 10, district-scoped 60)  ·  wards represented 11/11
Contact coverage: email 62/70, phone 53/70
Blocking failures: 0   Row failures: 0

## ca_on_markham_candidates_20260817T152956 — ca_on_markham — 2026-08-17T15:34:54+00:00

Roster status: registered
Verdict: PASS
Rows: 32  (role-scoped 8, district-scoped 24)  ·  wards represented 8/8
Contact coverage: email 26/32, phone 21/32
Blocking failures: 0   Row failures: 0

## ca_on_kitchener_candidates_20260817T152956 — ca_on_kitchener — 2026-08-17T15:35:58+00:00

Roster status: registered
Verdict: PASS
Rows: 38  (role-scoped 4, district-scoped 34)  ·  wards represented 10/10
Contact coverage: email 36/38, phone 24/38
Blocking failures: 0   Row failures: 0

## ca_on_burlington_candidates_20260817T152956 — ca_on_burlington — 2026-08-17T15:37:48+00:00

Roster status: registered
Verdict: PASS
Rows: 27  (role-scoped 5, district-scoped 22)  ·  wards represented 6/6
Contact coverage: email 26/27, phone 17/27
Blocking failures: 0   Row failures: 0

## ca_on_windsor_candidates_20260817T152956 — ca_on_windsor — 2026-08-17T15:38:07+00:00

Roster status: registered
Verdict: PASS
Rows: 33  (role-scoped 7, district-scoped 26)  ·  wards represented 10/10
Contact coverage: email 29/33, phone 14/33
Blocking failures: 0   Row failures: 0

## ca_on_oakville_candidates_20260817T152956 — ca_on_oakville — 2026-08-17T15:38:27+00:00

Roster status: registered
Verdict: PASS
Rows: 41  (role-scoped 4, district-scoped 37)  ·  wards represented 7/7
Contact coverage: email 38/41, phone 29/41
Blocking failures: 0   Row failures: 0

## ca_on_oshawa_candidates_20260817T153336 — ca_on_oshawa — 2026-08-17T15:39:45+00:00

Roster status: registered
Verdict: PASS
Rows: 43  (role-scoped 7, district-scoped 36)  ·  wards represented 5/5
Contact coverage: email 41/43, phone 0/43
Blocking failures: 0   Row failures: 0

## ca_on_barrie_candidates_20260817T153455 — ca_on_barrie — 2026-08-17T15:39:47+00:00

Roster status: registered
Verdict: PASS
Rows: 34  (role-scoped 4, district-scoped 30)  ·  wards represented 10/10
Contact coverage: email 30/34, phone 23/34
Blocking failures: 0   Row failures: 0

## ca_on_vaughan_candidates_20260817T152956 — ca_on_vaughan — 2026-08-17T15:39:48+00:00

Roster status: registered
Verdict: PASS
Rows: 17  (role-scoped 8, district-scoped 9)  ·  wards represented 5/5
Contact coverage: email 9/17, phone 9/17
Blocking failures: 0   Row failures: 0

## ca_on_guelph_candidates_20260817T153455 — ca_on_guelph — 2026-08-17T15:39:59+00:00

Roster status: registered
Verdict: PASS
Rows: 44  (role-scoped 4, district-scoped 40)  ·  wards represented 6/6
Contact coverage: email 39/44, phone 23/44
Blocking failures: 0   Row failures: 0

## ca_on_cambridge_candidates_20260817T153455 — ca_on_cambridge — 2026-08-17T15:41:02+00:00

Roster status: registered
Verdict: PASS
Rows: 35  (role-scoped 12, district-scoped 23)  ·  wards represented 8/8
Contact coverage: email 23/35, phone 9/35
Blocking failures: 0   Row failures: 0

## ca_on_milton_candidates_20260817T153609 — ca_on_milton — 2026-08-17T15:41:04+00:00

Roster status: registered
Verdict: PASS
Rows: 41  (role-scoped 9, district-scoped 32)  ·  wards represented 4/4
Contact coverage: email 38/41, phone 35/41
Blocking failures: 0   Row failures: 0

## ca_on_ottawa_candidates_20260817T152415 — ca_on_ottawa — 2026-08-17T15:41:05+00:00

Roster status: registered
Verdict: PASS
Rows: 69  (role-scoped 6, district-scoped 63)  ·  wards represented 24/24
Contact coverage: email 60/69, phone 35/69
Blocking failures: 0   Row failures: 0

## ca_on_st_catharines_candidates_20260817T153609 — ca_on_st_catharines — 2026-08-17T15:41:28+00:00

Roster status: registered
Verdict: PASS
Rows: 32  (role-scoped 5, district-scoped 27)  ·  wards represented 6/6
Contact coverage: email 27/32, phone 21/32
Blocking failures: 0   Row failures: 0

## ca_on_waterloo_candidates_20260817T153609 — ca_on_waterloo — 2026-08-17T15:41:41+00:00

Roster status: registered
Verdict: PASS
Rows: 23  (role-scoped 1, district-scoped 22)  ·  wards represented 7/7
Contact coverage: email 20/23, phone 8/23
Blocking failures: 0   Row failures: 0

## ca_on_kingston_candidates_20260817T153455 — ca_on_kingston — 2026-08-17T15:41:51+00:00

Roster status: registered
Verdict: PASS
Rows: 37  (role-scoped 4, district-scoped 33)  ·  wards represented 12/12
Contact coverage: email 37/37, phone 31/37
Blocking failures: 0   Row failures: 0

## ca_on_brantford_candidates_20260817T153838 — ca_on_brantford — 2026-08-17T15:42:34+00:00

Roster status: registered
Verdict: PASS
Rows: 30  (role-scoped 6, district-scoped 24)  ·  wards represented 5/5
Contact coverage: email 30/30, phone 28/30
Blocking failures: 0   Row failures: 0

## ca_on_ajax_candidates_20260817T153609 — ca_on_ajax — 2026-08-17T15:43:14+00:00

Roster status: registered
Verdict: PASS WITH ROW FAILURES
Rows: 33  (role-scoped 4, district-scoped 29)  ·  wards represented 3/3
Contact coverage: email 29/33, phone 24/33
Blocking failures: 0   Row failures: 1

### Row failures (logged, non-blocking)
- [email_sanity] Malcolm Andre Barrington — ward Ward 1 — email='Barrington4 ward1@gmail.com' is not an address

## ca_on_brant_candidates_20260817T153838 — ca_on_brant — 2026-08-17T15:43:35+00:00

Roster status: registered
Verdict: PASS
Rows: 27  (role-scoped 3, district-scoped 24)  ·  wards represented 5/5
Contact coverage: email 24/27, phone 26/27
Blocking failures: 0   Row failures: 0

## ca_on_whitby_candidates_20260817T153336 — ca_on_whitby — 2026-08-17T15:43:52+00:00

Roster status: registered
Verdict: PASS
Rows: 32  (role-scoped 3, district-scoped 29)  ·  wards represented 4/4
Contact coverage: email 26/32, phone 25/32
Blocking failures: 0   Row failures: 0

## ca_on_peterborough_candidates_20260817T154000 — ca_on_peterborough — 2026-08-17T15:44:00+00:00

Roster status: unknown
Verdict: PASS
Rows: 31  (role-scoped 6, district-scoped 25)  ·  wards represented 5/5
Contact coverage: email 28/31, phone 14/31
Blocking failures: 0   Row failures: 0

## ca_on_peterborough_candidates_20260817T154000 — ca_on_peterborough — 2026-08-17T15:44:41+00:00

Roster status: unknown
Verdict: PASS
Rows: 31  (role-scoped 6, district-scoped 25)  ·  wards represented 5/5
Contact coverage: email 28/31, phone 14/31
Blocking failures: 0   Row failures: 0

## ca_on_greater_sudbury_candidates_20260817T153838 — ca_on_greater_sudbury — 2026-08-17T15:44:52+00:00

Roster status: registered
Verdict: PASS
Rows: 42  (role-scoped 6, district-scoped 36)  ·  wards represented 12/12
Contact coverage: email 39/42, phone 25/42
Blocking failures: 0   Row failures: 0

## ca_on_norfolk_county_candidates_20260817T154000 — ca_on_norfolk_county — 2026-08-17T15:45:29+00:00

Roster status: registered
Verdict: PASS
Rows: 26  (role-scoped 6, district-scoped 20)  ·  wards represented 7/7
Contact coverage: email 20/26, phone 19/26
Blocking failures: 0   Row failures: 0

## ca_on_toronto_candidates_20260829T194632 — ca_on_toronto — 2026-08-29T19:58:39+00:00

Roster status: certified
Verdict: PASS
Rows: 243  (role-scoped 53, district-scoped 190)  ·  wards represented 25/25
Contact coverage: email 148/243, phone 72/243
Blocking failures: 0   Row failures: 0

## ca_on_mississauga_candidates_20260829T194632 — ca_on_mississauga — 2026-08-29T19:58:43+00:00

Roster status: certified
Verdict: PASS
Rows: 89  (role-scoped 14, district-scoped 75)  ·  wards represented 11/11
Contact coverage: email 79/89, phone 62/89
Blocking failures: 0   Row failures: 0

## ca_on_brampton_candidates_20260829T194632 — ca_on_brampton — 2026-08-29T19:58:45+00:00

Roster status: certified
Verdict: PASS
Rows: 81  (role-scoped 81, district-scoped 0)  ·  wards represented 0/10
Contact coverage: email 62/81, phone 57/81
Blocking failures: 0   Row failures: 0

## ca_on_hamilton_candidates_20260829T194632 — ca_on_hamilton — 2026-08-29T19:58:47+00:00

Roster status: certified
Verdict: PASS
Rows: 89  (role-scoped 13, district-scoped 76)  ·  wards represented 15/15
Contact coverage: email 87/89, phone 47/89
Blocking failures: 0   Row failures: 0

## ca_on_london_candidates_20260829T194632 — ca_on_london — 2026-08-29T19:58:49+00:00

Roster status: certified
Verdict: PASS
Rows: 81  (role-scoped 12, district-scoped 69)  ·  wards represented 14/14
Contact coverage: email 72/81, phone 52/81
Blocking failures: 0   Row failures: 0

## ca_on_markham_candidates_20260829T194632 — ca_on_markham — 2026-08-29T19:58:51+00:00

Roster status: certified
Verdict: PASS
Rows: 44  (role-scoped 14, district-scoped 30)  ·  wards represented 8/8
Contact coverage: email 36/44, phone 27/44
Blocking failures: 0   Row failures: 0

## ca_on_vaughan_candidates_20260829T194632 — ca_on_vaughan — 2026-08-29T19:58:54+00:00

Roster status: certified
Verdict: PASS
Rows: 26  (role-scoped 12, district-scoped 14)  ·  wards represented 5/5
Contact coverage: email 0/26, phone 0/26
Blocking failures: 0   Row failures: 0

## ca_on_windsor_candidates_20260829T194632 — ca_on_windsor — 2026-08-29T19:58:55+00:00

Roster status: certified
Verdict: PASS
Rows: 54  (role-scoped 11, district-scoped 43)  ·  wards represented 10/10
Contact coverage: email 45/54, phone 26/54
Blocking failures: 0   Row failures: 0

## ca_on_oakville_candidates_20260829T194632 — ca_on_oakville — 2026-08-29T19:58:57+00:00

Roster status: certified
Verdict: PASS
Rows: 51  (role-scoped 5, district-scoped 46)  ·  wards represented 7/7
Contact coverage: email 48/51, phone 36/51
Blocking failures: 0   Row failures: 0

## ca_on_kitchener_candidates_20260829T194632 — ca_on_kitchener — 2026-08-29T19:58:58+00:00

Roster status: certified
Verdict: PASS
Rows: 52  (role-scoped 7, district-scoped 45)  ·  wards represented 10/10
Contact coverage: email 47/52, phone 31/52
Blocking failures: 0   Row failures: 0

## ca_on_burlington_candidates_20260829T194632 — ca_on_burlington — 2026-08-29T19:59:02+00:00

Roster status: certified
Verdict: PASS
Rows: 31  (role-scoped 5, district-scoped 26)  ·  wards represented 6/6
Contact coverage: email 28/31, phone 19/31
Blocking failures: 0   Row failures: 0

## ca_on_oshawa_candidates_20260829T194632 — ca_on_oshawa — 2026-08-29T19:59:03+00:00

Roster status: certified
Verdict: PASS
Rows: 57  (role-scoped 9, district-scoped 48)  ·  wards represented 5/5
Contact coverage: email 53/57, phone 1/57
Blocking failures: 0   Row failures: 0

## ca_on_barrie_candidates_20260829T194632 — ca_on_barrie — 2026-08-29T19:59:05+00:00

Roster status: certified
Verdict: PASS
Rows: 41  (role-scoped 4, district-scoped 37)  ·  wards represented 10/10
Contact coverage: email 37/41, phone 28/41
Blocking failures: 0   Row failures: 0

## ca_on_st_catharines_candidates_20260829T194632 — ca_on_st_catharines — 2026-08-29T19:59:07+00:00

Roster status: certified
Verdict: PASS
Rows: 36  (role-scoped 5, district-scoped 31)  ·  wards represented 6/6
Contact coverage: email 31/36, phone 25/36
Blocking failures: 0   Row failures: 0

## ca_on_cambridge_candidates_20260829T194632 — ca_on_cambridge — 2026-08-29T19:59:08+00:00

Roster status: certified
Verdict: PASS
Rows: 40  (role-scoped 11, district-scoped 29)  ·  wards represented 8/8
Contact coverage: email 27/40, phone 13/40
Blocking failures: 0   Row failures: 0

## ca_on_whitby_candidates_20260829T194632 — ca_on_whitby — 2026-08-29T19:59:10+00:00

Roster status: certified
Verdict: PASS
Rows: 33  (role-scoped 3, district-scoped 30)  ·  wards represented 4/4
Contact coverage: email 23/33, phone 19/33
Blocking failures: 0   Row failures: 0

## ca_on_guelph_candidates_20260829T194632 — ca_on_guelph — 2026-08-29T19:59:12+00:00

Roster status: certified
Verdict: PASS
Rows: 49  (role-scoped 6, district-scoped 43)  ·  wards represented 6/6
Contact coverage: email 47/49, phone 27/49
Blocking failures: 0   Row failures: 0

## ca_on_greater_sudbury_candidates_20260829T194632 — ca_on_greater_sudbury — 2026-08-29T19:59:14+00:00

Roster status: certified
Verdict: PASS
Rows: 58  (role-scoped 8, district-scoped 50)  ·  wards represented 12/12
Contact coverage: email 54/58, phone 39/58
Blocking failures: 0   Row failures: 0

## ca_on_brant_candidates_20260829T194632 — ca_on_brant — 2026-08-29T19:59:39+00:00

Roster status: certified
Verdict: PASS
Rows: 33  (role-scoped 6, district-scoped 27)  ·  wards represented 5/5
Contact coverage: email 31/33, phone 31/33
Blocking failures: 0   Row failures: 0

## ca_on_brantford_candidates_20260829T194632 — ca_on_brantford — 2026-08-29T19:59:40+00:00

Roster status: certified
Verdict: PASS
Rows: 37  (role-scoped 7, district-scoped 30)  ·  wards represented 5/5
Contact coverage: email 37/37, phone 34/37
Blocking failures: 0   Row failures: 0

## ca_on_kingston_candidates_20260829T194632 — ca_on_kingston — 2026-08-29T19:59:41+00:00

Roster status: certified
Verdict: PASS
Rows: 36  (role-scoped 4, district-scoped 32)  ·  wards represented 12/12
Contact coverage: email 36/36, phone 31/36
Blocking failures: 0   Row failures: 0

## ca_on_milton_candidates_20260829T194632 — ca_on_milton — 2026-08-29T19:59:42+00:00

Roster status: certified
Verdict: PASS
Rows: 45  (role-scoped 10, district-scoped 35)  ·  wards represented 4/4
Contact coverage: email 40/45, phone 37/45
Blocking failures: 0   Row failures: 0

## ca_on_norfolk_county_candidates_20260829T194632 — ca_on_norfolk_county — 2026-08-29T19:59:44+00:00

Roster status: certified
Verdict: PASS
Rows: 33  (role-scoped 7, district-scoped 26)  ·  wards represented 7/7
Contact coverage: email 23/33, phone 23/33
Blocking failures: 0   Row failures: 0

## ca_on_peterborough_candidates_20260829T194632 — ca_on_peterborough — 2026-08-29T19:59:45+00:00

Roster status: certified
Verdict: PASS
Rows: 35  (role-scoped 7, district-scoped 28)  ·  wards represented 5/5
Contact coverage: email 31/35, phone 16/35
Blocking failures: 0   Row failures: 0

## ca_on_ajax_candidates_20260829T194632 — ca_on_ajax — 2026-08-29T20:00:16+00:00

Roster status: certified
Verdict: PASS WITH ROW FAILURES
Rows: 36  (role-scoped 5, district-scoped 31)  ·  wards represented 3/3
Contact coverage: email 32/36, phone 24/36
Blocking failures: 0   Row failures: 1

### Row failures (logged, non-blocking)
- [email_sanity] Malcolm Andre Barrington — ward Ward 1 — email='Barrington4 ward1@gmail.com' is not an address

## ca_on_waterloo_candidates_20260829T194632 — ca_on_waterloo — 2026-08-29T20:00:41+00:00

Roster status: certified
Verdict: PASS WITH ROW FAILURES
Rows: 28  (role-scoped 5, district-scoped 23)  ·  wards represented 7/7
Contact coverage: email 27/28, phone 9/28
Blocking failures: 0   Row failures: 1

### Row failures (logged, non-blocking)
- [required_fields] Abdullah — ward Ward 7 — empty first_name

## ca_on_ottawa_candidates_20260829T194632 — ca_on_ottawa — 2026-08-30T20:50:26+00:00

Roster status: certified
Verdict: PASS
Rows: 101  (role-scoped 14, district-scoped 87)  ·  wards represented 24/24
Contact coverage: email 90/101, phone 51/101
Blocking failures: 0   Row failures: 0

## ca_on_thunder_bay_candidates_20260831T140935 — ca_on_thunder_bay — 2026-08-31T14:12:37+00:00

Roster status: certified
Verdict: PASS
Rows: 46  (role-scoped 24, district-scoped 22)  ·  wards represented 7/7
Contact coverage: email 44/46, phone 41/46
Blocking failures: 0   Row failures: 0

## ca_on_richmond_hill_candidates_20260831T141435 — ca_on_richmond_hill — 2026-08-31T14:21:33+00:00

Roster status: certified
Verdict: PASS
Rows: 33  (role-scoped 6, district-scoped 27)  ·  wards represented 6/6
Contact coverage: email 20/33, phone 13/33
Blocking failures: 0   Row failures: 0
