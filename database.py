"""
Database manager — SQLite with aiosqlite for async access.
Handles user state machine, monitored Telegram channels, and stats.
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Tuple
import aiosqlite

from config import DB_PATH


# ─── Schema ───────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    chat_id         TEXT PRIMARY KEY,
    state           TEXT DEFAULT 'main',
    state_data      TEXT DEFAULT '{}',
    total_requests  INTEGER DEFAULT 0,
    created_at      INTEGER DEFAULT (strftime('%s','now')),
    updated_at      INTEGER DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS monitored_channels (
    chat_id         TEXT NOT NULL,
    channel         TEXT NOT NULL,
    last_msg_link   TEXT DEFAULT '',
    alert_enabled   INTEGER DEFAULT 0,
    added_at        INTEGER DEFAULT (strftime('%s','now')),
    PRIMARY KEY (chat_id, channel)
);

CREATE TABLE IF NOT EXISTS request_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id         TEXT,
    action          TEXT,
    ts              INTEGER DEFAULT (strftime('%s','now'))
);
"""


# ─── Init ─────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables on first run."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


# ─── User State ───────────────────────────────────────────────────────────────

async def get_state(chat_id: str) -> Dict[str, Any]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT state, state_data FROM users WHERE chat_id = ?", (chat_id,)
        ) as cur:
            row = await cur.fetchone()
    if row:
        return {"state": row[0], "data": json.loads(row[1] or "{}")}
    return {"state": "main", "data": {}}


async def set_state(chat_id: str, state: str, data: Optional[Dict] = None) -> None:
    data_str = json.dumps(data or {})
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (chat_id, state, state_data, updated_at)
            VALUES (?, ?, ?, strftime('%s','now'))
            ON CONFLICT(chat_id) DO UPDATE SET
                state      = excluded.state,
                state_data = excluded.state_data,
                updated_at = excluded.updated_at,
                total_requests = total_requests + 1
            """,
            (chat_id, state, data_str),
        )
        await db.commit()


async def reset_state(chat_id: str) -> None:
    await set_state(chat_id, "main", {})


# ─── Monitored Channels ───────────────────────────────────────────────────────

async def add_monitored_channel(chat_id: str, channel: str) -> bool:
    """Returns True if newly added, False if already exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO monitored_channels (chat_id, channel) VALUES (?, ?)",
                (chat_id, channel),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_monitored_channel(chat_id: str, channel: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM monitored_channels WHERE chat_id = ? AND channel = ?",
            (chat_id, channel),
        )
        await db.commit()


async def get_user_channels(chat_id: str) -> List[Tuple[str, str, int]]:
    """Returns list of (channel, last_msg_link, alert_enabled)."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT channel, last_msg_link, alert_enabled FROM monitored_channels WHERE chat_id = ?",
            (chat_id,),
        ) as cur:
            return await cur.fetchall()


async def toggle_channel_alert(chat_id: str, channel: str, enabled: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE monitored_channels SET alert_enabled = ? WHERE chat_id = ? AND channel = ?",
            (1 if enabled else 0, chat_id, channel),
        )
        await db.commit()


async def update_last_msg_link(chat_id: str, channel: str, link: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE monitored_channels SET last_msg_link = ? WHERE chat_id = ? AND channel = ?",
            (link, chat_id, channel),
        )
        await db.commit()


async def get_all_alert_subs() -> List[Tuple[str, str, str]]:
    """Get all (chat_id, channel, last_msg_link) where alert is enabled."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT chat_id, channel, last_msg_link FROM monitored_channels WHERE alert_enabled = 1"
        ) as cur:
            return await cur.fetchall()


# ─── Stats ────────────────────────────────────────────────────────────────────

async def log_action(chat_id: str, action: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO request_log (chat_id, action) VALUES (?, ?)",
            (chat_id, action),
        )
        await db.commit()


async def get_user_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            row = await cur.fetchone()
    return row[0] if row else 0
