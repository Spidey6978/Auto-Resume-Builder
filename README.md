Auto Resume Builder 🚀

An automated resume generation pipeline that uses Python, Jinja2, and LaTeX to build ATS-friendly resumes programmatically.

This project aims to automate the tedious process of updating a resume by extracting dynamic content (like projects) from the GitHub API, utilizing an LLM to generate impact-driven bullet points, and compiling it directly into a pristine PDF using LaTeX.

🏗️ Architecture

Templating: Jinja2 + LaTeX

Data Sources: GitHub API (for dynamic projects) + Local YAML (for static profile info)

Compiler: Tectonic / pdflatex

🚀 Getting Started

1. Prerequisites

Ensure you have Python 3.8+ installed, along with a LaTeX compiler (like texlive or tectonic).

2. Installation

Clone the repository and install the required Python packages:

git clone [https://github.com/yourusername/auto-resume-builder.git](https://github.com/yourusername/auto-resume-builder.git)
cd auto-resume-builder
pip install -r requirements.txt


3. Setup Your Profile Data

For privacy reasons, personal data is not tracked in this repository. You need to create your own profile data file.

Copy the provided example template:

cp data/static_profile.example.yaml data/static_profile.yaml


Open data/static_profile.yaml and fill it in with your actual personal information, education, and static experience.

(Note: data/static_profile.yaml is included in .gitignore so your personal details will never be accidentally committed to GitHub).

4. Build the Resume

Run the orchestrator script to inject your data into the LaTeX template and sanitize it:

python src/main.py


This will generate a build/resume.tex file.

5. Compile to PDF

Compile the generated .tex file into a PDF:

pdflatex build/resume.tex
# OR if using tectonic:
# tectonic build/resume.tex


📝 Roadmap

[x] Basic Jinja -> LaTeX templating engine

[x] LaTeX special character sanitization

[ ] GitHub API integration to fetch pinned repositories

[ ] LLM Integration (Gemini/OpenAI) to parse READMEs into bullet points

[ ] GitHub Actions CI/CD pipeline for automated cloud building