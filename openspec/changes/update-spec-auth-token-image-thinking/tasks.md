## 1. Spec delta authoring (all implementation already deployed)

- [x] 1.1 Write auth-security delta: REMOVE dev token, ADD api token endpoint, MODIFY env config
- [x] 1.2 Write document-ingestion delta: MODIFY multi-format upload, ADD image-to-text conversion
- [x] 1.3 Write llm-integration delta: ADD extended thinking budget

## 2. Validation

- [ ] 2.1 Run `openspec validate update-spec-auth-token-image-thinking --strict` and fix any issues

## 3. Archive

- [ ] 3.1 After approval, run `openspec archive update-spec-auth-token-image-thinking --yes`
- [ ] 3.2 Verify `openspec validate --strict` passes on updated specs
