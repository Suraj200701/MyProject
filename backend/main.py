"""FastAPI application entrypoint.

Run locally with:
    uvicorn main:app --reload --port 8000

Production:
    gunicorn main:app -c docker/gunicorn.conf.py
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.v1.router import api_router
from config.logging_config import configure_logging
from config.settings import settings
from database.session import engine

configure_logging("DEBUG" if settings.DEBUG else "INFO")
from middleware.rate_limit import RateLimitMiddleware
from middleware.request_logging import RequestLoggingMiddleware
from redis_cache.client import close_redis_pool, get_redis_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: warm the Redis pool so the first request isn't slow.
    get_redis_pool()
    yield
    # Shutdown: release pooled connections cleanly.
    await close_redis_pool()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "LeadMaster AI backend API. Interactive docs are available at /docs "
            "(Swagger UI) and /redoc (ReDoc)."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    register_exception_handlers(app)
    return app


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "message": exc.detail, "errors": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        # exc.errors() can include a raw Python exception object under
        # error["ctx"]["error"] when a Pydantic field_validator raises a
        # plain ValueError — that's not JSON-serializable, so stringify it
        # before it hits the encoder.
        errors = []
        for error in exc.errors():
            ctx = error.get("ctx")
            if isinstance(ctx, dict) and isinstance(ctx.get("error"), Exception):
                error = {**error, "ctx": {**ctx, "error": str(ctx["error"])}}
            errors.append(error)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "message": "Validation error",
                "errors": jsonable_encoder(errors),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Internal server error", "errors": None},
        )


app = create_app()
