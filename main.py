#!/usr/bin/env python3
"""
Main CLI entry point for EPUB Wild-to-Clean Pipeline.

Usage:
    python main.py around-the-world.epub
    python main.py around-the-world.epub --ground-truth <path>
    python main.py around-the-world.epub --phases 0,1,2,4
    python main.py around-the-world.epub --dry-run
    python main.py around-the-world.epub --output <path>
    python main.py around-the-world.epub --realign-spine
    python main.py around-the-world.epub --lang it
    python main.py around-the-world.epub --epub2-compat
    python main.py around-the-world.epub --validate
"""

import argparse
import sys
from pathlib import Path

from toc_fixer.core import PipelineReport
from toc_fixer.core.file_manager import PipelineFileTracker
from toc_fixer.batch_processor import BatchProcessor
from toc_fixer.pipeline import (
    run_phase0, run_phase1, run_phase2, run_phase3, run_phase4, run_phase5,
    run_phase6, run_phase7
)


def main():
    parser = argparse.ArgumentParser(
        description="Transform wild EPUB (Gutenberg/Calibre) into clean Standard Ebooks EPUB"
    )
    
    parser.add_argument(
        "epub",
        nargs="?",
        default=None,
        help="Path to input EPUB file (or use --batch-input for batch processing)"
    )
    
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Path to output EPUB (default: input_clean.epub)"
    )
    
    parser.add_argument(
        "--ground-truth", "-g",
        default=None,
        help="Path to Standard Ebooks ground truth EPUB for F1 scoring"
    )
    
    parser.add_argument(
        "--phases",
        default="0,1,2,3,4,5,6,7",
        help="Comma-separated list of phases to run (default: all)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze only, do not write files"
    )
    
    parser.add_argument(
        "--realign-spine",
        action="store_true",
        help="Enable Phase 3 (spine realignment, optional)"
    )
    
    parser.add_argument(
        "--lang",
        default="en",
        choices=["en", "it"],
        help="Language for typography rules (default: en)"
    )
    
    parser.add_argument(
        "--epub2-compat",
        action="store_true",
        help="Output EPUB 2.0 compatible format"
    )
    
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run epubcheck validation at end"
    )
    
    parser.add_argument(
        "--debug-output",
        action="store_true",
        help="Keep intermediate phase files for debugging (default: clean up)"
    )
    
    parser.add_argument(
        "--json-reports",
        action="store_true",
        help="Generate JSON reports for each phase (stored in reports/ directory)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "--batch-input",
        default=None,
        help="Batch mode: directory containing EPUBs to process (preserves directory structure)"
    )
    
    parser.add_argument(
        "--batch-output",
        default=None,
        help="Batch mode: directory where cleaned EPUBs will be saved"
    )
    
    parser.add_argument(
        "--batch-report",
        action="store_true",
        help="Generate batch_report.json with processing results"
    )
    
    parser.add_argument(
        "--keep-toc-format",
        action="store_true",
        help="Keep original TOC format (NCX for EPUB2, nav.xhtml for EPUB3) instead of regenerating both"
    )
    
    args = parser.parse_args()
    
    # ========== BATCH MODE ==========
    if args.batch_input:
        if not args.batch_output:
            print("Error: --batch-output required when using --batch-input", file=sys.stderr)
            sys.exit(1)
        
        try:
            processor = BatchProcessor(
                input_dir=Path(args.batch_input),
                output_dir=Path(args.batch_output),
                phases=args.phases,
                realign_spine=args.realign_spine,
                json_reports=args.json_reports,
                verbose=args.verbose
            )
            
            # Process all EPUBs
            batch_report = processor.process_batch()
            
            # Print summary
            processor.print_summary()
            
            # Save report if requested
            if args.batch_report:
                report_file = processor.save_batch_report()
                print(f"\nBatch report saved to: {report_file}")
            
            # Exit with success
            sys.exit(0)
        
        except Exception as e:
            print(f"Error: Batch processing failed: {e}", file=sys.stderr)
            sys.exit(1)
    
    # ========== SINGLE FILE MODE ==========
    if not args.epub:
        print("Error: Must provide EPUB file or use --batch-input", file=sys.stderr)
        sys.exit(1)
    
    # Validate input file
    epub_path = Path(args.epub)
    if not epub_path.exists():
        print(f"Error: Input EPUB not found: {epub_path}", file=sys.stderr)
        sys.exit(1)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        stem = epub_path.stem
        output_path = f"{stem}_clean.epub"
    
    # Set up tmp directory for intermediate EPUBs
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(exist_ok=True)
    
    # Set up reports directory if --json-reports flag is set
    reports_dir = None
    if args.json_reports:
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
    
    # Parse phases
    try:
        phases = [p.strip() for p in args.phases.split(",")]
    except Exception:
        print(f"Error: Invalid phases argument: {args.phases}", file=sys.stderr)
        sys.exit(1)
    
    if args.verbose:
        print()
    
    # Initialize report and file tracker
    report = PipelineReport(input=str(epub_path), output=output_path)
    file_tracker = PipelineFileTracker(str(epub_path), debug_mode=args.debug_output)
    
    # Run Phase 0 (always first)
    if "0" in phases:
        if args.verbose:
            print("Running Phase 0: Diagnosis...")
        # Determine Phase 0 report path
        if args.json_reports:
            phase0_report_path = str(reports_dir / f"{epub_path.stem}_phase0_report.json")
        else:
            phase0_report_path = None
        report = run_phase0(str(epub_path), phase0_report_path)
        
        if args.verbose:
            print(f"  EPUB version: {report.epub_version}")
            print(f"  Language: {report.language}")
            print(f"  RTL: {report.rtl}")
            print(f"  Fixed layout: {report.fixed_layout}")
            print(f"  DRM: {report.drm}")
            print(f"  Spine items: {report.spine_items}")
            print(f"  Semantic headings: {report.semantic_headings_found}")
            print(f"  epub:type tags: {report.epub_type_tags_found}")
            print(f"  Original TOC entries: {report.original_toc_entries}")
            print(f"  Markup quality: {report.markup_quality}")
            print(f"  Dominant pattern: {report.dominant_pattern}")
            print(f"  Recommended phases: {', '.join(report.recommended_phases)}")
            if report.validation_errors:
                print(f"  Errors: {'; '.join(report.validation_errors)}")
            if report.warnings:
                print(f"  Warnings: {'; '.join(report.warnings)}")
        
        if report.drm:
            print("Error: EPUB is DRM-protected and cannot be processed.", file=sys.stderr)
            sys.exit(1)
        
        if phase0_report_path:
            print(f"Phase 0 report written to: {phase0_report_path}")
    else:
        if args.verbose:
            print("Skipping Phase 0")
    
    # Track current EPUB file (changes after each phase)
    current_epub = str(epub_path)
    phase_output = None
    
    # Run Phase 1 if requested
    if "1" in phases:
        if args.verbose:
            print("\nRunning Phase 1: HTML Cleanup...")
        
        phase_output = str(tmp_dir / f"{epub_path.stem}_p1.epub")
        success = run_phase1(current_epub, phase_output, report)
        
        if success:
            file_tracker.register_phase_output(1, phase_output)
            current_epub = phase_output
            if args.verbose:
                print(f"  Phase 1 complete: {phase_output}")
        else:
            print(f"Warning: Phase 1 failed, skipping", file=sys.stderr)
            report.validation_errors.append("Phase 1 failed")
    
    # Run Phase 2 if requested
    if "2" in phases:
        if args.verbose:
            print("\nRunning Phase 2: Semantic Upgrade (6-pass heading detection)...")
        
        phase_output = str(tmp_dir / f"{epub_path.stem}_p2.epub")
        # Pass NCX entries from Phase 0 if available
        ncx_entries = getattr(report, "_ncx_entries", None)
        success = run_phase2(current_epub, phase_output, report, ncx_entries)
        
        if success:
            file_tracker.register_phase_output(2, phase_output)
            current_epub = phase_output
            if args.verbose:
                print(f"  Phase 2 complete: {phase_output}")
                if hasattr(report, "detection_sources"):
                    print(f"  Heading detection sources: {report.detection_sources}")
        else:
            print(f"Warning: Phase 2 failed, skipping", file=sys.stderr)
            report.validation_errors.append("Phase 2 failed")
    
    # Run Phase 3 if requested and --realign-spine flag set
    if "3" in phases and args.realign_spine:
        if args.verbose:
            print("\nRunning Phase 3: Spine Realignment (se split-file)...")
        
        phase_output = str(tmp_dir / f"{epub_path.stem}_p3.epub")
        success = run_phase3(current_epub, phase_output, report)
        
        if success:
            file_tracker.register_phase_output(3, phase_output)
            current_epub = phase_output
            if args.verbose:
                print(f"  Phase 3 complete: {phase_output}")
        else:
            print(f"Warning: Phase 3 failed, skipping", file=sys.stderr)
            report.validation_errors.append("Phase 3 failed")
    
    # Run Phase 4 if requested
    if "4" in phases:
        if args.verbose:
            print("\nRunning Phase 4: TOC Rebuild...")
        
        phase_output = str(tmp_dir / f"{epub_path.stem}_p4.epub")
        success = run_phase4(
            current_epub, 
            phase_output, 
            report,
            keep_toc_format=args.keep_toc_format
        )
        
        if success:
            file_tracker.register_phase_output(4, phase_output)
            current_epub = phase_output
            if args.verbose:
                print(f"  Phase 4 complete: {phase_output}")
                if args.keep_toc_format:
                    print(f"  TOC format: {report.original_toc_format} (preserved)")
                else:
                    print(f"  TOC format: NCX + nav.xhtml (both generated)")
                if hasattr(report, "rebuilt_toc_entries"):
                    print(f"  Rebuilt TOC entries: {report.rebuilt_toc_entries}")
        else:
            print(f"Warning: Phase 4 failed, skipping", file=sys.stderr)
            report.validation_errors.append("Phase 4 failed")
    
    # Run Phase 5 if requested
    if "5" in phases:
        if args.verbose:
            print("\nRunning Phase 5: Typogrify (Typography)...")
        
        phase_output = str(tmp_dir / f"{epub_path.stem}_p5.epub")
        success = run_phase5(current_epub, phase_output, report, args.lang)
        
        if success:
            file_tracker.register_phase_output(5, phase_output)
            current_epub = phase_output
            if args.verbose:
                print(f"  Phase 5 complete: {phase_output}")
        else:
            print(f"Warning: Phase 5 failed, skipping", file=sys.stderr)
            report.validation_errors.append("Phase 5 failed")
    
    # Run Phase 6 if requested
    if "6" in phases:
        if args.verbose:
            print("\nRunning Phase 6: CSS Rewrite (consolidation and standardization)...")
        
        phase_output = str(tmp_dir / f"{epub_path.stem}_p6.epub")
        success = run_phase6(current_epub, phase_output, report)
        
        if success:
            file_tracker.register_phase_output(6, phase_output)
            current_epub = phase_output
            if args.verbose:
                print(f"  Phase 6 complete: {phase_output}")
        else:
            print(f"Warning: Phase 6 failed, skipping", file=sys.stderr)
            report.validation_errors.append("Phase 6 failed")
    
    # Run Phase 7 if requested (validation + F1 scoring)
    if "7" in phases:
        if args.verbose:
            print("\nRunning Phase 7: Validation (se lint, epubcheck, F1 scoring)...")
        
        if args.json_reports:
            phase7_report_path = str(reports_dir / f"{epub_path.stem}_phase7_report.json")
        else:
            phase7_report_path = None
        success = run_phase7(current_epub, phase7_report_path, report, args.ground_truth)
        
        if success:
            if args.verbose:
                if phase7_report_path:
                    print(f"  Phase 7 complete: {phase7_report_path}")
                else:
                    print(f"  Phase 7 complete")
                if report.f1_score is not None:
                    print(f"  F1 score: {report.f1_score:.3f}")
                if report.validation_errors:
                    print(f"  Errors found: {len(report.validation_errors)}")
        else:
            print(f"Warning: Phase 7 failed, skipping", file=sys.stderr)
            report.validation_errors.append("Phase 7 failed")
    
    # Copy current output to final output path if different
    if current_epub != output_path:
        import shutil
        import os
        
        # Verify the source file exists before attempting copy
        if not os.path.exists(current_epub):
            # Try to find the most recent phase output that exists
            found_file = None
            for phase in sorted(file_tracker.phase_files.keys(), reverse=True):
                candidate = file_tracker.phase_files[phase]
                if os.path.exists(candidate):
                    found_file = candidate
                    current_epub = candidate
                    print(f"Note: Using {os.path.basename(candidate)} as input for final output", file=sys.stderr)
                    break
            
            if not found_file:
                # No valid phase output found; use input file as fallback
                current_epub = str(epub_path)
                if not os.path.exists(current_epub):
                    print(f"Error: No valid input file found. Pipeline produced no usable output.", file=sys.stderr)
                    sys.exit(1)
                print(f"Warning: No phase outputs available; using original input file", file=sys.stderr)
        
        # Now copy the verified source file
        shutil.copy(current_epub, output_path)
        file_tracker.register_phase_output(99, current_epub)  # Mark current as eligible for cleanup
    
    # Clean up intermediate files (unless --debug-output flag)
    deleted_count = file_tracker.finalize(output_path, tmp_dir=tmp_dir)
    
    if args.verbose:
        print("\n[OK] Pipeline complete!")
        print(f"Final output: {output_path}")
        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} intermediate file(s)")
        elif args.debug_output:
            print(f"Debug mode: {len(file_tracker.phase_files)} intermediate files preserved")
        if args.json_reports:
            print(f"JSON reports written to: {reports_dir}")
        file_tracker.print_summary()


if __name__ == "__main__":
    main()
