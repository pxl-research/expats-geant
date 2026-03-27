## MODIFIED Requirements

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

## ADDED Requirements

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
