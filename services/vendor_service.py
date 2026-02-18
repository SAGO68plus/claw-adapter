"""Vendor service — aggregation queries for vendor data."""
from db import decrypt
from models import VendorOut, VendorKeyNested, ProviderNested
from utils import mask_key


def build_vendor_out(db, v) -> VendorOut:
    """Build a full VendorOut with nested keys and providers."""
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
            api_key_masked=mask_key(decrypt(k["api_key_enc"])),
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
