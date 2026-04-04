import os
import yaml
import subprocess
import time
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
from github_fetcher import fetch_github_projects, get_repo_data
from llm_parser import generate_bullets_from_readme
from sanitizer import sanitize_data, escape_latex

# Load API keys from the .env file
load_dotenv()

def compile_pdf(tex_path):
    """Compiles the generated .tex file into a PDF."""
    
    # If this script is running inside GitHub Actions, we skip local compilation
    # because the Action uses the 'setup-tectonic' step to compile instead.
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("Running in CI/CD. Skipping local compilation; Action will handle it.")
        return

    print("Compiling PDF...")
    try:
        # Runs pdflatex. -interaction=nonstopmode prevents it from hanging if there's a syntax error.
        subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory', os.path.dirname(tex_path), tex_path],
            check=True,
            stdout=subprocess.DEVNULL
        )
        print("PDF generated successfully.")
    except FileNotFoundError:
        print("Error: pdflatex not found. Please install a LaTeX distribution (like TeX Live) or use Tectonic.")
    except subprocess.CalledProcessError:
        print("Error: LaTeX compilation failed. Check the .log file in the build folder.")

def main():
    print("Starting Resume Build Process...")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Prioritize the real user data
    data_path = os.path.join(base_dir, 'data', 'static_profile.yaml') 
    
    # Fallback to dummy data if real profile doesn't exist yet (for public clones)
    if not os.path.exists(data_path):
        print("Real static_profile.yaml not found. Falling back to dummy data.")
        data_path = os.path.join(base_dir, 'data', 'static_profile.yaml')

    with open(data_path, 'r') as file:
        raw_data = yaml.safe_load(file)

    github_user = raw_data.get('github_username')
    github_token = os.getenv("GITHUB_TOKEN")
    
    all_projects = []

    # 1. Process Grouped Projects (The "Umbrella" Feature)
    for group in raw_data.get('grouped_repos', []):
        print(f"Processing Umbrella Project: {group['name']}...")
        combined_readme = ""
        combined_tech = set()
        
        for repo_name in group['repos']:
            data = get_repo_data(github_user, repo_name, github_token)
            if data:
                combined_readme += f"\n--- {repo_name} ---\n{data.get('readme_content', '')}"
                tech = data.get('tech_stack', "")
                if tech and tech != "Various":
                    # Split languages and add to a set to remove duplicates (e.g., Python from both frontend/backend)
                    combined_tech.update([t.strip() for t in tech.split(',')])
        
        # Generate full-stack bullets
        bullets = generate_bullets_from_readme(group['name'], combined_readme, is_umbrella=True)
        time.sleep(4) # Rate limit pacing
        
        all_projects.append({
            "name": group['name'],
            "tech_stack": ", ".join(list(combined_tech)[:5]), # Keep max 5 languages so it fits on one line
            "link": f"https://github.com/{github_user}/{group['repos'][0]}",
            "bullets": bullets 
        })

    # 2. Process Individual Showcase Repos
    showcase_names = raw_data.get('showcase_repos', [])
    if showcase_names:
        repos = fetch_github_projects(github_user, showcase_names, github_token)
        for r in repos:
            # Fallback to repo description if README is too short
            content = r['readme_content'] if len(r.get('readme_content', '')) > 50 else r.get('description', '')
            bullets = generate_bullets_from_readme(r['name'], content, is_umbrella=False)
            time.sleep(4) # Rate limit pacing
            
            all_projects.append({
                "name": r['name'],
                "tech_stack": r['tech_stack'],
                "link": r['link'],
                "bullets": bullets
            })

    # 3. Handle Manual Projects (Hardware, specific jobs, etc.) & Merge
    manual_projects = raw_data.get('projects', [])
    all_projects.extend(manual_projects)

    # 4. Prepare and Sanitize the whole data structure
    final_data = raw_data.copy()
    final_data['projects'] = all_projects
    
    # 🚨 BOMB DEFUSED: The Global Sanitization
    # We recursively escape LaTeX characters across the ENTIRE profile (summary, skills, bullets)
    safe_data = sanitize_data(final_data) 

    # 5. Render Template
    env = Environment(
        loader=FileSystemLoader(os.path.join(base_dir, 'templates')),
        block_start_string='<%', block_end_string='%>',
        variable_start_string='<<', variable_end_string='>>'
    )
    
    # 🚨 Inject our sanitizer directly into Jinja as a filter
    env.filters['escape_latex'] = escape_latex
    
    try:
        template = env.get_template('resume_template.tex')
        # Pass the sanitized data to the template, NOT the raw data
        rendered_resume = template.render(safe_data)
        
        build_dir = os.path.join(base_dir, 'build')
        os.makedirs(build_dir, exist_ok=True)
        tex_output_path = os.path.join(build_dir, 'resume.tex')
        
        with open(tex_output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_resume)

        print(f"LaTeX file generated at: {tex_output_path}")
        compile_pdf(tex_output_path)
        
    except Exception as e:
        print(f"Error during rendering: {e}")

if __name__ == "__main__":
    main()