"""ASGI body bound and security headers, independent of hosting provider."""


class SecurityMiddleware:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > self.settings.MAX_CONTENT_LENGTH:
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                        }
                    )
                    await send(
                        {"type": "http.response.body", "body": b"Upload is too large. Use smaller photos."}
                    )
                    return
                if not message.get("more_body", False):
                    break
            delivered = False
            original_receive = receive

            async def body_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await original_receive()

            receive = body_receive

        async def safe_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                additions = {
                    "content-security-policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self' https://wa.me https://api.whatsapp.com https://web.whatsapp.com whatsapp:; frame-ancestors 'none'",
                    "x-content-type-options": "nosniff",
                    "x-frame-options": "DENY",
                    "referrer-policy": "same-origin",
                    "permissions-policy": "camera=(), microphone=(), geolocation=()",
                }
                if self.settings.APP_ENV == "production":
                    additions["strict-transport-security"] = "max-age=31536000"
                if not any(k.lower() == b"cache-control" for k, v in headers):
                    additions["cache-control"] = "no-store"
                headers.extend((k.encode(), v.encode()) for k, v in additions.items())
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, safe_send)
