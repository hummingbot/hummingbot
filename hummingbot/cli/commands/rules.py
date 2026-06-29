"""``hbot rules`` — show an exchange's trading rules for a pair.

Fetches the connector's trading rules (min order size, min notional, tick/step sizes, supported order
types) for a fuzzy-matched pair — read-only, no running bot. This is the data you need to size a
strategy's orders correctly (e.g. so each order clears the minimum notional).
"""
import asyncio
from typing import List, Tuple

import typer

from hummingbot.cli.output import ExitCode, fail, print_json
from hummingbot.cli.password import login


def _rule_dict(rule) -> dict:
    def f(v):
        return float(v) if v is not None else None
    return {
        "trading_pair": rule.trading_pair,
        "min_order_size": f(rule.min_order_size),
        "max_order_size": f(rule.max_order_size),
        "min_notional_size": f(rule.min_notional_size),
        "min_order_value": f(rule.min_order_value),
        "min_price_increment": f(rule.min_price_increment),
        "min_base_amount_increment": f(rule.min_base_amount_increment),
        "min_quote_amount_increment": f(rule.min_quote_amount_increment),
        "supports_limit_orders": bool(rule.supports_limit_orders),
        "supports_market_orders": bool(rule.supports_market_orders),
    }


async def _run(ccm, exchange: str, pair: str, timeout: float, json_output: bool) -> Tuple[dict, str, List[str]]:
    from hummingbot.cli.commands._market_data import make_connector, resolve_or_fail, trading_rules_universe
    conn = await make_connector(ccm, exchange, [], json_output)
    rules = await asyncio.wait_for(trading_rules_universe(conn), timeout)
    if not rules:
        fail(f"{exchange} returned no trading rules", ExitCode.ERROR, json_output=json_output)
    matched, alts = resolve_or_fail(list(rules.keys()), pair, json_output)
    return _rule_dict(rules[matched]), matched, alts


def _render(rule: dict, matched: str, query: str, alts: List[str]) -> str:
    lines = [f"  {matched}  ({rule['trading_pair']})"]
    if matched.upper() != query.upper().replace("_", "-").replace("/", "-"):
        lines[0] += f"   [fuzzy-matched from '{query}']"
    rows = [
        ("min order size", rule["min_order_size"], "base"),
        ("max order size", rule["max_order_size"], "base"),
        ("min notional", rule["min_notional_size"], "quote"),
        ("min order value", rule["min_order_value"], "quote"),
        ("price increment (tick)", rule["min_price_increment"], ""),
        ("base step (amount)", rule["min_base_amount_increment"], ""),
        ("quote step", rule["min_quote_amount_increment"], ""),
    ]
    for label, val, unit in rows:
        if val is not None:
            lines.append(f"    {label:24} {val:<20g} {unit}")
    types = []
    if rule["supports_limit_orders"]:
        types.append("limit")
    if rule["supports_market_orders"]:
        types.append("market")
    lines.append(f"    {'order types':24} {', '.join(types) or 'unknown'}")
    if alts:
        lines.append(f"\n  also matched: {', '.join(alts)}")
    return "\n".join(lines)


def rules(
    exchange: str = typer.Argument(..., help="Exchange, e.g. hyperliquid_perpetual or binance."),
    pair: str = typer.Argument(..., help="Trading pair (fuzzy), e.g. ETH-USD, spcx/usd, xyz:tsla-usd."),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the keystore password from stdin (else $HBOT_PASSWORD or a prompt)."),
    json_output: bool = typer.Option(False, "--json", help="Machine-readable JSON output."),
) -> None:
    """Show an exchange's trading rules for a pair (min size, min notional, tick/step sizes)."""
    ccm, _ = login(password_stdin=password_stdin, json_output=json_output)
    timeout = float(ccm.commands_timeout.other_commands_timeout)
    try:
        rule, matched, alts = asyncio.run(_run(ccm, exchange, pair, timeout, json_output))
    except asyncio.TimeoutError:
        fail("network timeout fetching trading rules", ExitCode.TIMEOUT, json_output=json_output)

    if json_output:
        print_json({"ok": True, "exchange": exchange, "query": pair, "matched": matched,
                    "alternatives": alts, "rule": rule})
    else:
        typer.echo(_render(rule, matched, pair, alts))
