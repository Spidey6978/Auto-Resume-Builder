import requests
import base64

def get_repo_data(username, repo_name, token=None):
    headers = {'Accept': 'application/vnd.github.v3+json'}
    if token:
        headers['Authorization'] = f'token {token}'
        
    # Fetch main repo details
    url = f'https://api.github.com/repos/{username}/{repo_name}'
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"  [!] Failed to fetch {repo_name}: HTTP {response.status_code}")
        return None
        
    data = response.json()
    
    # Fetch languages to automatically build the "tech_stack" string
    langs_url = data['languages_url']
    langs_response = requests.get(langs_url, headers=headers)
    tech_stack = []
    if langs_response.status_code == 200:
        tech_stack = list(langs_response.json().keys())

    # Fetch README for LLM parsing
    readme_url = f'https://api.github.com/repos/{username}/{repo_name}/readme'
    readme_response = requests.get(readme_url, headers=headers)
    readme_content = ""
    if readme_response.status_code == 200:
        readme_data = readme_response.json()
        readme_content = base64.b64decode(readme_data['content']).decode('utf-8', errors='ignore')

    # Clean up the repo name for the resume (e.g., "multiplayer-chess" -> "Multiplayer Chess")
    clean_name = data['name'].replace('-', ' ').replace('_', ' ').title()

    return {
        "name": clean_name,
        "tech_stack": ", ".join(tech_stack) if tech_stack else "Various",
        "link": data['html_url'],
        "readme_content": readme_content,
        "bullets": [data['description'] or "No description provided."]
    }
    
def fetch_github_projects(username, repo_list, token=None):
    print(f"Fetching {len(repo_list)} projects for {username} from GitHub...")
    projects = []
    for repo in repo_list:
        print(f"  -> Fetching {repo}...")
        repo_data = get_repo_data(username, repo, token)
        if repo_data:
            projects.append(repo_data)
            
    return projects