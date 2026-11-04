# Architecture decisions

- **Deterministic demo first:** reproducible and API-key-free baseline before LLM integrations.
- **SQLite synthetic warehouse:** simple local setup; not intended for concurrent production use.
- **Read-only execution:** SELECT-only validation, schema allow-list, read-only connection and query-only mode. Not a substitute for a hardened SQL sandbox.
- **Thin frontend:** React renders the workflow and results; business logic stays in independently testable FastAPI backend.
