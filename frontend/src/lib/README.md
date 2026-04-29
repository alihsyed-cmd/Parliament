# API response field availability

Source of truth for what fields are present at each jurisdiction level.
Generated 2026-04-29 from M3J3R2 (federal + Ontario + Toronto) and H3A0G4
(Quebec, coverage gap) staging responses.

When Phase 2 resumes and new jurisdictions are added, update this matrix.
The component layer relies on these availability assumptions.

## Representative fields

| Field | Federal MP | Ontario MPP | Toronto Cllr |
|---|:---:|:---:|:---:|
| name           | ✅ | ✅ | ✅ |
| role           | ✅ | ✅ | ✅ |
| party          | ✅ | ✅ | ❌ |
| riding         | ✅ | ✅ | ❌ |
| ward           | ❌ | ❌ | ✅ |
| photo_url      | ✅ | ❌ | ✅ |
| email          | ❌ | ✅ | ✅ |
| phone          | ❌ | ✅ | ✅ |
| website        | ❌ | ❌ | ✅ |
| elected        | ✅ | ❌ | ❌ |
| next_election  | ✅ | ✅ | ❌ |

## Leadership fields

| Field | Federal Cabinet | Ontario Cabinet | Toronto (Mayor) |
|---|:---:|:---:|:---:|
| name      | ✅ | ✅ | ✅ |
| role      | ✅ | ✅ | ✅ |
| party     | ✅ | ❌ | ❌ |
| photo_url | ✅ | ❌ | ✅ |
| website   | ❌ | ✅ | ✅ |
| email     | ❌ | ❌ | ✅ |
| phone     | ❌ | ❌ | ✅ |

## Governance metadata

| Field | Federal | Ontario | Toronto |
|---|:---:|:---:|:---:|
| type                 | ward_based | ward_based | ward_based |
| partisan             | true       | true       | false      |
| rep_count_expected   | 1          | 1          | 1          |
| election_cycle_years | 4          | 4          | 4          |
| max_term_years       | 5          | —          | —          |
| has_mayor            | —          | —          | true       |

## Coverage gap

Postal codes outside Canada/Ontario/Toronto return:
- `governance: null`
- `leadership: []`
- `representatives: []`

All three level keys (federal, provincial, municipal) are always present in
the response — never missing — but children are nullish/empty for
unsupported jurisdictions.
