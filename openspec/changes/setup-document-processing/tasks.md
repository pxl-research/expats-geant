# Phase 2.1: Document Processing Implementation Tasks

## 1. Setup & Dependencies

- [ ] 1.1 Add MarkItDown to `requirements.txt` (version 0.1.4 or later)
- [ ] 1.2 Create `m_autofill/document_processor.py` module skeleton
- [ ] 1.3 Add `m_autofill/__init__.py` if missing

## 2. Text Extraction

- [ ] 2.1 Implement `extract_text(file_path: str) -> tuple[str, dict]` for .txt files
- [ ] 2.2 Implement PDF extraction using MarkItDown with position tracking
- [ ] 2.3 Implement Word (.docx) extraction using MarkItDown with position tracking
- [ ] 2.4 Add file type detection/validation (reject unsupported formats)
- [ ] 2.5 Unit tests for text extraction (sample files for each format)

## 3. Chunking Strategy

- [ ] 3.1 Implement `chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]`
- [ ] 3.2 Ensure chunks respect sentence/paragraph boundaries (no mid-word splits)
- [ ] 3.3 Support configurable chunk size and overlap
- [ ] 3.4 Unit tests for chunking (verify boundary handling, overlap correctness)

## 4. Metadata Preservation

- [ ] 4.1 Create chunk metadata structure (source_filename, position, timestamp, optional highlights)
- [ ] 4.2 Implement `attach_metadata(chunks: list[str], source_filename: str, positions: list[dict]) -> list[dict]`
- [ ] 4.3 Map chunk positions back to original document (page/section numbers for PDFs/Word)
- [ ] 4.4 Unit tests for metadata preservation

## 5. Document Processor API

- [ ] 5.1 Implement `upload_document(file_path: str, session_id: str) -> list[dict]` (returns chunked documents with metadata)
- [ ] 5.2 Implement file size validation (max 50MB suggested, configurable)
- [ ] 5.3 Implement file type validation (only .txt, .pdf, .docx allowed)
- [ ] 5.4 Add error handling for malformed/corrupted files

## 6. Input Validation

- [ ] 6.1 Add `validate_file_upload(file_path: str) -> bool` with size/type checks
- [ ] 6.2 Unit tests for validation (reject oversized files, unsupported formats)

## 7. Testing

- [ ] 7.1 Unit tests for text extraction (create sample .txt, .pdf, .docx test files)
- [ ] 7.2 Unit tests for chunking (boundary cases, empty documents)
- [ ] 7.3 Unit tests for metadata (verify position tracking accuracy)
- [ ] 7.4 Integration test: upload → extract → chunk → verify metadata
- [ ] 7.5 All tests passing, 80%+ code coverage

## 8. Documentation

- [ ] 8.1 Docstrings for all public functions
- [ ] 8.2 Brief README in `m_autofill/` explaining document processor API
