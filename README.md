# UVA AI Course Scheduler

For CS 4710: Artificial Intelligence — Spring 2026

An AI-powered course scheduling system for UVA CS students that recommends personalized semester schedules using three AI methods: a Naive Bayes Net, a Neural Network, and an LLM.

## Quick Start

### macOS / Linux

```bash
# Create virtual environment and install dependencies
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Generate synthetic review and section data
python scripts/generate_synthetic_data.py

# Run the web application
uvicorn src.api.app:app --reload

# Open http://localhost:8000 in your browser
```

### Windows (PowerShell)

#### Prerequisites

- Python 3.11+ installed
- PowerShell
- `uv` package manager

#### 1) Install `uv` (one-time)

If `uv --version` fails, install `uv` with:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then close and reopen PowerShell, and verify:

```powershell
uv --version
```

#### 2) Create virtual environment and install dependencies

From the project root:

```powershell
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

If activation is blocked by execution policy, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

#### 3) Generate synthetic review and section data

```powershell
python .\scripts\generate_synthetic_data.py
```

#### 4) Run the web application

```powershell
uvicorn src.api.app:app --reload
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

#### 5) Start Ollama for natural-language schedule explanations (optional)

If you want richer LLM-generated explanations (instead of template fallback), run Ollama locally.

1. Install Ollama for Windows: [https://ollama.com/download/windows](https://ollama.com/download/windows)
2. Launch the **Ollama** app from the Start Menu (this starts the local server).
3. Pull the model used by this project:

```powershell
ollama pull qwen2.5:7b
```

4. Verify Ollama is running:

```powershell
ollama list
```

5. (Optional sanity check) run a direct prompt:

```powershell
ollama run qwen2.5:7b "Say hello in one sentence."
```

If your app still uses template responses, restart the app after starting Ollama so `backend="auto"` can detect `http://localhost:11434`.

## Running Tests

### macOS / Linux

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

### Windows (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest .\tests\ -v
```

## Common Windows Issues

- **`uv` is not recognized**: `uv` is not installed or not on `PATH`. Install it using the command above, then restart PowerShell.
- **`source` command does not work**: `source` is a Unix command. In PowerShell use `.\.venv\Scripts\Activate.ps1`.
- **Activation script blocked**: run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and try activation again.
- **`python` not recognized**: use `py` instead (for example, `py -m pytest .\tests\ -v`).
- **`ollama` is not recognized**: usually your current PowerShell session has not picked up the new `PATH` yet.
  - Close and reopen PowerShell, then run:
    ```powershell
    Get-Command ollama
    ```
  - If still not found, run Ollama by full path:
    ```powershell
    & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version
    & "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull qwen2.5:7b
    ```
  - Optional: refresh PATH in the current terminal session:
    ```powershell
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    ```
- **`os error 396` when installing packages**: this is usually a OneDrive hardlink limitation when `uv` installs into `.venv`.
  - Example error includes: `The cloud operation cannot be performed on a file with incompatible hardlinks. (os error 396)`
  - Fix for current terminal session:
    ```powershell
    $env:UV_LINK_MODE = "copy"
    $env:UV_CACHE_DIR = "$env:LOCALAPPDATA\uv\cache"
    ```
    Then reinstall:
    ```powershell
    if (Test-Path .venv) { Remove-Item .venv -Recurse -Force }
    uv venv .venv
    .\.venv\Scripts\Activate.ps1
    uv pip install -r requirements.txt
    ```
  - Optional (persist for future PowerShell sessions):
    ```powershell
    [Environment]::SetEnvironmentVariable("UV_LINK_MODE","copy","User")
    [Environment]::SetEnvironmentVariable("UV_CACHE_DIR","$env:LOCALAPPDATA\uv\cache","User")
    ```
    Reopen PowerShell after setting persistent variables.

## Architecture

```
src/
  data/            Course loader, prerequisite parser/AST, DAG, reviews, sections
  student/         Transcript model, degree requirements, preference schema
  models/          Naive Bayes scorer, CSP schedule generator, NN optimizer
  llm/             LLM client (Ollama/template), preference parser, explainer
  api/             FastAPI application, routes, schemas
  ui/              Jinja2 templates, CSS, JavaScript
  evaluation/      Random baseline generator, rating collector, evaluation report
tests/             104 tests across all components
scripts/           Synthetic data generation
```

## AI Methods

1. **Naive Bayes Net** (`src/models/bayes_net.py`) — Scores each candidate course by P(liked | features), using review data and student preferences as priors. Features include difficulty, instructor rating, enjoyment, topics, and course type.

2. **Neural Network** (`src/models/neural_optimizer.py`) — A PyTorch feed-forward network that reranks schedules produced by the CSP solver. Takes schedule-level feature vectors (course features + time-of-day + gap encoding) and predicts a quality score.

3. **LLM Integration** (`src/llm/`) — Parses natural language preferences into structured input, performs sentiment analysis on reviews, and generates chain-of-reasoning explanations for recommended schedules. Supports Ollama (local) with a template-based fallback.

## How It Works

1. Student inputs their transcript (completed courses)
2. System computes remaining degree requirements (BSCS)
3. Student provides preferences (difficulty, topics, time constraints) via form or chatbot
4. Naive Bayes Net scores all candidate courses by student-course affinity
5. CSP solver generates valid schedules (no time conflicts, prerequisites satisfied)
6. Neural Network reranks schedules by predicted quality
7. LLM explains why each schedule was recommended
8. Student rates schedules (1-10) for evaluation

## Data

- `courses.json` — 126 UVA CS courses with descriptions, credits, types, and prerequisites
- `data/reviews/` — Synthetic review data (1,620 reviews) with difficulty, instructor, and enjoyment ratings
- `data/sections/` — Synthetic section schedule data (312 sections) with times, days, and instructors
