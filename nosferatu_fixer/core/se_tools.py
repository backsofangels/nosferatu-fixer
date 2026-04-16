"""SE tools wrapper for consistent subprocess handling."""

import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from zipfile import ZipFile

if TYPE_CHECKING:
    from .models import PipelineReport


class SEToolError(Exception):
    """Raised when SE tool execution fails."""
    pass


class SEToolWrapper:
    """Handle SE tool execution with consistent error handling."""
    
    @staticmethod
    def unpack_epub(epub_path: str) -> Path:
        """
        Unpack EPUB to temporary directory.
        
        Args:
            epub_path: Path to EPUB file
            
        Returns:
            Path to temporary directory with unpacked EPUB
            
        Raises:
            SEToolError: If unpacking fails
        """
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="epub_"))
            with ZipFile(epub_path, "r") as zf:
                zf.extractall(temp_dir)
            return temp_dir
        except Exception as e:
            raise SEToolError(f"Failed to unpack EPUB: {str(e)}")
    
    @staticmethod
    def run_tool(
        tool_name: str,
        temp_dir: Path,
        timeout: int = 120,
        report: Optional["PipelineReport"] = None
    ) -> bool:
        """
        Run SE tool on unpacked EPUB.
        
        Args:
            tool_name: Name of SE tool (e.g., "clean", "semanticate", "build-toc")
            temp_dir: Unpacked EPUB directory
            timeout: Execution timeout in seconds
            report: PipelineReport for logging warnings
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = subprocess.run(
                ["se", tool_name, str(temp_dir)],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                if report:
                    report.warnings.append(f"Used se {tool_name} tool")
                return True
            else:
                if report:
                    report.warnings.append(
                        f"se {tool_name} failed (code {result.returncode})"
                    )
                return False
        
        except FileNotFoundError:
            if report:
                report.warnings.append(f"se {tool_name} not found, using custom implementation")
            return False
        except subprocess.TimeoutExpired:
            if report:
                report.warnings.append(f"se {tool_name} timed out, using custom implementation")
            return False
        except Exception as e:
            if report:
                report.warnings.append(f"se {tool_name} error: {str(e)}, using custom implementation")
            return False
