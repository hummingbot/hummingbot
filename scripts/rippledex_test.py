import asyncio
import math  # noqa
import textwrap
import traceback
from array import array  # noqa
from decimal import Decimal
from logging import CRITICAL, DEBUG, ERROR, INFO, WARNING  # noqa
from os import path
from pathlib import Path
from typing import Any, Dict, List  # noqa

import jsonpickle
import nest_asyncio
import yaml  # noqa

from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.clob.clob_types import OrderSide as RippleOrderSide
from hummingbot.connector.gateway.clob.clob_utils import convert_order_side, convert_trading_pair  # noqa
from hummingbot.connector.gateway.clob.gateway_rippledex_clob import GatewayRippledexCLOB
from hummingbot.core.data_type.common import OrderType, TradeType  # noqa
from hummingbot.core.data_type.order_candidate import OrderCandidate  # noqa
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

# from .utils import MidPriceStrategy  # noqa
# from .utils import alignment_column  # noqa
# from .utils import calculate_mid_price  # noqa
# from .utils import format_lines  # noqa
# from .utils import format_percentage  # noqa
from .utils import decimal_zero, format_currency, format_line, parse_order_book

nest_asyncio.apply()


class TestRippleDEXGateway(ScriptStrategyBase):
    _initialized: bool = False
    _is_busy: bool = False
    _script_name: str
    _connector_id: str = "rippleDEX_ripple_testnet"
    _base_token: str = "USD.rh8LssQyeBdEXk7Zv86HxHrx8k2R2DBUrx"
    _quote_token: str = "VND.rh8LssQyeBdEXk7Zv86HxHrx8k2R2DBUrx"
    _trading_pair = f"{_base_token}-{_quote_token}"
    _refresh_timestamp: int
    _gateway: GatewayHttpClient
    _connector: GatewayRippledexCLOB
    _market: str
    _market_info: Dict[str, Any]

    _configuration = {
        "chain": "ripple",
        "network": "testnet",
        "connector": "rippleDEX",
        "refresh_interval": 60,
    }

    _summary = {
        "price": {
            "ticker_price": decimal_zero,
            "market_price": decimal_zero,
            "market_mid_price": decimal_zero,
        },
        "balance": {
            "wallet": {
                "base": decimal_zero,
                "quote": decimal_zero
            },
            "orders": {
                "base": decimal_zero,
                "quote": decimal_zero,
            }
        },
        "order_book": {
            "bids": Any,
            "asks": Any,
            "top_bid": decimal_zero,
            "top_ask": decimal_zero,
        }
    }

    markets = {
        _connector_id: [_trading_pair]
    }

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        try:
            self._log(DEBUG, """__init__... start""")

            super().__init__(connectors)

            self._script_name = path.basename(Path(__file__).parent)
            self._market = convert_trading_pair(self._trading_pair)
            self._connector: GatewayRippledexCLOB = self.connectors[self._connector_id]
            self._gateway: GatewayHttpClient = self._connector.get_gateway_instace()
            self._refresh_timestamp = 0
            self._initialized = True
        finally:
            self._log(DEBUG, """__init__... end""")

    def on_tick(self):
        try:
            self._log(DEBUG, """on_tick... start""")
            # if not self._initialized:
            #     asyncio.get_event_loop().run_until_complete(self._initialize())

            if not self._is_busy and (self._refresh_timestamp <= self.current_timestamp):
                asyncio.get_event_loop().run_until_complete(self._async_on_tick())

        except Exception as exception:
            self._handle_error(exception)
        finally:
            self._log(DEBUG, """on_tick... end""")

    # async def _initialize(self):
    #     try:
    #         self._log(DEBUG, """_initialize... start""")
    #
    #         self.notify_hb_app(f"Starting {self._script_name} script...")
    #
    #         # noinspection PyTypeChecker
    #         self._connector: GatewayRippledexCLOB = self.connectors[self._connector_id]
    #         self._gateway: GatewayHttpClient = self._connector.get_gateway_instace()
    #
    #         self._market_info = await self._get_market()
    #
    #         self._initialized = True
    #     finally:
    #         self._log(DEBUG, """_initialize... end""")

    async def _async_on_tick(self):
        try:
            self._log(DEBUG, """_async_on_tick... start""")

            self._is_busy = True

            # proposal: List[OrderCandidate] = await self._create_proposal()
            # candidate_orders: List[OrderCandidate] = self._adjust_proposal_to_budget(proposal)

            # replaced_orders = await self._replace_orders(candidate_orders)
            # await self._cancel_duplicated_and_remaining_orders(candidate_orders, replaced_orders)

            balances = await self._get_balances()
            self._summary["balance"]["wallet"]["base"] = Decimal(balances["balances"][self._base_token])
            self._summary["balance"]["wallet"]["quote"] = Decimal(balances["balances"][self._quote_token])
            order_book = await self._get_order_book()
            bids, asks, top_ask, top_bid = parse_order_book(order_book)
            self._summary["order_book"]["bids"] = bids
            self._summary["order_book"]["asks"] = asks
            self._summary["order_book"]["top_ask"] = top_ask
            self._summary["order_book"]["top_bid"] = top_bid

            ticker_price = await self._get_market_price()
            self._summary["price"]["ticker_price"] = ticker_price
            self._market_info = await self._get_market()

            buy_order = {
                "marketName": self._market,
                "walletAddress": self._connector.address,
                "side": RippleOrderSide.BUY.value[0],
                "amount": 5,
                "price": 1500,
            }
            buy_order_rsp = await self._post_orders(order=buy_order)

            sell_order = {
                "marketName": self._market,
                "walletAddress": self._connector.address,
                "side": RippleOrderSide.SELL.value[0],
                "amount": 5,
                "price": 3000,
            }
            sell_order_rsp = await self._post_orders(order=sell_order)

            replace_buy_order = {
                "marketName": self._market,
                "walletAddress": self._connector.address,
                "side": RippleOrderSide.BUY.value[0],
                "amount": 10,
                "price": 1500,
                "sequence": buy_order_rsp["sequence"]
            }
            replace_buy_order_rsp = await self._post_orders(order=replace_buy_order)

            replace_sell_order = {
                "marketName": self._market,
                "walletAddress": self._connector.address,
                "side": RippleOrderSide.SELL.value[0],
                "amount": 10,
                "price": 3000,
                "sequence": sell_order_rsp["sequence"]
            }
            replace_sell_order_rsp = await self._post_orders(order=replace_sell_order)

            open_orders_balance = await self._get_open_orders_balance()
            self._summary["balance"]["orders"]["base"] = open_orders_balance["base"]
            self._summary["balance"]["orders"]["quote"] = open_orders_balance["quote"]

            self._show_summary()

            delete_orders = [
                {
                    "walletAddress": self._connector.address,
                    "offerSequence": replace_buy_order_rsp["sequence"]
                },
                {
                    "walletAddress": self._connector.address,
                    "offerSequence": replace_sell_order_rsp["sequence"]
                }
            ]

            await self._cancel_orders(orders=delete_orders)
            # self._show_orderbook()
        finally:
            self._refresh_timestamp = int(self._configuration["refresh_interval"]) + self.current_timestamp
            self._is_busy = False
            HummingbotApplication.main_application().stop()

            self._log(DEBUG, """_async_on_tick... end""")

    async def _get_balances(self) -> Dict[str, Any]:
        try:
            self._log(DEBUG, """_get_balances... start""")

            response = None
            try:
                request = {
                    "network": self._configuration["network"],
                    "address": self._connector.address,
                    "token_symbols": [self._base_token, self._quote_token]
                }

                self._log(INFO, f"""gateway.ripple_get_balances:\nrequest:\n{self._dump(request)}""")

                response = await self._gateway.ripple_get_balances(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO, f"""gateway.ripple_get_balances:\nresponse:\n{self._dump(response)}""")
        finally:
            self._log(DEBUG, """_get_balances... end""")

    async def _get_market(self):
        try:
            self._log(DEBUG, """_get_market... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "name": self._market
                }

                response = await self._gateway.rippledex_get_markets(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO, f"""gateway.clob_get_markets:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""") # noqa
        finally:
            self._log(DEBUG, """_get_market... end""")

    async def _get_order_book(self):
        try:
            self._log(DEBUG, """_get_order_book... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "market_name": self._market
                }

                response = await self._gateway.rippledex_get_order_books(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO, f"""gateway.clob_get_order_books:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""") # noqa
        finally:
            self._log(DEBUG, """_get_order_book... end""")

    async def _get_market_price(self) -> Decimal:
        try:
            self._log(DEBUG, """_get_market_price... start""")

            return Decimal((await self._get_ticker())["price"])
        except Exception as exception:
            self._handle_error(exception)
        finally:
            self._log(DEBUG, """_get_market_price... end""")

    async def _get_ticker(self) -> Dict[str, Any]:
        try:
            self._log(DEBUG, """_get_ticker... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "market_name": self._market
                }

                response = await self._gateway.rippledex_get_tickers(**request)

                return response
            except Exception as exception:
                response = exception

                raise exception
            finally:
                self._log(INFO, f"""gateway.clob_get_tickers:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""") # noqa

        finally:
            self._log(DEBUG, """_get_ticker... end""")

    async def _get_open_orders_balance(self) -> Dict[str, Decimal]:
        open_orders = await self._get_open_orders()
        open_orders_base_amount = decimal_zero
        open_orders_quote_amount = decimal_zero
        for order in open_orders[self._market].values():
            if order['side'] == RippleOrderSide.BUY.value[0]:
                open_orders_base_amount += Decimal(order["amount"])
            if order['side'] == RippleOrderSide.SELL.value[0]:
                open_orders_quote_amount += Decimal(order["amount"]) * Decimal(order['price'])

        return {"base": open_orders_base_amount, "quote": open_orders_quote_amount}

    async def _get_open_orders(self) -> Dict[str, Any]:
        try:
            self._log(DEBUG, """_get_open_orders... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "order": {
                        "marketName": self._market,
                        "walletAddress": self._connector.address,
                    }
                }

                response = await self._gateway.rippledex_get_open_orders(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO, f"""gateway.clob_get_open_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""") # noqa
        finally:
            self._log(DEBUG, """_get_open_orders... end""")

    async def _post_orders(self, order=None, orders=None):
        # TODO: Just post buy orders, do once for now
        try:
            self._log(DEBUG, """_post_orders... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "order": order,
                    "orders": orders
                }

                response = await self._gateway.rippledex_post_orders(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO, f"""gateway._post_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""") # noqa
        finally:
            self._log(DEBUG, """_post_orders... end""")

    async def _cancel_orders(self, order=None, orders=None):
        try:
            self._log(DEBUG, """_cancel_orders... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "order": order,
                    "orders": orders
                }

                response = await self._gateway.rippledex_delete_orders(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO, f"""gateway._cancel_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""") # noqa
        finally:
            self._log(DEBUG, """_cancel_orders... end""")
        pass

    async def _check_open_orders_status(self):

        pass

    def _show_summary(self):
        self._log(
            INFO,
            textwrap.dedent(
                f"""\
                Price:
                {format_line(" Middle:", format_currency(self._summary["price"]["ticker_price"], 6))}
                {format_line(" Top Ask:", format_currency(self._summary["order_book"]["top_ask"], 6))}
                {format_line(" Top Bid:", format_currency(self._summary["order_book"]["top_bid"], 6))}
                Balance:
                -Wallet:
                {format_line(f"  {self._base_token}:", format_currency(self._summary["balance"]["wallet"]["base"], 4))}
                {format_line(f"  {self._quote_token}:", format_currency(self._summary["balance"]["wallet"]["quote"], 4))} # noqa
                -Market:
                {format_line(f"  tickSize:", format_currency(Decimal(self._market_info["tickSize"]), 15))}
                {format_line(f"  minimumOrderSize:", format_currency(Decimal(self._market_info["minimumOrderSize"]), 15))} # noqa
                -Open Orders Balance:
                {format_line(f"  BUY:", format_currency(self._summary["balance"]["orders"]["base"], 4))}
                {format_line(f"  SELL:", format_currency(self._summary["balance"]["orders"]["quote"], 4))}
                """
            ),
            True
        )

    def _show_orderbook(self):
        self._log(
            INFO,
            textwrap.dedent(
                f"""\
                <b>OrderBook</b>:
                {self._dump(self._summary["order_book"])}
                """

            ),
            True
        )

    def _log(self, level: int, message: str, use_telegram: bool = False, *args, **kwargs):
        self.logger().log(level, message, *args, **kwargs)

        if use_telegram:
            self.notify_hb_app(f"""{message}""")

    def _handle_error(self, exception: Exception):
        try:
            message = f"""<b>ERROR</b>: {type(exception).__name__} {str(exception)}"""
            self._log(ERROR, message, True)
        finally:
            raise exception

    @staticmethod
    def _dump(target: Any):
        try:
            return jsonpickle.encode(target, unpicklable=True, indent=2)
        except (Exception,):
            return target
