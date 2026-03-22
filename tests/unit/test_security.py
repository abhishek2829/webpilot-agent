"""Tests for WebPilot Agent — Security Hardening (Task 16).

Tests API key authentication, rate limiting, input sanitization,
and credential security.

TDD: These tests are written FIRST, before the implementation.
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.security.middleware import (
    APIKeyAuthMiddleware,
    RateLimiter,
    InputSanitizer,
    SecurityHeaders,
)


# =========================================================================
# Test: API Key Authentication
# =========================================================================

class TestAPIKeyAuth:
    """Test API key authentication middleware."""

    def test_valid_api_key_passes(self):
        """Request with valid API key should pass through."""
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware, api_keys={"test-key-123"}, exclude_paths={"/health"})

        @app.get("/api/workflows")
        async def list_workflows():
            return {"workflows": []}

        client = TestClient(app)
        response = client.get(
            "/api/workflows",
            headers={"X-API-Key": "test-key-123"},
        )
        assert response.status_code == 200

    def test_missing_api_key_returns_401(self):
        """Request without API key should return 401."""
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware, api_keys={"test-key-123"}, exclude_paths={"/health"})

        @app.get("/api/workflows")
        async def list_workflows():
            return {"workflows": []}

        client = TestClient(app)
        response = client.get("/api/workflows")
        assert response.status_code == 401

    def test_invalid_api_key_returns_401(self):
        """Request with wrong API key should return 401."""
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware, api_keys={"test-key-123"}, exclude_paths={"/health"})

        @app.get("/api/workflows")
        async def list_workflows():
            return {"workflows": []}

        client = TestClient(app)
        response = client.get(
            "/api/workflows",
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_health_endpoint_excluded_from_auth(self):
        """Health check should work without API key."""
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware, api_keys={"test-key-123"}, exclude_paths={"/health"})

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_docs_endpoint_excluded_from_auth(self):
        """OpenAPI docs should work without API key."""
        app = FastAPI()
        app.add_middleware(
            APIKeyAuthMiddleware,
            api_keys={"test-key-123"},
            exclude_paths={"/health", "/docs", "/openapi.json"},
        )

        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_bearer_token_also_accepted(self):
        """Authorization: Bearer header should also work."""
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware, api_keys={"test-key-123"}, exclude_paths={"/health"})

        @app.get("/api/workflows")
        async def list_workflows():
            return {"workflows": []}

        client = TestClient(app)
        response = client.get(
            "/api/workflows",
            headers={"Authorization": "Bearer test-key-123"},
        )
        assert response.status_code == 200

    def test_empty_api_keys_set_allows_all(self):
        """If no API keys configured, all requests pass (dev mode)."""
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware, api_keys=set(), exclude_paths={"/health"})

        @app.get("/api/workflows")
        async def list_workflows():
            return {"workflows": []}

        client = TestClient(app)
        response = client.get("/api/workflows")
        assert response.status_code == 200


# =========================================================================
# Test: Rate Limiter
# =========================================================================

class TestRateLimiter:
    """Test in-memory rate limiter."""

    def test_allows_requests_under_limit(self):
        """Should allow requests under the rate limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("client-1") is True

    def test_blocks_requests_over_limit(self):
        """Should block requests exceeding the rate limit."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.is_allowed("client-1")
        assert limiter.is_allowed("client-1") is False

    def test_separate_limits_per_client(self):
        """Each client should have independent rate limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("client-a")
        limiter.is_allowed("client-a")
        # client-a is at limit
        assert limiter.is_allowed("client-a") is False
        # client-b should still be allowed
        assert limiter.is_allowed("client-b") is True

    def test_window_expires_resets_counter(self):
        """After the time window, rate limit should reset."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        assert limiter.is_allowed("client-1") is True
        assert limiter.is_allowed("client-1") is False
        # Wait for window to expire
        time.sleep(1.1)
        assert limiter.is_allowed("client-1") is True

    def test_get_remaining_returns_count(self):
        """get_remaining should return how many requests are left."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        limiter.is_allowed("client-1")
        limiter.is_allowed("client-1")
        assert limiter.get_remaining("client-1") == 3


# =========================================================================
# Test: Input Sanitizer
# =========================================================================

class TestInputSanitizer:
    """Test input sanitization for API endpoints."""

    def test_sanitize_workflow_name_valid(self):
        """Valid workflow names should pass through."""
        s = InputSanitizer()
        assert s.sanitize_workflow_name("clerk-setup") == "clerk-setup"
        assert s.sanitize_workflow_name("my_workflow_v2") == "my_workflow_v2"

    def test_sanitize_workflow_name_rejects_path_traversal(self):
        """Workflow names with path traversal should be rejected."""
        s = InputSanitizer()
        with pytest.raises(ValueError, match="Invalid workflow name"):
            s.sanitize_workflow_name("../../../etc/passwd")

    def test_sanitize_workflow_name_rejects_special_chars(self):
        """Workflow names with shell-dangerous characters should be rejected."""
        s = InputSanitizer()
        with pytest.raises(ValueError, match="Invalid workflow name"):
            s.sanitize_workflow_name("workflow;rm -rf /")

    def test_sanitize_workflow_name_rejects_empty(self):
        """Empty workflow name should be rejected."""
        s = InputSanitizer()
        with pytest.raises(ValueError, match="Invalid workflow name"):
            s.sanitize_workflow_name("")

    def test_sanitize_workflow_name_rejects_too_long(self):
        """Workflow names over 100 chars should be rejected."""
        s = InputSanitizer()
        with pytest.raises(ValueError, match="Invalid workflow name"):
            s.sanitize_workflow_name("a" * 101)

    def test_sanitize_variable_value_strips_html(self):
        """Variable values should have HTML/script tags stripped."""
        s = InputSanitizer()
        result = s.sanitize_variable_value("<script>alert('xss')</script>MyApp")
        assert "<script>" not in result
        assert "MyApp" in result

    def test_sanitize_variable_value_preserves_normal_text(self):
        """Normal variable values should pass through unchanged."""
        s = InputSanitizer()
        assert s.sanitize_variable_value("MyProject-v2") == "MyProject-v2"

    def test_sanitize_variables_dict(self):
        """Should sanitize all values in a variables dict."""
        s = InputSanitizer()
        variables = {
            "project_name": "MyApp",
            "evil": "<script>hack</script>",
        }
        result = s.sanitize_variables(variables)
        assert result["project_name"] == "MyApp"
        assert "<script>" not in result["evil"]


# =========================================================================
# Test: Security Headers
# =========================================================================

class TestSecurityHeaders:
    """Test that security response headers are added."""

    def test_adds_security_headers(self):
        """Response should include standard security headers."""
        app = FastAPI()
        app.add_middleware(SecurityHeaders)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert "strict-transport-security" in {k.lower() for k in response.headers.keys()}

    def test_removes_server_header(self):
        """Server header should not reveal implementation details."""
        app = FastAPI()
        app.add_middleware(SecurityHeaders)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")
        # Server header should either be removed or generic
        server = response.headers.get("server", "")
        assert "uvicorn" not in server.lower()
