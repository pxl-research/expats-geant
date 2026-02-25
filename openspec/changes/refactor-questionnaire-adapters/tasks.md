## 1. Spec Updates
- [x] 1.1 Update questionnaire-design spec (adapter pattern, platform support)
- [x] 1.2 Update data-models spec (formalize common denominator intent)

## 2. Implementation (Phase 4)
- [ ] 2.1 Create `m_chat/adapters/` package with base `SurveyAdapter` abstract class
- [ ] 2.2 Implement `m_chat/adapters/qti.py` (QTI 3.0 import/export)
- [ ] 2.3 Implement `m_chat/adapters/limesurvey.py` (LimeSurvey JSON/LSS import/export)
- [ ] 2.4 Implement `m_chat/adapters/qualtrics.py` (Qualtrics QSF import/export)
- [ ] 2.5 Implement `m_chat/adapters/surveymonkey.py` (SurveyMonkey JSON import/export)
- [ ] 2.6 Add adapter selection logic to `m_chat/api.py` (detect format or accept explicit param)
- [ ] 2.7 Write unit tests per adapter (round-trip: internal → platform → internal)
- [ ] 2.8 Write integration test: import from platform A → export to platform B
