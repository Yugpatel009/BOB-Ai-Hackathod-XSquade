from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from app.config import settings
from app.database import Base, engine, SessionLocal
import app.models  # Ensure all models are registered
from app.api import (
    dashboard_router,
    events_router,
    incidents_router,
    investigations_router,
    reports_router,
    chat_router,
    simulation_router
)
from app.seed.seed_data import seed_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("cybersentinel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and seed baseline telemetry
    logger.info("Initializing CyberSentinel database schema...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        logger.info("Checking demo seed data...")
        seed_database(db, force=False)
    finally:
        db.close()
        
    logger.info("CyberSentinel AI SOC Analyst backend ready.")
    yield
    logger.info("CyberSentinel backend shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Security Operations Center (SOC) Assistant for Event Correlation, Threat Investigation, and Risk Scoring",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler to prevent stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error processing {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred in CyberSentinel SOC engine."}
    )

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Health & Root Check
@app.get("/")
def root_status():
    index_file = STATIC_DIR / "index.html"
    if STATIC_DIR.exists() and index_file.exists():
        return FileResponse(str(index_file))
    return {
        "service": "CyberSentinel AI SOC Analyst",
        "status": "OPERATIONAL",
        "version": "1.0.0",
        "ai_status": "READY"
    }


@app.get("/api/health")
def api_health():
    return {
        "status": "healthy",
        "system": "OPERATIONAL",
        "ai_engine": "READY",
        "database": "CONNECTED"
    }


# Include Routers
app.include_router(dashboard_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(incidents_router, prefix="/api")
app.include_router(investigations_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(simulation_router, prefix="/api")

# ── Serve Frontend Static Files (Production / Render) ────────────────
# In production, the built React frontend is placed in backend/static/
# The backend serves it directly — no separate frontend server needed.
if STATIC_DIR.exists() and STATIC_DIR.is_dir():
    # Mount static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static-assets")

    # Serve other static files (favicon, manifest, etc.)
    @app.get("/favicon.ico")
    @app.get("/vite.svg")
    async def serve_static_root_files(request: Request):
        file_path = STATIC_DIR / request.url.path.lstrip("/")
        if file_path.exists():
            return FileResponse(str(file_path))
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    # SPA catch-all: serve index.html for any non-API route
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api"):
            return JSONResponse(status_code=404, content={"detail": "API endpoint not found"})
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return JSONResponse(status_code=404, content={"detail": "Frontend not built"})

    logger.info(f"Serving frontend static files from {STATIC_DIR}")

