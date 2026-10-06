# Quick start

Use Flask as the primary application. FastAPI/MCP is optional and provides typed API/tool access.

## 1. Install — recommended

The recommended setup is the cross-platform Python helper. It creates the virtual environment, installs dependencies, and creates `.env` without overwriting an existing private configuration:

```bash
python scripts/setup.py install
```

Use `py` instead of `python` on Windows if needed:

```powershell
py scripts/setup.py install
```

Then open `.env`, add your OpenAI key, and start the application:

```bash
python scripts/setup.py run
```

The helper also supports `python scripts/setup.py test` and `python scripts/setup.py clean`.

It also creates a private `config/user-settings.yaml`. Use this YAML file to control CV selection defaults, document length, cover-letter tone, technical emphasis, focus skills, and optional writing instructions. API keys stay in `.env`, not the YAML file.

To start from the fictional base CV instead of an empty profile:

```bash
python scripts/setup.py init-profile
```

It creates a private `data/candidate_profile.json` and will not overwrite an existing profile. The example is only a structure guide: replace every placeholder and retain only claims you can support.

## 2. Manual installation

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows PowerShell, create the environment with `py -3.12 -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1`.

## 3. Configure AI features

```bash
cp .env.example .env
```

Add your key to `.env`:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Keep `.env` private. AI features include job-description analysis, evidence matching, and cover-letter generation.

## Personal settings

Edit `config/user-settings.yaml` to tailor document preferences. The committed [example settings](config/user-settings.example.yaml) describe every supported option. Settings complement the app's evidence rules; they cannot turn unsupported skills or experience into verified claims.

## 4. Start the app

```bash
python scripts/setup.py run
```

Open the Flask dashboard:

- Dashboard: <http://127.0.0.1:5000/dashboard>
- Flask health: <http://127.0.0.1:5000/health>
- FastAPI docs: <http://127.0.0.1:8000/docs>
- FastAPI health: <http://127.0.0.1:8000/health>

## 5. Generate an application

1. Edit or paste your candidate profile in the dashboard.
2. Paste a complete job description.
3. Select **Analyze job**.
4. Review the evidence match and proposed CV additions.
5. Add an optional personal reason for applying.
6. Generate the CV or cover letter.
7. Review the generated text before downloading PDF, LaTeX, or text files.

Only profile-supported claims should be used as professional experience. Keep studied or introductory skills marked as `FAMILIARITY`.

## 6. PDF exports

Install `latexmk` or `pdflatex` for PDF downloads. The application still produces LaTeX source when a PDF compiler is unavailable.

## 7. Run tests

```bash
python scripts/setup.py test
```

For the full setup and troubleshooting guide, see [PROJECT_GUIDE.md](PROJECT_GUIDE.md).
