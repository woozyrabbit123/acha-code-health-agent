"""Policy evaluation scaffolding for ACE.

TODO: Implement policy scoring for ACE governance.
"""
from __future__ import annotations


def rstar(v: float, i: float, *, alpha: float = 0.7, beta: float = 0.3) -> float:
    """Compute the placeholder ACE R* metric.

    TODO: Replace with the finalized ACE policy aggregation function.
    """
    return (alpha * v) + (beta * i)
