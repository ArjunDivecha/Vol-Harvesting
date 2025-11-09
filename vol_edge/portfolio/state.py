"""Portfolio state representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PortfolioState:
    cash: float = 0.0
    holdings: Dict[str, float] = field(default_factory=dict)

    def equity(self, prices: Dict[str, float]) -> float:
        return self.cash + sum(self.holdings.get(sym, 0.0) * prices.get(sym, 0.0) for sym in self.holdings)

    def weights(self, prices: Dict[str, float]) -> Dict[str, float]:
        equity = self.equity(prices)
        if equity == 0:
            return {sym: 0.0 for sym in self.holdings}
        return {sym: (shares * prices.get(sym, 0.0)) / equity for sym, shares in self.holdings.items()}

    def apply_orders(self, orders: Dict[str, float], prices: Dict[str, float], cost_bps: float = 0.0) -> None:
        for sym, shares_delta in orders.items():
            price = prices[sym]
            value = shares_delta * price
            fee = abs(value) * cost_bps / 10000.0
            self.cash -= value + fee
            self.holdings[sym] = self.holdings.get(sym, 0.0) + shares_delta

    def copy(self) -> "PortfolioState":
        return PortfolioState(cash=self.cash, holdings=dict(self.holdings))
