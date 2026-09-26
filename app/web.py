"""Server-rendered responses using Starlette and Jinja2."""

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

from fastapi import HTTPException
from fastapi.templating import Jinja2Templates
from starlette.responses import FileResponse, JSONResponse, RedirectResponse, Response

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def abort(code, message=None):
    raise HTTPException(
        code,
        message
        or {
            400: "Please check your entries.",
            403: "You cannot access this page.",
            404: "This page could not be found.",
            429: "Too many requests. Please try again shortly.",
        }.get(code, "Request could not be completed."),
    )


def redirect(url, code=302):
    return RedirectResponse(url, status_code=code)


def send_file(path, mimetype=None):
    return FileResponse(path, media_type=mimetype)


def flash(request, message, category="info"):
    messages = request.session.setdefault("flashes", [])
    messages.append((category, message))
    request.session["flashes"] = messages[-10:]


def render(request, template, **context):
    from .security import generate_csrf

    def url_for(name, **values):
        if name == "static":
            return str(request.url_for("static", path=values.pop("filename", values.pop("path", ""))))
        if name == "market.browse":
            return "/market?" + urlencode(values)
        if name == "auth.signup":
            return "/auth/signup"
        return str(request.url_for(name, **values))

    def page_url(number):
        args = dict(request.query_params)
        args["page"] = number
        return request.url.path + "?" + urlencode(args)

    context.update(
        g=SimpleNamespace(
            user=getattr(request.state, "user", None),
            login_session=getattr(request.state, "login_session", None),
        ),
        csrf_token=lambda: generate_csrf(request),
        url_for=url_for,
        page_url=page_url,
        get_flashed_messages=lambda **kwargs: request.session.pop("flashes", []),
    )
    return templates.TemplateResponse(request=request, name=template, context=context)


def respond(body, status=200, headers=None):
    if isinstance(body, Response):
        body.status_code = status
        body.headers.update(headers or {})
        return body
    return JSONResponse(body, status_code=status, headers=headers)
