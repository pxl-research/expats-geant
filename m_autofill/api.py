"""FastAPI endpoints for M-Autofill answer suggestion service."""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, status, UploadFile, File, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from m_shared.session.manager import SessionManager
from m_shared.llm.client import LLMClient
from m_shared.utils.audit import AuditLogger
from m_shared.auth.jwt_handler import create_token
from m_autofill.validation import validate_file_upload, FileValidationError
from m_autofill.ingest import ingest_files_into_store
from m_autofill.rag_pipeline import RAGPipeline


# Request models
class SuggestRequest(BaseModel):
    """Request for answer suggestion."""
    question: str = Field(..., min_length=1, max_length=2000, description="Question to answer")
    context: Optional[str] = Field(None, max_length=1000, description="Optional context")


# Response models
class UploadResponse(BaseModel):
    """Document upload response."""
    status: str
    filename: str
    size_bytes: int
    upload_timestamp: str
    session_id: str


class CitationResponse(BaseModel):
    """Citation information."""
    source: str
    position: str
    position_range: dict
    timestamp: str
    excerpt: str


class SuggestResponse(BaseModel):
    """Answer suggestion response."""
    answer: str
    citations: list[CitationResponse]
    metadata: dict


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


class DevTokenRequest(BaseModel):
    """Request for development token generation."""
    user_id: str = Field(default="dev_user", description="User ID for token")
    org: str = Field(default="dev_org", description="Organization ID")
    roles: list[str] = Field(default=["respondent"], description="User roles")


class DevTokenResponse(BaseModel):
    """Development token response."""
    token: str
    user_id: str
    expires_in_hours: int
    message: str


def create_app(
    session_manager: SessionManager,
    llm_client: Optional[LLMClient] = None,
    audit_logger: Optional[AuditLogger] = None,
    max_file_size_mb: int = 50,
) -> FastAPI:
    """Create FastAPI application with M-Autofill endpoints.
    
    Args:
        session_manager: SessionManager instance
        llm_client: LLM client for answer generation (optional for session-only endpoints)
        audit_logger: Audit logger for compliance tracking
        max_file_size_mb: Maximum file size in MB (default: 50)
        
    Returns:
        Configured FastAPI app
    """
    app = FastAPI(
        title="M-Autofill API",
        description="Evidence-based answer suggestion service",
        version="0.1.0"
    )
    
    # Initialize RAG pipeline if LLM client provided
    rag_pipeline = None
    if llm_client:
        rag_pipeline = RAGPipeline(
            session_manager=session_manager,
            llm_client=llm_client,
            audit_logger=audit_logger
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
    
    @app.post("/dev/token", response_model=DevTokenResponse, tags=["Development"])
    async def generate_dev_token(request: DevTokenRequest):
        """Generate JWT token for development/testing (disabled in production).
        
        This endpoint allows developers to easily generate valid JWT tokens for testing
        the API without needing to set up a full authentication infrastructure.
        
        **IMPORTANT**: This endpoint is only available when ENVIRONMENT != "production"
        
        Args:
            request: Token generation parameters (user_id, org, roles)
            
        Returns:
            JWT token and metadata
            
        Raises:
            HTTPException: 403 if called in production environment
        """
        # Check environment - block in production
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token generation endpoint disabled in production"
            )
        
        # Generate session ID from user_id for consistency
        session_id = f"dev_session_{request.user_id}"
        
        # Create token with requested parameters
        try:
            token = create_token(
                user_id=request.user_id,
                session_id=session_id,
                org=request.org,
                roles=request.roles,
                expiration_hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
            )
            
            return DevTokenResponse(
                token=token,
                user_id=request.user_id,
                expires_in_hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")),
                message="Token generated successfully. Use in Authorization header: Bearer <token>"
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Token generation failed: {str(e)}"
            )
    
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
    
    @app.post("/upload", response_model=UploadResponse)
    async def upload_document(
        request: Request,
        file: UploadFile = File(...),
    ):
        """Upload a document to the session for answer suggestions.
        
        Session is automatically identified from JWT token via middleware.
        
        Args:
            file: Document file (PDF, DOCX, TXT, MD)
            
        Returns:
            Upload confirmation with metadata
            
        Raises:
            HTTPException: 400 if file invalid, 404 if session not found
        """
        session = request.state.session
        manager = request.state.session_manager
        claims = request.state.claims
        
        # Save uploaded file temporarily
        temp_dir = manager._get_session_path(session.session_id) / "uploads"
        temp_dir.mkdir(exist_ok=True)
        file_path = temp_dir / file.filename
        
        try:
            # Write file to disk
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Validate file
            is_valid, error_msg = validate_file_upload(
                str(file_path),
                max_size_bytes=max_file_size_mb * 1024 * 1024
            )
            if not is_valid:
                raise FileValidationError(error_msg)
            
            # Get vector store for session
            store = manager.get_vector_store(session.session_id)
            if not store:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session not found or expired"
                )
            
            # Ingest file into vector store
            ingest_files_into_store(
                file_paths=[str(file_path)],
                store=store,
                session_id=session.session_id,
                user_id=claims.get("user_id"),
                audit_logger=audit_logger,
            )
            
            file_size = os.path.getsize(file_path)
            upload_timestamp = datetime.now(timezone.utc).isoformat()
            
            return UploadResponse(
                status="success",
                filename=file.filename,
                size_bytes=file_size,
                upload_timestamp=upload_timestamp,
                session_id=session.session_id,
            )
            
        except FileValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {e}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {e}"
            )
    
    @app.post("/suggest", response_model=SuggestResponse)
    async def suggest_answer(
        request: Request,
        suggest_request: SuggestRequest,
    ):
        """Generate answer suggestion based on uploaded documents.
        
        Session is automatically identified from JWT token via middleware.
        
        Args:
            suggest_request: Question and optional context
            
        Returns:
            Answer with citations
            
        Raises:
            HTTPException: 400 if invalid, 404 if no documents, 500 if LLM error
        """
        if not rag_pipeline:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="RAG pipeline not initialized (LLM client missing)"
            )
        
        session = request.state.session
        claims = request.state.claims
        
        try:
            # Generate suggestion
            result = rag_pipeline.suggest_answer(
                question=suggest_request.question,
                session_id=session.session_id,
                user_id=claims.get("user_id"),
            )
            
            # Format citations
            citations = [
                CitationResponse(
                    source=cit.source_id,
                    position=f"{cit.position_percentage:.1%}" if cit.position_percentage else "unknown",
                    position_range={
                        "start_percentage": cit.position_start or 0,
                        "end_percentage": cit.position_end or 0,
                    },
                    timestamp=cit.timestamp.isoformat() if cit.timestamp else "",
                    excerpt=cit.highlights[0] if cit.highlights else "",
                )
                for cit in result["citations"]
            ]
            
            return SuggestResponse(
                answer=result["answer"],
                citations=citations,
                metadata=result.get("metadata", {}),
            )
            
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Suggestion failed: {e}"
            )
    
    @app.get("/audit-report")
    async def get_audit_report(
        request: Request,
        format: str = "json",
    ):
        """Retrieve session audit report.
        
        Session is automatically identified from JWT token via middleware.
        
        Args:
            format: Response format ('json' or 'plaintext')
            
        Returns:
            Audit report in requested format
            
        Raises:
            HTTPException: 404 if session not found
        """
        if not audit_logger:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audit logging not enabled"
            )
        
        session = request.state.session
        
        try:
            report = audit_logger.generate_report(session.session_id)
            
            if format == "plaintext":
                # Convert to plaintext
                plaintext = f"""AUDIT REPORT — Session {session.session_id}
Created: {report.get('created_at', 'N/A')}
Ended: {report.get('ended_at', 'N/A')}

DOCUMENTS UPLOADED ({report['summary']['total_documents']}):
"""
                for doc in report.get('documents', []):
                    plaintext += f"- {doc['filename']} ({doc['size_bytes']:,} bytes) — uploaded {doc['upload_timestamp']}\n"
                
                plaintext += f"\nSUGGESTIONS GENERATED ({report['summary']['total_suggestions']}):\n"
                for i, sug in enumerate(report.get('suggestions', []), 1):
                    plaintext += f"[{i}] Question: {sug['question']}\n"
                    plaintext += f"    Suggestion: {sug['suggested_answer'][:100]}...\n"
                    plaintext += f"    Sources: {', '.join(sug['sources'])}\n"
                    plaintext += f"    Generated: {sug['generation_timestamp']}\n"
                    if sug.get('user_edited_answer'):
                        plaintext += f"    User Edit: {sug['user_edited_answer'][:50]}...\n"
                    plaintext += "\n"
                
                plaintext += f"""SUMMARY:
- Total Documents: {report['summary']['total_documents']}
- Total Suggestions: {report['summary']['total_suggestions']}
- Total Edits: {report['summary']['total_user_edits']}
- Avg Sources per Suggestion: {report['summary']['avg_sources_per_suggestion']:.1f}
"""
                return PlainTextResponse(content=plaintext)
            else:
                # JSON format (default)
                return report
                
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Report generation failed: {e}"
            )
    
    @app.get("/privacy", response_class=PlainTextResponse)
    async def get_privacy_statement():
        """Return privacy and GDPR disclosure statement.
        
        Returns:
            Plaintext privacy statement
        """
        privacy_text = """M-AUTOFILL PRIVACY STATEMENT

DATA COLLECTION:
- Documents you upload are processed temporarily during your session
- Answer suggestions and citations are generated from your documents only
- All processing happens within your isolated session

DATA RETENTION:
- Operational data (documents, vectors, temporary files) deleted when session expires (default: 24-48 hours)
- Audit reports retained for 1 year for compliance, then automatically deleted
- You can delete your session immediately using DELETE /session

DATA USAGE:
- Documents used only for generating answer suggestions
- No profiling, tracking, or cross-session correlation
- No data sharing with third parties

YOUR RIGHTS (GDPR):
- Right to access: Download your audit report anytime (GET /audit-report)
- Right to deletion: Delete your session and data immediately (DELETE /session)
- Right to know: This statement explains all data handling

CONSENT:
By using this service, you consent to:
- Temporary processing of uploaded documents for answer generation
- Storage of audit logs for 1 year for compliance purposes
- LLM processing via OpenRouter (EU-based deployment)

CONTACT:
For privacy concerns: [Insert institutional contact]
For technical issues: [Insert support contact]

Last updated: January 2026
"""
        return privacy_text
    
    return app
