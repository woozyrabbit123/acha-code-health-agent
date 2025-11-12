"""
Built-in Codemod Packs for ACE v1.6.

Defines standard codemod packs that can be applied via CLI.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, List

from ace.skills.python import EditPlan


@dataclass
class CodemodPack:
    """Definition of a codemod pack."""
    id: str
    name: str
    description: str
    codemod_func: Callable[[str, str], Optional[EditPlan]]
    risk_level: str  # "low", "medium", "high"
    category: str  # "modernization", "security", "performance", "style"


# Pack Registry
BUILTIN_PACKS = {}


def register_pack(pack: CodemodPack) -> None:
    """Register a codemod pack."""
    BUILTIN_PACKS[pack.id] = pack


def get_pack(pack_id: str) -> Optional[CodemodPack]:
    """Get a pack by ID."""
    return BUILTIN_PACKS.get(pack_id)


def list_packs() -> List[CodemodPack]:
    """List all registered packs."""
    return list(BUILTIN_PACKS.values())


# Define built-in packs

def _init_packs():
    """Initialize built-in packs."""
    from ace.codemods.pathlib_modernize import PathlibModernizeCodemod
    from ace.codemods.requests_hardener import RequestsHardenerCodemod
    from ace.codemods.dataclass_slots import DataclassSlotsCodemod
    from ace.codemods.print_to_logging import PrintToLoggingCodemod
    from ace.codemods.dead_imports import DeadImportsCodemod

    register_pack(CodemodPack(
        id="PY_PATHLIB",
        name="Pathlib Modernization",
        description="Modernize os.path.* calls to pathlib.Path",
        codemod_func=PathlibModernizeCodemod.plan,
        risk_level="low",
        category="modernization"
    ))

    register_pack(CodemodPack(
        id="PY_REQUESTS_HARDEN",
        name="Requests Hardening",
        description="Add timeout and error handling to requests calls",
        codemod_func=RequestsHardenerCodemod.plan,
        risk_level="medium",
        category="security"
    ))

    register_pack(CodemodPack(
        id="PY_DATACLASS_SLOTS",
        name="Dataclass Slots",
        description="Add slots=True to @dataclass decorators for memory efficiency",
        codemod_func=DataclassSlotsCodemod.plan,
        risk_level="low",
        category="performance"
    ))

    register_pack(CodemodPack(
        id="PY_PRINT_LOGGING",
        name="Print to Logging",
        description="Convert print() calls to logging.info()",
        codemod_func=PrintToLoggingCodemod.plan,
        risk_level="low",
        category="style"
    ))

    register_pack(CodemodPack(
        id="PY_DEAD_IMPORTS",
        name="Remove Dead Imports",
        description="Remove unused imports (scope-aware)",
        codemod_func=DeadImportsCodemod.plan,
        risk_level="low",
        category="style"
    ))


# Initialize on import
_init_packs()


def apply_pack_to_file(pack_id: str, file_path: str, source_code: str) -> Optional[EditPlan]:
    """
    Apply a codemod pack to a file.

    Args:
        pack_id: Pack ID (e.g., "PY_PATHLIB")
        file_path: File path
        source_code: Source code content

    Returns:
        EditPlan if changes needed, None otherwise
    """
    pack = get_pack(pack_id)
    if not pack:
        raise ValueError(f"Unknown pack: {pack_id}")

    return pack.codemod_func(source_code, file_path)


def apply_pack_to_directory(pack_id: str, directory: Path, pattern: str = "**/*.py") -> List[EditPlan]:
    """
    Apply a codemod pack to all matching files in a directory.

    Args:
        pack_id: Pack ID
        directory: Directory to scan
        pattern: Glob pattern for files

    Returns:
        List of EditPlans
    """
    plans = []

    for file_path in directory.glob(pattern):
        if file_path.is_file():
            try:
                source_code = file_path.read_text(encoding='utf-8')
                plan = apply_pack_to_file(pack_id, str(file_path), source_code)
                if plan:
                    plans.append(plan)
            except Exception:
                continue

    return plans
