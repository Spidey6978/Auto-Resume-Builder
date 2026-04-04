Auto Resume Builder 🚀

An enterprise-grade, ATS-friendly resume generation pipeline. This project dynamically fetches your pinned GitHub repositories, uses a cascading AI pipeline (Google Gemini) to generate highly technical resume bullet points from your raw README.md files, and injects the data into a pristine LaTeX template.

✨ Core Features

AI-Powered Impact Parsing: Leverages a 40,000-token context window with Gemini (2.5/1.5 Flash) to analyze entire project READMEs, extracting complex math, logic, and architecture to generate exactly three 15-25 word ATS-optimized bullets per project.

Intelligent AI Fallbacks: Built-in graceful degradation. The script dynamically queries your API key's authorized models and cascades from gemini-2.5-flash down to gemini-1.0-pro to completely avoid rate-limit crashes.

Umbrella Projects: Intelligently groups decoupled multi-repo projects (e.g., a React frontend and FastAPI backend) into a single unified "Full-Stack" resume entry.

Bulletproof LaTeX Sanitization: Features a custom recursive sanitizer that automatically escapes special characters (&, %, $, _) while intelligently preserving raw URLs for hyperlinking, ensuring the LaTeX compiler never crashes.

Mock AI Dry-Runs: Includes a --mock-ai CLI flag for local UI debugging. Generates a fully compiled PDF using simulated bullets in milliseconds, saving your daily Gemini API quota.

Zero-Install Cloud CI/CD: Includes a GitHub Actions workflow (build_resume.yml) utilizing Tectonic to automatically compile and release your updated resume as a PDF artifact on every push.

🚀 Getting Started (Choose Your Path)

You can run this project entirely in the cloud without installing any software, or set it up locally for rapid template development.

Path A: The "Cloud-Only" Route (Zero Install)

Best if you just want to generate a resume without installing Python or LaTeX.

Fork this repository to your own GitHub account.

Go to your repository's Settings > Secrets and variables > Actions > New repository secret.

Name: GEMINI_API_KEY

Secret: (Paste your free Gemini API key from Google AI Studio)

In your browser, navigate to data/static_profile.example.yaml and copy its contents.

Create a new file in the data/ folder named static_profile.yaml, paste the contents, fill in your personal details, and commit the file.

Go to the Actions tab. The workflow will automatically run, fetch your repos, generate the AI bullets, compile the LaTeX, and provide a downloadable PDF in the Artifacts section!

Path B: Local Developer Setup

Best if you want to preview, tweak margins, and test your resume rapidly on your own machine.

1. Prerequisites

Python 3.8+

A LuaLaTeX-compatible Compiler: * Windows: MiKTeX or TeX Live

macOS: MacTeX

Linux: sudo apt-get install texlive-full

2. Installation & Setup

Clone the repository and run the automated setup wizard:

git clone [https://github.com/yourusername/auto-resume-builder.git](https://github.com/yourusername/auto-resume-builder.git)
cd auto-resume-builder
pip install -r requirements.txt

# Run the setup wizard to configure your API keys and profile template
python setup.py


The wizard will safely create your local .env file and generate a static_profile.yaml file for you.

3. Customize Your Profile

Open data/static_profile.yaml and fill in your details. You can define your dynamic GitHub fetching in two ways:

showcase_repos: List standard, standalone repositories.

grouped_repos: List multi-repo applications to have the AI fuse their READMEs into one full-stack entry.

4. Build and Compile

Step 1: The Dry Run (Highly Recommended)
Test your LaTeX formatting and margins without burning your API quota:

python src/main.py --mock-ai


Step 2: The Production Build
Once your layout looks perfect, run the full pipeline to fetch real AI bullets and compile the final PDF:

python src/main.py


Check the build/ directory for your pristine resume.pdf!

🛠️ Tech Stack

Orchestration: Python 3.10

Templating: Jinja2

Typesetting: LaTeX (LuaLaTeX engine / Tectonic)

APIs: GitHub REST API, Google Generative AI API (Gemini)

CI/CD: GitHub Actions
