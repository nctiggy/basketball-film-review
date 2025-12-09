"""
Audit logging for security-sensitive operations.

Logs authentication events, authorization failures, and sensitive operations
to help with security monitoring and incident response.
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import Request

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Create handler if not already configured
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - AUDIT - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)


class AuditLogger:
    """
    Centralized audit logging for security events.

    All security-sensitive operations should be logged here.
    """

    @staticmethod
    def _get_client_ip(request: Optional[Request]) -> str:
        """Extract client IP from request."""
        if not request:
            return "unknown"

        # Check for forwarded IP (if behind proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Fall back to client.host
        return request.client.host if request.client else "unknown"

    @staticmethod
    def log_auth_event(
        event_type: str,
        user_id: Optional[str],
        username: Optional[str],
        success: bool,
        request: Optional[Request] = None,
        details: Optional[str] = None
    ):
        """
        Log authentication events.

        Args:
            event_type: Type of auth event (login, logout, register, token_refresh)
            user_id: User ID if known
            username: Username or email
            success: Whether the operation succeeded
            request: FastAPI request object for IP extraction
            details: Additional details about the event
        """
        ip = AuditLogger._get_client_ip(request) if request else "unknown"
        status = "SUCCESS" if success else "FAILURE"

        message = (
            f"AUTH_EVENT | {event_type.upper()} | {status} | "
            f"user_id={user_id or 'N/A'} | username={username or 'N/A'} | "
            f"ip={ip}"
        )

        if details:
            message += f" | details={details}"

        if success:
            audit_logger.info(message)
        else:
            audit_logger.warning(message)

    @staticmethod
    def log_authorization_failure(
        user_id: str,
        username: str,
        role: str,
        resource_type: str,
        resource_id: str,
        action: str,
        request: Optional[Request] = None,
        reason: Optional[str] = None
    ):
        """
        Log authorization failures (403 responses).

        Args:
            user_id: User attempting access
            username: Username of user
            role: User's role
            resource_type: Type of resource (team, clip, game, etc.)
            resource_id: ID of resource
            action: Action attempted (read, write, delete, etc.)
            request: FastAPI request object
            reason: Reason for denial
        """
        ip = AuditLogger._get_client_ip(request) if request else "unknown"

        message = (
            f"AUTHZ_FAILURE | user_id={user_id} | username={username} | "
            f"role={role} | resource={resource_type}:{resource_id} | "
            f"action={action} | ip={ip}"
        )

        if reason:
            message += f" | reason={reason}"

        audit_logger.warning(message)

    @staticmethod
    def log_sensitive_operation(
        operation: str,
        user_id: str,
        username: str,
        role: str,
        target_user_id: Optional[str] = None,
        request: Optional[Request] = None,
        details: Optional[str] = None
    ):
        """
        Log sensitive operations.

        Args:
            operation: Operation type (password_change, role_change, account_suspend, etc.)
            user_id: User performing the operation
            username: Username of user
            role: User's role
            target_user_id: If operation affects another user
            request: FastAPI request object
            details: Additional details
        """
        ip = AuditLogger._get_client_ip(request) if request else "unknown"

        message = (
            f"SENSITIVE_OP | {operation.upper()} | "
            f"user_id={user_id} | username={username} | role={role} | "
            f"ip={ip}"
        )

        if target_user_id:
            message += f" | target_user_id={target_user_id}"

        if details:
            message += f" | details={details}"

        audit_logger.info(message)


# Convenience functions
def log_auth_event(
    event_type: str,
    user_id: Optional[str],
    username: Optional[str],
    success: bool,
    request: Optional[Request] = None,
    details: Optional[str] = None
):
    """Convenience wrapper for AuditLogger.log_auth_event."""
    AuditLogger.log_auth_event(event_type, user_id, username, success, request, details)


def log_authorization_failure(
    user_id: str,
    username: str,
    role: str,
    resource_type: str,
    resource_id: str,
    action: str,
    request: Optional[Request] = None,
    reason: Optional[str] = None
):
    """Convenience wrapper for AuditLogger.log_authorization_failure."""
    AuditLogger.log_authorization_failure(
        user_id, username, role, resource_type, resource_id, action, request, reason
    )


def log_sensitive_operation(
    operation: str,
    user_id: str,
    username: str,
    role: str,
    target_user_id: Optional[str] = None,
    request: Optional[Request] = None,
    details: Optional[str] = None
):
    """Convenience wrapper for AuditLogger.log_sensitive_operation."""
    AuditLogger.log_sensitive_operation(
        operation, user_id, username, role, target_user_id, request, details
    )
