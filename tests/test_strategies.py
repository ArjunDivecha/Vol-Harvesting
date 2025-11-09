from __future__ import annotations

from vol_edge.config import StrategyConfig, StrategyName
from vol_edge.signals import TermStructureState
from vol_edge.strategies import StrategyContext, build_strategy


def make_ctx(vix=20.0, vix3m=22.0, erv30=10.0, evrp=10.0, state=TermStructureState.CONTANGO):
    return StrategyContext(vix=vix, vix3m=vix3m, erv30=erv30, evrp=evrp, term_structure=state)


def test_passive_strategy_always_targets_20pct():
    cfg = StrategyConfig(name=StrategyName.PASSIVE)
    strat = build_strategy(cfg)
    decision = strat.target_weights(make_ctx())
    assert decision.weights["short_vol"] == 0.20


def test_evrp_strategy_goes_cash_when_negative():
    cfg = StrategyConfig(name=StrategyName.EVRP)
    strat = build_strategy(cfg)
    positive = strat.target_weights(make_ctx(evrp=1.0))
    assert positive.weights["short_vol"] == 0.20
    zero = strat.target_weights(make_ctx(evrp=-0.1))
    assert zero.weights.get("short_vol", 0.0) == 0.0


def test_evrp_boc_branches_cover_all_cases():
    cfg = StrategyConfig(name=StrategyName.EVRP_BOC)
    strat = build_strategy(cfg)
    contango_pos = strat.target_weights(make_ctx(evrp=1.0, state=TermStructureState.CONTANGO))
    assert contango_pos.weights["short_vol"] == 0.20
    contango_neg = strat.target_weights(make_ctx(evrp=-0.1, state=TermStructureState.CONTANGO))
    assert contango_neg.weights["short_vol"] == 0.10
    backward = strat.target_weights(make_ctx(evrp=-0.1, state=TermStructureState.BACKWARDATION))
    assert backward.weights["long_vol"] == 0.20


def test_evrp_boc_sizing_caps_exposure():
    cfg = StrategyConfig(name=StrategyName.EVRP_BOC_SIZING, max_vol_exposure_pct=0.30)
    strat = build_strategy(cfg)
    ctx = make_ctx(vix=18, evrp=1.0)
    decision = strat.target_weights(ctx)
    assert decision.weights["short_vol"] == min(0.18, 0.30)

    ctx2 = make_ctx(vix=30, evrp=-1.0, state=TermStructureState.CONTANGO)
    decision2 = strat.target_weights(ctx2)
    assert decision2.weights["short_vol"] == 0.15  # half sizing capped at 0.15

    ctx3 = make_ctx(vix=30, evrp=-1.0, state=TermStructureState.BACKWARDATION)
    decision3 = strat.target_weights(ctx3)
    assert decision3.weights["long_vol"] == 0.30  # capped by max exposure
