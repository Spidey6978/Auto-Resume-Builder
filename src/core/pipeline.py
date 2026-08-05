import os
import uuid
import logging
from typing import Optional
from dataclasses import dataclass

from core.profile_manager import ProfileManager
from core.fact_extractor import FactExtractor
from core.generator import ContentGenerator
from core.compiler import ResumeCompiler
from adapters.registry import AdapterRegistry
from core.normalizer import normalize_languages
from models.presentation import ResumeDocument, RenderedProject, RenderedExperience, RenderedAward
from core.target_engine import TargetEngine
from models.domain import TargetContext

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
        target_engine: TargetEngine
    ):
        self.profile_manager = profile_manager
        self.adapter_registry = adapter_registry
        self.extractor = extractor
        self.generator = generator
        self.compiler = compiler
        self.target_engine = target_engine

    def sync_project(self, source_type: str, identifier: str, mock_ai: bool = False) -> SyncResult:
        """
        INGEST -> EXTRACT -> NORMALIZE -> MERGE -> SAVE
        """
        try:
            # 1. Resolve Adapter
            adapter = self.adapter_registry.get_adapter(source_type)
            if not adapter:
                return SyncResult(False, f"No adapter registered for source type '{source_type}'")

            # 2. Ingest
            source_result = adapter.ingest(identifier=identifier)
            if source_result.status != "success":
                return SyncResult(False, source_result.metadata.get("error", f"Failed to ingest {identifier}"))
                
            # 2. Extract Facts
            extraction_result = self.extractor.extract(source_result, entity_id=source_result.source_id, mock_ai=mock_ai)
            
            # 3. Normalize Languages
            languages_dict = source_result.metadata.get("languages", {})
            normalized_stack = normalize_languages(languages_dict)
            
            # 4. Merge into Profile
            raw_name = source_result.metadata.get("name", source_result.source_id.split("/")[-1])
            link = source_result.metadata.get("link")
            
            self.profile_manager.upsert_project(
                source_id=source_result.source_id,
                raw_name=raw_name,
                link=link,
                normalized_languages=normalized_stack,
                extraction_result=extraction_result
            )
            
            # 5. Save Atomic
            self.profile_manager.save()
            
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

        
        rendered_projects = []
        for planned_proj in plan.projects:
            # find original project to get non-bullet info
            proj = next((p for p in raw_profile.projects if p.id == planned_proj.project_id), None)
            if not proj:
                continue
                
            gen_result = self.generator.generate_project_bullets(raw_profile, planned_proj, target=target, mock_ai=mock_ai)
            bullets = gen_result.bullets if gen_result.status == "success" else []
            if not bullets and gen_result.status != "success":
                logger.warning(f"Failed to generate bullets for '{proj.name}' ({gen_result.status}).")
                
            rendered_projects.append(RenderedProject(
                id=proj.id,
                name=proj.name,
                link=proj.link,
                tech_stack=proj.tech_stack,
                bullets=bullets
            ))
            
        # For experience and awards, if we later add fact extraction to them, we would generate bullets here.
        # Currently, the canonical profile doesn't have a direct field for old raw bullets. 
        # If human added bullets manually in legacy yaml, we can pass them through for now, or just leave them empty.
        rendered_experience = []
        for exp in raw_profile.experience:
            rendered_experience.append(RenderedExperience(
                id=exp.id,
                organization=exp.organization,
                title=exp.title,
                location=exp.location,
                start_date=exp.start_date,
                end_date=exp.end_date,
                bullets=[]  # To be implemented when we generate experience bullets
            ))
            
        rendered_awards = []
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
            personal=raw_profile.personal,
            education=raw_profile.education,
            experience=rendered_experience,
            awards=rendered_awards,
            projects=rendered_projects,
            skills=raw_profile.skills,
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
            output_dir = os.path.join(os.path.dirname(self.compiler.templates_dir), "build", build_id)
            
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
