import json
import re
from typing import List, Dict, Type

class ManifestParser:
    def parse(self, content: str) -> List[str]:
        """Returns a list of raw dependencies found in the manifest."""
        return []

class PackageJsonParser(ManifestParser):
    def parse(self, content: str) -> List[str]:
        try:
            data = json.loads(content)
            deps = list(data.get("dependencies", {}).keys())
            deps.extend(list(data.get("devDependencies", {}).keys()))
            return deps
        except Exception:
            return []

class RequirementsTxtParser(ManifestParser):
    def parse(self, content: str) -> List[str]:
        deps = []
        for line in content.splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            # Extract package name before ==, >=, etc
            match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
            if match:
                deps.append(match.group(1).lower())
        return deps

class PyProjectTomlParser(ManifestParser):
    def parse(self, content: str) -> List[str]:
        # Very basic regex to avoid a heavy TOML dependency
        # We just grab quoted words inside arrays or standard keys and let tech_mappings filter the noise
        deps = []
        matches = re.findall(r'[\'"]([a-zA-Z0-9_\-]+)[\'"]', content)
        for m in matches:
            deps.append(m.lower())
        return deps

class GoModParser(ManifestParser):
    def parse(self, content: str) -> List[str]:
        deps = []
        in_require = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("require ("):
                in_require = True
            elif line.startswith(")") and in_require:
                in_require = False
            elif in_require and line:
                parts = line.split()
                if len(parts) >= 1:
                    deps.append(parts[0].split("/")[-1].lower())
            elif line.startswith("require "):
                parts = line.split()
                if len(parts) >= 2:
                    deps.append(parts[1].split("/")[-1].lower())
        return deps

class CargoTomlParser(ManifestParser):
    def parse(self, content: str) -> List[str]:
        deps = []
        in_deps = False
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("[dependencies]") or line.startswith("[dev-dependencies]"):
                in_deps = True
            elif line.startswith("["):
                in_deps = False
            elif in_deps and "=" in line:
                pkg_name = line.split("=")[0].strip()
                deps.append(pkg_name.lower())
        return deps

MANIFEST_PARSERS: Dict[str, Type[ManifestParser]] = {
    "package.json": PackageJsonParser,
    "requirements.txt": RequirementsTxtParser,
    "pyproject.toml": PyProjectTomlParser,
    "go.mod": GoModParser,
    "Cargo.toml": CargoTomlParser
}
