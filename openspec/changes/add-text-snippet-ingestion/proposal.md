# Change: Add Direct Text Snippet Ingestion

## Why
Users may have relevant personal information or content copied from a webpage that they want
to use as context for answer suggestions. Requiring them to create a file first adds friction;
accepting a plain-text string directly lowers the barrier without any new dependencies.

## What Changes
- New `POST /upload-text` endpoint in m-autofill accepting a JSON body `{text, label?}`
- New `ingest_text_into_store` helper in `m_autofill/ingest.py` (parallel to existing `ingest_files_into_store`, bypasses file I/O)
- New `ingest_text_snippet` method in `m_ui/api_client.py`
- Textarea added to the documents page (`documents.html` + `router.py`) so users can type or paste text alongside (or instead of) file uploads

## Impact
- Affected specs: `document-ingestion`, `survey-ui`
- Affected code: `m_autofill/api.py`, `m_autofill/ingest.py`, `m_ui/router.py`, `m_ui/api_client.py`, `m_ui/templates/documents.html`
- No breaking changes; file upload path is unchanged
