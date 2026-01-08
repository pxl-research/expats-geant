# Implementation Tasks: setup-data-models

## 1. Core Model Implementation

- [ ] 1.1 Create `m_shared/models/__init__.py` with module exports
- [ ] 1.2 Implement Survey model with sections array and metadata
- [ ] 1.3 Implement Section model with title, description, and questions array
- [ ] 1.4 Implement Question model with type support (multiple_choice, single_choice, open_ended, ranking, slider)
- [ ] 1.5 Implement AnswerOption model for question choices
- [ ] 1.6 Implement Response model with question_id, answer_value, timestamp
- [ ] 1.7 Implement Citation model with source tracking and highlights
- [ ] 1.8 Implement Session model with TTL and expiration logic

## 2. Validation & Serialization

- [ ] 2.1 Add Pydantic validators for all models
- [ ] 2.2 Implement JSON schema generation for API docs
- [ ] 2.3 Test serialization/deserialization round-trips

## 3. Unit Tests

- [ ] 3.1 Create `tests/test_models.py`
- [ ] 3.2 Test Survey model creation ansixlidation
- [ ] 3.3 Test Question model with all four question types
- [ ] 3.4 Test Response model with various answer types
- [ ] 3.5 Test Citation model with source metadata
- [ ] 3.6 Test Session model with TTL calculation
- [ ] 3.7 Run tests and verify 100% passing

## 4. Documentation

- [ ] 4.1 Add docstrings to all models
- [ ] 4.2 Include usage examples in module docstring
