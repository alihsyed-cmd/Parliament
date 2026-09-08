# Parliament

A civic technology application for Canadian voters. Users enter their postal code and
see their elected representatives at every level of government — federal, provincial,
and municipal. The 2026 municipal cycle adds candidate profiles alongside incumbents.

## Architecture

Two halves that meet at a Supabase (PostgreSQL + PostGIS) database.

**Backend** — a Flask API at the repo root, served by gunicorn (`api:app`, see `Procfile`).

```
api.py                  # app factory, lookup + jurisdiction + representative routes
db.py                   # Supabase connection
claim.py                # claim_bp — candidates claiming their profile
claim_mask.py           # contact-masking helpers used by the claim flow
portal.py               # portal_bp — authenticated candidate self-service
candidates_public.py    # public_bp — public candidate reads
migrations/             # 001_schema, 002_raw_candidates, 003_invitations_submissions
```

**Frontend** — a Next.js app in `frontend/`, deployed on Vercel with `frontend` as the
Vercel root directory. `.vercelignore` keeps pipeline data and credentials out of the upload.

**Data pipelines** — two agent-driven pipelines defined in `CLAUDE.md`, with one subagent
per stage under `.claude/agents/`. The incumbent pipeline registers a jurisdiction's
elected officials; the candidate pipeline collects an election's candidate roster.
`CLAUDE.md` is the authoritative description of both — read it before running either.

```
data/jurisdictions.csv        # one row per registered jurisdiction
data/<slug>/                  # canonical per-jurisdiction tree: politicians.csv,
                              # raw_candidates.csv, boundary files, _archive/
data/_registry/               # known_sources.yaml, candidate_validation_log.md
data/_staging/<run_id>/       # per-run working files (gitignored, disposable once
                              # the run's canonical output is written)
docs/schemas.md               # canonical column definitions
```

## Running the API

```bash
pip install -r requirements.txt
python3 api.py
```

Then query:

```bash
curl "http://127.0.0.1:5000/lookup?postal_code=M3J3R2"
curl "http://127.0.0.1:5000/health"
```

## Database

Supabase (PostgreSQL with PostGIS). Enable the PostGIS extension via Database →
Extensions in the dashboard, then apply the migrations in `migrations/` in numeric order.

Geometry and rows reach the database only through the pipelines' export stages
(`export` for incumbents, `candidate-export` for candidates). Those are the only
stages that write remotely; every other stage writes locally.

## Utilities

```
scripts/candidate_tail.py           # runs candidate stages 5-8 deterministically
build_jurisdictions_overview.py     # regenerates jurisdictions_overview.csv
build_data_gaps_report.py           # regenerates DATA_GAPS.md
demo/demo_candidates.py             # seeds the Pepperland demo jurisdiction
```

## Testing

Fixture-based regression tests. Install pytest first — it is not in `requirements.txt`.

```bash
pip install pytest
pytest tests/ -v
```

See `tests/README.md` for the fixture format and how to add cases.

## Environment

Requires a `.env` file (gitignored) with at least:

- `SUPABASE_DB_URL` — session pooler connection string
- `GOOGLE_MAPS_API_KEY` — postal code geocoding
