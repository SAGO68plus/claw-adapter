"""Vendor Key CRUD routes."""
from fastapi import APIRouter, HTTPException
from typing import List
from db import get_db, encrypt, decrypt
from models import VendorKeyCreate, VendorKeyUpdate, VendorKeyOut

router = APIRouter(prefix="/api", tags=["keys"])


def _mask(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.get("/vendors/{vid}/keys", response_model=List[VendorKeyOut])
def list_vendor_keys(vid: int):
    db = get_db()
    rows = db.execute("SELECT * FROM vendor_keys WHERE vendor_id=? ORDER BY id", (vid,)).fetchall()
    db.close()
    return [VendorKeyOut(
        id=r["id"], vendor_id=r["vendor_id"], label=r["label"],
        api_key_masked=_mask(decrypt(r["api_key_enc"])),
        balance=r["balance"], quota=r["quota"], status=r["status"],
        notes=r["notes"] or "",
    ) for r in rows]


@router.post("/keys", response_model=VendorKeyOut)
def create_key(k: VendorKeyCreate):
    db = get_db()
    vendor = db.execute("SELECT id FROM vendors WHERE id=?", (k.vendor_id,)).fetchone()
    if not vendor:
        db.close()
        raise HTTPException(404, "Vendor not found")
    try:
        cur = db.execute(
            "INSERT INTO vendor_keys (vendor_id, label, api_key_enc, notes) VALUES (?,?,?,?)",
            (k.vendor_id, k.label, encrypt(k.api_key), k.notes),
        )
        db.commit()
        kid = cur.lastrowid
    except Exception as e:
        db.close()
        raise HTTPException(400, str(e))
    row = db.execute("SELECT * FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    db.close()
    return VendorKeyOut(
        id=row["id"], vendor_id=row["vendor_id"], label=row["label"],
        api_key_masked=_mask(decrypt(row["api_key_enc"])),
        balance=row["balance"], quota=row["quota"], status=row["status"],
        notes=row["notes"] or "",
    )


@router.put("/keys/{kid}", response_model=VendorKeyOut)
def update_key(kid: int, k: VendorKeyUpdate):
    db = get_db()
    row = db.execute("SELECT * FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    if not row:
        db.close()
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
    db.close()
    # Auto-sync providers using this key
    if key_changed:
        from routes.sync import sync_key_to_bindings
        sync_key_to_bindings(kid)
    return VendorKeyOut(
        id=row["id"], vendor_id=row["vendor_id"], label=row["label"],
        api_key_masked=_mask(decrypt(row["api_key_enc"])),
        balance=row["balance"], quota=row["quota"], status=row["status"],
        notes=row["notes"] or "",
    )


@router.delete("/keys/{kid}")
def delete_key(kid: int):
    db = get_db()
    # Unlink providers using this key (set vendor_key_id=NULL)
    db.execute("UPDATE providers SET vendor_key_id=NULL WHERE vendor_key_id=?", (kid,))
    db.execute("DELETE FROM vendor_keys WHERE id=?", (kid,))
    db.commit()
    db.close()
    return {"ok": True}


@router.get("/keys/{kid}/reveal")
def reveal_key(kid: int):
    db = get_db()
    row = db.execute("SELECT api_key_enc FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Key not found")
    return {"api_key": decrypt(row["api_key_enc"])}
