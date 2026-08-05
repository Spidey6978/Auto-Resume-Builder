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
        # Handle syntax like "fastapi>=0.100" or fastapi = "^0.68.0"
        deps = []
        # Match quoted strings in list arrays or dict keys
        matches = re.findall(r'[\'"]([a-zA-Z0-9_\-]+)(?:[>=<~^\[].*)?[\'"]', content)
        for m in matches:
            deps.append(m.lower())
            
        # Match unquoted keys before '=' only when they appear inside a dependency table.
        # This avoids falsely parsing section headers like [tool.poetry.dependencies] and
        # metadata keys such as name/version/description from the project table.
        dep_table_matches = re.finditer(r'^\s*\[(?:tool\.poetry\.dependencies|dependencies|dev-dependencies)\]\s*$', content, re.MULTILINE)
        for match in dep_table_matches:
            table_start = match.end()
            section_body = content[table_start:]
            for line in section_body.splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("["):
                    break
                if "=" not in stripped:
                    continue
                key = stripped.split("=", 1)[0].strip()
                if re.match(r'^[a-zA-Z0-9_\-]+$', key):
                    deps.append(key.lower())
            
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

class PomXmlParser(ManifestParser):
    def parse(self, content: str) -> List[str]:
        deps = []
        import xml.etree.ElementTree as ET
        try:
            # pom.xml uses namespaces, strip them for simple search
            content = re.sub(r'\sxmlns="[^"]+"', '', content, count=1)
            root = ET.fromstring(content)
            for dep in root.findall(".//dependency/artifactId"):
                if dep.text:
                    deps.append(dep.text.lower())
        except Exception:
            # Fallback regex
            matches = re.findall(r'<artifactId>([^<]+)</artifactId>', content)
            deps.extend([m.lower() for m in matches])
        return deps

MANIFEST_PARSERS: Dict[str, Type[ManifestParser]] = {
    "package.json": PackageJsonParser,
    "requirements.txt": RequirementsTxtParser,
    "pyproject.toml": PyProjectTomlParser,
    "go.mod": GoModParser,
    "Cargo.toml": CargoTomlParser,
    "pom.xml": PomXmlParser
}
