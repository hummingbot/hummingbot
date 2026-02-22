import os
from unittest import TestCase


class TestBingXPerpetualConstants(TestCase):

    def setUp(self):
        constants_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'bing_x_perpetual', 'bing_x_perpetual_constants.py'
        )
        with open(constants_path) as f:
            self.source = f.read()

    def test_rest_url_is_bingx(self):
        self.assertIn('open-api.bingx.com', self.source)

    def test_perpetual_endpoints_use_swap_path(self):
        self.assertIn('/openApi/swap/v2/', self.source)

    def test_ticker_endpoint(self):
        self.assertIn('/openApi/swap/v2/quote/ticker', self.source)

    def test_order_endpoint(self):
        self.assertIn('/openApi/swap/v2/trade/order', self.source)

    def test_balance_endpoint(self):
        self.assertIn('/openApi/swap/v2/user/balance', self.source)

    def test_positions_endpoint(self):
        self.assertIn('/openApi/swap/v2/user/positions', self.source)

    def test_funding_rate_endpoint(self):
        self.assertIn('/openApi/swap/v2/quote/fundingRate', self.source)

    def test_leverage_endpoint(self):
        self.assertIn('/openApi/swap/v2/trade/leverage', self.source)

    def test_websocket_url_is_bingx(self):
        self.assertIn('open-api-ws.bingx.com', self.source)

    def test_exchange_name(self):
        self.assertIn('bing_x_perpetual', self.source)

    def test_order_states_mapping(self):
        self.assertIn('FILLED', self.source)
        self.assertIn('CANCELED', self.source)
        self.assertIn('PARTIALLY_FILLED', self.source)

    def test_symbol_format_uses_dash(self):
        self.assertNotIn('BTCUSDT', self.source)

    def test_ws_heartbeat_defined(self):
        self.assertIn('WS_HEARTBEAT_TIME_INTERVAL', self.source)

    def test_broker_id(self):
        self.assertIn('BROKER_ID', self.source)
        self.assertIn('hummingbot', self.source)

    def test_side_constants(self):
        self.assertIn('SIDE_BUY', self.source)
        self.assertIn('SIDE_SELL', self.source)

    def test_position_side_constants(self):
        self.assertIn('POSITION_SIDE_LONG', self.source)
        self.assertIn('POSITION_SIDE_SHORT', self.source)

    def test_time_in_force_constants(self):
        self.assertIn('TIME_IN_FORCE_GTC', self.source)
        self.assertIn('TIME_IN_FORCE_IOC', self.source)

    def test_order_type_constants(self):
        self.assertIn('ORDER_TYPE_MARKET', self.source)
        self.assertIn('ORDER_TYPE_LIMIT', self.source)

    def test_depth_endpoint(self):
        self.assertIn('/openApi/swap/v2/quote/depth', self.source)

    def test_mark_price_endpoint(self):
        self.assertIn('/openApi/swap/v2/quote/premiumIndex', self.source)
