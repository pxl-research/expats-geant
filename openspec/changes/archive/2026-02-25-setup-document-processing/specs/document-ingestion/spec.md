# Capability: Document Ingestion

Upload, parse, and prepare documents for semantic search and answer suggestion.

## ADDED Requirements

### Requirement: Multi-Format Document Upload

The system SHALL accept documents in common formats for M-Autofill sessions.

#### Scenario: Upload text file

- **WHEN** a .txt file is uploaded
- **THEN** the file is stored and queued for text extraction

#### Scenario: Upload PDF document

- **WHEN** a .pdf file is uploaded
- **THEN** the file is stored and queued for text extraction via MarkItDown

#### Scenario: Upload Word document

- **WHEN** a .docx file is uploaded
- **THEN** the file is stored and queued for text extraction via MarkItDown

#### Scenario: Reject unsupported format

- **WHEN** a file with unsupported extension is uploaded
- **THEN** the system rejects the upload with clear error message

#### Scenario: Reject oversized file

- **WHEN** a file exceeds the size limit (default 50MB)
- **THEN** the system rejects the upload with clear error message

### Requirement: Text Extraction

The system SHALL extract readable text from uploaded documents with position metadata.

#### Scenario: Extract text from PDF

- **WHEN** PDF text extraction completes
- **THEN** text is returned with position metadata (page number, position offset)

#### Scenario: Extract text from Word doc

- **WHEN** Word document extraction completes
- **THEN** text is returned with position metadata (paragraph number, section)

#### Scenario: Extract text from plain text

- **WHEN** a .txt file is extracted
- **THEN** text is returned with line number metadata

### Requirement: Document Chunking

The system SHALL split extracted text into chunks suitable for embedding and semantic search.

#### Scenario: Chunk text by sentence boundaries

- **WHEN** text is chunked
- **THEN** chunks respect sentence/paragraph boundaries (not mid-word splits)

#### Scenario: Configurable chunk strategy

- **WHEN** chunking parameters are specified (size, overlap)
- **THEN** documents are split according to those parameters while respecting boundaries

### Requirement: Metadata Tagging

The system SHALL preserve document metadata for citation accuracy.

#### Scenario: Store chunk metadata

- **WHEN** a chunk is created
- **THEN** it retains source filename, position/percentage, timestamp, and original document reference

#### Scenario: Map chunk positions

- **WHEN** a chunk is stored
- **THEN** its position in the original document is tracked (page numbers, section indices, line offsets)

### Requirement: Session Document Association

The system SHALL associate uploaded documents with user sessions.

#### Scenario: Documents isolated per session

- **WHEN** documents are uploaded for a session
- **THEN** they are associated with that session ID and deleted when session expires

## Notes

- MVP scope: Text, PDF, DOCX formats only (no audio/video transcription yet)
- Uses MarkItDown library for text extraction
- Documents processed immediately after upload; original files discarded after chunking
- Located in `m_autofill/document_processor.py`
- Dependencies: Phase 1 data models (Session, Citation)
