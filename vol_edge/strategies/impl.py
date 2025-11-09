"""Concrete strategy implementations."""

from __future__ import annotations

from dataclasses import dataclass

from vol_edge.config import StrategyConfig
from vol_edge.signals import TermStructureState

from .base import Strategy, StrategyContext, StrategyDecision


@dataclass
class StaticShortVol(Strategy):
    def __init__(self, config: StrategyConfig, target_weight: float):
        super().__init__(config)
        self.target_weight = target_weight

    def target_weights(self, ctx: StrategyContext) -> StrategyDecision:
        weight = self._bounded(self.target_weight)
        return StrategyDecision({"short_vol": weight})


class EVRPStrategy(Strategy):
    def target_weights(self, ctx: StrategyContext) -> StrategyDecision:
        weight = 0.0
        if ctx.evrp > 0:
            weight = min(0.20, self.config.max_vol_exposure_pct)
        return StrategyDecision({"short_vol": weight})


class EVRPBoCStrategy(Strategy):
    def target_weights(self, ctx: StrategyContext) -> StrategyDecision:
        weight = {"short_vol": 0.0, "long_vol": 0.0}
        if ctx.evrp > 0 and ctx.term_structure is TermStructureState.CONTANGO:
            weight["short_vol"] = min(0.20, self.config.max_vol_exposure_pct)
        elif ctx.evrp <= 0 and ctx.term_structure is TermStructureState.CONTANGO:
            weight["short_vol"] = min(0.10, self.config.max_vol_exposure_pct)
        elif ctx.evrp <= 0 and ctx.term_structure is TermStructureState.BACKWARDATION:
            weight["long_vol"] = min(0.20, self.config.max_vol_exposure_pct)
        return StrategyDecision({k: self._bounded(v) for k, v in weight.items() if v})


class EVRPBoCSizingStrategy(Strategy):
    def target_weights(self, ctx: StrategyContext) -> StrategyDecision:
        vix_pct = min(ctx.vix / self.config.size_rule_divisor, self.config.max_vol_exposure_pct)
        decision: dict[str, float] = {"short_vol": 0.0, "long_vol": 0.0}
        if ctx.evrp > 0 and ctx.term_structure is TermStructureState.CONTANGO:
            decision["short_vol"] = vix_pct
        elif ctx.evrp < 0 and ctx.term_structure is TermStructureState.CONTANGO:
            if self.config.half_sizing_in_contango_when_neg_evrp:
                decision["short_vol"] = min(vix_pct * 0.5, self.config.max_vol_exposure_pct)
            else:
                decision["short_vol"] = 0.0
        elif ctx.evrp < 0 and ctx.term_structure is TermStructureState.BACKWARDATION:
            decision["long_vol"] = vix_pct
        # else stay cash
        return StrategyDecision({k: self._bounded(v) for k, v in decision.items() if v})
