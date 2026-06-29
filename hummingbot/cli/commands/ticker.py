"""``hbot ticker`` — best bid/ask/mid/last for a pair on an exchange.

Read-only public market data, fetched ad-hoc (no running bot): builds a connector, waits for the
order book, reads the prices, tears down. The pair is fuzzy-matched against the exchange's universe.
"""
import asyncio
from typing import List, Tuple

import typer

from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import login


async def _run(ccm, exchange: str, pair: str, timeout: float, json_output: bool) -> Tuple[dict, str, List[str]]:
    from hummingbot.cli.commands._market_data import all_pairs, make_connector, resolve_or_fail, wait_orderbook_ready
    from hummingbot.core.data_type.common import PriceType
    lister = await make_connector(ccm, exchange, [], json_output)
    matched, alts = resolve_or_fail(await asyncio.wait_for(all_pairs(lister), timeout), pair, json_output)

    conn = await make_connector(ccm, exchange, [matched], json_output)
    try:
        await asyncio.wait_for(wait_orderbook_ready(conn, timeout), timeout)
        # Derive bid/ask/mid from the order-book snapshot directly — more robust than
        # get_price_by_type, which can raise on some (e.g. perpetual) connectors.
        ob = conn.get_order_book(matched)
        bids, asks = ob.snapshot[0], ob.snapshot[1]
        best_bid = float(bids.iloc[0]["price"]) if len(bids) else None
        best_ask = float(asks.iloc[0]["price"]) if len(asks) else None
        mid = (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else None

        def last_trade():
            try:
                return float(conn.get_price_by_type(matched, PriceType.LastTrade))
            except Exception:
                return None
        data = {"best_bid": best_bid, "best_ask": best_ask, "mid_price": mid, "last_trade": last_trade()}
    finally:
        await conn.stop_network()
    return data, matched, alts


def _render(data: dict, exchange: str, matched: str, query: str, alts: List[str]) -> str:
    def fmt(v):
        return f"{v:g}" if v is not None else "n/a"
    head = f"  {exchange}  {matched}"
    if matched.upper() != query.upper().replace("_", "-").replace("/", "-"):
        head += f"   [fuzzy-matched from '{query}']"
    lines = [head,
             f"    best bid   {fmt(data['best_bid'])}",
             f"    best ask   {fmt(data['best_ask'])}",
             f"    mid price  {fmt(data['mid_price'])}",
             f"    last trade {fmt(data['last_trade'])}"]
    if alts:
        lines.append(f"\n  also matched: {', '.join(alts)}")
    return "\n".join(lines)


def ticker(
    exchange: str = typer.Argument(..., help="Exchange, e.g. hyperliquid_perpetual or binance."),
    pair: str = typer.Argument(..., help="Trading pair (fuzzy), e.g. ETH-USD, btc/usdt."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show best bid, ask, mid, and last price for a pair on an exchange."""
    ccm, _ = login(password_stdin=password_stdin, json_output=json_output)
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        data, matched, alts = asyncio.run(_run(ccm, exchange, pair, timeout, json_output))
    except asyncio.TimeoutError:
        fail("timed out waiting for the order book", ExitCode.TIMEOUT, json_output=json_output)

    if json_output:
        print_json({"ok": True, "exchange": exchange, "query": pair, "matched": matched,
                    "alternatives": alts, "ticker": data})
    else:
        typer.echo(_render(data, exchange, matched, pair, alts))
