"""Synchronous SQLAlchemy persistence and request-scoped dependencies."""

from dataclasses import dataclass
from math import ceil
from pathlib import Path

from fastapi import HTTPException, Request
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session as SASession
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


@dataclass
class Pagination:
    items: list
    page: int
    per_page: int
    total: int

    @property
    def pages(self):
        return ceil(self.total / self.per_page)

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1

    @property
    def next_num(self):
        return self.page + 1

    def iter_pages(self, left_edge=2, left_current=2, right_current=4, right_edge=2):
        last = 0
        for number in range(1, self.pages + 1):
            if (
                number <= left_edge
                or self.page - left_current <= number <= self.page + right_current
                or number > self.pages - right_edge
            ):
                if last + 1 != number:
                    yield None
                yield number
                last = number


class Query(SAQuery):
    def first_or_404(self, description=None):
        item = self.first()
        if item is None:
            raise HTTPException(404, description or "Not found")
        return item

    def get_or_404(self, ident, description=None):
        item = self.get(ident)
        if item is None:
            raise HTTPException(404, description or "Not found")
        return item

    def paginate(self, *, page=1, per_page=20, max_per_page=None, error_out=True, count=True):
        page, per_page = int(page), int(per_page)
        if page < 1 or per_page < 1:
            if error_out:
                raise HTTPException(404, "Page not found")
            page, per_page = max(1, page), max(1, per_page)
        if max_per_page:
            per_page = min(per_page, max_per_page)
        total = self.order_by(None).count() if count else 0
        items = self.limit(per_page).offset((page - 1) * per_page).all()
        if not items and page != 1 and error_out:
            raise HTTPException(404, "Page not found")
        return Pagination(items, page, per_page, total)


class Session(SASession):
    def get_or_404(self, entity, ident, description=None):
        item = self.get(entity, ident)
        if item is None:
            raise HTTPException(404, description or "Not found")
        return item


def make_engine(settings):
    options = {"pool_pre_ping": True}
    if settings.DATABASE_URL.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        if settings.DATABASE_URL in ("sqlite://", "sqlite:///:memory:"):
            options["poolclass"] = StaticPool
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    if settings.DATABASE_URL.startswith("postgresql"):
        options["connect_args"] = {"connect_timeout": 5}
    engine = create_engine(settings.DATABASE_URL, **options)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine):
    return sessionmaker(bind=engine, class_=Session, query_cls=Query, expire_on_commit=False)


def get_db(request: Request):
    existing = getattr(request.state, "db", None)
    if existing is not None:
        yield existing
        return
    with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
