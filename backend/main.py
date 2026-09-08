"""FastAPI application entry point."""
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

CATALOG_PATH = Path(__file__).parent / "catalog" / "chart_catalog.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: pre-load the chart catalog into memory."""
    logger.info("🚀 Chart Suggest API starting...")

    # Ensure catalog exists — build it if not
    if not CATALOG_PATH.exists():
        logger.warning("chart_catalog.json not found. Building from Excel workbook...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/build_catalog.py"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error(f"Catalog build failed: {result.stderr}")
        else:
            logger.info(result.stdout.strip())

    # Pre-warm catalog
    from services.chart_matcher import _load_catalog
    catalog = _load_catalog()
    logger.info(f"✅ Chart catalog loaded: {len(catalog)} charts")

    yield
    logger.info("Chart Suggest API shutting down.")


app = FastAPI(
    title="Chart Suggest API",
    description="Intelligent CSV-to-Chart recommendation engine powered by the Apache ECharts catalog.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the single application API endpoint: POST /recommend-charts
from api.routes.recommend import router as recommend_router

app.include_router(recommend_router, tags=["Recommendation"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Lightweight health check endpoint for frontend connection verification."""
    return {"status": "ok", "service": "Chart Suggest API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

