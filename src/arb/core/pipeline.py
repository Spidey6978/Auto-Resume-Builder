import os
import uuid
import logging
from typing import Optional
from dataclasses import dataclass

from arb.core.profile_manager import ProfileManager
from arb.core.fact_extractor import FactExtractor
from arb.core.generator import ContentGenerator
from arb.core.compiler import ResumeCompiler
import hashlib
import json
from arb.adapters.registry import AdapterRegistry
from arb.core.normalizer import normalize_languages
from arb.models.presentation import ResumeDocument, RenderedProject, RenderedExperience, RenderedAward
from arb.core.target_engine import TargetEngine
from arb.models.domain import TargetContext
from arb.core.domain_loader import DomainLoader
import datetime
from arb.core.document_segmenter import DocumentSegmenter
from arb.core.evidence_extractor import EvidenceExtractor
from arb.core.profile_merger import ProfileMerger
from arb.core.source_manager import SourceManager
from arb.models.domain import SourceRecord, SourceRef, EvidenceItem

logger = logging.getLogger(__name__)

@dataclass
class SyncResult:
    success: bool
    message: str

@dataclass
class BuildResult:
    success: bool
    pdf_path: Optional[str]
    message: str

class BuildPipeline:
    """
    Orchestrates the resume generation process.
    Uses Dependency Injection for all sub-components to enable isolated testing.
    """
    
    def __init__(
        self,
        profile_manager: ProfileManager,
        adapter_registry: AdapterRegistry,
        extractor: FactExtractor,
        generator: ContentGenerator,
        compiler: ResumeCompiler,
        target_engine: TargetEngine,
        domain_loader: DomainLoader = None,
        document_segmenter: DocumentSegmenter = None,
        evidence_extractor: EvidenceExtractor = None,
        source_manager: SourceManager = None
    ):
        self.profile_manager = profile_manager
        self.adapter_registry = adapter_registry
        self.extractor = extractor
        self.generator = generator
        self.compiler = compiler
        self.target_engine = target_engine
        self.domain_loader = domain_loader
        self.document_segmenter = document_segmenter
        self.evidence_extractor = evidence_extractor
        self.source_manager = source_manager

    def sync_source(self, source_type: str, identifier: str, mock_ai: bool = False) -> SyncResult:
        """
        INGEST -> SEGMENT (if doc) -> EXTRACT -> NORMALIZE -> MERGE -> SAVE
        """
        try:
            adapter = self.adapter_registry.get_adapter(source_type)
            if not adapter:
                return SyncResult(False, f"No adapter registered for source type '{source_type}'")

            source_result = adapter.ingest(identifier=identifier)
            if source_result.status != "success":
                if self.source_manager:
                    record = SourceRecord(
                        id=source_result.source_id or f"{source_type}:{identifier}",
                        type=source_type,
                        identifier=identifier,
                        display_name=identifier,
                        added_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        last_synced=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        status="failed",
                        adapter_version=source_result.metadata.get("adapter_version"),
                        metadata={"error": source_result.metadata.get("error")}
                    )
                    self.source_manager.upsert_source(record)
                    self.source_manager.save()
                return SyncResult(False, source_result.metadata.get("error", f"Failed to ingest {identifier}"))
                
            # Compute evidence hash once so it is available for both skip checks and persistence.
            evidence_json = json.dumps([e.to_dict() for e in source_result.evidence], sort_keys=True)
            new_hash = hashlib.sha256(evidence_json.encode('utf-8')).hexdigest()

            # Check skip logic via SourceManager
            if self.source_manager:
                existing = self.source_manager.get_source(source_result.source_id)
                should_skip = False
                
                if existing and existing.status == "success":
                    old_hash = existing.last_ingested_hash
                    if old_hash and new_hash == old_hash:
                        should_skip = True
                            
                if should_skip:
                    existing.last_synced = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    self.source_manager.upsert_source(existing)
                    self.source_manager.save()
                    return SyncResult(True, f"Skipped {identifier}. No changes detected.")
                
            merger = ProfileMerger(self.profile_manager.profile)
                
            if source_type == "document":
                if not self.document_segmenter or not self.evidence_extractor:
                    return SyncResult(False, "Document ingestion dependencies not configured.")
                    
                segmented_evidence = self.document_segmenter.segment(source_result.evidence)
                for ev in segmented_evidence:
                    extraction = self.evidence_extractor.extract(ev, mock_ai=mock_ai)
                    merger.merge(extraction)
                    
            elif source_type == "github":
                if not self.evidence_extractor:
                    return SyncResult(False, "GitHub ingestion dependencies not configured.")

                languages_dict = source_result.metadata.get("languages", {})
                normalized_stack = normalize_languages(languages_dict)
                frameworks = source_result.metadata.get("frameworks", [])
                combined_stack = list(dict.fromkeys(normalized_stack + frameworks))

                raw_name = source_result.metadata.get("name", source_result.source_id.split("/")[-1])
                link = source_result.metadata.get("link")

                repo_evidence = EvidenceItem(
                    id=f"{source_result.source_id}-metadata",
                    kind="projects",
                    content={
                        "id": source_result.source_id,
                        "name": raw_name,
                        "link": link,
                        "tech_stack": combined_stack,
                        "facts": [],
                    },
                    provenance=SourceRef(type="github", id=source_result.source_id)
                )

                extraction = self.evidence_extractor.extract(repo_evidence, mock_ai=mock_ai)
                merger.merge(extraction)

            elif source_type in ("manual", "linkedin"):
                if not self.evidence_extractor:
                    return SyncResult(False, f"{source_type.title()} ingestion dependencies not configured.")
                for ev in source_result.evidence:
                    extraction = self.evidence_extractor.extract(ev, mock_ai=mock_ai)
                    merger.merge(extraction)

            # Save Atomic
            self.profile_manager.save()
            
            # Record Success
            if self.source_manager:
                existing = self.source_manager.get_source(source_result.source_id)
                added_at = existing.added_at if existing else datetime.datetime.now(datetime.timezone.utc).isoformat()
                
                display_name = identifier
                if source_type == "github":
                    display_name = source_result.metadata.get("name", identifier)
                elif source_type == "document":
                    display_name = os.path.basename(identifier)
                    
                record = SourceRecord(
                    id=source_result.source_id,
                    type=source_type,
                    identifier=identifier,
                    display_name=display_name,
                    added_at=added_at,
                    last_synced=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    status="success",
                    adapter_version=source_result.metadata.get("adapter_version"),
                    last_ingested_hash=new_hash,
                    metadata=source_result.metadata
                )
                self.source_manager.upsert_source(record)
                self.source_manager.save()
            
            return SyncResult(True, f"Successfully synced {identifier}")
            
        except Exception as e:
            return SyncResult(False, f"Sync failed: {e}")

    def create_document(self, target: TargetContext, mock_ai: bool = False) -> ResumeDocument:
        """
        LOAD canonical profile -> CREATE plan -> GENERATE bullets -> construct Document
        """
        raw_profile = self.profile_manager.profile
        
        # Apply targeting rules and AI fact scoring to create a plan
        plan = self.target_engine.create_plan(raw_profile, target, mock_ai=mock_ai)
        
        allowed_entities = plan.allowed_entities
        
        rendered_projects = []
        for proj in plan.projects:
            if not self.generator:
                break
            res = self.generator.generate_project_bullets(raw_profile, proj, target, mock_ai=mock_ai)
            if res.status == "success":
                canonical_proj = next((p for p in raw_profile.projects if p.id == proj.project_id), None)
                if canonical_proj:
                    rp = RenderedProject(
                        id=proj.project_id,
                        name=canonical_proj.name,
                        tech_stack=canonical_proj.tech_stack,
                        link=canonical_proj.link,
                        bullets=res.bullets
                    )
                    rendered_projects.append(rp)
                    
        rendered_experience = []
        if "experience" in allowed_entities:
            for exp in plan.experience:
                if not self.generator:
                    # Fallback to no bullets if generator missing
                    canonical_exp = next((e for e in raw_profile.experience if e.id == exp.experience_id), None)
                    if canonical_exp:
                        re_obj = RenderedExperience(
                            id=exp.experience_id,
                            organization=canonical_exp.organization,
                            title=canonical_exp.title,
                            location=canonical_exp.location,
                            start_date=canonical_exp.start_date,
                            end_date=canonical_exp.end_date,
                            bullets=[]
                        )
                        rendered_experience.append(re_obj)
                    continue
                    
                res = self.generator.generate_experience_bullets(raw_profile, exp, target, mock_ai=mock_ai)
                if res.status == "success":
                    canonical_exp = next((e for e in raw_profile.experience if e.id == exp.experience_id), None)
                    if canonical_exp:
                        re_obj = RenderedExperience(
                            id=exp.experience_id,
                            organization=canonical_exp.organization,
                            title=canonical_exp.title,
                            location=canonical_exp.location,
                            start_date=canonical_exp.start_date,
                            end_date=canonical_exp.end_date,
                            bullets=res.bullets
                        )
                        rendered_experience.append(re_obj)
        
        rendered_awards = []
        if "awards" in allowed_entities:
            for awd in raw_profile.awards:
                rendered_awards.append(RenderedAward(
                    id=awd.id,
                    title=awd.title,
                    event=awd.event,
                    organization=awd.organization,
                    year=awd.year,
                    bullets=[]
                ))
            
        # Retrieve section_order from policies, or use a default
        resolved_order_policy = plan.policies.policies.get("page_policy") if plan.policies else None
        section_order_dict = plan.policies.policies.get("section_order") if plan.policies else None
        section_order = section_order_dict.get("order") if (section_order_dict and "order" in section_order_dict) else ["summary", "education", "experience", "projects", "awards", "technical_skills"]
        page_policy = resolved_order_policy or {"pages": 1}

        return ResumeDocument(
            personal=raw_profile.personal if "personal" in allowed_entities else None,
            education=raw_profile.education if "education" in allowed_entities else [],
            experience=rendered_experience,
            awards=rendered_awards,
            projects=rendered_projects, # Already filtered by target_engine
            skills=raw_profile.skills if "skills" in allowed_entities else {},
            section_order=section_order,
            page_policy=page_policy
        )

    def _trim_lowest_priority_bullet(self, document: ResumeDocument) -> bool:
        """
        Finds the RenderedBullet with the lowest relevance_score across all projects and experiences
        and removes it. Returns True if a bullet was removed, False if no bullets are left to remove.
        """
        lowest_score = float('inf')
        target_list = None
        target_index = -1
        
        # Check projects
        for proj in document.projects:
            for i, bullet in enumerate(proj.bullets):
                if bullet.relevance_score < lowest_score:
                    lowest_score = bullet.relevance_score
                    target_list = proj.bullets
                    target_index = i
                    
        # Check experiences (if they have bullets)
        for exp in document.experience:
            for i, bullet in enumerate(exp.bullets):
                if bullet.relevance_score < lowest_score:
                    lowest_score = bullet.relevance_score
                    target_list = exp.bullets
                    target_index = i
                    
        if target_list is not None and target_index != -1:
            removed = target_list.pop(target_index)
            logger.info(f"OverflowResolver: Removed bullet '{removed.text[:30]}...' with score {removed.relevance_score}")
            return True
            
        return False

    def build_resume(self, target: TargetContext, mock_ai: bool = False) -> BuildResult:
        """
        Builds the presentation document, sets up a unique workspace, and compiles the PDF.
        Implements an overflow resolution loop to enforce page limits.
        """
        try:
            document = self.create_document(target=target, mock_ai=mock_ai)
            
            build_id = uuid.uuid4().hex
            output_root = os.path.join(os.getcwd(), "build")
            output_dir = os.path.join(output_root, build_id)
            
            max_iterations = 5
            allowed_pages = document.page_policy.get("pages", 1) if document.page_policy else 1
            
            for iteration in range(max_iterations):
                logger.info(f"Build Pipeline: Compiling iteration {iteration + 1} (Target pages: {allowed_pages})")
                compilation_result = self.compiler.compile_resume(document, output_dir=output_dir)
                
                if not compilation_result.success:
                    return BuildResult(False, None, "LaTeX compilation failed.")
                    
                actual_pages = compilation_result.page_count
                if actual_pages <= allowed_pages:
                    logger.info(f"Build Pipeline: Document fits in {actual_pages} pages. Done.")
                    return BuildResult(True, compilation_result.pdf_path, "Resume compiled successfully")
                    
                logger.warning(f"Build Pipeline: Overflow detected ({actual_pages} > {allowed_pages} pages). Attempting to trim...")
                
                # Try to remove the lowest priority bullet
                trimmed = self._trim_lowest_priority_bullet(document)
                if not trimmed:
                    logger.warning("Build Pipeline: Could not find any bullets to trim. Stopping overflow resolution.")
                    break
                    
            return BuildResult(True, compilation_result.pdf_path, f"Compiled successfully, but may exceed {allowed_pages} pages after max trimming iterations.")
            
        except Exception as e:
            logger.error(f"Compilation failed: {e}", exc_info=True)
            return BuildResult(False, None, f"Compilation failed: {e}")
