# Professionalization Plan

## Product direction

This project will remain **local-first and database-free**.

Each friend gets their own copy of the application, their own `.env`, candidate profile, generated documents, and local application files. The project is not planned as a shared multi-user SaaS application. That means we do not need accounts, PostgreSQL, cloud storage, or a hosted application database for the target use case.

If the project later becomes a shared public web service, that should be treated as a separate product and architecture decision.

## Definition of production-ready for this project

A friend should be able to:

1. Clone the GitHub repository.
2. Install the dependencies with one documented command.
3. Create a private `.env` file.
4. Start the application with one command.
5. Open the dashboard locally.
6. Add or edit their own profile.
7. Analyze a job description.
8. Review and select skills.
9. Generate and download a CV and cover letter.
10. Run the tests and understand common failures.

The project should be safe, predictable, documented, and easy to maintain without introducing unnecessary infrastructure.

## Phase 1: Remove unnecessary infrastructure

Goal: make the application genuinely database-free.

- Replace database-backed application history with local JSON or filesystem metadata only if history is still needed.
- Otherwise remove the unused database module, SQLAlchemy dependency, database configuration, database routes, and database documentation.
- Keep generated artifacts under the local `data/applications/` directory.
- Add a clear reset/export workflow for local files.
- Ensure every friend has an isolated local profile and output directory.

Acceptance criteria:

- A clean installation does not create `applications.db`.
- The application starts without SQLAlchemy.
- CV, cover-letter, and analysis workflows still work.
- Tests do not require a database.

## Phase 2: Installation and configuration quality

Goal: make setup reliable for non-developers.

- Keep `.env.example` minimal and accurate.
- Add a setup script or Makefile with `install`, `run`, `test`, and `clean` commands.
- Add a supported Python version and dependency policy.
- Add startup validation with friendly messages for missing dependencies or API keys.
- Document optional LaTeX/PDF installation for Linux, macOS, and Windows.
- Add a version display in the UI and API health response.

Acceptance criteria:

- A new user can follow `QUICKSTART.md` without guessing.
- Startup failures explain exactly how to fix them.
- The supported commands are tested in CI.

## Phase 3: Professional code quality

Goal: make future changes safe.

- Add Ruff for linting and formatting.
- Add type checking with Pyright or mypy.
- Add pre-commit hooks.
- Remove dead code and unused imports.
- Standardize error types and user-facing errors.
- Add return types and docstrings to public service functions.
- Keep Flask/FastAPI routes thin and reusable logic in `app/services/`.

Acceptance criteria:

- Formatting, linting, and tests pass locally and in CI.
- No unused deprecated runtime remains.
- New behavior has focused regression coverage.

## Phase 4: Test and release confidence

Goal: prove the complete local workflow.

- Keep unit tests for matching, prompts, validation, and CV generation.
- Add integration tests for dashboard analysis, selection, cover-letter generation, and downloads.
- Add tests for empty profiles, missing skills, familiarity, transferable evidence, malformed job descriptions, and missing API keys.
- Add tests for safe file names and output directories.
- Add a GitHub Actions workflow for tests and quality checks.
- Add a release checklist and semantic versioning.

Acceptance criteria:

- CI passes on every pull request.
- A tagged release has a tested installation path.
- The release notes describe user-visible changes.

## Phase 5: Privacy and safe local use

Goal: protect each user's personal application data.

- Keep `.env`, profiles, databases, generated applications, and PDF build artifacts ignored.
- Add a visible privacy notice explaining that AI features send job/profile context to the configured provider.
- Add a “delete local application data” instruction.
- Avoid logging profile content, job descriptions, API keys, or generated letters.
- Add input-size limits and request timeouts for AI calls.
- Preserve human review before documents are submitted.

Acceptance criteria:

- A user can identify what leaves the machine.
- No private files are included in Git commits.
- Long or failed AI requests fail gracefully.

## Phase 6: Usability and presentation

Goal: make the project feel professional to friends and contributors.

- Improve first-run empty states.
- Add clear progress and error messages.
- Add a profile editor guide and example profile template.
- Add generated-document preview and review instructions.
- Add accessible labels, keyboard-friendly controls, and responsive styling.
- Add screenshots or a short demo GIF to the GitHub README.
- Add a concise contribution guide.
- Add a changelog.

Acceptance criteria:

- A first-time user understands the workflow without personal help.
- A generated document can be reviewed and downloaded without confusion.
- GitHub visitors can understand the project in under two minutes.

## Proposed delivery order

1. Remove the database dependency and decide whether local history is needed.
2. Add one-command setup/run/test commands.
3. Add linting, type checking, and GitHub Actions.
4. Improve startup errors and privacy messaging.
5. Add end-to-end workflow tests.
6. Improve UI polish and add screenshots.
7. Release version `0.1.0` with a tested friend-installation guide.

## Explicit non-goals

For the current product direction, do not add:

- User accounts
- Shared online profiles
- PostgreSQL
- Cloud object storage
- Multi-tenant authorization
- A hosted public service

Those are only required if the project changes from “each friend runs their own private local copy” to “many users share one hosted instance.”
