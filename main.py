from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional
import httpx
from bs4 import BeautifulSoup
import asyncio
import re
from datetime import datetime

from database import (
    init_db, get_db,
    add_company, get_companies, delete_company,
    add_keyword, get_keywords, delete_keyword,
    add_job, get_jobs,
    update_scrape_status, get_scrape_status
)

app = FastAPI(title="Job Scraper API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    init_db()

# ── Models ──────────────────────────────────────────────────────────────────

class CompanyCreate(BaseModel):
    name: str
    careers_url: str

class KeywordCreate(BaseModel):
    keyword: str

class RunRequest(BaseModel):
    company_ids: Optional[list[int]] = None   # None = all companies
    keyword_ids: Optional[list[int]] = None   # None = all keywords

# ── Companies ───────────────────────────────────────────────────────────────

@app.get("/companies")
def list_companies():
    return get_companies()

@app.post("/companies", status_code=201)
def create_company(body: CompanyCreate):
    company_id = add_company(body.name, body.careers_url)
    return {"id": company_id, "name": body.name, "careers_url": body.careers_url}

@app.delete("/companies/{company_id}", status_code=204)
def remove_company(company_id: int):
    if not delete_company(company_id):
        raise HTTPException(status_code=404, detail="Company not found")

# ── Keywords ─────────────────────────────────────────────────────────────────

@app.get("/keywords")
def list_keywords():
    return get_keywords()

@app.post("/keywords", status_code=201)
def create_keyword(body: KeywordCreate):
    keyword_id = add_keyword(body.keyword)
    return {"id": keyword_id, "keyword": body.keyword}

@app.delete("/keywords/{keyword_id}", status_code=204)
def remove_keyword(keyword_id: int):
    if not delete_keyword(keyword_id):
        raise HTTPException(status_code=404, detail="Keyword not found")

# ── Jobs ─────────────────────────────────────────────────────────────────────

@app.get("/jobs")
def list_jobs(company_id: Optional[int] = None, keyword: Optional[str] = None):
    return get_jobs(company_id=company_id, keyword=keyword)

# ── Status ───────────────────────────────────────────────────────────────────

@app.get("/status")
def scrape_status():
    return get_scrape_status()

# ── Run (scrape) ──────────────────────────────────────────────────────────────

async def scrape_page(client: httpx.AsyncClient, url: str, keywords: list[str], company: dict) -> list[dict]:
    """Fetch a career page and extract job titles matching any keyword."""
    found = []
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Collect candidate text nodes (links, headings, list items, common job divs)
        candidates = set()
        selectors = [
            "a", "h1", "h2", "h3", "h4", "li",
            "[class*='job']", "[class*='role']", "[class*='position']",
            "[class*='opening']", "[class*='career']",
        ]
        for sel in selectors:
            for el in soup.select(sel):
                text = el.get_text(separator=" ", strip=True)
                if 3 < len(text) < 200:          # ignore tiny / huge strings
                    candidates.add(text)

        kw_lower = [k.lower() for k in keywords]
        for text in candidates:
            text_lower = text.lower()
            for kw, kw_orig in zip(kw_lower, keywords):
                # whole-word match so "engineer" doesn't hit "engineering" unexpectedly
                if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                    found.append({
                        "company_id": company["id"],
                        "company_name": company["name"],
                        "title": text,
                        "keyword_matched": kw_orig,
                        "source_url": url,
                    })
                    break   # one match per text node is enough

    except Exception as exc:
        print(f"[scraper] ERROR {url}: {exc}")
    return found


async def run_scrape(company_ids: Optional[list[int]], keyword_ids: Optional[list[int]]):
    update_scrape_status("running", started_at=datetime.utcnow().isoformat())
    try:
        companies = get_companies()
        keywords  = get_keywords()

        if company_ids:
            companies = [c for c in companies if c["id"] in company_ids]
        if keyword_ids:
            keywords  = [k for k in keywords  if k["id"] in keyword_ids]

        if not companies:
            update_scrape_status("idle", error="No companies to scrape")
            return
        if not keywords:
            update_scrape_status("idle", error="No keywords configured")
            return

        kw_strings = [k["keyword"] for k in keywords]
        total_found = 0

        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)
        async with httpx.AsyncClient(limits=limits, headers={
            "User-Agent": "Mozilla/5.0 (compatible; JobScraper/1.0)"
        }) as client:
            tasks = [scrape_page(client, c["careers_url"], kw_strings, c) for c in companies]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for company_results in results:
            if isinstance(company_results, list):
                for job in company_results:
                    add_job(job)
                    total_found += 1

        update_scrape_status(
            "idle",
            last_run=datetime.utcnow().isoformat(),
            jobs_found=total_found,
            companies_scraped=len(companies),
        )
    except Exception as exc:
        update_scrape_status("idle", error=str(exc))


@app.post("/run", status_code=202)
async def run_scraper(body: RunRequest, background_tasks: BackgroundTasks):
    status = get_scrape_status()
    if status.get("status") == "running":
        raise HTTPException(status_code=409, detail="A scrape is already running")
    background_tasks.add_task(run_scrape, body.company_ids, body.keyword_ids)
    return {"message": "Scrape started", "status": "running"}
