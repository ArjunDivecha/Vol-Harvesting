"""Configuration models and loader for the Volatility Edge backtest."""

from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml
from pydantic import BaseModel, Field, PositiveFloat, field_validator, model_validator


class StrategyName(str, Enum):
    """Supported strategy flavors from Table 2."""

    PASSIVE = "passive"
    EVRP = "evrp"
    EVRP_BOC = "evrp_boc"
    EVRP_BOC_SIZING = "evrp_boc_sizing"


class InstrumentConfig(BaseModel):
    symbol: str
    exchange: Optional[str] = None
    currency: str = "USD"
    multiplier: float = 1.0


class InstrumentsConfig(BaseModel):
    long_vol: InstrumentConfig
    short_vol: InstrumentConfig


class YFinanceConfig(BaseModel):
    session_tz: str = "America/New_York"


class CsvPaths(BaseModel):
    spy: Path
    vix: Path
    vix3m: Path
    long_vol: Path
    short_vol: Path


class DataProvider(str, Enum):
    YFINANCE = "yfinance"
    CSV = "csv"
    IBKR = "ibkr"


class IBKRConnectionConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7496
    client_id: int = 7
    connect_timeout: float = 10.0


class DataConfig(BaseModel):
    provider: DataProvider = DataProvider.YFINANCE
    yfinance: YFinanceConfig = Field(default_factory=YFinanceConfig)
    csv: Optional[CsvPaths] = None
    ibkr: IBKRConnectionConfig = Field(default_factory=IBKRConnectionConfig)

    @model_validator(mode="after")
    def _validate_payload(self) -> "DataConfig":
        if self.provider == DataProvider.CSV and self.csv is None:
            raise ValueError("csv provider requires csv paths")
        if self.provider == DataProvider.IBKR and not self.ibkr:
            raise ValueError("ibkr provider requires ibkr configuration")
        return self


class StrategyConfig(BaseModel):
    name: StrategyName = StrategyName.EVRP_BOC_SIZING
    rebalance_threshold_pct: float = Field(0.02, ge=0.0)
    trade_cost_bps: float = 0.0
    term_structure_epsilon: float = 0.0
    max_vol_exposure_pct: float = Field(0.40, gt=0.0, le=1.0)
    size_rule_divisor: PositiveFloat = 100.0
    half_sizing_in_contango_when_neg_evrp: bool = True


class BacktestConfig(BaseModel):
    start_date: date
    end_date: Optional[date] = None
    initial_equity: PositiveFloat = 1_000_000.0
    benchmark_symbol: str = "SPY"

    @field_validator("end_date")
    @classmethod
    def end_not_before_start(cls, end_date: Optional[date], info):
        start_date = info.data.get("start_date")
        if end_date and start_date and end_date < start_date:
            raise ValueError("end_date must be on/after start_date")
        return end_date


class RiskConfig(BaseModel):
    nav_dislocation_check: bool = False
    dislocation_max_premium_pct: float = 3.0


class LoggingConfig(BaseModel):
    level: str = "INFO"


class AppConfig(BaseModel):
    instruments: InstrumentsConfig
    data: DataConfig = Field(default_factory=DataConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    backtest: BacktestConfig
    risk: RiskConfig = Field(default_factory=RiskConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_config(source: Union[str, Path, Dict[str, Any]]) -> AppConfig:
    """Load and validate the application config from a path or raw mapping."""

    if isinstance(source, (str, Path)):
        path = Path(source)
        payload = yaml.safe_load(path.read_text()) or {}
    elif isinstance(source, dict):
        payload = source
    else:
        raise TypeError("config source must be a path or mapping")

    return AppConfig.model_validate(payload)


__all__ = [
    "AppConfig",
    "BacktestConfig",
    "DataConfig",
    "DataProvider",
    "IBKRConnectionConfig",
    "InstrumentConfig",
    "InstrumentsConfig",
    "LoggingConfig",
    "RiskConfig",
    "StrategyConfig",
    "StrategyName",
    "load_config",
]
