import os
import uuid
import logging
from typing import Optional
from dataclasses import dataclass

from core.profile_manager import ProfileManager
from core.fact_extractor import FactExtractor
from core.generator import ContentGenerator
from core.compiler import ResumeCompiler
from adapters.github_adapter import GitHubAdapter
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
        github_adapter: GitHubAdapter,
        extractor: FactExtractor,
        generator: ContentGenerator,
        compiler: ResumeCompiler,
        target_engine: TargetEngine
    ):
        self.profile_manager = profile_manager
        self.github = github_adapter
        self.extractor = extractor
        self.generator = generator
        self.compiler = compiler
        self.target_engine = target_engine

    def sync_github_project(self, repo_url: str, mock_ai: bool = False) -> SyncResult:
        """
        INGEST -> EXTRACT -> NORMALIZE -> MERGE -> SAVE
        """
        try:
            # 1. Ingest
            source_result = self.github.fetch(repo_url)
            if source_result.status != "success":
                return SyncResult(False, f"Failed to fetch GitHub repo: {repo_url}")
                
            # 2. Extract Facts
            extraction_result = self.extractor.extract(source_result, entity_id=source_result.source_id, mock_ai=mock_ai)
            
            # 3. Normalize Languages
            languages_dict = source_result.metadata.get("languages", {})
            normalized_stack = normalize_languages(languages_dict)
            
            # 4. Merge into Profile
            raw_name = source_result.metadata.get("name", source_result.source_id.split("/")[-1])
            link = source_result.metadata.get("html_url")
            
            self.profile_manager.upsert_project(
                source_id=source_result.source_id,
                raw_name=raw_name,
                link=link,
                normalized_languages=normalized_stack,
                extraction_result=extraction_result
            )
            
            # 5. Save Atomic
            self.profile_manager.save()
            
            return SyncResult(True, f"Successfully synced {repo_url}")
            
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
            
        return ResumeDocument(
            personal=raw_profile.personal,
            education=raw_profile.education,
            experience=rendered_experience,
            awards=rendered_awards,
            projects=rendered_projects,
            skills=raw_profile.skills
        )

    def build_resume(self, target: TargetContext, mock_ai: bool = False) -> BuildResult:
        """
        Builds the presentation document, sets up a unique workspace, and compiles the PDF.
        """
        try:
            document = self.create_document(target=target, mock_ai=mock_ai)
            
            build_id = uuid.uuid4().hex
            output_dir = os.path.join(os.path.dirname(self.compiler.templates_dir), "build", build_id)
            
            pdf_path = self.compiler.compile_resume(document, output_dir=output_dir)
            return BuildResult(True, pdf_path, "Resume compiled successfully")
        except Exception as e:
            logger.error(f"Compilation failed: {e}")
            return BuildResult(False, None, f"Compilation failed: {e}")
