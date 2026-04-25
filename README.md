# UVA AI Course Scheduler

For CS 4710: Artificial Intelligence — Spring 2026

An AI-powered course scheduling system for UVA CS students that recommends personalized semester schedules using three AI methods: a Naive Bayes Net, a Neural Network, and an LLM.

## Quick Start

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

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

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
