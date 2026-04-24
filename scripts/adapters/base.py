"""
Base adapter class for jurisdiction lookups.

Every jurisdiction type (ward-based, at-large, nested-borough, consensus)
must subclass JurisdictionAdapter and implement the required methods.

The registry treats all adapters uniformly through this interface.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class JurisdictionAdapter(ABC):
    """
    Abstract base class for jurisdiction adapters.

    Subclasses must implement:
      - load_data(): read boundary and representative data into memory
      - get_representatives(lat, lon): return representatives for a point
      - validate(): verify loaded data meets basic sanity checks
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the adapter with its configuration.

        Args:
            config: Dictionary parsed from the jurisdiction's JSON config file.
                    Must contain at minimum: 'name', 'level', 'adapter_type'.
        """
        self.config = config
        self.name = config["name"]
        self.level = config["level"]  # "federal", "provincial", or "municipal"
        self.adapter_type = config["adapter_type"]
        self._loaded = False

    @abstractmethod
    def load_data(self) -> None:
        """
        Load boundary and representative data into memory.

        Called once at registry startup. Subclasses are responsible for reading
        their own file formats (shapefile, GeoJSON, CSV, XML) per the config.
        """
        pass

    @abstractmethod
    def get_representatives(self, lat: float, lon: float) -> List[Dict[str, Any]]:
        """
        Return representatives for a given geographic point.

        Args:
            lat: Latitude in WGS84 (EPSG:4326).
            lon: Longitude in WGS84 (EPSG:4326).

        Returns:
            A list of representative dictionaries. Empty list if the point is
            outside this jurisdiction. Always a list, even for single-rep results.
        """
        pass

    @abstractmethod
    def validate(self) -> bool:
        """
        Verify that loaded data meets basic sanity checks.

        Subclasses should assert expected row counts, required fields,
        non-null values, etc. Called after load_data() during registry startup.

        Returns:
            True if validation passes. Raises AssertionError otherwise.
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} level={self.level!r}>"
