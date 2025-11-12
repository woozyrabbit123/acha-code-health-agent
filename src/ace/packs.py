"""Macro-Fix Packs - Group related findings for cohesive refactoring."""

import hashlib
from dataclasses import dataclass
from typing import Any

from ace.uir import UnifiedIssue


# ============================================================================
# Pack Recipes - Define related rules that should be fixed together
# ============================================================================

@dataclass(frozen=True)
class PackRecipe:
    """
    Definition of a pack - related rules that should be fixed together.

    Attributes:
        id: Unique pack identifier (e.g., "PY_HTTP_SAFETY")
        rules: List of rule IDs that belong to this pack
        context: Grouping level ("file", "function", "class")
        description: Human-readable pack description
    """
    id: str
    rules: list[str]
    context: str  # "file", "function", "class"
    description: str


# Built-in pack recipes
PACK_RECIPES = [
    PackRecipe(
        id="PY_HTTP_SAFETY",
        rules=[
            "PY-S101-UNSAFE-HTTP",
            "PY-S201-SUBPROCESS-CHECK",
            "PY-I101-IMPORT-SORT",
        ],
        context="function",
        description="HTTP safety and subprocess security fixes",
    ),
    PackRecipe(
        id="PY_EXCEPTION_HANDLING",
        rules=[
            "PY-E201-BROAD-EXCEPT",
        ],
        context="function",
        description="Exception handling improvements",
    ),
    PackRecipe(
        id="PY_CODE_QUALITY",
        rules=[
            "PY-Q201-ASSERT-IN-NONTEST",
            "PY-Q202-PRINT-IN-SRC",
            "PY-Q203-EVAL-EXEC",
        ],
        context="function",
        description="Code quality improvements",
    ),
    PackRecipe(
        id="PY_STYLE",
        rules=[
            "PY-S310-TRAILING-WS",
            "PY-S311-EOF-NL",
            "PY-S312-BLANKLINES",
        ],
        context="file",
        description="Code style and formatting",
    ),
]


@dataclass
class Pack:
    """
    A pack represents a group of related findings.

    Attributes:
        id: Stable pack identifier (context_id + recipe_id hash)
        recipe: The pack recipe that matches these findings
        context_id: Context identifier (file, file::class, file::class::func)
        findings: List of findings in this pack
        cohesion: Cohesion score (0.0 to 1.0)
    """
    id: str
    recipe: PackRecipe
    context_id: str
    findings: list[UnifiedIssue]
    cohesion: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert pack to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "recipe_id": self.recipe.id,
            "recipe_description": self.recipe.description,
            "context_id": self.context_id,
            "context": self.recipe.context,
            "findings": [f.to_dict() for f in self.findings],
            "cohesion": self.cohesion,
            "rule_count": len(set(f.rule for f in self.findings)),
            "finding_count": len(self.findings),
        }


# ============================================================================
# Context ID computation
# ============================================================================

def compute_context_id(finding: UnifiedIssue, context_level: str) -> str:
    """
    Compute context ID for a finding based on context level.

    For now, uses simplified heuristics:
    - "file": just the file path
    - "function": file + line range (assumes findings within 50 lines are same function)
    - "class": file + line range (assumes findings within 100 lines are same class)

    Args:
        finding: UnifiedIssue to compute context for
        context_level: One of "file", "function", "class"

    Returns:
        Context ID string (e.g., "foo.py", "foo.py::100-150", "foo.py::Class::func")
    """
    if context_level == "file":
        return finding.file

    elif context_level == "function":
        # Group by file and 50-line ranges (rough function approximation)
        line_bucket = (finding.line // 50) * 50
        return f"{finding.file}::L{line_bucket}-{line_bucket + 50}"

    elif context_level == "class":
        # Group by file and 100-line ranges (rough class approximation)
        line_bucket = (finding.line // 100) * 100
        return f"{finding.file}::L{line_bucket}-{line_bucket + 100}"

    else:
        # Default to file
        return finding.file


def compute_pack_id(context_id: str, recipe_id: str) -> str:
    """
    Compute stable pack ID from context and recipe.

    Args:
        context_id: Context identifier
        recipe_id: Pack recipe ID

    Returns:
        Stable pack ID (first 12 chars of SHA256 hash)
    """
    combined = f"{context_id}::{recipe_id}"
    hash_bytes = hashlib.sha256(combined.encode("utf-8")).digest()
    return hash_bytes.hex()[:12]


# ============================================================================
# Pack finding algorithm
# ============================================================================

def find_packs(
    findings: list[UnifiedIssue],
    recipes: list[PackRecipe] | None = None,
    min_findings: int = 2,
) -> list[Pack]:
    """
    Find packs (groups of related findings) using deterministic grouping.

    Algorithm:
    1. For each pack recipe, find findings that match recipe rules
    2. Group matching findings by context_id (computed from context level)
    3. Create Pack objects for groups with >= min_findings
    4. Compute cohesion score based on rule coverage

    Args:
        findings: List of UnifiedIssue findings to group
        recipes: Pack recipes to use (default: built-in PACK_RECIPES)
        min_findings: Minimum findings required to form a pack (default: 2)

    Returns:
        List of Pack objects, sorted by (cohesion desc, context_id asc)

    Examples:
        >>> findings = [
        ...     UnifiedIssue("test.py", 10, "PY-S101-UNSAFE-HTTP", "high", "msg", "", ""),
        ...     UnifiedIssue("test.py", 15, "PY-S201-SUBPROCESS-CHECK", "high", "msg", "", ""),
        ... ]
        >>> packs = find_packs(findings)
        >>> len(packs)
        1
        >>> packs[0].recipe.id
        'PY_HTTP_SAFETY'
    """
    if recipes is None:
        recipes = PACK_RECIPES

    packs = []

    # Track which findings have been assigned to packs
    used_findings = set()

    # For each recipe, find matching packs
    for recipe in recipes:
        # Find findings that match recipe rules
        recipe_rule_set = set(recipe.rules)
        matching_findings = [
            f for f in findings
            if f.rule in recipe_rule_set and id(f) not in used_findings
        ]

        if len(matching_findings) < min_findings:
            continue

        # Group by context ID
        context_groups: dict[str, list[UnifiedIssue]] = {}
        for finding in matching_findings:
            context_id = compute_context_id(finding, recipe.context)
            if context_id not in context_groups:
                context_groups[context_id] = []
            context_groups[context_id].append(finding)

        # Create packs for groups with enough findings
        for context_id, group_findings in context_groups.items():
            if len(group_findings) < min_findings:
                continue

            # Compute cohesion: ratio of unique rules to total recipe rules
            unique_rules = len(set(f.rule for f in group_findings))
            cohesion = min(1.0, unique_rules / len(recipe.rules))

            # Create pack
            pack_id = compute_pack_id(context_id, recipe.id)
            pack = Pack(
                id=pack_id,
                recipe=recipe,
                context_id=context_id,
                findings=group_findings,
                cohesion=cohesion,
            )
            packs.append(pack)

            # Mark findings as used
            for f in group_findings:
                used_findings.add(id(f))

    # Sort packs: high cohesion first, then by context_id for determinism
    packs.sort(key=lambda p: (-p.cohesion, p.context_id))

    return packs


def get_pack_summary(packs: list[Pack]) -> dict[str, Any]:
    """
    Generate summary statistics for packs.

    Args:
        packs: List of Pack objects

    Returns:
        Dictionary with pack statistics
    """
    if not packs:
        return {
            "pack_count": 0,
            "total_findings": 0,
            "avg_cohesion": 0.0,
            "recipes_used": [],
        }

    total_findings = sum(len(p.findings) for p in packs)
    avg_cohesion = sum(p.cohesion for p in packs) / len(packs)
    recipes_used = sorted(set(p.recipe.id for p in packs))

    return {
        "pack_count": len(packs),
        "total_findings": total_findings,
        "avg_cohesion": round(avg_cohesion, 3),
        "recipes_used": recipes_used,
        "packs": [
            {
                "id": p.id,
                "recipe": p.recipe.id,
                "context": p.context_id,
                "findings": len(p.findings),
                "cohesion": round(p.cohesion, 3),
            }
            for p in packs
        ],
    }


def filter_packs_by_rules(packs: list[Pack], enabled_rules: list[str]) -> list[Pack]:
    """
    Filter packs to only include those with enabled rules.

    Args:
        packs: List of Pack objects
        enabled_rules: List of enabled rule IDs

    Returns:
        Filtered list of packs
    """
    if not enabled_rules:
        return packs

    enabled_set = set(enabled_rules)
    filtered = []

    for pack in packs:
        # Keep pack if any of its findings have enabled rules
        pack_findings = [f for f in pack.findings if f.rule in enabled_set]
        if pack_findings:
            # Create new pack with filtered findings
            filtered_pack = Pack(
                id=pack.id,
                recipe=pack.recipe,
                context_id=pack.context_id,
                findings=pack_findings,
                cohesion=pack.cohesion,
            )
            filtered.append(filtered_pack)

    return filtered
