from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_engines, dispose_engines
from .routers import health, auth, employees


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async lifespan handler: initialize DB engines on startup, dispose on shutdown."""
    await init_engines()
    yield
    await dispose_engines()


app = FastAPI(
    title="Argus API",
    description="Tamper-evident, self-verifying audit trail engine for PostgreSQL",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server and common deployment origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers under /api prefix
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
