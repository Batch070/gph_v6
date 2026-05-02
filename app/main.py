"""
GPH Automated Fine Payment System — FastAPI entry point.

Registers all routers, middleware, exception handlers, CORS, and creates
database tables on startup.
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import engine, Base

# Import models so SQLAlchemy sees them before create_all
from app.models import student, faculty, request, fine, attendance, subject, branch  # noqa: F401

from app.routes import auth, student as student_routes, faculty as faculty_routes, hod, admin, incharge, attendance as attendance_routes, webhooks, subjects
from app.middleware.rate_limit import limiter
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.exception_handlers import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)

# Path to the frontend folder
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: create tables if they don't exist
    try:
        print("🚀 [Startup] Initializing database...")
        Base.metadata.create_all(bind=engine)
        
        # Populate initial subjects
        from app.database import SessionLocal
        from app.services import subject_service
        db = SessionLocal()
        try:
            subject_service.populate_initial_subjects(db)
            print("✅ [Startup] Database initialized successfully.")
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️ [Startup Warning] Database initialization failed: {e}")
        # We don't raise here to allow the app to start and show a proper error via API
    
    yield



app = FastAPI(
    title="GPH Automated Fine Payment System",
    description="Backend API for automated fine payment and clearance workflow (IT Branch)",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Security Headers ──────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── Rate Limiter ──────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
if "*" in cors_origins:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,  # Set to False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ───────────────────────────────────────
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(student_routes.router)
app.include_router(faculty_routes.router)
app.include_router(hod.router)
app.include_router(admin.router)
app.include_router(incharge.router)
app.include_router(attendance_routes.router)
app.include_router(webhooks.router)
app.include_router(subjects.router)

# ── Serve Frontend Static Files ──────────────────────────────
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "App is running successfully!"}


from fastapi.responses import HTMLResponse, FileResponse

# ... (middleware and routers)

@app.get("/", tags=["Frontend"])
def serve_login_page():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/admin-dashboard", tags=["Frontend"])
def serve_admin_dashboard():
    return FileResponse(FRONTEND_DIR / "admin-dashboard.html")

@app.get("/hod-dashboard", tags=["Frontend"])
def serve_hod_dashboard():
    return FileResponse(FRONTEND_DIR / "hod-dashboard.html")

@app.get("/incharge-dashboard", tags=["Frontend"])
def serve_incharge_dashboard():
    return FileResponse(FRONTEND_DIR / "incharge-dashboard.html")

@app.get("/student-dashboard", tags=["Frontend"])
def serve_student_dashboard():
    return FileResponse(FRONTEND_DIR / "student-dashboard.html")

@app.get("/pti-dashboard", tags=["Frontend"])
def serve_pti_dashboard():
    return FileResponse(FRONTEND_DIR / "pti-dashboard.html")

@app.get("/librarian-dashboard", tags=["Frontend"])
def serve_librarian_dashboard():
    return FileResponse(FRONTEND_DIR / "librarian-dashboard.html")

@app.get("/ano-dashboard", tags=["Frontend"])
def serve_ano_dashboard():
    return FileResponse(FRONTEND_DIR / "ano-dashboard.html")

@app.get("/canteen-dashboard", tags=["Frontend"])
def serve_canteen_dashboard():
    return FileResponse(FRONTEND_DIR / "canteen-dashboard.html")

@app.get("/hostel-dashboard", tags=["Frontend"])
def serve_hostel_dashboard():
    return FileResponse(FRONTEND_DIR / "hostel-dashboard.html")

