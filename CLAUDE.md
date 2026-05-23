# Parliament

Civic technology project for Canadian voters: representative lookup by postal code across federal, provincial, and municipal levels of government. Future scope includes structured civic discourse and international expansion.

---

## What this file is

This is the project's orchestrator context. Claude Code loads it automatically at the start of every session in this repo. It defines:

1. The default behavior on session start
2. The pre-migration data pipeline (10 stages)
3. Run-level responsibilities the orchestrator owns directly
4. Cross-cutting conventions all subagents follow
5. Where things live in the repo

For detailed per-stage logic, see the subagent definitions in `.claude/agents/`.

---

## Default behavior on session start

Greet the user briefly and ask what jurisdiction they want to register or refresh.

Example opener:
> Welcome back to Parliament. Which jurisdiction would you like to register or refresh today?

If the user instead asks for general coding help on the project (Flask API, Supabase integration, frontend work, etc.), drop the pipeline framing and act as a normal coding assistant. The pipeline is one mode of use; not all sessions will trigger it.

---

## The pre-registration pipeline

Atomic, single-level jurisdiction registration (or refresh). One run produces:

- One row appended to `data/jurisdictions.csv`
- One `politicians.csv` written to `data/<slug>/`
- Boundary files saved alongside `politicians.csv` (preserving native format for v1)

For refresh runs, prior contents of the jurisdiction folder are archived to `data/<slug>/_archive/<ISO_timestamp>/` before overwriting.

### Stages

| # | Stage | Owner | Purpose |
|---|---|---|---|
| 1 | Intake & disambiguation | `intake` subagent | Resolve user input to country + level + (subdivision) + (city); generate slug; detect new-vs-refresh |
| 2 | Source discovery | `source-discovery` subagent | Find official government sources per source_type; consult `known_sources.yaml` first |
| 3 | **HITL Gate 1** | **Orchestrator** | Present candidate sources for human approval |
| 4 | Acquisition | `acquisition` subagent | Download boundary files and approved pages to staging |
| 5 | Boundary inspection | `boundary-inspector` subagent | Inventory boundary file; extract exact district_id values for use as extraction constraint |
| 6 | Extraction (parallel) | `representatives`, `executive`, `cabinet`, `misc`, `metadata` subagents | Populate rows per schema |
| 7 | Reconciliation | `reconciliation` subagent | Generate UUID5; merge rows by UUID across streams |
| 8 | Validation | `validation` subagent | Programmatic checks: row counts, district_id match, photo URL probes, encoding, types |
| 9 | **HITL Gate 2** | **Orchestrator** | Present validation summary + diff for human approval |
| 10 | Write to canonical tree | `writer` subagent | Archive prior data (if refresh); write new files; append jurisdiction row; append validated sources to registry |

### Orchestration rules

- Between every stage, the orchestrator pauses with a brief summary and waits for the user's next prompt. This applies to every stage transition, not only the two named HITL gates.
- Subagents never invoke other subagents (Claude Code constraint and intentional design).
- Stages 1–9 write only within `data/_staging/<run_id>/`. Stage 10 is the only stage that touches the canonical `data/<slug>/` tree or `data/jurisdictions.csv`.

---

## Run-level responsibilities (orchestrator-owned)

These are handled directly by the orchestrator (the main session), not by any subagent, because they are run-level scaffolding rather than stage-level work.

### run_id

At the very start of each pipeline run — after the user names a jurisdiction, before invoking the intake subagent — the orchestrator generates a `run_id`:

- Format: UTC, ISO-8601 compact basic format `YYYYMMDDTHHMMSS` (e.g., `20260519T143000`).
- One run_id per run. It identifies the run's staging directory and is passed to every subagent that needs it.

### Staging directory

Immediately after generating the run_id, the orchestrator creates the run's staging directory:

```
data/_staging/<run_id>/
```

Subagents that write intermediate output (source-discovery, acquisition, boundary-inspector, the extraction subagents, reconciliation, validation) write into this existing directory. They are not responsible for creating it — they only need to write files into a directory the orchestrator has already made.

### last_confirmed derivation

Several stages stamp a `last_confirmed` (or `last_verified`) date. This is always the **date portion** of the current run_id, formatted `YYYY-MM-DD`. For run_id `20260519T143000`, that is `2026-05-19`. Every stage derives it the same way so timestamps across a run are internally consistent.

---

## Slug generation

Format:

- Federal: `<country>_federal` → `ca_federal`
- Provincial/state/territorial: `<country>_<subdivision>` → `ca_on`, `us_ca`
- Municipal: `<country>_<subdivision>_<city>` → `ca_on_hamilton`, `us_ca_los_angeles`

Rules:

- Lowercase only.
- ASCII only — strip accents and diacritics (`Montréal` → `montreal`, `Québec` → `quebec`).
- Replace spaces and hyphens with underscores (`Saint-Hyacinthe` → `saint_hyacinthe`, `New York` → `new_york`).
- No abbreviations, ever (`toronto`, not `to` or `tor`).
- Country code: ISO 3166-1 alpha-2, lowercased (`ca`, `us`, `de`).
- Subdivision code: ISO 3166-2, lowercased and stripped of country prefix (`on` not `ca-on`).

The slug is also the jurisdiction's folder name: a jurisdiction with slug `ca_on_hamilton` has its canonical data at `data/ca_on_hamilton/`. There is no level-based nesting; the path is always `data/<slug>/`.

If the user's input is ambiguous (e.g., "Hamilton" could resolve to Ontario, New Zealand, or several US locations), the intake subagent must disambiguate with the user before generating a slug.

---

## Schema conventions

These apply to every CSV the pipeline writes. Full column definitions live in `docs/schemas.md`.

- **Encoding:** UTF-8. French characters, em-dashes, and Unicode apostrophes are expected and preserved.
- **Dates:** ISO 8601 only (`YYYY-MM-DD`). Approximate or unknown dates are left empty, never guessed or formatted as prose.
- **Booleans:** Lowercase strings `true` or `false`. Not `TRUE`, `Yes`, `1`, or anything else.
- **Missing data:** Empty cells. Never `null`, `N/A`, `unknown`, or any placeholder string.
- **UUIDs:** Deterministic UUID5 from `<slug>|<first_name>|<last_name>` (NFC-normalized, lowercased, stripped). The same person produces the same UUID across re-runs and across every row they appear in within a jurisdiction.
- **One row per role.** A politician holding multiple roles (e.g., MP + PM + cabinet minister + party leader) appears in multiple rows sharing one UUID.

---

## Source policy

Official government sources only. If government sources are silent on a piece of data, the corresponding field is left empty rather than filled from a third-party source (Wikipedia, party websites, news outlets, OpenNorth, etc.).

The known-sources registry at `data/_registry/known_sources.yaml` is the discovery subagent's ground truth: a cache of pre-validated sources for already-registered jurisdictions, and a pattern library of what official sources look like for novel ones. When HITL Gate 1 validates new authoritative sources, they are appended to the registry at stage 10.

---

## File layout

```
Parliament/
├── CLAUDE.md                          # this file
├── .claude/agents/                    # subagent definitions (one .md file per stage)
├── data/
│   ├── jurisdictions.csv              # one row per registered jurisdiction
│   ├── _registry/
│   │   └── known_sources.yaml         # discovery ground truth
│   ├── _staging/<run_id>/             # per-run working directory (gitignored; orchestrator-created)
│   ├── ca_federal/                    # one folder per jurisdiction, named by slug
│   │   ├── politicians.csv
│   │   ├── _archive/<ISO_timestamp>/  # prior versions on refresh
│   │   └── *.shp | *.geojson          # boundary files
│   ├── ca_on/
│   ├── ca_on_toronto/
│   └── ...                            # additional jurisdictions, all data/<slug>/
├── docs/
│   └── schemas.md                     # canonical schema definitions
├── _archive_pre_pipeline/             # pre-pipeline data moved out of the canonical tree (gitignored)
├── lookup.py                          # existing geospatial lookup engine (v1 API)
└── ...
```

---

## HITL gates

Both gates are mandatory. They exist to catch source-validity errors (Gate 1) and extraction errors (Gate 2) before bad data is written to the canonical tree, where it would be expensive to detect and correct downstream.

- **Gate 1 — Source validation.** Appears after source discovery. The orchestrator presents each candidate source with URL, authority, format, and origin (registry-cached with date, or newly discovered). The user approves, rejects, or substitutes per source. After the user finalizes their decisions, the orchestrator writes the approved set to data/_staging/<run_id>/sources_approved.yaml, preserving the same structure as sources.yaml. Every source type from sources.yaml appears in the approved file with its outcome: approved sources carry their final URL and status: found; substituted sources carry the user-provided URL and status: found; rejected sources are retained with status: rejected and a one-line reason; not_applicable and not_found types carry through unchanged. This file — not the raw sources.yaml — is the input to acquisition (stage 4).
- **Gate 2 — Pre-write review.** Appears after validation. The orchestrator presents row counts vs. expected, validation pass/fail per check, and (for refresh runs) a row-level diff summary (N added, M removed, K changed) rather than the full table. The user approves or sends back to an earlier stage.

If the user asks the orchestrator to skip a gate or "just run the whole thing without stopping," explain why the gate exists and proceed normally with the gate in place. Skipping risks silently writing wrong data to the canonical tree.
