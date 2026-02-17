"""OpenClaw adapter — reads/writes openclaw.json models.providers config."""
import json
import os
from typing import Any, Dict, List, Optional
from .base import BaseAdapter


class OpenClawAdapter(BaseAdapter):
    id = "openclaw"
    label = "OpenClaw"
    default_config_path = os.path.expanduser("~/.openclaw/openclaw.json")

    def read_current(self, config_path: str) -> Optional[Dict[str, Any]]:
        path = config_path or self.default_config_path
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        providers = data.get("models", {}).get("providers", {})
        if not providers:
            return None
        results: List[Dict[str, Any]] = []
        for name, cfg in providers.items():
            results.append({
                "provider_name": name,
                "base_url": cfg.get("baseUrl", ""),
                "api_key": cfg.get("apiKey", ""),
                "api": cfg.get("api", ""),
                "models": [m.get("id", "") for m in cfg.get("models", [])],
            })
        return {"providers": results}

    def apply(self, config_path: str, base_url: str, api_key: str, **kwargs) -> bool:
        path = config_path or self.default_config_path
        if not os.path.exists(path):
            return False
        with open(path, "r") as f:
            data = json.load(f)
        providers = data.setdefault("models", {}).setdefault("providers", {})
        target = kwargs.get("provider_name", "")
        if target and target in providers:
            # Update specific provider
            providers[target]["baseUrl"] = base_url
            providers[target]["apiKey"] = api_key
        else:
            # Update all providers
            for name in providers:
                providers[name]["baseUrl"] = base_url
                providers[name]["apiKey"] = api_key
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
