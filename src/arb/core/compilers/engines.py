import os
import subprocess
import logging
from typing import Protocol
from dataclasses import dataclass
from pathlib import Path
import shutil
from arb.core.paths import get_bundled_binary_dir

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
    def _resolve_tectonic(self) -> str:
        """
        Resolves the tectonic executable.
        Checks bundled binaries first, then falls back to system PATH.
        """
        # 1. Check bundled binary
        bin_dir = get_bundled_binary_dir()
        bundled_exe = bin_dir / "tectonic.exe" if os.name == "nt" else bin_dir / "tectonic"
        if bundled_exe.exists() and bundled_exe.is_file():
            return str(bundled_exe)
        
        # 2. Check system PATH
        system_exe = shutil.which("tectonic")
        if system_exe:
            return system_exe
            
        return "tectonic"  # Let subprocess throw FileNotFoundError

    def compile(self, tex_path: str) -> CompilationResult:
        output_dir = os.path.dirname(tex_path)
        pdf_path = tex_path.replace(".tex", ".pdf")
        
        tectonic_cmd = self._resolve_tectonic()
        
        logger.info(f"Compiling LaTeX to PDF using Tectonic ({tectonic_cmd})...")
        try:
            subprocess.run(
                [
                    tectonic_cmd,
                    "--outdir",
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
