"""Sync routes — adapter management, bindings, push config, import from services."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from urllib.parse import urlparse
from db import get_db, decrypt, encrypt
from adapters import get_adapter, all_adapters
from models import BindingCreate, BindingOut

router = APIRouter(prefix="/api/sync", tags=["sync"])


class AdapterUpdate(BaseModel):
    config_path: Optional[str] = None
    icon: Optional[str] = None
    enabled: Optional[bool] = None


def _mask(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


# ── Adapters ──

@router.get("/adapters")
def list_adapters():
    db = get_db()
    db_rows = {r["id"]: dict(r) for r in db.execute("SELECT * FROM adapters").fetchall()}
    db.close()
    result = []
    for aid, adapter in all_adapters().items():
        db_info = db_rows.get(aid, {})
        result.append({
            "id": aid,
            "label": adapter.label,
            "config_path": db_info.get("config_path", adapter.default_config_path),
            "icon": db_info.get("icon", ""),
            "enabled": bool(db_info.get("enabled", 1)),
        })
    return result


@router.put("/adapters/{adapter_id}")
def update_adapter(adapter_id: str, body: AdapterUpdate):
    adapter = get_adapter(adapter_id)
    if not adapter:
        raise HTTPException(404, "Adapter not found")
    db = get_db()
    row = db.execute("SELECT * FROM adapters WHERE id=?", (adapter_id,)).fetchone()
    config_path = body.config_path if body.config_path is not None else (row["config_path"] if row else adapter.default_config_path)
    icon = body.icon if body.icon is not None else (row["icon"] if row else "")
    enabled = body.enabled if body.enabled is not None else (bool(row["enabled"]) if row else True)
    db.execute(
        "INSERT INTO adapters (id, label, config_path, icon, enabled) VALUES (?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET config_path=excluded.config_path, icon=excluded.icon, enabled=excluded.enabled",
        (adapter_id, adapter.label, config_path, icon, int(enabled)),
    )
    db.commit()
    db.close()
    return {"ok": True}


@router.get("/adapters/{adapter_id}/current")
def read_adapter_current(adapter_id: str):
    adapter = get_adapter(adapter_id)
    if not adapter:
        raise HTTPException(404, "Adapter not found")
    db = get_db()
    row = db.execute("SELECT config_path FROM adapters WHERE id=?", (adapter_id,)).fetchone()
    db.close()
    config_path = row["config_path"] if row else ""
    current = adapter.read_current(config_path)
    if not current:
        return {}
    if "api_key" in current:
        current["api_key_masked"] = _mask(current["api_key"])
        del current["api_key"]
    if "providers" in current:
        for p in current["providers"]:
            if "api_key" in p:
                p["api_key_masked"] = _mask(p["api_key"])
                del p["api_key"]
    return current


# ── Bindings ──

@router.get("/bindings", response_model=List[BindingOut])
def list_bindings(provider_id: Optional[int] = None, adapter_id: Optional[str] = None):
    db = get_db()
    sql = """SELECT b.*, p.name as p_name, a.label as a_label
             FROM bindings b
             LEFT JOIN providers p ON b.provider_id = p.id
             LEFT JOIN adapters a ON b.adapter_id = a.id
             WHERE 1=1"""
    params = []
    if provider_id is not None:
        sql += " AND b.provider_id=?"
        params.append(provider_id)
    if adapter_id is not None:
        sql += " AND b.adapter_id=?"
        params.append(adapter_id)
    rows = db.execute(sql, params).fetchall()
    db.close()
    return [BindingOut(
        id=r["id"], provider_id=r["provider_id"], provider_name=r["p_name"] or "",
        adapter_id=r["adapter_id"], adapter_label=r["a_label"] or "",
        target_provider_name=r["target_provider_name"], auto_sync=bool(r["auto_sync"]),
    ) for r in rows]


@router.post("/bindings", response_model=BindingOut)
def create_binding(b: BindingCreate):
    db = get_db()
    provider = db.execute("SELECT * FROM providers WHERE id=?", (b.provider_id,)).fetchone()
    if not provider:
        db.close()
        raise HTTPException(404, "Provider not found")
    adapter = get_adapter(b.adapter_id)
    if not adapter:
        db.close()
        raise HTTPException(404, "Adapter not found")
    try:
        cur = db.execute(
            "INSERT INTO bindings (provider_id, adapter_id, target_provider_name, auto_sync) VALUES (?,?,?,?)",
            (b.provider_id, b.adapter_id, b.target_provider_name, int(b.auto_sync)),
        )
        db.commit()
        bid = cur.lastrowid
    except Exception as e:
        db.close()
        raise HTTPException(400, f"Binding already exists or error: {e}")
    row = db.execute(
        """SELECT b.*, p.name as p_name, a.label as a_label
           FROM bindings b LEFT JOIN providers p ON b.provider_id=p.id
           LEFT JOIN adapters a ON b.adapter_id=a.id WHERE b.id=?""", (bid,)
    ).fetchone()
    db.close()
    return BindingOut(
        id=row["id"], provider_id=row["provider_id"], provider_name=row["p_name"] or "",
        adapter_id=row["adapter_id"], adapter_label=row["a_label"] or "",
        target_provider_name=row["target_provider_name"], auto_sync=bool(row["auto_sync"]),
    )


@router.delete("/bindings/{binding_id}")
def delete_binding(binding_id: int):
    db = get_db()
    db.execute("DELETE FROM bindings WHERE id=?", (binding_id,))
    db.commit()
    db.close()
    return {"ok": True}


@router.patch("/bindings/{binding_id}")
def update_binding(binding_id: int, auto_sync: bool):
    db = get_db()
    db.execute("UPDATE bindings SET auto_sync=? WHERE id=?", (int(auto_sync), binding_id))
    db.commit()
    db.close()
    return {"ok": True}


# ── Topology ──

@router.get("/topology")
def get_topology():
    """Return full topology data for visualization: vendors, providers, adapters, bindings."""
    db = get_db()
    vendors_rows = db.execute("SELECT id, name, domain, icon FROM vendors ORDER BY name").fetchall()
    keys_rows = db.execute("SELECT id, vendor_id, label FROM vendor_keys ORDER BY id").fetchall()
    providers_rows = db.execute("SELECT id, vendor_id, vendor_key_id, name, base_url FROM providers ORDER BY name").fetchall()
    adapter_rows = {r["id"]: dict(r) for r in db.execute("SELECT * FROM adapters").fetchall()}
    bindings_rows = db.execute(
        """SELECT b.id, b.provider_id, b.adapter_id, b.target_provider_name, b.auto_sync,
                  p.name as provider_name, p.vendor_id
           FROM bindings b LEFT JOIN providers p ON b.provider_id=p.id"""
    ).fetchall()
    db.close()

    # Build adapter list with current provider names from read_current
    adapter_list = []
    for aid, adapter in all_adapters().items():
        db_info = adapter_rows.get(aid, {})
        config_path = db_info.get("config_path", adapter.default_config_path)
        current = adapter.read_current(config_path)
        service_names = []
        if current and "providers" in current:
            service_names = [p.get("provider_name", "") for p in current["providers"] if p.get("provider_name")]
        adapter_list.append({
            "id": aid,
            "label": adapter.label,
            "icon": db_info.get("icon", ""),
            "enabled": bool(db_info.get("enabled", 1)),
            "services": service_names,
        })

    return {
        "vendors": [{"id": r["id"], "name": r["name"], "domain": r["domain"], "icon": r["icon"] or ""} for r in vendors_rows],
        "keys": [{"id": r["id"], "vendor_id": r["vendor_id"], "label": r["label"]} for r in keys_rows],
        "providers": [{"id": r["id"], "vendor_id": r["vendor_id"], "vendor_key_id": r["vendor_key_id"], "name": r["name"]} for r in providers_rows],
        "adapters": adapter_list,
        "bindings": [{"id": r["id"], "provider_id": r["provider_id"], "adapter_id": r["adapter_id"],
                       "target_provider_name": r["target_provider_name"], "auto_sync": bool(r["auto_sync"]),
                       "provider_name": r["provider_name"] or "", "vendor_id": r["vendor_id"]} for r in bindings_rows],
    }


# ── Sync engine ──

def _do_apply(adapter, config_path, base_url, api_key, target_name):
    """Apply config to an adapter, return ok bool."""
    return adapter.apply(config_path, base_url, api_key, provider_name=target_name)


def _resolve_api_key(db, provider) -> str:
    """Get the decrypted API key for a provider via its vendor_key_id."""
    kid = provider["vendor_key_id"]
    if not kid:
        return ""
    row = db.execute("SELECT api_key_enc FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    if not row:
        return ""
    return decrypt(row["api_key_enc"])


def sync_provider_to_bindings(provider_id: int):
    """Push a provider's config to all its auto_sync bindings."""
    db = get_db()
    provider = db.execute("SELECT * FROM providers WHERE id=?", (provider_id,)).fetchone()
    if not provider:
        db.close()
        return []
    bindings = db.execute(
        "SELECT b.*, a.config_path FROM bindings b LEFT JOIN adapters a ON b.adapter_id=a.id WHERE b.provider_id=? AND b.auto_sync=1",
        (provider_id,)
    ).fetchall()
    if not bindings:
        db.close()
        return []
    api_key = _resolve_api_key(db, provider)
    db.close()
    results = []
    for b in bindings:
        adapter = get_adapter(b["adapter_id"])
        if not adapter:
            results.append({"adapter": b["adapter_id"], "target": b["target_provider_name"], "ok": False})
            continue
        ok = _do_apply(adapter, b["config_path"] or "", provider["base_url"], api_key, b["target_provider_name"])
        results.append({"adapter": b["adapter_id"], "target": b["target_provider_name"], "ok": ok})
    return results


def sync_key_to_bindings(key_id: int):
    """When a vendor_key changes, sync all providers using that key."""
    db = get_db()
    providers = db.execute("SELECT id FROM providers WHERE vendor_key_id=?", (key_id,)).fetchall()
    db.close()
    results = []
    for p in providers:
        results.extend(sync_provider_to_bindings(p["id"]))
    return results


def sync_vendor_to_bindings(vendor_id: int):
    """When vendor changes, sync all providers under it."""
    db = get_db()
    providers = db.execute("SELECT id FROM providers WHERE vendor_id=?", (vendor_id,)).fetchall()
    db.close()
    results = []
    for p in providers:
        results.extend(sync_provider_to_bindings(p["id"]))
    return results


# ── Push / Import ──

@router.post("/push/{adapter_id}/{provider_id}")
def push_to_adapter(adapter_id: str, provider_id: int, target_provider_name: str = ""):
    adapter = get_adapter(adapter_id)
    if not adapter:
        raise HTTPException(404, "Adapter not found")
    db = get_db()
    row = db.execute("SELECT * FROM providers WHERE id=?", (provider_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Provider not found")
    arow = db.execute("SELECT config_path FROM adapters WHERE id=?", (adapter_id,)).fetchone()
    config_path = arow["config_path"] if arow else ""
    api_key = _resolve_api_key(db, row)
    pname = target_provider_name or row["name"]
    ok = _do_apply(adapter, config_path, row["base_url"], api_key, pname)
    if not ok:
        db.close()
        raise HTTPException(500, f"Failed to apply config to {adapter_id}")
    db.execute(
        "INSERT OR IGNORE INTO bindings (provider_id, adapter_id, target_provider_name, auto_sync) VALUES (?,?,?,1)",
        (provider_id, adapter_id, pname),
    )
    db.commit()
    db.close()
    return {"ok": True, "adapter": adapter_id, "provider": row["name"], "target_provider_name": pname}


@router.post("/import/{adapter_id}")
def import_from_adapter(adapter_id: str):
    """Import current API config from a service, create vendors+providers, and auto-bind."""
    adapter = get_adapter(adapter_id)
    if not adapter:
        raise HTTPException(404, "Adapter not found")
    db = get_db()
    arow = db.execute("SELECT config_path FROM adapters WHERE id=?", (adapter_id,)).fetchone()
    config_path = arow["config_path"] if arow else ""
    current = adapter.read_current(config_path)
    if not current:
        db.close()
        raise HTTPException(400, f"No config found in {adapter_id}")

    imported = []
    items = current.get("providers", [current]) if "providers" in current else [current]
    for item in items:
        base_url = item.get("base_url", "")
        api_key = item.get("api_key", "")
        if not api_key:
            continue
        # Extract domain for vendor grouping
        domain = ""
        try:
            domain = urlparse(base_url).netloc
        except Exception:
            pass
        pname = item.get("provider_name", "default")
        # Find or create vendor by domain
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
        # Find or create vendor_key
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
        # Create provider under vendor
        provider_name = f"{adapter_id}-{pname}"
        try:
            cur = db.execute(
                "INSERT INTO providers (vendor_id, vendor_key_id, name, base_url, notes) VALUES (?,?,?,?,?)",
                (vid, kid, provider_name, base_url, f"Imported from {adapter.label}"),
            )
            db.commit()
            pid = cur.lastrowid
            # Auto-create binding
            db.execute(
                "INSERT OR IGNORE INTO bindings (provider_id, adapter_id, target_provider_name, auto_sync) VALUES (?,?,?,1)",
                (pid, adapter_id, pname),
            )
            db.commit()
            imported.append({"id": pid, "name": provider_name, "vendor_id": vid, "bound_to": pname})
        except Exception:
            pass
    db.close()
    if not imported:
        raise HTTPException(400, "No new providers imported (may already exist)")
    return {"imported": imported}
