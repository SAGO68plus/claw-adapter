"""Abstract base adapter — all service adapters inherit from this."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAdapter(ABC):
    """Each adapter knows how to read/write API config for one service."""

    id: str          # unique key, e.g. "openclaw"
    label: str       # display name
    default_config_path: str = ""

    @abstractmethod
    def read_current(self, config_path: str) -> Optional[Dict[str, Any]]:
        """Read the service's current API provider config.
        Returns dict with at least {base_url, api_key} or None."""
        ...

    @abstractmethod
    def apply(self, config_path: str, base_url: str, api_key: str, **kwargs) -> bool:
        """Write the provider config into the service's config file.
        Returns True on success."""
        ...

    def mask_key(self, key: str) -> str:
        if len(key) <= 8:
            return "****"
        return key[:4] + "****" + key[-4:]
