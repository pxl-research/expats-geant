## 1. Spec Updates
- [x] 1.1 Update questionnaire-design spec (adapter pattern, platform support)
- [x] 1.2 Update data-models spec (formalize common denominator intent)
- [x] 1.3 Add capability discovery and submit_responses to questionnaire-design spec

## 2. Implementation (Phase 4)
- [x] 2.1 Create `m_shared/adapters/` package with base `SurveyAdapter` abstract class
          — `import_survey()`, `export_survey()`, `capabilities()`, `submit_responses()` (raises NotImplementedError)
- [x] 2.2 Implement `m_shared/adapters/limesurvey.py` (PRIMARY)
          — import: LSS/XML parse; export: serialize to LSS; submit: RemoteControl 2 `add_response`
- [x] 2.3 Implement `m_shared/adapters/qualtrics.py` (PRIMARY)
          — import: QSF parse; export: serialize to QSF; submit: Qualtrics Response Import API
- [x] 2.4 Implement `m_shared/adapters/qti.py` (SECONDARY — import/export only)
- [x] 2.5 Implement `m_shared/adapters/surveymonkey.py` (SECONDARY — import/export only)
- [x] 2.6 Add adapter selection logic (registry pattern: format string → adapter class)
- [x] 2.7 Write unit tests per adapter (import round-trip; export round-trip)
- [x] 2.8 Write unit tests for submit_responses (LimeSurvey + Qualtrics, mock API)
- [x] 2.9 Write unit test: capability discovery returns correct sets per adapter
- [x] 2.10 Write integration test: import from platform A → export to platform B
