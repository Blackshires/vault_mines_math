"""Minimal Stake Engine RGS probe for a stateful Vault Mines round.

This script is intentionally separate from the math/runtime implementation. It
exists only to inspect how a real RGS environment behaves for /bet/action.

By default it is DRY RUN and will not send any request that can create a bet.
Pass --execute only against a test/mock Stake Engine environment.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def _post(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return {
                "httpStatus": response.status,
                "body": json.loads(raw) if raw else None,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return {"httpStatus": exc.code, "body": parsed}
    except urllib.error.URLError as exc:
        return {"networkError": str(exc.reason)}


def _pretty(label: str, value: Any) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def _planned_requests(args: argparse.Namespace) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = [
        {
            "path": "/wallet/authenticate",
            "payload": {"sessionID": args.session_id, "language": args.language},
        },
    ]

    if args.start_round:
        play_payload: dict[str, Any] = {
            "sessionID": args.session_id,
            "amount": args.amount,
            "currency": args.currency,
            "mode": args.mode,
        }
        if args.mines is not None:
            play_payload["meta"] = {"mines": args.mines}
        requests.append({"path": "/wallet/play", "payload": play_payload})

    action_meta: dict[str, Any] = {"cell": args.cell}
    if args.mines is not None:
        action_meta["mines"] = args.mines

    requests.append(
        {
            "path": "/bet/action",
            "payload": {
                "sessionID": args.session_id,
                "action": "DECISION",
                "meta": action_meta,
            },
        }
    )

    requests.append(
        {
            "path": "/wallet/authenticate",
            "payload": {"sessionID": args.session_id, "language": args.language},
        }
    )

    if args.end_round:
        requests.append(
            {
                "path": "/wallet/end-round",
                "payload": {"sessionID": args.session_id},
            }
        )

    return requests


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Stake Engine /bet/action DECISION behaviour."
    )
    parser.add_argument("--rgs-url", required=True, help="Example: https://rgs.example.com")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--cell", type=int, default=7)
    parser.add_argument("--language", default="en")
    parser.add_argument("--mode", default="base")
    parser.add_argument("--amount", type=int, default=10)
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--mines", type=int, choices=range(1, 21))
    parser.add_argument(
        "--start-round",
        action="store_true",
        help="Also call /wallet/play before /bet/action. This can debit a bet.",
    )
    parser.add_argument(
        "--end-round",
        action="store_true",
        help="Call /wallet/end-round after probing the action.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually send the requests. Without this flag the script is dry-run only.",
    )
    args = parser.parse_args()

    if not 0 <= args.cell < 25:
        parser.error("--cell must be between 0 and 24")

    planned = _planned_requests(args)
    _pretty("PLANNED REQUESTS", planned)

    if not args.execute:
        print(
            "\nDRY RUN ONLY. No request was sent. "
            "Add --execute only on a test/mock RGS session."
        )
        return 0

    if args.start_round:
        print(
            "\nWARNING: --start-round sends /wallet/play and may debit the supplied "
            "session. Continue only if this is a test/mock environment."
        )

    for request in planned:
        result = _post(args.rgs_url, request["path"], request["payload"])
        _pretty(request["path"], result)

        # If Play fails, a following DECISION cannot teach us anything useful.
        if request["path"] == "/wallet/play" and result.get("httpStatus") not in range(200, 300):
            print("\n/play failed; stopping before /bet/action.")
            return 2

        # Do not automatically continue to EndRound after a network failure.
        if "networkError" in result:
            print("\nNetwork failure; stopping probe.")
            return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
