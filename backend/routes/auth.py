"""
Authentication routes.

Provides endpoints for:
- Google OAuth authentication
- Username/password login
- Account registration via invite code
- Token refresh
- User profile management
"""

from fastapi import APIRouter, HTTPException, status, Depends, Request
from datetime import datetime
import uuid
import hashlib

from backend.models.user import (
    GoogleAuthRequest,
    UserLogin,
    InviteRegisterRequest,
    UserUpdate,
    PasswordChange,
    TokenResponse,
    UserResponse,
    RefreshTokenRequest
)
from backend.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    exchange_code_for_token,
    get_current_user
)
from backend.auth.oauth import get_google_auth_url
from backend.auth.dependencies import db_pool
from backend.utils.audit_log import log_auth_event, log_sensitive_operation
import secrets

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/google/url")
async def get_google_oauth_url():
    """
    Get the Google OAuth authorization URL.

    Returns a URL that the frontend can redirect to for Google OAuth flow.
    Includes a random state parameter for CSRF protection.
    """
    # Generate random state for CSRF protection
    state = secrets.token_urlsafe(32)

    # Get the Google OAuth URL with state parameter
    auth_url = get_google_auth_url(state=state)

    return {"url": auth_url}


@router.post("/google", response_model=TokenResponse)
async def google_auth(auth_request: GoogleAuthRequest, request: Request):
    """
    Authenticate with Google OAuth.

    Creates a new coach account if the user doesn't exist.
    """
    try:
        # Exchange code for user info
        user_info = await exchange_code_for_token(auth_request.code)

        email = user_info.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not provided by Google"
            )

        # Check if user exists
        async with db_pool.acquire() as conn:
            user = await conn.fetchrow(
                """
                SELECT id, email, username, display_name, role, phone, status,
                       auth_provider, created_at, last_login_at
                FROM users
                WHERE email = $1
                """,
                email
            )

            if user:
                # Update last login
                await conn.execute(
                    "UPDATE users SET last_login_at = NOW() WHERE id = $1",
                    user["id"]
                )

                # Check if suspended
                if user["status"] == "suspended":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account suspended"
                    )

            else:
                # Create new coach account
                user_id = uuid.uuid4()
                display_name = user_info.get("name", email.split("@")[0])

                user = await conn.fetchrow(
                    """
                    INSERT INTO users (id, email, display_name, role, auth_provider, status, last_login_at)
                    VALUES ($1, $2, $3, 'coach', 'google', 'active', NOW())
                    RETURNING id, email, username, display_name, role, phone, status,
                              auth_provider, created_at, last_login_at
                    """,
                    user_id, email, display_name
                )

            # Create tokens
            access_token = create_access_token(str(user["id"]), user["role"])
            refresh_token = create_refresh_token(str(user["id"]))

            # Store refresh token hash
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            await conn.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES ($1, $2, NOW() + INTERVAL '7 days')
                """,
                user["id"], token_hash
            )

            user_response = UserResponse(
                id=str(user["id"]),
                email=user["email"],
                username=user["username"],
                display_name=user["display_name"],
                role=user["role"],
                phone=user["phone"],
                status=user["status"],
                auth_provider=user["auth_provider"],
                created_at=user["created_at"],
                last_login_at=user["last_login_at"]
            )

            # Log successful authentication
            log_auth_event(
                event_type="google_login",
                user_id=str(user["id"]),
                username=email,
                success=True,
                request=request
            )

            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                user=user_response
            )

    except HTTPException as e:
        # Log failed authentication
        log_auth_event(
            event_type="google_login",
            user_id=None,
            username=None,
            success=False,
            request=request,
            details=str(e.detail)
        )
        raise
    except Exception as e:
        # Log failed authentication
        log_auth_event(
            event_type="google_login",
            user_id=None,
            username=None,
            success=False,
            request=request,
            details=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google authentication failed: {str(e)}"
        )


@router.post("/login", response_model=TokenResponse)
async def login(login_request: UserLogin, request: Request):
    """
    Authenticate with username/password.

    Works for players and parents who have local accounts.
    """
    async with db_pool.acquire() as conn:
        # Find user by username or email
        user = await conn.fetchrow(
            """
            SELECT id, email, username, display_name, role, phone, status,
                   auth_provider, password_hash, created_at, last_login_at
            FROM users
            WHERE (username = $1 OR email = $1) AND auth_provider = 'local'
            """,
            login_request.username
        )

        if not user:
            # Log failed login attempt
            log_auth_event(
                event_type="login",
                user_id=None,
                username=login_request.username,
                success=False,
                request=request,
                details="User not found"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )

        # Verify password
        if not verify_password(login_request.password, user["password_hash"]):
            # Log failed login attempt
            log_auth_event(
                event_type="login",
                user_id=str(user["id"]),
                username=user["username"] or user["email"],
                success=False,
                request=request,
                details="Invalid password"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )

        # Check if suspended
        if user["status"] == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account suspended"
            )

        # Check if still in invited status
        if user["status"] == "invited":
            # Update to active on first login
            await conn.execute(
                "UPDATE users SET status = 'active', last_login_at = NOW() WHERE id = $1",
                user["id"]
            )
        else:
            # Update last login
            await conn.execute(
                "UPDATE users SET last_login_at = NOW() WHERE id = $1",
                user["id"]
            )

        # Create tokens
        access_token = create_access_token(str(user["id"]), user["role"])
        refresh_token = create_refresh_token(str(user["id"]))

        # Store refresh token hash
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '7 days')
            """,
            user["id"], token_hash
        )

        user_response = UserResponse(
            id=str(user["id"]),
            email=user["email"],
            username=user["username"],
            display_name=user["display_name"],
            role=user["role"],
            phone=user["phone"],
            status="active",  # Updated status
            auth_provider=user["auth_provider"],
            created_at=user["created_at"],
            last_login_at=datetime.utcnow()
        )

        # Log successful login
        log_auth_event(
            event_type="login",
            user_id=str(user["id"]),
            username=user["username"] or user["email"],
            success=True,
            request=request
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=user_response
        )


@router.post("/register", response_model=TokenResponse)
async def register_with_invite(register_request: InviteRegisterRequest, request: Request):
    """
    Register a new account using an invite code.

    Creates a player or parent account based on the invite.
    """
    async with db_pool.acquire() as conn:
        # Find and validate invite
        invite = await conn.fetchrow(
            """
            SELECT id, team_id, target_role, target_name, linked_player_id,
                   expires_at, claimed_by, created_by
            FROM invites
            WHERE code = $1 AND claimed_by IS NULL AND expires_at > NOW()
            """,
            register_request.invite_code
        )

        if not invite:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invite code"
            )

        # Check if username already exists
        existing = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM users WHERE username = $1)",
            register_request.username
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

        # Create user
        user_id = uuid.uuid4()
        password_hash_value = hash_password(register_request.password)

        user = await conn.fetchrow(
            """
            INSERT INTO users (id, username, password_hash, display_name, role,
                             phone, auth_provider, status, created_by, last_login_at)
            VALUES ($1, $2, $3, $4, $5, $6, 'local', 'active', $7, NOW())
            RETURNING id, email, username, display_name, role, phone, status,
                      auth_provider, created_at, last_login_at
            """,
            user_id, register_request.username, password_hash_value, register_request.display_name,
            invite["target_role"], register_request.phone, invite["created_by"]
        )

        # Add to team based on role
        if invite["target_role"] == "player":
            await conn.execute(
                """
                INSERT INTO team_players (team_id, player_id)
                VALUES ($1, $2)
                """,
                invite["team_id"], user_id
            )

        elif invite["target_role"] == "parent":
            # Link parent to player
            if invite["linked_player_id"]:
                await conn.execute(
                    """
                    INSERT INTO parent_links (parent_id, player_id, verified_at)
                    VALUES ($1, $2, NOW())
                    """,
                    user_id, invite["linked_player_id"]
                )

        # Mark invite as claimed
        await conn.execute(
            """
            UPDATE invites
            SET claimed_by = $1, claimed_at = NOW()
            WHERE id = $2
            """,
            user_id, invite["id"]
        )

        # Create tokens
        access_token = create_access_token(str(user["id"]), user["role"])
        refresh_token = create_refresh_token(str(user["id"]))

        # Store refresh token hash
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '7 days')
            """,
            user["id"], token_hash
        )

        user_response = UserResponse(
            id=str(user["id"]),
            email=user["email"],
            username=user["username"],
            display_name=user["display_name"],
            role=user["role"],
            phone=user["phone"],
            status=user["status"],
            auth_provider=user["auth_provider"],
            created_at=user["created_at"],
            last_login_at=user["last_login_at"]
        )

        # Log successful registration
        log_auth_event(
            event_type="register",
            user_id=str(user["id"]),
            username=user["username"],
            success=True,
            request=request,
            details=f"role={user['role']}"
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=user_response
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(request: RefreshTokenRequest):
    """
    Refresh an access token using a refresh token.
    """
    try:
        # Decode refresh token
        payload = decode_token(request.refresh_token)

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )

        # Verify refresh token exists in database and hasn't been revoked
        token_hash = hashlib.sha256(request.refresh_token.encode()).hexdigest()

        async with db_pool.acquire() as conn:
            token_record = await conn.fetchrow(
                """
                SELECT id, user_id, expires_at, revoked_at
                FROM refresh_tokens
                WHERE token_hash = $1 AND user_id = $2
                """,
                token_hash, uuid.UUID(user_id)
            )

            if not token_record:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )

            if token_record["revoked_at"]:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has been revoked"
                )

            if token_record["expires_at"] < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token expired"
                )

            # Get user info
            user = await conn.fetchrow(
                """
                SELECT id, email, username, display_name, role, phone, status,
                       auth_provider, created_at, last_login_at
                FROM users
                WHERE id = $1
                """,
                uuid.UUID(user_id)
            )

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )

            if user["status"] == "suspended":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account suspended"
                )

            # Create new tokens
            access_token = create_access_token(str(user["id"]), user["role"])
            new_refresh_token = create_refresh_token(str(user["id"]))

            # Revoke old refresh token and store new one
            await conn.execute(
                "UPDATE refresh_tokens SET revoked_at = NOW() WHERE id = $1",
                token_record["id"]
            )

            new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()
            await conn.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES ($1, $2, NOW() + INTERVAL '7 days')
                """,
                user["id"], new_token_hash
            )

            user_response = UserResponse(
                id=str(user["id"]),
                email=user["email"],
                username=user["username"],
                display_name=user["display_name"],
                role=user["role"],
                phone=user["phone"],
                status=user["status"],
                auth_provider=user["auth_provider"],
                created_at=user["created_at"],
                last_login_at=user["last_login_at"]
            )

            return TokenResponse(
                access_token=access_token,
                refresh_token=new_refresh_token,
                token_type="bearer",
                user=user_response
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Get the current user's profile.
    """
    return UserResponse(**current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    update: UserUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the current user's profile.
    """
    async with db_pool.acquire() as conn:
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        param_count = 1

        if update.display_name is not None:
            update_fields.append(f"display_name = ${param_count}")
            params.append(update.display_name)
            param_count += 1

        if update.phone is not None:
            update_fields.append(f"phone = ${param_count}")
            params.append(update.phone)
            param_count += 1

        if not update_fields:
            # No fields to update, return current user
            return UserResponse(**current_user)

        # Add user ID to params
        params.append(uuid.UUID(current_user["id"]))

        query = f"""
            UPDATE users
            SET {', '.join(update_fields)}
            WHERE id = ${param_count}
            RETURNING id, email, username, display_name, role, phone, status,
                      auth_provider, created_at, last_login_at
        """

        user = await conn.fetchrow(query, *params)

        return UserResponse(
            id=str(user["id"]),
            email=user["email"],
            username=user["username"],
            display_name=user["display_name"],
            role=user["role"],
            phone=user["phone"],
            status=user["status"],
            auth_provider=user["auth_provider"],
            created_at=user["created_at"],
            last_login_at=user["last_login_at"]
        )


@router.put("/me/password")
async def change_password(
    password_request: PasswordChange,
    current_user: dict = Depends(get_current_user),
    request: Request = None
):
    """
    Change the current user's password.

    Only works for users with local auth provider.
    """
    if current_user["auth_provider"] != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change password for OAuth accounts"
        )

    async with db_pool.acquire() as conn:
        # Get current password hash
        user = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1",
            uuid.UUID(current_user["id"])
        )

        # Verify current password
        if not verify_password(password_request.current_password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect"
            )

        # Hash new password
        new_hash = hash_password(password_request.new_password)

        # Update password
        await conn.execute(
            "UPDATE users SET password_hash = $1 WHERE id = $2",
            new_hash, uuid.UUID(current_user["id"])
        )

        # Log password change
        log_sensitive_operation(
            operation="password_change",
            user_id=current_user["id"],
            username=current_user["username"] or current_user["email"],
            role=current_user["role"],
            request=request
        )

        return {"message": "Password changed successfully"}


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user), request: Request = None):
    """
    Logout the current user by revoking all refresh tokens.
    """
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = NOW()
            WHERE user_id = $1 AND revoked_at IS NULL
            """,
            uuid.UUID(current_user["id"])
        )

    # Log logout
    log_auth_event(
        event_type="logout",
        user_id=current_user["id"],
        username=current_user["username"] or current_user["email"],
        success=True,
        request=request
    )

    return {"message": "Logged out successfully"}
