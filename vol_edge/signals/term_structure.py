"""Term structure helpers for VIX vs VIX3M."""

from __future__ import annotations

from enum import Enum


class TermStructureState(str, Enum):
    CONTANGO = "contango"
    BACKWARDATION = "backwardation"


def compute_term_structure_state(vix: float, vix3m: float, epsilon: float = 0.0) -> TermStructureState:
    diff = vix3m - vix
    if diff > epsilon:
        return TermStructureState.CONTANGO
    if diff < -epsilon:
        return TermStructureState.BACKWARDATION
    # Tie -> default to contango per spec to avoid churn.
    return TermStructureState.CONTANGO


def compute_evrp(vix: float, erv30: float) -> float:
    return float(vix - erv30)
