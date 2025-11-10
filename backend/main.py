"""
FastAPI backend for CulturaDB web app
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os
from dotenv import load_dotenv

from api.routes import movies, pipeline

# Load environment variables
load_dotenv()

app = FastAPI(
    title="CulturaDB API",
    description="API for CulturaDB movie data pipeline",
    version="1.0.0"
)

# CORS configuration for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port, Next.js default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(movies.router, prefix="/api/movies", tags=["movies"])
app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "CulturaDB API is running", "version": "1.0.0"}


@app.get("/api/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "CulturaDB API",
        "version": "1.0.0"
    }


@app.get("/api/test")
async def test():
    """Simple test endpoint"""
    return {"message": "Backend is working!", "test": True}

