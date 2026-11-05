# ORBIT hardening release notes

## Changes in this package

- Removed the nested duplicate `orbit-analytics-agent/` tree so the repository has one canonical project root.
- Excluded Git internals, virtual environments, caches, generated build output, and local dependency folders from the release archive.
- Frontend API base is configurable with `VITE_API_URL`; the default uses same-origin `/api` requests.
- Added a Vite development proxy for `/api` and a Docker Nginx reverse proxy for `/api`.
- Made FastAPI CORS origins configurable with `ORBIT_CORS_ORIGINS`.
- Added additional SQL validation regression tests for unknown columns, external database references, row limits, and oversized prompts.
- Changed CI frontend dependency installation to `npm ci` for lockfile-based reproducibility.
- Updated the README with accurate product scope, local run instructions, Docker instructions, environment variables, and security limitations.

## Explicitly not claimed as complete

- Authentication, role-based authorization, tenant isolation, and persistent audit logs are not implemented.
- The deterministic planner still supports a bounded set of natural-language analytics intents; Ollama is used for optional insight wording, not arbitrary SQL generation.
- This package has not been load-tested or deployed to a production environment.
- Build/test commands must be run in the recipient's environment. The current packaging environment had no network access to install the pinned dependencies, so fresh backend pytest and frontend npm build could not be executed here.
