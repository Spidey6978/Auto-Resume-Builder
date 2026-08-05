import os
import logging
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader
from arb.core.sanitizer import escape_latex, sanitize_data
from arb.core.compilers.engines import CompilationResult, LatexEngine, LuaLaTeXEngine

logger = logging.getLogger(__name__)


class ResumeCompiler:
    """
    Renders Jinja2 LaTeX templates and compiles them into final PDF documents.
    """

    def __init__(self, templates_dir: str, engine: LatexEngine = None):
        self.templates_dir = templates_dir
        self.engine = engine or LuaLaTeXEngine()
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            block_start_string="\\BLOCK{",
            block_end_string="}",
            variable_start_string="\\VAR{",
            variable_end_string="}",
        )
        self.env.filters["escape_latex"] = escape_latex

    def render(self, template_name: str, raw_data: dict) -> str:
        """Sanitizes input data and renders the specified Jinja2 template into LaTeX text."""
        safe_data = sanitize_data(raw_data)
        template = self.env.get_template(template_name)
        return template.render(safe_data)

    def compile_pdf(self, tex_path: str) -> CompilationResult:
        """
        Compiles a .tex file into a PDF using the configured LatexEngine.
        """
        return self.engine.compile(tex_path)

    def compile_resume(self, document: 'ResumeDocument', output_dir: str) -> CompilationResult:
        """
        Takes a highly structured ResumeDocument, renders it into LaTeX, 
        saves it into the specified output_dir, and compiles it into a PDF.
        """
        import dataclasses
        # Convert document dataclass back to dictionary for Jinja2
        doc_dict = dataclasses.asdict(document)
        
        rendered_tex = self.render("resume_template.tex", doc_dict)
        
        os.makedirs(output_dir, exist_ok=True)
        tex_output_path = os.path.join(output_dir, "resume.tex")
        
        with open(tex_output_path, "w", encoding="utf-8") as f:
            f.write(rendered_tex)
            
        logger.info(f"LaTeX file generated at: {tex_output_path}")
        return self.compile_pdf(tex_output_path)
