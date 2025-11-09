"""IBKR connection utilities."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass

from ib_insync import IB

from vol_edge.config import IBKRConnectionConfig


@dataclass
class IBKRClient(AbstractContextManager[IB]):
    """Context manager that connects to IBKR on enter and disconnects on exit."""

    config: IBKRConnectionConfig
    market_data_type: int = 3  # 3=delayed streaming, 4=delayed-frozen
    ib: IB | None = None

    def __enter__(self) -> IB:
        if self.ib is None:
            self.ib = IB()
        self.ib.connect(
            self.config.host,
            self.config.port,
            clientId=self.config.client_id,
            timeout=self.config.connect_timeout,
        )
        try:
            self.ib.reqMarketDataType(self.market_data_type)
        except Exception:
            # If the client does not support changing data type we just continue.
            pass
        return self.ib

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.ib is not None:
            self.ib.disconnect()
