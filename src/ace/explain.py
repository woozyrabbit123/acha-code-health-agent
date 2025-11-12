"""Explain - Generate human-friendly explanations for plans."""

from typing import Any

from ace.packs import Pack
from ace.policy import rstar, rstar_pack
from ace.skills.python import EditPlan
from ace.uir import Severity


def severity_to_score(severity: Severity) -> float:
    """
    Convert severity enum to numeric score.

    Args:
        severity: Severity enum

    Returns:
        Score from 0.0 to 1.0
    """
    mapping = {
        Severity.CRITICAL: 1.0,
        Severity.HIGH: 0.8,
        Severity.MEDIUM: 0.5,
        Severity.LOW: 0.3,
        Severity.INFO: 0.1,
    }
    return mapping.get(severity, 0.5)


def explain_plan(
    plan: EditPlan,
    pack: Pack | None = None,
    policy_config: dict | None = None,
) -> str:
    """
    Generate human-friendly explanation for a plan.

    Args:
        plan: EditPlan to explain
        pack: Optional Pack if this plan is part of a pack
        policy_config: Optional policy configuration

    Returns:
        Multi-line explanation string

    Examples:
        >>> from ace.uir import create_uir
        >>> from ace.skills.python import Edit
        >>> finding = create_uir("test.py", 10, "PY-S101-UNSAFE-HTTP", "high", "No timeout", "", "requests.get(url)")
        >>> plan = EditPlan("plan-1", [finding], [Edit("test.py", 10, 10, "replace", "requests.get(url, timeout=10)")], [], 0.8)
        >>> explanation = explain_plan(plan)
        >>> "PY-S101-UNSAFE-HTTP" in explanation
        True
    """
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append(f"Plan ID: {plan.id}")
    lines.append("=" * 70)

    # Pack information
    if pack:
        lines.append("")
        lines.append("## Pack Information")
        lines.append(f"  Pack ID: {pack.id}")
        lines.append(f"  Recipe: {pack.recipe.id} - {pack.recipe.description}")
        lines.append(f"  Context: {pack.context_id}")
        lines.append(f"  Cohesion: {pack.cohesion:.3f}")
        lines.append(f"  Findings in pack: {len(pack.findings)}")

    # Findings
    lines.append("")
    lines.append("## Findings")
    lines.append(f"  Total: {len(plan.findings)}")
    lines.append("")

    for i, finding in enumerate(plan.findings, 1):
        lines.append(f"  {i}. {finding.file}:{finding.line}")
        lines.append(f"     Rule: {finding.rule}")
        lines.append(f"     Severity: {finding.severity.value}")
        lines.append(f"     Message: {finding.message}")
        if finding.snippet:
            lines.append(f"     Snippet: {finding.snippet[:80]}...")
        lines.append("")

    # Edits
    lines.append("## Edits")
    lines.append(f"  Total: {len(plan.edits)}")
    lines.append("")

    for i, edit in enumerate(plan.edits, 1):
        lines.append(f"  {i}. {edit.file}")
        lines.append(f"     Lines: {edit.start_line}-{edit.end_line}")
        lines.append(f"     Operation: {edit.op}")
        payload_preview = edit.payload[:100].replace("\n", "\\n")
        if len(edit.payload) > 100:
            payload_preview += "..."
        lines.append(f"     Payload: {payload_preview}")
        lines.append("")

    # Risk calculation
    lines.append("## Risk Assessment")
    lines.append(f"  Estimated Risk: {plan.estimated_risk:.3f}")
    lines.append("")

    # Calculate R* score
    if plan.findings:
        # Use maximum severity across findings
        max_severity = max(severity_to_score(f.severity) for f in plan.findings)
        complexity = plan.estimated_risk  # Use estimated_risk as complexity

        if pack:
            # Pack R* with cohesion boost
            policy_config = policy_config or {}
            alpha = policy_config.get("alpha", 0.7)
            beta = policy_config.get("beta", 0.3)
            gamma = policy_config.get("gamma", 0.2)

            rstar_value = rstar_pack(max_severity, complexity, pack.cohesion, alpha, beta, gamma)
            lines.append("  R* Calculation (Pack):")
            lines.append(f"    R* = α×severity + β×complexity + γ×cohesion")
            lines.append(f"    R* = {alpha}×{max_severity:.3f} + {beta}×{complexity:.3f} + {gamma}×{pack.cohesion:.3f}")
            lines.append(f"    R* = {rstar_value:.3f}")
        else:
            # Individual R*
            policy_config = policy_config or {}
            alpha = policy_config.get("alpha", 0.7)
            beta = policy_config.get("beta", 0.3)

            rstar_value = rstar(max_severity, complexity, alpha, beta)
            lines.append("  R* Calculation:")
            lines.append(f"    R* = α×severity + β×complexity")
            lines.append(f"    R* = {alpha}×{max_severity:.3f} + {beta}×{complexity:.3f}")
            lines.append(f"    R* = {rstar_value:.3f}")

        lines.append("")

        # Decision
        auto_threshold = policy_config.get("auto_threshold", 0.70) if policy_config else 0.70
        suggest_threshold = policy_config.get("suggest_threshold", 0.50) if policy_config else 0.50

        if rstar_value >= auto_threshold:
            decision = "AUTO"
            lines.append(f"  Decision: {decision} (R* >= {auto_threshold})")
        elif rstar_value >= suggest_threshold:
            decision = "SUGGEST"
            lines.append(f"  Decision: {decision} ({suggest_threshold} <= R* < {auto_threshold})")
        else:
            decision = "SKIP"
            lines.append(f"  Decision: {decision} (R* < {suggest_threshold})")

    # Invariants
    if plan.invariants:
        lines.append("")
        lines.append("## Invariants")
        for invariant in plan.invariants:
            lines.append(f"  - {invariant}")

    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)


def explain_pack(pack: Pack, policy_config: dict | None = None) -> str:
    """
    Generate explanation for a pack.

    Args:
        pack: Pack to explain
        policy_config: Optional policy configuration

    Returns:
        Multi-line explanation string
    """
    lines = []

    lines.append("=" * 70)
    lines.append(f"Pack: {pack.id}")
    lines.append("=" * 70)
    lines.append("")

    lines.append("## Recipe")
    lines.append(f"  ID: {pack.recipe.id}")
    lines.append(f"  Description: {pack.recipe.description}")
    lines.append(f"  Context Level: {pack.recipe.context}")
    lines.append(f"  Rules: {', '.join(pack.recipe.rules)}")
    lines.append("")

    lines.append("## Context")
    lines.append(f"  Context ID: {pack.context_id}")
    lines.append(f"  Cohesion: {pack.cohesion:.3f}")
    lines.append("")

    lines.append("## Findings")
    lines.append(f"  Total: {len(pack.findings)}")
    lines.append("")

    # Group by rule
    rule_counts: dict[str, int] = {}
    for finding in pack.findings:
        rule_counts[finding.rule] = rule_counts.get(finding.rule, 0) + 1

    for rule, count in sorted(rule_counts.items()):
        lines.append(f"  {rule}: {count} finding(s)")

    lines.append("")

    # List findings
    lines.append("## Finding Details")
    for i, finding in enumerate(pack.findings, 1):
        lines.append(f"  {i}. {finding.file}:{finding.line}")
        lines.append(f"     Rule: {finding.rule}")
        lines.append(f"     Severity: {finding.severity.value}")
        lines.append(f"     Message: {finding.message}")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def get_explain_summary(plans: list[EditPlan], packs: list[Pack]) -> dict[str, Any]:
    """
    Get summary information for explain output.

    Args:
        plans: List of EditPlan objects
        packs: List of Pack objects

    Returns:
        Summary dictionary
    """
    # Map plan IDs to packs
    pack_map = {}
    for pack in packs:
        for finding in pack.findings:
            # Find plans containing this finding
            for plan in plans:
                for plan_finding in plan.findings:
                    if (
                        plan_finding.file == finding.file
                        and plan_finding.line == finding.line
                        and plan_finding.rule == finding.rule
                    ):
                        pack_map[plan.id] = pack
                        break

    # Count pack vs individual plans
    pack_plan_count = len(set(pack_map.keys()))
    individual_plan_count = len(plans) - pack_plan_count

    return {
        "total_plans": len(plans),
        "pack_plans": pack_plan_count,
        "individual_plans": individual_plan_count,
        "total_packs": len(packs),
    }
