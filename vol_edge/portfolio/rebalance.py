"""Rebalance logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .state import PortfolioState


@dataclass
class RebalanceEngine:
    threshold_pct: float

    def generate_orders(
        self,
        portfolio: PortfolioState,
        target_weights: Dict[str, float],
        prices: Dict[str, float],
    ) -> Dict[str, float]:
        equity = portfolio.equity(prices)
        orders: Dict[str, float] = {}
        if equity <= 0:
            return orders
        current_weights = portfolio.weights(prices)
        symbols = set(target_weights) | set(portfolio.holdings)
        for sym in symbols:
            current_weight = current_weights.get(sym, 0.0)
            target_weight = target_weights.get(sym, 0.0)
            if abs(target_weight - current_weight) <= self.threshold_pct:
                continue
            price = prices[sym]
            target_value = target_weight * equity
            current_shares = portfolio.holdings.get(sym, 0.0)
            target_shares = target_value / price
            delta = target_shares - current_shares
            if abs(delta) > 1e-9:
                orders[sym] = delta
        return orders
