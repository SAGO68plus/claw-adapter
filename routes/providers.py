"""Vendor & Provider CRUD routes."""
from fastapi import APIRouter, HTTPException
from typing import List
from db import get_db, encrypt, decrypt
from models import (
    VendorCreate, VendorUpdate, VendorOut, ProviderNested, VendorKeyNested,
    ProviderCreate, ProviderUpdate, ProviderOut,
)

router = APIRouter(prefix="/api", tags=["vendors", "providers"])


def _mask(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def _build_vendor_out(db, v) -> VendorOut:
    keys = db.execute(
        "SELECT * FROM vendor_keys WHERE vendor_id=? ORDER BY id", (v["id"],)
    ).fetchall()
    providers = db.execute(
        "SELECT p.*, vk.label as key_label FROM providers p "
        "LEFT JOIN vendor_keys vk ON p.vendor_key_id=vk.id "
        "WHERE p.vendor_id=? ORDER BY p.name", (v["id"],)
    ).fetchall()
    return VendorOut(
        id=v["id"], name=v["name"], domain=v["domain"],
        icon=v["icon"] or "", notes=v["notes"] or "",
        keys=[VendorKeyNested(
            id=k["id"], label=k["label"],
            api_key_masked=_mask(decrypt(k["api_key_enc"])),
            balance=k["balance"], quota=k["quota"], status=k["status"],
            notes=k["notes"] or "",
        ) for k in keys],
        providers=[ProviderNested(
            id=p["id"], name=p["name"], base_url=p["base_url"],
            vendor_key_id=p["vendor_key_id"],
            vendor_key_label=p["key_label"] or "",
            notes=p["notes"] or "",
        ) for p in providers],
    )


# ── Vendors ──

@router.get("/vendors", response_model=List[VendorOut])
def list_vendors():
    db = get_db()
    rows = db.execute("SELECT * FROM vendors ORDER BY name").fetchall()
    result = [_build_vendor_out(db, v) for v in rows]
    db.close()
    return result


@router.post("/vendors", response_model=VendorOut)
def create_vendor(v: VendorCreate):
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO vendors (name, domain, icon, notes) VALUES (?,?,?,?)",
            (v.name, v.domain, v.icon, v.notes),
        )
        db.commit()
        vid = cur.lastrowid
    except Exception as e:
        db.close()
        raise HTTPException(400, str(e))
    row = db.execute("SELECT * FROM vendors WHERE id=?", (vid,)).fetchone()
    result = _build_vendor_out(db, row)
    db.close()
    return result


@router.put("/vendors/{vid}", response_model=VendorOut)
def update_vendor(vid: int, v: VendorUpdate):
    db = get_db()
    row = db.execute("SELECT * FROM vendors WHERE id=?", (vid,)).fetchone()
    if not row:
        db.close()
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
    result = _build_vendor_out(db, row)
    db.close()
    return result


@router.delete("/vendors/{vid}")
def delete_vendor(vid: int):
    db = get_db()
    db.execute("DELETE FROM vendors WHERE id=?", (vid,))
    db.commit()
    db.close()
    return {"ok": True}


# ── Providers ──

def _get_key_masked(db, vendor_key_id):
    if not vendor_key_id:
        return "****"
    row = db.execute("SELECT api_key_enc FROM vendor_keys WHERE id=?", (vendor_key_id,)).fetchone()
    if not row:
        return "****"
    return _mask(decrypt(row["api_key_enc"]))


@router.get("/providers", response_model=List[ProviderOut])
def list_providers():
    db = get_db()
    rows = db.execute(
        "SELECT p.*, v.name as v_name, vk.label as key_label, vk.api_key_enc "
        "FROM providers p "
        "LEFT JOIN vendors v ON p.vendor_id=v.id "
        "LEFT JOIN vendor_keys vk ON p.vendor_key_id=vk.id "
        "ORDER BY p.name"
    ).fetchall()
    db.close()
    return [ProviderOut(
        id=r["id"], vendor_id=r["vendor_id"], vendor_name=r["v_name"] or "",
        vendor_key_id=r["vendor_key_id"], vendor_key_label=r["key_label"] or "",
        name=r["name"], base_url=r["base_url"],
        api_key_masked=_mask(decrypt(r["api_key_enc"])) if r["api_key_enc"] else "****",
        notes=r["notes"] or "",
    ) for r in rows]


@router.post("/providers", response_model=ProviderOut)
def create_provider(p: ProviderCreate):
    db = get_db()
    vendor = db.execute("SELECT * FROM vendors WHERE id=?", (p.vendor_id,)).fetchone()
    if not vendor:
        db.close()
        raise HTTPException(404, "Vendor not found")
    try:
        cur = db.execute(
            "INSERT INTO providers (vendor_id, vendor_key_id, name, base_url, notes) VALUES (?,?,?,?,?)",
            (p.vendor_id, p.vendor_key_id, p.name, p.base_url, p.notes),
        )
        db.commit()
        pid = cur.lastrowid
    except Exception as e:
        db.close()
        raise HTTPException(400, str(e))
    row = db.execute("SELECT * FROM providers WHERE id=?", (pid,)).fetchone()
    key_masked = _get_key_masked(db, row["vendor_key_id"])
    db.close()
    return ProviderOut(
        id=row["id"], vendor_id=row["vendor_id"], vendor_name=vendor["name"],
        vendor_key_id=row["vendor_key_id"], vendor_key_label="",
        name=row["name"], base_url=row["base_url"],
        api_key_masked=key_masked, notes=row["notes"] or "",
    )


@router.put("/providers/{pid}", response_model=ProviderOut)
def update_provider(pid: int, p: ProviderUpdate):
    db = get_db()
    row = db.execute("SELECT * FROM providers WHERE id=?", (pid,)).fetchone()
    if not row:
        db.close()
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
    key_masked = _get_key_masked(db, row["vendor_key_id"])
    db.close()
    if url_changed or key_changed:
        from routes.sync import sync_provider_to_bindings
        sync_provider_to_bindings(pid)
    return ProviderOut(
        id=row["id"], vendor_id=row["vendor_id"],
        vendor_name=vendor["name"] if vendor else "",
        vendor_key_id=row["vendor_key_id"], vendor_key_label="",
        name=row["name"], base_url=row["base_url"],
        api_key_masked=key_masked, notes=row["notes"] or "",
    )


@router.delete("/providers/{pid}")
def delete_provider(pid: int):
    db = get_db()
    db.execute("DELETE FROM providers WHERE id=?", (pid,))
    db.commit()
    db.close()
    return {"ok": True}
