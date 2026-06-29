#!/usr/bin/env python3
"""Show Hyperliquid perpetual market stats: funding rate, open interest, mark price, 24h volume.

Read-only, no keys needed (public `metaAndAssetCtxs` info endpoint). Useful for picking a market:
funding tells you the cost/credit of holding a perp position; open interest and volume tell you how
liquid it is. Funding on Hyperliquid is charged hourly.

Usage:
    python market_stats.py                 # all perps, sorted by 24h volume
    python market_stats.py --filter ETH    # markets whose base matches ETH
    python market_stats.py --sort funding  # sort by absolute funding rate
    python market_stats.py --top 20        # only the top N rows
    python market_stats.py --json          # raw machine-readable JSON

No third-party dependencies (urllib). Mainnet by default; pass --testnet for testnet.
"""
import argparse
import json
import sys
import urllib.request

MAINNET = "https://api.hyperliquid.xyz/info"
TESTNET = "https://api.hyperliquid-testnet.xyz/info"


def _post(url: str, body: dict) -> object:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def perp_stats(url: str) -> list:
    meta, ctxs = _post(url, {"type": "metaAndAssetCtxs"})
    out = []
    for asset, ctx in zip(meta.get("universe", []), ctxs):
        name = asset.get("name", "")
        if ":" in name:  # skip HIP-3 dex-prefixed entries here; use list_markets.py --hip3
            continue
        funding = float(ctx.get("funding", 0))      # hourly funding rate (fraction)
        oi = float(ctx.get("openInterest", 0))      # in base units
        mark = float(ctx.get("markPx", 0) or 0)
        out.append({
            "hummingbot_pair": f"{name}-USD",
            "funding_hourly_pct": funding * 100,
            "funding_apr_pct": funding * 24 * 365 * 100,
            "open_interest_base": oi,
            "open_interest_usd": oi * mark,
            "mark_px": mark,
            "day_volume_usd": float(ctx.get("dayNtlVlm", 0) or 0),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Hyperliquid perp market stats (funding, OI, volume).")
    ap.add_argument("--filter", default=None, help="case-insensitive substring on the base asset")
    ap.add_argument("--sort", choices=["volume", "funding", "oi"], default="volume")
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()
    url = TESTNET if args.testnet else MAINNET

    rows = perp_stats(url)
    if args.filter:
        f = args.filter.upper()
        rows = [r for r in rows if f in r["hummingbot_pair"].upper()]

    key = {"volume": lambda r: r["day_volume_usd"],
           "funding": lambda r: abs(r["funding_hourly_pct"]),
           "oi": lambda r: r["open_interest_usd"]}[args.sort]
    rows.sort(key=key, reverse=True)
    if args.top:
        rows = rows[:args.top]

    if args.as_json:
        print(json.dumps(rows, indent=2))
        return 0

    print(f"\nHyperliquid perpetuals — funding charged hourly  (sorted by {args.sort})")
    print(f"  {'pair':16} {'funding/hr':>11} {'funding APR':>12} {'open interest':>16} "
          f"{'24h volume':>16}")
    for r in rows:
        print(f"  {r['hummingbot_pair']:16} {r['funding_hourly_pct']:>10.4f}% "
              f"{r['funding_apr_pct']:>11.1f}% ${r['open_interest_usd']:>14,.0f} "
              f"${r['day_volume_usd']:>14,.0f}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
