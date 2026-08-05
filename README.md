# Auto Resume Builder

A target-aware resume generation engine that turns a single **Canonical Profile** into tailored, ATS-friendly resumes for specific roles and job descriptions.

Instead of maintaining multiple resume copies, Auto Resume Builder stores your career history as structured facts, ranks the most relevant evidence for each target, generates grounded resume bullets, and compiles them into a polished PDF (via Tectonic) — automatically trimming lower-priority content when the document exceeds its page budget.

> **Status:** Core targeting, generation pipeline, and universal document ingestion are complete. Supports GitHub (v2), PDF/Document, LinkedIn data exports, and CLI manual ingestion with intelligent differential syncing.

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

- **Python 3.13+**: Ensure Python is installed and available in your PATH.
- **LaTeX Distribution**: You must have `tectonic` installed on your system (recommended), or `lualatex` as a fallback.
  - **Tectonic**: Install via `cargo install tectonic` or follow [official docs](https://tectonic-typesetting.github.io/en-US/).
  - **LuaLaTeX**: Install TeX Live (Linux) or MiKTeX (Windows).
- **API Keys**:
  - **Google Gemini API Key**: Required for the generation engine.
  - **GitHub Token**: Optional but highly recommended to avoid API rate limits when fetching repositories.

### Installation

Auto Resume Builder is distributed as a standalone Python wheel (`.whl`). You don't need to clone the repository or understand the source code to use it.

1. **Set up a virtual environment (Recommended)**
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

2. **Download and Install the latest Release**
   Head over to the [GitHub Releases](https://github.com/Spidey6978/Auto-Resume-Builder/releases) page and download the latest `.whl` file (e.g., `auto_resume_builder-0.1.0a1-py3-none-any.whl`).

   Then install it via pip:
   ```bash
   pip install path/to/auto_resume_builder-0.1.0a1-py3-none-any.whl
   ```
   *(This automatically installs all dependencies like Jinja2 and PyYAML).*

3. **Initialize ARB**
   The application now handles its own initialization and setup. Since it is installed globally in your virtual environment, simply run:

   ```bash
   arb init
   ```
   
   This will guide you through setting up your user data directory, creating a blank profile, and configuring your API keys.

---

## 💻 Usage

Auto Resume Builder is driven by a powerful CLI command: `arb`.

### 1. Check your setup

```bash
arb doctor
```
Verifies your Python version, user data directories, API keys, and LaTeX compilers.

### 2. Ingest your career history (Data Sources)

Auto Resume Builder extracts structured facts from your existing data without destroying anything.

**Import a GitHub project (v2):**
```bash
arb source add github Spidey6978/TransitOS
```
*Note: GitHub adapter v2 automatically scans Git trees to locate project manifests (like `package.json` or `requirements.txt`), pulling down exact tech stacks.*

**Import an existing PDF resume:**
```bash
arb source add document path/to/resume.pdf
```

**Import a LinkedIn data export:**
```bash
arb source add linkedin path/to/linkedin_data.zip
```
*Note: The LinkedIn adapter parses your raw export `.zip` to structurally extract positions, education, projects, and skills natively without AI parsing.*

**Manually input facts:**
```bash
arb source add manual
```
*Prompts you interactively to add experiences, projects, awards, or education directly to your canonical profile.*

**View all your synced sources:**
```bash
arb source list
```
*(The system uses intelligent deterministic SHA-256 syncing to avoid re-processing unmodified sources.)*

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
| **Typesetting** | Tectonic (or LuaLaTeX) |
| **Source Integration** | GitHub API, Local Parsers |
| **Testing** | Pytest |

---

## 🗺️ What Comes Next

Auto Resume Builder is rapidly evolving into a fully autonomous, agentic career intelligence platform that builds context-aware, ATS-optimized, hyper-targeted resumes dynamically. 

The core ingestion and generation engines are functional, and the architecture is stabilized. With Phase 4 (Universal Data Ingestion) officially complete, you can now seamlessly collect your career history across GitHub, LinkedIn, PDFs, and manual entry.

Our immediate roadmap focuses on unlocking entirely new candidate domains and giving you more control over the generation process:

```text
✓ Phase 4: Universal Data Ingestion (GitHub v2, LinkedIn, Manual, Documents, Source Merging)

→ Phase 4.6: Non-engineering Domains (Academic CVs, Consulting, Medical)
→ Phase 5: The "Interactive Grilling" Planner (An AI agent interviews you to align on design decisions)
→ Phase 6: End-to-End Orchestration (Self-managing subagents for continuous background syncing)
```

Larger ideas and deliberately deferred improvements live in [`BACKLOG.md`](./BACKLOG.md) so they don't turn into feature creep.

---

## ⚠️ Current Limitations

The system currently defaults heavily toward SWE (Software Engineering) targets, and Gemini is the solely implemented AI provider. We are expanding to cross-domain integrations soon.

---

## License

See [`LICENSE`](./LICENSE).

---

<p align="center">
  <b>One career history. Different opportunities. The right evidence for each.</b>
</p>