# Quick start

Use Flask as the primary application. FastAPI/MCP is optional and provides typed API/tool access.

## 1. Install

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, create the environment with `py -3.12 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`.

## 2. Configure AI features

```bash
cp .env.example .env
```

Add your key to `.env`:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Keep `.env` private. AI features include job-description analysis, evidence matching, and cover-letter generation.

## 3. Start the app

```bash
python main.py --mode all
```

Open the Flask dashboard:

- Dashboard: <http://127.0.0.1:5000/dashboard>
- Flask health: <http://127.0.0.1:5000/health>
- FastAPI docs: <http://127.0.0.1:8000/docs>
- FastAPI health: <http://127.0.0.1:8000/health>

## 4. Generate an application

1. Edit or paste your candidate profile in the dashboard.
2. Paste a complete job description.
3. Select **Analyze job**.
4. Review the evidence match and proposed CV additions.
5. Add an optional personal reason for applying.
6. Generate the CV or cover letter.
7. Review the generated text before downloading PDF, LaTeX, or text files.

Only profile-supported claims should be used as professional experience. Keep studied or introductory skills marked as `FAMILIARITY`.

## 5. PDF exports

Install `latexmk` or `pdflatex` for PDF downloads. The application still produces LaTeX source when a PDF compiler is unavailable.

## 6. Run tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
```

For the full setup and troubleshooting guide, see [PROJECT_GUIDE.md](PROJECT_GUIDE.md).
