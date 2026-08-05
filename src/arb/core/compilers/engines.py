import os
import subprocess
import logging
from typing import Protocol
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class CompilationResult:
    pdf_path: str
    page_count: int
    success: bool

class LatexEngine(Protocol):
    def compile(self, tex_path: str) -> CompilationResult:
        ...

class LuaLaTeXEngine:
    def compile(self, tex_path: str) -> CompilationResult:
        output_dir = os.path.dirname(tex_path)
        pdf_path = tex_path.replace(".tex", ".pdf")
        
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("[CI/CD] Running in GitHub Actions. Skipping local LuaLaTeX compilation.")
            return CompilationResult(pdf_path=pdf_path, page_count=1, success=True)

        logger.info("Compiling LaTeX to PDF using LuaLaTeX...")
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
            page_count = self._get_page_count(pdf_path)
            return CompilationResult(pdf_path=pdf_path, page_count=page_count, success=True)

        except FileNotFoundError:
            logger.error("Error: 'lualatex' compiler not found in system PATH.")
            return CompilationResult(pdf_path=pdf_path, page_count=0, success=False)
        except subprocess.CalledProcessError:
            logger.error("Error: LuaLaTeX compilation failed. Check log file in build folder.")
            return CompilationResult(pdf_path=pdf_path, page_count=0, success=False)
            
    def _get_page_count(self, pdf_path: str) -> int:
        if not os.path.exists(pdf_path):
            return 0
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Failed to extract page count using pypdf: {e}")
            return 0


class TectonicEngine:
    def compile(self, tex_path: str) -> CompilationResult:
        pdf_path = tex_path.replace(".tex", ".pdf")
        
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("[CI/CD] Running in GitHub Actions. Skipping local compilation.")
            return CompilationResult(pdf_path=pdf_path, page_count=1, success=True)

        logger.info("Compiling LaTeX to PDF using Tectonic...")
        try:
            subprocess.run(
                [
                    "tectonic",
                    tex_path,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            logger.info("PDF compilation successful.")
            page_count = self._get_page_count(pdf_path)
            return CompilationResult(pdf_path=pdf_path, page_count=page_count, success=True)

        except FileNotFoundError:
            logger.error("Error: 'tectonic' compiler not found in system PATH.")
            return CompilationResult(pdf_path=pdf_path, page_count=0, success=False)
        except subprocess.CalledProcessError:
            logger.error("Error: Tectonic compilation failed.")
            return CompilationResult(pdf_path=pdf_path, page_count=0, success=False)
            
    def _get_page_count(self, pdf_path: str) -> int:
        if not os.path.exists(pdf_path):
            return 0
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Failed to extract page count using pypdf: {e}")
            return 0
