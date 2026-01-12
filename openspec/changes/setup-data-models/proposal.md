# Change: Setup Core Data Models

## Why

The foundation of both M-Chat and M-Autofill requires shared domain models for surveys, questions, responses, citations, and user sessions. These models define the shape of data flowing through the system and enable clear contracts between modules.

## What Changes

- Implement Pydantic models for Survey, Section, Question, Response, Citation, and Session in `m_shared/models/`
- Add comprehensive unit tests for model validation and serialization
- Support five core QTI 3.0-compatible question types: multiple_choice, single_choice, open_ended, ranking, slider
- Enable JSON schema generation for API documentation

## Impact

- Affected specs: [data-models](../../specs/data-models/spec.md)
- Affected code: `m_shared/models/` (new module)
- Downstream impact: Required by [setup-llm-integration](../setup-llm-integration/) and [setup-jwt-auth](../setup-jwt-auth/) proposals
- No breaking changes

## Timeline

- Estimated effort: 8-12 hours
- Milestone: Phase 1 foundation layer
