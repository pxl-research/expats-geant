# Session Management

This module provides session-based isolation for vector stores with TTL-based cleanup.

## Overview

The `SessionManager` class manages user sessions with isolated ChromaDB vector stores. Each session:

- Has a unique ID derived from JWT token hashing (stable and deterministic)
- Gets its own folder structure with isolated ChromaDB instance
- Tracks creation time and expiration (TTL-based)
- Can be cleaned up automatically when expired

## Architecture

```
sessions/
├── abc123def456/              # Session ID (hashed from JWT)
│   ├── chroma_store/          # Isolated ChromaDB data
│   ├── documents/             # Uploaded documents (optional)
│   └── metadata.json          # Session metadata
└── xyz789ghi012/
    ├── chroma_store/
    ├── documents/
    └── metadata.json
```

## Usage

### Basic Usage

```python
from m_shared.session import SessionManager

# Initialize manager
manager = SessionManager(base_path="./sessions")

# Create session from JWT token
session = manager.create_session(
    user_id="user_123",
    jwt_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    ttl_hours=24  # Optional, defaults to 24 hours
)

# Get vector store for session
store = manager.get_vector_store(session.session_id)

# Use vector store
store.add_document(
    document_text="Sample document",
    metadata={"filename": "sample.txt"}
)

# Query vector store
results = store.query(query_text="sample", n_results=5)
```

### Session Lifecycle

```python
# Create or resume session (same token = same session ID)
session = manager.create_session(user_id="user_123", jwt_token=token)

# Get session info
session = manager.get_session(session_id)
print(f"Expires at: {session.expires_at}")

# Check if expired
if session.is_expired():
    print("Session has expired")

# List active sessions
active = manager.list_sessions(include_expired=False)
print(f"Active sessions: {len(active)}")

# Delete session manually
manager.delete_session(session_id)

# Cleanup expired sessions
deleted = manager.cleanup_expired_sessions()
print(f"Cleaned up {len(deleted)} expired sessions")
```

### Session Statistics

```python
# Get stats for a session
stats = manager.get_session_stats(session_id)
print(f"Documents: {stats['document_count']}")
print(f"Chunks: {stats['chunk_count']}")
print(f"TTL remaining: {stats['ttl_hours']} hours")
```

## Filtered Search

Documents ingested via `ingest_files_into_store` automatically receive an `ingested_at` Unix timestamp float (seconds since epoch) in their chunk metadata. This enables two filtering modes via `ChromaDocumentStore.query_with_filter()`:

```python
store = manager.get_vector_store(session.session_id)

# Filter by source document (restricts to that document's collection)
results = store.query_with_filter(
    query_text="What is my salary?",
    filters={"source": "contract.pdf"},
    n_results=5,
)

# Filter by ingestion time range (Unix timestamp float, supports $gte/$lte/$gt/$lt)
from datetime import datetime, timedelta
since_yesterday = (datetime.utcnow() - timedelta(days=1)).timestamp()
results = store.query_with_filter(
    query_text="leave policy",
    filters={"ingested_at": {"$gte": since_yesterday}},
    n_results=5,
)
```

When using `RAGPipeline`, pass filters through `retrieve()`:

```python
chunks = pipeline.retrieve(
    question="What is my salary?",
    session_id=session.session_id,
    filters={"source": "contract.pdf"},
)
```

Supported filter keys:
- `source`: `str` or `list[str]` — restrict to specific document(s) by filename (without path/extension)
- Any ChromaDB `where`-compatible key (e.g. `ingested_at`) with operators `$gte`, `$lte`, `$eq`, `$in`, etc.

## Integration with Document Ingestion

```python
from m_shared.session import SessionManager
from cue_api.ingest import ingest_files_into_store

# Initialize
manager = SessionManager()
session = manager.create_session(user_id="user_123", jwt_token=token)

# Get isolated vector store
store = manager.get_vector_store(session.session_id)

# Ingest documents
file_paths = ["doc1.pdf", "doc2.txt"]
added = ingest_files_into_store(
    file_paths=file_paths,
    store=store,
    max_chunk_size=512
)

print(f"Added {len(added)} documents to session {session.session_id}")
```

## TTL and Cleanup

Sessions expire after a configurable TTL (default 24 hours). Expired sessions can be cleaned up:

### Manual Cleanup (On-Demand)

```python
# In an API endpoint
deleted = manager.cleanup_expired_sessions()
return {"deleted_sessions": deleted}
```

### Automatic Cleanup (Optional)

For production, consider running cleanup periodically:

- Via cron job calling the cleanup API endpoint
- Via background task scheduler (e.g., APScheduler)
- Via scheduled cloud function (e.g., AWS Lambda, GCP Cloud Functions)

## Testing

The session module has comprehensive test coverage:

- `tests/test_session_manager.py`: 27 unit tests
- `tests/test_session_isolation.py`: 8 integration tests
- `tests/test_filtered_search.py`: filtered search (source and time-range)

Run tests:

```bash
pytest tests/test_session_manager.py tests/test_session_isolation.py tests/test_filtered_search.py -v
```

## Design Decisions

### JWT Token Hashing

- Session IDs are derived from JWT tokens via SHA256 hashing
- Same token always produces same session ID (idempotent)
- Enables session resumption across requests
- 16-character session ID for brevity

### Folder-Based Isolation

- Each session gets its own folder
- Contains isolated ChromaDB instance (no shared state)
- Easy cleanup: delete folder = delete session
- Supports concurrent sessions without interference

### Separate SessionManager Class

- SessionManager **uses** ChromaDocumentStore, not extends it
- Clear separation of concerns: session management vs vector operations
- Shared between M-Chat and M-Autofill modules
- Located in `m_shared` for reusability

