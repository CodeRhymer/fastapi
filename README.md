# Job Scraper API

A FastAPI backend that scrapes company career pages for job titles matching
configured keywords, storing results in SQLite.

---

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload        # dev
uvicorn main:app --host 0.0.0.0 --port 8000   # prod
```

Interactive docs → http://localhost:8000/docs

---

## Endpoints

### Status & Control

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/status` | Current scrape status (idle / running, last run, jobs found) |
| `POST` | `/run` | Start a background scrape job |
| `GET` | `/jobs` | List scraped jobs (filter: `?company_id=&keyword=`) |

#### POST /run — request body (all fields optional)
```json
{
  "company_ids": [1, 2],   // omit to scrape all companies
  "keyword_ids": [1]        // omit to use all keywords
}
```

Returns `202 Accepted` immediately; scraping runs in the background.

---

### Companies

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/companies` | List all companies |
| `POST` | `/companies` | Add a company |
| `DELETE` | `/companies/{id}` | Remove a company |

#### POST /companies
```json
{ "name": "Anthropic", "careers_url": "https://www.anthropic.com/careers" }
```

---

### Keywords

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/keywords` | List all keywords |
| `POST` | `/keywords` | Add a keyword |
| `DELETE` | `/keywords/{id}` | Remove a keyword |

#### POST /keywords
```json
{ "keyword": "engineer" }
```

---

## How Scraping Works

`POST /run` fires an async background task:

1. Fetches each company's `careers_url` with `httpx` (async, concurrent).
2. Parses the page with **BeautifulSoup**, scanning `<a>`, `<h1>`–`<h4>`, `<li>`,
   and elements whose class contains *job / role / position / opening / career*.
3. Performs a **whole-word regex match** against each keyword (case-insensitive).
4. Matched titles are deduplicated (same company + title on the same day is skipped)
   and inserted into the `jobs` table.

---

## Database Schema (SQLite)

```
companies      id, name, careers_url, created_at
keywords       id, keyword, created_at
jobs           id, company_id, company_name, title, keyword_matched, source_url, found_at
scrape_status  id=1, status, started_at, last_run, jobs_found, companies_scraped, error
```

The `jobs.db` file is created automatically on first run.
