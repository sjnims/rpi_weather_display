#!/usr/bin/env python3
"""Track code quality metrics over time using radon.

This script collects various code quality metrics and stores them locally
for tracking trends in complexity and maintainability.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pandas as pd
    pandas_available = True
except ImportError:
    pandas_available = False
    pd = None  # type: ignore[assignment]
    print("Warning: pandas not installed. Install with 'pip install pandas' for better reporting.")


class CodeQualityTracker:
    """Track code quality metrics using radon."""

    def __init__(self, project_root: Path) -> None:
        """Initialize the tracker.
        
        Args:
            project_root: Path to the project root directory
        """
        self.project_root = project_root
        self.src_path = project_root / "src"
        self.metrics_dir = project_root / "metrics"
        self.metrics_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for different metric types
        self.history_dir = self.metrics_dir / "history"
        self.history_dir.mkdir(exist_ok=True)
        
        self.reports_dir = self.metrics_dir / "reports"
        self.reports_dir.mkdir(exist_ok=True)

    def run_radon_command(
        self, metric_type: str, extra_args: list[str] | None = None
    ) -> dict[str, Any]:
        """Run a radon command and return JSON output.
        
        Args:
            metric_type: Type of metric (cc, mi, raw, hal)
            extra_args: Additional arguments for the command
            
        Returns:
            Dictionary with the command output
        """
        cmd = ["radon", metric_type, str(self.src_path), "-j"]
        if extra_args:
            cmd.extend(extra_args)
            
        try:
            result = subprocess.run(  # noqa: S603
                cmd, capture_output=True, text=True, check=True
            )  # cmd is constructed from hardcoded values
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"Error running radon {metric_type}: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing radon output: {e}")
            return {}

    def collect_metrics(self) -> dict[str, Any]:
        """Collect all metrics from radon.
        
        Returns:
            Dictionary containing all metrics
        """
        timestamp = datetime.now().isoformat()
        
        print("Collecting Cyclomatic Complexity...")
        cc_data = self.run_radon_command("cc", ["-a", "-nc"])
        
        print("Collecting Maintainability Index...")
        mi_data = self.run_radon_command("mi", [])
        
        print("Collecting Raw metrics...")
        raw_data = self.run_radon_command("raw")
        
        print("Collecting Halstead metrics...")
        hal_data = self.run_radon_command("hal")
        
        return {
            "timestamp": timestamp,
            "cyclomatic_complexity": cc_data,
            "maintainability_index": mi_data,
            "raw_metrics": raw_data,
            "halstead_metrics": hal_data,
        }

    def save_metrics(self, metrics: dict[str, Any]) -> Path:
        """Save metrics to a JSON file.
        
        Args:
            metrics: Metrics data to save
            
        Returns:
            Path to the saved file
        """
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = self.history_dir / f"metrics_{date_str}.json"
        
        with open(filename, "w") as f:
            json.dump(metrics, f, indent=2)
            
        print(f"Metrics saved to: {filename}")
        return filename

    def analyze_complexity(self, cc_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze cyclomatic complexity data.
        
        Args:
            cc_data: Cyclomatic complexity data from radon
            
        Returns:
            Analysis summary
        """
        total_complexity = 0
        total_functions = 0
        complex_functions: list[dict[str, Any]] = []
        
        for file_path, file_data in cc_data.items():
            for item in file_data:
                if item["type"] in ["method", "function"]:
                    total_functions += 1
                    total_complexity += item["complexity"]
                    
                    # Track functions with high complexity (>10)
                    if item["complexity"] > 10:
                        complex_functions.append({
                            "name": f"{file_path}:{item['name']}",
                            "complexity": item["complexity"],
                            "rank": item["rank"]
                        })
        
        avg_complexity = total_complexity / total_functions if total_functions > 0 else 0
        
        return {
            "total_functions": total_functions,
            "total_complexity": total_complexity,
            "average_complexity": round(avg_complexity, 2),
            "complex_functions": sorted(
                complex_functions, key=lambda x: x["complexity"], reverse=True
            )[:10]
        }

    def analyze_maintainability(self, mi_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze maintainability index data.
        
        Args:
            mi_data: Maintainability index data from radon
            
        Returns:
            Analysis summary
        """
        mi_scores: list[float] = []
        low_maintainability: list[dict[str, Any]] = []
        
        for file_path, score in mi_data.items():
            mi_scores.append(score["mi"])
            
            # Track files with low maintainability (<20)
            if score["mi"] < 20:
                low_maintainability.append({
                    "file": file_path,
                    "score": round(score["mi"], 2),
                    "rank": score["rank"]
                })
        
        if mi_scores:
            avg_mi = sum(mi_scores) / len(mi_scores)
            return {
                "average_maintainability": round(avg_mi, 2),
                "total_files": len(mi_scores),
                "low_maintainability_files": sorted(
                    low_maintainability, key=lambda x: x["score"]
                )
            }
        
        return {"average_maintainability": 0, "total_files": 0, "low_maintainability_files": []}

    def analyze_raw_metrics(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze raw metrics data.
        
        Args:
            raw_data: Raw metrics data from radon
            
        Returns:
            Analysis summary
        """
        total_loc = 0
        total_sloc = 0
        total_comments = 0
        total_blank = 0
        
        for _file_path, metrics in raw_data.items():
            total_loc += metrics["loc"]
            total_sloc += metrics["sloc"]
            total_comments += metrics["comments"]
            total_blank += metrics["blank"]
        
        comment_ratio = (total_comments / total_sloc * 100) if total_sloc > 0 else 0
        
        return {
            "total_lines": total_loc,
            "source_lines": total_sloc,
            "comment_lines": total_comments,
            "blank_lines": total_blank,
            "comment_ratio": round(comment_ratio, 2)
        }

    def generate_report(self, metrics: dict[str, Any]) -> str:
        """Generate a markdown report from metrics.
        
        Args:
            metrics: All collected metrics
            
        Returns:
            Markdown formatted report
        """
        cc_analysis = self.analyze_complexity(metrics["cyclomatic_complexity"])
        mi_analysis = self.analyze_maintainability(metrics["maintainability_index"])
        raw_analysis = self.analyze_raw_metrics(metrics["raw_metrics"])
        
        report = f"""# Code Quality Report

Generated: {metrics['timestamp']}

## Summary

### Code Size
- **Total Lines**: {raw_analysis['total_lines']:,}
- **Source Lines**: {raw_analysis['source_lines']:,}
- **Comment Lines**: {raw_analysis['comment_lines']:,}
- **Comment Ratio**: {raw_analysis['comment_ratio']}%

### Complexity
- **Average Cyclomatic Complexity**: {cc_analysis['average_complexity']}
- **Total Functions/Methods**: {cc_analysis['total_functions']}

### Maintainability
- **Average Maintainability Index**: {mi_analysis['average_maintainability']}/100
- **Total Files Analyzed**: {mi_analysis['total_files']}

## Areas of Concern

### High Complexity Functions (CC > 10)
"""
        
        if cc_analysis['complex_functions']:
            for func in cc_analysis['complex_functions']:
                report += f"- `{func['name']}` - CC: {func['complexity']} (Rank: {func['rank']})\n"
        else:
            report += "None found - all functions have acceptable complexity!\n"
            
        report += "\n### Low Maintainability Files (MI < 20)\n"
        
        if mi_analysis['low_maintainability_files']:
            for file in mi_analysis['low_maintainability_files']:
                report += f"- `{file['file']}` - MI: {file['score']} (Rank: {file['rank']})\n"
        else:
            report += "None found - all files have acceptable maintainability!\n"
            
        return report

    def generate_trend_data(self) -> None:
        """Generate trend data from historical metrics."""
        history_files = sorted(self.history_dir.glob("metrics_*.json"))
        
        if not history_files:
            print("No historical data found.")
            return
            
        if not pandas_available or pd is None:
            print("Pandas not available - skipping trend analysis.")
            return
            
        trends: list[dict[str, Any]] = []
        
        for file_path in history_files:
            with open(file_path) as f:
                data = json.load(f)
                
            cc_analysis = self.analyze_complexity(data["cyclomatic_complexity"])
            mi_analysis = self.analyze_maintainability(data["maintainability_index"])
            raw_analysis = self.analyze_raw_metrics(data["raw_metrics"])
            
            trends.append({
                "timestamp": data["timestamp"],
                "avg_complexity": cc_analysis["average_complexity"],
                "avg_maintainability": mi_analysis["average_maintainability"],
                "total_sloc": raw_analysis["source_lines"],
                "comment_ratio": raw_analysis["comment_ratio"]
            })
        
        df = pd.DataFrame(trends)
        df['timestamp'] = pd.to_datetime(df['timestamp'])  # type: ignore[call-overload]
        df = df.sort_values('timestamp')  # type: ignore[call-overload]
        
        # Save as CSV for easy viewing
        csv_path = self.reports_dir / "quality_trends.csv"
        df.to_csv(csv_path, index=False)  # type: ignore[call-overload]
        print(f"Trend data saved to: {csv_path}")
        
        # Print recent trend
        if len(df) > 1:
            latest = df.iloc[-1]  # type: ignore[no-any-return]
            previous = df.iloc[-2]  # type: ignore[no-any-return]
            
            print("\n## Trend Analysis (vs previous run)")
            # Type checking is difficult with pandas DataFrames
            cc_delta = float(latest['avg_complexity'] - previous['avg_complexity'])  # type: ignore[arg-type]
            mi_delta = float(latest['avg_maintainability'] - previous['avg_maintainability'])  # type: ignore[arg-type]
            sloc_delta = int(latest['total_sloc'] - previous['total_sloc'])  # type: ignore[arg-type]
            comment_delta = float(latest['comment_ratio'] - previous['comment_ratio'])  # type: ignore[arg-type]
            
            print(f"- Complexity: {latest['avg_complexity']:.2f} ({cc_delta:+.2f})")
            print(f"- Maintainability: {latest['avg_maintainability']:.2f} ({mi_delta:+.2f})")
            print(f"- Source Lines: {latest['total_sloc']:,} ({sloc_delta:+,})")
            print(f"- Comment Ratio: {latest['comment_ratio']:.1f}% ({comment_delta:+.1f}%)")

    def run(self) -> None:
        """Run the complete tracking process."""
        print("=== Code Quality Tracker ===\n")
        
        # Check if radon is installed
        try:
            subprocess.run(  # noqa: S603
                ["radon", "--version"], capture_output=True, check=True  # noqa: S607
            )  # checking for radon installation
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Error: radon is not installed.")
            print("Install with: pip install radon")
            sys.exit(1)
        
        # Collect metrics
        metrics = self.collect_metrics()
        
        # Save metrics
        self.save_metrics(metrics)
        
        # Generate report
        report = self.generate_report(metrics)
        report_path = self.reports_dir / "latest_report.md"
        with open(report_path, "w") as f:
            f.write(report)
        
        print(f"\nReport saved to: {report_path}")
        print("\n" + "=" * 50)
        print(report)
        
        # Generate trends if we have historical data
        print("\n" + "=" * 50)
        self.generate_trend_data()


def main() -> None:
    """Main entry point."""
    project_root = Path(__file__).parent.parent
    tracker = CodeQualityTracker(project_root)
    tracker.run()


if __name__ == "__main__":
    main()  # pragma: no cover