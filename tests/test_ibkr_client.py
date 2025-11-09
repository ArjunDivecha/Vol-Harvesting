from __future__ import annotations

from unittest.mock import MagicMock

from vol_edge.config import IBKRConnectionConfig
from vol_edge.data.ibkr.client import IBKRClient


def test_ibkr_client_connects_and_disconnects(monkeypatch):
    fake_ib = MagicMock()
    monkeypatch.setattr("vol_edge.data.ibkr.client.IB", lambda: fake_ib)

    cfg = IBKRConnectionConfig(host="1.2.3.4", port=4000, client_id=42, connect_timeout=5)
    with IBKRClient(cfg) as conn:
        assert conn is fake_ib

    fake_ib.connect.assert_called_once_with("1.2.3.4", 4000, clientId=42, timeout=5)
    fake_ib.disconnect.assert_called_once()
