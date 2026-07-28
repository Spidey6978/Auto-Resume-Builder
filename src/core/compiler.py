import os
import subprocess
from jinja2 import Environment, FileSystemLoader
from core.sanitizer import escape_latex, sanitize_data


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

    def compile_pdf(self, tex_path: str) -> bool:
        """
        Compiles a .tex file into a PDF using LuaLaTeX.
        Returns True if successful, False otherwise.
        """
        if os.getenv("GITHUB_ACTIONS") == "true":
            print("  [CI/CD] Running in GitHub Actions. Skipping local LuaLaTeX compilation.")
            return True

        output_dir = os.path.dirname(tex_path)
        print("  Compiling LaTeX to PDF...")
        try:
            result = subprocess.run(
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
            print("  [OK] PDF compilation successful.")
            return True

        except FileNotFoundError:
            print("  [!] Error: 'lualatex' compiler not found in system PATH. Check LaTeX installation.")
            return False
        except subprocess.CalledProcessError as e:
            print("  [!] Error: LuaLaTeX compilation failed. Check log file in build folder.")
            return False
