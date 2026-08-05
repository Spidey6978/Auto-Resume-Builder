import json
import uuid
import datetime
from typing import Dict, Any, List

from arb.models.domain import SourceResult, SourceStatus, EvidenceItem, SourceRef
from arb.adapters.base import BaseAdapter

class ManualAdapter(BaseAdapter):
    """
    Adapter for manually entering career facts via interactive CLI prompts.
    Produces highly structured EvidenceItems tagged with 'manual' provenance.
    """

    def __init__(self):
        pass

    def ingest(self, identifier: str) -> SourceResult:
        """
        identifier is the entity type: 'experience', 'project', 'education', 'award', 'skill'
        """
        entity_type = identifier.lower()
        supported = ["experience", "project", "education", "award"]
        
        if entity_type not in supported:
            return SourceResult(
                source_type="manual",
                source_id="manual:cli",
                status=SourceStatus.FAILED,
                metadata={"error": f"Unsupported manual entity type '{entity_type}'. Must be one of: {', '.join(supported)}"}
            )
            
        print(f"\n--- Adding Manual {entity_type.capitalize()} ---")
        
        data = {}
        if entity_type == "experience":
            data = self._prompt_experience()
        elif entity_type == "project":
            data = self._prompt_project()
        elif entity_type == "education":
            data = self._prompt_education()
        elif entity_type == "award":
            data = self._prompt_award()
            
        if not data:
            return SourceResult(
                source_type="manual",
                source_id="manual:cli",
                status=SourceStatus.FAILED,
                metadata={"error": "User cancelled or provided empty data."}
            )
            
        # Create a unique ID for this manual entry
        entry_id = f"manual_{uuid.uuid4().hex[:8]}"
        
        evidence = EvidenceItem(
            id=entry_id,
            kind=entity_type,
            content=data,
            provenance=SourceRef(type="manual", id="manual:cli")
        )
        
        # We set source_id to a timestamp-based ID so the SourceManager knows it's a unique manual session
        # Or just use manual:cli. But if we use manual:cli, SourceManager will only track one record for all manual syncs.
        # Actually, it's fine. We can just update the `last_synced` of the `manual:cli` source record.
        return SourceResult(
            source_type="manual",
            source_id="manual:cli",
            evidence=[evidence],
            status=SourceStatus.SUCCESS,
            metadata={"entity_type": entity_type, "name": "Manual CLI Entry"}
        )

    def _prompt_experience(self) -> Dict[str, Any]:
        org = input("Organization/Company: ").strip()
        if not org: return {}
        
        title = input("Job Title: ").strip()
        if not title: return {}
        
        start_date = input("Start Date (e.g., 2020): ").strip()
        end_date = input("End Date (e.g., 2022, Present): ").strip()
        
        print("\nEnter facts/bullets for this experience (leave blank to finish):")
        facts = []
        while True:
            fact = input(" - ").strip()
            if not fact: break
            facts.append({
                "id": f"fact_{uuid.uuid4().hex[:8]}",
                "text": fact,
                "fact_type": "general",
                "source_refs": [{"type": "manual", "id": "manual:cli"}]
            })
            
        return {
            "organization": org,
            "title": title,
            "start_date": start_date,
            "end_date": end_date,
            "facts": facts
        }

    def _prompt_project(self) -> Dict[str, Any]:
        name = input("Project Name: ").strip()
        if not name: return {}
        
        link = input("Link (optional): ").strip()
        tech = input("Tech Stack (comma separated): ").strip()
        
        print("\nEnter facts/bullets for this project (leave blank to finish):")
        facts = []
        while True:
            fact = input(" - ").strip()
            if not fact: break
            facts.append({
                "id": f"fact_{uuid.uuid4().hex[:8]}",
                "text": fact,
                "fact_type": "general",
                "source_refs": [{"type": "manual", "id": "manual:cli"}]
            })
            
        return {
            "name": name,
            "link": link,
            "tech_stack": [t.strip() for t in tech.split(",")] if tech else [],
            "facts": facts
        }

    def _prompt_education(self) -> Dict[str, Any]:
        inst = input("Institution/School: ").strip()
        if not inst: return {}
        
        degree = input("Degree (e.g., B.S. Computer Science): ").strip()
        if not degree: return {}
        
        start_date = input("Start Date: ").strip()
        end_date = input("End Date: ").strip()
        
        return {
            "institution": inst,
            "degree": degree,
            "start_date": start_date,
            "end_date": end_date
        }

    def _prompt_award(self) -> Dict[str, Any]:
        title = input("Award Title: ").strip()
        if not title: return {}
        
        event = input("Event/Competition (optional): ").strip()
        org = input("Organization (optional): ").strip()
        year = input("Year (optional): ").strip()
        
        print("\nEnter facts/bullets for this award (leave blank to finish):")
        facts = []
        while True:
            fact = input(" - ").strip()
            if not fact: break
            facts.append({
                "id": f"fact_{uuid.uuid4().hex[:8]}",
                "text": fact,
                "fact_type": "general",
                "source_refs": [{"type": "manual", "id": "manual:cli"}]
            })
            
        return {
            "title": title,
            "event": event,
            "organization": org,
            "year": year,
            "facts": facts
        }
