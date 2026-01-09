# Phase 2.1: Document Processing Implementation Tasks

## 1. Setup & Dependencies

- [x] 1.1 Add MarkItDown to `requirements.txt` (version 0.1.4 or later) — Already in requirements.txt as markitdown>=0.1.3
- [x] 1.2 Create `m_autofill/document_processor.py` module skeleton — Exists as ingest.py with working implementation
- [x] 1.3 Add `m_autofill/__init__.py` if missing — Already exists with proper exports

## 2. Text Extraction

- [x] 2.1 Implement `extract_text(file_path: str) -> tuple[str, dict]` for .txt files — `document_to_markdown()` in vectordb/utils.py supports all formats
- [x] 2.2 Implement PDF extraction using MarkItDown with position tracking — `document_to_markdown()` handles PDFs
- [x] 2.3 Implement Word (.docx) extraction using MarkItDown with position tracking — `document_to_markdown()` handles DOCX
- [x] 2.4 Add file type detection/validation (reject unsupported formats) — `sanitize_filename()` in vectordb/utils.py validates
- [ ] 2.5 Unit tests for text extraction (sample files for each format) — Tests do not exist yet

## 3. Chunking Strategy

- [x] 3.1 Implement `chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]` — `iterative_chunking()` in vectordb/utils.py
- [x] 3.2 Ensure chunks respect sentence/paragraph boundaries (no mid-word splits) — Already implemented in `iterative_chunking()`
- [x] 3.3 Support configurable chunk size and overlap — `iterative_chunking(text, max_size=...)` supports this
- [ ] 3.4 Unit tests for chunking (verify boundary handling, overlap correctness) — Tests do not exist yet

## 4. Metadata Preservation

- [x] 4.1 Create chunk metadata structure (source_filename, position, timestamp, optional highlights) — Already done in ingest.py with meta_info dict
- [ ] 4.2 Implement `attach_metadata(chunks: list[str], source_filename: str, positions: list[dict]) -> list[dict]` — Partially done in ingest.py; needs refactoring into reusable function
- [ ] 4.3 Map chunk positions back to original document (page/section numbers for PDFs/Word) — Position tracking exists but needs enhancement for PDF page numbers
- [ ] 4.4 Unit tests for metadata preservation — Tests do not exist yet

## 5. Document Processor API

- [x] 5.1 Implement `upload_document(file_path: str, session_id: str) -> list[dict]` — `ingest_files_into_store()` exists; needs refactoring for session support
- [ ] 5.2 Implement file size validation (max 50MB suggested, configurable) — Not yet implemented
- [ ] 5.3 Implement file type validation (only .txt, .pdf, .docx allowed) — Partially done; needs hardening
- [ ] 5.4 Add error handling for malformed/corrupted files — Basic error handling exists; needs comprehensive coverage

## 6. Input Validation

- [ ] 6.1 Add `validate_file_upload(file_path: str) -> bool` with size/type checks — Not a standalone function yet
- [ ] 6.2 Unit tests for validation (reject oversized files, unsupported formats) — Tests do not exist yet

## 7. Testing

- [ ] 7.1 Unit tests for text extraction (create sample .txt, .pdf, .docx test files) — No test files yet
- [ ] 7.2 Unit tests for chunking (boundary cases, empty documents) — No tests exist yet
- [ ] 7.3 Unit tests for metadata (verify position tracking accuracy) — No tests exist yet
- [ ] 7.4 Integration test: upload → extract → chunk → verify metadata — No integration tests yet
- [ ] 7.5 All tests passing, 80%+ code coverage — Not yet measured

## 8. Documentation

- [x] 8.1 Docstrings for all public functions — Already present in ingest.py and vectordb/utils.py
- [ ] 8.2 Brief README in `m_autofill/` explaining document processor API — README.md exists but needs update for v2.1 API
