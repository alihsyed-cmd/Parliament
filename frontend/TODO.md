

### [Phase 4] Backfill missing photos via API-first ingestion
**Reported:** 2026-04-29 (Task 7 testing)
**Context:** Ontario MPPs and Ontario cabinet members lack photo_url in current data; some federal MP photos return 404. Frontend shows gray placeholder gracefully, but real photos build trust and recognition. Right path is switching ingestion to OpenNorth's Represent API (or similar API-first source) which provides photos sourced from official government sites.
**Action:** During Phase 4 backend expansion, replace shapefile+CSV ingestion with Represent API or equivalent. Photos come along with the rep data, no separate scraping or hosting required. Will also benefit future provinces and cities.
**Trigger:** Phase 4 (post-frontend launch, when backend coverage expansion resumes).
