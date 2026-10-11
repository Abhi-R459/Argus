"""Bound request bodies and log requests without query strings or credentials."""

import logging
import time
import uuid

from starlette.responses import JSONResponse

logger = logging.getLogger("uvicorn.error.argus.requests")


class RequestSafetyMiddleware:
    def __init__(self, app, max_body_bytes: int):
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request_id = uuid.uuid4().hex
        start = time.monotonic()
        status = 500
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = -1
        if length < 0 or length > self.max_body_bytes:
            response = JSONResponse({"detail": "Request body is too large or has an invalid length."}, status_code=413)
            response.headers["X-Request-ID"] = request_id
            return await response(scope, receive, send)

        # Buffer only a bounded body, including requests sent without a length.
        messages = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_body_bytes:
                response = JSONResponse({"detail": "Request body is too large."}, status_code=413)
                response.headers["X-Request-ID"] = request_id
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break

        async def bounded_receive():
            if messages:
                return messages.pop(0)
            return await receive()

        async def tracked_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = list(message["headers"]) + [(b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, bounded_receive, tracked_send)
        finally:
            logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
                        request_id, scope["method"], scope["path"], status,
                        (time.monotonic() - start) * 1000)
