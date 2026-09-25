import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend import config
from backend.errors import AppError

logging.basicConfig(
    level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

    # Validate configuration on startup (fail-fast if required keys are missing)
    config.validate_config()

    # Initialize the shared HTTP client for external API calls
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    logger.info(
        "Startup complete (provider=%s model=%s)",
        config.LLM_PROVIDER,
        config.LLM_MODEL,
    )

    yield
    # Cleanup resources on shutdown
    await app.state.http_client.aclose()
    logger.info("shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(title=config.APP_NAME, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app


app = create_app()


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception):
    logger.exception("Unhandled error")  # logs full traceback server-side
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": "Something went wrong."}},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": config.LLM_PROVIDER, "llm_model": config.LLM_MODEL}
