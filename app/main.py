from fastapi import FastAPI
from app.api import routes_applications, routes_documents, routes_jobs, routes_profiles

app = FastAPI(title="Job Application Engine", version="0.1.0", description="Evidence-first local job application assistant")
app.include_router(routes_profiles.router, prefix="/api")
app.include_router(routes_jobs.router, prefix="/api")
app.include_router(routes_applications.router, prefix="/api")
app.include_router(routes_documents.router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok"}
