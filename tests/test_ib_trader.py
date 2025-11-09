from __future__ import annotations

from types import SimpleNamespace

import pytest

from vol_edge.config import load_config
from vol_edge.exec.ib_trader import TradeExecutor, build_contract, get_positions, get_last_price


def test_build_contract_defaults():
    contract = build_contract(SimpleNamespace(symbol="UVXY", exchange=None, currency="USD"))
    assert contract.symbol == "UVXY"
    assert contract.exchange == "SMART"


def test_get_positions(monkeypatch):
    fake_ib = SimpleNamespace(
        positions=lambda: [
            SimpleNamespace(account="U1", contract=SimpleNamespace(symbol="UVXY"), position=10),
            SimpleNamespace(account="U2", contract=SimpleNamespace(symbol="SVXY"), position=5),
        ]
    )
    holdings = get_positions(fake_ib, account_id="U1")
    assert holdings["UVXY"] == 10


def test_trade_executor_places_moc(monkeypatch):
    orders = []

    def fake_place_order(contract, order):
        orders.append(order)
        return SimpleNamespace(order=SimpleNamespace(orderId=123))

    fake_ib = SimpleNamespace(placeOrder=fake_place_order)

    class FakeClient:
        def __init__(self, cfg):
            pass

        def __enter__(self):
            return fake_ib

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("vol_edge.exec.ib_trader.IBKRClient", FakeClient)

    config = load_config(
        {
            "instruments": {"long_vol": {"symbol": "UVXY"}, "short_vol": {"symbol": "SVXY"}},
            "backtest": {"start_date": "2020-01-01"},
            "execution": {"account_id": "U1"},
        }
    )

    executor = TradeExecutor(config)
    order_id = executor.place_moc_order(config.instruments.long_vol, 100, ib=fake_ib)
    assert order_id == "123"
    assert orders[-1].orderType == "MOC"
    assert orders[-1].account == "U1"


def test_get_last_price(monkeypatch):
    class FakeTicker:
        def __init__(self):
            self._price = 12.34
            self.last = 0
            self.close = 0

        def marketPrice(self):
            return self._price

    fake_ib = SimpleNamespace(reqTickers=lambda contract: [FakeTicker()])
    price = get_last_price(fake_ib, SimpleNamespace(symbol="UVXY", exchange="ARCA", currency="USD"))
    assert price == 12.34
