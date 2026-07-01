"""Helpers shared across hbot command modules (kept here so commands don't import each other)."""
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

from hummingbot.cli import bot
from hummingbot.cli.output import ExitCode, fail

_TYPE_FLAGS = (("v1-strategy", "--v1-strategy"), ("v2-script", "--v2-script"), ("controller", "--controller"))


def one_type(v1: bool, v2: bool, controller: bool, required: bool) -> Optional[str]:
    """Collapse the --v1-strategy / --v2-script / --controller flags into a single type id (or None).

    Fails if more than one is set, or if ``required`` and none is set. Shared by ``strategy`` and
    ``start`` so the flag semantics stay identical."""
    chosen = [t for (t, _flag), on in zip(_TYPE_FLAGS, (v1, v2, controller)) if on]
    names = " / ".join(flag for _t, flag in _TYPE_FLAGS)
    if len(chosen) > 1:
        fail(f"use only one of {names}", ExitCode.CONFIG_ERROR)
    if required and not chosen:
        fail(f"specify one of {names}", ExitCode.CONFIG_ERROR)
    return chosen[0] if chosen else None


def position_dict(p) -> dict:
    """Normalize a connector ``Position`` into a flat dict (side, size, entry/mark price, notional,
    unrealized PnL, leverage). Shared by ``balance`` to show perp positions inline."""
    amt = float(p.amount)
    entry = float(p.entry_price)
    upnl = float(p.unrealized_pnl)
    # Current mark is exact from the position's own data (uPnL = amount*(mark-entry) for linear
    # perps), so the market value needs no rate-oracle / price fetch.
    mark = entry + (upnl / amt) if amt else entry
    return {
        "trading_pair": p.trading_pair,
        "side": getattr(p.position_side, "name", str(p.position_side)),
        "amount": amt,
        "entry_price": entry,
        "mark_price": mark,
        "value": abs(amt) * mark,          # current market value (notional at mark, in quote currency)
        "notional": abs(amt) * entry,      # entry notional (kept for balance's existing render)
        "unrealized_pnl": upnl,
        "leverage": int(p.leverage),
    }


def read_json_object_from_stdin() -> dict:
    """Read a JSON object {key: value} from stdin, failing clearly on bad/non-object input."""
    raw = sys.stdin.read()
    try:
        parsed = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        fail(f"invalid JSON on stdin: {e}", ExitCode.CONFIG_ERROR)
    if not isinstance(parsed, dict):
        fail("stdin must be a JSON object of field -> value", ExitCode.CONFIG_ERROR)
    return parsed


def resolve_db_for_command(name: Optional[str]) -> Tuple[Path, Optional[str], bool]:
    """Resolve ``(db_path, config_filter, running)`` for the trades/history commands.

    With ``name`` -> a past/stopped bot's DB (no config filter, not running). Otherwise the current
    bot's DB. Fails clearly when the bot/DB is absent. Centralizes the lookup + error wording so the
    two commands can't drift apart."""
    if name:
        db_path = bot.db_path_for(name)
        if db_path is None:
            fail(f"no trades database for '{name}' (available: {', '.join(bot.list_bots()) or 'none'})",
                 ExitCode.NOT_FOUND)
        return db_path, None, False
    if not bot.exists():
        fail("no bot has been started (pass a name to view a past bot)", ExitCode.NOT_FOUND)
    db_path = bot.resolve_db_path()
    if db_path is None:
        fail("no trades database yet (no fills?)", ExitCode.ERROR)
    pid = bot.read_pid()
    running = pid is not None and bot.pid_alive(pid)
    return db_path, bot.config_file_path(), running
