# Improvement Plan

Goal: make the assistant produce consistently strong, honest, evidence-backed CVs and cover letters, with a simpler and more reliable architecture. Sections are done one at a time; each ends with passing tests.

## Status

| # | Section | Status |
|---|---------|--------|
| 1 | LLM layer hardening | Done (58 tests pass) |
| 2 | Strict matching (no silent fallback) | Done |
| 3 | Generate → verify → revise loop | Done (cover letter + CV tailoring agent, higher-quality extraction and mapping) |
| 4 | Application tracker (SQLite) | Done |
| 5 | Company research and voice profile | Done |
| 6 | ATS keyword coverage | Pending |
| 7 | Cleanup of duplicates | Pending |
| 8 | Evaluation tests | Pending |

## 1. LLM layer hardening
Files: `app/services/llm.py`, `app/services/generation.py`, `tests/test_llm_layer.py`
- Single shared OpenAI client with a 60 s timeout and 3 automatic retries (rate limits, timeouts, 5xx).
- One corrective retry when the model returns malformed JSON.
- In-memory cache of identical requests, so re-submitting the same job description is instant.
- `generation.py` reuses the shared client.
- Later follow-ups: schema-constrained outputs (Pydantic parsing) and per-stage models (`JD_MODEL`, `MATCHING_MODEL`, ... already exist in `config.py` but are unused).

## 2. Strict matching
Files: `app/services/matching_engine.py`
- Remove the silent token-overlap fallback in `match_job`. If AI matching fails, show a clear error, as job analysis already does.
- The local matcher remains available only as an explicit opt-in: `ALLOW_LOCAL_MATCHING=1`.

## 3. Generate → verify → revise loop
Files: `app/services/generation.py`, `app/services/cover_letter_engine.py`, `app/services/workflow.py`
- Draft the CV or letter, then run the existing fact validator and recruiter critique.
- If problems are found, revise automatically (max 2 rounds), then show the final text plus the remaining warnings.
- Biggest expected quality gain; most checkers already exist.

## 4. Application tracker
New: `app/services/tracker.py` (SQLite in `data/`)
- Store company, role, date, status, match score, job analysis, and paths to the CV and letter.
- UI: history list, reopen a past application, avoid duplicate work.

## 5. Company research and voice profile
- Fetch the company page or job posting; extract mission, products and stack; mark as `verified` with source URLs (the engine already accepts verified research only).
- Let the user save 2–3 past letters; feed them to `analyze_voice`.

## 6. ATS keyword coverage
- Compare required and preferred terms from the job against the final CV text; report missing keywords. Never suggest adding unsupported skills.

## 7. Cleanup
- Merge the duplicated PDF/TeX download branches in `app/flask_app.py`.
- Keep one API layer (Flask or FastAPI); drop or finish the MCP registry (`app/mcp/`) depending on whether an external agent will use it.
- Merge the overlapping docs (`ARCHITECTURE.md`, `PRODUCTION_PLAN.md`, `PROJECT_GUIDE.md`, `QUICKSTART.md`, `TUTORIAL.md`, `README.md`).

## 8. Evaluation tests
- Golden job descriptions with expected match types.
- Tests that the validator rejects invented claims and that the revise loop fixes them.

## Environment notes (macOS)
- Port 5000 is used by AirPlay Receiver; run with `--port 5001`.
- PDF export needs LaTeX: `brew install --cask basictex`, then `sudo tlmgr install latexmk enumitem fullpage marvosym titlesec preprint`.
- Start with: `.venv/bin/python start_services.py --port 5001` (with `/Library/TeX/texbin` on `PATH`).
