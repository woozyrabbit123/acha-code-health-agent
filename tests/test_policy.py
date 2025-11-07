from utils.policy import PolicyConfig, PolicyEnforcer

def test_policy_violations_risky():
    cfg = PolicyConfig(fail_on_risky=True, max_errors=0)
    enforcer = PolicyEnforcer(cfg)
    results = {"issues": [{"rule": "risky_construct", "severity": "critical"}]}
    ok, reasons = enforcer.check_violations(results)
    assert not ok and any("risky" in r.lower() for r in reasons)

def test_inline_suppression():
    cfg = PolicyConfig(suppression_enabled=True)
    enforcer = PolicyEnforcer(cfg)
    issues = [{"rule": "long_function", "line": 5}]
    src = ["", "", "", "", "def f():  # acha: disable=long_function"]
    filtered = enforcer.filter_suppressed(issues, src)
    assert filtered == []
