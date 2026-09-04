"""Deterministic localhost application shared by API and browser workflow tests."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit


class WorkflowSandboxServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int], token: str) -> None:
        super().__init__(address, WorkflowSandboxHandler)
        self.token = token
        self.orders: dict[str, dict[str, Any]] = {}
        self.sequence = 0
        self.state_lock = threading.Lock()

    def reset(self) -> None:
        with self.state_lock:
            self.orders.clear()
            self.sequence = 0


class WorkflowSandboxHandler(BaseHTTPRequestHandler):
    server: WorkflowSandboxServer

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send(
        self,
        status: HTTPStatus,
        body: bytes,
        content_type: str,
        *,
        location: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, payload: object) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json; charset=utf-8")

    def _error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._json(status, {"error": {"code": code, "message": message}})

    def _authorized(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {self.server.token}"

    def _require_api_auth(self) -> bool:
        if self._authorized():
            return True
        self._error(HTTPStatus.UNAUTHORIZED, "unauthorized", "A valid bearer token is required.")
        return False

    def _read_json(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _order(self, identifier: str) -> dict[str, Any] | None:
        with self.server.state_lock:
            order = self.server.orders.get(identifier)
            return dict(order) if order else None

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlsplit(self.path).path
        if path.startswith("/api/") and not self._require_api_auth():
            return
        if path == "/api/catalog":
            self._json(
                HTTPStatus.OK,
                {"products": [{"id": "SKU-001", "name": "Launch Kit", "available": True}]},
            )
            return
        if path.startswith("/api/orders/"):
            identifier = path.removeprefix("/api/orders/")
            order = self._order(identifier)
            if order is None:
                self._error(HTTPStatus.NOT_FOUND, "order_not_found", "Order was not found.")
            else:
                self._json(HTTPStatus.OK, order)
            return
        if path.startswith("/orders/"):
            identifier = path.removeprefix("/orders/")
            order = self._order(identifier)
            if order is None:
                self._send(HTTPStatus.NOT_FOUND, b"<h1>Order not found</h1>", "text/html")
                return
            body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Order {identifier}</title></head>
<body><main><h1>Order {identifier}</h1><p>Product: {order["product_id"]}</p>
<p>Status: <strong id="order-status">{order["status"]}</strong></p>
<form method="post" action="/orders/{identifier}/approve">
<button type="submit">Approve order</button></form></main></body></html>""".encode()
            self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
            return
        self._send(HTTPStatus.NOT_FOUND, b"<h1>Not found</h1>", "text/html")

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlsplit(self.path).path
        if path.startswith("/api/") and not self._require_api_auth():
            return
        if path == "/api/orders":
            payload = self._read_json()
            if (
                payload is None
                or payload.get("product_id") != "SKU-001"
                or not isinstance(payload.get("quantity"), int)
                or payload["quantity"] < 1
            ):
                self._error(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_order",
                    "A known product and positive integer quantity are required.",
                )
                return
            with self.server.state_lock:
                self.server.sequence += 1
                identifier = f"ORDER-{self.server.sequence:03d}"
                order = {
                    "id": identifier,
                    "product_id": payload["product_id"],
                    "quantity": payload["quantity"],
                    "status": "pending",
                }
                self.server.orders[identifier] = order
            self._json(HTTPStatus.CREATED, order)
            return
        if path.startswith("/api/orders/") and path.endswith("/fulfill"):
            identifier = path.removeprefix("/api/orders/").removesuffix("/fulfill")
            with self.server.state_lock:
                order = self.server.orders.get(identifier)
                if order is not None and order["status"] == "approved":
                    order["status"] = "fulfilled"
                    result = dict(order)
                else:
                    result = None
            if result is None:
                self._error(
                    HTTPStatus.CONFLICT,
                    "order_not_approved",
                    "Only approved orders can be fulfilled.",
                )
            else:
                self._json(HTTPStatus.OK, result)
            return
        if path.startswith("/orders/") and path.endswith("/approve"):
            identifier = path.removeprefix("/orders/").removesuffix("/approve")
            with self.server.state_lock:
                order = self.server.orders.get(identifier)
                if order is not None:
                    order["status"] = "approved"
            if order is None:
                self._send(HTTPStatus.NOT_FOUND, b"<h1>Order not found</h1>", "text/html")
            else:
                self._send(
                    HTTPStatus.SEE_OTHER,
                    b"",
                    "text/plain; charset=utf-8",
                    location=f"/orders/{identifier}",
                )
            return
        self._error(HTTPStatus.NOT_FOUND, "route_not_found", "Route was not found.")
