import asyncio
import json
import re
from decimal import Decimal
from functools import partial
from test.hummingbot.connector.exchange.dexalot.programmable_client import ProgrammableClient
from typing import Any, Callable, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from aioresponses.core import RequestCall

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.dexalot import dexalot_constants as CONSTANTS, dexalot_web_utils as web_utils
from hummingbot.connector.exchange.dexalot.dexalot_exchange import DexalotExchange
from hummingbot.connector.test_support.exchange_connector_test import AbstractExchangeConnectorTests
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.event.events import OrderBookTradeEvent


class DexalotExchangeTests(AbstractExchangeConnectorTests.ExchangeConnectorTests):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "someKey"
        cls.api_secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        cls.base_asset = "AVAX"
        cls.quote_asset = "USDC"  # linear
        cls.trading_pair = combine_to_hb_trading_pair(cls.base_asset, cls.quote_asset)
        cls.client_order_id_prefix = "0x48424f5442454855443630616330301"  # noqa: mock

    def setUp(self) -> None:
        super().setUp()

        self._original_async_loop = asyncio.get_event_loop()
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        self.exchange._orders_processing_delta_time = 0.1
        self.async_tasks.append(self.async_loop.create_task(self.exchange._process_queued_orders()))

    def tearDown(self) -> None:
        super().tearDown()
        self.async_loop.stop()
        self.async_loop.close()
        asyncio.set_event_loop(self._original_async_loop)

    @property
    def all_symbols_url(self):
        return web_utils.public_rest_url(path_url=CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)

    @property
    def network_status_url(self):
        url = web_utils.private_rest_url(CONSTANTS.PING_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def trading_rules_url(self):
        url = web_utils.private_rest_url(CONSTANTS.EXCHANGE_INFO_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def order_creation_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def balance_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ACCOUNTS_PATH_URL, domain=self.exchange._domain)
        return url

    @property
    def orders_url(self):
        url = web_utils.private_rest_url(CONSTANTS.ORDERS_PATH_URL, domain=self.exchange._domain)
        return url

    @staticmethod
    def _callback_wrapper_with_response(callback: Callable, response: Any, *args, **kwargs):
        callback(args, kwargs)
        if isinstance(response, Exception):
            raise response
        else:
            return response

    @property
    def all_symbols_request_mock_response(self):
        return [
            {'env': 'production-multi-subnet',
             'pair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), 'base': self.base_asset,
             'quote': self.quote_asset,
             'basedisplaydecimals': 3,
             'quotedisplaydecimals': 3, 'baseaddress': '0x0000000000000000000000000000000000000000',
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': True,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 5, 'additional_ordertypes': 0, 'taker_fee': 0.001, 'maker_fee': 0.0012}
        ]

    @property
    def all_symbols_including_invalid_pair_mock_response(self) -> Tuple[str, Any]:
        response = [
            {'env': 'production-multi-subnet',
             'pair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), 'base': self.base_asset,
             'quote': self.quote_asset,
             'basedisplaydecimals': 3,
             'quotedisplaydecimals': 3, 'baseaddress': '0x0000000000000000000000000000000000000000',
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': True,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 5, 'additional_ordertypes': 0, 'taker_fee': 0.001, 'maker_fee': 0.0012},
            {'env': 'production-multi-subnet', 'pair': self.exchange_symbol_for_tokens("INVALID", "PAIR"),
             'base': "INVALID", 'quote': self.quote_asset,
             'basedisplaydecimals': 3,
             'quotedisplaydecimals': 3, 'baseaddress': '0x0000000000000000000000000000000000000000',
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': False,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 5, 'additional_ordertypes': 0, 'taker_fee': 0.001, 'maker_fee': 0.0012},

        ]

        return "INVALID-PAIR", response

    @property
    def network_status_request_successful_mock_response(self):
        return {}

    @property
    def trading_rules_request_mock_response(self):
        return [
            {'env': 'production-multi-subnet',
             'pair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), 'base': self.base_asset,
             'quote': self.quote_asset,
             'basedisplaydecimals': 3,
             'quotedisplaydecimals': 3, 'baseaddress': '0x0000000000000000000000000000000000000000',
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': True,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 5, 'additional_ordertypes': 0, 'taker_fee': 0.001, 'maker_fee': 0.0012}
        ]

    @property
    def trading_rules_request_erroneous_mock_response(self):
        return [
            {'env': 'production-multi-subnet',
             'pair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset), 'base': self.base_asset,
             'quote': self.quote_asset,
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': True,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 5, 'additional_ordertypes': 0, 'taker_fee': 0.001, 'maker_fee': 0.0012}
        ]

    @property
    def order_creation_request_successful_mock_response(self):
        return "017C130E3602A48E5C9D661CAC657BF1B79262D4B71D5C25B1DA62DE2338DA0E"  # noqa: mock

    @property
    def balance_request_mock_response_for_base_and_quote(self):
        return [
            {'traderaddress': '0x335e5b9a72a3aba693b68bde44feba1252e54cfc',  # noqa: mock
             'symbol': 'AVAX', 'trades': '0',
             'xfers': '0',
             'fee': '0', 'currentbal': '10'},
            {'traderaddress': '0x335e5b9a72a3aba693b68bde44feba1252e54cfc',  # noqa: mock
             'symbol': 'USDC', 'trades': '0',
             'xfers': '0',
             'fee': '0', 'currentbal': '2000'}]

    @property
    def orders_request_mock_response_for_base_and_quote(self):
        return {"rows": []}

    @property
    def balance_request_mock_response_only_base(self):
        return [
            {'traderaddress': '0x335e5b9a72a3aba693b68bde44feba1252e54cfc',  # noqa: mock
             'symbol': 'AVAX', 'trades': '0',
             'xfers': '0',
             'fee': '0', 'currentbal': '10'}]

    def test_user_stream_balance_update(self):
        pass

    @property
    def balance_event_websocket_update(self):
        pass

    @property
    def expected_latest_price(self):
        return 5.1

    @property
    def expected_supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    @property
    def expected_trading_rule(self):
        mocked_response = self.trading_rules_request_mock_response
        min_order_size = Decimal(f"1e-{mocked_response[0]['basedisplaydecimals']}")
        min_price_inc = Decimal(f"1e-{mocked_response[0]['quotedisplaydecimals']}")
        min_notional = Decimal(mocked_response[0]['mintrade_amnt'])

        return TradingRule(
            trading_pair=self.trading_pair,
            min_order_size=min_order_size,
            min_price_increment=min_price_inc,
            min_base_amount_increment=min_order_size,
            min_notional_size=min_notional
        )

    @property
    def expected_logged_error_for_erroneous_trading_rule(self):
        erroneous_rule = self.trading_rules_request_erroneous_mock_response[0]
        return f"Error parsing the trading pair rule {erroneous_rule}. Skipping."

    @property
    def expected_exchange_order_id(self):
        return "0x000000000000000000000000000000000000000000000000000000006bff4383"  # noqa: mock

    @property
    def is_order_fill_http_update_included_in_status_update(self) -> bool:
        return False

    @property
    def is_order_fill_http_update_executed_during_websocket_order_event_processing(self) -> bool:
        return False

    @property
    def expected_partial_fill_price(self) -> Decimal:
        return Decimal(10500)

    @property
    def expected_partial_fill_amount(self) -> Decimal:
        return Decimal("0.05")

    # todo
    @property
    def expected_fill_fee(self) -> TradeFeeBase:
        return DeductedFromReturnsTradeFee(
            percent_token=self.quote_asset,
            flat_fees=[TokenAmount(token=self.quote_asset, amount=Decimal("0.001"))])

    @property
    def expected_fill_trade_id(self) -> int:
        return 1809034423

    def _expected_initial_status_dict(self) -> Dict[str, bool]:
        return {
            "symbols_mapping_initialized": False,
            "order_books_initialized": False,
            "account_balance": True,
            "trading_rule_initialized": False,
            "user_stream_initialized": False,
        }

    def exchange_symbol_for_tokens(self, base_token: str, quote_token: str) -> str:
        return f"{base_token}/{quote_token}"

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        exchange = DexalotExchange(
            client_config_map=client_config_map,
            dexalot_api_key=self.api_key,
            dexalot_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
        )
        exchange._tx_client = ProgrammableClient()

        exchange._evm_params[self.trading_pair] = {
            "base_coin": self.base_asset,
            "quote_coin": self.quote_asset,
            "base_evmdecimals": Decimal(6),
            "quote_evmdecimals": Decimal(18),
        }
        exchange._account_balances[self.base_asset] = exchange._account_available_balances[self.base_asset] = 10
        exchange._account_balances[self.quote_asset] = exchange._account_available_balances[self.quote_asset] = 10
        return exchange

    def validate_auth_credentials_present(self, request_call: RequestCall):
        self._validate_auth_credentials_taking_parameters_from_argument(
            request_call_tuple=request_call,
            params=request_call.kwargs["headers"]
        )

    def validate_order_creation_request(self, order: InFlightOrder, request_call: RequestCall):
        pass

    def validate_order_cancelation_request(self, order: InFlightOrder, request_call: RequestCall):
        pass

    def validate_order_status_request(self, order: InFlightOrder, request_call: RequestCall):
        request_data = request_call.kwargs["data"]
        self.assertIsNone(request_data)

    def validate_trades_request(self, order: InFlightOrder, request_call: RequestCall):
        request_params = request_call.kwargs["params"]
        self.assertEqual(order.exchange_order_id, str(request_params["orderid"]))

    def configure_order_not_found_error_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        pass

    def configure_one_successful_one_erroneous_cancel_all_response(
            self,
            successful_order: InFlightOrder,
            erroneous_order: InFlightOrder,
            mock_api: aioresponses) -> List[str]:
        """
        :return: a list of all configured URLs for the cancelations
        """
        response = self._order_cancelation_request_successful_mock_response(order=successful_order)
        err_response = self._order_cancelation_request_erroneous_mock_response(order=erroneous_order)

        self.exchange._tx_client._cancel_order_responses.put_nowait(response)
        self.exchange._tx_client._cancel_order_responses.put_nowait(err_response)
        return []

    def configure_completely_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_completely_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_canceled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_canceled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_erroneous_http_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        mock_api.get(regex_url, status=400, callback=callback)
        return url

    def configure_open_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        """
        :return: the URL configured
        """
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_open_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_http_error_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(regex_url, status=401, callback=callback)
        return url

    def configure_partially_filled_order_status_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = self._order_status_request_partially_filled_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_order_not_found_error_order_status_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> List[str]:
        url = web_utils.private_rest_url(CONSTANTS.ORDER_PATH_URL.format(order.exchange_order_id))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        response = {'message': ''}
        mock_api.get(regex_url, body=json.dumps(response), status=400, callback=callback)
        return [url]

    def configure_partial_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_partial_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_full_fill_trade_response(
            self,
            order: InFlightOrder,
            mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None) -> str:
        url = web_utils.private_rest_url(path_url=CONSTANTS.MY_TRADES_PATH_URL)
        regex_url = re.compile(url + r"\?.*")
        response = self._order_fills_request_full_fill_mock_response(order=order)
        mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        return url

    def configure_successful_creation_order_status_response(
            self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = self.order_creation_request_successful_mock_response
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._tx_client._place_order_responses = mock_queue
        return ""

    def configure_erroneous_creation_order_status_response(
            self, callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        creation_response = self.order_creation_request_erroneous_mock_response

        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(
            self._callback_wrapper_with_response, callback=callback, response=creation_response
        )
        self.exchange._tx_client._place_order_responses = mock_queue
        return ""

    def configure_successful_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = self._order_cancelation_request_successful_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._tx_client._cancel_order_responses = mock_queue
        return ""

    def configure_erroneous_cancelation_response(
            self, order: InFlightOrder, mock_api: aioresponses,
            callback: Optional[Callable] = lambda *args, **kwargs: None
    ) -> str:
        response = self._order_cancelation_request_erroneous_mock_response(order=order)
        mock_queue = AsyncMock()
        mock_queue.get.side_effect = partial(self._callback_wrapper_with_response, callback=callback, response=response)
        self.exchange._tx_client._cancel_order_responses = mock_queue
        return ""

    def order_event_for_new_order_websocket_update(self, order: InFlightOrder):
        return {
            'data': {
                'version': 2, 'traderaddress': '0x335e5b9a72A3aBA693B68bDe44FeBA1252e54cFc',  # noqa: mock
                'pair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                'orderId': order.exchange_order_id,
                'clientOrderId': order.client_order_id,
                'price': order.price,
                'totalamount': '0.0', 'quantity': order.amount, 'side': 'SELL', 'sideId': 1, 'type1': 'LIMIT',
                'type1Id': 1,
                'type2': 'GTC', 'type2Id': 0, 'status': 'NEW', 'statusId': 0, 'quantityfilled': '0.0',
                'totalfee': '0.0',
                'code': '', 'blockTimestamp': 1725525853,
                'transactionHash': '0xc49b40fdb17fa478529aac7994575dd20343fb1b77964dc1de6230371aa89058',  # noqa: mock
                'blockNumber': 23064646,
                'blockHash': '0x262b5735b1588c263bf10ffc2685374c7d079f47f94758da0d8da340e0b38fee'  # noqa: mock
            },
            'type': 'orderStatusUpdateEvent'
        }

    def order_event_for_canceled_order_websocket_update(self, order: InFlightOrder):
        return {'data': {
            'version': 2, 'traderaddress': '0x335e5b9a72A3aBA693B68bDe44FeBA1252e54cFc',  # noqa: mock
            'pair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            'orderId': order.exchange_order_id,
            'clientOrderId': order.client_order_id,
            'price': order.price,
            'totalamount': '0.0', 'quantity': order.amount, 'side': 'SELL', 'sideId': 1, 'type1': 'LIMIT',
            'type1Id': 1,
            'type2': 'GTC', 'type2Id': 0, 'status': 'CANCELED', 'statusId': 0, 'quantityfilled': '0.0',
            'totalfee': '0.0',
            'code': '', 'blockTimestamp': 1725525853,
            'transactionHash': '0xc49b40fdb17fa478529aac7994575dd20343fb1b77964dc1de6230371aa89058',  # noqa: mock
            'blockNumber': 23064646,
            'blockHash': '0x262b5735b1588c263bf10ffc2685374c7d079f47f94758da0d8da340e0b38fee'  # noqa: mock
        },
            'type': 'orderStatusUpdateEvent'}

    def order_event_for_full_fill_websocket_update(self, order: InFlightOrder):
        return {'data': {
            'version': 2, 'traderaddress': '0x335e5b9a72A3aBA693B68bDe44FeBA1252e54cFc',  # noqa: mock
            'pair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            'orderId': order.exchange_order_id,
            'clientOrderId': order.client_order_id,
            'price': order.price,
            'totalamount': str(Decimal(order.amount) * Decimal(order.price)), 'quantity': order.amount,
            'side': 'SELL', 'sideId': 1, 'type1': 'LIMIT',
            'type1Id': 1,
            'type2': 'GTC', 'type2Id': 0, 'status': 'FILLED', 'statusId': 0, 'quantityfilled': '0.0',
            'totalfee': '0.0',
            'code': '', 'blockTimestamp': 1725525853,
            'transactionHash': '0xc49b40fdb17fa478529aac7994575dd20343fb1b77964dc1de6230371aa89058',  # noqa: mock
            'blockNumber': 23064646,
            'blockHash': '0x262b5735b1588c263bf10ffc2685374c7d079f47f94758da0d8da340e0b38fee'  # noqa: mock
        },
            'type': 'orderStatusUpdateEvent'}

    def trade_event_for_full_fill_websocket_update(self, order: InFlightOrder):

        return {'data': {
            'version': 1, 'pair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
            'price': order.price, 'quantity': order.amount,
            'makerOrder': order.exchange_order_id,
            'takerOrder': order.exchange_order_id,
            'feeMaker': str(self.expected_fill_fee.flat_fees[0].amount),
            'feeTaker': '0.025', 'takerSide': order.trade_type.name, 'execId': self.expected_fill_trade_id,
            'addressMaker': self.api_key,
            'addressTaker': '0x335e5b9a72A3aBA693B68bDe44FeBA1252e54cFc',  # noqa: mock
            'blockNumber': 23065679,
            'blockTimestamp': 1725527931,
            'blockHash': '0x57ade54126523855c36a89420b1da0b323b406461c3c762af393f6917e80de82',  # noqa: mock
            'transactionHash': '0x0cbef96103b18b7c45cc906596e733521af2a02fd8564b4cd474b7ec3a568e21',  # noqa: mock
            'takerSideId': 1
        },
            'type': 'executionEvent'}

    @aioresponses()
    def test_update_balances(self, mock_api):
        response = self.balance_request_mock_response_for_base_and_quote
        self._configure_balance_response(response=response, mock_api=mock_api)

        url = self.orders_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.orders_request_mock_response_for_base_and_quote
        mock_api.get(regex_url, body=json.dumps(resp))

        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), available_balances[self.quote_asset])
        self.assertEqual(Decimal("10"), total_balances[self.base_asset])
        self.assertEqual(Decimal("2000"), total_balances[self.quote_asset])

        response = self.balance_request_mock_response_only_base

        url = self.orders_url
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        resp = self.orders_request_mock_response_for_base_and_quote
        mock_api.get(regex_url, body=json.dumps(resp))

        self._configure_balance_response(response=response, mock_api=mock_api)
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn(self.quote_asset, available_balances)
        self.assertNotIn(self.quote_asset, total_balances)
        self.assertEqual(Decimal("10"), available_balances[self.base_asset])
        self.assertEqual(Decimal("10"), total_balances[self.base_asset])

    @aioresponses()
    def test_update_order_status_when_canceled(self, mock_api):
        self._simulate_trading_rules_initialized()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.expected_exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("1"),
        )
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_canceled_order_status_response(
            order=order,
            mock_api=mock_api)

        self.async_run_with_timeout(self.exchange._update_order_status())
        cancel_event = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)
        self.assertEqual(order.exchange_order_id, cancel_event.exchange_order_id)
        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(
            self.is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_create_buy_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_create_sell_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.place_sell_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_create_buy_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_snapshot(
            bids=[OrderBookRow(price=4000, amount=20, update_id=1)],
            asks=[OrderBookRow(price=5000, amount=20, update_id=1)],
            update_id=1,
        )

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.exchange.buy(
            trading_pair=self.trading_pair,
            amount=Decimal("10"),
            order_type=OrderType.MARKET,
            price=Decimal("10_000"),
        )
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

    @aioresponses()
    def test_create_sell_market_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_snapshot(
            bids=[OrderBookRow(price=5000, amount=20, update_id=1)],
            asks=[OrderBookRow(price=6000, amount=20, update_id=1)],
            update_id=1,
        )

        self.configure_successful_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.exchange.sell(
            trading_pair=self.trading_pair,
            amount=Decimal("10"),
            order_type=OrderType.MARKET,
            price=Decimal("10_000"),
        )

        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(1, len(self.exchange.in_flight_orders))
        self.assertIn(order_id, self.exchange.in_flight_orders)

    def test_create_order_fails_and_raises_failure_event(self):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_erroneous_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)",
            )
        )

    @aioresponses()
    def test_create_order_fails_when_trading_rule_error_and_raises_failure_event(self, mock_api):
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.configure_erroneous_creation_order_status_response(
            callback=lambda *args, **kwargs: request_sent_event.set()
        )

        order_id_for_invalid_order = self.place_buy_order(
            amount=Decimal("0.0001"), price=Decimal("0.1")
        )
        # The second order is used only to have the event triggered and avoid using timeouts for tests
        order_id = self.place_buy_order()
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertNotIn(order_id_for_invalid_order, self.exchange.in_flight_orders)
        self.assertNotIn(order_id, self.exchange.in_flight_orders)

        self.assertEquals(0, len(self.buy_order_created_logger.event_log))
        failure_event = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(OrderType.LIMIT, failure_event.order_type)
        self.assertEqual(order_id_for_invalid_order, failure_event.order_id)

        self.assertTrue(
            self.is_logged(
                "WARNING",
                "Buy order amount 0.0001 is lower than the minimum order "
                "size 0.001. The order will not be created, increase the "
                "amount to be higher than the minimum order size."
            )
        )
        self.assertTrue(
            self.is_logged(
                "INFO",
                f"Order {order_id} has failed. Order Update: OrderUpdate(trading_pair='{self.trading_pair}', "
                f"update_timestamp={self.exchange.current_timestamp}, new_state={repr(OrderState.FAILED)}, "
                f"client_order_id='{order_id}', exchange_order_id=None, misc_updates=None)"
            )
        )

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order: InFlightOrder = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_successful_cancelation_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.exchange.cancel(trading_pair=order.trading_pair, client_order_id=order.client_order_id)
        self.async_run_with_timeout(request_sent_event.wait())
        self.assertIn(order.client_order_id, self.exchange.in_flight_orders)
        self.assertTrue(order.is_pending_cancel_confirmation)

    @aioresponses()
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        self.configure_erroneous_cancelation_response(
            order=order, mock_api=mock_api, callback=lambda *args, **kwargs: request_sent_event.set()
        )

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=self.client_order_id_prefix + "1")
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEquals(0, len(self.order_cancelled_logger.event_log))
        self.assertTrue(
            any(
                log.msg.startswith("Failed to cancel orders")
                for log in self.log_records
            )
        )

    @aioresponses()
    def test_cancel_lost_order_raises_failure_event_when_request_fails(self, mock_api):
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(1640780000)

        self.exchange.start_tracking_order(
            order_id=self.client_order_id_prefix + "1",
            exchange_order_id=self.exchange_order_id_prefix + "1",
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(self.client_order_id_prefix + "1", self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[self.client_order_id_prefix + "1"]

        for _ in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(
                self.exchange._order_tracker.process_order_not_found(client_order_id=order.client_order_id))

        self.assertNotIn(order.client_order_id, self.exchange.in_flight_orders)

        url = self.configure_erroneous_cancelation_response(
            order=order,
            mock_api=mock_api,
            callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._cancel_lost_orders())
        self.async_run_with_timeout(request_sent_event.wait())

        if url:
            cancel_request = self._all_executed_requests(mock_api, url)[0]
            self.validate_auth_credentials_present(cancel_request)
            self.validate_order_cancelation_request(
                order=order,
                request_call=cancel_request)

        self.assertIn(order.client_order_id, self.exchange._order_tracker.lost_orders)
        self.assertEquals(0, len(self.order_cancelled_logger.event_log))

    @aioresponses()
    def test_cancel_order_not_found_in_the_exchange(self, mock_api):
        # This tests does not apply for Dexalot. The batch orders update message used for cancelations will not
        # detect if the orders exists or not. That will happen when the transaction is executed.
        pass

    @aioresponses()
    def test_lost_order_removed_if_not_found_during_order_status_update(self, mock_api):
        # Disabling this test because the connector has not been updated yet to validate
        # order not found during status update (check _is_order_not_found_during_status_update_error)
        pass

    @aioresponses()
    def test_cancel_two_orders_with_cancel_all_and_one_fails(self, mock_api):
        # This tests does not apply for Dexalot. The batch orders update message used for cancelations will not
        # detect if the orders exists or not. That will happen when the transaction is executed.
        pass

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        pass

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        pass

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        pass

    def _validate_auth_credentials_taking_parameters_from_argument(self,
                                                                   request_call_tuple: RequestCall,
                                                                   params: Dict[str, Any]):
        self.assertIn("x-signature", params)

    def _order_cancelation_request_successful_mock_response(self, order: InFlightOrder) -> Any:
        return "0xdd8fa4a81d8424d8041d0a2aff8dede86c9a951a4acf5d87437c38e16c8548dc"  # noqa: mock

    def _order_cancelation_request_erroneous_mock_response(self, order: InFlightOrder) -> Any:
        return Exception("{'code': -32000, 'message': 'nonce too low: next nonce 125, tx nonce 100'}")

    @property
    def order_creation_request_erroneous_mock_response(self):
        return Exception("{'code': -32000, 'message': 'nonce too low: next nonce 125, tx nonce 100'}")

    def _order_status_request_completely_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {'id': order.exchange_order_id or "dummyOrdId",
                'clientOrderId': order.client_order_id,
                'tx': '0xbb86fc3ba6702b59febd14cebea8fdea89fded7058b2d226eb7b3c2e18507473',  # noqa: mock
                'tradePair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                'type1': order.order_type.name.upper(), 'type2': 'GTC', 'side': order.trade_type.name.upper(),
                'price': str(order.price),
                'quantity': str(order.amount), 'totalAmount': '0.000000000000000000', 'status': 'FILLED',
                'quantityFilled': '0.000000000000000000', 'totalFee': '0.000000000000000000',
                'timestamp': '2024-09-09T17:33:24.000Z', 'updateTs': '2024-09-09T17:56:00.000Z'}

    def _order_status_request_canceled_mock_response(self, order: InFlightOrder) -> Any:
        return {'id': order.exchange_order_id or "dummyOrdId",
                'clientOrderId': order.client_order_id,
                'tx': '0xbb86fc3ba6702b59febd14cebea8fdea89fded7058b2d226eb7b3c2e18507473',  # noqa: mock
                'tradePair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                'type1': order.order_type.name.upper(), 'type2': 'GTC', 'side': order.trade_type.name.upper(),
                'price': str(order.price),
                'quantity': str(order.amount), 'totalAmount': '0.000000000000000000', 'status': 'CANCELED',
                'quantityFilled': '0.000000000000000000', 'totalFee': '0.000000000000000000',
                'timestamp': '2024-09-09T17:33:24.000Z', 'updateTs': '2024-09-09T17:56:00.000Z'}

    def _order_status_request_open_mock_response(self, order: InFlightOrder) -> Any:
        return {'id': order.exchange_order_id or "dummyOrdId",
                'clientOrderId': order.client_order_id,
                'tx': '0xbb86fc3ba6702b59febd14cebea8fdea89fded7058b2d226eb7b3c2e18507473',  # noqa: mock
                'tradePair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                'type1': order.order_type.name.upper(), 'type2': 'GTC', 'side': order.trade_type.name.upper(),
                'price': str(order.price),
                'quantity': str(order.amount), 'totalAmount': '0.000000000000000000', 'status': 'NEW',
                'quantityFilled': '0.000000000000000000', 'totalFee': '0.000000000000000000',
                'timestamp': '2024-09-09T17:33:24.000Z', 'updateTs': '2024-09-09T17:56:00.000Z'}

    def _order_status_request_partially_filled_mock_response(self, order: InFlightOrder) -> Any:
        return {'id': order.exchange_order_id or "dummyOrdId",
                'clientOrderId': order.client_order_id,
                'tx': '0xbb86fc3ba6702b59febd14cebea8fdea89fded7058b2d226eb7b3c2e18507473',  # noqa: mock
                'tradePair': self.exchange_symbol_for_tokens(self.base_asset, self.quote_asset),
                'type1': order.order_type.name.upper(), 'type2': 'GTC', 'side': order.trade_type.name.upper(),
                'price': str(order.price),
                'quantity': str(order.amount), 'totalAmount': '0.000000000000000000', 'status': 'PARTIAL',
                'quantityFilled': '0.000000000000000000', 'totalFee': '0.000000000000000000',
                'timestamp': '2024-09-09T17:33:24.000Z', 'updateTs': '2024-09-09T17:56:00.000Z'}

    def _order_fills_request_partial_fill_mock_response(self, order: InFlightOrder):
        return [{'env': 'production-multi-subnet', 'execid': int(self.expected_fill_trade_id), 'type': 'M',
                 'orderid': '0x000000000000000000000000000000000000000000000000000000006bd377e9',  # noqa: mock
                 'traderaddress': '0x335e5b9a72a3aba693b68bde44feba1252e54cfc',
                 'tx': '0xe34b34f8153ca90fa289e0f5627efec649a84d27eb057b2d6560f663a180c69c',  # noqa: mock
                 'pair': self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset), 'side': 1,
                 'quantity': str(self.expected_partial_fill_amount), 'price': str(self.expected_partial_fill_price),
                 'fee': str(self.expected_fill_fee.flat_fees[0].amount),
                 'feeunit': 'USDC', 'ts': '2024-09-05T08:44:29.000Z'}]

    def _order_fills_request_full_fill_mock_response(self, order: InFlightOrder):
        return [{'env': 'production-multi-subnet', 'execid': int(self.expected_fill_trade_id), 'type': 'T',
                 'orderid': order.exchange_order_id,
                 'traderaddress': '0x335e5b9a72a3aba693b68bde44feba1252e54cfc',  # noqa: mock
                 'tx': '0x0cbef96103b18b7c45cc906596e733521af2a02fd8564b4cd474b7ec3a568e21',  # noqa: mock
                 'pair': self.exchange_symbol_for_tokens(order.base_asset, order.quote_asset),
                 'side': 1, 'quantity': str(order.amount), 'price': str(order.price),
                 'fee': str(self.expected_fill_fee.flat_fees[0].amount),
                 'feeunit': str(self.expected_fill_fee.flat_fees[0].token), 'ts': '2024-09-05T09:18:51.000Z'}]

    @property
    def latest_prices_request_mock_response(self):
        pass

    @property
    def latest_prices_url(self):
        pass

    @aioresponses()
    def test_get_last_trade_prices(self, mock_api):
        order_book = OrderBook()
        self.exchange.order_book_tracker._order_books[self.trading_pair] = order_book
        order_book.apply_trade(
            OrderBookTradeEvent(self.trading_pair, 1499865549, TradeType.BUY, Decimal(5.1), Decimal(10), '123')
        )

        latest_prices: Dict[str, float] = self.async_run_with_timeout(
            self.exchange.get_last_traded_prices(trading_pairs=[self.trading_pair])
        )

        self.assertEqual(1, len(latest_prices))
        self.assertEqual(self.expected_latest_price, latest_prices[self.trading_pair])

    def get_trading_rule_rest_msg(self):
        return [
            {'env': 'production-multi-subnet', 'pair': 'AVAX/USDC', 'base': 'AVAX', 'quote': 'USDC',
             'basedisplaydecimals': 3,
             'quotedisplaydecimals': 3, 'baseaddress': '0x0000000000000000000000000000000000000000',  # noqa: mock
             'quoteaddress': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',  # noqa: mock
             'mintrade_amnt': '5.000000000000000000',
             'maxtrade_amnt': '50000.000000000000000000', 'base_evmdecimals': 18, 'quote_evmdecimals': 6,
             'allowswap': True,
             'auctionmode': 0, 'auctionendtime': None, 'status': 'deployed', 'maker_rate_bps': 10, 'taker_rate_bps': 12,
             'allowed_slippage_pct': 5, 'additional_ordertypes': 0, 'taker_fee': 0.001, 'maker_fee': 0.0012}
        ]

    def _simulate_trading_rules_initialized(self):
        mocked_response = self.get_trading_rule_rest_msg()
        self.exchange._initialize_trading_pair_symbols_from_exchange_info(mocked_response)
        min_order_size = Decimal(f"1e-{mocked_response[0]['basedisplaydecimals']}")
        min_price_inc = Decimal(f"1e-{mocked_response[0]['quotedisplaydecimals']}")
        min_notional = Decimal(mocked_response[0]['mintrade_amnt'])

        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=min_order_size,
                min_price_increment=min_price_inc,
                min_base_amount_increment=min_order_size,
                min_notional_size=min_notional
            )
        }
