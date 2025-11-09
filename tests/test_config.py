from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from vol_edge.config import DataProvider, StrategyName, load_config


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "test_config.yml"
    path.write_text(dedent(text))
    return path


def test_load_config_applies_defaults(tmp_path):
    config_path = write_config(
        tmp_path,
        """
        instruments:
          long_vol:
            symbol: UVXY
          short_vol:
            symbol: SVIX
        data:
          provider: yfinance
        strategy:
          name: evrp_boc_sizing
        backtest:
          start_date: 2010-01-01
          end_date: 2011-01-01
        """,
    )

    config = load_config(config_path)

    assert config.backtest.start_date == date(2010, 1, 1)
    assert config.strategy.name is StrategyName.EVRP_BOC_SIZING
    assert config.strategy.trade_cost_bps == 0
    assert config.strategy.rebalance_threshold_pct == pytest.approx(0.02)
    assert config.instruments.long_vol.symbol == "UVXY"
    assert config.instruments.short_vol.symbol == "SVIX"


def test_csv_provider_requires_all_paths(tmp_path):
    config_path = write_config(
        tmp_path,
        """
        instruments:
          long_vol:
            symbol: UVXY
          short_vol:
            symbol: SVIX
        data:
          provider: csv
          csv:
            spy: data/spy.csv
            long_vol: data/uvxy.csv
        backtest:
          start_date: 2010-01-01
        """,
    )

    with pytest.raises(ValidationError):
        load_config(config_path)


def test_ibkr_provider_uses_defaults():
    config = load_config(
        {
            "instruments": {
                "long_vol": {"symbol": "UVXY"},
                "short_vol": {"symbol": "SVIX"},
            },
            "data": {
                "provider": "ibkr",
            },
            "backtest": {"start_date": "2020-01-01", "end_date": "2020-02-01"},
        }
    )

    assert config.data.provider is DataProvider.IBKR
    assert config.data.ibkr.host == "127.0.0.1"


def test_execution_config_defaults():
    config = load_config(
        {
            "instruments": {
                "long_vol": {"symbol": "UVXY"},
                "short_vol": {"symbol": "SVXY"},
            },
            "backtest": {"start_date": "2020-01-01"},
            "execution": {
                "moc_deadline_minutes_before_close": 10,
            },
        }
    )

    exec_cfg = config.execution
    assert exec_cfg.moc_deadline_minutes_before_close == 10
    assert exec_cfg.fallback_loc_offset_bps == 5
    assert exec_cfg.max_retries == 2
    assert exec_cfg.account_id is None
