"""Real ASGI test client with multipart helpers and fixture identity-map refresh."""

from fastapi.testclient import TestClient


class Client(TestClient):
    def __init__(self, app, **kwargs):
        kwargs.setdefault("follow_redirects", False)
        super().__init__(app, **kwargs)

    def request(self, *args, **kwargs):
        try:
            return super().request(*args, **kwargs)
        finally:
            session = getattr(self.app.state, "test_session", None)
            if session is not None:
                session.expire_all()

    def post(self, url, *, content_type=None, **kwargs):
        if content_type == "multipart/form-data":
            fields, files = {}, []
            for key, value in kwargs.pop("data", {}).items():
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if isinstance(item, tuple) and hasattr(item[0], "read"):
                        files.append((key, (item[1], item[0])))
                    else:
                        fields[key] = item
            kwargs.update(data=fields, files=files)
        return super().post(url, **kwargs)
