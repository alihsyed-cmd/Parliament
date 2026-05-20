# Parliament — Data Schemas

Canonical column definitions for `jurisdictions.csv` and `politicians.csv`. The agentic pipeline (see `CLAUDE.md`) produces files conforming to these schemas before they are upserted to Supabase.

_Last revised: 2026-05-19 — politicians.csv path updated to slug-flat layout (`data/<slug>/`)._
_Prior revision 2026-05-18 — removed `has_mayor`; `standard_role` enum reduced to 4 values; `specific_title` semantics broadened and abbreviations dropped._

---

## `jurisdictions.csv` — Schema

One row per jurisdiction. The agentic pipeline appends one row per new jurisdiction registered.

| Column | Type | Description |
|---|---|---|
| `slug` | text | Stable machine-readable identifier. Format: `<country>_<province>_<city>` or `<country>_<province>` or `<country>_federal`. Examples: `ca_federal`, `ca_on`, `ca_on_hamilton`, `ca_bc_vancouver`. Lowercase, underscores only. Also serves as the jurisdiction's folder name under `data/`. |
| `name_en` | text | Human-readable English name. Examples: "Canada", "Ontario", "Hamilton". |
| `name_fr` | text | Human-readable French name. Often identical to English for proper nouns. |
| `level` | text | Enum: `federal`, `provincial`, `municipal`, `state`, `territorial`. |
| `country_code` | text | ISO 3166-1 alpha-2 code. Examples: `CA`, `US`, `DE`. |
| `province_code` | text | ISO 3166-2 subdivision code. Examples: `ON`, `BC`, `QC`. Empty for federal jurisdictions. |
| `parent_slug` | text | For nested jurisdictions (e.g., Montreal boroughs nested inside Montreal). Empty for top-level jurisdictions. |
| `governance_type` | text | Enum: `ward_based`, `at_large`, `nested_borough`, `consensus`. Describes the structural model. |
| `partisan` | boolean | `true` if politicians at this level have party affiliations. `false` for non-partisan systems (most Canadian municipal). |
| `district_term_en` | text | English label for districts at this level. Examples: "Ward", "Riding", "Borough". |
| `district_term_fr` | text | French equivalent. Examples: "Quartier", "Circonscription", "Arrondissement". |
| `role_label_singular_en` | text | English singular form of the district-rep role. Examples: "Councillor", "MP", "MPP". |
| `role_label_plural_en` | text | English plural. Examples: "Councillors", "MPs", "MPPs". |
| `role_label_singular_fr` | text | French singular. Examples: "Conseiller", "député", "député provincial". |
| `role_label_plural_fr` | text | French plural. Examples: "Conseillers", "députés", "députés provinciaux". |
| `expected_district_count` | integer | Total number of districts this jurisdiction is divided into. Used for validation against actual loaded data. Examples: 25 (Toronto), 343 (federal), 15 (Hamilton), 124 (Ontario). |
| `expected_cabinet_count` | integer | Total number of role-scoped positions expected (Mayor + cabinet ministers, or Premier + cabinet, or PM + cabinet). For Toronto: 1. For Ontario: 42. For federal: 38. For Hamilton: 1. |
| `last_election` | date (YYYY-MM-DD) | Date of the most recent election that determined the current officeholders. Used as a fallback when individual politician `date_elected` values are missing. |
| `election_date_set` | boolean | `true` if `next_election` is a hard, scheduled date. `false` if it's an estimate based on `term_duration_years`. |
| `next_election` | date (YYYY-MM-DD) | Next scheduled election date. Empty if `election_date_set` is `false`. |
| `term_duration_years` | integer | Length of an elected term. Used to estimate next election when `election_date_set` is false. Examples: 4 (most Canadian jurisdictions), 2 (US House). |
| `governance_summary_en` | text | A 1-3 sentence English explanation of how this jurisdiction's government is organized. Example: "Hamilton voters elect a mayor and 15 city councillors who together form the 16-member city council. The mayor is elected city-wide; each councillor represents one of 15 wards." |
| `governance_summary_fr` | text | French equivalent of `governance_summary_en`. |
| `boundary_file` | text | Filename of the boundary file in the jurisdiction's data folder. Examples: `Ward_Boundaries.shp`, `wards.geojson`. The register script reads this to know which file to ingest. |
| `boundary_district_id_column` | text | Name of the column in the boundary file that contains the district identifier. Examples: `WARD`, `AREA_SHORT_CODE`, `RIDING_NAME`. Must match values found in `politicians.csv`'s `district_id` column. |

**25 columns total.**

---

## `politicians.csv` — Schema

One row per politician per role. A politician holding multiple roles (e.g., MP who is also PM who is also a party leader) appears in multiple rows with the same UUID. Lives at `data/<slug>/politicians.csv`. The jurisdiction is implied by the file's path (no slug column needed inside the file).

| Column | Type | Description |
|---|---|---|
| `uuid` | UUID | Stable identifier for this politician *within this jurisdiction*. Generated deterministically (UUID5) from `<slug>\|<first_name>\|<last_name>` so re-runs produce the same UUID for the same person. The same person holding multiple roles within one jurisdiction uses the same UUID across all their rows. See "UUID generation" below for rationale and known limitations. |
| `role_scope` | text | Enum: `district` or `role`. `district` for politicians who represent a geographic area (MP, MPP, Councillor). `role` for politicians who hold a jurisdiction-wide position (Mayor, Premier, PM, cabinet minister, party leader, opposition leader, critic). |
| `district_id` | text | When `role_scope` is `district`: the identifier matching the boundary file's district ID column. Examples: `WARD 1`, `Humber River—Black Creek`, `7`. Empty when `role_scope` is `role`. |
| `district_name_en` | text | Human-readable English name of the district. Examples: "Ward 1", "Humber River—Black Creek". Empty for role-scoped politicians. |
| `district_name_fr` | text | French equivalent. Often identical for proper nouns; localized for generic terms like "Quartier 1". Empty for role-scoped politicians. |
| `honorific` | text | Title prefix. Examples: `Hon.`, `Right Hon.`, `Dr.`, `Mr.`, `Ms.`. Empty if none. |
| `first_name` | text | Given name(s). |
| `last_name` | text | Family name. |
| `standard_role` | text | Enum: `representative`, `executive`, `cabinet`, `misc`. The role *category*: `representative` for district-elected reps; `executive` for the single jurisdiction-wide head of government (Mayor, Premier, Prime Minister); `cabinet` for cabinet ministers and deputy executives; `misc` for everything else (party leaders, opposition leaders, critics, Speakers, etc.). The frontend uses this enum directly to surface the executive alongside the user's district representatives. |
| `specific_title` | text | The politician's specific role title within their `standard_role` category. Always populated. Use full official titles, never abbreviations — the frontend handles display abbreviation. For `representative`: full role title (`Member of Parliament`, `Member of Provincial Parliament`, `Member of the Legislative Assembly`, `Councillor`). For `executive`: the executive title (`Mayor`, `Premier`, `Prime Minister`). For `cabinet`: the portfolio (`Minister of Foreign Affairs`, `Deputy Premier`). For `misc`: the role description (`Leader of the Official Opposition`, `Critic, Intergovernmental Affairs`); for party leaders specifically, the leadership-of-party formulation (`Leader of the Progressive Conservative Party of Ontario`). |
| `party_name` | text | Party affiliation. Examples: "Liberal", "Conservative", "NDP", "Green Party". Empty for independents or non-partisan systems. |
| `date_elected` | date (YYYY-MM-DD) | When this politician was elected to this specific role. Empty if unknown; frontend falls back to jurisdiction's `last_election`. |
| `next_election` | date (YYYY-MM-DD) | When this specific role is next up for election. Empty if not set; frontend falls back to jurisdiction's `next_election` or estimates from `term_duration_years`. |
| `phone` | text | Contact phone number. Examples: `905-546-2416`, `+1 416-338-5335`. |
| `email` | text | Contact email. Should be the politician's official office email, not personal. |
| `website` | text | Official politician page on their government's website. |
| `photo_url` | text | Direct URL to an official headshot. Must be a hotlinkable image URL, not a page containing the image. |
| `source_url` | text | URL of the page from which this politician's data was sourced. Used for auditing and freshness verification. |
| `last_verified` | date (YYYY-MM-DD) | Date the agentic pipeline last confirmed this row's data is accurate. Derived from the run_id date portion. Set on creation; updated on each refresh pass. |

**19 columns total.**

---

## Notes for the Agentic Pipeline Builder

**UUID generation.**
The same person must always produce the same UUID across re-runs *within a given jurisdiction*. Recommended approach: `uuid.uuid5(namespace, canonical_string)` where `canonical_string` is `<slug>|<first_name>|<last_name>`, lowercased, NFC-normalized, and stripped. The namespace UUID is a fixed constant for the project. If a politician changes role within the same jurisdiction (e.g., MPP becomes Premier), their UUID stays the same; only the row's `role_scope`, `standard_role`, and `specific_title` change.

Jurisdiction is included in the hash deliberately, to prevent silent collisions between unrelated people with the same name in different jurisdictions (e.g., two "Robert Smith"s) once all `politicians.csv` files merge in Supabase. The known cost is that cross-jurisdiction career tracking (e.g., Patrick Brown's arc as federal MP → provincial MPP → mayor) does not work via UUID equality — those are three different UUIDs for the same person. The future fix is a separate identity layer in Supabase (a `persons` table with its own canonical person IDs, populated by fuzzy matching across jurisdictions and confirmed by a human). That is a v2+ concern; for now, the jurisdiction-scoped UUID is the safe default.

Date of birth would resolve both concerns at once, but is not reliably published on Canadian government sources, so it is not part of the canonical hash inputs.

**Empty cells, not nulls or placeholders.**
For missing data, leave the cell empty in the CSV. Don't use `null`, `N/A`, `unknown`, or other placeholder strings. The ingestion script treats empty as NULL in the database.

**Dates use ISO 8601.**
`YYYY-MM-DD` only. No "On or before October 2029" style strings. If a date is approximate or estimated, leave it empty and let the frontend compute the fallback from jurisdiction-level data.

**Boolean values are lowercase strings.**
`true` or `false` in the CSV. Not `TRUE`, `Yes`, `1`, etc.

**Encoding is UTF-8.**
French characters, Unicode apostrophes (`L'Érable`), em-dashes (`Humber River—Black Creek`) are all expected. The ingestion script handles these correctly as long as the file is UTF-8 encoded.

**The `district_id` in politicians.csv must exactly match what appears in the boundary file's column.**
This is the join key. Whitespace, case, and Unicode characters must match precisely. The Hamilton example: boundary file `WARD` column contains `1`, `2`, ..., `15`; politicians.csv `district_id` for Maureen Wilson must be `1` (string), not `Ward 1` or `01`. The agentic pipeline must inspect the boundary file to determine the exact format used.

**`specific_title` is always populated, and always in full.**
Unlike in earlier drafts where this column was reserved for cabinet/committee titles, `specific_title` now carries the politician's specific role for every row, with the value's meaning determined by the row's `standard_role` category. Use full official titles. Abbreviation is a frontend display concern.

**One row per role.**

Doug Ford appears in 4 rows in `data/ca_on/politicians.csv`, all sharing his UUID:

| role_scope | standard_role | specific_title | district_id |
|---|---|---|---|
| `district` | `representative` | `Member of Provincial Parliament` | (his Etobicoke North district ID) |
| `role` | `executive` | `Premier` | (empty) |
| `role` | `cabinet` | `Minister of Intergovernmental Affairs` | (empty) |
| `role` | `misc` | `Leader of the Progressive Conservative Party of Ontario` | (empty) |

Marit Stiles appears in 4 rows, all sharing her UUID:

| role_scope | standard_role | specific_title |
|---|---|---|
| `district` | `representative` | `Member of Provincial Parliament` |
| `role` | `misc` | `Leader of the New Democratic Party of Ontario` |
| `role` | `misc` | `Leader of the Official Opposition` |
| `role` | `misc` | `Critic, Intergovernmental Affairs` |

Mark Carney appears in 3 rows in `data/ca_federal/politicians.csv`, all sharing his UUID:

| role_scope | standard_role | specific_title |
|---|---|---|
| `district` | `representative` | `Member of Parliament` |
| `role` | `executive` | `Prime Minister` |
| `role` | `misc` | `Leader of the Liberal Party of Canada` |

**Photo URLs must be direct image links.**
The pipeline should verify each URL returns an image (not a webpage). URLs that 404 or return HTML should be left empty rather than included broken.

---

## Future scope

The current schema is scoped to elected leadership in jurisdictions that operate via district representation plus a single executive. Several adjacent concerns are intentionally deferred:

**Senators.** Canadian Senators are appointed rather than elected and represent one of eight territorial divisions (Maritime, Quebec, Ontario, Western, Newfoundland and Labrador, and one each for the three territories). When Senate data enters scope, each division becomes its own jurisdiction row in `jurisdictions.csv` with its own `politicians.csv`, rather than being shoehorned into an existing federal-level enum.

**Heads of state.** King Charles III and the Governor General of Canada are non-elected but materially relevant to the federal jurisdiction's executive structure. A future schema may introduce a fifth `standard_role` enum value (e.g., `head_of_state`) or a separate file to capture these.

**District identifiers.** Districts are currently joined to politicians by the byte-exact `district_id` ↔ boundary column value. Stable district UUIDs are not part of v1 and are not stored in boundary files. If they become necessary (e.g., to track redistributions over time, or for cleaner foreign keys at Supabase scale), the right design is a separate `districts.csv` per jurisdiction with its own UUID column, not modification of boundary files.

**Cross-jurisdiction person identity.** The deliberate jurisdiction-scoping of politician UUIDs means the same person across multiple jurisdictions has multiple UUIDs. A v2 `persons` table in Supabase, populated by fuzzy matching with human confirmation, is the planned solution.
