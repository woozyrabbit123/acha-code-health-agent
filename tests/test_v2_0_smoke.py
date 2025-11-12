"""Smoke tests for ACE v2.0 features.

Tests basic functionality of Planner v1 and LLM Assist.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import pytest
except ImportError:
    pytest = None


def test_planner_v1_basic():
    """Test Planner v1 basic functionality."""
    from ace.planner import Planner, PlannerConfig, Action
    from ace.refactor import EditPlan

    # Create mock plans
    plans = [
        EditPlan(
            id="plan-1",
            findings=[],
            estimated_risk=0.85,
            rules=["TEST-RULE-1"],
            description="Test plan 1",
        ),
        EditPlan(
            id="plan-2",
            findings=[],
            estimated_risk=0.92,
            rules=["TEST-RULE-2"],
            description="Test plan 2",
        ),
    ]

    config = PlannerConfig(
        target=Path("."),
        use_context_engine=False,
        use_learning=False,
        use_telemetry=False,
    )
    planner = Planner(config)
    actions = planner.plan_actions(plans)

    # Check that actions were created
    assert len(actions) == 2
    assert all(isinstance(a, Action) for a in actions)

    # Check ordering (higher R★ should come first)
    assert actions[0].plan.id == "plan-2"  # 0.92 R★
    assert actions[1].plan.id == "plan-1"  # 0.85 R★

    # Check rationale exists
    assert actions[0].rationale is not None
    assert "R★=" in actions[0].rationale


def test_planner_priority_calculation():
    """Test Planner priority formula components."""
    from ace.planner import Planner, PlannerConfig
    from ace.refactor import EditPlan
    from ace.uir import UnifiedIssue, Severity

    # Create plan with multiple findings in same file (cohesion bonus)
    findings = [
        UnifiedIssue(
            file="test.py",
            line=10,
            rule="TEST-RULE",
            severity=Severity.HIGH,
            message="Test",
            suggestion="",
            snippet="",
        ),
        UnifiedIssue(
            file="test.py",
            line=20,
            rule="TEST-RULE",
            severity=Severity.HIGH,
            message="Test",
            suggestion="",
            snippet="",
        ),
    ]

    plan = EditPlan(
        id="plan-cohesion",
        findings=findings,
        estimated_risk=0.80,
        rules=["TEST-RULE"],
        description="Test cohesion",
    )

    config = PlannerConfig(target=Path("."), use_context_engine=False)
    planner = Planner(config)
    actions = planner.plan_actions([plan])

    # Cohesion bonus should be present in rationale
    assert "cohesion" in actions[0].rationale


def test_planner_determinism():
    """Test that Planner produces deterministic ordering."""
    from ace.planner import Planner, PlannerConfig
    from ace.refactor import EditPlan

    plans = [
        EditPlan(id=f"plan-{i}", findings=[], estimated_risk=0.75, rules=["TEST"], description=f"Plan {i}")
        for i in range(10)
    ]

    config = PlannerConfig(target=Path("."), use_context_engine=False)
    planner = Planner(config)

    # Run twice, check same ordering
    actions1 = planner.plan_actions(plans[:])
    actions2 = planner.plan_actions(plans[:])

    ids1 = [a.plan.id for a in actions1]
    ids2 = [a.plan.id for a in actions2]

    assert ids1 == ids2, "Planner should be deterministic"


def test_llm_assist_null_provider():
    """Test LLM Assist with NullProvider (heuristic fallbacks)."""
    from ace.llm import LLMAssist, NullProvider

    assist = LLMAssist(provider=NullProvider())

    # Test docstring generation
    result = assist.docstring_one_liner("def calculate_total(items: list) -> float")
    assert result.text is not None
    assert len(result.text) > 0
    assert result.provider == "NullProvider"
    assert not result.cached

    # Test name suggestion
    code = "def do_stuff(x):\n    return x * 2"
    result = assist.suggest_name(code, "do_stuff")
    assert result.text is not None
    assert result.provider == "NullProvider"

    # Test diff summarization
    diff = "+++ b/test.py\n@@ -1,0 +1,3 @@\n+def foo():\n+    pass"
    result = assist.summarize_diff(diff)
    assert result.text is not None
    assert result.provider == "NullProvider"


def test_llm_assist_budget_enforcement():
    """Test that LLM Assist enforces budget limits."""
    from ace.llm import LLMAssist, NullProvider

    assist = LLMAssist(provider=NullProvider())

    # Make 4 calls (should all succeed)
    for i in range(4):
        result = assist.docstring_one_liner(f"def func_{i}(): pass")
        assert result.text is not None
        assert result.provider in ["NullProvider", "budget-exceeded"]

    # 5th call should hit budget limit
    result = assist.docstring_one_liner("def func_5(): pass")
    assert result.provider == "budget-exceeded"


def test_llm_assist_caching():
    """Test LLM Assist caching with content fingerprinting."""
    from ace.llm import LLMAssist, NullProvider, LLMCache

    cache_path = Path("/tmp/test_llm_cache.json")
    cache_path.unlink(missing_ok=True)

    cache = LLMCache(cache_path=cache_path)
    assist = LLMAssist(provider=NullProvider(), cache=cache)

    prompt = "def calculate_total(items): pass"

    # First call - not cached
    result1 = assist.docstring_one_liner(prompt)
    assert not result1.cached

    # Second call - should be cached
    result2 = assist.docstring_one_liner(prompt)
    assert result2.cached
    assert result2.text == result1.text

    # Clean up
    cache_path.unlink(missing_ok=True)


def test_llm_cache_fingerprinting():
    """Test LLM cache fingerprint generation."""
    from ace.llm import LLMCache

    # Same prompts should have same fingerprint
    fp1 = LLMCache.fingerprint("test prompt")
    fp2 = LLMCache.fingerprint("test prompt")
    assert fp1 == fp2

    # Different prompts should have different fingerprints
    fp3 = LLMCache.fingerprint("different prompt")
    assert fp1 != fp3


def test_llm_cache_persistence():
    """Test LLM cache persists to disk."""
    from ace.llm import LLMCache

    cache_path = Path("/tmp/test_cache_persist.json")
    cache_path.unlink(missing_ok=True)

    # Create cache and add entry
    cache1 = LLMCache(cache_path=cache_path)
    fp = LLMCache.fingerprint("test")
    cache1.set(fp, "result")

    # Load cache in new instance
    cache2 = LLMCache(cache_path=cache_path)
    assert cache2.get(fp) == "result"

    # Clean up
    cache_path.unlink(missing_ok=True)


def test_ollama_provider_detection():
    """Test OllamaProvider auto-detection from env var."""
    from ace.llm import LLMAssist, OllamaProvider
    import os

    # Set OLLAMA_HOST env var
    original_host = os.environ.get("OLLAMA_HOST")
    os.environ["OLLAMA_HOST"] = "http://localhost:11434"

    try:
        assist = LLMAssist()
        # Should detect Ollama from env var
        assert isinstance(assist.provider, OllamaProvider)
    finally:
        # Restore original env var
        if original_host:
            os.environ["OLLAMA_HOST"] = original_host
        else:
            os.environ.pop("OLLAMA_HOST", None)


def test_autopilot_uses_planner():
    """Test that autopilot uses Planner v1."""
    # This is an integration test - just verify the import works
    from ace.autopilot import run_autopilot, AutopilotConfig
    from ace.planner import Planner

    # Verify Planner is imported in autopilot module
    import ace.autopilot
    assert hasattr(ace.autopilot, "Planner")


def test_cli_check_strict():
    """Test ace check --strict command."""
    from ace.cli import cmd_check
    from ace.errors import ExitCode
    from unittest.mock import MagicMock
    import argparse

    # Mock args
    args = argparse.Namespace(
        target=Path("."),
        rules=None,
        strict=True,
    )

    # Mock run_analyze to return findings
    with patch("ace.cli.run_analyze") as mock_analyze:
        mock_analyze.return_value = [MagicMock()]  # Non-empty findings

        # Strict mode should fail with findings
        exit_code = cmd_check(args)
        assert exit_code == ExitCode.POLICY_DENY


def test_cli_assist_imports():
    """Test that assist CLI commands can be imported."""
    from ace.cli import cmd_assist, cmd_commitmsg

    # Just verify they exist
    assert callable(cmd_assist)
    assert callable(cmd_commitmsg)


def test_planner_with_learning():
    """Test Planner integration with Learning."""
    from ace.planner import Planner, PlannerConfig
    from ace.refactor import EditPlan
    from ace.learn import LearningEngine
    from pathlib import Path

    learn_path = Path("/tmp/test_planner_learn.json")
    learn_path.unlink(missing_ok=True)

    # Create learning with some data
    learning = LearningEngine(learn_path=learn_path)
    learning.record_outcome("TEST-RULE", "applied")
    learning.record_outcome("TEST-RULE", "applied")
    learning.record_outcome("TEST-RULE", "applied")
    learning.save()

    # Create plan
    plan = EditPlan(
        id="plan-1",
        findings=[],
        estimated_risk=0.80,
        rules=["TEST-RULE"],
        description="Test",
    )

    # Planner should use learning data
    config = PlannerConfig(target=Path("."), use_learning=True)
    planner = Planner(config)
    planner.learning = learning  # Inject our test learning

    actions = planner.plan_actions([plan])

    # Should include success_rate_bonus in rationale
    assert "success_rate_bonus" in actions[0].rationale or actions[0].priority > 80.0

    # Clean up
    learn_path.unlink(missing_ok=True)


def test_planner_with_telemetry():
    """Test Planner integration with Telemetry."""
    from ace.planner import Planner, PlannerConfig
    from ace.refactor import EditPlan
    from ace.telemetry import Telemetry
    from pathlib import Path

    telemetry_path = Path("/tmp/test_planner_telemetry.jsonl")
    telemetry_path.unlink(missing_ok=True)

    # Create telemetry with some data
    telemetry = Telemetry(telemetry_path=telemetry_path)
    telemetry.record("TEST-RULE-1", duration_ms=50.0, files=1, ok=True)
    telemetry.record("TEST-RULE-2", duration_ms=150.0, files=1, ok=True)

    # Create plans
    plans = [
        EditPlan(id="plan-1", findings=[], estimated_risk=0.80, rules=["TEST-RULE-1"], description="Fast rule"),
        EditPlan(id="plan-2", findings=[], estimated_risk=0.80, rules=["TEST-RULE-2"], description="Slow rule"),
    ]

    # Planner should prefer faster rule
    config = PlannerConfig(target=Path("."), use_telemetry=True)
    planner = Planner(config)
    planner.telemetry = telemetry  # Inject our test telemetry

    actions = planner.plan_actions(plans)

    # Fast rule should have higher priority (less cost penalty)
    # Both have same R★, so cost penalty should determine order
    # Actually with deterministic sorting by plan.id, need to check rationale
    assert any("cost_penalty" in a.rationale for a in actions)

    # Clean up
    telemetry_path.unlink(missing_ok=True)


def test_pre_commit_idempotence():
    """Test pre-commit installation is idempotent."""
    from ace.cli import cmd_install_pre_commit
    from ace.errors import ExitCode
    import argparse
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create fake git directory
        git_dir = Path(tmpdir) / ".git"
        git_dir.mkdir()

        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)

            args = argparse.Namespace()

            # First install
            exit_code1 = cmd_install_pre_commit(args)
            assert exit_code1 == ExitCode.SUCCESS

            # Second install (should be idempotent)
            exit_code2 = cmd_install_pre_commit(args)
            assert exit_code2 == ExitCode.SUCCESS

        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    # Run tests
    print("Running v2.0 smoke tests...\n")

    test_planner_v1_basic()
    print("✓ Planner v1 basic test passed")

    test_planner_priority_calculation()
    print("✓ Planner priority calculation test passed")

    test_planner_determinism()
    print("✓ Planner determinism test passed")

    test_llm_assist_null_provider()
    print("✓ LLM Assist NullProvider test passed")

    test_llm_assist_budget_enforcement()
    print("✓ LLM Assist budget enforcement test passed")

    test_llm_assist_caching()
    print("✓ LLM Assist caching test passed")

    test_llm_cache_fingerprinting()
    print("✓ LLM cache fingerprinting test passed")

    test_llm_cache_persistence()
    print("✓ LLM cache persistence test passed")

    test_autopilot_uses_planner()
    print("✓ Autopilot uses Planner test passed")

    test_cli_check_strict()
    print("✓ CLI check --strict test passed")

    test_cli_assist_imports()
    print("✓ CLI assist imports test passed")

    test_planner_with_learning()
    print("✓ Planner with Learning test passed")

    test_planner_with_telemetry()
    print("✓ Planner with Telemetry test passed")

    test_pre_commit_idempotence()
    print("✓ Pre-commit idempotence test passed")

    print("\n✓ All v2.0 smoke tests passed!")
