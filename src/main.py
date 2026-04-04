import os
import yaml
import subprocess
import time
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
from github_fetcher import fetch_github_projects, get_repo_data
from llm_parser import generate_bullets_from_readme
from sanitizer import sanitize_for_latex  # Renamed for clarity

load_dotenv()

def compile_pdf(tex_path):
    """Compiles the generated .tex file into a PDF."""
    print("Compiling PDF...")
    try:
        # Using pdflatex (requires TeX Live / MiKTeX installed)
        # -interaction=nonstopmode ensures it doesn't hang on errors
        subprocess.run(
            ['pdflatex', '-interaction=nonstopmode', '-output-directory', os.path.dirname(tex_path), tex_path],
            check=True,
            stdout=subprocess.DEVNULL
        )
        print("PDF generated successfully.")
    except FileNotFoundError:
        print("Error: pdflatex not found. Please install a LaTeX distribution.")
    except subprocess.CalledProcessError:
        print("Error: LaTeX compilation failed. Check the .log file in the build folder.")

def main():
    print("Starting Resume Build Process...")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, 'data', 'dummy_static_profile.yaml')
    
    with open(data_path, 'r') as file:
        raw_data = yaml.safe_load(file)

    github_user = raw_data.get('github_username')
    github_token = os.getenv("GITHUB_TOKEN")
    
    all_projects = []

    # 1. Process Grouped Projects (Umbrella)
    for group in raw_data.get('grouped_repos', []):
        print(f"Processing Umbrella: {group['name']}...")
        combined_readme = ""
        combined_tech = set()
        
        for repo_name in group['repos']:
            data = get_repo_data(github_user, repo_name, github_token)
            if data:
                combined_readme += f"\n--- {repo_name} ---\n{data.get('readme_content', '')}"
                # Extract tech stack if available
                tech = data.get('tech_stack', "")
                if tech and tech != "Various":
                    combined_tech.update([t.strip() for t in tech.split(',')])
        
        # LLM Generation
        bullets = generate_bullets_from_readme(group['name'], combined_readme, is_umbrella=True)
        
        # Pacing the API to avoid 429 Rate Limit Error
        time.sleep(4)
        
        all_projects.append({
            "name": group['name'],
            "tech_stack": ", ".join(list(combined_tech)[:5]),
            "link": f"https://github.com/{github_user}/{group['repos'][0]}",
            "bullets": [sanitize_for_latex(b) for b in bullets]
        })

    # 2. Process Individual Showcase Repos
    showcase_names = raw_data.get('showcase_repos', [])
    if showcase_names:
        repos = fetch_github_projects(github_user, showcase_names, github_token)
        # Sort by most recent push if the data is available in r['updated_at']
        for r in repos:
            content = r['readme_content'] if len(r.get('readme_content', '')) > 50 else r.get('description', '')
            bullets = generate_bullets_from_readme(r['name'], content, is_umbrella=False)
            
            # Pacing the API to avoid 429 Rate Limit Error
            time.sleep(4)
            
            all_projects.append({
                "name": r['name'],
                "tech_stack": r['tech_stack'],
                "link": r['link'],
                "bullets": [sanitize_for_latex(b) for b in bullets]
            })

    # 3. Handle Manual Projects & Merge
    manual_projects = raw_data.get('projects', [])
    for mp in manual_projects:
        mp['bullets'] = [sanitize_for_latex(b) for b in mp.get('bullets', [])]
    
    all_projects.extend(manual_projects)

    # 4. Prepare and Sanitize the whole data structure
    final_data = raw_data.copy()
    final_data['projects'] = all_projects
    
    # We apply specific LaTeX escaping to all string values
    # You should implement this in your sanitizer.py
    # safe_data = recursive_latex_sanitize(final_data) 

    # 5. Render Template
    env = Environment(
        loader=FileSystemLoader(os.path.join(base_dir, 'templates')),
        block_start_string='<%', block_end_string='%>',
        variable_start_string='<<', variable_end_string='>>'
    )
    
    try:
        template = env.get_template('resume_template.tex')
        rendered_resume = template.render(final_data)
        
        build_dir = os.path.join(base_dir, 'build')
        os.makedirs(build_dir, exist_ok=True)
        tex_output_path = os.path.join(build_dir, 'resume.tex')
        
        with open(tex_output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_resume)

        print(f"LaTeX file generated at: {tex_output_path}")
        
        # 6. AUTO-COMPILE STEP
        compile_pdf(tex_output_path)
        
    except Exception as e:
        print(f"Error during rendering: {e}")

if __name__ == "__main__":
    main()