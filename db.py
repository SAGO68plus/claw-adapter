"""SQLite database + Fernet encryption for API keys."""
import os
import sqlite3
from contextlib import contextmanager
from cryptography.fernet import Fernet

DB_PATH = os.environ.get("VAULT_DB", os.path.join(os.path.dirname(__file__), "vault.db"))
_MASTER_KEY = os.environ.get("VAULT_KEY", "")

def _get_fernet():
    key = _MASTER_KEY
    if not key:
        key_file = os.path.join(os.path.dirname(__file__), ".vault_key")
        if os.path.exists(key_file):
            key = open(key_file).read().strip()
        else:
            key = Fernet.generate_key().decode()
            with open(key_file, "w") as f:
                f.write(key)
            os.chmod(key_file, 0o600)
    return Fernet(key.encode() if isinstance(key, str) else key)

_fernet = _get_fernet()

def encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode()).decode()

def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db_ctx():
    """Context manager for manual use: with get_db_ctx() as db: ..."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def get_db_dep():
    """FastAPI Depends generator: db = Depends(get_db_dep)"""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            domain TEXT NOT NULL DEFAULT '',
            icon TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS vendor_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            label TEXT NOT NULL DEFAULT 'default',
            api_key_enc TEXT NOT NULL,
            balance REAL DEFAULT NULL,
            quota REAL DEFAULT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER NOT NULL,
            vendor_key_id INTEGER DEFAULT NULL,
            name TEXT NOT NULL UNIQUE,
            base_url TEXT NOT NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE,
            FOREIGN KEY (vendor_key_id) REFERENCES vendor_keys(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS adapters (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            config_path TEXT NOT NULL DEFAULT '',
            icon TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_id INTEGER NOT NULL,
            adapter_id TEXT NOT NULL,
            target_provider_name TEXT NOT NULL DEFAULT '',
            auto_sync INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE,
            FOREIGN KEY (adapter_id) REFERENCES adapters(id) ON DELETE CASCADE,
            UNIQUE(provider_id, adapter_id, target_provider_name)
        );
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER,
            vendor_key_id INTEGER,
            provider_id INTEGER,
            adapter_id TEXT DEFAULT '',
            model TEXT DEFAULT '',
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost REAL DEFAULT 0,
            status_code INTEGER DEFAULT 200,
            latency_ms INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE SET NULL,
            FOREIGN KEY (vendor_key_id) REFERENCES vendor_keys(id) ON DELETE SET NULL,
            FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS model_pricing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER,
            model_name TEXT NOT NULL,
            input_price REAL DEFAULT 0,
            output_price REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            source TEXT DEFAULT 'manual',
            source_url TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(vendor_id, model_name),
            FOREIGN KEY (vendor_id) REFERENCES vendors(id) ON DELETE CASCADE
        );
    """)
    # ── Migrations ──
    cur = conn.execute("PRAGMA table_info(vendors)")
    vendor_cols = [r[1] for r in cur.fetchall()]
    if "icon" not in vendor_cols:
        conn.execute("ALTER TABLE vendors ADD COLUMN icon TEXT DEFAULT ''")
    cur = conn.execute("PRAGMA table_info(adapters)")
    adapter_cols = [r[1] for r in cur.fetchall()]
    if "icon" not in adapter_cols:
        conn.execute("ALTER TABLE adapters ADD COLUMN icon TEXT DEFAULT ''")
    cur = conn.execute("PRAGMA table_info(providers)")
    provider_cols = [r[1] for r in cur.fetchall()]
    if "vendor_key_id" not in provider_cols:
        conn.execute("ALTER TABLE providers ADD COLUMN vendor_key_id INTEGER DEFAULT NULL REFERENCES vendor_keys(id) ON DELETE SET NULL")
    # Migrate api_key_enc from vendors → vendor_keys (v0.3 → v0.4)
    if "api_key_enc" in vendor_cols:
        rows = conn.execute("SELECT id, api_key_enc FROM vendors WHERE api_key_enc IS NOT NULL AND api_key_enc != ''").fetchall()
        for r in rows:
            existing = conn.execute("SELECT id FROM vendor_keys WHERE vendor_id=?", (r["id"],)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO vendor_keys (vendor_id, label, api_key_enc) VALUES (?,?,?)",
                    (r["id"], "default", r["api_key_enc"]),
                )
                kid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute("UPDATE providers SET vendor_key_id=? WHERE vendor_id=? AND vendor_key_id IS NULL", (kid, r["id"]))
        try:
            conn.execute("ALTER TABLE vendors DROP COLUMN api_key_enc")
        except Exception:
            pass  # older SQLite, column stays but is unused
    conn.commit()
    conn.close()
