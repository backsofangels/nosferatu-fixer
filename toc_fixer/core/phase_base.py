"""Base class for EPUB transformation phases."""

import posixpath
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from zipfile import ZipFile

from bs4 import BeautifulSoup

from .epub_utils import EPUBRepackager, EPUBRepackingError
from .se_tools import SEToolWrapper
from .utils import safe_read

if TYPE_CHECKING:
    from .models import PipelineReport


class EPUBPhaseBase(ABC):
    """Base class for EPUB transformation phases with SE tool fallback pattern."""
    
    def __init__(self, epub_path: str, report: "PipelineReport"):
        """
        Initialize phase.
        
        Args:
            epub_path: Path to input EPUB
            report: PipelineReport for logging
        """
        self.epub_path = epub_path
        self.report = report
        self.temp_dir: Optional[Path] = None
        self.opf_base = ""
        self.opf_path: Optional[Path] = None
        self.opf_soup: Optional[BeautifulSoup] = None
    
    def execute(self, se_tool_name: Optional[str] = None, output_path: str = "") -> bool:
        """
        Execute phase with SE tool fallback.
        
        Tries SE tool first (if provided), then falls back to custom implementation.
        Always cleans up temp directory.
        
        Args:
            se_tool_name: Name of SE tool to try first (e.g., "clean", "semanticate")
            output_path: Path for output EPUB
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try SE tool first
            if se_tool_name:
                if self._try_se_tool(se_tool_name):
                    if output_path:
                        self._repack_and_save(output_path)
                    return True
            
            # Fallback to custom implementation
            return self._run_custom_implementation(output_path)
        
        finally:
            self.cleanup()
    
    def _try_se_tool(self, tool_name: str) -> bool:
        """
        Try to run SE tool.
        
        Args:
            tool_name: Name of SE tool
            
        Returns:
            True if successful
        """
        try:
            self.temp_dir = SEToolWrapper.unpack_epub(self.epub_path)
            return SEToolWrapper.run_tool(tool_name, self.temp_dir, self.se_tool_timeout, self.report)
        except Exception as e:
            self.report.warnings.append(f"SE tool setup failed: {str(e)}")
            return False
    
    @abstractmethod
    def _run_custom_implementation(self, output_path: str) -> bool:
        """
        Subclasses implement custom transformation logic.
        
        Args:
            output_path: Path for output EPUB
            
        Returns:
            True if successful
        """
        pass
    
    def _unpack_epub(self) -> None:
        """Unpack EPUB to temp directory if not already unpacked."""
        if self.temp_dir is None:
            try:
                self.temp_dir = SEToolWrapper.unpack_epub(self.epub_path)
            except Exception as e:
                self.report.validation_errors.append(f"Failed to unpack EPUB: {str(e)}")
    
    def _parse_opf(self) -> None:
        """
        Parse OPF file.
        
        Sets self.opf_path, self.opf_base, and self.opf_soup.
        """
        if not self.temp_dir:
            return
        
        try:
            opf_files = list(self.temp_dir.glob("**/*.opf"))
            if not opf_files:
                self.report.validation_errors.append("No OPF file found in EPUB")
                return
            
            self.opf_path = opf_files[0]
            self.opf_base = str(self.opf_path.parent.relative_to(self.temp_dir))
            
            with open(self.opf_path, "r", encoding="utf-8", errors="replace") as f:
                opf_content = f.read()
            
            self.opf_soup = BeautifulSoup(opf_content, "lxml-xml")
        
        except Exception as e:
            self.report.warnings.append(f"Failed to parse OPF: {str(e)}")
    
    def _repack_and_save(self, output_path: str) -> bool:
        """
        Repack modified EPUB and save to output path.
        
        Args:
            output_path: Path for output EPUB
            
        Returns:
            True if successful
        """
        try:
            EPUBRepackager.repack_from_temp_dir(self.temp_dir, output_path)
            return True
        except EPUBRepackingError as e:
            self.report.validation_errors.append(str(e))
            return False
    
    def _write_opf(self) -> None:
        """Write updated OPF back to disk."""
        if not self.opf_soup or not self.opf_path:
            return
        
        try:
            opf_content = str(self.opf_soup.prettify())
            with open(self.opf_path, "w", encoding="utf-8") as f:
                f.write(opf_content)
        except Exception as e:
            self.report.validation_errors.append(f"Failed to write OPF: {str(e)}")
    
    def cleanup(self) -> None:
        """Clean up temporary directory."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                self.report.warnings.append(f"Failed to clean up temp directory: {str(e)}")
    
    @property
    def se_tool_timeout(self) -> int:
        """Timeout for SE tool execution. Override in subclass if needed."""
        return 120
