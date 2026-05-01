from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sqlite3, os, requests
from bs4 import BeautifulSoup
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = "jobs.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT, title TEXT, keywords_matched TEXT,
        url TEXT UNIQUE, found_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT UNIQUE
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT, word TEXT UNIQUE
    )""")
    conn.commit(); conn.close()

init_db()

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/jobs")
def get_jobs():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT company, title, keywords_matched, url, found_at FROM jobs ORDER BY found_at DESC")
    rows = c.fetchall(); conn.close()
    return [{"company": r[0], "title": r[1], "keywords_matched": r[2], "url": r[3], "found_at": r[4]} for r in rows]

@app.get("/status")
def get_status():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    jobs_found = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    companies = c.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    conn.close()
    return {"jobs_found": jobs_found, "companies_searched": companies, "jobs_updated": jobs_found, "last_run": datetime.now().isoformat()}

@app.post("/run")
def run_scraper(payload: dict = {}):
    companies = payload.get("companies", [])
    keywords = payload.get("keywords", [])
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    new_jobs = 0
    for company_url in companies:
        try:
            res = requests.get(company_url, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            links = soup.find_all("a", href=True)
            company_name = company_url.split("//")[-1].split("/")[0].replace("www.", "")
            for link in links:
                title = link.get_text(strip=True)
                href = link["href"]
                matched = [kw for kw in keywords if kw.lower() in title.lower()]
                if matched:
                    full_url = href if href.startswith("http") else company_url.rstrip("/") + "/" + href.lstrip("/")
                    try:
                        c.execute("INSERT INTO jobs (company, title, keywords_matched, url, found_at) VALUES (?,?,?,?,?)",
                            (company_name, title, ", ".join(matched), full_url, datetime.now().isoformat()))
                        new_jobs += 1
                    except: pass
        except Exception as e:
            print(f"Error scraping {company_url}: {e}")
    conn.commit(); conn.close()
    return {"new_jobs": new_jobs}

@app.get("/companies")
def get_companies():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id, url FROM companies").fetchall(); conn.close()
    return [{"id": r[0], "url": r[1]} for r in rows]

@app.post("/companies")
def add_company(payload: dict):
    conn = sqlite3.connect(DB)
    try:
        conn.execute("INSERT INTO companies (url) VALUES (?)", (payload["url"],))
        conn.commit()
    except: pass
    conn.close(); return {"ok": True}

@app.delete("/companies/{id}")
def delete_company(id: int):
    conn = sqlite3.connect(DB); conn.execute("DELETE FROM companies WHERE id=?", (id,)); conn.commit(); conn.close()
    return {"ok": True}

@app.get("/keywords")
def get_keywords():
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT id, word FROM keywords").fetchall(); conn.close()
    return [{"id": r[0], "word": r[1]} for r in rows]

@app.post("/keywords")
def add_keyword(payload: dict):
    conn = sqlite3.connect(DB)
    try:
        conn.execute("INSERT INTO keywords (word) VALUES (?)", (payload["word"],))
        conn.commit()
    except: pass
    conn.close(); return {"ok": True}

@app.delete("/keywords/{id}")
def delete_keyword(id: int):
    conn = sqlite3.connect(DB); conn.execute("DELETE FROM keywords WHERE id=?", (id,)); conn.commit(); conn.close()
    return {"ok": True}
