"""Stats & request log routes."""
from fastapi import APIRouter, Query
from typing import Optional
from db import get_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
def get_overview():
    """Global stats: counts of vendors, keys, providers, bindings, adapters, logs."""
    db = get_db()
    vendors = db.execute("SELECT COUNT(*) as c FROM vendors").fetchone()["c"]
    keys = db.execute("SELECT COUNT(*) as c FROM vendor_keys").fetchone()["c"]
    providers = db.execute("SELECT COUNT(*) as c FROM providers").fetchone()["c"]
    bindings = db.execute("SELECT COUNT(*) as c FROM bindings").fetchone()["c"]
    adapters = db.execute("SELECT COUNT(*) as c FROM adapters WHERE enabled=1").fetchone()["c"]
    total_requests = db.execute("SELECT COUNT(*) as c FROM request_logs").fetchone()["c"]
    total_tokens = db.execute(
        "SELECT COALESCE(SUM(input_tokens),0) as inp, COALESCE(SUM(output_tokens),0) as out FROM request_logs"
    ).fetchone()
    total_cost = db.execute("SELECT COALESCE(SUM(cost),0) as c FROM request_logs").fetchone()["c"]
    # Key status summary
    keys_active = db.execute("SELECT COUNT(*) as c FROM vendor_keys WHERE status='active'").fetchone()["c"]
    db.close()
    return {
        "vendors": vendors, "keys": keys, "keys_active": keys_active,
        "providers": providers, "bindings": bindings, "adapters": adapters,
        "total_requests": total_requests,
        "total_input_tokens": total_tokens["inp"],
        "total_output_tokens": total_tokens["out"],
        "total_cost": round(total_cost, 4),
    }


@router.get("/usage")
def get_usage(
    range: str = Query("7d", pattern="^(1d|7d|30d|all)$"),
    vendor_id: Optional[int] = None,
    vendor_key_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    adapter_id: Optional[str] = None,
):
    """Time-series usage data grouped by day."""
    db = get_db()
    where = []
    params = []
    if range != "all":
        days = {"1d": 1, "7d": 7, "30d": 30}[range]
        where.append("created_at >= datetime('now', ?)")
        params.append(f"-{days} days")
    if vendor_id is not None:
        where.append("vendor_id=?"); params.append(vendor_id)
    if vendor_key_id is not None:
        where.append("vendor_key_id=?"); params.append(vendor_key_id)
    if provider_id is not None:
        where.append("provider_id=?"); params.append(provider_id)
    if adapter_id is not None:
        where.append("adapter_id=?"); params.append(adapter_id)
    w = ("WHERE " + " AND ".join(where)) if where else ""
    rows = db.execute(f"""
        SELECT date(created_at) as day,
               COUNT(*) as requests,
               COALESCE(SUM(input_tokens),0) as input_tokens,
               COALESCE(SUM(output_tokens),0) as output_tokens,
               COALESCE(SUM(cost),0) as cost
        FROM request_logs {w}
        GROUP BY date(created_at)
        ORDER BY day
    """, params).fetchall()
    db.close()
    return [{"day": r["day"], "requests": r["requests"],
             "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
             "cost": round(r["cost"], 4)} for r in rows]


@router.get("/by-vendor")
def stats_by_vendor():
    db = get_db()
    rows = db.execute("""
        SELECT r.vendor_id, v.name as vendor_name,
               COUNT(*) as requests,
               COALESCE(SUM(r.input_tokens),0) as input_tokens,
               COALESCE(SUM(r.output_tokens),0) as output_tokens,
               COALESCE(SUM(r.cost),0) as cost
        FROM request_logs r LEFT JOIN vendors v ON r.vendor_id=v.id
        GROUP BY r.vendor_id ORDER BY requests DESC
    """).fetchall()
    db.close()
    return [{"vendor_id": r["vendor_id"], "vendor_name": r["vendor_name"] or "unknown",
             "requests": r["requests"], "input_tokens": r["input_tokens"],
             "output_tokens": r["output_tokens"], "cost": round(r["cost"], 4)} for r in rows]


@router.get("/by-model")
def stats_by_model():
    db = get_db()
    rows = db.execute("""
        SELECT model, COUNT(*) as requests,
               COALESCE(SUM(input_tokens),0) as input_tokens,
               COALESCE(SUM(output_tokens),0) as output_tokens,
               COALESCE(SUM(cost),0) as cost
        FROM request_logs WHERE model != ''
        GROUP BY model ORDER BY requests DESC
    """).fetchall()
    db.close()
    return [{"model": r["model"], "requests": r["requests"],
             "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
             "cost": round(r["cost"], 4)} for r in rows]


@router.get("/by-key")
def stats_by_key(vendor_id: Optional[int] = None):
    db = get_db()
    where = ""
    params = []
    if vendor_id is not None:
        where = "WHERE vk.vendor_id=?"
        params.append(vendor_id)
    rows = db.execute(f"""
        SELECT r.vendor_key_id, vk.label as key_label, v.name as vendor_name,
               COUNT(*) as requests,
               COALESCE(SUM(r.input_tokens),0) as input_tokens,
               COALESCE(SUM(r.output_tokens),0) as output_tokens,
               COALESCE(SUM(r.cost),0) as cost
        FROM request_logs r
        LEFT JOIN vendor_keys vk ON r.vendor_key_id=vk.id
        LEFT JOIN vendors v ON vk.vendor_id=v.id
        {where}
        GROUP BY r.vendor_key_id ORDER BY requests DESC
    """, params).fetchall()
    db.close()
    return [{"vendor_key_id": r["vendor_key_id"], "key_label": r["key_label"] or "unknown",
             "vendor_name": r["vendor_name"] or "", "requests": r["requests"],
             "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
             "cost": round(r["cost"], 4)} for r in rows]


@router.get("/logs")
def get_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    vendor_id: Optional[int] = None,
    vendor_key_id: Optional[int] = None,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
):
    """Paginated request logs."""
    db = get_db()
    where = []
    params = []
    if vendor_id is not None:
        where.append("r.vendor_id=?"); params.append(vendor_id)
    if vendor_key_id is not None:
        where.append("r.vendor_key_id=?"); params.append(vendor_key_id)
    if provider_id is not None:
        where.append("r.provider_id=?"); params.append(provider_id)
    if model is not None:
        where.append("r.model LIKE ?"); params.append(f"%{model}%")
    w = ("WHERE " + " AND ".join(where)) if where else ""
    total = db.execute(f"SELECT COUNT(*) as c FROM request_logs r {w}", params).fetchone()["c"]
    offset = (page - 1) * limit
    rows = db.execute(f"""
        SELECT r.*, v.name as vendor_name, vk.label as key_label, p.name as provider_name
        FROM request_logs r
        LEFT JOIN vendors v ON r.vendor_id=v.id
        LEFT JOIN vendor_keys vk ON r.vendor_key_id=vk.id
        LEFT JOIN providers p ON r.provider_id=p.id
        {w} ORDER BY r.created_at DESC LIMIT ? OFFSET ?
    """, params + [limit, offset]).fetchall()
    db.close()
    return {
        "total": total, "page": page, "limit": limit,
        "items": [{"id": r["id"], "vendor_name": r["vendor_name"] or "",
                    "key_label": r["key_label"] or "", "provider_name": r["provider_name"] or "",
                    "adapter_id": r["adapter_id"], "model": r["model"],
                    "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
                    "cost": r["cost"], "status_code": r["status_code"],
                    "latency_ms": r["latency_ms"], "created_at": r["created_at"]} for r in rows],
    }
