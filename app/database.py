import aiosqlite
from app.config import DB_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _init_tables(_db)
    return _db


async def _init_tables(db: aiosqlite.Connection):
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            dept_code TEXT NOT NULL,
            dept_name TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            appointment_number INTEGER NOT NULL,
            last_notified_number INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, doctor_name)
        );

        CREATE TABLE IF NOT EXISTS clinic_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_code TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            current_number INTEGER NOT NULL,
            next_number TEXT,
            location TEXT,
            sub_dept TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(dept_code, doctor_name)
        );

        CREATE TABLE IF NOT EXISTS user_state (
            user_id TEXT PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'IDLE',
            context TEXT DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    await db.commit()


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None
