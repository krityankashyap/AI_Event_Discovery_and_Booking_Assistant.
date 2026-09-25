import logging
import httpx
from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend import config

logging.basicConfig(
  level=config.LOG_LEVEL,
  format= "%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

logger= logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):

  config.validate_config() # Validate configuration on startup

  app.state.http_client = httpx.AsyncClient(timeout=10.0) # Initialize HTTP client for external API calls
  logger.info("Startup complete (provider=%s model= %s)", # Log the LLM provider and model being used
              config.LLM_PROVIDER, config.LLM_MODEL)
  
  yield
  # Cleanup resources on shutdown
  await app.state.http_client.aclose()
  logger.info("shutdown complete")



