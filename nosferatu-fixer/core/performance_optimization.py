"""Performance optimization utilities and analysis."""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass


@dataclass
class OptimizationRecommendation:
    """An optimization recommendation."""
    category: str
    issue: str
    impact: str  # "high", "medium", "low"
    recommendation: str
    estimated_improvement: str


class PerformanceAnalyzer:
    """Analyze performance metrics and generate optimization recommendations."""

    def __init__(self, test_report_path: str):
        """
        Initialize analyzer.
        
        Args:
            test_report_path: Path to test_report.json
        """
        self.report_path = test_report_path
        self.report: Dict[str, Any] = {}
        self._load_report()

    def _load_report(self) -> None:
        """Load test report from JSON file."""
        try:
            with open(self.report_path, "r") as f:
                self.report = json.load(f)
        except Exception as e:
            print(f"Error loading report: {str(e)}")
            self.report = {}

    def analyze_size_growth(self) -> List[OptimizationRecommendation]:
        """
        Analyze EPUB size growth and recommend optimizations.
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if not self.report.get("results"):
            return recommendations
        
        for result in self.report["results"]:
            input_size = result.get("epub_size_mb", 0)
            output_size = result.get("final_output_size_mb", 0)
            
            if input_size == 0:
                continue
            
            growth_ratio = output_size / input_size
            growth_pct = (growth_ratio - 1) * 100
            
            if growth_ratio > 1.5:
                recommendations.append(OptimizationRecommendation(
                    category="Size Growth",
                    issue=f"EPUB size increased by {growth_pct:.1f}% ({input_size:.2f}MB → {output_size:.2f}MB)",
                    impact="high",
                    recommendation="Optimize CSS consolidation (Phase 6): Remove redundant rules, minify CSS",
                    estimated_improvement="10-20% size reduction"
                ))
            
            if growth_ratio > 1.3:
                recommendations.append(OptimizationRecommendation(
                    category="Size Growth",
                    issue=f"Moderate size increase ({growth_pct:.1f}%)",
                    impact="medium",
                    recommendation="Review Phase 1 HTML cleanup: Check for unnecessary attributes or formatting",
                    estimated_improvement="5-10% size reduction"
                ))
        
        return recommendations

    def analyze_execution_time(self) -> List[OptimizationRecommendation]:
        """
        Analyze execution time and recommend optimizations.
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if not self.report.get("results"):
            return recommendations
        
        total_time = self.report.get("total_time_seconds", 0)
        avg_time = self.report.get("average_time_seconds", 0)
        
        if avg_time > 5:
            recommendations.append(OptimizationRecommendation(
                category="Execution Time",
                issue=f"Average pipeline time is {avg_time:.2f} seconds",
                impact="medium",
                recommendation="Profile phases to identify slow operations; consider caching common parsing",
                estimated_improvement="30-40% faster execution"
            ))
        
        if avg_time > 10:
            recommendations.append(OptimizationRecommendation(
                category="Execution Time",
                issue=f"Pipeline is slow ({avg_time:.2f}s average)",
                impact="high",
                recommendation="Implement parallel processing for independent phases (2,4,5,6 can run concurrently after 1)",
                estimated_improvement="50% faster execution"
            ))
        
        return recommendations

    def analyze_failures(self) -> List[OptimizationRecommendation]:
        """
        Analyze test failures.
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if not self.report.get("results"):
            return recommendations
        
        for result in self.report["results"]:
            if not result.get("success"):
                errors = result.get("validation_errors", [])
                if errors:
                    recommendations.append(OptimizationRecommendation(
                        category="Failure Recovery",
                        issue=f"EPUB test failed: {errors[0][:60]}...",
                        impact="high",
                        recommendation="Implement error recovery and fallback mechanisms",
                        estimated_improvement="100% success rate"
                    ))
        
        return recommendations

    def generate_optimization_plan(self) -> Dict[str, Any]:
        """
        Generate comprehensive optimization plan.
        
        Returns:
            Dictionary with optimization recommendations organized by priority
        """
        all_recommendations = []
        all_recommendations.extend(self.analyze_size_growth())
        all_recommendations.extend(self.analyze_execution_time())
        all_recommendations.extend(self.analyze_failures())
        
        # Sort by impact and then by category
        impact_order = {"high": 0, "medium": 1, "low": 2}
        sorted_recs = sorted(all_recommendations, key=lambda x: (impact_order.get(x.impact, 3), x.category))
        
        # Group by impact level
        plan = {
            "high_priority": [r for r in sorted_recs if r.impact == "high"],
            "medium_priority": [r for r in sorted_recs if r.impact == "medium"],
            "low_priority": [r for r in sorted_recs if r.impact == "low"],
            "summary": {
                "total_recommendations": len(sorted_recs),
                "high_priority_count": len([r for r in sorted_recs if r.impact == "high"]),
                "medium_priority_count": len([r for r in sorted_recs if r.impact == "medium"]),
                "low_priority_count": len([r for r in sorted_recs if r.impact == "low"])
            }
        }
        
        return plan

    def print_optimization_plan(self) -> None:
        """Print optimization plan to console."""
        plan = self.generate_optimization_plan()
        
        print("\n" + "="*70)
        print("PERFORMANCE OPTIMIZATION PLAN")
        print("="*70)
        print(f"Total recommendations: {plan['summary']['total_recommendations']}")
        print(f"High priority: {plan['summary']['high_priority_count']}")
        print(f"Medium priority: {plan['summary']['medium_priority_count']}")
        print(f"Low priority: {plan['summary']['low_priority_count']}")
        
        for priority_level in ["high_priority", "medium_priority", "low_priority"]:
            recommendations = plan.get(priority_level, [])
            
            if not recommendations:
                continue
            
            priority_name = priority_level.replace("_", " ").title()
            print(f"\n{priority_name} Recommendations:")
            print("-" * 70)
            
            for i, rec in enumerate(recommendations, 1):
                print(f"\n{i}. [{rec.category}] {rec.issue}")
                print(f"   Impact: {rec.impact.upper()}")
                print(f"   Recommendation: {rec.recommendation}")
                print(f"   Est. Improvement: {rec.estimated_improvement}")

    def export_optimization_plan(self, path: str) -> None:
        """
        Export optimization plan to JSON.
        
        Args:
            path: Output file path
        """
        plan = self.generate_optimization_plan()
        
        # Convert dataclass objects to dicts for JSON serialization
        def convert_to_dict(obj):
            if hasattr(obj, "__dict__"):
                return vars(obj)
            return obj
        
        plan_to_save = {
            "high_priority": [convert_to_dict(r) for r in plan.get("high_priority", [])],
            "medium_priority": [convert_to_dict(r) for r in plan.get("medium_priority", [])],
            "low_priority": [convert_to_dict(r) for r in plan.get("low_priority", [])],
            "summary": plan.get("summary", {})
        }
        
        with open(path, "w") as f:
            json.dump(plan_to_save, f, indent=2)


class CSSOptimizer:
    """Optimize CSS in EPUB files."""

    @staticmethod
    def minify_css(css_content: str) -> str:
        """
        Minify CSS by removing whitespace and comments.
        
        Args:
            css_content: Original CSS
        
        Returns:
            Minified CSS
        """
        import re
        
        # Remove comments
        css = re.sub(r"/\*[^*]*\*+(?:[^/*][^*]*\*+)*/", "", css_content)
        
        # Remove newlines and excess whitespace
        css = re.sub(r"\n", "", css)
        css = re.sub(r"\s+", " ", css)
        
        # Remove spaces around selector and declaration markers
        css = re.sub(r"\s*{\s*", "{", css)
        css = re.sub(r"\s*}\s*", "}", css)
        css = re.sub(r"\s*:\s*", ":", css)
        css = re.sub(r"\s*;\s*", ";", css)
        css = re.sub(r"\s*,\s*", ",", css)
        
        # Remove trailing semicolon before closing brace
        css = re.sub(r";\}", "}", css)
        
        # Remove spaces before opening brace
        css = re.sub(r"\s+{", "{", css)
        
        return css.strip()

    @staticmethod
    def deduplicate_rules(css_content: str) -> str:
        """
        Remove duplicate CSS rules.
        
        Args:
            css_content: CSS content
        
        Returns:
            CSS with duplicates removed
        """
        rules = []
        seen = set()
        
        # Split by closing brace to find rule blocks
        blocks = css_content.split("}")
        
        for block in blocks:
            if "{" not in block:
                continue
            
            # Normalize rule for comparison
            normalized = block.replace("\n", "").replace("  ", " ").strip()
            
            if normalized and normalized not in seen:
                seen.add(normalized)
                rules.append(block + "}")
        
        return "\n".join(rules)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python performance_optimization.py <test_report.json>")
        sys.exit(1)
    
    report_path = sys.argv[1]
    analyzer = PerformanceAnalyzer(report_path)
    analyzer.print_optimization_plan()
    
    # Export to file
    output_path = report_path.replace(".json", "_optimization_plan.json")
    analyzer.export_optimization_plan(output_path)
    print(f"\nOptimization plan saved to: {output_path}")
