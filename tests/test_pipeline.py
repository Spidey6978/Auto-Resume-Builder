from unittest.mock import MagicMock
from core.pipeline import BuildPipeline
from models.domain import CanonicalProfile, Project, Fact, TargetContext
from models.presentation import ResumeDocument

def test_pipeline_build_resume():
    # 1. Mock dependencies
    mock_profile_manager = MagicMock()
    mock_profile_manager.profile = CanonicalProfile(
        projects=[Project(id="p1", name="Project 1", facts=[Fact(id="f1", text="text", fact_type="general", source_refs=[])])]
    )
    
    mock_generator = MagicMock()
    mock_generator_result = MagicMock()
    mock_generator_result.status = "success"
    mock_generator_result.bullets = ["Bullet 1", "Bullet 2"]
    mock_generator.generate_project_bullets.return_value = mock_generator_result
    
    mock_compiler = MagicMock()
    mock_compiler.compile_resume.return_value = "/build/resume.pdf"
    
    pipeline = BuildPipeline(
        profile_manager=mock_profile_manager,
        github_adapter=MagicMock(),
        extractor=MagicMock(),
        generator=mock_generator,
        compiler=mock_compiler
    )
    
    target = TargetContext(id="test", description="desc")
    result = pipeline.build_resume(target=target)
    
    # 3. Assertions
    assert result.success is True
    assert result.pdf_path == "/build/resume.pdf"
    
    # Verify generator was called with the project
    mock_generator.generate_project_bullets.assert_called_once()
    
    # Verify compiler was called with ResumeDocument
    mock_compiler.compile_resume.assert_called_once()
    call_args = mock_compiler.compile_resume.call_args[0]
    document = call_args[0]
    
    assert isinstance(document, ResumeDocument)
    assert len(document.projects) == 1
    assert document.projects[0].bullets == ["Bullet 1", "Bullet 2"]
