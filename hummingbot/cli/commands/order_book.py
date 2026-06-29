"""``hbot order-book`` — bid/ask depth for a pair on an exchange.

Read-only public market data, fetched ad-hoc (no running bot): builds a connector, waits for the
order book, reads the top-N levels, tears down. The pair is fuzzy-matched against the exchange's
universe (mirrors Hummingbot's ``order_book`` command, but standalone).
"""
import asyncio
from typing import List, Tuple

import typer

from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import login


async def _run(ccm, exchange: str, pair: str, lines: int, timeout: float,
               json_output: bool) -> Tuple[dict, str, List[str]]:
    from hummingbot.cli.commands._market_data import all_pairs, make_connector, resolve_or_fail, wait_orderbook_ready
    lister = await make_connector(ccm, exchange, [], json_output)
    matched, alts = resolve_or_fail(await asyncio.wait_for(all_pairs(lister), timeout), pair, json_output)

    conn = await make_connector(ccm, exchange, [matched], json_output)
    try:
        await asyncio.wait_for(wait_orderbook_ready(conn, timeout), timeout)
        ob = conn.get_order_book(matched)
        bids = ob.snapshot[0][["price", "amount"]].head(lines)
        asks = ob.snapshot[1][["price", "amount"]].head(lines)
        data = {
            "bids": [{"price": float(p), "amount": float(a)} for p, a in bids.itertuples(index=False)],
            "asks": [{"price": float(p), "amount": float(a)} for p, a in asks.itertuples(index=False)],
        }
    finally:
        await conn.stop_network()
    return data, matched, alts


def _render(data: dict, exchange: str, matched: str, query: str, alts: List[str]) -> str:
    head = f"  {exchange}  {matched}"
    if matched.upper() != query.upper().replace("_", "-").replace("/", "-"):
        head += f"   [fuzzy-matched from '{query}']"
    out = [head, f"    {'bid price':>14} {'bid amt':>14}   {'ask price':>14} {'ask amt':>14}"]
    n = max(len(data["bids"]), len(data["asks"]))
    for i in range(n):
        b = data["bids"][i] if i < len(data["bids"]) else None
        a = data["asks"][i] if i < len(data["asks"]) else None
        bp = f"{b['price']:>14g}" if b else " " * 14
        ba = f"{b['amount']:>14g}" if b else " " * 14
        ap = f"{a['price']:>14g}" if a else " " * 14
        aa = f"{a['amount']:>14g}" if a else " " * 14
        out.append(f"    {bp} {ba}   {ap} {aa}")
    if alts:
        out.append(f"\n  also matched: {', '.join(alts)}")
    return "\n".join(out)


def order_book(
    exchange: str = typer.Argument(..., help="Exchange, e.g. hyperliquid_perpetual or binance."),
    pair: str = typer.Argument(..., help="Trading pair (fuzzy), e.g. ETH-USD, btc/usdt."),
    lines: int = typer.Option(5, "-n", "--lines", help="Number of price levels per side (default 5)."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show the order-book depth (top levels of bids and asks) for a pair on an exchange."""
    ccm, _ = login(password_stdin=password_stdin, json_output=json_output)
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        data, matched, alts = asyncio.run(_run(ccm, exchange, pair, lines, timeout, json_output))
    except asyncio.TimeoutError:
        fail("timed out waiting for the order book", ExitCode.TIMEOUT, json_output=json_output)

    if json_output:
        print_json({"ok": True, "exchange": exchange, "query": pair, "matched": matched,
                    "alternatives": alts, "order_book": data})
    else:
        typer.echo(_render(data, exchange, matched, pair, alts))
