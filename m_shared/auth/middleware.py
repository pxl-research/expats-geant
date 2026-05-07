"""FastAPI middleware for implicit session management via JWT authentication."""

import logging
from collections.abc import Callable

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from m_shared.auth.jwt_handler import TokenExpiredError, TokenInvalidError, validate_token
from m_shared.session.manager import SessionManager

logger = logging.getLogger(__name__)


class SessionMiddleware(BaseHTTPMiddleware):
    """Middleware for implicit session management based on JWT authentication.

    This middleware:
    1. Extracts JWT from Authorization header
    2. Validates the token
    3. Extracts session_id from token claims
    4. Lazy-creates session if it doesn't exist (or reuses existing)
    5. Attaches session and claims to request.state for downstream handlers
    6. Updates session TTL on each authenticated request

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> app.add_middleware(SessionMiddleware, session_manager=manager)
    """

    def __init__(self, app, session_manager: SessionManager, ttl_hours: int = 24):
        """Initialize middleware.

        Args:
            app: FastAPI application
            session_manager: SessionManager instance
            ttl_hours: Default TTL for new sessions (hours)
        """
        super().__init__(app)
        self.session_manager = session_manager
        self.ttl_hours = ttl_hours

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and attach session context.

        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain

        Returns:
            Response from downstream handler

        Raises:
            HTTPException: 401 if token invalid/expired, 500 if session error
        """
        from fastapi.responses import JSONResponse

        # Skip authentication for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)

        # Extract token from Authorization header
        token = self._extract_token(request)
        if not token:
            logger.warning("Missing Bearer token on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing authorization token"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        try:
            claims = validate_token(token)
        except TokenExpiredError:
            logger.warning("Expired token rejected on %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token has expired"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except TokenInvalidError as e:
            logger.warning(
                "Invalid token rejected on %s %s: %s", request.method, request.url.path, e
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or malformed token"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error("Token validation error on %s %s: %s", request.method, request.url.path, e)
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Authentication error"},
            )

        # Extract session info from claims
        session_id = claims.get("session_id")
        user_id = claims.get("user_id")

        if not session_id or not user_id:
            logger.warning(
                "Token missing required claims (session_id, user_id) on %s %s",
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token missing required claims (session_id, user_id)"},
            )

        # Get or create session (lazy initialization)
        try:
            session = self.session_manager.get_session(session_id)

            if not session:
                # Session doesn't exist or expired - create new one
                session = self.session_manager.create_session(
                    user_id=user_id, jwt_token=token, ttl_hours=self.ttl_hours
                )
        except Exception as e:
            logger.error(
                "Session management error on %s %s: %s", request.method, request.url.path, e
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Session error"},
            )

        # Attach session and claims to request state
        request.state.session = session
        request.state.claims = claims
        request.state.session_manager = self.session_manager

        # Resolve per-tenant LLM client from pool (if configured)
        pool = getattr(request.app.state, "llm_client_pool", None)
        if pool:
            org = claims.get("org", "default")
            request.state.llm_client = pool.get(org) or pool.get("default")
        elif hasattr(request.app.state, "llm_client"):
            request.state.llm_client = request.app.state.llm_client

        # Process request
        response = await call_next(request)

        return response

    def _extract_token(self, request: Request) -> str | None:
        """Extract JWT from Authorization header.

        Args:
            request: Incoming request

        Returns:
            Token string or None if not found
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        return parts[1]

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint should skip authentication.

        Args:
            path: Request path

        Returns:
            True if public endpoint
        """
        public_paths = [
            "/",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/privacy",
            "/auth/token",
            "/auth/login",
            "/auth/callback",
            "/admin/reload-tenants",
        ]
        return path in public_paths
