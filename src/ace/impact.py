"""
Impact Analyzer for ACE - Predict affected files from changes.

Analyzes dependency graph to predict which files will be impacted
by changes to a given set of files.
"""

from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

from ace.depgraph import DepGraph
from ace.repomap import RepoMap


@dataclass
class ImpactReport:
    """Report of files impacted by changes."""
    changed_files: list[str]
    impacted_files: list[str]
    impact_by_depth: dict[int, list[str]] = field(default_factory=dict)
    total_impact: int = 0
    explanations: dict[str, str] = field(default_factory=dict)


class ImpactAnalyzer:
    """
    Analyzes impact of file changes using dependency graph.

    Predicts which files will be affected by changes to a given
    set of files, with configurable depth limits.
    """

    def __init__(self, depgraph: DepGraph):
        """
        Initialize impact analyzer.

        Args:
            depgraph: Dependency graph
        """
        self.depgraph = depgraph
        self.repo_map = depgraph.repo_map

    def predict_impacted(
        self,
        files_changed: list[str],
        depth: int = 2,
        include_dependencies: bool = True
    ) -> ImpactReport:
        """
        Predict files impacted by changes.

        Args:
            files_changed: List of changed file paths
            depth: Maximum dependency depth to traverse (2 = direct dependents + their dependents)
            include_dependencies: If True, also include files that changed files depend on

        Returns:
            ImpactReport with affected files
        """
        impacted = set()
        impact_by_depth = defaultdict(list)
        explanations = {}

        # For each changed file, find its dependents
        for file in files_changed:
            # Get files that depend on this file (reverse dependencies)
            self._traverse_dependents(
                file,
                depth=depth,
                impacted=impacted,
                impact_by_depth=impact_by_depth,
                explanations=explanations,
                current_depth=0
            )

            # Optionally include forward dependencies
            if include_dependencies:
                deps = self.depgraph.depends_on(file, depth=depth)
                for dep in deps:
                    if dep not in impacted and dep not in files_changed:
                        impacted.add(dep)
                        depth_level = self._calculate_depth(file, dep)
                        impact_by_depth[depth_level].append(dep)
                        explanations[dep] = f"Dependency of {file}"

        # Sort results
        impacted_list = sorted(impacted)

        # Sort impact by depth
        sorted_impact_by_depth = {
            d: sorted(files)
            for d, files in sorted(impact_by_depth.items())
        }

        return ImpactReport(
            changed_files=files_changed,
            impacted_files=impacted_list,
            impact_by_depth=sorted_impact_by_depth,
            total_impact=len(impacted_list),
            explanations=explanations
        )

    def _traverse_dependents(
        self,
        file: str,
        depth: int,
        impacted: set[str],
        impact_by_depth: dict[int, list[str]],
        explanations: dict[str, str],
        current_depth: int,
        visited: Optional[set[str]] = None
    ) -> None:
        """
        Recursively traverse dependents up to max depth.

        Args:
            file: Current file
            depth: Maximum depth
            impacted: Set of impacted files (accumulated)
            impact_by_depth: Files grouped by depth level
            explanations: Explanation for each impacted file
            current_depth: Current traversal depth
            visited: Set of visited files to avoid cycles
        """
        if visited is None:
            visited = set()

        if current_depth > depth:
            return

        if file in visited:
            return

        visited.add(file)

        # Get files that directly depend on this file
        dependents = self.depgraph.who_depends_on(file)

        for dependent in dependents:
            if dependent not in impacted:
                impacted.add(dependent)
                impact_by_depth[current_depth + 1].append(dependent)
                explanations[dependent] = f"Depends on {file} (depth {current_depth + 1})"

            # Recursively traverse this dependent's dependents
            if current_depth + 1 < depth:
                self._traverse_dependents(
                    dependent,
                    depth=depth,
                    impacted=impacted,
                    impact_by_depth=impact_by_depth,
                    explanations=explanations,
                    current_depth=current_depth + 1,
                    visited=visited
                )

    def _calculate_depth(self, source: str, target: str) -> int:
        """
        Calculate dependency depth between two files.

        Args:
            source: Source file
            target: Target file

        Returns:
            Depth (number of hops)
        """
        # BFS to find shortest path
        from collections import deque

        if source == target:
            return 0

        visited = {source}
        queue = deque([(source, 0)])

        while queue:
            current, depth = queue.popleft()

            # Check dependencies
            deps = self.depgraph.get_file_imports(current)
            if target in deps:
                return depth + 1

            for dep in deps:
                if dep not in visited:
                    visited.add(dep)
                    queue.append((dep, depth + 1))

        return -1  # No path found

    def explain_impact(self, file: str) -> dict:
        """
        Explain the impact of changing a specific file.

        Args:
            file: File path

        Returns:
            Dictionary with impact explanation
        """
        # Get direct dependents
        direct_dependents = self.depgraph.who_depends_on(file)

        # Get files this depends on
        dependencies = self.depgraph.get_file_imports(file)

        # Get symbols in this file
        symbols = self.repo_map.get_file_symbols(file)
        symbol_names = [s.name for s in symbols if s.type in ["function", "class"]]

        # Predict full impact
        report = self.predict_impacted([file], depth=2)

        return {
            "file": file,
            "direct_dependents": sorted(direct_dependents),
            "direct_dependencies": sorted(dependencies),
            "exported_symbols": symbol_names,
            "total_impacted": report.total_impact,
            "impacted_by_depth": report.impact_by_depth,
            "risk_level": self._assess_risk(report.total_impact, len(direct_dependents))
        }

    def _assess_risk(self, total_impact: int, direct_dependents: int) -> str:
        """
        Assess risk level based on impact metrics.

        Args:
            total_impact: Total number of impacted files
            direct_dependents: Number of direct dependents

        Returns:
            Risk level: "low", "medium", "high", or "critical"
        """
        if total_impact == 0 and direct_dependents == 0:
            return "low"
        elif total_impact <= 3 and direct_dependents <= 2:
            return "low"
        elif total_impact <= 10 and direct_dependents <= 5:
            return "medium"
        elif total_impact <= 20 and direct_dependents <= 10:
            return "high"
        else:
            return "critical"

    def get_blast_radius(self, files: list[str], depth: int = 3) -> dict:
        """
        Calculate "blast radius" - comprehensive impact assessment.

        Args:
            files: List of changed files
            depth: Analysis depth

        Returns:
            Comprehensive impact metrics
        """
        report = self.predict_impacted(files, depth=depth)

        # Calculate additional metrics
        unique_depths = set(report.impact_by_depth.keys())
        max_depth_reached = max(unique_depths) if unique_depths else 0

        # Find critical files (most impacted)
        impact_counts = defaultdict(int)
        for file in files:
            for impacted_file in report.impacted_files:
                impact_counts[impacted_file] += 1

        critical_files = sorted(
            impact_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return {
            "changed_files": files,
            "total_impacted": report.total_impact,
            "max_depth_reached": max_depth_reached,
            "impact_by_depth": report.impact_by_depth,
            "critical_files": [{"file": f, "impact_count": c} for f, c in critical_files],
            "overall_risk": self._assess_risk(report.total_impact, len(files))
        }

    def compare_changes(self, changes_a: list[str], changes_b: list[str], depth: int = 2) -> dict:
        """
        Compare impact of two different change sets.

        Args:
            changes_a: First set of changed files
            changes_b: Second set of changed files
            depth: Analysis depth

        Returns:
            Comparison metrics
        """
        report_a = self.predict_impacted(changes_a, depth=depth)
        report_b = self.predict_impacted(changes_b, depth=depth)

        impacted_a = set(report_a.impacted_files)
        impacted_b = set(report_b.impacted_files)

        overlap = impacted_a & impacted_b
        only_a = impacted_a - impacted_b
        only_b = impacted_b - impacted_a

        return {
            "changes_a": changes_a,
            "changes_b": changes_b,
            "impact_a": len(impacted_a),
            "impact_b": len(impacted_b),
            "overlap": sorted(overlap),
            "only_a": sorted(only_a),
            "only_b": sorted(only_b),
            "similarity": len(overlap) / max(len(impacted_a | impacted_b), 1)
        }

    def find_bottlenecks(self, top_n: int = 10) -> list[dict]:
        """
        Find bottleneck files (most depended upon).

        Args:
            top_n: Number of top bottlenecks to return

        Returns:
            List of bottleneck files with metrics
        """
        bottlenecks = []

        for file in self.repo_map.get_files():
            dependents = self.depgraph.who_depends_on(file)
            if dependents:
                impact = self.predict_impacted([file], depth=1)
                bottlenecks.append({
                    "file": file,
                    "direct_dependents": len(dependents),
                    "total_impact": impact.total_impact,
                    "risk_level": self._assess_risk(impact.total_impact, len(dependents))
                })

        # Sort by total impact descending
        bottlenecks.sort(key=lambda x: x["total_impact"], reverse=True)

        return bottlenecks[:top_n]
