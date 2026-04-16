"""Coverage tests for hummingbot/strategy/spot_perpetual_arbitrage/utils.py
Missing lines: 11 (async function entry), 31-32 (ArbProposalSide construction when prices exist).

utils.py imports from `.data_types` which does not exist as a module (the file is missing).
We inject a fully-mocked `data_types` module into sys.modules before importing utils so the
import chain succeeds, then exercise the live logic.
"""

import sys
import types
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Inject fake data_types with mock classes ──────────────────────────────────
_fake_data_types = types.ModuleType("hummingbot.strategy.spot_perpetual_arbitrage.data_types")

# ArbProposalSide is called with 5 positional args inside utils.create_arb_proposals
_fake_data_types.ArbProposalSide = MagicMock(side_effect=lambda *a, **kw: MagicMock())
# ArbProposal is called with (first_side, second_side)
_fake_data_types.ArbProposal = MagicMock(side_effect=lambda *a, **kw: MagicMock())

sys.modules.setdefault("hummingbot.strategy.spot_perpetual_arbitrage.data_types", _fake_data_types)

# Force re-import if module was already cached without data_types
_mod_key = "hummingbot.strategy.spot_perpetual_arbitrage.utils"
if _mod_key in sys.modules:
    del sys.modules[_mod_key]

from hummingbot.strategy.spot_perpetual_arbitrage.utils import create_arb_proposals  # noqa: E402


def _make_market_info(trading_pair: str, q_price, o_price):
    mi = MagicMock()
    mi.trading_pair = trading_pair
    mi.market.get_quote_price = AsyncMock(return_value=q_price)
    mi.market.get_order_price = AsyncMock(return_value=o_price)
    return mi


@pytest.mark.asyncio
async def test_create_arb_proposals_skips_when_price_is_none():
    """Lines 11 (function entry) + 29 (continue) when any price is None — returns empty list."""
    m1 = _make_market_info("BTC-USDT", None, None)
    m2 = _make_market_info("BTC-USDT", None, None)

    results = await create_arb_proposals(m1, m2, Decimal("1"))
    assert results == []


@pytest.mark.asyncio
async def test_create_arb_proposals_builds_sides_when_prices_exist():
    """Lines 31-32: ArbProposalSide construction executed when all prices are non-None."""
    m1 = _make_market_info("BTC-USDT", Decimal("100"), Decimal("100"))
    m2 = _make_market_info("BTC-USDT", Decimal("101"), Decimal("101"))

    results = await create_arb_proposals(m1, m2, Decimal("1"))
    # Both loop iterations should produce proposals (lines 31-32 hit)
    assert len(results) == 2
