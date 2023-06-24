import unittest
from decimal import Decimal
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade import cat_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_order_types import (
    CoinbaseAdvancedTradeAPIOrderConfiguration,
    CoinbaseAdvancedTradeOrderTypeEnum,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types.cat_api_v3_request_types import (
    CoinbaseAdvancedTradeCreateOrderRequest,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.cat_exchange_mixins.cat_orders_mixin import OrdersMixin
from hummingbot.core.event.events import OrderType, TradeType


class TestOrdersMixin(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.mixin = OrdersMixin()
        self.mixin.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-USD")
        self.mixin.api_post = AsyncMock(return_value={"order_id": "12345"})
        self.mixin.time_synchronizer = MagicMock()
        self.mixin.time_synchronizer.time = MagicMock(return_value=1624379186.738521)

    @patch.object(CoinbaseAdvancedTradeAPIOrderConfiguration, "create")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.cat_data_types"
           ".cat_api_v3_request_types.CoinbaseAdvancedTradeCreateOrderRequest")
    async def test_place_order(self, mock_order_request_class, mock_order_config):
        mock_order_request = mock_order_request_class.return_value
        mock_order_request.to_dict_for_json.return_value = {"mocked": "data"}

        mock_order_config.return_value = CoinbaseAdvancedTradeAPIOrderConfiguration(
            market_market_ioc={"quote_size": "1", "base_size": "1"}
        )
        expected_data = CoinbaseAdvancedTradeCreateOrderRequest.dict_sample_from_json_docstring(
            {
                'client_order_id': 'test_order',
                'side': 'BUY',
                'product_id': 'BTC-USD',
                "order_configuration":
                    {
                        "market_market_ioc": {"quote_size": "1", "base_size": "1"}
                    }
            }
        )
        self.mixin.api_post = AsyncMock(return_value={"order_id": "12345"})
        await self.mixin._place_order("test_order",
                                      "BTC-USD",
                                      Decimal(1),
                                      TradeType.BUY,
                                      OrderType.MARKET,
                                      Decimal(40000))

        mock_order_config.assert_called_once_with(OrderType.MARKET, base_size=Decimal(1), quote_size=Decimal(40000),
                                                  limit_price=Decimal(40000))
        self.mixin.api_post.assert_called_once_with(path_url=CONSTANTS.ORDER_EP,
                                                    data=expected_data,
                                                    is_auth_required=True)

    def test_supported_order_types(self):
        self.assertEqual(self.mixin.supported_order_types(), [OrderType.MARKET, OrderType.LIMIT, OrderType.LIMIT_MAKER])

    def test_to_coinbase_advanced_trade_order_type(self):
        self.assertEqual(CoinbaseAdvancedTradeOrderTypeEnum.MARKET,
                         self.mixin.to_coinbase_advanced_trade_order_type(OrderType.MARKET))
        self.assertEqual(CoinbaseAdvancedTradeOrderTypeEnum.LIMIT,
                         self.mixin.to_coinbase_advanced_trade_order_type(OrderType.LIMIT))
        self.assertEqual(CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_MAKER,
                         self.mixin.to_coinbase_advanced_trade_order_type(OrderType.LIMIT_MAKER))

    def test_to_hb_order_type(self):
        self.assertEqual(self.mixin.to_hb_order_type(CoinbaseAdvancedTradeOrderTypeEnum.MARKET), OrderType.MARKET)
        self.assertEqual(self.mixin.to_hb_order_type(CoinbaseAdvancedTradeOrderTypeEnum.LIMIT), OrderType.LIMIT)
        self.assertEqual(self.mixin.to_hb_order_type(CoinbaseAdvancedTradeOrderTypeEnum.LIMIT_MAKER),
                         OrderType.LIMIT_MAKER)

    async def test_daisy_chaining_with_kwargs(self):
        class BaseClass:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def base_method(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

            async def overwritten_in_mixin(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

            async def overwritten_in_subclass(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        class OtherMixin:
            def __init__(self, **kwargs):
                if super().__class__ is not object:
                    super().__init__(**kwargs)

            async def overwritten_in_mixin(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        class SubClass(OrdersMixin, OtherMixin, BaseClass):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)

            async def overwritten_in_subclass(self, *args, **kwargs) -> Dict[str, Any]:
                return {}

        test_obj = SubClass(test="test")
        # Mock the methods in the base class
        with patch.object(BaseClass, "base_method", new_callable=AsyncMock) as mock_method:
            with patch.object(OtherMixin, "overwritten_in_mixin", new_callable=AsyncMock) as mock_mixin:
                with patch.object(SubClass, "overwritten_in_subclass", new_callable=AsyncMock) as mock_subbclass:
                    await test_obj.overwritten_in_subclass()
                    await test_obj.overwritten_in_mixin()
                    await test_obj.base_method()
                    mock_method.assert_called_once_with()
                    mock_mixin.assert_called_once_with()
                    mock_subbclass.assert_called_once_with()
                    self.assertEqual(test_obj.kwargs, {"test": "test"})


if __name__ == "__main__":
    unittest.main()
