# Refactor plan: Flask + FastAPI + MCP

## Target architecture

This project will evolve into a layered application:

- Flask web app: user-facing interface and browser routes
- FastAPI MCP service: typed tool layer for business actions
- Shared service layer: current logic extracted from Streamlit and existing service modules
- Local storage: current JSON profile + SQLite application records + generated files

## Goals

1. Remove the Streamlit-only orchestration dependency.
2. Keep the current evidence-first business rules.
3. Preserve the current app workflows: profile, job analysis, matching, CV generation, application storage.
4. Make the system tool-based and extensible via MCP.

## Phase 1: boundary extraction

- Keep current domain models in `app/models/schemas.py`.
- Move route logic out of Streamlit and into service functions.
- Define clear responsibilities:
  - profile management
  - job analysis
  - requirement matching
  - CV generation
  - export / PDF compilation

## Phase 2: create API layers

### Flask layer
- Handles browser / UI requests.
- Exposes routes for page rendering and JSON endpoints.
- Calls the service layer, not external logic directly.

### FastAPI MCP layer
- Exposes typed MCP tools.
- Tool names map to business capabilities.
- Returns JSON dictionaries or pydantic models.

## Phase 3: MCP tool registry

Each tool should accept explicit input and return structured output. Example tool categories:

- `profile_tools.get_profile`
- `profile_tools.save_profile`
- `job_tools.analyze_job`
- `match_tools.match_job`
- `cv_tools.generate_cv_tex`
- `document_tools.compile_pdf`
- `application_tools.save_application`

## Phase 4: migration rules

- Keep existing service behavior until the new architecture is proven.
- Do not rewrite the entire project in one pass.
- Migrate one workflow at a time: profile -> job -> match -> CV -> export -> application history.
- Keep compatibility with current data and generated artifacts.

## Initial files to scaffold

- `app/api/flask_routes/`
- `app/api/fastapi_mcp/server.py`
- `app/api/fastapi_mcp/tools/`
- `app/mcp/registry.py`
- `app/services/` as the shared business layer
- `app/repositories/` for profile/application storage access

## Recommended deployment stance

For now, use local single-machine deployment with:

- Flask for UI/API
- FastAPI MCP for tool access
- SQLite for application records
- JSON files for profile persistence
- generated output folders for CV and PDF artifacts

## Current implementation status

The Flask dashboard is the primary web application. Shared application services now coordinate the dashboard and Flask document routes:

- `ApplicationWorkflowService` handles analysis-state restoration and CV generation.
- `CoverLetterService` handles cover-letter generation and advisory checks.
- `DocumentExportService` handles company-named LaTeX, PDF, and text exports.

FastAPI/MCP remains a thin typed adapter over the shared services. `streamlit_app.py` is deprecated and retained only as a historical reference.
