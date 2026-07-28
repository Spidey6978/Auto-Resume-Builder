import requests
import base64
from typing import List, Dict, Optional, Any
from adapters.base import BaseAdapter
from core.cache import CacheManager


class GitHubAdapter(BaseAdapter):
    """
    Source adapter for fetching repository details and READMEs from GitHub.
    Uses CacheManager to prevent redundant HTTP requests.
    """

    CACHE_NAMESPACE = "github_api"

    def __init__(self, token: Optional[str] = None, cache_manager: Optional[CacheManager] = None):
        self.token = token
        self.cache = cache_manager or CacheManager()
        self.headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'

    def _get_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Performs a GET request with caching."""
        cached = self.cache.get(self.CACHE_NAMESPACE, url)
        if cached is not None:
            return cached

        headers = self.headers.copy()
        if self.token and self.token.strip():
            token_val = self.token.strip()
            prefix = "Bearer" if token_val.startswith("github_pat_") or token_val.startswith("ghp_") else "token"
            headers['Authorization'] = f"{prefix} {token_val}"

        response = requests.get(url, headers=headers)
        if response.status_code == 401 and 'Authorization' in headers:
            # Fallback to unauthenticated request for public repositories
            response = requests.get(url, headers={'Accept': 'application/vnd.github.v3+json'})

        if response.status_code != 200:
            print(f"  [!] GitHub HTTP {response.status_code} for {url}")
            return None

        data = response.json()
        self.cache.set(self.CACHE_NAMESPACE, url, data)
        return data

    def get_repo_data(self, username: str, repo_name: str) -> Optional[Dict[str, Any]]:
        """Fetches repository metadata, tech stack languages, and README content."""
        repo_url = f'https://api.github.com/repos/{username}/{repo_name}'
        data = self._get_url(repo_url)

        if not data:
            print(f"  [!] Failed to fetch {repo_name} from GitHub")
            return None

        # Fetch language breakdown
        langs_url = data.get('languages_url', '')
        tech_stack = []
        if langs_url:
            langs_data = self._get_url(langs_url)
            if langs_data and isinstance(langs_data, dict):
                tech_stack = list(langs_data.keys())

        # Fetch README
        readme_url = f'https://api.github.com/repos/{username}/{repo_name}/readme'
        readme_data = self._get_url(readme_url)
        readme_content = ""
        if readme_data and 'content' in readme_data:
            try:
                readme_content = base64.b64decode(readme_data['content']).decode('utf-8', errors='ignore')
            except Exception:
                readme_content = ""

        clean_name = data['name'].replace('-', ' ').replace('_', ' ').title()

        return {
            "name": clean_name,
            "raw_name": data['name'],
            "tech_stack": ", ".join(tech_stack) if tech_stack else "Various",
            "link": data.get('html_url', f"https://github.com/{username}/{repo_name}"),
            "readme_content": readme_content,
            "description": data.get('description', "No description provided.")
        }

    def fetch_projects(self, username: str, repo_list: List[str]) -> List[Dict[str, Any]]:
        """Fetches multiple repositories by name."""
        projects = []
        for repo in repo_list:
            data = self.get_repo_data(username, repo)
            if data:
                projects.append(data)
        return projects

    def fetch(self, username: str, repo_list: List[str], **kwargs) -> Dict[str, Any]:
        """BaseAdapter fetch contract implementation."""
        projects = self.fetch_projects(username, repo_list)
        return {"projects": projects}
