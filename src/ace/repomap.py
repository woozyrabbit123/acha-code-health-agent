"""
Symbol Indexer for ACE - Fast AST-based Python symbol extraction.

Provides RepoMap class for building, saving, loading, and querying
a repository's symbol table with zero external dependencies (stdlib only).
"""

import ast
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Optional

from ace.safety import atomic_write


@dataclass
class Symbol:
    """Represents a code symbol (function, class, or module)."""
    name: str
    type: Literal["function", "class", "module"]
    file: str  # Relative path from repo root
    line: int
    deps: list[str] = field(default_factory=list)  # Import dependencies
    mtime: int = 0  # File modification time (unix timestamp)
    size: int = 0   # File size in bytes

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Symbol":
        """Create Symbol from dict."""
        return cls(**d)


class RepoMap:
    """
    Symbol index for a Python repository.

    Builds a fast symbol table using AST parsing, tracks dependencies,
    and provides query capabilities.
    """

    def __init__(self, root: Optional[Path] = None):
        """
        Initialize RepoMap.

        Args:
            root: Repository root path (optional)
        """
        self.root = root
        self.symbols: list[Symbol] = []
        self._symbol_index: dict[str, list[Symbol]] = {}  # name -> symbols

    def build(self, root: Path, exclude_patterns: Optional[list[str]] = None) -> "RepoMap":
        """
        Build symbol index by walking directory and parsing Python files.

        Args:
            root: Repository root path
            exclude_patterns: Patterns to exclude (e.g., ['tests', '__pycache__'])

        Returns:
            Self for chaining
        """
        self.root = root
        self.symbols = []
        self._symbol_index = {}

        if exclude_patterns is None:
            exclude_patterns = ['__pycache__', '.git', '.ace', 'venv', '.venv',
                              'node_modules', '.pytest_cache', '.mypy_cache']

        # Walk directory tree
        py_files = []
        for py_file in root.rglob("*.py"):
            # Check exclusions
            if any(pattern in str(py_file.relative_to(root)) for pattern in exclude_patterns):
                continue
            py_files.append(py_file)

        # Parse each Python file
        for py_file in py_files:
            self._parse_file(py_file, root)

        # Sort symbols for determinism: (file, line)
        self.symbols.sort(key=lambda s: (s.file, s.line))

        # Build index for fast lookups
        self._rebuild_index()

        return self

    def _parse_file(self, file_path: Path, root: Path) -> None:
        """
        Parse a Python file and extract symbols.

        Args:
            file_path: Path to Python file
            root: Repository root for relative paths
        """
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content, filename=str(file_path))

            rel_path = str(file_path.relative_to(root))
            stat = file_path.stat()
            mtime = int(stat.st_mtime)
            size = stat.st_size

            # Extract imports (file-level dependencies)
            deps = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    deps.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        deps.append(node.module)

            # Module symbol
            module_name = rel_path.replace('/', '.').replace('.py', '')
            self.symbols.append(Symbol(
                name=module_name,
                type="module",
                file=rel_path,
                line=1,
                deps=sorted(set(deps)),
                mtime=mtime,
                size=size
            ))

            # Extract functions and classes
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self.symbols.append(Symbol(
                        name=node.name,
                        type="function",
                        file=rel_path,
                        line=node.lineno,
                        deps=sorted(set(deps)),  # Inherit file-level deps
                        mtime=mtime,
                        size=size
                    ))
                elif isinstance(node, ast.ClassDef):
                    self.symbols.append(Symbol(
                        name=node.name,
                        type="class",
                        file=rel_path,
                        line=node.lineno,
                        deps=sorted(set(deps)),
                        mtime=mtime,
                        size=size
                    ))

        except (SyntaxError, UnicodeDecodeError, OSError) as e:
            # Skip files with parse errors
            pass

    def _rebuild_index(self) -> None:
        """Rebuild internal index for fast lookups."""
        self._symbol_index = {}
        for symbol in self.symbols:
            if symbol.name not in self._symbol_index:
                self._symbol_index[symbol.name] = []
            self._symbol_index[symbol.name].append(symbol)

    def save(self, path: Path) -> None:
        """
        Save symbol index to JSON file with deterministic ordering and atomic writes.

        Args:
            path: Output file path (e.g., .ace/symbols.json)
        """
        data = {
            "root": str(self.root) if self.root else None,
            "symbols": [s.to_dict() for s in self.symbols],
            # Timestamp removed for deterministic builds - metadata can be tracked externally
        }

        # Write with sorted keys for determinism and atomic write for durability
        content = json.dumps(data, indent=2, sort_keys=True).encode('utf-8')
        atomic_write(path, content)

    @classmethod
    def load(cls, path: Path) -> "RepoMap":
        """
        Load symbol index from JSON file.

        Args:
            path: Input file path (e.g., .ace/symbols.json)

        Returns:
            RepoMap instance
        """
        with path.open('r', encoding='utf-8') as f:
            data = json.load(f)

        repo_map = cls(root=Path(data["root"]) if data.get("root") else None)
        repo_map.symbols = [Symbol.from_dict(s) for s in data["symbols"]]
        repo_map._rebuild_index()

        return repo_map

    def query(
        self,
        pattern: Optional[str] = None,
        type: Optional[Literal["function", "class", "module"]] = None
    ) -> list[Symbol]:
        """
        Query symbols by pattern and/or type.

        Args:
            pattern: Name pattern (substring match)
            type: Symbol type filter

        Returns:
            List of matching symbols
        """
        results = self.symbols

        if type:
            results = [s for s in results if s.type == type]

        if pattern:
            pattern_lower = pattern.lower()
            results = [s for s in results if pattern_lower in s.name.lower()]

        return results

    def get_by_name(self, name: str) -> list[Symbol]:
        """
        Get symbols by exact name.

        Args:
            name: Symbol name

        Returns:
            List of symbols with matching name
        """
        return self._symbol_index.get(name, [])

    def get_files(self) -> list[str]:
        """Get list of all indexed files."""
        files = sorted(set(s.file for s in self.symbols))
        return files

    def get_file_symbols(self, file: str) -> list[Symbol]:
        """
        Get all symbols from a specific file.

        Args:
            file: Relative file path

        Returns:
            List of symbols in file
        """
        return [s for s in self.symbols if s.file == file]

    def stats(self) -> dict:
        """Get statistics about the symbol index."""
        total = len(self.symbols)
        by_type = {}
        for s in self.symbols:
            by_type[s.type] = by_type.get(s.type, 0) + 1

        return {
            "total_symbols": total,
            "by_type": by_type,
            "total_files": len(self.get_files()),
            "root": str(self.root) if self.root else None
        }
