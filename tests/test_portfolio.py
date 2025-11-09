from vol_edge.portfolio import PortfolioState, RebalanceEngine


def test_portfolio_weights_and_equity():
    state = PortfolioState(cash=1000, holdings={"SVIX": 50})
    prices = {"SVIX": 10.0}
    assert state.equity(prices) == 1000 + 500
    weights = state.weights(prices)
    assert round(weights["SVIX"], 4) == round(500 / 1500, 4)


def test_apply_orders_updates_cash_and_holdings():
    state = PortfolioState(cash=1000, holdings={})
    prices = {"SVIX": 5.0}
    state.apply_orders({"SVIX": 100}, prices, cost_bps=0)
    assert state.cash == 1000 - 500
    assert state.holdings["SVIX"] == 100


def test_rebalance_engine_respects_threshold():
    state = PortfolioState(cash=0, holdings={"SVIX": 10})
    prices = {"SVIX": 10.0}
    engine = RebalanceEngine(threshold_pct=0.02)
    # current weight is 1.0, small tweak below threshold -> no order
    orders = engine.generate_orders(state, {"SVIX": 0.99}, prices)
    assert orders == {}
    # big change -> order
    orders = engine.generate_orders(state, {"SVIX": 0.5}, prices)
    assert "SVIX" in orders
