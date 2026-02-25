# Implementation Tasks: setup-data-models

## 1. Core Model Implementation

- [x] 1.1 Create `m_shared/models/__init__.py` with module exports
- [x] 1.2 Implement Survey model with sections array and metadata
- [x] 1.3 Implement Section model with title, description, and questions array
- [x] 1.4 Implement Question model with type support (multiple_choice, single_choice, open_ended, ranking, slider)
- [x] 1.5 Implement AnswerOption model for question choices
- [x] 1.6 Implement Response model with question_id, answer_value, timestamp
- [x] 1.7 Implement Citation model with source tracking and highlights
- [x] 1.8 Implement Session model with TTL and expiration logic

## 2. Validation & Serialization

- [x] 2.1 Add Pydantic validators for all models
- [x] 2.2 Implement JSON schema generation for API docs
- [x] 2.3 Test serialization/deserialization round-trips

## 3. Unit Tests

- [x] 3.1 Create `tests/test_models.py`
- [x] 3.2 Test Survey model creation and validation
- [x] 3.3 Test Question model with all five question types
- [x] 3.4 Test Response model with various answer types
- [x] 3.5 Test Citation model with source metadata
- [x] 3.6 Test Session model with TTL calculation
- [x] 3.7 Run tests and verify 100% passing

## 4. Documentation

- [x] 4.1 Add docstrings to all models
- [x] 4.2 Include usage examples in module docstring
