"""Batch processing for multiple EPUBs with directory structure preservation."""

import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from .core import PipelineReport


@dataclass
class BatchResult:
    """Result of processing a single EPUB in batch."""
    input_path: str
    output_path: str
    success: bool
    error: Optional[str] = None
    epub_version: Optional[str] = None
    original_toc_entries: int = 0
    rebuilt_toc_entries: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class BatchReport:
    """Summary report for entire batch operation."""
    batch_input_dir: str
    batch_output_dir: str
    total_files: int = 0
    processed_successful: int = 0
    processed_failed: int = 0
    files: list[BatchResult] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.processed_successful / self.total_files * 100


class BatchProcessor:
    """Process multiple EPUBs while preserving directory structure."""
    
    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        phases: str = "0,1,2,3,4,5,6,7",
        realign_spine: bool = False,
        json_reports: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize batch processor.
        
        Args:
            input_dir: Directory containing EPUBs to process
            output_dir: Directory where cleaned EPUBs will be saved
            phases: Comma-separated phases to run
            realign_spine: Enable spine realignment phase
            json_reports: Generate JSON reports for each EPUB
            verbose: Verbose output
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.phases = phases
        self.realign_spine = realign_spine
        self.json_reports = json_reports
        self.verbose = verbose
        
        # Validate input directory
        if not self.input_dir.exists():
            raise ValueError(f"Input directory not found: {self.input_dir}")
        if not self.input_dir.is_dir():
            raise ValueError(f"Input path is not a directory: {self.input_dir}")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.batch_report = BatchReport(
            batch_input_dir=str(self.input_dir),
            batch_output_dir=str(self.output_dir)
        )
    
    def find_epubs(self) -> list[Path]:
        """Find all EPUB files in input directory recursively."""
        epub_files = list(self.input_dir.rglob("*.epub"))
        return sorted(epub_files)
    
    def get_output_path(self, input_epub: Path) -> Path:
        """
        Get output path, preserving directory structure.
        
        Examples:
            input_dir/book.epub → output_dir/book-cleaned.epub
            input_dir/classics/book.epub → output_dir/classics/book-cleaned.epub
        """
        # Get relative path from input_dir
        rel_path = input_epub.relative_to(self.input_dir)
        
        # Create output subdirectories if needed
        output_subdir = self.output_dir / rel_path.parent
        output_subdir.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename: book.epub → book-cleaned.epub
        stem = input_epub.stem
        output_file = output_subdir / f"{stem}-cleaned.epub"
        
        return output_file
    
    def process_batch(self) -> BatchReport:
        """
        Process all EPUBs in input directory.
        
        Returns:
            Batch report with results
        """
        epub_files = self.find_epubs()
        
        if not epub_files:
            if self.verbose:
                print(f"No EPUB files found in {self.input_dir}")
            return self.batch_report
        
        if self.verbose:
            print(f"Found {len(epub_files)} EPUB files")
            print()
        
        self.batch_report.total_files = len(epub_files)
        
        for idx, input_epub in enumerate(epub_files, 1):
            output_epub = self.get_output_path(input_epub)
            
            if self.verbose:
                print(f"[{idx}/{len(epub_files)}] Processing: {input_epub.name}")
                print(f"  → {output_epub.relative_to(self.output_dir)}")
            
            result = self._process_single_epub(input_epub, output_epub)
            self.batch_report.files.append(result)
            
            if result.success:
                self.batch_report.processed_successful += 1
                if self.verbose:
                    print(f"  ✓ Success (TOC: {result.rebuilt_toc_entries} entries)")
            else:
                self.batch_report.processed_failed += 1
                if self.verbose:
                    print(f"  ✗ Failed: {result.error}")
            
            if self.verbose:
                print()
        
        return self.batch_report
    
    def _process_single_epub(self, input_epub: Path, output_epub: Path) -> BatchResult:
        """
        Process a single EPUB file.
        
        Args:
            input_epub: Path to input EPUB
            output_epub: Path to output EPUB
            
        Returns:
            BatchResult with success/failure info
        """
        try:
            # Import here to avoid circular imports
            from .pipeline import run_phase0, run_phase1, run_phase2, run_phase3
            from .pipeline import run_phase4, run_phase5, run_phase6, run_phase7
            from .core.file_manager import PipelineFileTracker
            
            report = PipelineReport(input=str(input_epub), output=str(output_epub))
            file_tracker = PipelineFileTracker(str(input_epub), debug_mode=False)
            
            phases = [p.strip() for p in self.phases.split(",")]
            
            # Phase 0: Always run for metadata
            if "0" in phases:
                report = run_phase0(str(input_epub), None)
                if report.drm:
                    return BatchResult(
                        input_path=str(input_epub),
                        output_path=str(output_epub),
                        success=False,
                        error="DRM-protected EPUB"
                    )
            
            # Set up temp/reports directories for this batch
            tmp_dir = Path("tmp")
            tmp_dir.mkdir(exist_ok=True)
            
            current_epub = str(input_epub)
            
            # Phase 1: HTML cleanup
            if "1" in phases:
                phase_output = str(tmp_dir / f"{input_epub.stem}_p1.epub")
                if run_phase1(current_epub, phase_output, report):
                    file_tracker.register_phase_output(1, phase_output)
                    current_epub = phase_output
            
            # Phase 2: Semantic upgrade
            if "2" in phases:
                phase_output = str(tmp_dir / f"{input_epub.stem}_p2.epub")
                ncx_entries = getattr(report, "_ncx_entries", None)
                if run_phase2(current_epub, phase_output, report, ncx_entries):
                    file_tracker.register_phase_output(2, phase_output)
                    current_epub = phase_output
            
            # Phase 3: Spine realignment (optional)
            if "3" in phases and self.realign_spine:
                phase_output = str(tmp_dir / f"{input_epub.stem}_p3.epub")
                if run_phase3(current_epub, phase_output, report):
                    file_tracker.register_phase_output(3, phase_output)
                    current_epub = phase_output
            
            # Phase 4: TOC rebuild
            if "4" in phases:
                phase_output = str(tmp_dir / f"{input_epub.stem}_p4.epub")
                if run_phase4(current_epub, phase_output, report):
                    file_tracker.register_phase_output(4, phase_output)
                    current_epub = phase_output
            
            # Phase 5: Typography
            if "5" in phases:
                phase_output = str(tmp_dir / f"{input_epub.stem}_p5.epub")
                if run_phase5(current_epub, phase_output, report):
                    file_tracker.register_phase_output(5, phase_output)
                    current_epub = phase_output
            
            # Phase 6: CSS rewrite
            if "6" in phases:
                phase_output = str(tmp_dir / f"{input_epub.stem}_p6.epub")
                if run_phase6(current_epub, phase_output, report):
                    file_tracker.register_phase_output(6, phase_output)
                    current_epub = phase_output
            
            # Phase 7: Validation (no output file during processing)
            if "7" in phases:
                run_phase7(current_epub, str(output_epub), report)
            
            # Copy final EPUB to output location (if not already done by Phase 7)
            if current_epub != str(output_epub):
                import shutil
                shutil.copy(current_epub, output_epub)
            
            # Finalize (cleanup is optional in batch mode as we just copy final output)
            # file_tracker.finalize(str(output_epub))
            
            return BatchResult(
                input_path=str(input_epub),
                output_path=str(output_epub),
                success=True,
                epub_version=report.epub_version,
                original_toc_entries=report.original_toc_entries,
                rebuilt_toc_entries=report.rebuilt_toc_entries,
                warnings=report.warnings[:3] if report.warnings else []
            )
        
        except Exception as e:
            return BatchResult(
                input_path=str(input_epub),
                output_path=str(output_epub),
                success=False,
                error=str(e)
            )
    
    def save_batch_report(self) -> Path:
        """
        Save batch report as JSON.
        
        Returns:
            Path to saved report
        """
        report_file = self.output_dir / "batch_report.json"
        
        # Convert to dict for JSON serialization
        report_dict = {
            "batch_input_dir": self.batch_report.batch_input_dir,
            "batch_output_dir": self.batch_report.batch_output_dir,
            "total_files": self.batch_report.total_files,
            "processed_successful": self.batch_report.processed_successful,
            "processed_failed": self.batch_report.processed_failed,
            "success_rate_percent": round(self.batch_report.success_rate, 1),
            "files": [
                {
                    "input_path": str(f.input_path),
                    "output_path": str(f.output_path),
                    "success": f.success,
                    "error": f.error,
                    "epub_version": f.epub_version,
                    "original_toc_entries": f.original_toc_entries,
                    "rebuilt_toc_entries": f.rebuilt_toc_entries,
                    "warnings": f.warnings
                }
                for f in self.batch_report.files
            ]
        }
        
        with open(report_file, "w") as f:
            json.dump(report_dict, f, indent=2)
        
        return report_file
    
    def print_summary(self) -> None:
        """Print batch processing summary to stdout."""
        print("\n" + "="*60)
        print("BATCH PROCESSING SUMMARY")
        print("="*60)
        print(f"Input directory:      {self.batch_report.batch_input_dir}")
        print(f"Output directory:     {self.batch_report.batch_output_dir}")
        print(f"Total files:          {self.batch_report.total_files}")
        print(f"Successful:           {self.batch_report.processed_successful}")
        print(f"Failed:               {self.batch_report.processed_failed}")
        print(f"Success rate:         {self.batch_report.success_rate:.1f}%")
        print("="*60)
        
        if self.batch_report.files:
            print("\nProcessed files:")
            for result in self.batch_report.files:
                status = "✓" if result.success else "✗"
                toc_info = f"TOC: {result.rebuilt_toc_entries}" if result.success else result.error
                print(f"  {status} {Path(result.input_path).name:40} {toc_info}")
