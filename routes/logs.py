"""Request log ingestion route."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from db import get_db

router = APIRouter(prefix="/api/logs", tags=["logs"])


class LogEntry(BaseModel):
    vendor_id: Optional[int] = None
    vendor_key_id: Optional[int] = None
    provider_id: Optional[int] = None
    adapter_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0
    status_code: int = 200
    latency_ms: int = 0


@router.post("/ingest")
def ingest_log(entry: LogEntry):
    """Receive a request log entry from external services."""
    db = get_db()
    db.execute(
        """INSERT INTO request_logs
           (vendor_id, vendor_key_id, provider_id, adapter_id, model,
            input_tokens, output_tokens, cost, status_code, latency_ms)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (entry.vendor_id, entry.vendor_key_id, entry.provider_id,
         entry.adapter_id, entry.model, entry.input_tokens, entry.output_tokens,
         entry.cost, entry.status_code, entry.latency_ms),
    )
    db.commit()
    db.close()
    return {"ok": True}


@router.post("/ingest/batch")
def ingest_batch(entries: list[LogEntry]):
    """Receive multiple log entries at once."""
    db = get_db()
    for e in entries:
        db.execute(
            """INSERT INTO request_logs
               (vendor_id, vendor_key_id, provider_id, adapter_id, model,
                input_tokens, output_tokens, cost, status_code, latency_ms)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (e.vendor_id, e.vendor_key_id, e.provider_id,
             e.adapter_id, e.model, e.input_tokens, e.output_tokens,
             e.cost, e.status_code, e.latency_ms),
        )
    db.commit()
    db.close()
    return {"ok": True, "count": len(entries)}
