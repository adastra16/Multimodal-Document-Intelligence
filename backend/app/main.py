"""FastAPI application factory. Business logic does not live here."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import TraceIdMiddleware

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved)

    app = FastAPI(
        title="Multimodal Document Intelligence",
        version=__version__,
        description="Question answering over visually rich PDFs with grounded citations.",
    )
    app.state.settings = resolved

    origins = resolved.cors_origin_list
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)

    logger.info("app_created", env=resolved.app_env)
    return app


app = create_app()
