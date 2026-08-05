# Auto Resume Builder

A target-aware resume generation engine that turns a single **Canonical Profile** into tailored, ATS-friendly resumes for specific roles and job descriptions.

Instead of maintaining multiple resume copies, Auto Resume Builder stores your career history as structured facts, ranks the most relevant evidence for each target, generates grounded resume bullets, and compiles them into a polished LuaLaTeX PDF — automatically trimming lower-priority content when the document exceeds its page budget.

> **Status:** Core targeting and generation pipeline complete. Currently supports GitHub ingestion, with multi-source ingestion planned next.

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
   Create a `.env` file in the root of the project:

   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GITHUB_TOKEN=your_github_token_here
   ```

---

## 💻 Usage

### Import a GitHub project

```bash
python src/cli/main.py --sync Spidey6978/TransitOS
```

The repository is analyzed into structured facts and merged into:

```text
data/canonical_profile.yaml
```

### Build for a target

```bash
python src/cli/main.py --build --target backend
```

### Build against a job description

```bash
python src/cli/main.py --build --job path/to/job_description.txt
```

### Test without AI calls

```bash
python src/cli/main.py --build --target backend --mock-ai
```

Generated files are isolated per build:

```text
build/<uuid>/
├── resume.tex
├── resume.log
└── resume.pdf
```

### Clear cached generations

```bash
python src/cli/main.py --clear-cache
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

## 🗺️ Roadmap

The core resume engine is functional. The next major focus is making the Canonical Profile easier and richer to populate.

```text
✓ Infrastructure & caching
✓ Canonical profile + fact extraction
✓ Targeting + fact ranking
✓ Resume planning + content budgeting

→ Multi-source ingestion
→ Resume / CV import
→ Richer GitHub evidence extraction
→ Domain-aware onboarding
→ Web UI
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