"""Common utility functions shared across routes and services."""
from db import decrypt


def mask_key(key: str) -> str:
    """Mask an API key for display, showing first/last 4 chars."""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def mask_key_enc(api_key_enc: str) -> str:
    """Decrypt then mask an encrypted API key."""
    if not api_key_enc:
        return "****"
    return mask_key(decrypt(api_key_enc))


def resolve_api_key(db, provider) -> str:
    """Get the decrypted API key for a provider via its vendor_key_id."""
    kid = provider["vendor_key_id"]
    if not kid:
        return ""
    row = db.execute("SELECT api_key_enc FROM vendor_keys WHERE id=?", (kid,)).fetchone()
    if not row:
        return ""
    return decrypt(row["api_key_enc"])
