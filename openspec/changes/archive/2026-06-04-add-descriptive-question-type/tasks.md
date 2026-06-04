## 1. Data model

- [x] 1.1 Add `DESCRIPTIVE = "descriptive"` to `QuestionType` enum in `m_shared/models/question.py`
- [x] 1.2 Add model_validator to force `required=False` for descriptive questions
- [x] 1.3 Write unit tests for descriptive question creation and serialization

## 2. Adapters — import

- [x] 2.1 LimeSurvey: add `"X": QuestionType.DESCRIPTIVE` to `_LS_TYPE_MAP`
- [x] 2.2 Qualtrics: handle `DB` type in `_map_question_type()`
- [x] 2.3 SurveyMonkey: map `"presentation"` family to `QuestionType.DESCRIPTIVE` instead of `None`
- [x] 2.4 QTI: handle `<assessmentItem>` with `<itemBody>` but no interaction element
- [x] 2.5 Update adapter import tests for descriptive items

## 3. Adapters — export

- [x] 3.1 LimeSurvey: add `QuestionType.DESCRIPTIVE: "X"` to `_INTERNAL_TO_LS_TYPE`
- [x] 3.2 Qualtrics: add `QuestionType.DESCRIPTIVE: ("DB", "TB")` to `_EXPORT_TYPE`
- [x] 3.3 SurveyMonkey: add descriptive → `"presentation"` family mapping
- [x] 3.4 QTI: export descriptive items as `<assessmentItem>` with content-only `<itemBody>`

## 4. Cue — skip descriptive items

- [x] 4.1 Filter out `DESCRIPTIVE` items in batch suggest endpoint (before sending to RAG pipeline)
- [x] 4.2 Cue UI: render descriptive items as static text (no input, no suggestion zone)
- [x] 4.3 Filter out descriptive items in Cue UI batch builder

## 5. Shape — support descriptive blocks

- [x] 5.1 Add descriptive to conversation.py hardcoded type list
- [x] 5.2 Validation engine: already handles descriptive correctly (type guards skip non-matching types)
- [x] 5.3 Suggestion/tagging engines: already work automatically

## 6. Testing

- [x] 6.1 Round-trip test: import a survey with descriptive items, export, verify content preserved
- [x] 6.2 Smoke-test: import a real survey with descriptive blocks, review in Cue UI
- [x] 6.3 Verify no regressions in existing tests (1071/1071 pass)
