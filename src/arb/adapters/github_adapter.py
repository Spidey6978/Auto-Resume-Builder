import requests
import base64
import logging
import yaml
from typing import List, Dict, Optional, Any
from arb.adapters.base import BaseAdapter
from arb.core.cache import CacheManager
from arb.core.paths import get_bundled_data_dir
from arb.models.domain import SourceResult, EvidenceItem, SourceRef, SourceStatus
from arb.adapters.github_manifests import MANIFEST_PARSERS

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
            
        self.tech_mappings = self._load_tech_mappings()

    def _load_tech_mappings(self) -> dict:
        mapping_path = get_bundled_data_dir() / "data" / "knowledge" / "tech_mappings.yaml"
        if mapping_path.exists():
            try:
                with open(mapping_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load tech_mappings.yaml: {e}")
        return {}

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

        # Determine stats
        default_branch = data.get("default_branch", "main")
        stars = data.get("stargazers_count", 0)
        forks = data.get("forks_count", 0)
        topics = data.get("topics", [])
        license_info = data.get("license", {}).get("name", "None") if data.get("license") else "None"
        archived = data.get("archived", False)

        # Fetch language breakdown
        langs_url = data.get('languages_url', '')
        tech_stack = []
        langs_data = {}
        if langs_url:
            langs_data = self._get_url(langs_url)
            if langs_data and isinstance(langs_data, dict):
                tech_stack = list(langs_data.keys())

        # Trees API for Manifests
        trees_url = f'https://api.github.com/repos/{username}/{repo_name}/git/trees/{default_branch}'
        trees_data = self._get_url(trees_url)
        found_manifests = []
        if trees_data and "tree" in trees_data:
            for item in trees_data["tree"]:
                if item["type"] == "blob" and item["path"] in MANIFEST_PARSERS:
                    found_manifests.append(item["path"])

        raw_deps = []
        for manifest in found_manifests:
            content_url = f'https://raw.githubusercontent.com/{username}/{repo_name}/{default_branch}/{manifest}'
            # Raw contents API requires Accept header change or using raw.githubusercontent.com
            # We use _get_url which handles caching. For raw content, we'd better bypass the JSON parse in _get_url,
            # but since _get_url expects JSON, let's do a direct request for simplicity or use github API.
            # Using contents API is safer for json response.
            manifest_url = f'https://api.github.com/repos/{username}/{repo_name}/contents/{manifest}?ref={default_branch}'
            manifest_data = self._get_url(manifest_url)
            if manifest_data and "content" in manifest_data:
                try:
                    content = base64.b64decode(manifest_data["content"]).decode("utf-8")
                    parser = MANIFEST_PARSERS[manifest]()
                    deps = parser.parse(content)
                    raw_deps.extend(deps)
                except Exception as e:
                    logger.warning(f"Failed to parse manifest {manifest}: {e}")
                    
        # Map dependencies to frameworks
        frameworks = set()
        for dep in raw_deps:
            if dep in self.tech_mappings:
                rule = self.tech_mappings[dep]
                if rule.get("ignore"):
                    continue
                if rule.get("canonical"):
                    frameworks.add(rule["canonical"])
        
        frameworks_list = sorted(list(frameworks))

        # Fetch README
        readme_url = f'https://api.github.com/repos/{username}/{repo_name}/readme'
        readme_data = self._get_url(readme_url)
        readme_content = ""
        if readme_data and isinstance(readme_data, dict) and 'content' in readme_data:
            try:
                readme_content = base64.b64decode(readme_data['content']).decode('utf-8', errors='ignore')
            except Exception:
                readme_content = ""

        # Inject Technical Context
        context_lines = ["=== TECHNICAL CONTEXT ==="]
        if tech_stack:
            context_lines.append("Languages:")
            for lang in tech_stack:
                context_lines.append(f"- {lang}")
        if frameworks_list:
            context_lines.append("Frameworks:")
            for fw in frameworks_list:
                context_lines.append(f"- {fw}")
        context_lines.append("Repository Statistics:")
        context_lines.append(f"- Stars: {stars}")
        context_lines.append(f"- Forks: {forks}")
        if topics:
            context_lines.append(f"- Topics: {', '.join(topics)}")
        context_lines.append(f"- License: {license_info}")
        if archived:
            context_lines.append(f"- Archived: True")
        context_lines.append("=== README ===")
        context_lines.append(readme_content)
        
        enriched_readme = "\n".join(context_lines)

        clean_name = data['name'].replace('-', ' ').replace('_', ' ').title()

        return {
            "name": clean_name,
            "raw_name": data['name'],
            "tech_stack": ", ".join(tech_stack) if tech_stack else "Various",
            "frameworks": frameworks_list,
            "languages": langs_data if (langs_url and langs_data and isinstance(langs_data, dict)) else {},
            "link": data.get('html_url', f"https://github.com/{username}/{repo_name}"),
            "readme_content": enriched_readme,
            "description": data.get('description', "No description provided.")
        }

    def ingest(self, identifier: str, **kwargs) -> SourceResult:
        """
        BaseAdapter ingest contract implementation.
        identifier expects a string like 'username/repo_name'
        """
        parts = identifier.split("/")
        if len(parts) != 2:
            return SourceResult(
                source_type="github",
                source_id=identifier,
                evidence=[],
                status=SourceStatus.FAILED,
                metadata={"error": "Invalid identifier format. Expected 'username/repo_name'"}
            )
        
        username, repo_name = parts
        repo_data = self.get_repo_data(username, repo_name)
        
        if not repo_data:
            return SourceResult(
                source_type="github",
                source_id=identifier,
                evidence=[],
                status=SourceStatus.FAILED,
                metadata={"error": f"Failed to fetch {identifier}"}
            )

        provenance = SourceRef(type="github", id=identifier)
        evidence = []

        # 1. README Evidence
        if repo_data.get("readme_content"):
            evidence.append(
                EvidenceItem(
                    id=f"{identifier}-readme",
                    kind="readme",
                    content=repo_data["readme_content"],
                    provenance=provenance
                )
            )
        
        meta_content = {
            "name": repo_data["name"],
            "description": repo_data["description"],
            "tech_stack": repo_data["tech_stack"],
            "frameworks": repo_data.get("frameworks", []),
            "languages": repo_data["languages"],
            "link": repo_data["link"],
            "adapter_version": "v2"
        }
        evidence.append(
            EvidenceItem(
                id=f"{identifier}-metadata",
                kind="repo_metadata",
                content=meta_content,
                provenance=provenance
            )
        )

        return SourceResult(
            source_type="github",
            source_id=identifier,
            evidence=evidence,
            metadata=meta_content,
            status=SourceStatus.SUCCESS
        )
