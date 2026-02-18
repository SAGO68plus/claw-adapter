"""Sync routes — push config and import from services."""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/push/{adapter_id}/{provider_id}")
def push_to_adapter(adapter_id: str, provider_id: int, target_provider_name: str = ""):
    from services.sync_engine import do_push
    result = do_push(adapter_id, provider_id, target_provider_name)
    if not result.get("ok"):
        raise HTTPException(400 if result.get("error", "").startswith("No") else 404, result.get("error", "Unknown error"))
    return result


@router.post("/import/{adapter_id}")
def import_from_adapter(adapter_id: str):
    """Import current API config from a service, create vendors+providers, and auto-bind."""
    from services.sync_engine import do_import
    result = do_import(adapter_id)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result
