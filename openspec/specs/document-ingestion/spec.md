# Capability: Document Ingestion

## Purpose

Upload, parse, and prepare documents for semantic search and answer suggestion.
## Requirements
### Requirement: Multi-Format Document Upload

The system SHALL accept documents in common formats for Cue sessions. Supported formats
are: `.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, and images
(`.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`).

#### Scenario: Upload text file

- **WHEN** a `.txt` or `.md` file is uploaded
- **THEN** the file is stored and queued for text extraction

#### Scenario: Upload PDF document

- **WHEN** a `.pdf` file is uploaded
- **THEN** the file is stored and queued for text extraction via PDF parser

#### Scenario: Upload Word document

- **WHEN** a `.docx` file is uploaded
- **THEN** the file is stored and queued for text extraction

#### Scenario: Upload Office document

- **WHEN** a `.pptx`, `.xlsx`, or `.xls` file is uploaded
- **THEN** the file is stored and queued for text extraction

#### Scenario: Upload image file

- **WHEN** a `.jpg`, `.jpeg`, `.png`, `.gif`, or `.webp` file is uploaded
- **THEN** the file is queued for LLM-based image-to-text conversion before ingestion

#### Scenario: Reject unsupported format

- **WHEN** a file with an unsupported extension is uploaded
- **THEN** the request is rejected with HTTP 400 and a list of allowed extensions is returned

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

### Requirement: Direct Text Snippet Ingestion

The system SHALL accept a plain-text or markdown string via `POST /upload-text` as an
alternative to file upload and ingest it into the session RAG store.

The request body SHALL contain a non-empty `text` field and an optional `label` field used
as the source identifier in chunk metadata (defaults to `"pasted text"` when omitted).

#### Scenario: Ingest valid text snippet

- **WHEN** a non-empty `text` string is submitted to `POST /upload-text`
- **THEN** the text is chunked, embedded, and stored in the session vector store
- **AND** each chunk carries `source` metadata equal to the provided or default label

#### Scenario: Reject empty text

- **WHEN** the `text` field is empty or contains only whitespace
- **THEN** a 400 Bad Request error is returned

#### Scenario: Duplicate label is skipped

- **WHEN** a snippet with the same label already exists in the session store
- **THEN** the submission is silently skipped (consistent with file deduplication behaviour)

### Requirement: Image-to-Text Conversion

The system SHALL convert uploaded image files to Markdown text descriptions using an LLM
before chunking and ingestion. The LLM prompt SHALL request a detailed description in
English using Markdown format. If no LLM client is configured, image files SHALL be
skipped with a warning and SHALL NOT cause an error for the overall upload request.

#### Scenario: Image ingested via LLM description

- **WHEN** an image file is uploaded and an LLM client is available
- **THEN** the image is passed to the LLM with a description prompt
- **AND** the returned Markdown text is chunked and stored in the session vector store
- **AND** chunk metadata records the original image filename as the source

#### Scenario: Image skipped without LLM client

- **WHEN** an image file is uploaded and no LLM client is configured
- **THEN** the image is skipped
- **AND** a warning is logged
- **AND** the remaining files in the upload batch continue to be processed normally

## Notes

- MVP scope: Text, PDF, DOCX formats only (no audio/video transcription yet)
- Uses MarkItDown or similar library for text extraction
- Documents stored temporarily during session, deleted on cleanup
- Located in `cue_api/document_processor.py`
