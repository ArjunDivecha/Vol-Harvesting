"""Strategy base classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from vol_edge.config import StrategyConfig
from vol_edge.signals import TermStructureState


@dataclass
class StrategyContext:
    vix: float
    vix3m: float
    erv30: float
    evrp: float
    term_structure: TermStructureState


@dataclass
class StrategyDecision:
    weights: Dict[str, float] = field(default_factory=dict)


class Strategy:
    def __init__(self, config: StrategyConfig):
        self.config = config

    def target_weights(self, ctx: StrategyContext) -> StrategyDecision:  # pragma: no cover - interface
        raise NotImplementedError

    def _bounded(self, value: float) -> float:
        return max(-self.config.max_vol_exposure_pct, min(self.config.max_vol_exposure_pct, value))
