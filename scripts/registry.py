"""
JurisdictionRegistry — loads all jurisdiction configs at startup,
instantiates the appropriate adapter for each, and dispatches lookup
queries to all registered adapters.

The registry is the single entry point that api.py calls. It hides all
adapter-specific logic from the API layer.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from adapters.base import JurisdictionAdapter
from adapters.ward_based import WardBasedAdapter


# Map of adapter_type config values to adapter classes.
# Add new adapter types here as they are implemented (at_large, nested_borough, consensus, etc.)
ADAPTER_TYPES: Dict[str, type] = {
    "ward_based": WardBasedAdapter,
}


class JurisdictionRegistry:
    """
    Loads and manages all jurisdiction adapters.

    At startup, scans the configured jurisdictions directory, instantiates
    one adapter per config file, calls load_data() and validate() on each.
    """

    def __init__(self, config_dir: str = None):
        """
        Args:
            config_dir: Path to directory containing jurisdiction JSON configs.
                        Defaults to the JURISDICTIONS_CONFIG_DIR environment variable.
        """
        if config_dir is None:
            config_dir = os.getenv("JURISDICTIONS_CONFIG_DIR")
        if not config_dir:
            raise ValueError(
                "JURISDICTIONS_CONFIG_DIR env var must be set "
                "or config_dir must be passed explicitly"
            )

        self.config_dir = Path(config_dir)
        self.adapters: List[JurisdictionAdapter] = []
        self._load_all()

    def _load_all(self) -> None:
        """Discover and load every *.json config in the config directory."""
        config_files = sorted(self.config_dir.glob("*.json"))
        if not config_files:
            raise RuntimeError(f"No jurisdiction configs found in {self.config_dir}")

        for config_file in config_files:
            try:
                self._load_one(config_file)
            except Exception as e:
                # Don't crash the whole registry if one jurisdiction fails.
                # Log the error and continue — other jurisdictions still work.
                print(f"WARNING: Failed to load {config_file.name}: {e}")

    def _load_one(self, config_file: Path) -> None:
        """Load a single jurisdiction config and instantiate its adapter."""
        with open(config_file) as f:
            config = json.load(f)

        # Inject the slug derived from the config filename. The slug is what
        # links a config to its row in the Supabase jurisdictions table.
        config["slug"] = config_file.stem

        adapter_type = config.get("adapter_type")
        if adapter_type not in ADAPTER_TYPES:
            raise ValueError(
                f"Unknown adapter_type '{adapter_type}' in {config_file.name}. "
                f"Known types: {list(ADAPTER_TYPES.keys())}"
            )

        adapter_class = ADAPTER_TYPES[adapter_type]
        adapter = adapter_class(config)
        adapter.load_data()
        adapter.validate()
        self.adapters.append(adapter)
        print(f"  Loaded: {adapter}")

    def lookup_all(self, lat: float, lon: float) -> Dict[str, Dict[str, Any]]:
        """
        Query every registered adapter for the given point.

        If a single adapter raises an exception, log it and continue with the
        remaining adapters. This ensures one broken jurisdiction doesn't break
        lookups for the rest.

        Returns:
            A dict keyed by level ('federal', 'provincial', 'municipal'). Each
            level maps to a dict containing:
              - 'governance': metadata describing how the jurisdiction is governed
                (or None if no covering jurisdiction at this level)
              - 'representatives': a list of representatives at this point
                (empty list if no covering jurisdiction)
        """
        results: Dict[str, Dict[str, Any]] = {
            "federal": {"governance": None, "representatives": []},
            "provincial": {"governance": None, "representatives": []},
            "municipal": {"governance": None, "representatives": []},
        }

        for adapter in self.adapters:
            try:
                reps = adapter.get_representatives(lat, lon)
                if reps:
                    results[adapter.level]["representatives"].extend(reps)
                    # Attach governance for any level where the point matched
                    # a jurisdiction. If the point falls outside all jurisdictions
                    # at a level, governance stays None.
                    if results[adapter.level]["governance"] is None:
                        results[adapter.level]["governance"] = adapter.governance
            except Exception as e:
                # One bad adapter must not break lookups for the rest.
                print(f"WARNING: {adapter.name} adapter failed: {e}")

        return results

    def __repr__(self) -> str:
        return f"<JurisdictionRegistry adapters={len(self.adapters)}>"
