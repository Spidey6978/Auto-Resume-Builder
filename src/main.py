import os
import yaml
import jinja2
from sanitizer import sanitize_data
from github_fetcher import fetch_github_projects
from llm_parser import generate_bullets_from_readme
from dotenv import load_dotenv

def main():
    print("Starting Resume Build Process...")
    load_dotenv() # Load environment variables from .env

    # 1. Setup paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # UPDATE: Pointing to your dummy file now!
    data_path = os.path.join(base_dir, 'data', 'dummy_static_profile.yaml')
    
    template_dir = os.path.join(base_dir, 'templates')
    build_dir = os.path.join(base_dir, 'build')

    # Ensure build directory exists
    os.makedirs(build_dir, exist_ok=True)

    # 2. Load the YAML data
    print(f"Loading data from {os.path.basename(data_path)}...")
    try:
        with open(data_path, 'r', encoding='utf-8') as file:
            raw_data = yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Error: Could not find {data_path}. Please create it first.")
        return

    # --- NEW GITHUB INTEGRATION ---
    if 'github_username' in raw_data and 'showcase_repos' in raw_data:
        gh_token = os.getenv('GITHUB_TOKEN')
        fetched_projects = fetch_github_projects(
            raw_data['github_username'], 
            raw_data['showcase_repos'],
            token=gh_token
        )
        
        # Create projects list if it doesn't exist, then append fetched projects
        if 'projects' not in raw_data or raw_data['projects'] is None:
            raw_data['projects'] = []
            
        # Parse READMEs with LLM
        print("Parsing READMEs with LLM to generate impact bullets...")
        for proj in fetched_projects:
            if proj.get('readme_content'):
                print(f"  -> Generating bullets for {proj['name']}...")
                proj['bullets'] = generate_bullets_from_readme(proj['name'], proj['readme_content'])
            
            # Clean up the payload before it hits LaTeX to prevent bloat
            proj.pop('readme_content', None)
            
        raw_data['projects'].extend(fetched_projects)
    # ------------------------------

    # 3. Sanitize data to prevent LaTeX crashes
    print("Sanitizing data for LaTeX compatibility...")
    safe_data = sanitize_data(raw_data)

    # 4. Configure Jinja2 Environment
    # We change the delimiters so Jinja doesn't clash with LaTeX's { }
    print("Configuring Jinja2 templating engine...")
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        block_start_string='<%',
        block_end_string='%>',
        variable_start_string='<<',
        variable_end_string='>>',
        comment_start_string='<#',
        comment_end_string='#>',
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=False # We handle escaping manually via our sanitizer
    )

    # 5. Load Template and Render
    print("Rendering LaTeX template...")
    template = env.get_template('resume_template.tex')
    rendered_resume = template.render(safe_data)

    # 6. Save the output
    output_path = os.path.join(build_dir, 'resume.tex')
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(rendered_resume)
        
    print(f"Success! Generated LaTeX resume at: {output_path}")
    print("\nNext steps:")
    print("Run 'pdflatex build/resume.tex' or 'tectonic build/resume.tex' to generate the PDF.")

if __name__ == "__main__":
    main()