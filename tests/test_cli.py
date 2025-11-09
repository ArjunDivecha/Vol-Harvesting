import json
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _write_csv(path: Path, values):
    dates = pd.date_range("2020-01-01", periods=len(values), freq="B")
    df = pd.DataFrame(
        {
            "date": dates,
            "open": values,
            "high": [v * 1.01 for v in values],
            "low": [v * 0.99 for v in values],
            "close": values,
            "adj_close": values,
            "volume": 1000,
        }
    )
    df.to_csv(path, index=False)


def test_cli_backtest(tmp_path):
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    length = 25
    _write_csv(csv_dir / "spy.csv", [100 + i * 0.2 for i in range(length)])
    _write_csv(csv_dir / "vix.csv", [18 + (i % 3) for i in range(length)])
    _write_csv(csv_dir / "vix3m.csv", [20 + (i % 2) for i in range(length)])
    _write_csv(csv_dir / "uvxy.csv", [15 - 0.1 * i for i in range(length)])
    _write_csv(csv_dir / "svix.csv", [40 + 0.3 * i for i in range(length)])

    config = tmp_path / "config.yml"
    config.write_text(
        f"""
        instruments:
          long_vol: {{symbol: UVXY}}
          short_vol: {{symbol: SVIX}}
        data:
          provider: csv
          csv:
            spy: {csv_dir / 'spy.csv'}
            vix: {csv_dir / 'vix.csv'}
            vix3m: {csv_dir / 'vix3m.csv'}
            long_vol: {csv_dir / 'uvxy.csv'}
            short_vol: {csv_dir / 'svix.csv'}
        backtest:
          start_date: 2020-01-01
          end_date: 2020-02-10
        """
    )

    result = subprocess.run(
        [sys.executable, "-m", "vol_edge.cli", "backtest", "--config", str(config)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout.strip())
    assert payload["records"] > 0
    assert payload["final_equity"] > 0
