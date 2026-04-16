"""Coverage tests for cross_exchange_mining_config_map_pydantic.py - line 113 (order_amount_prompt)."""

from unittest.mock import MagicMock

from hummingbot.strategy.cross_exchange_mining.cross_exchange_mining_config_map_pydantic import (
    CrossExchangeMiningConfigMap,
)


def test_order_amount_prompt_contains_base_asset():
    """Line 113: order_amount_prompt classmethod returns string with base asset from maker_market_trading_pair."""
    model_instance = MagicMock()
    model_instance.maker_market_trading_pair = "ETH-USDT"

    result = CrossExchangeMiningConfigMap.order_amount_prompt(model_instance)

    assert "ETH" in result
