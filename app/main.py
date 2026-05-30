from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.db.database import Database
from app.web import router as web_router


settings = get_settings()
Database(settings.require_database_url()).init()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.require_session_secret_key(),
    same_site="lax",
    https_only=settings.session_https_only,
    max_age=60 * 60 * 24 * 7,
)
app.add_exception_handler(AppError, app_error_handler)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(api_router, prefix="/api")
app.include_router(web_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.app_env,
    }
