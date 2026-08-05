import csv
import zipfile
import tempfile
import uuid
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from arb.models.domain import SourceResult, SourceStatus, EvidenceItem, SourceRef, ExperienceItem, EducationItem, Project, Fact
from arb.adapters.base import BaseAdapter

class LinkedInAdapter(BaseAdapter):
    """
    Adapter for processing LinkedIn Data Exports (ZIP or folder).
    Maps CSV columns directly to Canonical objects via EvidenceItem payloads.
    Bypasses the LLM entirely due to strict tabular structure.
    """
    def __init__(self):
        pass

    def ingest(self, identifier: str) -> SourceResult:
        """
        Identifier is the path to the LinkedIn ZIP file or extracted directory.
        """
        path = Path(identifier)
        if not path.exists():
            return SourceResult(
                source_type="linkedin",
                source_id="linkedin:export",
                status=SourceStatus.FAILED,
                metadata={"error": f"Path not found: {identifier}"}
            )

        evidence_items = []
        warnings = []

        if path.is_file() and path.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory() as temp_dir:
                try:
                    with zipfile.ZipFile(path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    items, w = self._process_directory(Path(temp_dir))
                    evidence_items.extend(items)
                    warnings.extend(w)
                except zipfile.BadZipFile:
                    return SourceResult(
                        source_type="linkedin",
                        source_id="linkedin:export",
                        status=SourceStatus.FAILED,
                        metadata={"error": f"Invalid ZIP file: {identifier}"}
                    )
        elif path.is_dir():
            items, w = self._process_directory(path)
            evidence_items.extend(items)
            warnings.extend(w)
        else:
            return SourceResult(
                source_type="linkedin",
                source_id="linkedin:export",
                status=SourceStatus.FAILED,
                metadata={"error": f"Path is neither a directory nor a ZIP: {identifier}"}
            )

        # source_id can be based on the file modified time or simply a static ID since we rely on SourceManager's last_synced
        # Actually, using a hash of the file could enable differential syncing.
        # But for now, we'll just use a static ID or one based on file modification time.
        stat = path.stat()
        source_id = f"linkedin:{stat.st_size}_{stat.st_mtime}"

        return SourceResult(
            source_type="linkedin",
            source_id=source_id,
            evidence=evidence_items,
            status=SourceStatus.SUCCESS,
            metadata={"warnings": warnings, "name": path.name, "adapter_version": "v1"}
        )

    def _process_directory(self, dir_path: Path) -> tuple[List[EvidenceItem], List[str]]:
        evidence = []
        warnings = []
        
        # Files to process
        csv_handlers = {
            "Positions.csv": self._parse_positions,
            "Education.csv": self._parse_education,
            "Projects.csv": self._parse_projects,
            "Skills.csv": self._parse_skills
        }
        
        # Check files
        found_files = [f.name for f in dir_path.glob("*.csv")]
        
        for file_name, handler in csv_handlers.items():
            file_path = dir_path / file_name
            if file_path.exists():
                try:
                    items = handler(file_path)
                    evidence.extend(items)
                except Exception as e:
                    warnings.append(f"Failed to parse {file_name}: {e}")
            else:
                warnings.append(f"Missing expected file: {file_name}")
                
        # Optional files we don't handle yet but might exist
        unsupported = set(found_files) - set(csv_handlers.keys())
        if unsupported:
            warnings.append(f"Ignored unsupported CSV files: {', '.join(unsupported)}")
            
        return evidence, warnings

    def _safe_read_csv(self, file_path: Path) -> List[Dict[str, str]]:
        # LinkedIn CSVs sometimes contain BOMs or weird encodings.
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                return list(reader)

    def _parse_positions(self, file_path: Path) -> List[EvidenceItem]:
        items = []
        rows = self._safe_read_csv(file_path)
        for row in rows:
            company = row.get("Company Name", "").strip()
            title = row.get("Title", "").strip()
            if not company and not title:
                continue
                
            start = row.get("Started On", "").strip()
            end = row.get("Finished On", "").strip()
            desc = row.get("Description", "").strip()
            loc = row.get("Location", "").strip()
            
            # Create a simple fact from the description
            facts = []
            if desc:
                # Split description by newlines to create bullets
                for line in desc.split("\n"):
                    line = line.strip()
                    if line and line not in ["-", "*", "•"]:
                        # Strip leading bullets if present
                        if line.startswith("- ") or line.startswith("* ") or line.startswith("• "):
                            line = line[2:].strip()
                        facts.append({
                            "id": f"fact_{uuid.uuid4().hex[:8]}",
                            "text": line,
                            "fact_type": "general",
                            "source_refs": [{"type": "linkedin", "id": "linkedin:export"}]
                        })
            
            data = {
                "id": f"{company}_{title}".replace(" ", "_").lower(),
                "organization": company,
                "title": title,
                "location": loc,
                "start_date": start,
                "end_date": end,
                "facts": facts
            }
            items.append(EvidenceItem(
                id=f"linkedin_exp_{uuid.uuid4().hex[:8]}",
                kind="experience",
                content=data,
                provenance=SourceRef(type="linkedin", id="linkedin:export")
            ))
        return items

    def _parse_education(self, file_path: Path) -> List[EvidenceItem]:
        items = []
        rows = self._safe_read_csv(file_path)
        for row in rows:
            school = row.get("School Name", "").strip()
            degree = row.get("Degree Name", "").strip()
            if not school:
                continue
                
            start = row.get("Started On", "").strip()
            end = row.get("Finished On", "").strip()
            
            data = {
                "id": f"{school}_{degree}".replace(" ", "_").lower(),
                "institution": school,
                "degree": degree,
                "start_date": start,
                "end_date": end
            }
            items.append(EvidenceItem(
                id=f"linkedin_edu_{uuid.uuid4().hex[:8]}",
                kind="education",
                content=data,
                provenance=SourceRef(type="linkedin", id="linkedin:export")
            ))
        return items

    def _parse_projects(self, file_path: Path) -> List[EvidenceItem]:
        items = []
        rows = self._safe_read_csv(file_path)
        for row in rows:
            title = row.get("Title", "").strip()
            if not title:
                continue
                
            desc = row.get("Description", "").strip()
            url = row.get("Url", "").strip()
            
            facts = []
            if desc:
                facts.append({
                    "id": f"fact_{uuid.uuid4().hex[:8]}",
                    "text": desc,
                    "fact_type": "general",
                    "source_refs": [{"type": "linkedin", "id": "linkedin:export"}]
                })
                
            data = {
                "id": title.replace(" ", "_").lower(),
                "name": title,
                "link": url,
                "facts": facts,
                "tech_stack": []
            }
            items.append(EvidenceItem(
                id=f"linkedin_proj_{uuid.uuid4().hex[:8]}",
                kind="projects",
                content=data,
                provenance=SourceRef(type="linkedin", id="linkedin:export")
            ))
        return items

    def _parse_skills(self, file_path: Path) -> List[EvidenceItem]:
        items = []
        rows = self._safe_read_csv(file_path)
        skills = []
        for row in rows:
            name = row.get("Name", "").strip()
            if name:
                skills.append(name)
                
        if skills:
            items.append(EvidenceItem(
                id=f"linkedin_skills_{uuid.uuid4().hex[:8]}",
                kind="skills",
                content={"General": skills},
                provenance=SourceRef(type="linkedin", id="linkedin:export")
            ))
        return items
