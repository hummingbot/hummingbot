import unittest

from requests_mock import Mocker

from coinbase.rest import RESTClient
from coinbase.rest.types.orders_types import ListOrdersResponse

from ..constants import TEST_API_KEY, TEST_API_SECRET


class OrdersTest(unittest.TestCase):
    def test_create_order(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order_configuration = {"market_market_ioc": {"quote_size": "1"}}

            order = client.create_order(
                "client_order_id_1",
                "product_id_1",
                "BUY",
                order_configuration,
                self_trade_prevention_id="self_trade_prevention_id_1",
                margin_type="CROSS",
                leverage="5",
                retail_portfolio_id="portfolio_id_1",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {"market_market_ioc": {"quote_size": "1"}},
                    "self_trade_prevention_id": "self_trade_prevention_id_1",
                    "margin_type": "CROSS",
                    "leverage": "5",
                    "retail_portfolio_id": "portfolio_id_1",
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_market_order(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )

            order = client.market_order(
                "client_order_id_1", "product_id_1", "BUY", quote_size="1"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()
            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {"market_market_ioc": {"quote_size": "1"}},
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_market_order_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )

            order = client.market_order_buy("client_order_id_1", "product_id_1", "1")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {"market_market_ioc": {"quote_size": "1"}},
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_market_order_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )

            order = client.market_order_sell("client_order_id_1", "product_id_1", "1")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {"market_market_ioc": {"base_size": "1"}},
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_ioc(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_ioc(
                "client_order_id_1", "product_id_1", "BUY", "1", "100"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "sor_limit_ioc": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_ioc_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_ioc_buy(
                "client_order_id_1", "product_id_1", "1", "100"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "sor_limit_ioc": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_ioc_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_ioc_sell(
                "client_order_id_1", "product_id_1", "1", "100"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "sor_limit_ioc": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_gtc(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_gtc(
                "client_order_id_1",
                "product_id_1",
                "BUY",
                "1",
                "100",
                True,
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "post_only": True,
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_gtc_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_gtc_buy(
                "client_order_id_1",
                "product_id_1",
                "1",
                "100",
                True,
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "post_only": True,
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_gtc_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_gtc_sell(
                "client_order_id_1",
                "product_id_1",
                "1",
                "100",
                True,
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "limit_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "post_only": True,
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_gtd(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_gtd(
                "client_order_id_1",
                "product_id_1",
                "BUY",
                "1",
                "100",
                "2022-01-01T00:00:00Z",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "end_time": "2022-01-01T00:00:00Z",
                            "post_only": False,
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_gtd_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_gtd_buy(
                "client_order_id_1", "product_id_1", "1", "100", "2022-01-01T00:00:00Z"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "end_time": "2022-01-01T00:00:00Z",
                            "post_only": False,
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_gtd_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_gtd_sell(
                "client_order_id_1", "product_id_1", "1", "100", "2022-01-01T00:00:00Z"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "limit_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "end_time": "2022-01-01T00:00:00Z",
                            "post_only": False,
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_fok(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_fok(
                "client_order_id_1", "product_id_1", "BUY", "1", "100"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_fok": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_fok_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_fok_buy(
                "client_order_id_1", "product_id_1", "1", "100"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_fok": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_limit_order_fok_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.limit_order_fok_sell(
                "client_order_id_1", "product_id_1", "1", "100"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "limit_limit_fok": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_stop_limit_order_gtc(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.stop_limit_order_gtc(
                "client_order_id_1",
                "product_id_1",
                "BUY",
                "1",
                "100",
                "90",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_stop_limit_order_gtc_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.stop_limit_order_gtc_buy(
                "client_order_id_1",
                "product_id_1",
                "1",
                "100",
                "90",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_stop_limit_order_gtc_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.stop_limit_order_gtc_sell(
                "client_order_id_1",
                "product_id_1",
                "1",
                "100",
                "90",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_stop_limit_order_gtd(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.stop_limit_order_gtd(
                "client_order_id_1",
                "product_id_1",
                "BUY",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_stop_limit_order_gtd_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.stop_limit_order_gtd_buy(
                "client_order_id_1",
                "product_id_1",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_stop_limit_order_gtd_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.stop_limit_order_gtd_sell(
                "client_order_id_1",
                "product_id_1",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_trigger_bracket_order_gtc(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.trigger_bracket_order_gtc(
                "client_order_id_1",
                "product_id_1",
                "BUY",
                "1",
                "100",
                "90",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "trigger_bracket_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_trigger_bracket_order_gtc_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.trigger_bracket_order_gtc_buy(
                "client_order_id_1", "product_id_1", "1", "100", "90"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "trigger_bracket_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_trigger_bracket_order_gtc_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.trigger_bracket_order_gtc_sell(
                "client_order_id_1", "product_id_1", "1", "100", "90"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "trigger_bracket_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_trigger_bracket_order_gtd(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.trigger_bracket_order_gtd(
                "client_order_id_1",
                "product_id_1",
                "BUY",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "trigger_bracket_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_trigger_bracket_order_gtd_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.trigger_bracket_order_gtd_buy(
                "client_order_id_1",
                "product_id_1",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "trigger_bracket_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_trigger_bracket_order_gtd_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders",
                json=expected_response,
            )
            order = client.trigger_bracket_order_gtd_sell(
                "client_order_id_1",
                "product_id_1",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "trigger_bracket_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                        }
                    },
                },
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_get_order(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/orders/historical/order_id_1",
                json=expected_response,
            )
            order = client.get_order("order_id_1")

            captured_request = m.request_history[0]

            self.assertEqual(captured_request.query, "")
            self.assertEqual(order.__dict__, expected_response)

    def test_list_orders(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"orders": [{"order_id": "1234"}, {"order_id": "5678"}]}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/orders/historical/batch",
                json=expected_response,
            )
            orders = client.list_orders(
                product_ids=["product_id_1", "product_id_2"],
                order_status="OPEN",
                limit=2,
                product_type="SPOT",
            )

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query,
                "product_ids=product_id_1&product_ids=product_id_2&order_status=open&limit=2&product_type=spot",
            )
            actual_response_dict = orders.to_dict()
            expected_response_dict = ListOrdersResponse(expected_response).to_dict()
            self.assertEqual(actual_response_dict, expected_response_dict)

    def test_get_fills(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"orders": [{"order_id": "1234"}]}

        with Mocker() as m:
            m.request(
                "GET",
                "https://api.coinbase.com/api/v3/brokerage/orders/historical/fills",
                json=expected_response,
            )
            orders = client.get_fills(
                order_ids=["1234"],
                product_ids=["product_id_1"],
                retail_portfolio_id="portfolio_id_1",
                limit=2,
                cursor="abc",
            )

            captured_request = m.request_history[0]

            self.assertEqual(
                captured_request.query,
                "order_ids=1234&product_ids=product_id_1&retail_portfolio_id=portfolio_id_1&limit=2&cursor=abc",
            )
            self.assertEqual(orders.__dict__, expected_response)

    def test_edit_order(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "order_id_1"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/edit",
                json=expected_response,
            )
            order = client.edit_order("order_id_1", "100", "50")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json, {"order_id": "order_id_1", "size": "100", "price": "50"}
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_preview_edit_order(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "order_id_1"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/edit_preview",
                json=expected_response,
            )
            order = client.preview_edit_order("order_id_1", "100", "50")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json, {"order_id": "order_id_1", "size": "100", "price": "50"}
            )
            self.assertEqual(order.__dict__, expected_response)

    def test_cancel_orders(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "order_id_1"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/batch_cancel",
                json=expected_response,
            )
            order = client.cancel_orders(["order_id_1", "order_id_2"])

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(captured_json, {"order_ids": ["order_id_1", "order_id_2"]})
            self.assertEqual(order.__dict__, expected_response)

    def test_preview_order(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "order_id_1"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )

            order_configuration = {"market_market_ioc": {"quote_size": "1"}}

            preview = client.preview_order(
                "product_id_1",
                "BUY",
                order_configuration,
                leverage="5",
                margin_type="CROSS",
                retail_portfolio_id="portfolio_id_1",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {"market_market_ioc": {"quote_size": "1"}},
                    "leverage": "5",
                    "margin_type": "CROSS",
                    "retail_portfolio_id": "portfolio_id_1",
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_market_order(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )

            preview = client.preview_market_order("product_id_1", "BUY", quote_size="1")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {"market_market_ioc": {"quote_size": "1"}},
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_market_order_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )

            preview = client.preview_market_order_buy("product_id_1", "1")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {"market_market_ioc": {"quote_size": "1"}},
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_market_order_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )

            preview = client.preview_market_order_sell("product_id_1", "1")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {"market_market_ioc": {"base_size": "1"}},
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_ioc(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_ioc("product_id_1", "BUY", "1", "100")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "sor_limit_ioc": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_ioc_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_ioc_buy("product_id_1", "1", "100")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "sor_limit_ioc": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_ioc_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_ioc_sell("product_id_1", "1", "100")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "sor_limit_ioc": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_gtc(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_gtc(
                "product_id_1",
                "BUY",
                "1",
                "100",
                True,
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "post_only": True,
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_gtc_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_gtc_buy(
                "product_id_1",
                "1",
                "100",
                True,
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "post_only": True,
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_gtc_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_gtc_sell(
                "product_id_1",
                "1",
                "100",
                True,
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "limit_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "post_only": True,
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_gtd(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_gtd(
                "product_id_1",
                "BUY",
                "1",
                "100",
                "2022-01-01T00:00:00Z",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "end_time": "2022-01-01T00:00:00Z",
                            "post_only": False,
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_gtd_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_gtd_buy(
                "product_id_1", "1", "100", "2022-01-01T00:00:00Z"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "end_time": "2022-01-01T00:00:00Z",
                            "post_only": False,
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_gtd_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_gtd_sell(
                "product_id_1", "1", "100", "2022-01-01T00:00:00Z"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "limit_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "end_time": "2022-01-01T00:00:00Z",
                            "post_only": False,
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_fok(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_fok("product_id_1", "BUY", "1", "100")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_fok": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_fok_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_fok_buy("product_id_1", "1", "100")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "limit_limit_fok": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_limit_order_fok_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_limit_order_fok_sell("product_id_1", "1", "100")

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "limit_limit_fok": {"base_size": "1", "limit_price": "100"}
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_stop_limit_order_gtc(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_stop_limit_order_gtc(
                "product_id_1",
                "BUY",
                "1",
                "100",
                "90",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_stop_limit_order_gtc_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_stop_limit_order_gtc_buy(
                "product_id_1",
                "1",
                "100",
                "90",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_stop_limit_order_gtc_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_stop_limit_order_gtc_sell(
                "product_id_1",
                "1",
                "100",
                "90",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_stop_limit_order_gtd(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_stop_limit_order_gtd(
                "product_id_1",
                "BUY",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_stop_limit_order_gtd_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_stop_limit_order_gtd_buy(
                "product_id_1",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_stop_limit_order_gtd_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_stop_limit_order_gtd_sell(
                "product_id_1",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
                "STOP_DIRECTION_STOP_UP",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "stop_limit_stop_limit_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                            "stop_direction": "STOP_DIRECTION_STOP_UP",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_trigger_bracket_order_gtc(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_trigger_bracket_order_gtc(
                "product_id_1",
                "BUY",
                "1",
                "100",
                "90",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "trigger_bracket_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_trigger_bracket_order_gtc_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_trigger_bracket_order_gtc_buy(
                "product_id_1", "1", "100", "90"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "trigger_bracket_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_trigger_bracket_gtc_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_trigger_bracket_order_gtc_sell(
                "product_id_1", "1", "100", "90"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "trigger_bracket_gtc": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_trigger_bracket_order_gtd(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_trigger_bracket_order_gtd(
                "product_id_1",
                "BUY",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "trigger_bracket_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_trigger_bracket_order_gtd_buy(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_trigger_bracket_order_gtd_buy(
                "product_id_1",
                "1",
                "100",
                "90",
                "2022-01-01T00:00:00Z",
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "BUY",
                    "order_configuration": {
                        "trigger_bracket_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_preview_trigger_bracket_gtd_sell(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {"order_id": "1234"}

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/preview",
                json=expected_response,
            )
            preview = client.preview_trigger_bracket_order_gtd_sell(
                "product_id_1", "1", "100", "90", "2022-01-01T00:00:00Z"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "product_id": "product_id_1",
                    "side": "SELL",
                    "order_configuration": {
                        "trigger_bracket_gtd": {
                            "base_size": "1",
                            "limit_price": "100",
                            "stop_trigger_price": "90",
                            "end_time": "2022-01-01T00:00:00Z",
                        }
                    },
                },
            )
            self.assertEqual(preview.__dict__, expected_response)

    def test_close_position(self):
        client = RESTClient(TEST_API_KEY, TEST_API_SECRET)

        expected_response = {
            "client_order_id": "client_order_id_1",
            "product_id": "product_id_1",
        }

        with Mocker() as m:
            m.request(
                "POST",
                "https://api.coinbase.com/api/v3/brokerage/orders/close_position",
                json=expected_response,
            )
            closedOrder = client.close_position(
                "client_order_id_1", "product_id_1", "100"
            )

            captured_request = m.request_history[0]
            captured_json = captured_request.json()

            self.assertEqual(captured_request.query, "")
            self.assertEqual(
                captured_json,
                {
                    "client_order_id": "client_order_id_1",
                    "product_id": "product_id_1",
                    "size": "100",
                },
            )
            self.assertEqual(closedOrder.__dict__, expected_response)
