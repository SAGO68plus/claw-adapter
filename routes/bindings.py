"""Binding CRUD + topology routes."""
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from db import get_db_dep
from adapters import get_adapter, all_adapters
from models import BindingCreate, BindingOut

router = APIRouter(prefix="/api/sync", tags=["bindings"])


@router.get("/bindings")
def list_bindings(provider_id: Optional[int] = None, adapter_id: Optional[str] = None,
                  db: sqlite3.Connection = Depends(get_db_dep)):
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

    # Collect live endpoints per adapter for orphan detection
    adapter_live: dict[str, set[str]] = {}
    for r in rows:
        aid = r["adapter_id"]
        if aid not in adapter_live:
            adapter = get_adapter(aid)
            if adapter:
                arow = db.execute("SELECT config_path FROM adapters WHERE id=?", (aid,)).fetchone()
                config_path = arow["config_path"] if arow else ""
                current = adapter.read_current(config_path)
                names = set()
                if current and "providers" in current:
                    names = {p.get("provider_name", "") for p in current["providers"] if p.get("provider_name")}
                adapter_live[aid] = names
            else:
                adapter_live[aid] = set()

    result = []
    for r in rows:
        live = adapter_live.get(r["adapter_id"], set())
        orphaned = bool(r["target_provider_name"] and r["target_provider_name"] not in live)
        result.append({
            "id": r["id"], "provider_id": r["provider_id"], "provider_name": r["p_name"] or "",
            "adapter_id": r["adapter_id"], "adapter_label": r["a_label"] or "",
            "target_provider_name": r["target_provider_name"], "auto_sync": bool(r["auto_sync"]),
            "orphaned": orphaned,
        })
    return result


@router.post("/bindings")
def create_binding(b: BindingCreate, db: sqlite3.Connection = Depends(get_db_dep)):
    provider = db.execute("SELECT * FROM providers WHERE id=?", (b.provider_id,)).fetchone()
    if not provider:
        raise HTTPException(404, "Provider not found")
    adapter = get_adapter(b.adapter_id)
    if not adapter:
        raise HTTPException(404, "Adapter not found")
    # Check: target endpoint already occupied by another provider
    existing = db.execute(
        "SELECT b.id, p.name as provider_name FROM bindings b "
        "LEFT JOIN providers p ON b.provider_id = p.id "
        "WHERE b.adapter_id=? AND b.target_provider_name=?",
        (b.adapter_id, b.target_provider_name),
    ).fetchone()
    if existing:
        raise HTTPException(
            409,
            f"服务内端点 '{b.target_provider_name}' 在 {b.adapter_id} 中已被端点配置 "
            f"'{existing['provider_name']}' 占用，不允许多个 provider 推送同一个服务内端点",
        )
    # Soft validation: check if target endpoint exists in service config
    warning = ""
    arow = db.execute("SELECT config_path FROM adapters WHERE id=?", (b.adapter_id,)).fetchone()
    config_path = arow["config_path"] if arow else ""
    current = adapter.read_current(config_path)
    if current:
        live_names = set()
        if "providers" in current:
            live_names = {p.get("provider_name", "") for p in current["providers"] if p.get("provider_name")}
        if b.target_provider_name and live_names and b.target_provider_name not in live_names:
            warning = f"服务内端点 '{b.target_provider_name}' 在 {b.adapter_id} 的配置文件中不存在，绑定已创建但推送可能无效"
    try:
        cur = db.execute(
            "INSERT INTO bindings (provider_id, adapter_id, target_provider_name, auto_sync) VALUES (?,?,?,?)",
            (b.provider_id, b.adapter_id, b.target_provider_name, int(b.auto_sync)),
        )
        db.commit()
        bid = cur.lastrowid
    except Exception as e:
        raise HTTPException(400, f"Binding already exists or error: {e}")
    row = db.execute(
        """SELECT b.*, p.name as p_name, a.label as a_label
           FROM bindings b LEFT JOIN providers p ON b.provider_id=p.id
           LEFT JOIN adapters a ON b.adapter_id=a.id WHERE b.id=?""", (bid,)
    ).fetchone()
    result = {
        "id": row["id"], "provider_id": row["provider_id"], "provider_name": row["p_name"] or "",
        "adapter_id": row["adapter_id"], "adapter_label": row["a_label"] or "",
        "target_provider_name": row["target_provider_name"], "auto_sync": bool(row["auto_sync"]),
    }
    if warning:
        result["warning"] = warning
    return result


@router.delete("/bindings/{binding_id}")
def delete_binding(binding_id: int, db: sqlite3.Connection = Depends(get_db_dep)):
    db.execute("DELETE FROM bindings WHERE id=?", (binding_id,))
    db.commit()
    return {"ok": True}


@router.patch("/bindings/{binding_id}")
def update_binding(binding_id: int, auto_sync: bool, db: sqlite3.Connection = Depends(get_db_dep)):
    db.execute("UPDATE bindings SET auto_sync=? WHERE id=?", (int(auto_sync), binding_id))
    db.commit()
    return {"ok": True}


# ── Topology ──

@router.get("/topology")
def get_topology(db: sqlite3.Connection = Depends(get_db_dep)):
    """Return full topology data for visualization."""
    vendors_rows = db.execute("SELECT id, name, domain, icon FROM vendors ORDER BY name").fetchall()
    keys_rows = db.execute("SELECT id, vendor_id, label FROM vendor_keys ORDER BY id").fetchall()
    providers_rows = db.execute("SELECT id, vendor_id, vendor_key_id, name, base_url FROM providers ORDER BY name").fetchall()
    adapter_rows = {r["id"]: dict(r) for r in db.execute("SELECT * FROM adapters").fetchall()}
    bindings_rows = db.execute(
        """SELECT b.id, b.provider_id, b.adapter_id, b.target_provider_name, b.auto_sync,
                  p.name as provider_name, p.vendor_id
           FROM bindings b LEFT JOIN providers p ON b.provider_id=p.id"""
    ).fetchall()

    # Build adapter list + collect live service endpoints per adapter
    adapter_list = []
    adapter_live_endpoints: dict[str, set[str]] = {}
    for aid, adapter in all_adapters().items():
        db_info = adapter_rows.get(aid, {})
        config_path = db_info.get("config_path", adapter.default_config_path)
        current = adapter.read_current(config_path)
        service_names = []
        if current and "providers" in current:
            service_names = [p.get("provider_name", "") for p in current["providers"] if p.get("provider_name")]
        adapter_live_endpoints[aid] = set(service_names)
        adapter_list.append({
            "id": aid,
            "label": adapter.label,
            "icon": db_info.get("icon", ""),
            "enabled": bool(db_info.get("enabled", 1)),
            "services": service_names,
        })

    # Mark orphaned bindings
    bindings_out = []
    for r in bindings_rows:
        live = adapter_live_endpoints.get(r["adapter_id"], set())
        orphaned = bool(r["target_provider_name"] and r["target_provider_name"] not in live)
        bindings_out.append({
            "id": r["id"], "provider_id": r["provider_id"], "adapter_id": r["adapter_id"],
            "target_provider_name": r["target_provider_name"], "auto_sync": bool(r["auto_sync"]),
            "provider_name": r["provider_name"] or "", "vendor_id": r["vendor_id"],
            "orphaned": orphaned,
        })

    return {
        "vendors": [{"id": r["id"], "name": r["name"], "domain": r["domain"], "icon": r["icon"] or ""} for r in vendors_rows],
        "keys": [{"id": r["id"], "vendor_id": r["vendor_id"], "label": r["label"]} for r in keys_rows],
        "providers": [{"id": r["id"], "vendor_id": r["vendor_id"], "vendor_key_id": r["vendor_key_id"], "name": r["name"]} for r in providers_rows],
        "adapters": adapter_list,
        "bindings": bindings_out,
    }
