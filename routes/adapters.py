"""Adapter CRUD routes."""
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from db import get_db_dep
from adapters import get_adapter, all_adapters
from utils import mask_key

router = APIRouter(prefix="/api/sync", tags=["adapters"])


class AdapterUpdate(BaseModel):
    config_path: Optional[str] = None
    icon: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("/adapters")
def list_adapters(db: sqlite3.Connection = Depends(get_db_dep)):
    db_rows = {r["id"]: dict(r) for r in db.execute("SELECT * FROM adapters").fetchall()}
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
def update_adapter(adapter_id: str, body: AdapterUpdate, db: sqlite3.Connection = Depends(get_db_dep)):
    adapter = get_adapter(adapter_id)
    if not adapter:
        raise HTTPException(404, "Adapter not found")
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
    return {"ok": True}


@router.get("/adapters/{adapter_id}/current")
def read_adapter_current(adapter_id: str, db: sqlite3.Connection = Depends(get_db_dep)):
    adapter = get_adapter(adapter_id)
    if not adapter:
        raise HTTPException(404, "Adapter not found")
    row = db.execute("SELECT config_path FROM adapters WHERE id=?", (adapter_id,)).fetchone()
    config_path = row["config_path"] if row else ""
    current = adapter.read_current(config_path)
    if not current:
        return {}
    if "api_key" in current:
        current["api_key_masked"] = mask_key(current["api_key"])
        del current["api_key"]
    if "providers" in current:
        for p in current["providers"]:
            if "api_key" in p:
                p["api_key_masked"] = mask_key(p["api_key"])
                del p["api_key"]
    return current
