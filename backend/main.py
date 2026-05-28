"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.config import get_settings
from backend.database.db import init_db
from backend.utils.logger import logger

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    await init_db()
    logger.info("Traffic AI backend started")
    yield
    logger.info("Traffic AI backend shutdown")


app = FastAPI(
    title="Smart Traffic Monitoring API",
    description="AI-powered traffic monitoring for Bengaluru - Flipkart Gridlock Hackathon 2.0",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    return {
        "service": "Smart Traffic Monitoring & Mobility Intelligence",
        "version": "1.0.0",
        "docs": "/docs",
        "api": settings.API_PREFIX,
    }
