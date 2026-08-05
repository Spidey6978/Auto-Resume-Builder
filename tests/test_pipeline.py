from unittest.mock import MagicMock
from arb.core.pipeline import BuildPipeline
from arb.models.domain import CanonicalProfile, Project, Fact, TargetContext
from arb.models.presentation import ResumeDocument

def test_pipeline_build_resume():
    # 1. Mock dependencies
    mock_profile_manager = MagicMock()
    mock_profile_manager.profile = CanonicalProfile(
        projects=[Project(id="p1", name="Project 1", facts=[Fact(id="f1", text="text", fact_type="general", source_refs=[])])]
    )
    
    mock_generator = MagicMock()
    mock_generator_result = MagicMock()
    mock_generator_result.status = "success"
    from arb.models.presentation import RenderedBullet
    mock_generator_result.bullets = [RenderedBullet(text="Bullet 1"), RenderedBullet(text="Bullet 2")]
    mock_generator.generate_project_bullets.return_value = mock_generator_result

    mock_compiler = MagicMock()
    from arb.core.compilers.engines import CompilationResult
    mock_compiler.compile_resume.return_value = CompilationResult(pdf_path="/build/resume.pdf", page_count=1, success=True)
    
    mock_target_engine = MagicMock()
    from arb.models.plan import ResumePlan, PlannedProject, PlannedFact
    mock_target_engine.create_plan.return_value = ResumePlan(
        target=TargetContext(id="test", description="desc"),
        projects=[
            PlannedProject(project_id="p1", selected_facts=[PlannedFact(fact_id="f1", targeting_status="success")])
        ]
    )

    pipeline = BuildPipeline(
        profile_manager=mock_profile_manager,
        adapter_registry=MagicMock(),
        extractor=MagicMock(),
        generator=mock_generator,
        compiler=mock_compiler,
        target_engine=mock_target_engine
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
    assert document.projects[0].bullets[0].text == "Bullet 1"
    assert document.projects[0].bullets[1].text == "Bullet 2"
