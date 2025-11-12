"""
Dependency Graph for ACE - Lightweight file and symbol dependency analysis.

Builds a dependency graph from RepoMap, supporting:
- File-to-file edges via imports
- Symbol-level call analysis
- Transitive dependency resolution
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from collections import defaultdict, deque

from ace.repomap import RepoMap, Symbol


@dataclass
class DependencyEdge:
    """Represents a dependency edge between two files or symbols."""
    source: str
    target: str
    type: str = "import"  # "import", "call", or "inherit"


class DepGraph:
    """
    Dependency graph built from RepoMap.

    Tracks file-to-file dependencies via imports and provides
    transitive dependency resolution and reverse lookup.
    """

    def __init__(self, repo_map: RepoMap):
        """
        Initialize dependency graph from RepoMap.

        Args:
            repo_map: RepoMap instance with symbols
        """
        self.repo_map = repo_map
        self.edges: list[DependencyEdge] = []
        self._file_deps: dict[str, set[str]] = defaultdict(set)  # file -> files it imports
        self._file_reverse_deps: dict[str, set[str]] = defaultdict(set)  # file -> files that import it
        self._symbol_index: dict[str, list[Symbol]] = {}  # symbol name -> symbols

        self._build_graph()

    def _build_graph(self) -> None:
        """Build dependency graph from RepoMap symbols."""
        # Index symbols by name for fast lookup
        for symbol in self.repo_map.symbols:
            if symbol.name not in self._symbol_index:
                self._symbol_index[symbol.name] = []
            self._symbol_index[symbol.name].append(symbol)

        # Build file-to-file dependencies from imports
        for symbol in self.repo_map.symbols:
            if symbol.type == "module":
                # Module symbols have file-level imports
                for dep in symbol.deps:
                    # Try to resolve import to a file in the repo
                    target_files = self._resolve_import(dep)
                    for target_file in target_files:
                        if target_file != symbol.file:
                            self._file_deps[symbol.file].add(target_file)
                            self._file_reverse_deps[target_file].add(symbol.file)
                            self.edges.append(DependencyEdge(
                                source=symbol.file,
                                target=target_file,
                                type="import"
                            ))

    def _resolve_import(self, import_name: str) -> list[str]:
        """
        Resolve an import name to file paths in the repository.

        Args:
            import_name: Import name (e.g., 'ace.kernel')

        Returns:
            List of matching file paths
        """
        # Convert import to possible file paths
        # ace.kernel -> ace/kernel.py
        possible_path = import_name.replace('.', '/') + '.py'

        # Check if this file exists in our index
        matching_files = []
        for symbol in self.repo_map.symbols:
            if symbol.type == "module":
                if symbol.file == possible_path:
                    matching_files.append(symbol.file)
                # Also check for package imports (ace -> ace/__init__.py)
                elif symbol.file == import_name.replace('.', '/') + '/__init__.py':
                    matching_files.append(symbol.file)

        return matching_files

    def depends_on(self, file: str, depth: int = -1) -> list[str]:
        """
        Get transitive dependencies of a file.

        Args:
            file: Source file path (relative)
            depth: Maximum depth (-1 for unlimited)

        Returns:
            List of file paths that the given file depends on
        """
        if file not in self._file_deps:
            return []

        visited = set()
        queue = deque([(file, 0)])
        result = []

        while queue:
            current, current_depth = queue.popleft()

            if current in visited:
                continue
            visited.add(current)

            if current != file:
                result.append(current)

            # Stop if we've reached max depth
            if depth != -1 and current_depth >= depth:
                continue

            # Add dependencies to queue
            for dep in self._file_deps.get(current, []):
                if dep not in visited:
                    queue.append((dep, current_depth + 1))

        return sorted(result)

    def who_calls(self, symbol: str) -> list[str]:
        """
        Find files that might call a given symbol.

        This performs a name-based match across all files that import
        the file containing the symbol or have it in their dependency tree.

        Args:
            symbol: Symbol name (function, class, or module)

        Returns:
            List of file paths that likely use this symbol
        """
        # Find files where this symbol is defined
        symbol_files = set()
        for sym in self._symbol_index.get(symbol, []):
            symbol_files.add(sym.file)

        if not symbol_files:
            return []

        # Find files that depend on any of these files
        callers = set()
        for sym_file in symbol_files:
            # Direct reverse dependencies
            callers.update(self._file_reverse_deps.get(sym_file, []))

        return sorted(callers)

    def who_depends_on(self, file: str) -> list[str]:
        """
        Get files that directly depend on the given file.

        Args:
            file: Target file path (relative)

        Returns:
            List of file paths that import this file
        """
        return sorted(self._file_reverse_deps.get(file, []))

    def get_file_imports(self, file: str) -> list[str]:
        """
        Get direct imports of a file.

        Args:
            file: Source file path (relative)

        Returns:
            List of directly imported files
        """
        return sorted(self._file_deps.get(file, []))

    def find_cycles(self) -> list[list[str]]:
        """
        Find circular dependencies in the graph.

        Returns:
            List of cycles, where each cycle is a list of file paths
        """
        cycles = []
        visited = set()

        def dfs(node: str, path: list[str], in_path: set[str]) -> None:
            if node in in_path:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:]
                if cycle not in cycles:
                    cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            in_path.add(node)
            path.append(node)

            for dep in self._file_deps.get(node, []):
                dfs(dep, path.copy(), in_path.copy())

            path.pop()
            in_path.remove(node)

        for file in self._file_deps.keys():
            if file not in visited:
                dfs(file, [], set())

        return cycles

    def get_subgraph(self, files: list[str], include_deps: bool = True) -> "DepGraph":
        """
        Extract a subgraph containing only specified files.

        Args:
            files: List of file paths to include
            include_deps: Whether to include their dependencies

        Returns:
            New DepGraph containing only the subgraph
        """
        # Create filtered RepoMap
        files_set = set(files)
        if include_deps:
            # Add all transitive dependencies
            for file in files:
                files_set.update(self.depends_on(file))

        filtered_symbols = [s for s in self.repo_map.symbols if s.file in files_set]

        # Create new RepoMap with filtered symbols
        new_repo_map = RepoMap(root=self.repo_map.root)
        new_repo_map.symbols = filtered_symbols
        new_repo_map._rebuild_index()

        # Build new graph
        return DepGraph(new_repo_map)

    def stats(self) -> dict:
        """Get statistics about the dependency graph."""
        total_files = len(set(self._file_deps.keys()) | set(self._file_reverse_deps.keys()))
        total_edges = len(self.edges)

        # Calculate average degree
        out_degrees = [len(deps) for deps in self._file_deps.values()]
        avg_out_degree = sum(out_degrees) / len(out_degrees) if out_degrees else 0

        # Find files with most dependencies (outbound)
        top_importers = sorted(
            [(f, len(deps)) for f, deps in self._file_deps.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Find files with most dependents (inbound)
        top_imported = sorted(
            [(f, len(deps)) for f, deps in self._file_reverse_deps.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        return {
            "total_files": total_files,
            "total_edges": total_edges,
            "avg_out_degree": round(avg_out_degree, 2),
            "top_importers": [{"file": f, "imports": n} for f, n in top_importers],
            "top_imported": [{"file": f, "dependents": n} for f, n in top_imported],
            "cycles": len(self.find_cycles())
        }
