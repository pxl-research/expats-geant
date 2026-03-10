# Writing a Custom Survey Adapter

This guide explains how to add support for a new survey platform by implementing
the `SurveyAdapter` interface.

## Overview

M-Shared ships with four built-in adapters:

| Format | Keys | Supports submission? |
|---|---|---|
| LimeSurvey (LSS XML) | `"limesurvey"`, `"lss"` | Yes (RemoteControl 2 API) |
| Qualtrics (QSF JSON) | `"qualtrics"`, `"qsf"` | Yes (Response Import API v3) |
| SurveyMonkey (API v3 JSON) | `"surveymonkey"`, `"sm"` | No (requires paid plan) |
| QTI 3.0 (XML) | `"qti"` | No (interchange format) |

If your platform is not listed, you can write and register your own adapter in
a few steps.

---

## The Contract

All adapters extend `m_shared.adapters.base.SurveyAdapter` and implement three
abstract methods plus one optional method:

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
        return {"import", "export"}  # add "submit" if submit_responses is implemented

    # Optional — only override if the platform has a response write-back API
    def submit_responses(self, survey_id: str, responses: list[Response]) -> None:
        """Submit responses to the originating platform."""
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
    order=position,
    metadata={
        "myplatform_field": raw_q.get("some_custom_key"),
    },
)
```

On export, read `question.metadata` to recover those fields.

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
                order=i,
                required=q.get("required", False),
                answer_options=[],
                metadata={},
            )
            for i, q in enumerate(data.get("questions", []))
        ]
        section = Section(id="s1", title="", order=0, questions=questions)
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
