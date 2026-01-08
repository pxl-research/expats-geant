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
- **THEN** the file is stored and queued for text extraction via PDF parser

#### Scenario: Upload Word document

- **WHEN** a .docx file is uploaded
- **THEN** the file is stored and queued for text extraction

### Requirement: Text Extraction

The system SHALL extract readable text from uploaded documents.

#### Scenario: Extract text from PDF

- **WHEN** PDF text extraction completes
- **THEN** text is returned with position metadata (page number, approximate position)

#### Scenario: Extract text from Word doc

- **WHEN** Word document extraction completes
- **THEN** text is returned with position metadata (paragraph number, section)

### Requirement: Document Chunking

The system SHALL split extracted text into chunks suitable for embedding.

#### Scenario: Chunk text by sentence boundaries

- **WHEN** text is chunked
- **THEN** chunks respect sentence/paragraph boundaries (not mid-word splits)

### Requirement: Metadata Tagging

The system SHALL preserve document metadata for citation accuracy.

#### Scenario: Store chunk metadata

- **WHEN** a chunk is created
- **THEN** it retains source filename, position/percentage, timestamp, and optional highlights

### Requirement: Session Document Association

The system SHALL associate uploaded documents with user sessions.

#### Scenario: Documents isolated per session

- **WHEN** documents are uploaded for a session
- **THEN** they are stored only for that session and deleted when session expires

## Notes

- MVP scope: Text, PDF, DOCX formats only (no audio/video transcription yet)
- Uses MarkItDown or similar library for text extraction
- Documents stored temporarily during session, deleted on cleanup
- Located in `m_autofill/document_processor.py`
