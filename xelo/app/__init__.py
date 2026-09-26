import sqlite3
from pathlib import Path

from flask import Flask, g, render_template
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from werkzeug.exceptions import HTTPException, SecurityError

from .config import configuration, validate_production
from .extensions import csrf, db, limiter, migrate


@event.listens_for(Engine, "connect")
def sqlite_foreign_keys(connection, record):
    if isinstance(connection, sqlite3.Connection):
        connection.execute("PRAGMA foreign_keys=ON")


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(configuration(app.instance_path))
    app.config.update(config or {})
    validate_production(app.config)
    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0, x_port=0)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    from . import models

    migrate.init_app(app, db, render_as_batch=True)
    csrf.init_app(app)
    limiter.init_app(app)

    @app.before_request
    def anonymous_default():
        g.user = None

    @app.get("/")
    def home():
        latest = []
        trending = []
        categories = []
        if g.user and g.user.campus.active:
            from .models import Category, Product
            from .services.security import visible_products

            latest = (
                visible_products()
                .filter(Product.status == "available")
                .order_by(Product.created_at.desc())
                .limit(4)
                .all()
            )
            trending = (
                visible_products()
                .filter(Product.status == "available", Product.views > 0)
                .order_by(Product.views.desc())
                .limit(4)
                .all()
            )
            categories = Category.query.filter_by(active=True).order_by(Category.position).all()
        return render_template("home.html", latest=latest, trending=trending, categories=categories)

    @app.get("/safety")
    def safety():
        return render_template("safety.html")

    @app.get("/health/live")
    @limiter.exempt
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    @limiter.exempt
    def ready():
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ready"}
        except Exception:
            db.session.rollback()
            return {"status": "unavailable"}, 503

    @app.after_request
    def headers(response):
        response.headers.update(
            {
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self' https://wa.me https://api.whatsapp.com https://web.whatsapp.com whatsapp:; frame-ancestors 'none'",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "same-origin",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            }
        )
        if app.config["APP_ENV"] == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if not response.headers.get("Cache-Control"):
            response.headers["Cache-Control"] = "no-store"
        return response

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def form_expired(error):
        return render_template("error.html", code=400,
            message="Please reopen the form and try again. Your session has changed."), 400

    @app.errorhandler(HTTPException)
    def http_error(error):
        if isinstance(error, SecurityError):
            return "Invalid request host.", 400
        return render_template("error.html", code=error.code, message=error.description), error.code

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("error.html", code=500, message="Something went wrong. Please try again."), 500

    from .services.security import load_user

    app.before_request(load_user)
    from .auth import bp as auth_bp
    from .profiles import bp as profiles_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profiles_bp)
    from .marketplace import bp as market_bp

    app.register_blueprint(market_bp)

    @app.context_processor
    def template_helpers():
        from urllib.parse import urlencode

        from flask import request

        def page_url(number):
            args = request.args.to_dict()
            args["page"] = number
            return request.path + "?" + urlencode(args)

        return {"page_url": page_url}

    from .messaging import bp as messages_bp
    from .notifications import bp as notifications_bp
    from .wishlist import bp as wishlist_bp

    for bp in (wishlist_bp, messages_bp, notifications_bp):
        app.register_blueprint(bp)
    from .admin import bp as admin_bp
    from .analytics import bp as dashboard_bp
    from .reports import bp as reports_bp
    from .reviews import bp as reviews_bp

    for bp in (reviews_bp, reports_bp, dashboard_bp, admin_bp):
        app.register_blueprint(bp)
    from .cli import register

    register(app)
    return app
