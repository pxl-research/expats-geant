"""FastAPI endpoints for M-Autofill answer suggestion service."""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from m_shared.session.manager import SessionManager


# Response models
class SessionStatsResponse(BaseModel):
    """Session statistics response."""
    session_id: str
    user_id: str
    created_at: str
    expires_at: str
    remaining_hours: float
    is_expired: bool
    document_count: int
    isolation_scope: str


class SessionDeleteResponse(BaseModel):
    """Session deletion response."""
    session_id: str
    deleted: bool
    message: str


def create_app(session_manager: SessionManager) -> FastAPI:
    """Create FastAPI application with session management endpoints.
    
    Args:
        session_manager: SessionManager instance
        
    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="M-Autofill API",
        description="Evidence-based answer suggestion service",
        version="0.1.0"
    )
    
    # Add exception handler for HTTPException
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTPException properly."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers
        )
    
    @app.get("/")
    async def root():
        """Health check endpoint."""
        return {"service": "m-autofill", "status": "running"}
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}
    
    @app.get("/session/stats", response_model=SessionStatsResponse)
    async def get_session_stats(request: Request):
        """Get statistics for the current user's session.
        
        Session is automatically identified from JWT token via middleware.
        
        Returns:
            Session statistics including TTL remaining, document count, etc.
            
        Raises:
            HTTPException: 404 if session not found
        """
        # Session and claims attached by middleware
        session = request.state.session
        manager = request.state.session_manager
        
        stats = manager.get_session_stats(session.session_id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return SessionStatsResponse(**stats)
    
    @app.delete("/session", response_model=SessionDeleteResponse)
    async def delete_session(request: Request):
        """Delete the current user's session and all associated data.
        
        This allows users to explicitly clean up their data before TTL expiration
        (privacy feature: "forget my data now").
        
        Session is automatically identified from JWT token via middleware.
        
        Returns:
            Confirmation of deletion
        """
        # Session and claims attached by middleware
        session = request.state.session
        manager = request.state.session_manager
        
        deleted = manager.delete_session(session.session_id)
        
        if deleted:
            return SessionDeleteResponse(
                session_id=session.session_id,
                deleted=True,
                message="Session and all data successfully deleted"
            )
        else:
            # Session already deleted or doesn't exist
            return SessionDeleteResponse(
                session_id=session.session_id,
                deleted=False,
                message="Session does not exist or was already deleted"
            )
    
    return app
