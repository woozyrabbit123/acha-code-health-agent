"""Optional LLM assist for ACE - strictly optional with budgets and caching.

Provides utilities for:
- suggest_name(code): Suggest a better name for a function/variable
- docstring_one_liner(sig): Generate a one-line docstring
- summarize_diff(diff): Summarize a diff for commit messages

Budget: Max 4 calls/run, 100 tokens each. Falls back to heuristics if unavailable.
Cache: .ace/llm_cache.json by content fingerprint.
"""

import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LLMResponse:
    """Response from LLM provider."""

    text: str
    cached: bool = False
    provider: str = "null"


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, prompt: str, max_tokens: int = 100) -> str:
        """
        Complete a prompt.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        pass


class NullProvider(LLMProvider):
    """Null provider that returns heuristic fallbacks (no network calls)."""

    def complete(self, prompt: str, max_tokens: int = 100) -> str:
        """Return empty string (no completion)."""
        return ""


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM (optional)."""

    def __init__(self, host: str = "http://localhost:11434", model: str = "tinyllama"):
        self.host = host
        self.model = model

    def complete(self, prompt: str, max_tokens: int = 100) -> str:
        """
        Complete prompt using Ollama.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text
        """
        try:
            import requests

            response = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "options": {"num_predict": max_tokens}},
                timeout=10,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                return ""

        except Exception:
            # Fallback to empty if Ollama unavailable
            return ""


class LLMCache:
    """Cache for LLM completions."""

    def __init__(self, cache_path: Path = Path(".ace/llm_cache.json")):
        self.cache_path = cache_path
        self.cache: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        """Load cache from disk."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.cache = {}

    def save(self) -> None:
        """Save cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, sort_keys=True)
            f.write("\n")

    def get(self, key: str) -> str | None:
        """Get cached completion."""
        return self.cache.get(key)

    def set(self, key: str, value: str) -> None:
        """Set cached completion."""
        self.cache[key] = value
        self.save()

    @staticmethod
    def fingerprint(prompt: str) -> str:
        """Compute fingerprint for prompt."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


class LLMAssist:
    """
    LLM assist with budgets and caching.

    Budget: Max 4 calls/run, 100 tokens each.
    Falls back to heuristics if provider unavailable.
    """

    def __init__(self, provider: LLMProvider | None = None, cache: LLMCache | None = None):
        self.provider = provider or self._detect_provider()
        self.cache = cache or LLMCache()
        self.call_count = 0
        self.max_calls = 4

    @staticmethod
    def _detect_provider() -> LLMProvider:
        """Detect available LLM provider."""
        # Check for OLLAMA_HOST environment variable
        ollama_host = os.environ.get("OLLAMA_HOST")
        if ollama_host:
            return OllamaProvider(host=ollama_host)

        # Default to null provider (heuristics only)
        return NullProvider()

    def _call_with_budget(self, prompt: str, max_tokens: int = 100) -> LLMResponse:
        """
        Call LLM with budget enforcement and caching.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens

        Returns:
            LLMResponse with text, cached flag, and provider name
        """
        # Check cache first
        fingerprint = LLMCache.fingerprint(prompt)
        cached_result = self.cache.get(fingerprint)
        if cached_result:
            return LLMResponse(text=cached_result, cached=True, provider=type(self.provider).__name__)

        # Check budget
        if self.call_count >= self.max_calls:
            # Budget exceeded, return empty
            return LLMResponse(text="", cached=False, provider="budget-exceeded")

        # Make call
        self.call_count += 1
        result = self.provider.complete(prompt, max_tokens=max_tokens)

        # Cache result
        if result:
            self.cache.set(fingerprint, result)

        return LLMResponse(text=result, cached=False, provider=type(self.provider).__name__)

    def suggest_name(self, code: str, current_name: str = "") -> str:
        """
        Suggest a better name for a function or variable.

        Args:
            code: Code snippet containing the entity
            current_name: Current name (optional)

        Returns:
            Suggested name, or empty string if unavailable
        """
        prompt = f"Suggest a better name for this code:\n\n{code}\n\nCurrent name: {current_name}\nSuggested name:"

        response = self._call_with_budget(prompt, max_tokens=20)

        if response.text:
            # Extract first word from response
            suggested = response.text.split()[0] if response.text.split() else ""
            # Clean up (remove quotes, etc.)
            suggested = suggested.strip("\"'`")
            return suggested

        # Heuristic fallback: return empty (caller can use their own fallback)
        return ""

    def docstring_one_liner(self, signature: str) -> str:
        """
        Generate a one-line docstring for a function.

        Args:
            signature: Function signature

        Returns:
            One-line docstring, or heuristic if unavailable
        """
        prompt = f"Write a one-line docstring for this function:\n\n{signature}\n\nDocstring:"

        response = self._call_with_budget(prompt, max_tokens=50)

        if response.text:
            # Clean up response
            docstring = response.text.strip()
            # Remove quotes if present
            docstring = docstring.strip("\"'")
            # Ensure it's a single line
            docstring = docstring.split("\n")[0]
            return docstring

        # Heuristic fallback: extract function name and create basic docstring
        func_name = signature.split("(")[0].strip().split()[-1] if "(" in signature else "function"
        return f"{func_name.replace('_', ' ').capitalize()}."

    def summarize_diff(self, diff: str) -> str:
        """
        Summarize a diff for a commit message.

        Args:
            diff: Git diff output

        Returns:
            Commit message summary
        """
        # Truncate diff if too long
        max_diff_len = 500
        diff_truncated = diff[:max_diff_len] + "..." if len(diff) > max_diff_len else diff

        prompt = f"Summarize this diff in one line for a commit message:\n\n{diff_truncated}\n\nCommit message:"

        response = self._call_with_budget(prompt, max_tokens=50)

        if response.text:
            # Clean up response
            summary = response.text.strip()
            # Remove common prefixes
            for prefix in ["commit:", "message:", "summary:"]:
                if summary.lower().startswith(prefix):
                    summary = summary[len(prefix) :].strip()
            return summary

        # Heuristic fallback: count additions/deletions
        additions = diff.count("\n+")
        deletions = diff.count("\n-")
        return f"Update code: +{additions} -{deletions}"


# Global instance (lazy initialization)
_assist_instance: LLMAssist | None = None


def get_assist() -> LLMAssist:
    """Get global LLM assist instance."""
    global _assist_instance
    if _assist_instance is None:
        _assist_instance = LLMAssist()
    return _assist_instance
