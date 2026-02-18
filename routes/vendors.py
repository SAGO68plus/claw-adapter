"""Vendor CRUD routes."""
import sqlite3
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from db import get_db_dep
from models import VendorCreate, VendorUpdate, VendorOut
from services.vendor_service import build_vendor_out

router = APIRouter(prefix="/api", tags=["vendors"])


@router.get("/vendors", response_model=List[VendorOut])
def list_vendors(db: sqlite3.Connection = Depends(get_db_dep)):
    rows = db.execute("SELECT * FROM vendors ORDER BY name").fetchall()
    return [build_vendor_out(db, v) for v in rows]


@router.post("/vendors", response_model=VendorOut)
def create_vendor(v: VendorCreate, db: sqlite3.Connection = Depends(get_db_dep)):
    try:
        cur = db.execute(
            "INSERT INTO vendors (name, domain, icon, notes) VALUES (?,?,?,?)",
            (v.name, v.domain, v.icon, v.notes),
        )
        db.commit()
        vid = cur.lastrowid
    except Exception as e:
        raise HTTPException(400, str(e))
    row = db.execute("SELECT * FROM vendors WHERE id=?", (vid,)).fetchone()
    return build_vendor_out(db, row)


@router.put("/vendors/{vid}", response_model=VendorOut)
def update_vendor(vid: int, v: VendorUpdate, db: sqlite3.Connection = Depends(get_db_dep)):
    row = db.execute("SELECT * FROM vendors WHERE id=?", (vid,)).fetchone()
    if not row:
        raise HTTPException(404, "Vendor not found")
    updates, params = [], []
    if v.name is not None:
        updates.append("name=?"); params.append(v.name)
    if v.domain is not None:
        updates.append("domain=?"); params.append(v.domain)
    if v.icon is not None:
        updates.append("icon=?"); params.append(v.icon)
    if v.notes is not None:
        updates.append("notes=?"); params.append(v.notes)
    if updates:
        updates.append("updated_at=CURRENT_TIMESTAMP")
        params.append(vid)
        db.execute(f"UPDATE vendors SET {','.join(updates)} WHERE id=?", params)
        db.commit()
    row = db.execute("SELECT * FROM vendors WHERE id=?", (vid,)).fetchone()
    return build_vendor_out(db, row)


@router.delete("/vendors/{vid}")
def delete_vendor(vid: int, db: sqlite3.Connection = Depends(get_db_dep)):
    db.execute("DELETE FROM vendors WHERE id=?", (vid,))
    db.commit()
    return {"ok": True}
