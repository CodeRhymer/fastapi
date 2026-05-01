import sqlite3
import json
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "jobs.db"

# ── Connection helper ────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

# ── Schema ───────────────────────────────────────────────────────────────────

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS companies (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                careers_url TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS keywords (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword    TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS jobs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id      INTEGER REFERENCES companies(id) ON DELETE CASCADE,
                company_name    TEXT,
                title           TEXT NOT NULL,
                keyword_matched TEXT,
                source_url      TEXT,
                found_at        TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS scrape_status (
                id                 INTEGER PRIMARY KEY CHECK (id = 1),
                status             TEXT DEFAULT 'idle',
                started_at         TEXT,
                last_run           TEXT,
                jobs_found         INTEGER DEFAULT 0,
                companies_scraped  INTEGER DEFAULT 0,
                error              TEXT
            );

            INSERT OR IGNORE INTO scrape_status (id, status) VALUES (1, 'idle');
        """)

# ── Companies ────────────────────────────────────────────────────────────────

def add_company(name: str, careers_url: str) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO companies (name, careers_url) VALUES (?, ?)",
            (name, careers_url)
        )
        return cur.lastrowid

def get_companies() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM companies ORDER BY name").fetchall()
        return [dict(r) for r in rows]

def delete_company(company_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
        return cur.rowcount > 0

# ── Keywords ─────────────────────────────────────────────────────────────────

def add_keyword(keyword: str) -> int:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO keywords (keyword) VALUES (?)", (keyword.strip(),)
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = conn.execute("SELECT id FROM keywords WHERE keyword = ?", (keyword.strip(),)).fetchone()
        return row["id"]

def get_keywords() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM keywords ORDER BY keyword").fetchall()
        return [dict(r) for r in rows]

def delete_keyword(keyword_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
        return cur.rowcount > 0

# ── Jobs ──────────────────────────────────────────────────────────────────────

def add_job(job: dict):
    with get_db() as conn:
        # Deduplicate: skip if same company + title already recorded today
        exists = conn.execute("""
            SELECT 1 FROM jobs
            WHERE company_id = ? AND title = ? AND date(found_at) = date('now')
        """, (job["company_id"], job["title"])).fetchone()
        if exists:
            return
        conn.execute("""
            INSERT INTO jobs (company_id, company_name, title, keyword_matched, source_url)
            VALUES (:company_id, :company_name, :title, :keyword_matched, :source_url)
        """, job)

def get_jobs(company_id: Optional[int] = None, keyword: Optional[str] = None) -> list[dict]:
    query = "SELECT * FROM jobs WHERE 1=1"
    params: list = []
    if company_id is not None:
        query += " AND company_id = ?"
        params.append(company_id)
    if keyword:
        query += " AND keyword_matched LIKE ?"
        params.append(f"%{keyword}%")
    query += " ORDER BY found_at DESC"
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

# ── Scrape status ─────────────────────────────────────────────────────────────

def get_scrape_status() -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM scrape_status WHERE id = 1").fetchone()
        return dict(row) if row else {}

def update_scrape_status(status: str, **kwargs):
    fields = {"status": status}
    fields.update(kwargs)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values())
    with get_db() as conn:
        conn.execute(
            f"UPDATE scrape_status SET {set_clause} WHERE id = 1",
            values
        )
