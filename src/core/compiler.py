import os
import subprocess
import logging
from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader
from core.sanitizer import escape_latex, sanitize_data

logger = logging.getLogger(__name__)

@dataclass
class CompilationResult:
    pdf_path: str
    page_count: int
    success: bool


class ResumeCompiler:
    """
    Renders Jinja2 LaTeX templates and compiles them into final PDF documents.
    """

    def __init__(self, templates_dir: str):
        self.templates_dir = templates_dir
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
        Compiles a .tex file into a PDF using LuaLaTeX.
        Returns CompilationResult with success status and page count.
        """
        output_dir = os.path.dirname(tex_path)
        pdf_path = tex_path.replace(".tex", ".pdf")
        log_path = tex_path.replace(".tex", ".log")
        
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("[CI/CD] Running in GitHub Actions. Skipping local LuaLaTeX compilation.")
            return CompilationResult(pdf_path=pdf_path, page_count=1, success=True)

        logger.info("Compiling LaTeX to PDF...")
        try:
            subprocess.run(
                [
                    "lualatex",
                    "-interaction=nonstopmode",
                    "-output-directory",
                    output_dir,
                    tex_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            logger.info("PDF compilation successful.")
            page_count = self._extract_page_count(log_path)
            return CompilationResult(pdf_path=pdf_path, page_count=page_count, success=True)

        except FileNotFoundError:
            logger.error("Error: 'lualatex' compiler not found in system PATH. Check LaTeX installation.")
            return CompilationResult(pdf_path=pdf_path, page_count=0, success=False)
        except subprocess.CalledProcessError as e:
            logger.error("Error: LuaLaTeX compilation failed. Check log file in build folder.")
            return CompilationResult(pdf_path=pdf_path, page_count=0, success=False)
            
    def _extract_page_count(self, log_path: str) -> int:
        if not os.path.exists(log_path):
            return 0
        try:
            import re
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "Output written on" in line and ".pdf" in line:
                        match = re.search(r"\((\d+) pages?,", line)
                        if match:
                            return int(match.group(1))
            return 0
        except Exception as e:
            logger.error(f"Failed to extract page count: {e}")
            return 0

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
