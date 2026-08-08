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

Auto Resume Builder is now available as **standalone executables** (Windows, Linux, macOS) and a Python package.

#### Option A: Standalone Executable (No Python Required)
The easiest way to use ARB is to download the standalone executable for your operating system.
1. Head over to the [GitHub Releases](https://github.com/Spidey6978/Auto-Resume-Builder/releases) page.
2. Download the binary for your OS (`arb-windows-x64.exe`, `arb-linux-x64`, or `arb-macos-x64`) from the latest release.
3. Open your terminal and run it directly.

On Windows (PowerShell/Command Prompt):
```powershell
.\arb-windows-x64.exe init
```

On Linux/macOS:
```bash
chmod +x arb-linux-x64
./arb-linux-x64 init
```
*(No Python, `pip`, or virtual environment is required!)*

#### Option B: Python Wheel (For Developers/macOS/Linux)
If you prefer installing via Python or are on a non-Windows OS, you can install the `.whl` package.
1. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
2. Download the `.whl` file from the [GitHub Releases](https://github.com/Spidey6978/Auto-Resume-Builder/releases) page and install it:
   ```bash
   pip install path/to/auto_resume_builder-0.1.0a1-py3-none-any.whl
   ```
3. Initialize the application:
   ```bash
   arb init
   ```

### Setup & Initialization

Whether you downloaded the `.exe` or installed the Python package, running the `init` command will guide you through setting up your user data directory, creating a blank canonical profile, and securely configuring your API keys.

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

Our immediate roadmap is structured to gather real-world friction and feedback before expanding horizontally:

```text
✓ Phase 4: Universal Data Ingestion (GitHub v2, LinkedIn, Manual, Documents, Source Merging)
✓ Phase 4.6 & 4.7: Packaging & Standalone Distribution (Windows, Linux, macOS releases)

→ ALPHA FREEZE: Gathering UX and correctness feedback from early friends/adopters
→ Phase 5.0: Productization & Core UX improvements based on feedback
→ Phase 6.0: Multi-domain expansion (Academic CVs, Consulting, Medical)
→ Phase 7.0: Web UI & End-to-End Orchestration
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