"""SillyTavern adapter — reads/writes secrets.json + settings.json."""
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from .base import BaseAdapter


class SillyTavernAdapter(BaseAdapter):
    id = "sillytavern"
    label = "SillyTavern"
    default_config_path = "/root/SillyTavern/data/default-user"

    def _secrets_path(self, config_path: str) -> str:
        base = config_path or self.default_config_path
        return os.path.join(base, "secrets.json")

    def _settings_path(self, config_path: str) -> str:
        base = config_path or self.default_config_path
        return os.path.join(base, "settings.json")

    def _get_key_by_secret_id(self, secrets: dict, secret_id: str) -> str:
        """Look up api_key value by secret-id in api_key_custom list."""
        for k in secrets.get("api_key_custom", []):
            if k.get("id") == secret_id:
                return k.get("value", "")
        return ""

    def read_current(self, config_path: str) -> Optional[Dict[str, Any]]:
        secrets_p = self._secrets_path(config_path)
        settings_p = self._settings_path(config_path)

        secrets = {}
        if os.path.exists(secrets_p):
            with open(secrets_p, "r") as f:
                secrets = json.load(f)

        settings = {}
        if os.path.exists(settings_p):
            with open(settings_p, "r") as f:
                settings = json.load(f)

        providers: List[Dict[str, Any]] = []

        # 1) Read connectionManager profiles (the primary source)
        #    May be at top-level or nested under extension_settings
        cm = settings.get("connectionManager", {})
        if not cm:
            cm = settings.get("extension_settings", {}).get("connectionManager", {})
        profiles = cm.get("profiles", [])
        for p in profiles:
            name = p.get("name", "")
            base_url = p.get("api-url", "")
            secret_id = p.get("secret-id", "")
            api_key = self._get_key_by_secret_id(secrets, secret_id) if secret_id else ""
            providers.append({
                "provider_name": name or "default",
                "base_url": base_url,
                "api_key": api_key,
                "model": p.get("model", ""),
                "preset": p.get("preset", ""),
            })

        # 2) Fallback: if no profiles, read legacy selected_proxy + active key
        if not providers:
            result: Dict[str, Any] = {}
            keys = secrets.get("api_key_custom", [])
            active = [k for k in keys if k.get("active")]
            if active:
                result["api_key"] = active[0].get("value", "")
            elif keys:
                result["api_key"] = keys[0].get("value", "")
            result["main_api"] = settings.get("main_api", "")
            proxy = settings.get("selected_proxy", {})
            result["base_url"] = proxy.get("url", "")
            return result if result.get("api_key") else None

        return {"providers": providers} if providers else None

    def apply(self, config_path: str, base_url: str, api_key: str, **kwargs) -> bool:
        ok = True
        provider_name = kwargs.get("provider_name", "")

        # Update secrets.json — set active key
        secrets_p = self._secrets_path(config_path)
        if os.path.exists(secrets_p):
            with open(secrets_p, "r") as f:
                secrets = json.load(f)
            keys = secrets.get("api_key_custom", [])
            # Deactivate all, then set new active
            for k in keys:
                k["active"] = False
            found = False
            for k in keys:
                if k["value"] == api_key:
                    k["active"] = True
                    found = True
                    break
            if not found:
                keys.append({
                    "id": str(uuid.uuid4()),
                    "value": api_key,
                    "label": datetime.now().strftime("%m/%d/%Y %I:%M %p"),
                    "active": True,
                })
            secrets["api_key_custom"] = keys
            with open(secrets_p, "w") as f:
                json.dump(secrets, f, indent=2, ensure_ascii=False)
        else:
            ok = False

        # Update settings.json
        settings_p = self._settings_path(config_path)
        if os.path.exists(settings_p):
            with open(settings_p, "r") as f:
                settings = json.load(f)

            # Try to update connectionManager profile by name
            cm = settings.get("connectionManager", {})
            if not cm:
                cm = settings.get("extension_settings", {}).get("connectionManager", {})
            profiles = cm.get("profiles", [])
            profile_updated = False
            if provider_name:
                for p in profiles:
                    if p.get("name") == provider_name:
                        p["api-url"] = base_url
                        # Find or create secret-id for this key
                        secret_id = ""
                        for k in secrets.get("api_key_custom", []) if os.path.exists(secrets_p) else []:
                            if k["value"] == api_key:
                                secret_id = k["id"]
                                break
                        if secret_id:
                            p["secret-id"] = secret_id
                        profile_updated = True
                        break

            # Also update selected_proxy as fallback
            if base_url:
                settings["selected_proxy"] = {
                    "name": provider_name or "api-vault",
                    "url": base_url,
                    "password": api_key,
                }

            with open(settings_p, "w") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        return ok
