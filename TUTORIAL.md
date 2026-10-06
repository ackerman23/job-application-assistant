# Running the Job Application Engine

This is a standalone guide for someone starting from the GitHub repository. The application runs locally: each person has their own private profile, settings, generated documents, and API key. Flask is the supported browser application; FastAPI is optional typed API/MCP access.

## Requirements

- Python 3.12 or newer
- Git
- A terminal; PowerShell on Windows is supported
- A LaTeX installation (`latexmk` or `pdflatex`) only for PDF exports
- An OpenAI API key if you want to analyze a job description or generate a tailored cover letter. There is no silent keyword-parser fallback for job extraction.

## 1. Download the project

Open a terminal and clone the repository:

```bash
git clone https://github.com/ackerman23/job-application-assistant.git
cd job-application-assistant
```

On Windows PowerShell, use the same commands. If Git is unavailable, download the repository ZIP from GitHub, extract it, and open a terminal in the extracted `job-application-assistant` folder.

## 2. Install with the setup helper

The supported cross-platform path is:

```bash
python scripts/setup.py install
```

It creates `.venv`, installs dependencies, and creates private `.env` and `config/user-settings.yaml` files from safe templates. It never overwrites existing private configuration.

Use this command on Windows if `python` is not available:

```powershell
py scripts/setup.py install
```

### Manual installation

Use this only if the setup helper cannot run. On Linux or macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
cp config/user-settings.example.yaml config/user-settings.yaml
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
Copy-Item config/user-settings.example.yaml config/user-settings.yaml
```

If Ubuntu or Debian reports that `ensurepip` is unavailable, install the matching Python virtual-environment package, then retry:

```bash
sudo apt update
sudo apt install python3.12-venv
```

## 3. Configure AI features

Open `.env` in a text editor and add your own API key:

```dotenv
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Keep `.env` private. The dashboard can open without a key, but **Analyze job** and tailored cover-letter generation require it. With a key, the job description and relevant profile evidence are sent to OpenAI for role analysis and matching; cover-letter generation also sends the profile and job context.

## 4. Personal YAML preferences

`config/user-settings.yaml` is a private settings file. It controls CV selection defaults, the number of CV entries, cover-letter tone, technical detail, target length, focus skills, hiring-manager review, and optional writing instructions.

Read the comments in [config/user-settings.example.yaml](config/user-settings.example.yaml) before editing it. Do not put an API key or private profile content in the YAML file. Preferences guide the writer but cannot override the requirement to avoid invented claims.

## 5. Create your candidate profile

Choose one option:

1. **Start empty.** The app creates `data/candidate_profile.json` when you first open the dashboard.
2. **Start from the fictional example profile.** Run:

   ```bash
   python scripts/setup.py init-profile
   ```

The source of truth is `data/candidate_profile.json`. You can edit it directly or in the dashboard. Replace every example value with your own accurate information. Keep experience, dates, metrics, and skill evidence accurate. Skills marked `FAMILIARITY` should remain described as familiarity, not professional experience.

## 6. Start the app stack

Run this from the project folder; virtual-environment activation is not required when using the helper:

```bash
python scripts/setup.py run
```

This starts the Flask dashboard at <http://127.0.0.1:5000/dashboard> and the FastAPI MCP service at <http://127.0.0.1:8000/docs>. Keep the terminal open while using the app; press `Ctrl+C` to stop both services.

In the dashboard, edit your profile, paste a job description, select **Analyze job**, review the evidence match, choose skill additions, then generate and review the CV or cover letter before downloading.

## 7. Optional: run services separately

Activate `.venv`, then run the following commands in separate terminals from the project folder:

```bash
python app/flask_app.py --port 5000
python -m uvicorn app.api.fastapi_mcp.server:app --host 0.0.0.0 --port 8000
```

The FastAPI health endpoint is <http://127.0.0.1:8000/health>; its interactive documentation is <http://127.0.0.1:8000/docs>.

## 8. Export PDFs

The app always provides LaTeX source. PDF downloads additionally require `latexmk` or `pdflatex`.

- Ubuntu/Debian: `sudo apt install latexmk texlive-latex-base`
- macOS: install MacTeX or BasicTeX from [TUG](https://www.tug.org/mactex/).
- Windows: install [MiKTeX](https://miktex.org/download), then reopen the terminal.

## 9. Run tests

From the project folder, run:

```bash
python scripts/setup.py test
```

The helper disables unrelated system-wide pytest plugins automatically.

## Common issues

- **`python scripts/setup.py install` fails:** confirm that `python --version` (or `py --version`) is Python 3.12 or newer. On Ubuntu/Debian, install `python3.12-venv` if `ensurepip` is missing.
- **A port is in use:** stop the other process, or choose different ports: `python scripts/setup.py run --flask-port 5001 --mcp-port 8001`.
- **Analyze job or cover-letter generation asks for `OPENAI_API_KEY`:** add a valid key to `.env`, save it, and restart the app.
- **PDF compilation fails:** install `latexmk`/`pdflatex`, or download the `.tex` source instead.
- **Profile JSON will not save:** validate its JSON syntax and check values against the documented example in [base-cv/](base-cv/).
- **Job analysis seems incomplete:** verify the API key and provide a complete job description with technical detail, then retry. Always review extracted requirements before relying on them.
- **The app reports invalid user settings:** compare `config/user-settings.yaml` with [config/user-settings.example.yaml](config/user-settings.example.yaml), correct the named value, then restart.

## Data and privacy

Profile data and generated files are stored locally. When AI features are used, the job description and relevant candidate evidence are sent to the configured OpenAI API. `data/candidate_profile.json`, `data/applications/`, `.env`, and `config/user-settings.yaml` are ignored by Git; keep personal application materials out of commits.
