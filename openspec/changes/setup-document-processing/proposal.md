# Change: Set Up Document Processing Pipeline

## Why

M-Autofill requires the ability to ingest documents in multiple formats (PDF, Word, text) and extract readable text with position metadata. This metadata is essential for accurate citations in Phase 3. Without a robust document processor, the RAG pipeline cannot function.

## What Changes

- Add MarkItDown (or equivalent) library for multi-format text extraction
- Implement document chunking strategy respecting sentence/paragraph boundaries
- Preserve metadata (filename, page/section numbers, timestamps) with each chunk
- Add input validation for file type and size constraints
- Create `m_autofill/document_processor.py` with public API for upload, parse, chunk

## Impact

- Affected specs: `specs/document-ingestion/spec.md`
- Affected code: New file `m_autofill/document_processor.py`; updates to `requirements.txt` (MarkItDown dependency)
- Dependencies: Phase 1 (data models for Session, Citation metadata)
- Blocking: Phase 2.2 (Vector DB) and Phase 3 (RAG pipeline)

## Acceptance Criteria

- All file formats (.txt, .pdf, .docx) extract and chunk correctly
- Metadata preserved in chunk objects (source, position, timestamp)
- Unit tests for text extraction, chunking, metadata tagging all passing
- No data loss during extraction or chunking
