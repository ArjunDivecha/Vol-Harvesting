"""Strategy factory."""

from __future__ import annotations

from vol_edge.config import StrategyConfig, StrategyName

from .base import Strategy
from .impl import EVRPBoCStrategy, EVRPBoCSizingStrategy, EVRPStrategy, StaticShortVol


def build_strategy(config: StrategyConfig) -> Strategy:
    if config.name is StrategyName.PASSIVE:
        return StaticShortVol(config, target_weight=min(0.20, config.max_vol_exposure_pct))
    if config.name is StrategyName.EVRP:
        return EVRPStrategy(config)
    if config.name is StrategyName.EVRP_BOC:
        return EVRPBoCStrategy(config)
    if config.name is StrategyName.EVRP_BOC_SIZING:
        return EVRPBoCSizingStrategy(config)
    raise ValueError(f"Unknown strategy name: {config.name}")
