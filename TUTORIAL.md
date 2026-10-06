# Running the Job Application Engine

This guide is for the project's current local development setup. Your candidate profile and generated application files are stored on this machine; review the profile and generated documents before using them.

For the shortest setup path, see [QUICKSTART.md](QUICKSTART.md).

Flask is the supported primary web application. FastAPI provides the typed MCP/tooling API.

## Requirements

- Python 3.12 or newer
- A terminal opened in the project folder
- A LaTeX installation (`latexmk` or `pdflatex`) only if you want PDF exports
- An OpenAI API key for job-description extraction and AI-assisted matching/cover letters. Job extraction will report an error rather than use regex/keyword fallback if the key is missing or the provider is unavailable.

## 1. Install with the setup helper

The supported cross-platform path is:

```bash
python scripts/setup.py install
```

It creates `.venv`, installs dependencies, creates private `.env` and `config/user-settings.yaml` files from safe templates, and does not overwrite existing private configuration.

Use `py scripts/setup.py install` on Windows if `python` is not available. Manual setup remains available below for troubleshooting.

### Manual environment setup

From the project folder, create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Ubuntu/Debian, if venv creation reports that `ensurepip` is unavailable, install the matching venv package (for Python 3.12):

```bash
sudo apt update
sudo apt install python3.12-venv
```

Then rerun the `python3 -m venv .venv` command. On Windows PowerShell, use `py -3.12 -m venv .venv` and activate with `.venv\Scripts\Activate.ps1`. On macOS, use `python3 -m venv .venv` and `source .venv/bin/activate`.

## 2. Configure optional cover letter generation

Copy `.env.example` to `.env` and add your API key:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Keep `.env` private. Job extraction and role-specific cover letters require a key. With a key, the job description and relevant profile evidence are sent to OpenAI for role analysis and matching; cover-letter generation also sends the profile and job context.

## 3. Personal YAML preferences

`config/user-settings.yaml` is a private settings file created by the setup helper. It controls CV selection defaults, the number of CV entries, cover-letter tone, technical detail, target length, focus skills, hiring-manager review, and optional writing instructions.

Read the comments in [config/user-settings.example.yaml](config/user-settings.example.yaml) before editing it. Do not put an API key or private profile content in the YAML file. Preferences guide the writer but cannot override the requirement to avoid invented claims.

## 4. Check the candidate profile

The source of truth is `data/candidate_profile.json`. You can edit it directly in the JSON file or use the Flask dashboard. Keep experience, dates, metrics, and skill evidence accurate. Skills marked `FAMILIARITY` should remain described as familiarity, not professional experience.

## 5. Start the app stack

With the environment active, run:

```bash
python scripts/setup.py run
```

This starts the Flask dashboard at `http://127.0.0.1:5000` and the FastAPI MCP service at `http://127.0.0.1:8000`. Open `http://127.0.0.1:5000/dashboard` to use the browser UI. Paste a job description, review the evidence match, add optional applicant notes for the cover letter, and generate application documents.

The Flask UI and API routes use the shared application services in `app/services/application_services.py`:

- `ApplicationWorkflowService` coordinates job analysis and CV generation.
- `CoverLetterService` generates a letter and returns advisory style suggestions.
- `DocumentExportService` creates company-named PDF, LaTeX, and text exports.

Generated source files and PDFs are saved under `data/applications/` when the corresponding workflow creates a saved application artifact.

## 6. Optional: run the services separately

Open another terminal in the project folder, activate `.venv`, then run:

```bash
python app/flask_app.py --port 5000
python -m uvicorn app.api.fastapi_mcp.server:app --host 0.0.0.0 --port 8000
```

The API health endpoint is `http://127.0.0.1:8000/health`; interactive API documentation is at `http://127.0.0.1:8000/docs`.

The FastAPI service is intended for typed tool/API access. It should not contain browser-specific workflow or template logic; document generation remains in the shared service layer.

## 7. Export PDFs

Install `latexmk` or `pdflatex` if it is not already present. The app saves `.tex` source files even when there is no compiler. Use the app's compile buttons to create PDF versions; compiler errors are shown in the app.

## 8. Run tests

From the project folder, with `.venv` active, run:

```bash
python scripts/setup.py test
```

The environment variable prevents unrelated system-wide pytest plugins from being loaded. It is useful on machines that also have ROS or other pytest integrations installed.

## Common issues

- **`python main.py` fails**: activate the environment with `source .venv/bin/activate` and install dependencies with `python -m pip install -r requirements.txt`.
- **Cover letter says to set `OPENAI_API_KEY`**: configure `.env` and restart the app. You can still use local analysis and CV generation without it.
- **PDF compilation fails**: install `latexmk`/`pdflatex`, or use the saved `.tex` file directly.
- **Profile JSON won't save**: validate the JSON syntax and ensure values conform to `app/models/schemas.py`.
- **Match output seems incomplete**: the local analyzer uses a limited vocabulary and wording cues. Check the extracted requirements against the job description before relying on the score.
- **The app reports invalid user settings**: compare `config/user-settings.yaml` with [config/user-settings.example.yaml](config/user-settings.example.yaml); correct the named value, then restart.

## Data and privacy

Profile data and generated files are stored locally. When AI features are used, the job description and relevant candidate evidence are sent to the configured OpenAI API. `data/applications/`, `.env`, and `config/user-settings.yaml` are ignored by Git; keep personal application materials out of commits.
