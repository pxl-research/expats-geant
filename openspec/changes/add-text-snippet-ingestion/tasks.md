## 1. Backend — ingestion helper
- [ ] 1.1 Add `ingest_text_into_store` to `m_autofill/ingest.py`: accepts `text: str`, `label: str`, and the usual `store`/`session_id`/`user_id`/`audit_logger` kwargs; chunks and embeds the text with `source=label` metadata

## 2. Backend — API endpoint
- [ ] 2.1 Add `UploadTextRequest` Pydantic model (fields: `text: str`, `label: str | None`) to `m_autofill/api.py` or models file
- [ ] 2.2 Add `POST /upload-text` endpoint to `m_autofill/api.py`: validate non-empty text (400 if blank), call `ingest_text_into_store`, return `UploadResponse`

## 3. UI — API client
- [ ] 3.1 Add `ingest_text_snippet(token, session_id, text, label)` method to `m_ui/api_client.py` calling `POST /upload-text`

## 4. UI — documents page
- [ ] 4.1 Add textarea + optional label input to `documents.html` below the file picker
- [ ] 4.2 Update `POST /session/{session_id}/documents` in `router.py` to read the text field and call `api_client.ingest_text_snippet` when non-empty; preserve existing file-upload logic

## 5. Tests
- [ ] 5.1 Unit tests for `ingest_text_into_store` (chunking, metadata, deduplication by label)
- [ ] 5.2 API integration tests for `POST /upload-text` (success, empty-text 400, unauthenticated 401)
