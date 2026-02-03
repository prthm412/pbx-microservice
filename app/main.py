"""
PBX Microservice - Main Application
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import init_db
from app.api.routes import calls
from app.config import settings
from app.services.call_processor import call_processor
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler - runs on startup and shutdown
    """
    # Startup
    logger.info("Starting PBX Microservice...")
    await init_db()
    logger.info("✅ Database initialized")
    
    # Start background call processor
    processor_task = asyncio.create_task(call_processor.start())
    logger.info("✅ Background call processor started")
    
    logger.info(f"🚀 Server ready at http://{settings.APP_HOST}:{settings.APP_PORT}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down PBX Microservice...")
    call_processor.stop()
    processor_task.cancel()
    try:
        await processor_task
    except asyncio.CancelledError:
        pass
    logger.info("✅ Background processor stopped")


# Create FastAPI application
app = FastAPI(
    title="PBX Microservice",
    description="High-performance microservice for PBX call streaming with AI processing",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(calls.router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "PBX Microservice",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "processor": call_processor.get_stats()
    }


@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    return call_processor.get_stats()