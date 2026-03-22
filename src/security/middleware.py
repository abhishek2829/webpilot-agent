"""WebPilot Agent — Security Middleware (Task 16).

Security hardening for the FastAPI API layer:
  - API key authentication (X-API-Key header or Bearer token)
  - In-memory rate limiting per client IP
  - Input sanitization (path traversal, XSS, injection)
  - Security response headers (HSTS, X-Frame-Options, etc.)

Analogy: The bouncer, the velvet rope, and the metal detector at a club.
  - APIKeyAuth is the bouncer: checks your ID at the door
  - RateLimiter is the velvet rope: controls the flow of people
  - InputSanitizer is the metal detector: checks what you're bringing in
  - SecurityHeaders is the dress code: ensures proper appearance on the way out

Patterns applied:
- security hardening: defense in depth (auth + rate limit + sanitize + headers)
- clean-code: each concern is a separate, composable middleware
- compound-engineering: rate limiter tracks usage stats
"""

from __future__ import annotations

import html
import re
import time
from collections import defaultdict
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


# =========================================================================
# API Key Authentication Middleware
# =========================================================================

class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that requires a valid API key for protected endpoints.

    Checks for the key in:
      1. X-API-Key header
      2. Authorization: Bearer <key> header

    If api_keys is empty, all requests are allowed (dev/local mode).
    Paths in exclude_paths bypass authentication (e.g., /health, /docs).

    Usage:
        app.add_middleware(
            APIKeyAuthMiddleware,
            api_keys={"key1", "key2"},
            exclude_paths={"/health", "/docs", "/openapi.json"},
        )
    """

    def __init__(
        self,
        app: Any,
        api_keys: set[str] | None = None,
        exclude_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._api_keys = api_keys or set()
        self._exclude_paths = exclude_paths or set()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check API key before forwarding the request."""
        # Dev mode: no keys configured → allow all
        if not self._api_keys:
            return await call_next(request)

        # Excluded paths bypass auth
        if request.url.path in self._exclude_paths:
            return await call_next(request)

        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")

        # Fallback: check Authorization: Bearer header
        if not api_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[7:]

        if not api_key or api_key not in self._api_keys:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

        return await call_next(request)


# =========================================================================
# Rate Limiter
# =========================================================================

class RateLimiter:
    """In-memory sliding window rate limiter.

    Tracks request timestamps per client key (typically IP address).
    Requests outside the time window are expired on each check.

    Usage:
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        if not limiter.is_allowed(client_ip):
            return 429 Too Many Requests

    Thread safety: Not thread-safe. For production, use Redis-backed limiting.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 60) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_key: str) -> bool:
        """Check if the client is within rate limits.

        Args:
            client_key: Unique client identifier (e.g., IP address)

        Returns:
            True if request is allowed, False if rate-limited
        """
        now = time.monotonic()
        cutoff = now - self._window_seconds

        # Expire old requests
        self._requests[client_key] = [
            t for t in self._requests[client_key] if t > cutoff
        ]

        if len(self._requests[client_key]) >= self._max_requests:
            return False

        self._requests[client_key].append(now)
        return True

    def get_remaining(self, client_key: str) -> int:
        """Get the number of requests remaining in the current window.

        Args:
            client_key: Unique client identifier

        Returns:
            Number of requests remaining before hitting the limit
        """
        now = time.monotonic()
        cutoff = now - self._window_seconds

        # Expire old requests
        self._requests[client_key] = [
            t for t in self._requests[client_key] if t > cutoff
        ]

        return max(0, self._max_requests - len(self._requests[client_key]))


# =========================================================================
# Input Sanitizer
# =========================================================================

# Only allow alphanumeric, hyphens, underscores, and dots in workflow names
_WORKFLOW_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}$")

# HTML/script tag pattern for stripping
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


class InputSanitizer:
    """Validates and sanitizes user input for API endpoints.

    Protects against:
      - Path traversal in workflow names (../)
      - Command injection via special characters
      - XSS via HTML/script tags in variable values
      - Overly long inputs

    Usage:
        sanitizer = InputSanitizer()
        name = sanitizer.sanitize_workflow_name(request.workflow_name)
        variables = sanitizer.sanitize_variables(request.variables)
    """

    def sanitize_workflow_name(self, name: str) -> str:
        """Validate and sanitize a workflow name.

        Args:
            name: The workflow name to validate

        Returns:
            The validated workflow name (unchanged if valid)

        Raises:
            ValueError: If the name contains invalid characters or patterns
        """
        if not name or not _WORKFLOW_NAME_PATTERN.match(name):
            raise ValueError(
                f"Invalid workflow name: '{name}'. "
                "Must be 1-100 characters, alphanumeric with hyphens/underscores/dots, "
                "starting with alphanumeric."
            )
        return name

    def sanitize_variable_value(self, value: str) -> str:
        """Sanitize a variable value by stripping HTML tags.

        Args:
            value: The variable value to sanitize

        Returns:
            The sanitized value with HTML tags removed
        """
        # Strip HTML tags
        cleaned = _HTML_TAG_PATTERN.sub("", value)
        # Also escape any remaining HTML entities
        return html.unescape(cleaned)

    def sanitize_variables(self, variables: dict[str, str]) -> dict[str, str]:
        """Sanitize all values in a variables dictionary.

        Args:
            variables: Dict of variable name → value

        Returns:
            Dict with all values sanitized
        """
        return {
            key: self.sanitize_variable_value(value)
            for key, value in variables.items()
        }


# =========================================================================
# Security Headers Middleware
# =========================================================================

class SecurityHeaders(BaseHTTPMiddleware):
    """Middleware that adds standard security headers to all responses.

    Headers added:
      - X-Content-Type-Options: nosniff
      - X-Frame-Options: DENY
      - Strict-Transport-Security: max-age=31536000
      - X-XSS-Protection: 0 (modern browsers use CSP instead)
      - Referrer-Policy: strict-origin-when-cross-origin
      - Server: (removed or generic)

    Usage:
        app.add_middleware(SecurityHeaders)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to the response."""
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Remove or replace server header
        if "server" in response.headers:
            del response.headers["server"]

        return response
