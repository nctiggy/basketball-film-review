"""
Rate limiting middleware for API endpoints.

Implements per-IP and per-user rate limiting to prevent abuse.
Uses in-memory storage (should be replaced with Redis in production).
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple
from datetime import datetime, timedelta
import time


class RateLimiter:
    """
    Simple in-memory rate limiter.

    For production, replace with Redis-backed implementation.
    """

    def __init__(self):
        # Storage: {key: [(timestamp, count)]}
        self.requests: Dict[str, list[Tuple[float, int]]] = {}
        self.cleanup_interval = 300  # Clean up old entries every 5 minutes
        self.last_cleanup = time.time()

    def _cleanup(self):
        """Remove old entries to prevent memory leak."""
        now = time.time()
        if now - self.last_cleanup > self.cleanup_interval:
            cutoff = now - 3600  # Remove entries older than 1 hour
            for key in list(self.requests.keys()):
                self.requests[key] = [
                    (ts, count) for ts, count in self.requests[key]
                    if ts > cutoff
                ]
                if not self.requests[key]:
                    del self.requests[key]
            self.last_cleanup = now

    def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, Dict]:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Unique identifier for rate limit (IP or user ID)
            limit: Maximum number of requests allowed
            window: Time window in seconds

        Returns:
            Tuple of (allowed, headers_dict) where headers_dict contains
            rate limit information for response headers
        """
        self._cleanup()

        now = time.time()
        window_start = now - window

        # Get requests in current window
        if key not in self.requests:
            self.requests[key] = []

        # Filter to current window
        current_window_requests = [
            (ts, count) for ts, count in self.requests[key]
            if ts > window_start
        ]
        self.requests[key] = current_window_requests

        # Count requests in window
        request_count = sum(count for _, count in current_window_requests)

        # Check if allowed
        allowed = request_count < limit

        if allowed:
            # Add this request
            self.requests[key].append((now, 1))
            remaining = limit - request_count - 1
        else:
            remaining = 0

        # Calculate reset time (end of current window)
        if current_window_requests:
            oldest_ts = min(ts for ts, _ in current_window_requests)
            reset_time = int(oldest_ts + window)
        else:
            reset_time = int(now + window)

        headers = {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(max(0, remaining)),
            "X-RateLimit-Reset": str(reset_time)
        }

        return allowed, headers


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to apply rate limiting to requests.

    Auth endpoints: 5 requests/minute per IP
    API endpoints: 100 requests/minute per user (or IP if not authenticated)
    File uploads: 10 requests/minute per user
    """

    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Determine rate limit based on path
        path = request.url.path

        # Auth endpoints (stricter limits)
        if path.startswith("/auth/"):
            limit = 5
            window = 60  # 1 minute
            key = f"auth:{client_ip}"

            allowed, headers = rate_limiter.is_allowed(key, limit, window)

            if not allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many authentication attempts. Please try again later."},
                    headers=headers
                )

            # Process request
            response = await call_next(request)
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value
            return response

        # File upload endpoints (medium limits)
        elif "/upload" in path or "/audio" in path:
            limit = 10
            window = 60  # 1 minute

            # Try to get user from token
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                # Extract token and get user ID if possible
                # For now, use IP as we don't want to decode token here
                key = f"upload:{client_ip}"
            else:
                key = f"upload:{client_ip}"

            allowed, headers = rate_limiter.is_allowed(key, limit, window)

            if not allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many file uploads. Please slow down."},
                    headers=headers
                )

            # Process request
            response = await call_next(request)
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value
            return response

        # General API endpoints
        elif path.startswith("/api") or path.startswith("/"):
            limit = 100
            window = 60  # 1 minute
            key = f"api:{client_ip}"

            allowed, headers = rate_limiter.is_allowed(key, limit, window)

            if not allowed:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many requests. Please slow down."},
                    headers=headers
                )

            # Process request
            response = await call_next(request)
            for header_name, header_value in headers.items():
                response.headers[header_name] = header_value
            return response

        # No rate limit for other paths
        return await call_next(request)
