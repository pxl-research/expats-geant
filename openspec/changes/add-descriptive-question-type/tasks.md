## 1. Data model

- [ ] 1.1 Add `DESCRIPTIVE = "descriptive"` to `QuestionType` enum in `m_shared/models/question.py`
- [ ] 1.2 Update validators: ensure descriptive questions pass without answer_options or min/max
- [ ] 1.3 Write unit tests for descriptive question creation and serialization

## 2. Adapters — import

- [ ] 2.1 LimeSurvey: add `"X": QuestionType.DESCRIPTIVE` to `_LS_TYPE_MAP`
- [ ] 2.2 Qualtrics: handle `DB` type in `_map_question_type()`
- [ ] 2.3 SurveyMonkey: map `"presentation"` family to `QuestionType.DESCRIPTIVE` instead of `None`
- [ ] 2.4 QTI: handle `<assessmentItem>` with `<itemBody>` but no interaction element
- [ ] 2.5 Write/update adapter import tests for descriptive items

## 3. Adapters — export

- [ ] 3.1 LimeSurvey: add `QuestionType.DESCRIPTIVE: "X"` to `_INTERNAL_TO_LS_TYPE`
- [ ] 3.2 Qualtrics: add `QuestionType.DESCRIPTIVE: ("DB", "TB")` to `_EXPORT_TYPE`
- [ ] 3.3 SurveyMonkey: add descriptive → `"presentation"` family mapping
- [ ] 3.4 QTI: export descriptive items as `<assessmentItem>` with content-only `<itemBody>`
- [ ] 3.5 Write/update adapter export tests for descriptive items

## 4. Cue — skip descriptive items

- [ ] 4.1 Filter out `DESCRIPTIVE` items in batch suggest endpoint (before sending to RAG pipeline)
- [ ] 4.2 Cue UI: render descriptive items as static text (no input, no suggestion zone)
- [ ] 4.3 Write tests for skip behavior

## 5. Shape — support descriptive blocks

- [ ] 5.1 Update suggestion engine: allow LLM to generate descriptive blocks
- [ ] 5.2 Update validation engine: skip question-specific rules for descriptive items
- [ ] 5.3 Update Shape UI survey preview to render descriptive blocks as text
- [ ] 5.4 Write tests for Shape engine behavior with descriptive items

## 6. Testing

- [ ] 6.1 Round-trip test: import a survey with descriptive items, export, verify content preserved
- [ ] 6.2 Smoke-test: import a real survey with descriptive blocks, review in Cue UI
- [ ] 6.3 Verify no regressions in existing tests
