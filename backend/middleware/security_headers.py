"""
Security headers middleware.

Adds security headers to all responses to protect against common web vulnerabilities.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: Prevent MIME type sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: Enable XSS filter in older browsers
    - Strict-Transport-Security: Force HTTPS (only if secure connection)
    - Content-Security-Policy: Restrict resource loading
    - Referrer-Policy: Control referrer information
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enable XSS protection in older browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Force HTTPS (only add if connection is secure)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy
        # Allow same-origin and specific trusted sources
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Allow inline scripts for SPA
            "style-src 'self' 'unsafe-inline'; "  # Allow inline styles
            "img-src 'self' data: blob:; "  # Allow data URLs for images
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "media-src 'self' blob:; "  # Allow blob URLs for video
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Content-Security-Policy"] = csp

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Remove server header to avoid information disclosure
        if "server" in response.headers:
            del response.headers["server"]

        return response
