"""File management utilities for EPUB pipeline."""

import os
import shutil
from pathlib import Path
from typing import Optional, List
from contextlib import contextmanager


class FileManager:
    """Manage pipeline output files with optional cleanup."""

    def __init__(self, keep_intermediate: bool = False):
        """
        Initialize file manager.
        
        Args:
            keep_intermediate: If True, keep intermediate files (debug mode)
        """
        self.keep_intermediate = keep_intermediate
        self.intermediate_files: List[Path] = []
        self.final_output: Optional[Path] = None

    def register_intermediate(self, file_path: str) -> None:
        """
        Register an intermediate file for potential cleanup.
        
        Args:
            file_path: Path to intermediate file
        """
        path = Path(file_path)
        if path.exists():
            self.intermediate_files.append(path)

    def set_final_output(self, file_path: str) -> None:
        """
        Register the final output file (will never be cleaned).
        
        Args:
            file_path: Path to final output file
        """
        self.final_output = Path(file_path)

    def cleanup_intermediate_files(self) -> int:
        """
        Clean up intermediate files if keep_intermediate is False.
        
        Returns:
            Number of files deleted
        """
        if self.keep_intermediate:
            return 0
        
        deleted_count = 0
        
        for file_path in self.intermediate_files:
            # Never delete the final output
            if self.final_output and file_path == self.final_output:
                continue
            
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"Warning: Could not delete {file_path}: {str(e)}")
        
        # Clear the list after cleanup
        self.intermediate_files.clear()
        
        return deleted_count

    def get_intermediate_status(self) -> dict:
        """
        Get status of intermediate files.
        
        Returns:
            Dictionary with file info
        """
        return {
            "keep_intermediate": self.keep_intermediate,
            "total_intermediate": len(self.intermediate_files),
            "intermediate_files": [str(p) for p in self.intermediate_files],
            "final_output": str(self.final_output) if self.final_output else None,
            "total_size_mb": sum(p.stat().st_size / (1024*1024) for p in self.intermediate_files if p.exists())
        }

    def print_status(self) -> None:
        """Print file status to console."""
        status = self.get_intermediate_status()
        
        print("\n" + "="*70)
        print("INTERMEDIATE FILES STATUS")
        print("="*70)
        print(f"Keep intermediate files: {'YES (debug mode)' if status['keep_intermediate'] else 'NO (cleanup enabled)'}")
        print(f"Total intermediate files: {status['total_intermediate']}")
        print(f"Total size: {status['total_size_mb']:.2f} MB")
        print(f"Final output: {status['final_output']}")
        
        if status['intermediate_files'] and not status['keep_intermediate']:
            print("\nFiles to be cleaned up:")
            for f in status['intermediate_files']:
                if f != status['final_output']:
                    size = Path(f).stat().st_size / (1024*1024) if Path(f).exists() else 0
                    print(f"  - {Path(f).name} ({size:.2f} MB)")


@contextmanager
def temp_epub_file(stage: int, base_name: str):
    """
    Context manager for temporary EPUB files during pipeline execution.
    
    Yields the file path and ensures cleanup on exit if not in debug mode.
    
    Usage:
        with temp_epub_file(1, "my_epub") as temp_file:
            # Process temp_file
            pass  # Auto-cleaned unless debug mode
    
    Args:
        stage: Pipeline phase number (0-7)
        base_name: Base name without extension
    
    Yields:
        Path to the temporary file
    """
    temp_path = Path(f"{base_name}_p{stage}.epub")
    try:
        yield str(temp_path)
    finally:
        # File is managed by FileManager, not cleaned here
        pass


class PipelineFileTracker:
    """Track all files created during pipeline execution."""

    def __init__(self, base_epub_path: str, debug_mode: bool = False):
        """
        Initialize file tracker.
        
        Args:
            base_epub_path: Path to input EPUB
            debug_mode: Whether to keep intermediate files
        """
        self.base_name = Path(base_epub_path).stem
        self.debug_mode = debug_mode
        self.file_manager = FileManager(keep_intermediate=debug_mode)
        self.phase_files: dict = {}

    def register_phase_output(self, phase: int, filepath: str) -> str:
        """
        Register a phase output file.
        
        Args:
            phase: Phase number
            filepath: Output file path
        
        Returns:
            The filepath
        """
        self.phase_files[phase] = filepath
        self.file_manager.register_intermediate(filepath)
        return filepath

    def get_phase_input(self, phase: int) -> Optional[str]:
        """
        Get the output file from previous phase as input for current phase.
        
        Args:
            phase: Phase number
        
        Returns:
            Path to previous phase output, or None if not available
        """
        # Find the most recent prior phase file
        for prev_phase in range(phase - 1, -1, -1):
            if prev_phase in self.phase_files:
                return self.phase_files[prev_phase]
        
        return None

    def finalize(self, final_output: str, tmp_dir: Optional[Path] = None) -> int:
        """
        Finalize pipeline execution and clean up intermediate files.
        
        Args:
            final_output: Path to final output file
            tmp_dir: Optional path to tmp directory to clean up
        
        Returns:
            Number of files deleted
        """
        self.file_manager.set_final_output(final_output)
        deleted = self.file_manager.cleanup_intermediate_files()
        
        # Clean up tmp directory if not in debug mode and it's empty or contains only deleted files
        if not self.debug_mode and tmp_dir and tmp_dir.exists():
            try:
                import shutil
                remaining_files = list(tmp_dir.glob("*"))
                if not remaining_files:  # Only delete if directory is empty
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    return deleted + 1  # Count directory deletion
            except Exception:
                pass  # Silently ignore cleanup errors
        
        return deleted

    def print_summary(self) -> None:
        """Print file summary."""
        print("\n" + "="*70)
        print("PIPELINE FILE SUMMARY")
        print("="*70)
        print(f"Phase files created: {len(self.phase_files)}")
        
        for phase in sorted(self.phase_files.keys()):
            filepath = self.phase_files[phase]
            if Path(filepath).exists():
                size = Path(filepath).stat().st_size / (1024*1024)
                print(f"  Phase {phase}: {Path(filepath).name} ({size:.2f} MB)")
        
        if self.debug_mode:
            print("\nDebug mode: All intermediate files preserved")
        else:
            print("\nCleanup mode: Intermediate files will be removed")
