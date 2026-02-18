"""Provider CRUD routes."""
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from db import get_db_dep
from models import ProviderCreate, ProviderUpdate, ProviderOut
from utils import mask_key_enc

router = APIRouter(prefix="/api", tags=["providers"])


def _get_key_masked(db, vendor_key_id):
    if not vendor_key_id:
        return "****"
    row = db.execute("SELECT api_key_enc FROM vendor_keys WHERE id=?", (vendor_key_id,)).fetchone()
    if not row:
        return "****"
    return mask_key_enc(row["api_key_enc"])


@router.get("/providers", response_model=List[ProviderOut])
def list_providers(db: sqlite3.Connection = Depends(get_db_dep)):
    rows = db.execute(
        "SELECT p.*, v.name as v_name, vk.label as key_label, vk.api_key_enc "
        "FROM providers p "
        "LEFT JOIN vendors v ON p.vendor_id=v.id "
        "LEFT JOIN vendor_keys vk ON p.vendor_key_id=vk.id "
        "ORDER BY p.name"
    ).fetchall()
    return [ProviderOut(
        id=r["id"], vendor_id=r["vendor_id"], vendor_name=r["v_name"] or "",
        vendor_key_id=r["vendor_key_id"], vendor_key_label=r["key_label"] or "",
        name=r["name"], base_url=r["base_url"],
        api_key_masked=mask_key_enc(r["api_key_enc"]) if r["api_key_enc"] else "****",
        notes=r["notes"] or "",
    ) for r in rows]


@router.post("/providers", response_model=ProviderOut)
def create_provider(p: ProviderCreate, db: sqlite3.Connection = Depends(get_db_dep)):
    vendor = db.execute("SELECT * FROM vendors WHERE id=?", (p.vendor_id,)).fetchone()
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    try:
        cur = db.execute(
            "INSERT INTO providers (vendor_id, vendor_key_id, name, base_url, notes) VALUES (?,?,?,?,?)",
            (p.vendor_id, p.vendor_key_id, p.name, p.base_url, p.notes),
        )
        db.commit()
        pid = cur.lastrowid
    except Exception as e:
        raise HTTPException(400, str(e))
    row = db.execute("SELECT * FROM providers WHERE id=?", (pid,)).fetchone()
    return ProviderOut(
        id=row["id"], vendor_id=row["vendor_id"], vendor_name=vendor["name"],
        vendor_key_id=row["vendor_key_id"], vendor_key_label="",
        name=row["name"], base_url=row["base_url"],
        api_key_masked=_get_key_masked(db, row["vendor_key_id"]), notes=row["notes"] or "",
    )


@router.put("/providers/{pid}", response_model=ProviderOut)
def update_provider(pid: int, p: ProviderUpdate, db: sqlite3.Connection = Depends(get_db_dep)):
    row = db.execute("SELECT * FROM providers WHERE id=?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "Provider not found")
    updates, params = [], []
    url_changed = False
    key_changed = False
    if p.name is not None:
        updates.append("name=?"); params.append(p.name)
    if p.base_url is not None:
        updates.append("base_url=?"); params.append(p.base_url)
        url_changed = True
    if p.vendor_key_id is not None:
        updates.append("vendor_key_id=?"); params.append(p.vendor_key_id)
        key_changed = True
    if p.notes is not None:
        updates.append("notes=?"); params.append(p.notes)
    if updates:
        updates.append("updated_at=CURRENT_TIMESTAMP")
        params.append(pid)
        db.execute(f"UPDATE providers SET {','.join(updates)} WHERE id=?", params)
        db.commit()
    row = db.execute("SELECT * FROM providers WHERE id=?", (pid,)).fetchone()
    vendor = db.execute("SELECT * FROM vendors WHERE id=?", (row["vendor_id"],)).fetchone()
    if url_changed or key_changed:
        from services.sync_engine import sync_provider_to_bindings
        sync_provider_to_bindings(pid)
    return ProviderOut(
        id=row["id"], vendor_id=row["vendor_id"],
        vendor_name=vendor["name"] if vendor else "",
        vendor_key_id=row["vendor_key_id"], vendor_key_label="",
        name=row["name"], base_url=row["base_url"],
        api_key_masked=_get_key_masked(db, row["vendor_key_id"]), notes=row["notes"] or "",
    )


@router.delete("/providers/{pid}")
def delete_provider(pid: int, db: sqlite3.Connection = Depends(get_db_dep)):
    db.execute("DELETE FROM providers WHERE id=?", (pid,))
    db.commit()
    return {"ok": True}
