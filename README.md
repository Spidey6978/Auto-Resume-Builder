# Auto Resume Builder

> **Build one career profile. Generate the right resume for the job.**

Auto Resume Builder is a target-aware resume generation engine that transforms a single **Canonical Profile** into tailored, ATS-friendly resumes for specific roles and job descriptions.

Instead of maintaining multiple resume copies and manually rewriting them for every application, the engine separates **what is true about a candidate** from **what should appear on a particular resume**.

It ingests career evidence, extracts structured facts, evaluates them against the target role, plans the document, generates evidence-grounded resume bullets, and compiles the result into a polished LuaLaTeX PDF — automatically enforcing the target's page budget.

The result is a hybrid deterministic + AI pipeline where AI handles semantic extraction and writing, while ranking, targeting, provenance, caching, policy evaluation, and document constraints remain explicit and inspectable.

> **Project Status — Phase 3 Complete**
>
> The core pipeline from canonical profile → targeting → planning → generation → page-budget enforcement → PDF compilation is implemented.
>
> Current ingestion primarily supports GitHub repositories and manually maintained profile data. Multi-source ingestion and user-facing onboarding are planned next.

---

## The Idea

Most resume tailoring looks something like this:

```text
Copy old resume
      ↓
Read job description
      ↓
Guess what matters
      ↓
Delete some bullets
      ↓
Rewrite other bullets
      ↓
Fight the formatting
      ↓
Save resume_final_v7_REAL.pdf
      ↓
Repeat
```

Auto Resume Builder approaches the problem differently.

Your complete career history is stored once:

```text
                     ┌───────────────────┐
                     │ Canonical Profile │
                     │                   │
                     │ Everything known  │
                     │ about the user    │
                     └─────────┬─────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
               ▼                               ▼
        Target Knowledge                Job Description
      hiring conventions,              requirements,
      priorities & policies            skills & context
               │                               │
               └───────────────┬───────────────┘
                               ▼
                        Resume Planner
                               │
                    selects the evidence
                    worth presenting
                               │
                               ▼
                      Content Generator
                               │
                    converts evidence into
                    resume-ready language
                               │
                               ▼
                         PDF Compiler
```

The **profile stays stable**.

The **resume changes with the target**.

---

# Core Concepts

Auto Resume Builder deliberately separates several concepts that traditional resume generators often mix together.

## 1. Canonical Profile — What Is True?

`canonical_profile.yaml` is the source of truth for the candidate.

It contains structured career information such as:

- personal information
- education
- experience
- projects
- awards
- technical skills
- atomic facts describing accomplishments

A project does **not** permanently store AI-generated resume bullets.

Instead, it stores evidence such as:

```yaml
facts:
  - id: kerr-geodesics
    text: Implemented null geodesic integration for near-extremal Kerr spacetime
    fact_type: technical
    tags:
      - numerical-methods
      - general-relativity
      - python
    source_refs:
      - github:null-geodesic-raytracer
```

Generated wording belongs to the resume being built — not to the candidate's underlying history.

---

## 2. TargetKnowledge — What Matters?

Different applications reward different things.

An entry-level software engineering resume, an academic CV, and a consulting resume should not follow identical assumptions about:

- section priority
- page length
- technical depth
- measurable impact
- education
- projects
- publications
- ATS formatting
- hiring signals

`TargetKnowledge` represents researched hiring guidance independently from the candidate.

Knowledge can be composed from dimensions such as:

```text
domain
specialization
career stage
document type
geography
```

This keeps hiring conventions separate from personal career data.

---

## 3. ResumePlan — What Should We Show?

Given:

```text
Canonical Profile
        +
TargetKnowledge
        +
Job Description / Target
```

the targeting engine constructs a **ResumePlan**.

Facts are scored against signals such as:

- hard-skill overlap
- target relevance
- measurable impact
- implied traits
- researched hiring priorities
- provenance/evidence strength

The planner therefore decides **what deserves document space before the LLM decides how to phrase it**.

---

## 4. ResumeDocument — How Should We Say It?

Selected facts are passed to the content-generation layer.

The LLM does not invent a career history.

Its job is much narrower:

```text
Selected Evidence
       ↓
Content Generator
       ↓
Resume-ready language
```

Generated bullets remain presentation data and never overwrite the Canonical Profile.

---

# Architecture

```text
                         DATA SOURCES
                      GitHub / Manual
                             │
                             ▼
                       Source Adapter
                             │
                             ▼
                       Fact Extraction
                             │
                             ▼
                  ┌────────────────────┐
                  │ Canonical Profile  │
                  │  Career Source of  │
                  │       Truth        │
                  └─────────┬──────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
              ▼                           ▼
       Target / Loadout              Job Description
              │                           │
              └─────────────┬─────────────┘
                            │
                            ▼
                   Knowledge Resolver
                            │
                            ▼
                    Policy Evaluator
                            │
                            ▼
                      Fact Ranker
                            │
                     scored evidence
                            │
                            ▼
                     Resume Planner
                            │
                      ResumePlan
                            │
                            ▼
                   Content Generator
                            │
                      generated text
                            │
                            ▼
                    ResumeDocument
                            │
                            ▼
                  Jinja2 + LuaLaTeX
                            │
                            ▼
                      Compile PDF
                            │
                            ▼
                   ┌─────────────────┐
                   │ Within Budget?  │
                   └───────┬─────────┘
                       Yes │ │ No
                           │ └──────────────┐
                           ▼                ▼
                      resume.pdf     Overflow Resolver
                                            │
                                  remove lowest-priority
                                  removable content
                                            │
                                            └──► Recompile
```

---

# Features

## Universal Canonical Profile

Maintain one structured representation of your career instead of several independently edited resumes.

The Canonical Profile acts as the persistent source of truth while generated documents remain disposable views over that data.

---

## Target-Aware Resume Generation

Build against a predefined target:

```bash
python src/cli/main.py --build --target backend
```

or a specific job description:

```bash
python src/cli/main.py --build --job path/to/job_description.txt
```

The same candidate profile can therefore produce different resumes depending on what the application values.

---

## Deterministic-First Fact Ranking

Resume selection is not delegated entirely to an LLM.

The ranking layer evaluates structured facts against the target using explicit signals before generation occurs.

This gives the pipeline a useful separation of responsibilities:

```text
Deterministic systems decide:

    WHAT deserves space

AI decides:

    HOW selected evidence should be communicated
```

This reduces unnecessary model usage while making targeting decisions easier to inspect and debug.

---

## Dynamic Content Budgeting

Page limits are treated as document constraints rather than formatting problems.

After generation, the actual LuaLaTeX document is compiled and measured.

If it exceeds the allowed page budget:

```text
Initial ResumePlan
       ↓
Generate
       ↓
Compile PDF
       ↓
Measure actual pages
       ↓
      Overflow?
       ↓ yes
Remove lowest-priority removable bullet
       ↓
Recompile
       ↓
Repeat until valid
```

This avoids relying purely on character-count estimates and avoids immediately destroying readability through tiny fonts or aggressive margin compression.

The current implementation uses iterative removal of lower-priority content while preserving stronger targeted evidence.

---

## Structured Fact Extraction

Source material is not converted directly into polished resume bullets.

Instead:

```text
Source Material
      ↓
FactExtractor
      ↓
Atomic Facts
      ↓
Canonical Profile
      ↓
Targeting
      ↓
Resume Bullets
```

This allows the same accomplishment to be presented differently for different applications without changing the underlying truth.

The extractor follows a zero-fabrication policy: insufficient evidence should produce insufficient data, not invented achievements.

---

## GitHub Ingestion

Repositories can be synchronized directly into the Canonical Profile:

```bash
python src/cli/main.py --sync Spidey6978/TransitOS
```

The current GitHub ingestion pipeline can collect repository information, normalize the detected technology stack, extract structured technical facts using Gemini, and safely merge them into an existing profile.

Existing manually authored facts are preserved through provenance-aware merging.

> **Current limitation:** GitHub ingestion is still primarily README-oriented. Repository-wide multi-signal evidence extraction is planned for a later phase.

---

## Provenance-Aware Facts

Extracted facts retain information about where they came from.

This allows the system to distinguish:

```text
GitHub-derived fact
Manual fact
Future resume-imported fact
Future portfolio-derived fact
```

and update source-owned information without blindly deleting user-authored data.

Provenance also establishes the foundation for richer evidence validation as additional sources are introduced.

---

## Safe Profile Merging

Re-ingesting a project should not destroy manual edits.

The profile manager uses source provenance to replace only facts belonging to the source being synchronized while preserving manually created facts and human-controlled project information.

The system also fails loudly on malformed profile data rather than silently overwriting a corrupted YAML file.

---

## Input-Hash Caching

Repeated AI calls are avoided whenever the relevant input has not changed.

Generation fingerprints include information such as:

```text
prompt version
target
input facts
source content
generation context
```

Results are stored in:

```text
.cache/build_cache.db
```

Therefore:

```text
same facts
+ same target
+ same generation rules
        ↓
      CACHE HIT
        ↓
0 repeated generation calls
```

Changing the target or prompt version naturally invalidates the relevant cached output.

---

## Resilient AI Gateway

All model communication is isolated behind a centralized `AIGateway`.

It handles concerns including:

- dependency-injected credentials
- prompt/version-aware caching
- transient failure detection
- exponential retry/backoff
- rate-limit handling
- model fallback
- consistent failure behavior

The current implementation uses Google Gemini through the `google.genai` SDK.

The architecture keeps model communication separate from the rest of the resume pipeline so the core system does not need to depend directly on one provider forever.

---

## Isolated Build Workspaces

Every compilation receives a unique build ID:

```text
build/
└── <uuid>/
    ├── resume.tex
    ├── resume.log
    └── resume.pdf
```

This prevents concurrent builds from overwriting one another and avoids relying on globally shared output paths.

It also keeps the compiler compatible with future service/web execution.

---

## LuaLaTeX Compilation

Resume documents are rendered through:

```text
ResumeDocument
      ↓
Jinja2 Template
      ↓
LaTeX Sanitizer
      ↓
LuaLaTeX
      ↓
PDF
```

A recursive sanitizer escapes LaTeX-sensitive content while preserving values such as raw URLs used by `\href{}`.

---

# End-to-End Build Flow

A targeted build follows roughly this lifecycle:

```text
1. LOAD
   canonical_profile.yaml

2. RESOLVE
   target + TargetKnowledge + optional job description

3. RANK
   score candidate facts against the target

4. PLAN
   select evidence for the document

5. GENERATE
   transform selected evidence into resume bullets

6. RENDER
   construct ResumeDocument

7. COMPILE
   render Jinja2 → LuaLaTeX → PDF

8. MEASURE
   inspect actual page count

9. BUDGET
   remove lower-priority content if necessary

10. OUTPUT
    build/<uuid>/resume.pdf
```

---

# Installation

## Requirements

- Python **3.10+**
- LuaLaTeX distribution
- Google Gemini API key
- GitHub token *(optional for public repositories)*

### LaTeX

**Windows**

Install either:

- MiKTeX
- TeX Live

**macOS**

Install MacTeX.

**Linux**

For Debian/Ubuntu-based distributions:

```bash
sudo apt-get install texlive-full
```

---

## Clone the Repository

```bash
git clone https://github.com/Spidey6978/Auto-Resume-Builder.git
cd Auto-Resume-Builder
```

---

## Create a Virtual Environment

```bash
python -m venv venv
```

### Windows

```bash
.\venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GITHUB_TOKEN=your_github_personal_access_token_here
```

`GITHUB_TOKEN` is optional when accessing public repositories but is recommended to reduce unauthenticated API limitations.

Never commit `.env` or API credentials to source control.

---

# Usage

## 1. Populate the Canonical Profile

Career data lives in:

```text
data/canonical_profile.yaml
```

It can currently be maintained manually and enriched through supported source adapters.

### Import a GitHub Project

```bash
python src/cli/main.py --sync Spidey6978/TransitOS
```

The ingestion pipeline:

```text
GitHub
  ↓
SourceResult
  ↓
Fact Extraction
  ↓
Technology Normalization
  ↓
Provenance-Aware Merge
  ↓
Canonical Profile
```

Review the resulting profile after ingestion and edit it where necessary.

The Canonical Profile is intentionally human-readable and remains user-controlled.

---

## 2. Build for a Target

For a predefined target such as backend engineering:

```bash
python src/cli/main.py --build --target backend
```

---

## 3. Build Against a Job Description

```bash
python src/cli/main.py --build --job path/to/job_description.txt
```

The supplied job description becomes additional targeting context for ranking and planning.

---

## 4. Dry-Run Without AI Generation

```bash
python src/cli/main.py --build --target backend --mock-ai
```

Useful when testing:

- templates
- LaTeX configuration
- page layout
- compilation
- pipeline behavior

without consuming model calls.

---

## 5. Clear Cached AI Results

```bash
python src/cli/main.py --clear-cache
```

This forces future operations to regenerate results instead of using existing cached outputs.

---

# Output

Each build receives an isolated workspace:

```text
build/
└── 7f14c...
    ├── resume.tex
    ├── resume.log
    └── resume.pdf
```

The final generated document is:

```text
build/<build-id>/resume.pdf
```

---

# Project Structure

The exact structure may evolve, but the major architectural layers are:

```text
Auto-Resume-Builder/
│
├── data/
│   └── canonical_profile.yaml
│
├── knowledge/
│   └── ...
│
├── templates/
│   └── ...
│
├── src/
│   │
│   ├── adapters/
│   │   ├── base.py
│   │   └── github_adapter.py
│   │
│   ├── cli/
│   │   └── main.py
│   │
│   ├── core/
│   │   ├── ai_gateway.py
│   │   ├── cache_manager.py
│   │   ├── compiler.py
│   │   ├── fact_extractor.py
│   │   ├── fact_ranker.py
│   │   ├── generator.py
│   │   ├── normalizer.py
│   │   ├── pipeline.py
│   │   ├── profile_manager.py
│   │   └── target_engine.py
│   │
│   └── models/
│       ├── profile.py
│       ├── presentation.py
│       └── ...
│
├── tests/
│
├── BACKLOG.md
├── requirements.txt
└── README.md
```

---

# Design Principles

## Career Truth and Resume Presentation Are Different Things

The Canonical Profile should describe what happened.

The resume should describe the subset of that history that matters for a particular opportunity.

Generated language therefore never becomes canonical truth automatically.

---

## AI Is a Component, Not the Architecture

LLMs are useful for:

- extracting semantic information from unstructured sources
- understanding ambiguous language
- synthesizing concise natural-language bullets

They are not required to control every decision.

Where deterministic logic is sufficient, the system prefers deterministic logic.

---

## Evidence Before Eloquence

A polished sentence is useless if the underlying claim cannot be supported.

The intended hierarchy is:

```text
Evidence
   ↓
Fact
   ↓
Relevance
   ↓
Selection
   ↓
Generation
```

not:

```text
README
   ↓
"write something impressive"
```

---

## Fail Rather Than Fabricate

Missing evidence should never become permission to manufacture resume claims.

When extraction cannot establish a credible fact, the correct result is insufficient data — not a generic accomplishment invented to keep the document populated.

---

## Human Supervision Over Endless Prompting

The long-term product is not intended to become a resume chatbot that interrogates the user for every field.

The goal is:

```text
automatically gather what can be gathered
                 ↓
extract structured information
                 ↓
show the user what the system understood
                 ↓
let them correct or enrich it
                 ↓
automate everything repeatable afterwards
```

The user remains the authority over their career history.

---

## Optimize From Evidence, Not Speculation

The project intentionally avoids prematurely introducing infrastructure or complexity simply because it might someday be useful.

Caching, concurrency isolation, AI boundaries, provenance, and targeting exist because the current architecture requires them.

More complex infrastructure should follow demonstrated requirements.

Deferred ideas live in [`BACKLOG.md`](./BACKLOG.md) instead of silently expanding the current milestone.

---

# Current Limitations

Auto Resume Builder is still under active development.

The current version has several deliberate limitations:

- GitHub is the primary automated ingestion source.
- GitHub understanding is still largely README-oriented.
- Manual editing of the Canonical Profile is currently important.
- Project targeting is more mature than several other career entity types.
- Google Gemini is currently the implemented AI provider.
- The primary interface is currently the CLI.
- The knowledge bank covers only the targets that have been researched and configured.
- Web/mobile onboarding and profile management do not exist yet.

These are product boundaries, not claims that the underlying problems have been solved.

---

# Roadmap

The core targeted-resume pipeline is now functional.

The next major direction is **better evidence acquisition and profile onboarding**.

Broadly:

```text
Phase 1
Infrastructure & reliability
        ✓

Phase 2
Canonical profile + fact architecture
        ✓

Phase 3
Targeting + planning + content budgeting
        ✓

Phase 4
Multi-source ingestion & profile onboarding
        ◄── NEXT

Future
Web UI
Domain-aware experiences
Broader document types
Deployment & multi-user execution
```

Specific deferred ideas and architectural experiments are maintained separately in [`BACKLOG.md`](./BACKLOG.md) so they do not become accidental feature creep.

---

# Where This Is Going

The long-term goal is broader than automatically writing software-engineering resumes.

The architecture is being developed around a more general problem:

> **Given everything we know about a candidate, what evidence should be presented, how should it be presented, and what should be omitted for this particular opportunity?**

That means the eventual system can potentially support different career contexts without becoming a collection of unrelated resume generators.

```text
                     Universal Profile
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
         Engineering    Research     Consulting
             │             │             │
             ▼             ▼             ▼
         SWE Resume    Academic CV   Consulting Resume
```

Different domains may require different sources, entities, hiring policies, document structures, and page conventions.

They should not require different core engines.

---

# Tech Stack

| Layer | Technology |
|---|---|
| Core Engine | Python 3.10+ |
| AI | Google Gemini (`google.genai`) |
| Structured Profile | YAML |
| Cache | SQLite |
| Templates | Jinja2 |
| Typesetting | LuaLaTeX |
| Source Integration | GitHub API |
| Validation / Testing | Pytest |

---

# Contributing

The project is evolving quickly and several interfaces may change as multi-source ingestion and broader domain support are introduced.

If you're experimenting with the project, bug reports, architecture discussions, and focused contributions are welcome.

When proposing larger features, check [`BACKLOG.md`](./BACKLOG.md) first — the idea may already be deliberately deferred rather than forgotten.

---

# License

See [`LICENSE`](./LICENSE) for licensing information.

---

<p align="center">
  <b>One career history. Different opportunities. The right evidence for each.</b>
</p>