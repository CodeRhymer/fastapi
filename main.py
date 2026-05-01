from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"greeting": "Hello, World!", "message": "Welcome to FastAPI!"}

@app.get("/jobs")
def get_jobs():
    return []

@app.get("/status")
def get_status():
    return {
        "last_run": None,
        "jobs_found": 0,
        "companies_searched": 0,
        "jobs_updated": 0
    }

@app.post("/run")
def run_scraper():
    return {"status": "started"}

@app.get("/companies")
def get_companies():
    return []

@app.post("/companies")
def add_company(body: dict):
    return {"id": 1, **body}

@app.delete("/companies/{id}")
def delete_company(id: int):
    return {"deleted": id}

@app.get("/keywords")
def get_keywords():
    return []

@app.post("/keywords")
def add_keyword(body: dict):
    return {"id": 1, **body}

@app.delete("/keywords/{id}")
def delete_keyword(id: int):
    return {"deleted": id}
