# Auto Resume Builder 

An enterprise-grade, ATS-friendly resume compiler. This tool dynamically ingests your projects from GitHub, extracts architecture and impact using Google Gemini AI, and compiles tailored, 1-page resumes using pristine LuaLaTeX templates.

---

##  Core Features

* **Input-Hash SQLite Disk Caching (`.cache/build_cache.db`)**: Computes SHA256 fingerprints for raw READMEs and LLM prompts. Re-running `resume build` on unchanged repositories consumes **0 Gemini API calls** and **0 GitHub API calls**, executing in sub-second time.
* **Centralized AI Gateway (`AIGateway`)**: Enforces rate-limit safety, retries, and automatic model fallback cascades (`gemini-2.5-flash` → `gemini-1.5-flash` → `gemini-1.5-pro` → `gemini-pro`) to eliminate quota crashes.
* **Modular Source Adapters (`src/adapters/`)**: Extensible adapter system (`GitHubAdapter`, and future adapters for LinkedIn CSV exports and legacy PDF resumes). Includes fine-grained token authentication with automatic unauthenticated fallback for public repos.
* **Umbrella Projects**: Groups decoupled multi-repo projects (e.g., a React frontend and FastAPI backend) into a single unified "Full-Stack" resume entry.
* **Bulletproof LaTeX Sanitization**: Custom recursive sanitizer (`src/core/sanitizer.py`) that automatically escapes special characters (`&`, `%`, `$`, `_`, `#`, `{`, `}`) while preserving raw URLs for `\href{}` links.
* **Mock AI Dry-Runs (`--mock-ai`)**: Instantly test LaTeX formatting and margins using simulated bullets in milliseconds without touching any API keys.
* **Cache Management (`--clear-cache`)**: Easily flush local SQLite caches when you want to force fresh data extraction.

---

## Architecture Overview

```text
src/
├── core/
│   ├── cache.py          # SQLite disk cache (namespace + SHA256 key hashing)
│   ├── ai_gateway.py     # Centralized Gemini AI Manager (cache, rate limits, model fallback)
│   ├── sanitizer.py      # Recursive LaTeX character escaping
│   └── compiler.py       # Jinja2 template rendering + LuaLaTeX PDF compiler
├── adapters/
│   ├── base.py           # Abstract BaseAdapter interface
│   └── github_adapter.py # GitHub REST API adapter with cached HTTP requests
├── models/
│   └── profile.py        # Dataclass schemas (ProfileData, ProjectItem)
└── cli/
    └── main.py           # CLI entry point and build orchestrator
```

---

## Step-by-Step Setup & Usage Guide

### 1. Prerequisites

* **Python 3.8+**
* **LuaLaTeX Compiler** (Required for local PDF compilation):
  * **Windows**: [MiKTeX](https://miktex.org/) or [TeX Live](https://www.tug.org/texlive/)
  * **macOS**: [MacTeX](https://www.tug.org/mactex/)
  * **Linux**: `sudo apt-get install texlive-full`

---

### 2. Installation & Configuration

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/auto-resume-builder.git
   cd auto-resume-builder
   ```

2. **Set up a Virtual Environment & Install Dependencies**:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Configure Environment Variables (`.env`)**:
   Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GITHUB_TOKEN=your_github_personal_access_token_here
   ```
   * *Gemini API Key*: Get a free key at [Google AI Studio](https://aistudio.google.com/).
   * *GitHub Token*: Optional for public repos, recommended for private repos and higher rate limits.

4. **Customize Your Profile (`data/static_profile.yaml`)**:
   Copy or edit `data/static_profile.yaml` to specify your details and repositories:
   ```yaml
   github_username: "YourGitHubUsername"

   showcase_repos:
     - "MyCoolRepo"
     - "Raytracer"
     - "TransitOS" # Use one repository when it contains the full application

   name: "Your Name"
   phone: "+1 123 456 7890"
   email: "you@example.com"
   ```

---

### 3. Usage Commands

#### Option A: Quick Dry-Run (No API Quota Used)
Test your LaTeX template rendering and PDF layout in milliseconds:
```bash
python src/main.py --mock-ai
```

#### Option B: Full Production Build
Fetch repository data, generate/retrieve cached AI bullets, and compile the final PDF:
```bash
python src/main.py
```
* The output PDF will be saved at `build/resume.pdf`.

#### Option C: Clear Cache & Force Fresh AI Generation
Flush your local SQLite cache database (`.cache/build_cache.db`) and re-query Gemini for all repositories:
```bash
python src/main.py --clear-cache
```

---

## 🛠️ Tech Stack

* **Language**: Python 3.10+
* **AI Engine**: Google Gemini API via `AIGateway` (`gemini-2.5-flash` / `1.5-flash`)
* **Caching**: SQLite (`.cache/build_cache.db`)
* **Templating**: Jinja2 (`templates/resume_template.tex`)
* **Typesetting**: LuaLaTeX Engine
* **APIs**: GitHub REST API v3
