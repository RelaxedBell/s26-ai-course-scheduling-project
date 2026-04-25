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

## Rivanna LLM (development only)

Run a real LLM on a Rivanna GPU node instead of locally or against the
Anthropic API. Intended for dev / demo use, not production.

### TL;DR (once everything below is set up)

```bash
cd s26-ai-course-scheduling-project
./dev          # starts tmux: Rivanna warmup (left) + uvicorn (right)
```

Browser opens to `http://localhost:8000` after ~12 s. Detach with
**Ctrl-B D**. Kill everything (and release the GPU allocation) with
`tmux kill-session -t ai-dev`.

`./dev` is a thin wrapper around `scripts/dev_start.sh`. The pieces it
runs:

- `scripts/rivanna_warmup.sh` — allocates a Rivanna GPU node, installs
  Ollama on Rivanna if missing, starts `ollama serve`, and tunnels
  `localhost:11434` on your machine to the compute node.
- `uvicorn src.api.app:app --reload` — the FastAPI dev server. Waits
  for the tunnel before starting so it picks up the Ollama backend
  instead of falling back to the keyword-matching template
  (`src/api/state.py:49` creates the LLM client once at startup).

---

### First-time setup (each teammate, once)

This section walks through everything you need to do before `./dev`
will work. **Pick the section that matches your OS** for steps 1–2;
steps 3–9 are the same on Mac and Windows (in WSL2 / Git Bash).

#### Prerequisites

- **UVA computing ID** (e.g. `abc1d`).
- **Rivanna account approved.** Apply or check status at
  <https://www.rc.virginia.edu/userinfo/rivanna/login/>. Approval
  usually takes a day or two.
- **Membership in our SLURM allocation** — `cs4710-cbx8wm` (the
  CS 4710 course allocation). The course staff adds students; if
  step 7 below shows you're not a member, ping the team chat.
- **DUO 2FA enrolled.** Have your phone handy — you'll get a push.

#### 1. Install a working bash + SSH environment

**Mac**

Built in. Open **Terminal**. You also need `tmux`:

```bash
# install Homebrew if you don't have it (https://brew.sh)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install tmux
```

**Windows**

The project uses bash scripts and `tmux`, neither of which exist in
PowerShell or cmd. Use **WSL2 with Ubuntu** — it's a real Linux
running alongside Windows.

```powershell
# In PowerShell, as Administrator (one-time):
wsl --install -d Ubuntu
# Reboot when prompted, then open "Ubuntu" from the Start menu.
# Set a Linux username/password when it first launches.
```

Inside the Ubuntu shell:

```bash
sudo apt update
sudo apt install -y tmux git curl openssh-client
```

**Run all subsequent commands inside Ubuntu**, not in PowerShell.
(Git Bash is OK for the SSH steps but doesn't have `tmux`, so `./dev`
won't work from Git Bash. Stick with WSL2.)

#### 2. Get on UVA's network

Rivanna's login nodes aren't reachable from the public internet. You
have two options.

**Option A — UVA Anywhere VPN (recommended, works for everyone)**

Install **Cisco Secure Client** (formerly Cisco AnyConnect). Search
"UVA Anywhere VPN install" on <https://its.virginia.edu> for the
current installer for your OS. After install, connect to:

```
uva-anywhere-1.itc.virginia.edu
```

Authenticate with NetBadge + DUO. Stay connected for the duration of
your dev session.

> **WSL2 note:** the VPN client runs on Windows, not inside WSL2.
> WSL2 inherits the Windows network, so once Windows is on the VPN,
> WSL2 commands can reach Rivanna too.

**Option B — CS portal bastion (only if you have a CS dept account)**

If you have an account on `portal.cs.virginia.edu`, you can skip the
VPN and SSH-jump through it instead. See "Alternative SSH config"
at the end of this section.

#### 3. Generate an SSH key (one-time)

```bash
ssh-keygen -t ed25519 -C "rivanna" -f ~/.ssh/rivanna_ed25519
```

- Press Enter to accept the default path.
- Setting a passphrase is more secure but means you'll type it once
  per session. Up to you.

This creates two files: `~/.ssh/rivanna_ed25519` (private — never
share) and `~/.ssh/rivanna_ed25519.pub` (public — safe to share).

#### 4. Install your public key on Rivanna (one-time)

**Make sure you're on the VPN first.** Then:

```bash
ssh-copy-id -i ~/.ssh/rivanna_ed25519.pub <your-id>@rivanna.hpc.virginia.edu
```

- Password = your **UVA NetBadge password**.
- A **DUO push** will hit your phone — approve it.

If `ssh-copy-id` isn't available, do it manually:

```bash
cat ~/.ssh/rivanna_ed25519.pub        # copy this output
ssh <your-id>@rivanna.hpc.virginia.edu  # password + DUO
# Now on Rivanna:
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo 'PASTE_THE_KEY_HERE' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
exit
```

#### 5. Configure SSH

Open `~/.ssh/config` (create the file if it doesn't exist). Add:

```
Host rivanna
  HostName rivanna.hpc.virginia.edu
  User <your-computing-id>
  IdentityFile ~/.ssh/rivanna_ed25519
  ServerAliveInterval 60
  ControlMaster auto
  ControlPath ~/.ssh/cm-%C
  ControlPersist 10m
```

Then create the directory the control sockets live in:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
```

**Why ControlMaster matters:** the warmup script makes 5+ SSH calls
in a row (submit job, poll status, read node name, open tunnel...).
Without multiplexing, each one triggers a fresh DUO push. With
`ControlPersist 10m`, you authenticate once and reuse the connection
for 10 minutes — DUO once per session, not per command.

#### 6. Test the connection

```bash
ssh rivanna whoami
# DUO push -> approve -> prints your computing ID

ssh rivanna whoami
# Should NOT prompt DUO this time (multiplexed).
```

If the second call re-prompts, ControlMaster isn't kicking in — see
Troubleshooting below.

#### 7. Verify SLURM allocation membership

```bash
ssh rivanna allocations
```

You should see `cs4710-cbx8wm` listed. If not, you're not in the
course allocation yet — ping the team.

#### 8. Set RIVANNA_ACCOUNT permanently

So you don't have to type it before every `./dev`:

**Mac (zsh — default since macOS Catalina):**
```bash
echo 'export RIVANNA_ACCOUNT=cs4710-cbx8wm' >> ~/.zshrc
source ~/.zshrc
```

**WSL2 / Linux / Git Bash (bash):**
```bash
echo 'export RIVANNA_ACCOUNT=cs4710-cbx8wm' >> ~/.bashrc
source ~/.bashrc
```

#### 9. First run

```bash
cd s26-ai-course-scheduling-project
./dev
```

The first run downloads `qwen2.5:7b` (~4.7 GB) on Rivanna inside the
SLURM job — the gap between `[4/5]` and `[5/5] READY` will take a
couple of minutes. Subsequent runs are fast because the model stays
cached in your Rivanna home directory.

---

### Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Permission denied (publickey)` | Key not authorized on Rivanna. Redo step 4. |
| `connect to host rivanna.hpc.virginia.edu port 22: Operation timed out` | You're not on UVA network. Connect VPN. |
| `Host key verification failed` | Run `ssh-keygen -R rivanna.hpc.virginia.edu` and retry. |
| Multiple DUO prompts during one `./dev` run | ControlMaster isn't working. Check `mkdir -p ~/.ssh && chmod 700 ~/.ssh`. On WSL2 some FS layouts dislike socket files — try `ControlPath /tmp/cm-%C` instead of `~/.ssh/cm-%C`. |
| `./dev` doesn't run on Windows | You're not in WSL2 / Git Bash. PowerShell can't execute `.sh` files. |
| `tmux: command not found` | Install it: Mac `brew install tmux`, WSL2 `sudo apt install tmux`. |
| Warmup stuck on `PENDING` for >5 min | GPU partition is busy. Either wait, or set `RIVANNA_PARTITION=standard` to fall back to CPU (much slower inference but unblocks demo). |
| Page at `localhost:8000` won't load after `./dev` | Right pane is still waiting for the tunnel. Reattach with `tmux attach -t ai-dev` and check the **left** pane for warmup errors. |

### Alternative SSH config — CS portal bastion

If you have a CS dept account and prefer not to use VPN, replace the
SSH config block in step 5 with:

```
Host rivanna
  HostName rivanna.hpc.virginia.edu
  User <your-computing-id>
  IdentityFile ~/.ssh/rivanna_ed25519
  ProxyJump <your-id>@portal.cs.virginia.edu
  ServerAliveInterval 60
  ControlMaster auto
  ControlPath ~/.ssh/cm-%C
  ControlPersist 10m
```

You'll also need to install your public key on `portal.cs.virginia.edu`:
repeat step 4 with `portal.cs.virginia.edu` as the host.

### Cleaning up

**Always run `tmux kill-session -t ai-dev` when you're done** —
otherwise the SLURM job sits on a GPU until its 4-hour wall time
expires, which counts against the course allocation. The Ctrl-C
handler in `rivanna_warmup.sh` runs `scancel` automatically when the
session dies, so this one command cleans up both sides.

Verify the GPU was released:

```bash
ssh rivanna 'squeue -u $USER'   # should show no ai-llm-* job
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
4. **Candidate filter** prunes the pool up front — drops already-taken
   courses, majors-ineligible courses, electives outside the student's
   chosen topics/departments, courses whose every section conflicts
   with an unavailable time block, and courses above the credit ceiling
   (`src/models/candidate_filter.py`)
5. Naive Bayes Net scores the remaining candidates by student-course affinity
6. CSP solver generates valid schedules (no time conflicts, prerequisites
   satisfied, total credits within `[min_credits - tolerance, max_credits + tolerance]`)
7. Neural Network reranks schedules by predicted quality
8. LLM explains why each schedule was recommended
9. Student rates schedules (1-10) for evaluation

## Data

- `courses.json` — 126 UVA CS courses with descriptions, credits, types, and prerequisites
- `data/reviews/` — Synthetic review data (1,620 reviews) with difficulty, instructor, and enjoyment ratings
- `data/sections/` — Synthetic section schedule data (312 sections) with times, days, and instructors
