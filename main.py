"""ClawAdapter — lightweight API key management service."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import db
from routes.vendors import router as vendors_router
from routes.providers import router as providers_router
from routes.keys import router as keys_router
from routes.adapter_routes import router as adapters_router
from routes.bindings import router as bindings_router
from routes.sync import router as sync_router
from routes.stats import router as stats_router
from routes.logs import router as logs_router
from routes.upload import router as upload_router

app = FastAPI(title="ClawAdapter", version="0.1.0")

@app.on_event("startup")
def startup():
    db.init_db()
    # Ensure built-in adapters are registered in DB
    conn = db.get_db()
    from adapters import all_adapters
    for aid, adapter in all_adapters().items():
        conn.execute(
            "INSERT OR IGNORE INTO adapters (id, label, config_path, enabled) VALUES (?,?,?,1)",
            (aid, adapter.label, adapter.default_config_path),
        )
    conn.commit()
    conn.close()

app.include_router(vendors_router)
app.include_router(providers_router)
app.include_router(keys_router)
app.include_router(adapters_router)
app.include_router(bindings_router)
app.include_router(sync_router)
app.include_router(stats_router)
app.include_router(logs_router)
app.include_router(upload_router)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    return FileResponse("static/index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8900)
