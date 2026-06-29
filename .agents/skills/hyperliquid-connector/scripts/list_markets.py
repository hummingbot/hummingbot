#!/usr/bin/env python3
"""List tradable Hyperliquid markets and their key trading rules.

There is no `hbot` command for trading rules yet, so this fills the gap: it queries the public
Hyperliquid `info` endpoint (no auth, no keys) and prints the perpetual and spot markets in the
`BASE-QUOTE` form Hummingbot expects, plus the fields you need to size orders correctly
(size decimals, max leverage). Use it before configuring a strategy to confirm a pair exists and
to avoid the minimum-notional trap.

Usage:
    python list_markets.py                 # perps + spot, summary table
    python list_markets.py --type perp     # perps only
    python list_markets.py --type spot     # spot only
    python list_markets.py --filter ETH    # only markets whose base matches ETH
    python list_markets.py --hip3          # builder-deployed (HIP-3) perp dexs + their markets
    python list_markets.py --json          # raw machine-readable JSON

HIP-3 builder-deployed perps live in SEPARATE dex universes — they are NOT in the default `meta`.
--hip3 enumerates them via `perpDexs` + per-dex `meta`. Their exchange symbol is `<dex>:<ASSET>`;
whether the Hummingbot connector can trade them is unverified — treat as advanced/experimental.

No third-party dependencies (uses urllib). Mainnet by default; pass --testnet for testnet.
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


def perp_markets(url: str) -> list:
    """Perp universe. Coin names are bare (e.g. 'ETH'); Hummingbot pair is '<COIN>-USD'.

    HIP-3 builder-deployed perps appear with a dex prefix ('<dex>:<ASSET>'); these are advanced and
    may not be supported by the Hummingbot connector yet — flagged in the output.
    """
    meta = _post(url, {"type": "meta"})
    out = []
    for a in meta.get("universe", []):
        name = a.get("name", "")
        hip3 = ":" in name
        base = name.split(":", 1)[1] if hip3 else name
        out.append({
            "exchange_symbol": name,
            "hummingbot_pair": f"{base}-USD",
            "max_leverage": a.get("maxLeverage"),
            "size_decimals": a.get("szDecimals"),
            "hip3": hip3,
            "delisted": a.get("isDelisted", False),
        })
    return out


def hip3_dexs(url: str) -> list:
    """Builder-deployed (HIP-3) perp dexs and their markets.

    `perpDexs` lists the builder dexs (the first entry is null = the main dex). Each named dex has
    its own `meta` universe, queried with {"type":"meta","dex":"<name>"}.
    """
    dexs = _post(url, {"type": "perpDexs"})
    out = []
    for d in dexs:
        if not d:  # the main (non-HIP-3) dex is null
            continue
        name = d.get("name", "")
        try:
            meta = _post(url, {"type": "meta", "dex": name})
            # Per-dex `meta` already returns dex-prefixed asset names (e.g. 'xyz:XYZ100'); use as-is.
            markets = [{
                "exchange_symbol": a.get("name", ""),
                "max_leverage": a.get("maxLeverage"),
                "size_decimals": a.get("szDecimals"),
            } for a in meta.get("universe", [])]
        except Exception as e:  # surface, don't swallow — the user needs to know a dex failed
            markets = [{"error": str(e)}]
        out.append({
            "dex": name,
            "deployer": d.get("deployer"),
            "full_name": d.get("full_name"),
            "markets": markets,
        })
    return out


def spot_markets(url: str) -> list:
    """Spot universe. Pairs are '<BASE>-<QUOTE>' (e.g. 'PURR-USDC')."""
    sm = _post(url, {"type": "spotMeta"})
    tokens = {t["index"]: t["name"] for t in sm.get("tokens", [])}
    out = []
    for p in sm.get("universe", []):
        idx = p.get("tokens", [])
        if len(idx) != 2:
            continue
        base, quote = tokens.get(idx[0], "?"), tokens.get(idx[1], "?")
        out.append({
            "exchange_symbol": p.get("name", ""),
            "hummingbot_pair": f"{base}-{quote}",
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="List tradable Hyperliquid markets.")
    ap.add_argument("--type", choices=["perp", "spot", "all"], default="all")
    ap.add_argument("--filter", default=None, help="case-insensitive substring on the base asset")
    ap.add_argument("--hip3", action="store_true", help="list HIP-3 builder-deployed perp dexs")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--testnet", action="store_true")
    args = ap.parse_args()
    url = TESTNET if args.testnet else MAINNET

    if args.hip3:
        dexs = hip3_dexs(url)
        if args.as_json:
            print(json.dumps(dexs, indent=2))
            return 0
        print(f"\nHIP-3 builder-deployed perp dexs ({len(dexs)}) — "
              f"advanced; Hummingbot connector support UNVERIFIED")
        for d in dexs:
            print(f"\n  dex '{d['dex']}'  ({d.get('full_name') or '—'})  deployer={d.get('deployer')}")
            for m in d["markets"]:
                if "error" in m:
                    print(f"    ! failed to load: {m['error']}")
                else:
                    print(f"    {m['exchange_symbol']:24} max_lev={m['max_leverage']} "
                          f"sz_dec={m['size_decimals']}")
        print()
        return 0

    data = {}
    if args.type in ("perp", "all"):
        data["perp"] = perp_markets(url)
    if args.type in ("spot", "all"):
        data["spot"] = spot_markets(url)

    if args.filter:
        f = args.filter.upper()
        for k in data:
            data[k] = [m for m in data[k] if f in m["hummingbot_pair"].upper()]

    if args.as_json:
        print(json.dumps(data, indent=2))
        return 0

    if "perp" in data:
        print(f"\nPERPETUAL  ({len(data['perp'])} markets) — connector: hyperliquid_perpetual")
        print(f"  {'hummingbot pair':20} {'max lev':>7} {'sz dec':>6}  notes")
        for m in sorted(data["perp"], key=lambda x: x["hummingbot_pair"]):
            notes = []
            if m["hip3"]:
                notes.append("HIP-3 (verify connector support)")
            if m["delisted"]:
                notes.append("delisted")
            print(f"  {m['hummingbot_pair']:20} {str(m['max_leverage']):>7} "
                  f"{str(m['size_decimals']):>6}  {', '.join(notes)}")
    if "spot" in data:
        print(f"\nSPOT  ({len(data['spot'])} markets) — connector: hyperliquid")
        for m in sorted(data["spot"], key=lambda x: x["hummingbot_pair"]):
            print(f"  {m['hummingbot_pair']:20} (exchange symbol: {m['exchange_symbol']})")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
