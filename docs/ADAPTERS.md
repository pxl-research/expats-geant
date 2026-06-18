# Writing a Custom Survey Adapter

This guide explains how to add support for a new survey platform by implementing
the `SurveyAdapter` interface.

## Overview

M-Shared ships with four built-in adapters:

| Format | Keys | Supports submission? | Supports creation? |
|---|---|---|---|
| LimeSurvey (LSS XML) | `"limesurvey"`, `"lss"` | Yes (RemoteControl 2 API) | Yes — pushes to live API, returns platform survey ID |
| Qualtrics (QSF JSON) | `"qualtrics"`, `"qsf"` | Yes (Response Import API v3) | Yes — pushes to live API, returns platform survey ID |
| SurveyMonkey (API v3 JSON) | `"surveymonkey"`, `"sm"` | No (requires paid plan) | File fallback — returns exported file content |
| QTI 3.0 (XML) | `"qti"` | No (interchange format) | File fallback — returns exported file content |

If your platform is not listed, you can write and register your own adapter in
a few steps.

---

## The Contract

All adapters extend `m_shared.adapters.base.SurveyAdapter` and implement three
abstract methods plus two optional methods:

```python
from m_shared.adapters.base import SurveyAdapter
from m_shared.models.response import Response
from m_shared.models.survey import Survey


class MySurveyAdapter(SurveyAdapter):

    def import_survey(self, raw: str) -> Survey:
        """Parse platform-specific content and return a Survey."""
        ...

    def export_survey(self, survey: Survey) -> str:
        """Serialize a Survey to the platform-specific format."""
        ...

    def capabilities(self) -> set[str]:
        """Declare which operations this adapter supports."""
        return {"import", "export"}  # add "submit", "create", "api_create" as appropriate

    # Optional — only override if the platform has a response write-back API
    def submit_responses(self, survey_id: str, responses: list[Response]) -> None:
        """Submit responses to the originating platform."""
        ...

    # Optional — only override if the platform supports survey creation
    def create_survey(self, survey: Survey) -> str:
        """Push survey to the platform API, or fall back to file export.

        Returns:
            str: Platform-assigned survey ID if the adapter pushes to a live API
                 (declare "api_create" in capabilities), or serialised file content
                 for file-fallback adapters (declare "create" only).
        """
        ...
```

Defined capability strings: `"import"`, `"export"`, `"submit"`, `"create"`, `"api_create"`.

- `"create"` — adapter implements `create_survey()`; may push to a platform API or fall back to file export
- `"api_create"` — `create_survey()` pushes to a live platform API and returns a platform ID (LimeSurvey, Qualtrics only); absent on file-fallback adapters (SurveyMonkey, QTI)

Callers use `capabilities()` to guard optional operations before calling them:

```python
adapter = get_adapter("myplatform")
if "submit" in adapter.capabilities():
    adapter.submit_responses(survey_id, responses)
if "create" in adapter.capabilities():
    result = adapter.create_survey(survey)
    if "api_create" in adapter.capabilities():
        platform_id = result      # e.g. "123456" — live survey created on platform
    else:
        file_content = result     # serialised file content for manual upload
```

---

## The `metadata` Convention

Every model (`Survey`, `Section`, `Question`, `AnswerOption`, `Response`) has a
`metadata: dict` field. Use it to preserve platform-specific fields that have no
counterpart in the common model. This ensures lossless round-trips when exporting
back to the same platform.

```python
question = Question(
    id=raw_q["id"],
    text=raw_q["title"],
    type=QuestionType.OPEN_ENDED,
    metadata={
        "myplatform_field": raw_q.get("some_custom_key"),
    },
)
```

On export, read `question.metadata` to recover those fields.

---

## Implementing `create_survey()`

`create_survey(survey: Survey) -> str` has two patterns depending on whether your
platform exposes a write API.

### API-push adapters (e.g. LimeSurvey, Qualtrics)

Push the survey to the platform and return the platform-assigned survey ID.
Declare both `"create"` and `"api_create"` in `capabilities()`.

```python
def capabilities(self) -> set[str]:
    return {"import", "export", "submit", "create", "api_create"}

def create_survey(self, survey: Survey) -> str:
    # translate Survey → platform payload, call platform API
    response = self._api_client.post("/surveys", payload)
    return response["id"]   # platform survey ID, e.g. "123456"
```

Return value: a non-empty string platform ID. Raise `RuntimeError` (or a
platform-specific exception) if the API call fails.

#### LimeSurvey specifics

Tested live against **LimeSurvey 6.17.4**. The adapter uses RC2 methods that
have been stable since LimeSurvey 3+ and are present on LimeSurvey 5+ and 6+:
`get_session_key`, `get_survey_properties`, `list_groups`, `list_questions`,
`get_question_properties`, `import_survey`, `add_response`,
`release_session_key`. We deliberately avoid `export_survey` and `add_question`
because LimeSurvey 6 removed them from the RC2 surface; pushing a full LSS via
`import_survey` is the canonical create path in LimeSurvey 6.

Required deployer configuration:

- **Configuration → Global settings → Interfaces → RPC interface = JSON-RPC**.
  XML-RPC will not work — the adapter speaks JSON only.
- Submit credentials may be supplied **per request** by the respondent (form
  fields on the survey page) or globally by the operator via the `LIMESURVEY_*`
  environment variables. The Cue API resolves credentials per-key with
  precedence body → env → none, mirroring `POST /surveys/import-from-api`.
  Per-request credentials are used for the one outbound platform call and
  never persisted.
- The user (whether supplied per request or via `LIMESURVEY_USERNAME`) must
  have permission to create, read, and submit responses to the surveys it
  will touch. On a single-tenant test instance the default admin is
  sufficient.

LimeSurvey versions older than 5 are best-effort: the RC2 surface is
compatible but we do not verify them in CI. Report issues if you hit one.

### File-fallback adapters (e.g. SurveyMonkey, QTI)

Delegate to `export_survey()` and return the serialised file content.
Declare `"create"` but **not** `"api_create"` in `capabilities()`.

```python
def capabilities(self) -> set[str]:
    return {"import", "export", "create"}

def create_survey(self, survey: Survey) -> str:
    return self.export_survey(survey)   # serialised XML/JSON for download
```

Return value: the same string `export_survey()` would return. The caller is
responsible for delivering the file to the user (e.g. as a download response).

### Choosing the right pattern

| Condition | Pattern | `"api_create"` in capabilities? |
|---|---|---|
| Platform has a write API and credentials are available | API-push | Yes |
| No write API, or write API not yet implemented | File fallback | No |

---

## Response Export (`"responses_export"` capability)

LimeSurvey and Qualtrics both expose a first-party file-based response
importer in their admin UIs — but **the file formats they accept are
platform-specific and not interchangeable** (LimeSurvey wants TSV in its
"VV" shape; Qualtrics wants a three-row CSV). Both importers are typically
usable on accounts where the platform's write API is locked down (no RC2 /
no API token), so adding the matching file-out path lets respondents close
the loop offline.

Override `export_responses(survey, responses) -> ResponseExport` on adapters
that support such an importer and add `"responses_export"` to
`capabilities()`. The returned `ResponseExport` is a NamedTuple of
`(content: bytes, media_type: str, filename_suffix: str)` so each adapter
declares its native format directly; the caller (Cue API endpoint) forwards
the media_type and filename suffix verbatim. The format must match the
platform's importer contract exactly — see the live-verification gotcha
note below.

| Platform | Format | Column shape |
|---|---|---|
| LimeSurvey | **TSV** in LS's "VV" shape (filename suffix `_vv.csv` — chosen to mirror LS's own `vvexport_{sid}.csv` naming; media type `text/tab-separated-values; charset=utf-8`). Two header rows: row 1 human display labels (ignored by the importer); row 2 column codes — fixed prefix `id, token, submitdate, lastpage, startlanguage, seed, startdate, datestamp` followed by one column per top-level question keyed by its `ls_qcode` and one column per M/P sub-question keyed `{qcode}_{sub_qcode}` (**underscore separator**). Empty cells use literal `{question_not_shown}`. | `id ... QM1 QM1_A1 QM1_A2 ...` (codes row) |
| Qualtrics  | **CSV** with BOM (filename suffix `.csv`, media type `text/csv; charset=utf-8`). Three header rows: row 1 column IDs (`StartDate`, `EndDate`, …, `QID<n>`, with `QID<n>_<choice_code>` per choice on multi-select), row 2 human-readable display labels, row 3 the per-column `{"ImportId":"…","timeZone":"UTC"}` JSON the importer keys on. | `QID1 QID2_1 QID2_2 ...` (row 1) |

Adapters that do not target such an importer (QTI, SurveyMonkey on the
tiers we support) MUST leave `export_responses` as the base
`NotImplementedError` default and MUST NOT advertise `"responses_export"`.

### LS gotcha — three incompatible response-format contracts

LimeSurvey has THREE incompatible response-format contracts that share no
parsing code on the LS side. Matching one does not imply matching another:

| Path | Column format | Sub-question separator |
|---|---|---|
| RC2 `add_response` (Submit) | `{sid}X{gid}X{qid}{sub_title}` (SGQA) | none — **no brackets** (issue #60) |
| CSV export (read-only) | `{qcode}[{sub_qcode}]`, semicolons | brackets |
| VV import (this method) | `{qcode}_{sub_qcode}`, TAB | underscore |

The LS adapter exposes `_sgqa_key` (for `submit_responses`) and
`export_responses` (for VV import) as two genuinely independent code
paths. Do not factor them together "because they look similar" — the
platform's contracts diverged on the LS side first.

### Data source

The Cue API endpoint `GET /sessions/{id}/responses/export?platform={fmt}`
builds the `list[Response]` from the session's persisted
`review_state.json` (the per-keystroke source of truth maintained by the
UI) and calls `export_responses`. There is no separate response-persistence
step — review state IS the persisted answer.

---

## Minimal Working Example

```python
"""Adapter for MyPlatform survey JSON format."""

import json

from m_shared.adapters.base import SurveyAdapter
from m_shared.models.answer_option import AnswerOption
from m_shared.models.question import Question, QuestionType
from m_shared.models.section import Section
from m_shared.models.survey import Survey


class MyPlatformAdapter(SurveyAdapter):

    def capabilities(self) -> set[str]:
        return {"import", "export"}

    def import_survey(self, raw: str) -> Survey:
        data = json.loads(raw)
        questions = [
            Question(
                id=q["id"],
                text=q["label"],
                type=QuestionType.OPEN_ENDED,
                required=q.get("required", False),
                answer_options=[],
                metadata={},
            )
            for q in data.get("questions", [])
        ]
        section = Section(id="s1", title="", questions=questions)
        return Survey(
            id=data["id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            sections=[section],
        )

    def export_survey(self, survey: Survey) -> str:
        questions = [
            {"id": q.id, "label": q.text, "required": q.required}
            for section in survey.sections
            for q in section.questions
        ]
        return json.dumps({"id": survey.id, "title": survey.title, "questions": questions})
```

Raise `ValueError` from `import_survey` if the raw content is invalid or missing
required fields.

---

## Registering Your Adapter

Edit `m_shared/adapters/registry.py` to add your adapter to the registry:

```python
def _build_registry() -> dict[str, type]:
    from m_shared.adapters.myplatform import MyPlatformAdapter
    # ... existing imports ...
    return {
        # ... existing entries ...
        "myplatform": MyPlatformAdapter,
        "mp": MyPlatformAdapter,   # optional short alias
    }
```

After registration, the adapter is accessible via the factory function:

```python
from m_shared.adapters import get_adapter

adapter = get_adapter("myplatform")
survey = adapter.import_survey(raw_json)
```

---

## Testing Your Adapter

Use `tests/test_adapters.py` as a reference. At minimum, test:

1. **Import** — valid input produces a correctly structured `Survey`
2. **Export** — a `Survey` round-trips back to a valid platform payload
3. **Capabilities** — `capabilities()` returns the expected set
4. **Error handling** — invalid input raises `ValueError`
5. **Create (if supported)** — `create_survey()` returns a platform ID (API-push) or file content (file-fallback)

```python
def test_import_survey():
    adapter = MyPlatformAdapter()
    survey = adapter.import_survey('{"id": "s1", "title": "Test", "questions": []}')
    assert survey.id == "s1"
    assert survey.title == "Test"

def test_capabilities():
    adapter = MyPlatformAdapter()
    assert adapter.capabilities() == {"import", "export"}

def test_import_invalid():
    adapter = MyPlatformAdapter()
    with pytest.raises(ValueError):
        adapter.import_survey("not valid json{{{")

# For API-push adapters — mock the HTTP call
def test_create_survey_api_push(requests_mock):
    requests_mock.post("https://platform/surveys", json={"id": "survey-abc"})
    adapter = MyApiPlatformAdapter(api_key="key")
    survey = Survey(id="s1", title="Test", description="", sections=[])
    result = adapter.create_survey(survey)
    assert result == "survey-abc"
    assert "api_create" in adapter.capabilities()

# For file-fallback adapters — no HTTP needed
def test_create_survey_file_fallback():
    adapter = MyFilePlatformAdapter()
    survey = Survey(id="s1", title="Test", description="", sections=[])
    result = adapter.create_survey(survey)
    assert isinstance(result, str) and len(result) > 0
    assert "api_create" not in adapter.capabilities()
    assert "create" in adapter.capabilities()
```

Run the suite:

```bash
source .venv/bin/activate
python3 -m pytest tests/test_adapters.py -v
```

---

## Reference

- Base class: [`m_shared/adapters/base.py`](../m_shared/adapters/base.py)
- Registry: [`m_shared/adapters/registry.py`](../m_shared/adapters/registry.py)
- Existing adapters: [`m_shared/adapters/`](../m_shared/adapters/)
- Data model: [`docs/DATA_MODEL.md`](DATA_MODEL.md)
- Tests: [`tests/test_adapters.py`](../tests/test_adapters.py)
