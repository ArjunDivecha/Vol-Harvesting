"""IBKR execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ib_insync import Contract, IB, Order, Ticker

from vol_edge.config import AppConfig, InstrumentConfig
from vol_edge.data.ibkr.client import IBKRClient


def build_contract(instr: InstrumentConfig) -> Contract:
    contract = Contract()
    contract.symbol = instr.symbol
    contract.secType = "STK"
    contract.exchange = instr.exchange or "SMART"
    contract.currency = instr.currency
    return contract


def get_positions(ib: IB, account_id: str | None = None) -> Dict[str, float]:
    positions = ib.positions()
    holdings: Dict[str, float] = {}
    for pos in positions:
        if account_id and getattr(pos, "account", "") != account_id:
            continue
        symbol = pos.contract.symbol
        holdings[symbol] = holdings.get(symbol, 0.0) + float(pos.position)
    return holdings


@dataclass
class TradeExecutor:
    config: AppConfig

    def __post_init__(self) -> None:
        self.client = IBKRClient(self.config.data.ibkr)

    def place_moc_order(self, instrument: InstrumentConfig, quantity: float, ib: Optional[IB] = None) -> str:
        qty = int(round(quantity))
        if qty == 0:
            return ""

        def _submit(conn: IB) -> str:
            contract = build_contract(instrument)
            order = Order()
            order.action = "BUY" if qty > 0 else "SELL"
            order.orderType = "MOC"
            order.totalQuantity = abs(qty)
            if self.config.execution.account_id:
                order.account = self.config.execution.account_id
            trade = conn.placeOrder(contract, order)
            return str(trade.order.orderId)

        if ib is None:
            with self.client as conn:
                return _submit(conn)
        return _submit(ib)


def get_last_price(ib: IB, instrument: InstrumentConfig) -> float:
    contract = build_contract(instrument)
    tickers = ib.reqTickers(contract)
    if not tickers:
        raise RuntimeError(f"No ticker data for {instrument.symbol}")
    ticker = tickers[0]
    price = ticker.marketPrice()
    if not price or price != price or price <= 0:
        price = ticker.last if ticker.last and ticker.last > 0 else ticker.close
    if not price or price <= 0:
        raise RuntimeError(f"No valid price for {instrument.symbol}")
    return float(price)
