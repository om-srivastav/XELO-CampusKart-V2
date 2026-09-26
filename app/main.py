import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import PlainTextResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from .config import Settings
from .database import Session, get_db, make_engine, make_session_factory
from .dependencies import prepare_request
from .middleware.http import SecurityMiddleware
from .middleware.rate_limit import configure
from .schemas.responses import HealthStatus
from .web import render

ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


def build_app(settings=None):
    settings = settings or Settings()
    application = FastAPI(title="XELO CampusKart", version="2.1.0", docs_url=None, redoc_url=None)
    application.state.settings = settings
    application.state.engine = make_engine(settings)
    application.state.session_factory = make_session_factory(application.state.engine)
    application.state.rate_storage, application.state.rate_limiter = configure(settings)
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.SECRET_KEY,
        session_cookie="xelo_session",
        same_site=settings.SESSION_COOKIE_SAMESITE,
        https_only=settings.SESSION_COOKIE_SECURE,
        max_age=settings.SESSION_HOURS * 3600,
    )
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
    application.add_middleware(SecurityMiddleware, settings=settings)
    application.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

    @application.exception_handler(HTTPException)
    async def http_error(request, error):
        if error.status_code in (301, 302, 303, 307, 308) and error.headers and error.headers.get("Location"):
            return RedirectResponse(error.headers["Location"], status_code=error.status_code)
        if "session" not in request.scope:
            return PlainTextResponse("Request could not be completed.", status_code=error.status_code)
        request.state.user = None
        result = render(request, "error.html", code=error.status_code, message=error.detail)
        result.status_code = error.status_code
        if error.headers:
            result.headers.update(error.headers)
        return result

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return await http_error(
            request, HTTPException(400, "Please check the supplied values and try again.")
        )

    @application.exception_handler(Exception)
    async def server_error(request, error):
        logger.error("Unhandled request error (%s)", type(error).__name__)
        return await http_error(request, HTTPException(500, "Something went wrong. Please try again."))

    @application.get("/", dependencies=[Depends(prepare_request)], response_model=None)
    def home(request: Request, db: Session = Depends(get_db)):
        from .models import Category, Product
        from .services.security import visible_products

        latest, trending, categories = [], [], []
        if request.state.user and request.state.user.campus.active:
            latest = (
                visible_products(request, db)
                .filter(Product.status == "available")
                .order_by(Product.created_at.desc())
                .limit(4)
                .all()
            )
            trending = (
                visible_products(request, db)
                .filter(Product.status == "available", Product.views > 0)
                .order_by(Product.views.desc())
                .limit(4)
                .all()
            )
            categories = db.query(Category).filter_by(active=True).order_by(Category.position).all()
        return render(request, "home.html", latest=latest, trending=trending, categories=categories)

    @application.get("/safety", dependencies=[Depends(prepare_request)], response_model=None)
    def safety(request: Request):
        return render(request, "safety.html")

    @application.get("/health/live", response_model=HealthStatus)
    def live():
        return {"status": "ok"}

    @application.get("/health/ready", response_model=HealthStatus)
    def ready(db: Session = Depends(get_db)):
        from starlette.responses import JSONResponse

        try:
            db.execute(text("SELECT 1"))
            if settings.RATELIMIT_ENABLED and settings.APP_ENV == "production":
                if not application.state.rate_storage.check():
                    raise RuntimeError("Unavailable")
            return {"status": "ready"}
        except Exception:
            db.rollback()
            return JSONResponse({"status": "unavailable"}, status_code=503)

    from .routers import (
        admin,
        analytics,
        auth,
        marketplace,
        messaging,
        notifications,
        profiles,
        reports,
        reviews,
        wishlist,
    )

    for module in (
        auth,
        marketplace,
        profiles,
        messaging,
        notifications,
        wishlist,
        reviews,
        reports,
        analytics,
        admin,
    ):
        module.router.routes.sort(key=lambda route: route.path.count("{"))
        application.include_router(module.router)
    return application


app = build_app()
