"""Pack synthesis - Create cohesive EditPlans from packs."""

import hashlib
from pathlib import Path
from typing import Any

from ace.packs import Pack
from ace.skills.python import Edit, EditPlan
from ace.uir import UnifiedIssue


def check_edit_overlap(edit1: Edit, edit2: Edit) -> bool:
    """
    Check if two edits have overlapping line ranges.

    Args:
        edit1: First edit
        edit2: Second edit

    Returns:
        True if edits overlap, False otherwise

    Examples:
        >>> e1 = Edit("test.py", 10, 15, "replace", "new code")
        >>> e2 = Edit("test.py", 12, 18, "replace", "other code")
        >>> check_edit_overlap(e1, e2)
        True
        >>> e3 = Edit("test.py", 20, 25, "replace", "different code")
        >>> check_edit_overlap(e1, e3)
        False
    """
    # Must be same file
    if edit1.file != edit2.file:
        return False

    # Check for line range overlap
    # Ranges [a, b] and [c, d] overlap if: max(a, c) <= min(b, d)
    return max(edit1.start_line, edit2.start_line) <= min(edit1.end_line, edit2.end_line)


def validate_non_overlapping(edits: list[Edit]) -> bool:
    """
    Validate that a list of edits don't have overlapping line ranges.

    Args:
        edits: List of Edit objects

    Returns:
        True if no overlaps, False if any overlaps found

    Examples:
        >>> e1 = Edit("test.py", 10, 15, "replace", "code1")
        >>> e2 = Edit("test.py", 20, 25, "replace", "code2")
        >>> validate_non_overlapping([e1, e2])
        True
        >>> e3 = Edit("test.py", 12, 18, "replace", "code3")
        >>> validate_non_overlapping([e1, e3])
        False
    """
    for i, edit1 in enumerate(edits):
        for edit2 in edits[i + 1:]:
            if check_edit_overlap(edit1, edit2):
                return False
    return True


def compute_pack_plan_id(pack: Pack) -> str:
    """
    Compute stable plan ID for a pack.

    Args:
        pack: Pack object

    Returns:
        Plan ID (first 16 chars of SHA256 hash)
    """
    # Use pack ID + finding IDs for stability
    finding_ids = sorted(f.to_dict()["stable_id"] for f in pack.findings)
    combined = f"pack:{pack.id}:" + ":".join(finding_ids)
    hash_bytes = hashlib.sha256(combined.encode("utf-8")).digest()
    return f"pack-{hash_bytes.hex()[:16]}"


def synthesize_pack_plan(
    pack: Pack,
    individual_plans: list[EditPlan],
) -> EditPlan | None:
    """
    Synthesize a single EditPlan from a pack by combining individual plans.

    Strategy:
    1. Find all individual plans that correspond to pack findings
    2. Collect all edits from these plans
    3. Validate that edits don't overlap
    4. If valid, create combined pack plan
    5. If overlaps found, return None (will fallback to individual)

    Args:
        pack: Pack object containing related findings
        individual_plans: List of individual EditPlan objects

    Returns:
        Combined EditPlan or None if conflicts detected

    Examples:
        >>> from ace.uir import create_uir
        >>> from ace.packs import PackRecipe, Pack
        >>> recipe = PackRecipe("TEST", ["R1", "R2"], "file", "Test pack")
        >>> findings = [
        ...     create_uir("test.py", 10, "R1", "high", "msg1", "", "snip1"),
        ...     create_uir("test.py", 20, "R2", "high", "msg2", "", "snip2"),
        ... ]
        >>> pack = Pack("test-pack", recipe, "test.py", findings, 1.0)
        >>> plan1 = EditPlan("p1", [findings[0]], [Edit("test.py", 10, 10, "replace", "fix1")], [], 0.5)
        >>> plan2 = EditPlan("p2", [findings[1]], [Edit("test.py", 20, 20, "replace", "fix2")], [], 0.5)
        >>> pack_plan = synthesize_pack_plan(pack, [plan1, plan2])
        >>> pack_plan is not None
        True
        >>> len(pack_plan.edits)
        2
    """
    # Build map of finding stable_id to individual plan
    finding_to_plan = {}
    for plan in individual_plans:
        for finding in plan.findings:
            stable = finding.to_dict()["stable_id"]
            finding_to_plan[stable] = plan

    # Collect plans that belong to this pack
    pack_plans = []
    for finding in pack.findings:
        stable = finding.to_dict()["stable_id"]
        if stable in finding_to_plan:
            plan = finding_to_plan[stable]
            if plan not in pack_plans:
                pack_plans.append(plan)

    if not pack_plans:
        return None

    # Collect all edits from pack plans
    all_edits = []
    all_invariants = []
    max_risk = 0.0

    for plan in pack_plans:
        all_edits.extend(plan.edits)
        all_invariants.extend(plan.invariants)
        max_risk = max(max_risk, plan.estimated_risk)

    # Validate non-overlapping
    if not validate_non_overlapping(all_edits):
        return None

    # Sort edits by file, then start line for determinism
    all_edits.sort(key=lambda e: (e.file, e.start_line))

    # Deduplicate invariants
    unique_invariants = sorted(set(all_invariants))

    # Create combined plan
    pack_plan_id = compute_pack_plan_id(pack)
    return EditPlan(
        id=pack_plan_id,
        findings=pack.findings,
        edits=all_edits,
        invariants=unique_invariants,
        estimated_risk=max_risk,
    )


def synthesize_pack_plans(
    packs: list[Pack],
    individual_plans: list[EditPlan],
) -> tuple[list[EditPlan], list[EditPlan]]:
    """
    Synthesize pack plans from individual plans.

    Args:
        packs: List of Pack objects
        individual_plans: List of individual EditPlan objects

    Returns:
        Tuple of (pack_plans, fallback_plans)
        - pack_plans: Successfully synthesized pack plans
        - fallback_plans: Individual plans that couldn't be packed or weren't in any pack

    Examples:
        >>> from ace.uir import create_uir
        >>> from ace.packs import PackRecipe, Pack
        >>> recipe = PackRecipe("TEST", ["R1", "R2"], "file", "Test")
        >>> f1 = create_uir("test.py", 10, "R1", "high", "msg1", "", "s1")
        >>> f2 = create_uir("test.py", 20, "R2", "high", "msg2", "", "s2")
        >>> f3 = create_uir("other.py", 5, "R3", "low", "msg3", "", "s3")
        >>> pack = Pack("p1", recipe, "test.py", [f1, f2], 1.0)
        >>> plan1 = EditPlan("plan1", [f1], [Edit("test.py", 10, 10, "replace", "fix")], [], 0.5)
        >>> plan2 = EditPlan("plan2", [f2], [Edit("test.py", 20, 20, "replace", "fix")], [], 0.5)
        >>> plan3 = EditPlan("plan3", [f3], [Edit("other.py", 5, 5, "replace", "fix")], [], 0.3)
        >>> pack_plans, fallback_plans = synthesize_pack_plans([pack], [plan1, plan2, plan3])
        >>> len(pack_plans)
        1
        >>> len(fallback_plans)
        1
    """
    pack_plans = []
    used_plan_ids = set()

    # Try to synthesize each pack
    for pack in packs:
        pack_plan = synthesize_pack_plan(pack, individual_plans)
        if pack_plan is not None:
            pack_plans.append(pack_plan)
            # Mark all findings in this pack as used
            for finding in pack.findings:
                stable = finding.to_dict()["stable_id"]
                # Find and mark the individual plans as used
                for plan in individual_plans:
                    for plan_finding in plan.findings:
                        if plan_finding.to_dict()["stable_id"] == stable:
                            used_plan_ids.add(plan.id)

    # Collect fallback plans (not used in any pack)
    fallback_plans = [
        plan for plan in individual_plans
        if plan.id not in used_plan_ids
    ]

    return pack_plans, fallback_plans


def merge_pack_and_fallback_plans(
    pack_plans: list[EditPlan],
    fallback_plans: list[EditPlan],
) -> list[EditPlan]:
    """
    Merge pack and fallback plans into a single sorted list.

    Plans are sorted by estimated risk (descending), then by plan ID.

    Args:
        pack_plans: List of pack EditPlan objects
        fallback_plans: List of fallback EditPlan objects

    Returns:
        Merged and sorted list of EditPlan objects
    """
    all_plans = pack_plans + fallback_plans
    all_plans.sort(key=lambda p: (-p.estimated_risk, p.id))
    return all_plans


def get_pack_synthesis_summary(
    packs: list[Pack],
    pack_plans: list[EditPlan],
    fallback_plans: list[EditPlan],
) -> dict[str, Any]:
    """
    Generate summary statistics for pack synthesis.

    Args:
        packs: List of Pack objects
        pack_plans: List of synthesized pack plans
        fallback_plans: List of fallback individual plans

    Returns:
        Dictionary with synthesis statistics
    """
    return {
        "packs_found": len(packs),
        "packs_synthesized": len(pack_plans),
        "fallback_plans": len(fallback_plans),
        "total_plans": len(pack_plans) + len(fallback_plans),
        "synthesis_rate": (
            round(len(pack_plans) / len(packs), 3) if packs else 0.0
        ),
    }
