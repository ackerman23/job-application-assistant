# Job Application Assistant: Project Guide

## What this project does

The Job Application Assistant is a local-first application for preparing tailored job applications. It accepts a job description and a structured candidate profile, then helps the user:

1. Analyze the role and extract technical requirements.
2. Compare those requirements with documented candidate evidence.
3. Review verified, transferable, familiarity, and missing capabilities.
4. Select skills for a tailored CV.
5. Generate CV LaTeX and optional PDF/text exports.
6. Generate a role-specific cover letter with hiring-manager reasoning and honest learning goals.
7. Save application artifacts locally for later review.

The Flask dashboard is the main user interface. FastAPI exposes typed HTTP and MCP-oriented tools for integrations.

## Supported runtime

The supported runtime is:

- Flask dashboard: `http://127.0.0.1:5000/dashboard`
- FastAPI documentation: `http://127.0.0.1:8000/docs`
- FastAPI health endpoint: `http://127.0.0.1:8000/health`

Start both services with:

```bash
python main.py --mode all
```

The old prototype UI has been removed. There is one supported browser workflow: Flask.

## Main workflow

### 1. Candidate profile

The profile is stored locally in `data/candidate_profile.json`. It is the source of truth for the candidate's:

- Personal information
- Education
- Experience
- Projects
- Skills and evidence status
- Career direction
- Writing samples

Keep this file accurate. Use `VERIFIED` only for direct evidence, `TRANSFERABLE` for adjacent experience, and `FAMILIARITY` for study or conceptual knowledge.

### 2. Job analysis

The job analyzer extracts the role, company, responsibilities, technical skills, tools, domains, preferred skills, and implicit technical requirements. The extracted result should always be reviewed because AI extraction can misunderstand job descriptions.

### 3. Evidence matching

The matching engine compares job requirements with profile evidence:

- **VERIFIED**: direct supporting evidence.
- **TRANSFERABLE**: related evidence that can be explained as relevant but not direct experience.
- **FAMILIARITY**: documented study or conceptual knowledge.
- **MISSING**: no supporting evidence was found.

Missing requirements can be selected for the CV when the user explicitly wants them included. The application does not silently add them.

### 4. CV generation

The CV generator preserves the candidate's profile content and prioritizes relevant experience and projects. Selected requirements are placed in the Skills section. The user can select verified, transferable, familiarity, or missing requirements; selections are explicit and are not automatically treated as evidence-backed experience.

### 5. Cover-letter generation

The cover-letter prompt performs internal job understanding and hiring-manager simulation before drafting. It constructs the letter around:

- Why this role
- Why this candidate
- Why the application makes sense now
- The strongest relevant evidence
- The candidate's differentiator
- The most useful learning objective
- A specific explanation of the role

A missing capability may be framed as a learning objective when it is connected to adjacent expertise. The generator must not invent experience, metrics, tools, projects, or company facts.

Style checks are advisory. They produce suggestions about length, paragraphs, clichés, punctuation, and repetitive sentence openings without blocking a generated draft.

## Project structure

```text
app/
  api/                  Flask routes and FastAPI/MCP server
  core/                 Configuration and project paths
  models/               Pydantic domain schemas
  prompts/              Cover-letter generation instructions
  services/             Analysis, matching, workflow, and document generation
  templates/            Flask HTML templates

templates/
  cv/                   CV LaTeX template
  cover_letter/         Cover-letter LaTeX template

data/
  candidate_profile.json Local profile; ignored by Git
  applications/          Generated application artifacts; ignored by Git

tests/                  Regression and workflow tests
```

## Important modules

- `app/services/jd_analyzer.py`: AI-only job-description extraction.
- `app/services/matching_engine.py`: technical requirement extraction and evidence matching.
- `app/services/cover_letter_engine.py`: structured context, narrative, strategy, and quality analysis.
- `app/services/generation.py`: CV, cover-letter, LaTeX, and validation generation.
- `app/services/workflow.py`: shared orchestration used by browser and API entry points.
- `app/services/application_services.py`: application-level services and export helpers.
- `app/models/schemas.py`: typed profile, job, match, and document models.
- `app/prompts/cover_letter.txt`: final writer specification.

## Installation

Recommended setup (Linux, macOS, and Windows):

```bash
python scripts/setup.py install
python scripts/setup.py run
```

The helper creates `.venv`, installs `requirements.txt`, and copies `.env.example` to `.env` only when `.env` does not already exist. The equivalent manual commands are shown in [QUICKSTART.md](QUICKSTART.md).

### Base CV starter

[base-cv/](base-cv/) contains a fictional, public example profile for a software-and-systems engineering candidate. It is intentionally separate from private local data. To copy it into your private profile, run `python scripts/setup.py init-profile`; the command will not overwrite a profile unless `--force` is supplied. Replace all sample details and retain only truthful, supportable claims.

Set `OPENAI_API_KEY` in `.env` for AI job extraction, AI-assisted matching, and cover-letter generation. Never commit `.env`.

PDF downloads additionally require `latexmk` or `pdflatex`. LaTeX source can still be generated without a PDF compiler.

## Testing

Run the full suite from the project root:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

The environment variable prevents unrelated globally installed pytest plugins from interfering with the project test run.

## Privacy and GitHub safety

The following are intentionally ignored by Git:

- `.env`
- `data/candidate_profile.json`
- `data/applications/`
- Generated PDFs and LaTeX build artifacts
- Virtual environments and Python caches

Do not commit personal profiles, job descriptions, generated letters, private application files, API keys, or access tokens.

When AI features are used, the configured provider receives the job description and relevant candidate evidence. Review the provider's data policy before using sensitive information.

## Extending the project

When adding a feature:

1. Add or update a typed model in `app/models/schemas.py` if the data crosses a service boundary.
2. Put reusable behavior in `app/services/` rather than in Flask or FastAPI route functions.
3. Route both browser and API entry points through `app/services/workflow.py` where applicable.
4. Add a focused regression test under `tests/`.
5. Update `README.md`, this guide, or `ARCHITECTURE.md` when behavior or setup changes.
6. Run the complete test suite before committing.

Keep evidence rules and privacy boundaries intact when modifying generation logic.

## Professionalization roadmap

The target product is a database-free local application that friends can run independently. See [PRODUCTION_PLAN.md](PRODUCTION_PLAN.md) for the staged plan, including removal of the current legacy application-history database path, one-command setup, CI, privacy, testing, and release quality.
