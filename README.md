# Job Application Engine

A local-first, evidence-led job application assistant. Flask is the primary browser application. FastAPI provides a thin typed MCP/tooling layer, while the core matching, document generation, and profile logic stays shared and reusable.

Use the Flask dashboard at `http://127.0.0.1:5000/dashboard`. FastAPI provides typed API and MCP access.

New here? Start with the [Quick start](QUICKSTART.md), then use the [project guide](PROJECT_GUIDE.md) for architecture, workflows, privacy, and troubleshooting.

## Start locally

Requires Python 3.12+. Create a virtual environment, install `requirements.txt`, then run:

```bash
python main.py --mode all
```

Or run the services separately:

```bash
python app/flask_app.py --port 5000
python -m uvicorn app.api.fastapi_mcp.server:app --host 0.0.0.0 --port 8000
```

Copy `.env.example` to `.env` and set `OPENAI_API_KEY` for AI job-description extraction, evidence matching, and role-specific cover-letter generation. Job extraction is AI-only: if the key is missing or the provider is unavailable, the app reports an error instead of silently switching to regex/keyword extraction. Evidence matching may still use its local fallback. Install `latexmk` or `pdflatex` to compile downloadable CV PDFs.

## Candidate profile

On first launch, an empty `data/candidate_profile.json` is created. Edit the profile either in the Flask dashboard or directly in the JSON file, then save. The profile is the source of truth; keep only accurate details and label studied skills as `FAMILIARITY`. Example skill:

```json
{"name":"SysML","status":"FAMILIARITY","evidence":["Completed introductory coursework"]}
```

Profile data, generated documents, and the SQLite database are stored locally. When AI-assisted analysis or cover-letter generation is used, job text and relevant candidate profile evidence are sent to the configured OpenAI API. `data/applications/`, `.env`, and database files are ignored by Git. Do not commit private application materials.

## Current MVP behavior

- Job descriptions are extracted with the configured OpenAI model. Extraction failures are visible and do not silently produce keyword-parser results. Evidence matching may use its local fallback if AI matching is unavailable.
- Requirements are compared against profile skills, experience, and projects. The AI classifier must cite profile evidence for VERIFIED or TRANSFERABLE matches; familiarity and unsupported gaps remain visibly labeled.
- The human review panel focuses on technical skills, tools, and engineering domains. General soft skills such as communication and teamwork are excluded from technical CV selection.
- A CV is rendered from profile evidence. Selected requirements determine skill placement and prioritize relevant experience; unsupported requirements can be added explicitly as skills when the user chooses them. Existing experience wording is preserved while relevant bullets are prioritized.
- Each analyzed application is recorded in SQLite. Generated reports include the job text, typed analyses, learning plan, and change log.
- The API is available at `/docs` when running FastAPI.

## Documentation

- [Quick start](QUICKSTART.md): install and run the application.
- [Project guide](PROJECT_GUIDE.md): architecture, workflows, privacy, testing, and troubleshooting.
- [Architecture](ARCHITECTURE.md): detailed layering and future design boundaries.
- [Professionalization plan](PRODUCTION_PLAN.md): database-free product direction and release roadmap.

## Notes

AI extraction can still misread a job description. Review the extracted requirements before selecting them. The CV template follows the section and macro style of the existing `resume.tex`; review generated documents before submission.

## Implementation boundaries

- AI extraction and matching can still misread a job description or evidence. Review the analysis and generated document before relying on them.
- The model output is validated against the profile evidence IDs, but this is not a full fact checker or recruiter decision.
- The generated text check flags literal mentions of missing requirements and some likely familiarity overclaims. It is not a full claim-by-claim fact checker; review every document against the profile.
- PDF export requires a local `latexmk` or `pdflatex` installation. LaTeX source files remain available when no compiler is installed.
- AI job extraction and role-specific cover-letter generation require `OPENAI_API_KEY`. Template-based CV generation works without it only when job and match data have already been provided.
