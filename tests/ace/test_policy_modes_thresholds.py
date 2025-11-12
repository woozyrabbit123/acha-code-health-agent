"""Tests for policy modes, thresholds, and R* scoring with packs."""

import pytest

from ace.policy import decision, rstar, rstar_pack, Decision


class TestRstar:
    """Tests for R* calculation."""

    def test_rstar_basic(self):
        """Test basic R* calculation."""
        # High severity, high complexity
        score = rstar(0.9, 0.8)
        assert 0.85 <= score <= 0.90

        # Low severity, low complexity
        score = rstar(0.3, 0.2)
        assert 0.25 <= score <= 0.30

    def test_rstar_bounds(self):
        """Test R* is bounded to [0.0, 1.0]."""
        score = rstar(0.0, 0.0)
        assert score == 0.0

        score = rstar(1.0, 1.0)
        assert score == 1.0

    def test_rstar_weights(self):
        """Test custom R* weights."""
        # Default: 0.7 * 1.0 + 0.3 * 0.0 = 0.7
        score = rstar(1.0, 0.0)
        assert score == 0.7

        # Custom: 0.5 * 1.0 + 0.5 * 0.0 = 0.5
        score = rstar(1.0, 0.0, alpha=0.5, beta=0.5)
        assert score == 0.5

    def test_rstar_input_validation(self):
        """Test R* handles out-of-bounds inputs."""
        # Should clamp to valid range
        score = rstar(-0.1, 1.5)
        assert 0.0 <= score <= 1.0

        score = rstar(1.5, -0.1)
        assert 0.0 <= score <= 1.0


class TestRstarPack:
    """Tests for pack R* calculation with cohesion boost."""

    def test_rstar_pack_basic(self):
        """Test pack R* includes cohesion boost."""
        # High severity, high complexity, perfect cohesion
        score = rstar_pack(0.9, 0.8, 1.0)
        # Base: 0.7*0.9 + 0.3*0.8 = 0.87
        # Boost: +0.2*1.0 = 0.2
        # Total: 1.07, capped at 1.0
        assert score == 1.0

    def test_rstar_pack_no_cohesion(self):
        """Test pack R* with zero cohesion."""
        # Same as regular R* when cohesion is 0
        score_pack = rstar_pack(0.9, 0.8, 0.0)
        score_regular = rstar(0.9, 0.8)
        assert score_pack == score_regular

    def test_rstar_pack_partial_cohesion(self):
        """Test pack R* with partial cohesion."""
        # Base: 0.7*0.5 + 0.3*0.3 = 0.44
        # Boost: +0.2*0.6 = 0.12
        # Total: 0.56
        score = rstar_pack(0.5, 0.3, 0.6)
        assert 0.55 <= score <= 0.57

    def test_rstar_pack_custom_weights(self):
        """Test pack R* with custom weights."""
        score = rstar_pack(
            0.8, 0.5, 1.0,
            alpha=0.5,
            beta=0.3,
            gamma=0.3,
        )
        # 0.5*0.8 + 0.3*0.5 + 0.3*1.0 = 0.4 + 0.15 + 0.3 = 0.85
        assert 0.84 <= score <= 0.86

    def test_rstar_pack_capped(self):
        """Test pack R* is capped at 1.0."""
        score = rstar_pack(1.0, 1.0, 1.0)
        assert score == 1.0

        # Even with very high inputs
        score = rstar_pack(1.0, 1.0, 1.0, alpha=0.9, beta=0.9, gamma=0.9)
        assert score == 1.0


class TestDecision:
    """Tests for refactoring decision based on R*."""

    def test_auto_decision(self):
        """Test AUTO decision for high R*."""
        d = decision(0.85)
        assert d == Decision.AUTO

        d = decision(0.70)  # At threshold
        assert d == Decision.AUTO

    def test_suggest_decision(self):
        """Test SUGGEST decision for medium R*."""
        d = decision(0.60)
        assert d == Decision.SUGGEST

        d = decision(0.50)  # At threshold
        assert d == Decision.SUGGEST

    def test_skip_decision(self):
        """Test SKIP decision for low R*."""
        d = decision(0.40)
        assert d == Decision.SKIP

        d = decision(0.10)
        assert d == Decision.SKIP

    def test_custom_thresholds(self):
        """Test custom decision thresholds."""
        # With auto=0.9, suggest=0.6
        d = decision(0.95, auto_threshold=0.9, suggest_threshold=0.6)
        assert d == Decision.AUTO

        d = decision(0.75, auto_threshold=0.9, suggest_threshold=0.6)
        assert d == Decision.SUGGEST

        d = decision(0.50, auto_threshold=0.9, suggest_threshold=0.6)
        assert d == Decision.SKIP

    def test_edge_cases(self):
        """Test edge cases."""
        # At exact thresholds
        d = decision(0.70, auto_threshold=0.70, suggest_threshold=0.50)
        assert d == Decision.AUTO

        d = decision(0.50, auto_threshold=0.70, suggest_threshold=0.50)
        assert d == Decision.SUGGEST

        d = decision(0.49, auto_threshold=0.70, suggest_threshold=0.50)
        assert d == Decision.SKIP


class TestPolicyModeScenarios:
    """Integration tests for policy modes and scenarios."""

    def test_high_severity_high_complexity_auto(self):
        """High severity + high complexity → AUTO."""
        rstar_value = rstar(0.9, 0.8)  # ~0.87
        d = decision(rstar_value)
        assert d == Decision.AUTO

    def test_medium_severity_low_complexity_suggest(self):
        """Medium severity + low complexity → SUGGEST."""
        rstar_value = rstar(0.5, 0.3)  # ~0.44
        d = decision(rstar_value)
        assert d == Decision.SKIP  # Below 0.5 threshold

        # But if we adjust weights
        rstar_value = rstar(0.6, 0.5)  # ~0.57
        d = decision(rstar_value)
        assert d == Decision.SUGGEST

    def test_low_severity_any_complexity_skip(self):
        """Low severity → likely SKIP."""
        rstar_value = rstar(0.2, 0.9)  # 0.7*0.2 + 0.3*0.9 = 0.41
        d = decision(rstar_value)
        assert d == Decision.SKIP

    def test_pack_cohesion_boost_changes_decision(self):
        """Pack cohesion can boost SUGGEST to AUTO."""
        # Without cohesion: SUGGEST
        rstar_value = rstar(0.6, 0.5)  # ~0.57
        d = decision(rstar_value)
        assert d == Decision.SUGGEST

        # With cohesion: AUTO
        rstar_pack_value = rstar_pack(0.6, 0.5, 1.0)  # ~0.77
        d = decision(rstar_pack_value)
        assert d == Decision.AUTO

    def test_partial_cohesion_boost(self):
        """Partial cohesion provides partial boost."""
        base = rstar(0.6, 0.4)  # 0.7*0.6 + 0.3*0.4 = 0.54

        partial = rstar_pack(0.6, 0.4, 0.5)  # + 0.2*0.5 = 0.64
        full = rstar_pack(0.6, 0.4, 1.0)  # + 0.2*1.0 = 0.74

        assert partial > base
        assert full > partial
        assert decision(base) == Decision.SUGGEST
        assert decision(partial) == Decision.SUGGEST
        assert decision(full) == Decision.AUTO


class TestPolicyThresholdTuning:
    """Tests for threshold tuning scenarios."""

    def test_conservative_thresholds(self):
        """Test conservative thresholds (higher bars)."""
        # Conservative: auto=0.9, suggest=0.7
        score = 0.85

        d = decision(score, auto_threshold=0.9, suggest_threshold=0.7)
        assert d == Decision.SUGGEST  # Would be AUTO with default thresholds

    def test_aggressive_thresholds(self):
        """Test aggressive thresholds (lower bars)."""
        # Aggressive: auto=0.5, suggest=0.3
        score = 0.55

        d = decision(score, auto_threshold=0.5, suggest_threshold=0.3)
        assert d == Decision.AUTO  # Would be SUGGEST with default thresholds

    def test_detect_only_mode(self):
        """Test detect-only mode (never auto-apply)."""
        # In detect-only, even high R* should not auto-apply
        # This is enforced at a higher level (policy config filter)
        # But we can simulate by using impossible threshold
        score = 0.95

        d = decision(score, auto_threshold=999.0)
        assert d == Decision.SUGGEST  # Can't reach AUTO threshold

    def test_auto_fix_mode(self):
        """Test auto-fix mode with normal thresholds."""
        score = 0.85

        d = decision(score)
        assert d == Decision.AUTO


class TestRiskClassMapping:
    """Tests for risk class → threshold mapping."""

    def test_security_high_priority(self):
        """Security issues should have high R* scores."""
        # Simulate security finding: high severity
        security_score = rstar(0.9, 0.5)
        assert security_score >= 0.70  # Should be AUTO

    def test_style_low_priority(self):
        """Style issues should have lower R* scores."""
        # Simulate style finding: low severity
        style_score = rstar(0.2, 0.1)
        assert style_score < 0.50  # Should be SKIP

    def test_reliability_medium_priority(self):
        """Reliability issues should have medium R* scores."""
        # Simulate reliability finding: medium severity
        reliability_score = rstar(0.5, 0.4)
        assert 0.40 <= reliability_score <= 0.60  # Likely SUGGEST

    def test_pack_prioritization(self):
        """Packs with related fixes get priority boost."""
        # Individual finding: might be SUGGEST
        individual = rstar(0.6, 0.4)

        # Same finding in a cohesive pack: AUTO
        pack = rstar_pack(0.6, 0.4, 0.9)

        assert decision(individual) == Decision.SUGGEST
        assert decision(pack) == Decision.AUTO
