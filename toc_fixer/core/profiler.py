"""Performance profiling utilities for EPUB pipeline."""

import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Dict, Any
import json


@dataclass
class PerformanceMetrics:
    """Performance metrics for a code section."""
    name: str
    duration_seconds: float
    memory_mb_before: float
    memory_mb_after: float
    memory_mb_delta: float
    peak_memory_mb: float


class PerformanceProfiler:
    """Profile performance of pipeline phases."""
    
    def __init__(self):
        """Initialize profiler."""
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.phase_metrics: Dict[int, Dict[str, Any]] = {}

    @contextmanager
    def profile(self, name: str):
        """
        Context manager to profile a code section.
        
        Usage:
            with profiler.profile("phase_name"):
                # Code to profile
        """
        tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        memory_before = current / (1024 * 1024)
        
        start_time = time.time()
        
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            current, peak = tracemalloc.get_traced_memory()
            memory_after = current / (1024 * 1024)
            peak_memory = peak / (1024 * 1024)
            memory_delta = memory_after - memory_before
            
            tracemalloc.stop()
            
            metric = PerformanceMetrics(
                name=name,
                duration_seconds=duration,
                memory_mb_before=memory_before,
                memory_mb_after=memory_after,
                memory_mb_delta=memory_delta,
                peak_memory_mb=peak_memory
            )
            
            self.metrics[name] = metric

    def record_phase_metric(self, phase: int, key: str, value: Any) -> None:
        """
        Record a metric for a phase.
        
        Args:
            phase: Phase number
            key: Metric key
            value: Metric value
        """
        if phase not in self.phase_metrics:
            self.phase_metrics[phase] = {}
        
        self.phase_metrics[phase][key] = value

    def get_phase_metrics(self, phase: int) -> Dict[str, Any]:
        """Get metrics for a specific phase."""
        return self.phase_metrics.get(phase, {})

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate performance report.
        
        Returns:
            Dictionary with performance data
        """
        total_time = sum(m.duration_seconds for m in self.metrics.values())
        total_memory = sum(m.memory_mb_delta for m in self.metrics.values())
        peak_memory = max((m.peak_memory_mb for m in self.metrics.values()), default=0)
        
        return {
            "total_time_seconds": total_time,
            "total_memory_mb": total_memory,
            "peak_memory_mb": peak_memory,
            "section_metrics": [
                {
                    "name": m.name,
                    "duration_seconds": m.duration_seconds,
                    "percentage_of_total": (m.duration_seconds / total_time * 100) if total_time > 0 else 0,
                    "memory_mb_delta": m.memory_mb_delta,
                    "peak_memory_mb": m.peak_memory_mb
                }
                for m in self.metrics.values()
            ],
            "phase_metrics": self.phase_metrics
        }

    def print_report(self) -> None:
        """Print performance report to console."""
        report = self.generate_report()
        
        print("\n" + "="*70)
        print("PERFORMANCE PROFILING REPORT")
        print("="*70)
        print(f"Total time: {report['total_time_seconds']:.2f} seconds")
        print(f"Total memory delta: {report['total_memory_mb']:.2f} MB")
        print(f"Peak memory: {report['peak_memory_mb']:.2f} MB")
        
        print("\nSection breakdown:")
        print(f"{'Section':<30} {'Time (s)':<12} {'% of Total':<12} {'Mem Delta (MB)':<15}")
        print("-" * 70)
        
        for section in sorted(report['section_metrics'], key=lambda x: x['duration_seconds'], reverse=True):
            print(
                f"{section['name']:<30} "
                f"{section['duration_seconds']:<12.3f} "
                f"{section['percentage_of_total']:<12.1f} "
                f"{section['memory_mb_delta']:<15.2f}"
            )

    def export_json(self, path: str) -> None:
        """
        Export metrics to JSON file.
        
        Args:
            path: File path for export
        """
        report = self.generate_report()
        
        with open(path, "w") as f:
            json.dump(report, f, indent=2)


# Global profiler instance
_profiler: Optional[PerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """Get or create global profiler instance."""
    global _profiler
    if _profiler is None:
        _profiler = PerformanceProfiler()
    return _profiler


def profile_section(name: str):
    """
    Decorator to profile a function.
    
    Usage:
        @profile_section("my_function")
        def my_function():
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            profiler = get_profiler()
            with profiler.profile(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator
