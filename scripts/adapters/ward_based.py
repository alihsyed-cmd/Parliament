"""
WardBasedAdapter — for jurisdictions where each representative has a
geographic district (ward, riding, constituency).

Handles any jurisdiction where:
  - Each point maps to exactly one district
  - Each district has exactly one representative
  - Join between boundary and rep data is by district name OR district ID

Used by: Canada federal, Ontario, Toronto, and all future ward-based cities
(Ottawa, Calgary, Edmonton, Mississauga, Brampton, Hamilton, Winnipeg, etc.)
"""

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from .base import JurisdictionAdapter


class WardBasedAdapter(JurisdictionAdapter):
    """
    Adapter for single-representative-per-district jurisdictions.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.boundaries: Optional[gpd.GeoDataFrame] = None
        self.representatives: Dict[Any, Dict[str, Any]] = {}
        self.join_mode: Optional[str] = None  # "name" or "id"

    # ── Data loading ─────────────────────────────────────────────────
    def load_data(self) -> None:
        """Load boundary file and representative data per config."""
        self._load_boundaries()
        self._load_representatives()
        self._loaded = True

    def _load_boundaries(self) -> None:
        """Read boundary file and build spatial index."""
        boundary_config = self.config["boundary"]
        path_env_var = boundary_config["file"]
        path = os.getenv(path_env_var)
        if not path:
            raise ValueError(
                f"{self.name}: boundary file env var '{path_env_var}' not set"
            )

        self.boundaries = gpd.read_file(path).to_crs(epsg=4326)

        # Determine join mode from config
        if "district_id_field" in boundary_config:
            self.join_mode = "id"
            self.district_field = boundary_config["district_id_field"]
        elif "district_name_field" in boundary_config:
            self.join_mode = "name"
            self.district_field = boundary_config["district_name_field"]
        else:
            raise ValueError(
                f"{self.name}: config must specify either "
                f"'district_name_field' or 'district_id_field'"
            )

    def _load_representatives(self) -> None:
        """Read rep data (CSV or XML) into a dict keyed by join_field."""
        reps_config = self.config["representatives"]
        path_env_var = reps_config["file"]
        path = os.getenv(path_env_var)
        if not path:
            raise ValueError(
                f"{self.name}: reps file env var '{path_env_var}' not set"
            )

        fmt = reps_config["format"]
        if fmt == "csv":
            self._load_csv(path, reps_config)
        elif fmt == "xml":
            self._load_xml(path, reps_config)
        else:
            raise ValueError(f"{self.name}: unsupported format '{fmt}'")

    def _load_csv(self, path: str, reps_config: Dict[str, Any]) -> None:
        """Load representatives from a CSV file."""
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip().str.replace('"', '')

        join_field = reps_config["join_field"]
        field_mapping = reps_config["field_mapping"]

        for _, row in df.iterrows():
            key = self._normalize_join_key(row.get(join_field))
            if key is None or key in self.representatives:
                continue
            self.representatives[key] = self._extract_fields(row, field_mapping)

    def _load_xml(self, path: str, reps_config: Dict[str, Any]) -> None:
        """Load representatives from an XML file."""
        tree = ET.parse(path)
        join_field = reps_config["join_field"]
        field_mapping = reps_config["field_mapping"]
        photo_template = reps_config.get("photo_url_template")

        for record in tree.getroot():
            key = self._normalize_join_key(record.findtext(join_field, "").strip())
            if key is None or key in self.representatives:
                continue

            extracted = {
                canonical: (record.findtext(source_tag, "") or "").strip()
                for canonical, source_tag in field_mapping.items()
            }

            # Federal-specific: trim elected date to YYYY-MM-DD
            if "elected" in extracted:
                extracted["elected"] = extracted["elected"][:10]

            # Build photo URL from template if configured
            if photo_template and "person_id" in extracted:
                extracted["photo_url"] = photo_template.format(
                    person_id=extracted["person_id"]
                )

            self.representatives[key] = extracted

    def _extract_fields(
        self, row: pd.Series, field_mapping: Dict[str, str]
    ) -> Dict[str, Any]:
        """Extract canonical fields from a CSV row per field_mapping."""
        extracted = {}
        for canonical, source_col in field_mapping.items():
            value = str(row.get(source_col, "")).strip()
            if value in ("nan", "None", ""):
                value = ""
            extracted[canonical] = value
        return extracted

    def _normalize_join_key(self, value: Any) -> Optional[Any]:
        """Normalize join key based on join_mode.

        For 'id' mode: cast to int (Toronto's WARD_NUMBER is 1.0, 2.0, ... as floats).
        For 'name' mode: strip whitespace, return None if empty or 'nan'.
        """
        if value is None:
            return None

        if self.join_mode == "id":
            try:
                if pd.isna(value):
                    return None
                return int(float(value))
            except (ValueError, TypeError):
                return None

        # name mode
        s = str(value).strip()
        if not s or s.lower() == "nan":
            return None
        return s

    # ── Lookup ───────────────────────────────────────────────────────
    def get_representatives(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        """Return representatives for a given point."""
        if not self._loaded:
            raise RuntimeError(f"{self.name}: load_data() must be called first")

        point = Point(lon, lat)

        # Two-stage spatial lookup:
        # 1. sindex.intersection() narrows to candidate polygons via bbox overlap
        # 2. exact .contains() filter selects polygons that actually contain the point
        # This pattern is more reliable across GeoPandas versions than sindex.query()
        candidate_idx = list(self.boundaries.sindex.intersection(point.bounds))
        if not candidate_idx:
            return []
        candidates = self.boundaries.iloc[candidate_idx]
        matches = candidates[candidates.geometry.contains(point)]

        if matches.empty:
            return []

        # Take the first match (in ward-based jurisdictions, a point should
        # only ever be in one district; if somehow in multiple, first wins)
        district_value = matches.iloc[0][self.district_field]
        key = self._normalize_join_key(district_value)

        rep = self.representatives.get(key)
        if rep is None:
            # Point is inside the jurisdiction but we have no rep data for
            # this district. Return empty rather than crash — surface the
            # district name so the caller can display "district known, rep unknown".
            return []

        # Enrich the rep dict with district info and output labels
        enriched = self._format_output(rep, district_value)
        return [enriched]

    def _format_output(
        self, rep: Dict[str, Any], district_value: Any
    ) -> Dict[str, Any]:
        """Build the final output dict combining rep data + static fields + district info."""
        # Start with the canonical name fields combined
        output: Dict[str, Any] = {}
        name = self._build_full_name(rep)
        if name:
            output["name"] = name

        # Copy rep fields, skipping name components (already merged into name)
        # and skipping empty/None values
        skip = {"first_name", "last_name", "honorific", "person_id"}
        for key, value in rep.items():
            if key in skip:
                continue
            if value is None or value == "":
                continue
            output[key] = value

        # Merge static fields (next_election, etc.)
        for key, value in self.config.get("static_fields", {}).items():
            if value is not None and value != "":
                output[key] = value

        # Attach district identifier using the configured label
        district_label = self.config.get("output_district_label", "district")
        output[district_label] = self._stringify_district(district_value)

        # Add role label
        role_label = self.config.get("output_role_label")
        if role_label:
            output["role"] = role_label.upper() if len(role_label) <= 3 else role_label.capitalize()

        return output

    def _stringify_district(self, value: Any) -> str:
        """Convert district value to a clean string. Floats like 7.0 become '7'."""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _build_full_name(self, rep: Dict[str, Any]) -> Optional[str]:
        """Assemble honorific + first + last into a single name string."""
        hon = rep.get("honorific", "").strip()
        first = rep.get("first_name", "").strip()
        last = rep.get("last_name", "").strip()

        if not (first or last):
            return None

        parts = []
        if hon and hon.lower() != "nan":
            parts.append(hon)
        if first:
            parts.append(first)
        if last:
            parts.append(last)
        return " ".join(parts)

    # ── Validation ───────────────────────────────────────────────────
    def validate(self) -> bool:
        """Verify loaded data is sane."""
        assert self.boundaries is not None, f"{self.name}: boundaries not loaded"
        assert len(self.boundaries) > 0, f"{self.name}: no boundary records"
        assert len(self.representatives) > 0, f"{self.name}: no representative records"
        return True
