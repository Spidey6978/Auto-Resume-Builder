# Auto Resume Builder

A target-aware resume generation engine that turns a single **Canonical Profile** into tailored, ATS-friendly resumes for specific roles and job descriptions.

Instead of maintaining multiple resume copies, Auto Resume Builder stores your career history as structured facts, ranks the most relevant evidence for each target, generates grounded resume bullets, and compiles them into a polished LuaLaTeX PDF — automatically trimming lower-priority content when the document exceeds its page budget.

> **Status:** Core targeting, generation pipeline, and universal document ingestion are complete. Currently supporting GitHub and PDF/Document ingestion with intelligent differential syncing.

---

## ✨ Features

- **Canonical Profile** — Maintain one structured source of truth for projects, experience, education, awards, skills, and career facts.
- **Targeted Resume Generation** — Tailor resumes using predefined role targets or a raw job description.
- **Hybrid Fact Ranking** — Deterministically scores evidence using skill overlap, target relevance, measurable impact, hiring priorities, and provenance before involving the LLM.
- **Evidence-Grounded Generation** — Gemini converts selected facts into resume-ready bullets without modifying the underlying career data.
- **Dynamic Page Budgeting** — Compiles the real PDF, detects overflow, removes the lowest-priority content, and recompiles until the requested page limit is satisfied.
- **GitHub Ingestion** — Extract technical facts and technology stacks from repositories and safely merge them into the Canonical Profile.
- **Input-Hash Caching** — SQLite-backed fingerprints prevent repeated AI calls when the facts, target, and generation rules haven't changed.
- **Resilient AI Gateway** — Centralized retries, rate-limit handling, prompt versioning, caching, and model fallback.
- **Isolated Builds** — Every generation runs inside its own workspace, preventing output collisions and keeping the pipeline ready for future multi-user execution.

---

## 🏗️ How It Works

```text
GitHub Ingestion
        │
        ▼
┌───────────────────┐
│ Canonical Profile │  ← everything known about the candidate
└─────────┬─────────┘
          │
          ├──────────── TargetKnowledge
          │
          └──────────── Job Description / Target
          │
          ▼
     Fact Ranker
          │
          ▼
    Resume Planner
          │
          ▼
  Content Generator
          │
          ▼
 Jinja2 + LuaLaTeX
          │
          ▼
  Overflow Resolver
          │
          ▼
      resume.pdf
```

The architecture deliberately separates:

**Career truth** → `CanonicalProfile`  
**What matters for the role** → `TargetKnowledge`  
**What should appear** → `ResumePlan`  
**How it should be written** → `ContentGenerator`

This keeps generated wording and targeting decisions from contaminating the candidate's underlying career data.

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+**: Ensure Python is installed and available in your PATH.
- **LaTeX Distribution**: You must have a LaTeX engine installed that supports `lualatex`.
  - **Windows**: [MiKTeX](https://miktex.org/)
  - **Linux**: `sudo apt install texlive-full`
  - **macOS**: [MacTeX](https://www.tug.org/mactex/)
- **API Keys**:
  - **Google Gemini API Key**: Required for the generation engine.
  - **GitHub Token**: Optional but highly recommended to avoid API rate limits when fetching repositories.

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Spidey6978/Auto-Resume-Builder.git
   cd Auto-Resume-Builder
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   ```

   *Activate the environment:*
   ```bash
   # Windows
   .\venv\Scripts\activate

   # Linux / macOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   The application now handles its own initialization and setup. Simply run the init command (you can alias `python -m src.arb.cli.main` to `arb`):

   ```bash
   python -m src.arb.cli.main init
   ```
   
   This will guide you through setting up your user data directory, migrating old profiles, and configuring your API keys.

---

## 💻 Usage

Auto Resume Builder is driven by a powerful CLI. (We recommend aliasing `python -m src.arb.cli.main` to `arb` for convenience).

### 1. Check your setup

```bash
arb doctor
```
Verifies your Python version, user data directories, API keys, and LaTeX compilers.

### 2. Ingest your career history (Data Sources)

Auto Resume Builder extracts structured facts from your existing data without destroying anything.

**Import a GitHub project:**
```bash
arb source add github Spidey6978/TransitOS
```

**Import an existing PDF resume:**
```bash
arb source add document path/to/resume.pdf
```

**View all your synced sources:**
```bash
arb source list
```
*(The system uses intelligent differential syncing to avoid re-processing unmodified sources.)*

### 3. Build a targeted resume

**Build for a predefined target:**
```bash
arb build --target backend
```

**Build against a raw job description:**
```bash
arb build --job path/to/job_description.txt
```

Generated files are isolated per build:
```text
build/<uuid>/
├── resume.tex
├── resume.log
└── resume.pdf
```

### 4. Other useful commands

```bash
# View or edit your canonical profile
arb profile show
arb profile edit

# Test generation without hitting the AI API
arb build --target backend --mock-ai

# Clear the local SQLite cache
arb cache clear
```

---

## 🧠 Why Facts Instead of Bullets?

Auto Resume Builder does **not** permanently store AI-generated resume bullets.

```text
Source
  ↓
Atomic Facts
  ↓
Canonical Profile
  ↓
Target + Job Description
  ↓
Relevant Facts
  ↓
Generated Bullets
```

The same accomplishment can therefore be presented differently for a backend role, research position, or another target without rewriting or corrupting the original career history.

The system follows a simple rule:

> **Missing evidence is never permission to manufacture evidence.**

---

## 🛠️ Tech Stack

| | |
|---|---|
| **Core** | Python |
| **AI** | Google Gemini (`google.genai`) |
| **Profile Storage** | YAML |
| **Caching** | SQLite |
| **Templating** | Jinja2 |
| **Typesetting** | LuaLaTeX |
| **Source Integration** | GitHub API |
| **Testing** | Pytest |

---

## 🗺️ What Comes Next

Auto Resume Builder is rapidly evolving into a fully autonomous, agentic career intelligence platform that builds context-aware, ATS-optimized, hyper-targeted resumes dynamically. 

The core ingestion and generation engines are functional and the architecture is stabilized. Our immediate roadmap focuses on unlocking more data sources and giving you precise manual control:

```text
✓ Phase 1-3: Core Infrastructure, Targeting, and Generation
✓ Phase 4.2: Universal Document Ingestion (PDFs)
✓ Phase 4.2.5: Source Registry & Differential Syncing

→ Phase 4.3: Manual Sources (CLI prompts & YAML editing helpers for fine-grained control)
→ Phase 4.4: LinkedIn Export Ingestion (ZIP, CSV, JSON)
→ Phase 4.5: GitHub Adapter v2 (Manifest parsing, dependency analysis, and richer evidence)
→ Phase 4.6: Non-engineering Sources (Academic ORCID integration, Portfolios)
```

Larger ideas and deliberately deferred improvements live in [`BACKLOG.md`](./BACKLOG.md) so they don't turn into feature creep.

---

## ⚠️ Current Limitations

GitHub is currently the primary automated source and repository understanding is still largely README-oriented. Project evidence is more mature than other career entity types, Gemini is the currently implemented AI provider, and the primary interface is the CLI.

These are the next areas of active development rather than features the project claims to have already solved.

---

## License

See [`LICENSE`](./LICENSE).

---

<p align="center">
  <b>One career history. Different opportunities. The right evidence for each.</b>
</p>