# CodeMap 🗺️

**Understand the code. Find the challenges. Discover what to improve next.**

CodeMap is an open-source project-intelligence MVP powered by Gemma 4. It imports a public GitHub repository or ZIP, scans Python source structure, visualizes module relationships, flags transparent static-analysis signals, suggests first-contribution starting points, and generates role-specific explanations for students, teachers, and developers.

## Features

- Import a public GitHub repository or upload a source ZIP.
- Visualize detected Python module imports.
- Explore files, classes, functions, and external imports.
- Challenge Radar for transparent signals such as long functions, complex control flow, missing obvious tests/docs/manifests, and parse errors.
- First Contribution Finder for possible beginner-sized tasks.
- Trace the Journey: ask Gemma 4 to explain a workflow using bounded code context.
- Student, Teacher, and Developer modes.
- Project readiness checklist and downloadable Markdown report.
- Separate model integration module and configurable provider endpoint.

## Requirements

- Python 3.10 or newer
- A Gemma 4 API key / endpoint supplied by your event's Flow setup, or a Google AI Studio API key if using Google's GenAI API directly
- Internet access for public GitHub imports and hosted inference

## Setup (Windows PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and set `GEMMA_API_KEY` to your own key. Never paste the key into chat or commit `.env` to GitHub.

### Model provider configuration

The model adapter supports two routes:

1. **OpenAI-compatible Flow endpoint:** set `GEMMA_API_BASE_URL` to the base URL supplied by your event, set the event key in `GEMMA_API_KEY`, and set `GEMMA_MODEL` to the exact model ID shown by Flow.
2. **Google GenAI API:** leave `GEMMA_API_BASE_URL` blank, use a Google AI Studio API key, and set `GEMMA_MODEL=gemma-4-26b-a4b-it`.

Do not assume these provider routes are interchangeable. Verify the event's required Flow endpoint and model identifier before the demo.

## Run

```powershell
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. Paste a public GitHub repository URL or upload a ZIP containing source files.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Security and limitations

- This MVP supports public GitHub repositories and Python-first static analysis. Private repositories are not supported.
- It fetches a bounded number of text files and skips common dependency/build folders, environment files, and suspicious paths.
- ZIP files are read in memory; files are not extracted to the filesystem.
- Static checks are heuristics. They do not run the repository, execute tests, prove bugs, or constitute a security audit.
- AI features send selected source snippets and structural metadata to the configured model provider. Do not upload secrets or code you are not permitted to share.
- Repository content is untrusted input. Treat model output as advice to verify, not as executable instructions.
- No model key is required for local static analysis, the graph, readiness checks, or Markdown report; AI buttons need a valid model configuration.

## Architecture

- `app.py` — Streamlit UI and user workflows
- `github_loader.py` — safe, bounded public GitHub/ZIP ingestion
- `code_analyzer.py` — local Python AST analysis, findings, graph, readiness checks
- `gemma_service.py` — isolated Gemma 4 model adapter and AI prompts
- `report_builder.py` — Markdown report generation

## License

MIT. See `LICENSE`.
