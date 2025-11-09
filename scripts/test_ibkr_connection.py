"""Simple IBKR connectivity test using ib_insync."""

from __future__ import annotations

import argparse

from ib_insync import IB


def main() -> None:
    parser = argparse.ArgumentParser(description="Test IBKR API connectivity")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7497)
    parser.add_argument("--client-id", type=int, default=5)
    args = parser.parse_args()

    ib = IB()
    print(f"Connecting to IBKR at {args.host}:{args.port} (client_id={args.client_id})...")
    ib.connect(args.host, args.port, clientId=args.client_id)
    current_time = ib.reqCurrentTime()
    print(f"Connected. IBKR current time: {current_time}")
    ib.disconnect()


if __name__ == "__main__":
    main()
