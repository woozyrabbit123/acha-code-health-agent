"""AST caching for improved performance"""

import ast
import hashlib
import pickle
from pathlib import Path


class ASTCache:
    """LRU cache for parsed AST trees with file mtime checking"""

    def __init__(self, cache_dir: Path = Path(".acha_cache"), max_size: int = 1000):
        """
        Initialize AST cache.

        Args:
            cache_dir: Directory to store cached AST trees
            max_size: Maximum number of entries in cache
        """
        self.cache_dir = cache_dir
        self.max_size = max_size
        self.enabled = True

        # In-memory cache: file_path -> (tree, mtime, access_count)
        self._memory_cache: dict[str, tuple[ast.AST, float, int]] = {}

        # Initialize cache directory
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_key(self, file_path: Path) -> str:
        """Generate cache key from file path"""
        # Use hash of absolute path to create unique filename
        abs_path = str(file_path.absolute())
        return hashlib.md5(abs_path.encode()).hexdigest()

    def _get_cache_file(self, file_path: Path) -> Path:
        """Get cache file path for a source file"""
        cache_key = self._get_cache_key(file_path)
        return self.cache_dir / f"{cache_key}.ast"

    def _get_file_mtime(self, file_path: Path) -> float:
        """Get file modification time"""
        try:
            return file_path.stat().st_mtime
        except Exception:
            return 0.0

    def get_ast(self, file_path: Path) -> ast.AST | None:
        """
        Return cached AST if file unchanged.

        Args:
            file_path: Source file path

        Returns:
            Cached AST tree or None if not cached or outdated
        """
        if not self.enabled:
            return None

        file_str = str(file_path.absolute())
        current_mtime = self._get_file_mtime(file_path)

        # Check memory cache first
        if file_str in self._memory_cache:
            tree, cached_mtime, access_count = self._memory_cache[file_str]
            if current_mtime == cached_mtime:
                # Update access count
                self._memory_cache[file_str] = (tree, cached_mtime, access_count + 1)
                return tree
            else:
                # File modified, invalidate
                del self._memory_cache[file_str]

        # Check disk cache
        cache_file = self._get_cache_file(file_path)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "rb") as f:
                cached_data = pickle.load(f)
                cached_mtime = cached_data.get("mtime", 0.0)

                # Check if file was modified
                if current_mtime != cached_mtime:
                    # File changed, invalidate cache
                    cache_file.unlink()
                    return None

                tree = cached_data.get("tree")

                # Store in memory cache
                self._memory_cache[file_str] = (tree, cached_mtime, 1)
                self._evict_if_needed()

                return tree
        except Exception:
            # Cache corrupted or error reading
            if cache_file.exists():
                cache_file.unlink()
            return None

    def put_ast(self, file_path: Path, tree: ast.AST):
        """
        Cache AST with file mtime.

        Args:
            file_path: Source file path
            tree: Parsed AST tree
        """
        if not self.enabled:
            return

        file_str = str(file_path.absolute())
        mtime = self._get_file_mtime(file_path)

        # Store in memory cache
        self._memory_cache[file_str] = (tree, mtime, 1)
        self._evict_if_needed()

        # Store on disk
        cache_file = self._get_cache_file(file_path)
        try:
            cached_data = {"tree": tree, "mtime": mtime, "file_path": str(file_path)}
            with open(cache_file, "wb") as f:
                pickle.dump(cached_data, f)
        except Exception:
            # Failed to write cache, continue without caching
            pass

    def _evict_if_needed(self):
        """Evict least recently used entries if cache is full"""
        if len(self._memory_cache) <= self.max_size:
            return

        # Sort by access count (LRU)
        sorted_entries = sorted(self._memory_cache.items(), key=lambda x: x[1][2])  # access_count

        # Remove 10% of least used entries
        to_remove = max(1, len(sorted_entries) // 10)
        for file_str, _ in sorted_entries[:to_remove]:
            del self._memory_cache[file_str]

    def invalidate(self, file_path: Path):
        """
        Remove from cache.

        Args:
            file_path: Source file path to invalidate
        """
        file_str = str(file_path.absolute())

        # Remove from memory cache
        if file_str in self._memory_cache:
            del self._memory_cache[file_str]

        # Remove from disk cache
        cache_file = self._get_cache_file(file_path)
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception:
                pass

    def clear(self):
        """Clear entire cache"""
        # Clear memory cache
        self._memory_cache.clear()

        # Clear disk cache
        if self.cache_dir.exists():
            try:
                for cache_file in self.cache_dir.glob("*.ast"):
                    cache_file.unlink()
            except Exception:
                pass

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics"""
        disk_count = len(list(self.cache_dir.glob("*.ast"))) if self.cache_dir.exists() else 0
        return {
            "memory_entries": len(self._memory_cache),
            "disk_entries": disk_count,
            "max_size": self.max_size,
        }
