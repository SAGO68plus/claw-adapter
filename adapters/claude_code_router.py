"""Claude Code Router adapter — reads/writes config.json Providers config."""
import json
import os
from typing import Any, Dict, List, Optional
from .base import BaseAdapter


class ClaudeCodeRouterAdapter(BaseAdapter):
    id = "claude_code_router"
    label = "Claude Code Router"
    default_config_path = "/root/.claude-code-router/config.json"

    def read_current(self, config_path: str) -> Optional[Dict[str, Any]]:
        path = config_path or self.default_config_path
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
        providers = data.get("Providers", [])
        if not providers:
            return None
        results: List[Dict[str, Any]] = []
        for p in providers:
            results.append({
                "provider_name": p.get("name", ""),
                "base_url": p.get("api_base_url", ""),
                "api_key": p.get("api_key", ""),
                "models": p.get("models", []),
            })
        return {"providers": results}

    def apply(self, config_path: str, base_url: str, api_key: str, **kwargs) -> bool:
        path = config_path or self.default_config_path
        if not os.path.exists(path):
            return False
        with open(path, "r") as f:
            data = json.load(f)
        providers = data.get("Providers", [])
        target = kwargs.get("provider_name", "")
        updated = False
        for p in providers:
            if target and p.get("name") != target:
                continue
            p["api_base_url"] = base_url
            p["api_key"] = api_key
            updated = True
        if not updated:
            return False
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
