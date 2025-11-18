from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from hummingbot.core.event.events import OrderType
from services.execution_service import ExecutionService
from services.models import ExecutionRiskLimits, OrderIntent


@pytest.mark.asyncio
async def test_execution_service_places_buy_order():
    connector = MagicMock()
    connector.get_mid_price.return_value = 100
    service = ExecutionService(connector)
    intent = OrderIntent(
        trading_pair="BTC-PERP",
        side="buy",
        amount=Decimal("1"),
        order_type=OrderType.MARKET,
    )
    await service.place_order(intent)
    connector.buy.assert_called_once()


@pytest.mark.asyncio
async def test_execution_service_checks_notional_limit():
    connector = MagicMock()
    connector.get_mid_price.return_value = 100
    service = ExecutionService(connector, ExecutionRiskLimits(max_notional=Decimal("50")))
    intent = OrderIntent(
        trading_pair="BTC-PERP",
        side="buy",
        amount=Decimal("1"),
    )
    with pytest.raises(ValueError):
        await service.place_order(intent)
