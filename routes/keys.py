"""Vendor Key CRUD routes."""
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from db import get_db_dep, encrypt, decrypt
from models import VendorKeyCreate, VendorKeyUpdate, VendorKeyOut
from utils import mask_key_enc

router = APIRouter(prefix="/api", tags=["keys"])


@router.get("/vendors/{vid}/keys", response_model=List[VendorKeyOut])
def list_vendor_keys(vid: int, db: sqlite3.Connection = Depends(get_db_dep)):
    rows = db.execute("SELECT * FROM vendor_keys WHERE vendor_id=? ORDER BY id", (vid,)).fetchall()
    return [VendorKeyOut(
        id=r["id"], vendor_id=r["vendor_id"], label=r["label"],
        api_key_masked=mask_key_enc(r["api_key_enc"]),
        balance=r["balance"], quota=r["quota"], status=r["status"],
        notes=r["notes"] or "",
    ) for r in rows]


@router.post("/keys", response_model=VendorKeyOut)
def create_key(k: VendorKeyCreate, db: sqlite3.Connection = Depends(get_db_dep)):
    vendor = db.execute("SELECT id FROM vendors WHERE id=?", (k.vendor_id,)).fetchone()
    if not vendor:
        raise HTTPException(404, "Vendor not found")
    try:
        cur = db.execute(
            "INSERT INTO vendor_keys (vendor_id, label, api_key_enc, notes) VALUES (?,?,?,?)",
            (k.vendor_id, k.label, encrypt(k.api_key), k.notes),
        )
        db.commit()
        kid = cur.lastrowid
    except Exception as e:
        raise HTTPException(400, str(e))
    row = db.execute("SELECT * FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    return VendorKeyOut(
        id=row["id"], vendor_id=row["vendor_id"], label=row["label"],
        api_key_masked=mask_key_enc(row["api_key_enc"]),
        balance=row["balance"], quota=row["quota"], status=row["status"],
        notes=row["notes"] or "",
    )


@router.put("/keys/{kid}", response_model=VendorKeyOut)
def update_key(kid: int, k: VendorKeyUpdate, db: sqlite3.Connection = Depends(get_db_dep)):
    row = db.execute("SELECT * FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    if not row:
        raise HTTPException(404, "Key not found")
    updates, params = [], []
    key_changed = False
    if k.label is not None:
        updates.append("label=?"); params.append(k.label)
    if k.api_key is not None:
        updates.append("api_key_enc=?"); params.append(encrypt(k.api_key))
        key_changed = True
    if k.notes is not None:
        updates.append("notes=?"); params.append(k.notes)
    if updates:
        updates.append("updated_at=CURRENT_TIMESTAMP")
        params.append(kid)
        db.execute(f"UPDATE vendor_keys SET {','.join(updates)} WHERE id=?", params)
        db.commit()
    row = db.execute("SELECT * FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    if key_changed:
        from services.sync_engine import sync_key_to_bindings
        sync_key_to_bindings(kid)
    return VendorKeyOut(
        id=row["id"], vendor_id=row["vendor_id"], label=row["label"],
        api_key_masked=mask_key_enc(row["api_key_enc"]),
        balance=row["balance"], quota=row["quota"], status=row["status"],
        notes=row["notes"] or "",
    )


@router.delete("/keys/{kid}")
def delete_key(kid: int, db: sqlite3.Connection = Depends(get_db_dep)):
    row = db.execute("SELECT id FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    if not row:
        raise HTTPException(404, "Key not found")
    providers_using = db.execute(
        "SELECT COUNT(*) as c FROM providers WHERE vendor_key_id=?", (kid,)
    ).fetchone()["c"]
    if providers_using > 0:
        raise HTTPException(400, f"该密钥正被 {providers_using} 个 Provider 使用，请先解绑或更换密钥")
    db.execute("DELETE FROM vendor_keys WHERE id=?", (kid,))
    db.commit()
    return {"ok": True}


@router.get("/keys/{kid}/reveal")
def reveal_key(kid: int, db: sqlite3.Connection = Depends(get_db_dep)):
    row = db.execute("SELECT api_key_enc FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    if not row:
        raise HTTPException(404, "Key not found")
    return {"api_key": decrypt(row["api_key_enc"])}
