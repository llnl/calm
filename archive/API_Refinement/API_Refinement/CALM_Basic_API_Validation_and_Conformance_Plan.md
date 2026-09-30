# CALM Basic API Validation and Conformance Plan

Status: draft

Purpose
- Define the tests, documentation gates, and review requirements that determine when a roadmap item can be marked implemented.

Gates
- Code: conforming code must pass unit tests and linters.
- Tests: each implemented item must include unit tests covering normal and edge cases. Integration tests are required for cross-module workflows.
- Docs: BASIC_API_Reference and User Guide must include updated examples and API signatures for the feature.
- Review: PR must be approved by at least one API owner and pass CI.

Test categories
- Unit tests: isolated pure-Python logic, mocking external services.
- Integration tests: exercising multiple modules inside a temporary project workspace.
- Regression tests: capture previously failing edge cases.

CI integration
- Tests should be organized so fast unit tests run in the first job and longer integration tests in a separate job.

Conformance checklist for marking an item implemented
- [ ] Code committed and PR opened
- [ ] Unit tests added and passing
- [ ] Integration tests added (if applicable) and passing
- [ ] Documentation updated (Reference + User Guide)
- [ ] PR approved by API owner

Appendix: example minimal test matrix for Registry Search
- Unit: query translation, error handling (fast)
- Integration: run search against a local mocked registry and assert returned MatchSearchResult fields preserved (slow)
