import asyncio
import textwrap
import traceback
from decimal import Decimal
from logging import DEBUG, ERROR, INFO
from os import path
from pathlib import Path
from typing import Any, Dict

import jsonpickle

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.clob.clob_types import OrderSide as XRPLOrderSide
from hummingbot.connector.gateway.clob.clob_utils import convert_trading_pair
from hummingbot.connector.gateway.clob.gateway_xrpldex_clob import GatewayXrpldexCLOB

# from hummingbot.core.data_type.common import OrderType, TradeType
# from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

from .utils import decimal_zero, format_currency, format_line, parse_order_book

# nest_asyncio.apply()


class TestXRPLDEXGateway(ScriptStrategyBase):
    _initialized: bool = False
    _is_busy: bool = False
    _script_name: str
    _connector_id: str = "xrpldex_xrpl_testnet"
    # _base_token: str = "USD.rh8LssQyeBdEXk7Zv86HxHrx8k2R2DBUrx"
    _base_token: str = "XRP"
    _quote_token: str = "VND.rh8LssQyeBdEXk7Zv86HxHrx8k2R2DBUrx"
    _trading_pair = f"{_base_token}-{_quote_token}"
    _refresh_timestamp: int
    _gateway: GatewayHttpClient
    _connector: GatewayXrpldexCLOB
    _market: str
    _market_info: Dict[str, Any]

    _configuration = {
        "chain": "xrpl",
        "network": "testnet",
        "connector": "xrpldex",
        "refresh_interval": 20,
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

    _flags = {
        "proceed_to_create_orders": True,
        # "proceed_to_check_created_orders_status": False,
        "proceed_to_replace_orders": False,
        # "proceed_to_check_replaced_orders_status": False,
        "proceed_to_cancel_orders": False,
        # "proceed_to_check_cancelled_orders_status": False,
    }

    _created_orders: Dict[str, Any]
    _replaced_orders: Dict[str, Any]
    _cancelled_orders: Dict[str, Any]

    markets = {
        _connector_id: [_trading_pair]
    }

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        try:
            self._log(DEBUG, """__init__... start""")

            super().__init__(connectors)

            self._script_name = path.basename(Path(__file__).parent)
            self._market = convert_trading_pair(self._trading_pair)
            self._connector: GatewayXrpldexCLOB = self.connectors[self._connector_id]
            self._gateway: GatewayHttpClient = self._connector.get_gateway_instance()
            self._refresh_timestamp = 0
            self._initialized = True
        finally:
            self._log(DEBUG, """__init__... end""")

    def on_tick(self):
        try:
            self._log(DEBUG, """on_tick... start""")
            if not self._is_busy and (self._refresh_timestamp <= self.current_timestamp):
                asyncio.ensure_future(self._async_on_tick())

        except Exception as exception:
            self._handle_error(exception)
        finally:
            self._log(DEBUG, """on_tick... end""")

    async def _async_on_tick(self):
        try:
            self._log(DEBUG, """_async_on_tick... start""")

            self._is_busy = True
            await self._show_summary()
            await self._script_create_orders()
            # await self._script_check_created_orders_status()
            await self._show_summary()
            await self._script_replace_orders()
            # await self._script_check_replaced_orders_status()
            await self._show_summary()
            await self._script_cancel_orders()
            # await self._script_check_cancelled_orders_status()
            await self._show_summary()
        finally:
            self._refresh_timestamp = int(self._configuration["refresh_interval"]) + self.current_timestamp
            self._is_busy = False
            HummingbotApplication.main_application().stop()

            self._log(DEBUG, """_async_on_tick... end""")

    async def _script_create_orders(self):
        if not self._flags["proceed_to_create_orders"]:
            return
        try:
            self._log(DEBUG, """_script_place_orders... start""")
            sell_order = {
                "marketName": self._market,
                "walletAddress": self._connector.address,
                "side": XRPLOrderSide.SELL.value[0],
                "amount": 1,
                "price": 1000,
            }

            buy_order = {
                "marketName": self._market,
                "walletAddress": self._connector.address,
                "side": XRPLOrderSide.BUY.value[0],
                "amount": 1,
                "price": 100,
            }
            sell_orders_rsp = await self._post_orders(orders=[sell_order, sell_order, sell_order])
            buy_orders_rsp = await self._post_orders(orders=[buy_order, buy_order, buy_order])

            created_orders = dict()
            created_orders.update(sell_orders_rsp)
            created_orders.update(buy_orders_rsp)
            self._created_orders = created_orders
        finally:
            self._flags["proceed_to_create_orders"] = False
            self._flags["proceed_to_replace_orders"] = True
            self._log(DEBUG, """_script_place_orders... end""")

    async def _script_check_created_orders_status(self):
        if not self._flags["proceed_to_check_created_orders_status"]:
            return
        try:
            self._log(DEBUG, """_script_cancel_orders... start""")
            keep_looping = False
            order_to_check = []
            for key, value in self._created_orders.items():
                order_to_check.append({
                    "signature": value["signature"],
                    "sequence": int(key)
                })

            resp = await self._get_orders(order_to_check)

            if len(resp.values()) == 0:
                keep_looping = True

            for value in resp.values():
                if value["status"] != "OPEN":
                    keep_looping = True

        finally:
            self._flags["proceed_to_check_created_orders_status"] = keep_looping
            self._flags["proceed_to_replace_orders"] = not keep_looping
            self._log(DEBUG, """proceed_to_check_created_orders_status... end""")

    async def _script_replace_orders(self):
        if not self._flags["proceed_to_replace_orders"]:
            return

        try:
            self._log(DEBUG, """_script_replace_orders... start""")
            replace_orders = []
            for key in self._created_orders:
                replace_orders.append({
                    "marketName": self._market,
                    "walletAddress": self._connector.address,
                    "side": self._created_orders[key]["side"],
                    "amount": 10,
                    "price": 1000 if self._created_orders[key]["side"] == "SELL" else 100,
                    "sequence": int(key)
                })

            resp = await self._post_orders(orders=replace_orders)
            self._replaced_orders = resp
        finally:
            self._flags["proceed_to_replace_orders"] = False
            self._flags["proceed_to_cancel_orders"] = True
            self._log(DEBUG, """_script_replace_orders... end""")

    async def _script_check_replaced_orders_status(self):
        if not self._flags["proceed_to_check_replaced_orders_status"]:
            return
        try:
            self._log(DEBUG, """_script_check_replaced_orders_status... start""")
            keep_looping = False
            order_to_check = []
            for key, value in self._replaced_orders.items():
                order_to_check.append({
                    "signature": value["signature"],
                    "sequence": int(key)
                })

            resp = await self._get_orders(order_to_check)

            if len(resp.values()) == 0:
                keep_looping = True

            for value in resp.values():
                if value["status"] != "OPEN":
                    keep_looping = True
        finally:
            self._flags["proceed_to_check_replaced_orders_status"] = keep_looping
            self._flags["proceed_to_cancel_orders"] = not keep_looping
            self._log(DEBUG, """_script_check_replaced_orders_status... end""")

    async def _script_cancel_orders(self):
        if not self._flags["proceed_to_cancel_orders"]:
            return
        try:
            self._log(DEBUG, """_script_cancel_orders... start""")
            cancel_orders = []
            for key in self._replaced_orders:
                cancel_orders.append({
                    "walletAddress": self._connector.address,
                    "offerSequence": int(key),
                })

            resp = await self._cancel_orders(orders=cancel_orders)
            self._cancelled_orders = resp

        finally:
            self._flags["proceed_to_cancel_orders"] = False
            self._flags["proceed_to_create_orders"] = True
            self._log(DEBUG, """_script_cancel_orders... end""")

    async def _script_check_cancelled_orders_status(self):
        if not self._flags["proceed_to_check_cancelled_orders_status"]:
            return
        try:
            self._log(DEBUG, """_script_check_cancelled_orders_status... start""")
            keep_looping = False
            order_to_check = []
            for key, value in self._cancelled_orders.items():
                order_to_check.append({
                    "signature": value["signature"],
                    "sequence": int(key)
                })

            resp = await self._get_orders(order_to_check)

            if len(resp.values()) == 0:
                keep_looping = True

            for value in resp.values():
                if value["status"] != "CANCELED":
                    keep_looping = True
        finally:
            self._flags["proceed_to_check_cancelled_orders_status"] = keep_looping
            self._flags["proceed_to_create_orders"] = not keep_looping
            self._log(DEBUG, """_script_check_cancelled_orders_status... end""")

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

                self._log(INFO, f"""gateway.xrpl_get_balances:\nrequest:\n{self._dump(request)}""")

                response = await self._gateway.xrpl_get_balances(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO, f"""gateway.xrpl_get_balances:\nresponse:\n{self._dump(response)}""")
        finally:
            self._log(DEBUG, """_get_balances... end""")

    async def _get_market(self):
        try:
            self._log(INFO, """_get_market... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "name": self._market
                }

                response = await self._gateway.xrpldex_get_markets(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.clob_get_markets:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")  # noqa
        finally:
            self._log(INFO, """_get_market... end""")

    async def _get_orders(self, orders=None):
        try:
            self._log(INFO, """_get_orders... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "orders": orders
                }

                response = await self._gateway.xrpldex_get_orders(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway._get_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")  # noqa
        finally:
            self._log(INFO, """_get_orders... end""")

    async def _get_order_book(self):
        try:
            self._log(INFO, """_get_order_book... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "market_name": self._market
                }

                response = await self._gateway.xrpldex_get_order_books(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.clob_get_order_books:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")  # noqa
        finally:
            self._log(INFO, """_get_order_book... end""")

    async def _get_market_price(self) -> Decimal:
        try:
            self._log(INFO, """_get_market_price... start""")

            return Decimal((await self._get_ticker())["price"])
        except Exception as exception:
            self._handle_error(exception)
        finally:
            self._log(INFO, """_get_market_price... end""")

    async def _get_ticker(self) -> Dict[str, Any]:
        try:
            self._log(INFO, """_get_ticker... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "market_name": self._market
                }

                response = await self._gateway.xrpldex_get_tickers(**request)

                return response
            except Exception as exception:
                response = exception

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.clob_get_tickers:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")  # noqa

        finally:
            self._log(INFO, """_get_ticker... end""")

    async def _get_open_orders_balance(self) -> Dict[str, Decimal]:
        open_orders = await self._get_open_orders()
        open_orders_base_amount = decimal_zero
        open_orders_quote_amount = decimal_zero
        for order in open_orders[self._market].values():
            if order['side'] == XRPLOrderSide.BUY.value[0]:
                open_orders_base_amount += Decimal(order["amount"])
            if order['side'] == XRPLOrderSide.SELL.value[0]:
                open_orders_quote_amount += Decimal(order["amount"]) * Decimal(order['price'])

        return {"base": open_orders_base_amount, "quote": open_orders_quote_amount}

    async def _get_open_orders(self) -> Dict[str, Any]:
        try:
            self._log(INFO, """_get_open_orders... start""")

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

                response = await self._gateway.xrpldex_get_open_orders(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.clob_get_open_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")  # noqa
        finally:
            self._log(INFO, """_get_open_orders... end""")

    async def _post_orders(self, order=None, orders=None):
        try:
            self._log(INFO, """_post_orders... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "wait_until_included_in_block": True,
                    "order": order,
                    "orders": orders
                }

                response = await self._gateway.xrpldex_post_orders(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway._post_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")  # noqa
        finally:
            self._log(INFO, """_post_orders... end""")

    async def _cancel_orders(self, order=None, orders=None):
        try:
            self._log(INFO, """_cancel_orders... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "wait_until_included_in_block": True,
                    "order": order,
                    "orders": orders
                }

                response = await self._gateway.xrpldex_delete_orders(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway._cancel_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")  # noqa
        finally:
            self._log(INFO, """_cancel_orders... end""")
        pass

    async def _check_open_orders_status(self):

        pass

    async def _show_summary(self):
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

        open_orders_balance = await self._get_open_orders_balance()
        self._summary["balance"]["orders"]["base"] = open_orders_balance["base"]
        self._summary["balance"]["orders"]["quote"] = open_orders_balance["quote"]

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
                {format_line(f"  {self._quote_token}:", format_currency(self._summary["balance"]["wallet"]["quote"], 4))}
                -Market:
                {format_line(f"  tickSize:", format_currency(Decimal(self._market_info["tickSize"]), 15))}
                {format_line(f"  minimumOrderSize:", format_currency(Decimal(self._market_info["minimumOrderSize"]), 15))}
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
