"""
File-based loader used only by the one-time migration script.

The runtime adapter (WardBasedAdapter) queries Supabase. The migration script
needs to read the original source files (shapefiles, CSVs, XML) to populate
Supabase. This module preserves the file-loading logic that used to live in
the adapter, so the migration can keep working independently.

This module is not used at runtime and can be deleted once data ingestion
moves fully to API-first sources in milestone 2.6.
"""

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional

import geopandas as gpd
import pandas as pd


class LegacySourceLoader:
    """Reads boundary + representative data from source files per a config dict."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config["name"]
        self.boundaries: Optional[gpd.GeoDataFrame] = None
        self.representatives: Dict[Any, Dict[str, Any]] = {}

        boundary_config = config.get("boundary", {})
        self.district_field = (
            boundary_config.get("district_id_field")
            or boundary_config.get("district_name_field")
        )
        self.join_mode = "id" if "district_id_field" in boundary_config else "name"

    def load(self) -> None:
        """Load boundaries and representatives from source files."""
        self._load_boundaries()
        self._load_representatives()

    def _load_boundaries(self) -> None:
        path = os.getenv(self.config["boundary"]["file"])
        if not path:
            raise ValueError(f"{self.name}: boundary file env var not set")
        self.boundaries = gpd.read_file(path).to_crs(epsg=4326)

    def _load_representatives(self) -> None:
        reps_config = self.config["representatives"]
        path = os.getenv(reps_config["file"])
        if not path:
            raise ValueError(f"{self.name}: reps file env var not set")

        fmt = reps_config["format"]
        if fmt == "csv":
            self._load_csv(path, reps_config)
        elif fmt == "xml":
            self._load_xml(path, reps_config)
        else:
            raise ValueError(f"{self.name}: unsupported format '{fmt}'")

    def _load_csv(self, path: str, reps_config: Dict[str, Any]) -> None:
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip().str.replace('"', '')

        join_field = reps_config["join_field"]
        field_mapping = reps_config["field_mapping"]

        for _, row in df.iterrows():
            key = self._normalize_join_key(row.get(join_field))
            if key is None or key in self.representatives:
                continue
            self.representatives[key] = {
                canonical: self._clean(row.get(source_col, ""))
                for canonical, source_col in field_mapping.items()
            }

    def _load_xml(self, path: str, reps_config: Dict[str, Any]) -> None:
        tree = ET.parse(path)
        join_field = reps_config["join_field"]
        field_mapping = reps_config["field_mapping"]
        photo_template = reps_config.get("photo_url_template")

        for record in tree.getroot():
            key = self._normalize_join_key(
                (record.findtext(join_field, "") or "").strip()
            )
            if key is None or key in self.representatives:
                continue

            extracted = {
                canonical: (record.findtext(source_tag, "") or "").strip()
                for canonical, source_tag in field_mapping.items()
            }

            if "elected" in extracted:
                extracted["elected"] = extracted["elected"][:10]

            if photo_template and "person_id" in extracted:
                extracted["photo_url"] = photo_template.format(
                    person_id=extracted["person_id"]
                )

            self.representatives[key] = extracted

    @staticmethod
    def _clean(value: Any) -> str:
        s = str(value).strip()
        return "" if s in ("nan", "None", "") else s

    def _normalize_join_key(self, value: Any) -> Optional[Any]:
        if value is None:
            return None

        if self.join_mode == "id":
            try:
                if pd.isna(value):
                    return None
                return int(float(value))
            except (ValueError, TypeError):
                return None

        s = str(value).strip()
        if not s or s.lower() == "nan":
            return None
        return s

    @staticmethod
    def build_full_name(rep: Dict[str, Any]) -> Optional[str]:
        hon = (rep.get("honorific") or "").strip()
        first = (rep.get("first_name") or "").strip()
        last = (rep.get("last_name") or "").strip()

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
