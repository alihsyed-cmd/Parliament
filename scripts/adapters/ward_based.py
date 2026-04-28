"""
WardBasedAdapter — queries Supabase for ward/riding-based jurisdictions.

After milestone 2.3, this adapter no longer reads source files at runtime.
Source data is migrated to Supabase via scripts/migrate_to_supabase.py;
this adapter executes spatial queries against the database to answer lookups.

Used by: Canada federal, Ontario, Toronto, and all future ward-based cities.
"""

from typing import Any, Dict, List, Optional

import db
from .base import JurisdictionAdapter


# District-based lookup: representatives whose district contains the point.
# Used for MPs, MPPs, Councillors — anyone who represents a specific area.
#
# Language selection uses COALESCE: try the requested language first, fall
# back to English if the requested language field is empty.
# %s parameters in order: lang, lang, lang, lang, lang, jurisdiction_id, lon, lat
DISTRICT_LOOKUP_SQL = """
    SELECT
        COALESCE(r.name->>%s, r.name->>'en')              AS name,
        COALESCE(r.party->>%s, r.party->>'en')            AS party,
        r.email                                            AS email,
        r.phone                                            AS phone,
        r.photo_url                                        AS photo_url,
        COALESCE(r.website_url->>%s, r.website_url->>'en') AS website_url,
        r.external_ids                                     AS external_ids,
        COALESCE(rep.role->>%s, rep.role->>'en')           AS role,
        rep.start_date                                     AS start_date,
        COALESCE(d.name->>%s, d.name->>'en')               AS district_name,
        d.external_id                                      AS district_external_id
    FROM districts d
    JOIN representations rep
        ON rep.district_id = d.id
       AND rep.end_date IS NULL
       AND rep.scope = 'district'
    JOIN representatives r
        ON r.id = rep.representative_id
    WHERE d.jurisdiction_id = %s
      AND ST_Contains(d.boundary, ST_SetSRID(ST_MakePoint(%s, %s), 4326));
"""

# Role-based lookup: representatives who hold a leadership role for the
# whole jurisdiction. PM, Premier, Mayor, cabinet ministers.
# %s parameters in order: lang, lang, lang, lang, jurisdiction_id
LEADERSHIP_LOOKUP_SQL = """
    SELECT
        COALESCE(r.name->>%s, r.name->>'en')              AS name,
        COALESCE(r.party->>%s, r.party->>'en')            AS party,
        r.email                                            AS email,
        r.phone                                            AS phone,
        r.photo_url                                        AS photo_url,
        COALESCE(r.website_url->>%s, r.website_url->>'en') AS website_url,
        r.external_ids                                     AS external_ids,
        COALESCE(rep.role->>%s, rep.role->>'en')           AS role,
        rep.start_date                                     AS start_date
    FROM representations rep
    JOIN representatives r ON r.id = rep.representative_id
    WHERE rep.jurisdiction_id = %s
      AND rep.scope = 'role'
      AND rep.end_date IS NULL
    ORDER BY rep.start_date ASC NULLS LAST;
"""


class WardBasedAdapter(JurisdictionAdapter):
    """Adapter for single-representative-per-district jurisdictions."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.slug: str = config.get("slug") or self._slug_from_name(config["name"])
        self.jurisdiction_id: Optional[str] = None

    @staticmethod
    def _slug_from_name(name: str) -> str:
        """Derive a slug from a display name. Used as fallback when config has no slug."""
        return name.lower().replace(" ", "_")

    # ── Loading ──────────────────────────────────────────────────────
    def load_data(self) -> None:
        """Resolve this jurisdiction's UUID from its slug.

        With Supabase storage, 'loading' is just looking up our jurisdiction's
        identifier so subsequent lookups can scope queries correctly.
        """
        # The slug used to identify this jurisdiction in Supabase comes from
        # the config filename. The registry passes that in via the adapter
        # type lookup; if it's not in the config, we derive it from the name.
        configured_slug = self.config.get("slug")
        if configured_slug:
            self.slug = configured_slug

        row = db.query_one(
            "SELECT id, governance FROM jurisdictions WHERE slug = %s;",
            (self.slug,),
        )
        if row is None:
            raise ValueError(
                f"{self.name}: no jurisdiction row found in Supabase for slug "
                f"'{self.slug}'. Has migrate_to_supabase.py been run?"
            )
        self.jurisdiction_id = row[0]
        self.governance = row[1]  # jsonb column comes back as a Python dict
        self._loaded = True

    # ── Lookup ───────────────────────────────────────────────────────
    def get_representatives(
        self, lat: float, lon: float, lang: str = "en"
    ) -> List[Dict[str, Any]]:
        """Return district-based representatives whose district contains the point.

        Args:
            lat: Latitude in WGS84.
            lon: Longitude in WGS84.
            lang: ISO 639-1 language code ('en' or 'fr'). Falls back to 'en'
                  if the requested language has no value for a given field.
        """
        if not self._loaded:
            raise RuntimeError(f"{self.name}: load_data() must be called first")

        # Pass lang 5 times for the 5 COALESCE expressions in DISTRICT_LOOKUP_SQL
        params = (lang, lang, lang, lang, lang, self.jurisdiction_id, lon, lat)
        rows = db.query(DISTRICT_LOOKUP_SQL, params)
        return [self._row_to_dict(row) for row in rows]

    def get_leadership(self, lang: str = "en") -> List[Dict[str, Any]]:
        """Return role-based representatives for this jurisdiction.

        Unlike get_representatives, this is not point-dependent — every user in
        a jurisdiction sees the same leadership.

        Args:
            lang: ISO 639-1 language code ('en' or 'fr').
        """
        if not self._loaded:
            raise RuntimeError(f"{self.name}: load_data() must be called first")

        # Pass lang 4 times for the 4 COALESCE expressions in LEADERSHIP_LOOKUP_SQL
        params = (lang, lang, lang, lang, self.jurisdiction_id)
        rows = db.query(LEADERSHIP_LOOKUP_SQL, params)
        return [self._row_to_dict_leadership(row) for row in rows]

    def _row_to_dict_leadership(self, row: tuple) -> Dict[str, Any]:
        """Convert a leadership query row into output dict shape (no district info)."""
        (name, party, email, phone, photo_url, website_url,
         external_ids, role, start_date) = row

        output: Dict[str, Any] = {"name": name}
        if party:
            output["party"] = party
        if email:
            output["email"] = email
        if phone:
            output["phone"] = phone
        if photo_url:
            output["photo_url"] = photo_url
        if website_url:
            output["website"] = website_url
        if start_date:
            output["start_date"] = start_date.isoformat()
        if role:
            output["role"] = role
        return output

    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Convert a query result row into the adapter's output dict shape."""
        (name, party, email, phone, photo_url, website_url,
         external_ids, role, start_date, district_name, district_external_id) = row

        district_label = self.config.get("output_district_label", "district")

        # Prefer the human-readable district name; fall back to external ID.
        # Stringify both — Toronto wards are stored as floats ("7.0") in the
        # source data and need to render as integers ("7").
        district_value = (
            self._stringify_district(district_name)
            or self._stringify_district(district_external_id)
        )

        output: Dict[str, Any] = {"name": name}

        if party:
            output["party"] = party
        if email:
            output["email"] = email
        if phone:
            output["phone"] = phone
        if photo_url:
            output["photo_url"] = photo_url
        if website_url:
            output["website"] = website_url
        if start_date:
            output["elected"] = start_date.isoformat()
        if role:
            output["role"] = role

        # Static fields from config (e.g., next_election dates)
        for key, value in self.config.get("static_fields", {}).items():
            if value:
                output[key] = value

        output[district_label] = district_value
        return output

    @staticmethod
    def _stringify_district(value: Any) -> str:
        """Convert a district identifier to a clean string."""
        if value is None:
            return ""
        s = str(value)
        # Floats stored as strings (e.g., "7.0") become integers
        try:
            f = float(s)
            if f.is_integer():
                return str(int(f))
        except (ValueError, TypeError):
            pass
        return s

    # ── Validation ───────────────────────────────────────────────────
    def validate(self) -> bool:
        """Verify the adapter is properly bound to a Supabase jurisdiction."""
        assert self.jurisdiction_id is not None, (
            f"{self.name}: jurisdiction_id not set. load_data() must run first."
        )

        # Confirm at least one district exists for this jurisdiction
        row = db.query_one(
            "SELECT COUNT(*) FROM districts WHERE jurisdiction_id = %s;",
            (self.jurisdiction_id,),
        )
        district_count = row[0]
        assert district_count > 0, (
            f"{self.name}: no districts found in Supabase for jurisdiction "
            f"'{self.slug}'. Has migrate_to_supabase.py been run?"
        )

        # Confirm at least one active representation exists
        row = db.query_one(
            """
            SELECT COUNT(*) FROM representations rep
            JOIN districts d ON d.id = rep.district_id
            WHERE d.jurisdiction_id = %s AND rep.end_date IS NULL;
            """,
            (self.jurisdiction_id,),
        )
        rep_count = row[0]
        assert rep_count > 0, (
            f"{self.name}: no active representations for jurisdiction '{self.slug}'."
        )

        return True
