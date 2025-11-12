"""
Context Ranking for ACE - Score and rank files for relevance.

Ranks files based on:
- Symbol density (functions + classes per KLOC)
- Recency boost (recently modified files score higher)
- Query relevance (symbol/file name matching)
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import time
import re

from ace.repomap import RepoMap, Symbol


@dataclass
class FileScore:
    """Represents a scored file for ranking."""
    file: str
    score: float
    symbol_density: float
    recency_boost: float
    relevance_score: float
    symbol_count: int
    loc: int


class ContextRanker:
    """
    Context ranking engine for code files.

    Scores files based on multiple signals to prioritize most relevant
    files for analysis or context loading.
    """

    def __init__(self, repo_map: RepoMap, current_time: Optional[int] = None):
        """
        Initialize context ranker.

        Args:
            repo_map: RepoMap instance with symbols
            current_time: Fixed timestamp for deterministic ranking (defaults to current time)
        """
        self.repo_map = repo_map
        self._file_cache: dict[str, FileScore] = {}
        # Store timestamp for deterministic ranking; use current time if not provided
        self._current_time = current_time if current_time is not None else int(time.time())

    def rank_files(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        recency_weight: float = 1.0,
        density_weight: float = 1.0,
        relevance_weight: float = 2.0
    ) -> list[FileScore]:
        """
        Rank files by relevance score.

        Args:
            query: Optional search query for relevance filtering
            limit: Maximum number of results
            recency_weight: Weight for recency boost
            density_weight: Weight for symbol density
            relevance_weight: Weight for query relevance

        Returns:
            List of FileScore objects, sorted by descending score
        """
        scores = []

        # Get all files
        files = self.repo_map.get_files()

        for file in files:
            file_score = self._score_file(
                file,
                query=query,
                recency_weight=recency_weight,
                density_weight=density_weight,
                relevance_weight=relevance_weight
            )
            if file_score:
                scores.append(file_score)

        # Sort by score descending, then by file path for determinism
        # This ensures ties are broken consistently
        scores.sort(key=lambda x: (-x.score, x.file))

        return scores[:limit]

    def _score_file(
        self,
        file: str,
        query: Optional[str] = None,
        recency_weight: float = 1.0,
        density_weight: float = 1.0,
        relevance_weight: float = 2.0
    ) -> Optional[FileScore]:
        """
        Calculate score for a single file.

        Args:
            file: File path
            query: Optional search query
            recency_weight: Weight for recency
            density_weight: Weight for density
            relevance_weight: Weight for relevance

        Returns:
            FileScore or None if file should be filtered
        """
        # Get file symbols
        symbols = self.repo_map.get_file_symbols(file)
        if not symbols:
            return None

        # Calculate components
        symbol_density = self._calculate_symbol_density(symbols)
        recency_boost = self._calculate_recency_boost(symbols)
        relevance_score = self._calculate_relevance(file, symbols, query) if query else 1.0

        # If query is provided and relevance is 0, filter out
        if query and relevance_score == 0:
            return None

        # Combine scores
        score = (
            density_weight * symbol_density +
            recency_weight * recency_boost +
            relevance_weight * relevance_score
        )

        # Count non-module symbols
        symbol_count = sum(1 for s in symbols if s.type in ["function", "class"])

        # Estimate LOC (use file size as proxy: ~50 bytes per line average)
        avg_size = sum(s.size for s in symbols) / len(symbols) if symbols else 0
        loc = int(avg_size / 50) if avg_size > 0 else 1

        return FileScore(
            file=file,
            score=score,
            symbol_density=symbol_density,
            recency_boost=recency_boost,
            relevance_score=relevance_score,
            symbol_count=symbol_count,
            loc=loc
        )

    def _calculate_symbol_density(self, symbols: list[Symbol]) -> float:
        """
        Calculate symbol density (functions + classes per KLOC).

        Args:
            symbols: List of symbols in file

        Returns:
            Symbol density score
        """
        # Count functions and classes
        symbol_count = sum(1 for s in symbols if s.type in ["function", "class"])

        if symbol_count == 0:
            return 0.0

        # Estimate LOC from file size (average ~50 bytes per line)
        avg_size = sum(s.size for s in symbols) / len(symbols) if symbols else 0
        kloc = (avg_size / 50) / 1000 if avg_size > 0 else 0.001

        # Density = symbols per KLOC
        density = symbol_count / kloc if kloc > 0 else symbol_count

        # Normalize to 0-1 range (cap at 100 symbols/KLOC as "max density")
        normalized = min(density / 100, 1.0)

        return normalized

    def _calculate_recency_boost(self, symbols: list[Symbol]) -> float:
        """
        Calculate recency boost based on file modification time.

        Formula: 1.0 + min(0.5, days_since_mtime^{-1} * 7)

        Args:
            symbols: List of symbols in file

        Returns:
            Recency boost (1.0 to 1.5)
        """
        if not symbols:
            return 1.0

        # Get most recent mtime
        max_mtime = max(s.mtime for s in symbols)
        # Use stored timestamp for deterministic ranking
        current_time = self._current_time

        # Calculate days since modification
        seconds_since = max(current_time - max_mtime, 1)
        days_since = seconds_since / 86400  # 86400 seconds in a day

        # Apply formula: 1.0 + min(0.5, 1/days * 7)
        boost = 1.0 + min(0.5, 7.0 / days_since)

        return boost

    def _calculate_relevance(
        self,
        file: str,
        symbols: list[Symbol],
        query: Optional[str]
    ) -> float:
        """
        Calculate relevance score based on query match.

        Args:
            file: File path
            symbols: List of symbols in file
            query: Search query

        Returns:
            Relevance score (0.0 to 1.0)
        """
        if not query:
            return 1.0

        query_lower = query.lower()
        score = 0.0

        # File path match (weight: 0.3)
        if query_lower in file.lower():
            score += 0.3

        # Symbol name matches
        symbol_matches = 0
        for symbol in symbols:
            if query_lower in symbol.name.lower():
                symbol_matches += 1

        # Symbol match score (weight: 0.7)
        if symbol_matches > 0:
            # Normalize by number of symbols (cap at 10 matches)
            symbol_score = min(symbol_matches / 10, 1.0) * 0.7
            score += symbol_score

        return min(score, 1.0)

    def get_related_files(
        self,
        file: str,
        limit: int = 10
    ) -> list[FileScore]:
        """
        Find files related to a given file.

        Uses symbol similarity and shared dependencies.

        Args:
            file: Source file path
            limit: Maximum results

        Returns:
            List of related files with scores
        """
        source_symbols = self.repo_map.get_file_symbols(file)
        if not source_symbols:
            return []

        # Extract symbol names and dependencies
        source_symbol_names = set(s.name for s in source_symbols)
        source_deps = set()
        for s in source_symbols:
            source_deps.update(s.deps)

        # Score all other files
        scores = []
        for other_file in self.repo_map.get_files():
            if other_file == file:
                continue

            other_symbols = self.repo_map.get_file_symbols(other_file)
            if not other_symbols:
                continue

            # Calculate similarity
            other_symbol_names = set(s.name for s in other_symbols)
            other_deps = set()
            for s in other_symbols:
                other_deps.update(s.deps)

            # Symbol name overlap
            symbol_overlap = len(source_symbol_names & other_symbol_names)

            # Dependency overlap
            dep_overlap = len(source_deps & other_deps)

            # Combined score
            similarity = symbol_overlap * 0.7 + dep_overlap * 0.3

            if similarity > 0:
                # Create FileScore with similarity as score
                file_score = FileScore(
                    file=other_file,
                    score=similarity,
                    symbol_density=self._calculate_symbol_density(other_symbols),
                    recency_boost=self._calculate_recency_boost(other_symbols),
                    relevance_score=similarity,
                    symbol_count=sum(1 for s in other_symbols if s.type in ["function", "class"]),
                    loc=int(sum(s.size for s in other_symbols) / 50) if other_symbols else 1
                )
                scores.append(file_score)

        # Sort by similarity descending, then by file path for determinism
        scores.sort(key=lambda x: (-x.score, x.file))

        return scores[:limit]

    def get_hot_files(self, limit: int = 10, days: int = 7) -> list[FileScore]:
        """
        Get recently modified files (hot files).

        Args:
            limit: Maximum results
            days: Consider files modified within this many days

        Returns:
            List of recently modified files with scores
        """
        current_time = int(time.time())
        cutoff_time = current_time - (days * 86400)

        scores = []
        for file in self.repo_map.get_files():
            symbols = self.repo_map.get_file_symbols(file)
            if not symbols:
                continue

            max_mtime = max(s.mtime for s in symbols)
            if max_mtime >= cutoff_time:
                file_score = self._score_file(
                    file,
                    query=None,
                    recency_weight=2.0,  # Emphasize recency
                    density_weight=0.5,
                    relevance_weight=0.0
                )
                if file_score:
                    scores.append(file_score)

        # Sort by score descending, then by file path for determinism
        scores.sort(key=lambda x: (-x.score, x.file))
        return scores[:limit]
