"""Print current IBKR holdings for a given account."""

from __future__ import annotations

import argparse
import json

from ib_insync import IB


def main() -> None:
    parser = argparse.ArgumentParser(description="Show IBKR positions")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7496)
    parser.add_argument("--client-id", type=int, default=5)
    parser.add_argument("--account", help="Account id to filter (e.g., U14983106)", default=None)
    args = parser.parse_args()

    ib = IB()
    ib.connect(args.host, args.port, clientId=args.client_id)
    positions = ib.positions()
    holdings = []
    for pos in positions:
        if args.account and pos.account != args.account:
            continue
        holdings.append(
            {
                "account": pos.account,
                "symbol": pos.contract.symbol,
                "exchange": pos.contract.exchange,
                "position": float(pos.position),
                "avg_cost": float(getattr(pos, "avgCost", 0.0)),
            }
        )
    print(json.dumps(holdings, indent=2))
    ib.disconnect()


if __name__ == "__main__":
    main()
