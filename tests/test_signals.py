import math

import pandas as pd
import pytest

from vol_edge.signals import TermStructureState, compute_erv30, compute_evrp, compute_term_structure_state


def test_compute_erv30_matches_manual_std():
    prices = [100 + i for i in range(12)]
    result = compute_erv30(prices)
    returns = pd.Series(prices).pct_change().dropna().tail(10)
    expected = returns.std(ddof=0) * math.sqrt(252) * 100
    assert result == pytest.approx(expected)


def test_compute_erv30_requires_enough_data():
    with pytest.raises(ValueError):
        compute_erv30([100, 101])


def test_term_structure_state_with_epsilon():
    assert compute_term_structure_state(15, 17, epsilon=0.1) is TermStructureState.CONTANGO
    assert compute_term_structure_state(17, 15) is TermStructureState.BACKWARDATION
    # tie should go to contango
    assert compute_term_structure_state(20.0, 20.0) is TermStructureState.CONTANGO


def test_evrp_calculation():
    assert compute_evrp(18.0, 12.5) == pytest.approx(5.5)
