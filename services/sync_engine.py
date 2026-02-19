"""Sync engine — core sync/push/import business logic, decoupled from routes."""
import json
from urllib.parse import urlparse
from db import get_db_ctx, encrypt
from adapters import get_adapter, all_adapters
from utils import resolve_api_key


def _parse_extra(raw) -> dict:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def do_apply(adapter, config_path: str, base_url: str, api_key: str, target_name: str, extra_fields: dict = None) -> bool:
    """Apply config to an adapter, return ok bool."""
    return adapter.apply(config_path, base_url, api_key, provider_name=target_name, extra_fields=extra_fields or {})


def sync_provider_to_bindings(provider_id: int) -> list:
    """Push a provider's config to all its auto_sync bindings."""
    with get_db_ctx() as db:
        provider = db.execute("SELECT * FROM providers WHERE id=?", (provider_id,)).fetchone()
        if not provider:
            return []
        bindings = db.execute(
            "SELECT b.*, a.config_path FROM bindings b LEFT JOIN adapters a ON b.adapter_id=a.id "
            "WHERE b.provider_id=? AND b.auto_sync=1",
            (provider_id,)
        ).fetchall()
        if not bindings:
            return []
        api_key = resolve_api_key(db, provider)
        extra = _parse_extra(provider["extra_config"])
    results = []
    for b in bindings:
        adapter = get_adapter(b["adapter_id"])
        if not adapter:
            results.append({"adapter": b["adapter_id"], "target": b["target_provider_name"], "ok": False})
            continue
        ok = do_apply(adapter, b["config_path"] or "", provider["base_url"], api_key, b["target_provider_name"], extra)
        results.append({"adapter": b["adapter_id"], "target": b["target_provider_name"], "ok": ok})
    return results


def sync_key_to_bindings(key_id: int) -> list:
    """When a vendor_key changes, sync all providers using that key."""
    with get_db_ctx() as db:
        providers = db.execute("SELECT id FROM providers WHERE vendor_key_id=?", (key_id,)).fetchall()
    results = []
    for p in providers:
        results.extend(sync_provider_to_bindings(p["id"]))
    return results


def sync_vendor_to_bindings(vendor_id: int) -> list:
    """When vendor changes, sync all providers under it."""
    with get_db_ctx() as db:
        providers = db.execute("SELECT id FROM providers WHERE vendor_id=?", (vendor_id,)).fetchall()
    results = []
    for p in providers:
        results.extend(sync_provider_to_bindings(p["id"]))
    return results


def do_push(adapter_id: str, provider_id: int, target_provider_name: str = "") -> dict:
    """Push a provider's config to a specific adapter. Returns result dict."""
    adapter = get_adapter(adapter_id)
    if not adapter:
        return {"ok": False, "error": "Adapter not found"}
    with get_db_ctx() as db:
        row = db.execute("SELECT * FROM providers WHERE id=?", (provider_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "Provider not found"}
        arow = db.execute("SELECT config_path FROM adapters WHERE id=?", (adapter_id,)).fetchone()
        config_path = arow["config_path"] if arow else ""
        api_key = resolve_api_key(db, row)
        extra = _parse_extra(row["extra_config"])
        pname = target_provider_name or row["name"]

        # Orphan detection: warn if target endpoint doesn't exist in service config
        warning = ""
        current = adapter.read_current(config_path)
        if current:
            live_names = set()
            if "providers" in current:
                live_names = {p.get("provider_name", "") for p in current["providers"] if p.get("provider_name")}
            if pname and live_names and pname not in live_names:
                warning = f"服务内端点 '{pname}' 在 {adapter_id} 的配置文件中不存在，推送可能无效"

        ok = do_apply(adapter, config_path, row["base_url"], api_key, pname, extra)
        if not ok:
            return {"ok": False, "error": f"Failed to apply config to {adapter_id}"}
        # Check if target endpoint already occupied by a different provider
        existing = db.execute(
            "SELECT provider_id FROM bindings WHERE adapter_id=? AND target_provider_name=?",
            (adapter_id, pname),
        ).fetchone()
        if existing and existing["provider_id"] != provider_id:
            return {"ok": False, "error": f"服务内端点 '{pname}' 在 {adapter_id} 中已被其他 provider 占用"}
        db.execute(
            "INSERT OR IGNORE INTO bindings (provider_id, adapter_id, target_provider_name, auto_sync) VALUES (?,?,?,1)",
            (provider_id, adapter_id, pname),
        )
        db.commit()
    result = {"ok": True, "adapter": adapter_id, "provider": row["name"], "target_provider_name": pname}
    if warning:
        result["warning"] = warning
    return result


def do_import(adapter_id: str) -> dict:
    """Import current API config from a service, create vendors+providers, and auto-bind.
    Returns {"imported": [...]} or {"error": "..."}."""
    adapter = get_adapter(adapter_id)
    if not adapter:
        return {"error": "Adapter not found"}
    with get_db_ctx() as db:
        arow = db.execute("SELECT config_path FROM adapters WHERE id=?", (adapter_id,)).fetchone()
        config_path = arow["config_path"] if arow else ""
        current = adapter.read_current(config_path)
        if not current:
            return {"error": f"No config found in {adapter_id}"}

        imported = []
        items = current.get("providers", [current]) if "providers" in current else [current]
        for item in items:
            base_url = item.get("base_url", "")
            api_key = item.get("api_key", "")
            if not api_key:
                continue
            domain = ""
            try:
                domain = urlparse(base_url).netloc
            except Exception:
                pass
            pname = item.get("provider_name", "default")
            existing_vendor = db.execute("SELECT id FROM vendors WHERE domain=?", (domain,)).fetchone() if domain else None
            if existing_vendor:
                vid = existing_vendor["id"]
            else:
                vname = domain.split(".")[0] if domain else pname
                try:
                    cur = db.execute(
                        "INSERT INTO vendors (name, domain, notes) VALUES (?,?,?)",
                        (vname, domain, f"Imported from {adapter.label}"),
                    )
                    db.commit()
                    vid = cur.lastrowid
                except Exception:
                    vname = f"{adapter_id}-{vname}"
                    cur = db.execute(
                        "INSERT INTO vendors (name, domain, notes) VALUES (?,?,?)",
                        (vname, domain, f"Imported from {adapter.label}"),
                    )
                    db.commit()
                    vid = cur.lastrowid
            existing_key = db.execute(
                "SELECT id FROM vendor_keys WHERE vendor_id=? AND api_key_enc=?",
                (vid, encrypt(api_key))
            ).fetchone()
            if existing_key:
                kid = existing_key["id"]
            else:
                cur = db.execute(
                    "INSERT INTO vendor_keys (vendor_id, label, api_key_enc, notes) VALUES (?,?,?,?)",
                    (vid, pname or "default", encrypt(api_key), f"Imported from {adapter.label}"),
                )
                db.commit()
                kid = cur.lastrowid
            # Extract connection-related extra fields
            extra = {}
            if item.get("api"):
                extra["api"] = item["api"]
            extra_json = json.dumps(extra, ensure_ascii=False) if extra else "{}"

            provider_name = f"{adapter_id}-{pname}"
            try:
                cur = db.execute(
                    "INSERT INTO providers (vendor_id, vendor_key_id, name, base_url, extra_config, notes) VALUES (?,?,?,?,?,?)",
                    (vid, kid, provider_name, base_url, extra_json, f"Imported from {adapter.label}"),
                )
                db.commit()
                pid = cur.lastrowid
                # Check target endpoint not already occupied
                existing_bind = db.execute(
                    "SELECT provider_id FROM bindings WHERE adapter_id=? AND target_provider_name=?",
                    (adapter_id, pname),
                ).fetchone()
                if not existing_bind or existing_bind["provider_id"] == pid:
                    db.execute(
                        "INSERT OR IGNORE INTO bindings (provider_id, adapter_id, target_provider_name, auto_sync) VALUES (?,?,?,1)",
                        (pid, adapter_id, pname),
                    )
                    db.commit()
                imported.append({"id": pid, "name": provider_name, "vendor_id": vid, "bound_to": pname})
            except Exception:
                pass
    if not imported:
        return {"error": "No new providers imported (may already exist)"}
    return {"imported": imported}
