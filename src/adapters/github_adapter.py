import requests
import base64
import logging
from typing import List, Dict, Optional, Any
from adapters.base import BaseAdapter
from core.cache import CacheManager

logger = logging.getLogger(__name__)

class GitHubAdapter(BaseAdapter):
    """
    Source adapter for fetching repository details and READMEs from GitHub.
    Uses CacheManager with ETag HTTP conditional requests for cheap cache freshness validation.
    """

    CACHE_NAMESPACE = "github_api"

    def __init__(self, token: Optional[str] = None, cache_manager: Optional[CacheManager] = None):
        self.token = token
        self.cache = cache_manager or CacheManager()
        self.headers = {'Accept': 'application/vnd.github.v3+json'}
        if self.token and self.token.strip():
            token_val = self.token.strip()
            prefix = "Bearer" if token_val.startswith("github_pat_") or token_val.startswith("ghp_") else "token"
            self.headers['Authorization'] = f"{prefix} {token_val}"

    def _get_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Performs a GET request with ETag conditional validation against the local cache.
        Sends 'If-None-Match' when a cached ETag exists.
        """
        cached_meta = self.cache.get_with_meta(self.CACHE_NAMESPACE, url)
        cached_payload, cached_etag = cached_meta if cached_meta else (None, None)

        headers = self.headers.copy()
        if cached_etag:
            headers['If-None-Match'] = cached_etag

        try:
            response = requests.get(url, headers=headers)

            # 1. Handle HTTP 304 Not Modified: Cache is fresh!
            if response.status_code == 304 and cached_payload is not None:
                return cached_payload

            # 2. Handle HTTP 401 Unauthorized: Retry unauthenticated for public repos
            if response.status_code == 401 and 'Authorization' in headers:
                unauth_headers = {'Accept': 'application/vnd.github.v3+json'}
                if cached_etag:
                    unauth_headers['If-None-Match'] = cached_etag
                response = requests.get(url, headers=unauth_headers)
                if response.status_code == 304 and cached_payload is not None:
                    return cached_payload

            # 3. Handle HTTP 200 OK: Data fetched / updated
            if response.status_code == 200:
                data = response.json()
                new_etag = response.headers.get("ETag")
                self.cache.set(self.CACHE_NAMESPACE, url, data, etag=new_etag)
                return data

            # 4. Handle HTTP 4xx/5xx Errors: Fallback to cache
            if response.status_code in (429, 500, 502, 503, 504) and cached_payload is not None:
                logger.warning(f"GitHub HTTP {response.status_code} for {url}. Serving cached fallback.")
                return cached_payload

            logger.error(f"GitHub HTTP {response.status_code} for {url}")
            return None

        except requests.RequestException as e:
            if cached_payload is not None:
                logger.warning(f"Request error for {url}: {e}. Serving cached fallback.")
                return cached_payload
            logger.error(f"Request error for {url}: {e}")
            return None

    def get_repo_data(self, username: str, repo_name: str) -> Optional[Dict[str, Any]]:
        """Fetches repository metadata, tech stack languages, and README content."""
        repo_url = f'https://api.github.com/repos/{username}/{repo_name}'
        data = self._get_url(repo_url)

        if not data:
            logger.error(f"Failed to fetch {repo_name} from GitHub")
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
        if readme_data and isinstance(readme_data, dict) and 'content' in readme_data:
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
