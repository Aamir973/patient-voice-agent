from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.database import engine
from app.routers import patients, vapi
from app.logging_config import api_logger  # noqa: F401 - side effect: configures logging

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Patient Registration API",
    description="REST API + Vapi voice-agent webhooks for the patient registration system.",
    version="1.0.0",
)

# Wide-open CORS since the dashboard is a static page that may be served from a
# different origin/port during local dev. Tighten this for a real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router)
app.include_router(vapi.router)

app.mount("/dashboard", StaticFiles(directory="static", html=True), name="dashboard")


@app.get("/")
def root():
    return {
        "service": "patient-registration-api",
        "status": "ok",
        "docs": "/docs",
        "dashboard": "/dashboard",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
