Auto Resume Builder 🚀

An automated, ATS-friendly resume generation pipeline. This project dynamically fetches your pinned GitHub repositories, uses AI (Google Gemini) to generate professional bullet points from your README.md files, and compiles everything into a pristine PDF using LaTeX.

✨ Features

Dynamic Content: Automatically fetches tech stacks and repository data via the GitHub API.

AI-Powered Impact: Uses Gemini 2.5 Flash to synthesize repository READMEs into strong, action-oriented resume bullets.

Umbrella Projects: Intelligently groups multi-repo projects (e.g., a decoupled frontend and backend) into a single full-stack resume entry.

LaTeX Sanitization: Automatically escapes special characters (&, %, $, etc.) so your LaTeX compiler never crashes.

CI/CD Ready: Includes a GitHub Actions workflow to automatically compile and release your resume as a PDF artifact on every push.

🚀 How to Use (Choose Your Path)

You can run this project entirely in the cloud without installing anything, or you can set it up locally on your machine.

Path A: The "Cloud-Only" Route (Easiest)

Best if you don't want to install Python or LaTeX on your computer.

Fork this repository to your own GitHub account.

Go to your repository's Settings > Secrets and variables > Actions > New repository secret.

Name: GEMINI_API_KEY

Secret: (Paste your Gemini API key from Google AI Studio)

In your browser, navigate to data/static_profile.example.yaml. Copy its contents.

Create a new file in the data/ folder named static_profile.yaml, paste the contents, fill in your details, and commit the file.

Go to the Actions tab. The workflow will automatically run, generate your resume, and provide a downloadable PDF in the Artifacts section!

Path B: Local Setup & Compilation

Best if you want to preview and test your resume rapidly on your own machine.

1. Prerequisites

Python 3.8+

A LaTeX Compiler: * Windows: MiKTeX or TeX Live

macOS: MacTeX

Linux: sudo apt-get install texlive-full

2. Installation & Setup

Clone the repository, install dependencies, and run our automated setup wizard:

git clone [https://github.com/yourusername/auto-resume-builder.git](https://github.com/yourusername/auto-resume-builder.git)
cd auto-resume-builder
pip install -r requirements.txt

# Run the setup wizard to configure your API keys and profile template
python setup.py


The wizard will safely create your .env file and generate a static_profile.yaml file for you.

3. Customize Your Profile

Open data/static_profile.yaml and fill in your contact info, education, and skills.
Configure your GitHub projects using the showcase_repos or grouped_repos sections.

4. Build and Compile

Run the main orchestrator script:

python src/main.py


What happens when you run this?

The script fetches your repos from GitHub.

Gemini reads the documentation and generates bullet points.

All text is sanitized to make it LaTeX-safe.

Jinja injects the data into templates/resume_template.tex.

pdflatex compiles build/resume.tex into build/resume.pdf.

(Pro-tip: If you prefer editing layouts visually, you can copy the generated text inside build/resume.tex and paste it directly into an empty Overleaf project!)