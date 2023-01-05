import asyncio
import math
import time
import traceback
from decimal import Decimal
from enum import Enum
from logging import DEBUG, ERROR, INFO, WARNING
from os import path
from pathlib import Path
from typing import Any, Dict, List, Union

import jsonpickle
import numpy as np

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.connector.gateway.clob.clob_types import OrderSide as XRPLOrderSide, OrderType as XRPLOrderType
from hummingbot.connector.gateway.clob.clob_utils import convert_order_side, convert_trading_pair
from hummingbot.connector.gateway.clob.gateway_xrpldex_clob import GatewayXrpldexCLOB
from hummingbot.core.clock import Clock
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.order_candidate import OrderCandidate
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

from .utils import format_currency, format_line

decimal_zero = Decimal(0)
alignment_column = 11


class XRPLCLOBPMMExample(ScriptStrategyBase):
    # Set your network and trading pair here
    _connector_id: str = "xrpldex_xrpl_testnet"
    # _base_token: str = "XRP"
    _base_token: str = "USD.rh8LssQyeBdEXk7Zv86HxHrx8k2R2DBUrx"
    _quote_token: str = "VND.rh8LssQyeBdEXk7Zv86HxHrx8k2R2DBUrx"
    _trading_pair = f"{_base_token}-{_quote_token}"

    markets = {
        _connector_id: [_trading_pair]
    }

    class MiddlePriceStrategy(Enum):
        SAP = 'SIMPLE_AVERAGE_PRICE'
        WAP = 'WEIGHTED_AVERAGE_PRICE'
        VWAP = 'VOLUME_WEIGHTED_AVERAGE_PRICE'

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        try:
            self._log(DEBUG, """__init__... start""")
            super().__init__(connectors)

            self._can_run: bool = True
            self._script_name = path.basename(Path(__file__))
            self._configuration = {
                "chain": "xrpl",
                "network": "testnet",
                "connector": "xrpldex",
                "strategy": {
                    "layers": [
                        {
                            "bid": {
                                "quantity": 1,
                                "spread_percentage": 1,
                                "max_liquidity_in_quote_token": 20000
                            },
                            "ask": {
                                "quantity": 1,
                                "spread_percentage": 1,
                                "max_liquidity_in_quote_token": 20000
                            }
                        },
                        {
                            "bid": {
                                "quantity": 1,
                                "spread_percentage": 5,
                                "max_liquidity_in_quote_token": 20000
                            },
                            "ask": {
                                "quantity": 1,
                                "spread_percentage": 5,
                                "max_liquidity_in_quote_token": 20000
                            }
                        },
                        {
                            "bid": {
                                "quantity": 1,
                                "spread_percentage": 10,
                                "max_liquidity_in_quote_token": 20000
                            },
                            "ask": {
                                "quantity": 1,
                                "spread_percentage": 10,
                                "max_liquidity_in_quote_token": 20000
                            }
                        },
                    ],
                    "tick_interval": 30,
                    "xrpldex_order_type": "LIMIT",
                    "price_strategy": "middle",
                    "middle_price_strategy": "VWAP",
                    "cancel_all_orders_on_start": True,
                    "cancel_all_orders_on_stop": True,
                    "run_only_once": False
                },
                "logger": {
                    "level": "INFO"
                }
            }

            self._summary = {
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
                    "top_bid": decimal_zero,
                    "top_ask": decimal_zero,
                }
            }

            self._owner_address = None
            self._hb_trading_pair = None
            self._is_busy: bool = False
            self._initialized: bool = False
            self._refresh_timestamp: int = self.current_timestamp
            self._market: str
            self._gateway: GatewayHttpClient
            self._connector: GatewayXrpldexCLOB
            self._market_info: Dict[str, Any]
            self._balances: Dict[str, Any] = {}
            self._tickers: Dict[str, Any]
            self._open_orders: Dict[str, Any] = None
            self._filled_orders: Dict[str, Any]
            self._vwap_threshold = 50
            self._int_zero = int(0)
            self._float_zero = float(0)
            self._float_infinity = float('inf')
            self._decimal_zero = Decimal(0)
            self._decimal_infinity = Decimal("Infinity")

        finally:
            self._log(DEBUG, """__init__... end""")

    def get_markets_definitions(self) -> Dict[str, List[str]]:
        return self.markets

    # noinspection PyAttributeOutsideInit
    async def initialize(self):
        try:
            if self._is_busy or (self._refresh_timestamp > self.current_timestamp):
                return

            self._log(DEBUG, """_initialize... start""")

            self.logger().setLevel(self._configuration["logger"].get("level", "INFO"))

            self._initialized = False
            self._is_busy = True

            self._hb_trading_pair = self._trading_pair
            self._market = convert_trading_pair(self._hb_trading_pair)

            # noinspection PyTypeChecker
            self._connector: GatewayXrpldexCLOB = self.connectors[self._connector_id]
            self._gateway: GatewayHttpClient = self._connector.get_gateway_instance()

            self._owner_address = self._connector.address

            self._market_info = await self._get_market()

            if self._configuration["strategy"]["cancel_all_orders_on_start"]:
                await self._cancel_all_orders()

        except Exception as exception:
            self._handle_error(exception)
        finally:
            waiting_time = self._calculate_waiting_time(self._configuration["strategy"]["tick_interval"])
            self._log(DEBUG, f"""Waiting for {waiting_time}s.""")
            self._refresh_timestamp = waiting_time + self.current_timestamp
            self._initialized = True
            self._is_busy = False
            self._log(DEBUG, """_initialize... end""")

    def on_tick(self):
        try:
            self._log(DEBUG, """on_tick... start""")
            if self._initialized:
                asyncio.ensure_future(self.async_on_tick())
            else:
                asyncio.ensure_future(self.initialize())

        except Exception as exception:
            self._handle_error(exception)
        finally:
            self._log(DEBUG, """on_tick... end""")

    async def async_on_tick(self):
        if (not self._is_busy) and (not self._can_run):
            HummingbotApplication.main_application().stop()

        if self._is_busy or (self._refresh_timestamp > self.current_timestamp):
            return

        try:
            self._log(DEBUG, """on_tick... start""")

            self._is_busy = True

            await self._get_open_orders(use_cache=False)
            await self._get_balances(use_cache=False)

            open_orders_balance = await self._get_open_orders_balance()
            self._summary["balance"]["orders"]["base"] = open_orders_balance["base"]
            self._summary["balance"]["orders"]["quote"] = open_orders_balance["quote"]

            proposal: List[OrderCandidate] = await self._create_proposal()
            candidate_orders: List[OrderCandidate] = await self._adjust_proposal_to_budget(proposal)

            await self._cancel_all_orders()
            await self._post_orders(candidate_orders)

        except Exception as exception:
            self._handle_error(exception)
        finally:
            waiting_time = self._calculate_waiting_time(self._configuration["strategy"]["tick_interval"])

            # noinspection PyAttributeOutsideInit
            self._refresh_timestamp = waiting_time + self.current_timestamp
            self._is_busy = False

            self._log(DEBUG, f"""Waiting for {waiting_time}s.""")

            self._log(DEBUG, """on_tick... end""")

            if self._configuration["strategy"]["run_only_once"]:
                HummingbotApplication.main_application().stop()

    def stop(self, clock: Clock):
        asyncio.ensure_future(self.async_stop(clock))

    async def async_stop(self, clock: Clock):
        try:
            self._log(DEBUG, """_stop... start""")

            self._can_run = False
            self._is_busy = True

            if self._configuration["strategy"]["cancel_all_orders_on_stop"]:
                await asyncio.sleep(5)
                await self._cancel_all_orders()

            super().stop(clock)
        finally:
            self._is_busy = False
            self._log(DEBUG, """_stop... end""")

    def format_status(self) -> str:
        return f"""\
                Token:
                {format_line(" Base: ", self._base_token)}
                {format_line(" Quote: ", self._quote_token)}
                Price:
                {format_line(" Middle:", format_currency(self._summary["price"]["ticker_price"], 6))}
                {format_line(" Top Ask:", format_currency(self._summary["order_book"]["top_ask"], 6))}
                {format_line(" Top Bid:", format_currency(self._summary["order_book"]["top_bid"], 6))}
                Balance:
                -Wallet:
                {format_line(f"  {self._base_token}:", format_currency(self._summary["balance"]["wallet"]["base"], 4))}
                {format_line(f"  {self._quote_token}:", format_currency(self._summary["balance"]["wallet"]["quote"], 4))}
                -Open Orders Balance:
                {format_line(f"  BUY:", format_currency(self._summary["balance"]["orders"]["base"], 4))}
                {format_line(f"  SELL:", format_currency(self._summary["balance"]["orders"]["quote"], 4))}
                """

    async def _create_proposal(self) -> List[OrderCandidate]:
        try:
            self._log(DEBUG, """_create_proposal... start""")

            order_book = await self._get_order_book()
            bids, asks, top_ask, top_bid = self._parse_order_book(order_book)

            self._summary["order_book"]["bids"] = bids
            self._summary["order_book"]["asks"] = asks
            self._summary["order_book"]["top_ask"] = top_ask
            self._summary["order_book"]["top_bid"] = top_bid

            ticker_price = await self._get_market_price()

            price_strategy = self._configuration["strategy"]["price_strategy"]
            if price_strategy == "ticker":
                used_price = ticker_price
            elif price_strategy == "middle":
                used_price = await self._get_market_mid_price(
                    bids,
                    asks,
                    self.MiddlePriceStrategy[
                        self._configuration["strategy"].get(
                            "middle_price_strategy",
                            "VWAP"
                        )
                    ]
                )
            else:
                raise ValueError("""Invalid "strategy.middle_price_strategy" configuration value.""")

            if used_price is None or used_price <= self._decimal_zero:
                raise ValueError(f"Invalid price: {used_price}")

            proposal = []

            bid_orders = []
            for index, layer in enumerate(self._configuration["strategy"]["layers"], start=1):
                best_ask = Decimal(next(iter(asks), {"price": self._float_infinity})["price"])
                bid_quantity = int(layer["bid"]["quantity"])
                bid_spread_percentage = Decimal(layer["bid"]["spread_percentage"])
                bid_market_price = ((100 - bid_spread_percentage) / 100) * min(used_price, best_ask)
                bid_max_liquidity_in_quote_token = Decimal(layer["bid"]["max_liquidity_in_quote_token"])
                bid_size = bid_max_liquidity_in_quote_token / bid_market_price / bid_quantity if bid_quantity > 0 else 0

                for i in range(bid_quantity):
                    bid_order = OrderCandidate(
                        trading_pair=self._hb_trading_pair.replace(" (NEW)", ""),
                        is_maker=True,
                        order_type=OrderType.LIMIT,
                        order_side=TradeType.BUY,
                        amount=bid_size,
                        price=bid_market_price
                    )
                    bid_orders.append(bid_order)

            ask_orders = []
            for index, layer in enumerate(self._configuration["strategy"]["layers"], start=1):
                best_bid = Decimal(next(iter(bids), {"price": self._float_zero})["price"])
                ask_quantity = int(layer["ask"]["quantity"])
                ask_spread_percentage = Decimal(layer["ask"]["spread_percentage"])
                ask_market_price = ((100 + ask_spread_percentage) / 100) * max(used_price, best_bid)
                ask_max_liquidity_in_quote_token = Decimal(layer["ask"]["max_liquidity_in_quote_token"])
                ask_size = ask_max_liquidity_in_quote_token / ask_market_price / ask_quantity if ask_quantity > 0 else 0

                for i in range(ask_quantity):
                    ask_order = OrderCandidate(
                        trading_pair=self._hb_trading_pair,
                        is_maker=True,
                        order_type=OrderType.LIMIT,
                        order_side=TradeType.SELL,
                        amount=ask_size,
                        price=ask_market_price
                    )
                    ask_orders.append(ask_order)

            proposal = [*proposal, *bid_orders, *ask_orders]

            self._log(DEBUG, f"""proposal:\n{self._dump(proposal)}""")

            return proposal
        finally:
            self._log(DEBUG, """_create_proposal... end""")

    async def _adjust_proposal_to_budget(self, candidate_proposal: List[OrderCandidate]) -> List[OrderCandidate]:
        try:
            self._log(DEBUG, """_adjust_proposal_to_budget... start""")

            adjusted_proposal: List[OrderCandidate] = []

            balances = await self._get_balances()
            base_balance = Decimal(balances["balances"][self._base_token])
            quote_balance = Decimal(balances["balances"][self._quote_token])
            current_base_balance = base_balance
            current_quote_balance = quote_balance

            for order in candidate_proposal:
                if order.order_side == TradeType.BUY:
                    if current_quote_balance > order.amount:
                        current_quote_balance -= order.amount
                        adjusted_proposal.append(order)
                    else:
                        continue
                elif order.order_side == TradeType.SELL:
                    if current_base_balance > order.amount:
                        current_base_balance -= order.amount
                        adjusted_proposal.append(order)
                    else:
                        continue
                else:
                    raise ValueError(f"""Unrecognized order size "{order.order_side}".""")

            self._log(DEBUG, f"""adjusted_proposal:\n{self._dump(adjusted_proposal)}""")

            return adjusted_proposal
        finally:
            self._log(DEBUG, """_adjust_proposal_to_budget... end""")

    async def _get_base_ticker_price(self) -> Decimal:
        try:
            self._log(DEBUG, """_get_ticker_price... start""")

            ticker_price = Decimal((await self._get_ticker(use_cache=False))["price"])
            self._summary["price"]["ticker_price"] = ticker_price

            return ticker_price
        finally:
            self._log(DEBUG, """_get_ticker_price... end""")

    async def _get_market_price(self) -> Decimal:
        return await self._get_base_ticker_price()

    async def _get_market_mid_price(self, bids, asks, strategy: MiddlePriceStrategy = None) -> Decimal:
        try:
            self._log(DEBUG, """_get_market_mid_price... start""")

            if strategy:
                return self._calculate_mid_price(bids, asks, strategy)

            try:
                return self._calculate_mid_price(bids, asks, self.MiddlePriceStrategy.VWAP)
            except (Exception,):
                try:
                    return self._calculate_mid_price(bids, asks, self.MiddlePriceStrategy.WAP)
                except (Exception,):
                    try:
                        return self._calculate_mid_price(bids, asks, self.MiddlePriceStrategy.SAP)
                    except (Exception,):
                        return await self._get_market_price()
        finally:
            self._log(DEBUG, """_get_market_mid_price... end""")

    async def _get_base_balance(self) -> Decimal:
        try:
            self._log(DEBUG, """_get_base_balance... start""")

            base_balance = Decimal((await self._get_balances())["balances"][self._base_token])
            self._summary["balance"]["orders"]["base"] = base_balance

            return base_balance
        finally:
            self._log(DEBUG, """_get_base_balance... end""")

    async def _get_quote_balance(self) -> Decimal:
        try:
            self._log(DEBUG, """_get_quote_balance... start""")

            quote_balance = Decimal((await self._get_balances())["balances"][self._quote_token])
            self._summary["balance"]["orders"]["quote"] = quote_balance

            return quote_balance
        finally:
            self._log(DEBUG, """_get_quote_balance... start""")

    async def _get_balances(self, use_cache: bool = True) -> Dict[str, Any]:
        try:
            self._log(DEBUG, """_get_balances... start""")

            response = None
            try:
                request = {
                    "network": self._configuration["network"],
                    "address": self._owner_address,
                    "token_symbols": []
                }

                if use_cache and self._balances is not None:
                    response = self._balances
                else:
                    response = await self._gateway.xrpl_get_balances(**request)

                    self._balances = {"balances": {}}
                    for (token, balance) in dict(response["balances"]).items():
                        decimal_balance = Decimal(balance)
                        if decimal_balance > self._decimal_zero:
                            self._balances["balances"][token] = Decimal(balance)

                    self._summary["balance"]["wallet"]["base"] = Decimal(response["balances"][self._base_token])
                    self._summary["balance"]["wallet"]["quote"] = Decimal(response["balances"][self._quote_token])

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

                response = await self._gateway.xrpldex_get_markets(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.xrpldex_get_markets:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")
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

                response = await self._gateway.xrpldex_get_order_books(**request)

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.xrpldex_get_order_books:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")
        finally:
            self._log(DEBUG, """_get_order_book... end""")

    async def _get_ticker(self, use_cache: bool = True) -> Dict[str, Any]:
        try:
            self._log(DEBUG, """_get_tickers... start""")

            request = None
            response = None
            try:
                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "market_name": self._market
                }

                if use_cache and self._tickers is not None:
                    response = self._tickers
                else:
                    response = await self._gateway.xrpldex_get_tickers(**request)

                    self._tickers = response

                return response
            except Exception as exception:
                response = exception

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.xrpldex_get_tickers:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")

        finally:
            self._log(DEBUG, """_get_tickers... end""")

    async def _get_open_orders(self, use_cache: bool = True) -> Dict[str, Any]:
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

                if use_cache and self._open_orders is not None:
                    response = self._open_orders
                else:
                    response = await self._gateway.xrpldex_get_open_orders(**request)
                    self._open_orders = response

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.xrpldex_get_open_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")
        finally:
            self._log(DEBUG, """_get_open_orders... end""")

    async def _post_orders(self, proposal: List[OrderCandidate]) -> Dict[str, Any]:
        try:
            self._log(DEBUG, """_replace_orders... start""")

            response = None
            try:
                orders = []
                for candidate in proposal:
                    orders.append({
                        "marketName": self._market,
                        "walletAddress": self._connector.address,
                        "side": convert_order_side(candidate.order_side).value[0],
                        "price": float(
                            self._round_to_significant_digits(candidate.price, int(self._market_info["tickSize"]))),
                        "amount": float(
                            self._round_to_significant_digits(candidate.amount,
                                                              int(self._market_info["minimumOrderSize"]))),
                        "type":
                            XRPLOrderType[self._configuration["strategy"].get("xrpldex_order_type", "LIMIT")].value[
                                0],
                    })

                request = {
                    "chain": self._configuration["chain"],
                    "network": self._configuration["network"],
                    "connector": self._configuration["connector"],
                    "wait_until_included_in_block": True,
                    "orders": orders
                }

                if len(orders):
                    response = await self._gateway.xrpldex_post_orders(**request)
                else:
                    self._log(WARNING, "No order was defined for placement/replacement. Skipping.", True)
                    response = []

                return response
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""gateway.clob_post_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")
        finally:
            self._log(DEBUG, """_replace_orders... end""")

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
                          f"""gateway.xrpldex_delete_orders:\nrequest:\n{self._dump(request)}\nresponse:\n{self._dump(response)}""")  # noqa
        finally:
            self._log(DEBUG, """_cancel_orders... end""")
        pass

    async def _cancel_all_orders(self):
        try:
            self._log(DEBUG, """_cancel_all_orders... start""")

            response = None
            try:
                open_orders_on_all_markets = await self._get_open_orders(use_cache=False)
                open_orders = open_orders_on_all_markets[self._market]

                cancel_orders = []
                for key in open_orders:
                    cancel_orders.append({
                        "walletAddress": self._connector.address,
                        "offerSequence": int(key),
                    })

                response = await self._cancel_orders(orders=cancel_orders)
            except Exception as exception:
                response = traceback.format_exc()

                raise exception
            finally:
                self._log(INFO,
                          f"""self._cancel_all_orders:\ncancel_orders:\n{self._dump(cancel_orders)}\nresponse:\n{self._dump(response)}""")  # noqa
        finally:
            self._log(DEBUG, """_cancel_all_orders... end""")

    # noinspection PyMethodMayBeStatic
    def _parse_order_book(self, orderbook: Dict[str, Any]) -> List[Union[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        bids_list = []
        asks_list = []

        bids: Dict[str, Any] = orderbook["bids"]
        asks: Dict[str, Any] = orderbook["asks"]
        top_ask = Decimal(orderbook["topAsk"])
        top_bid = Decimal(orderbook["topBid"])

        for bid in bids:
            if isinstance(bid["TakerGets"], str):
                bids_list.append(
                    {'price': pow(Decimal(bid["quality"]), -1) * 1000000, 'amount': Decimal(bid["TakerGets"])})
            else:
                bids_list.append(
                    {'price': pow(Decimal(bid["quality"]), -1), 'amount': Decimal(bid["TakerGets"]["value"])})

        for ask in asks:
            if isinstance(ask["TakerGets"], str):
                asks_list.append({'price': Decimal(ask["quality"]) * 1000000, 'amount': Decimal(ask["TakerGets"])})
            else:
                asks_list.append({'price': Decimal(ask["quality"]), 'amount': Decimal(ask["TakerGets"]["value"])})

        bids_list.sort(key=lambda x: x['price'], reverse=True)
        asks_list.sort(key=lambda x: x['price'], reverse=False)

        return [bids_list, asks_list, top_ask, top_bid]

    def _split_percentage(self, bids: [Dict[str, Any]], asks: [Dict[str, Any]]) -> List[Any]:
        asks = asks[:math.ceil((self._vwap_threshold / 100) * len(asks))]
        bids = bids[:math.ceil((self._vwap_threshold / 100) * len(bids))]

        return [bids, asks]

    # noinspection PyMethodMayBeStatic
    def _compute_volume_weighted_average_price(self, book: [Dict[str, Any]]) -> np.array:
        prices = [order['price'] for order in book]
        amounts = [order['amount'] for order in book]

        prices = np.array(prices)
        amounts = np.array(amounts)

        vwap = (np.cumsum(amounts * prices) / np.cumsum(amounts))

        return vwap

    # noinspection PyMethodMayBeStatic
    def _remove_outliers(self, order_book: [Dict[str, Any]], side: XRPLOrderSide) -> [Dict[str, Any]]:
        prices = [float(order['price']) for order in order_book]

        q75, q25 = np.percentile(prices, [75, 25])

        # https://www.askpython.com/python/examples/detection-removal-outliers-in-python
        # intr_qr = q75-q25
        # max_threshold = q75+(1.5*intr_qr)
        # min_threshold = q75-(1.5*intr_qr) # Error: Sometimes this function assigns negative value for min

        max_threshold = q75 * 1.5
        min_threshold = q25 * 0.5

        orders = []
        if side == XRPLOrderSide.SELL:
            orders = [order for order in order_book if float(order['price']) < max_threshold]
        elif side == XRPLOrderSide.BUY:
            orders = [order for order in order_book if float(order['price']) > min_threshold]

        return orders

    def _calculate_mid_price(self, bids: [Dict[str, Any]], asks: [Dict[str, Any]],
                             strategy: MiddlePriceStrategy) -> Decimal:
        if strategy == self.MiddlePriceStrategy.SAP:
            bid_prices = [item['price'] for item in bids]
            ask_prices = [item['price'] for item in asks]

            best_ask_price = 0
            best_bid_price = 0

            if len(ask_prices) > 0:
                best_ask_price = min(ask_prices)

            if len(bid_prices) > 0:
                best_bid_price = max(bid_prices)

            return Decimal((best_ask_price + best_bid_price) / 2.0)
        elif strategy == self.MiddlePriceStrategy.WAP:
            ask_prices = [item['price'] for item in asks]
            bid_prices = [item['price'] for item in bids]

            best_ask_price = 0
            best_ask_volume = 0
            best_bid_price = 0
            best_bid_amount = 0

            if len(ask_prices) > 0:
                best_ask_idx = ask_prices.index(min(ask_prices))
                best_ask_price = asks[best_ask_idx]['price']
                best_ask_volume = asks[best_ask_idx]['amount']

            if len(bid_prices) > 0:
                best_bid_idx = bid_prices.index(max(bid_prices))
                best_bid_price = bids[best_bid_idx]['price']
                best_bid_amount = bids[best_bid_idx]['amount']

            if best_ask_volume + best_bid_amount > 0:
                return Decimal(
                    (best_ask_price * best_ask_volume + best_bid_price * best_bid_amount)
                    / (best_ask_volume + best_bid_amount)
                )
            else:
                return self._decimal_zero
        elif strategy == self.MiddlePriceStrategy.VWAP:
            bids, asks = self._split_percentage(bids, asks)

            if len(bids) > 0:
                bids = self._remove_outliers(bids, XRPLOrderSide.BUY)

            if len(asks) > 0:
                asks = self._remove_outliers(asks, XRPLOrderSide.SELL)

            book = [*bids, *asks]

            if len(book) > 0:
                vwap = self._compute_volume_weighted_average_price(book)

                return Decimal(vwap[-1])
            else:
                return self._decimal_zero
        else:
            raise ValueError(f'Unrecognized mid price strategy "{strategy}".')

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

    # noinspection PyMethodMayBeStatic
    def _calculate_waiting_time(self, number: int) -> int:
        current_timestamp_in_milliseconds = int(time.time() * 1000)
        result = number - (current_timestamp_in_milliseconds % number)

        return result

    def _log(self, level: int, message: str, *args, **kwargs):
        # noinspection PyUnresolvedReferences
        message = f"""{message}"""

        self.logger().log(level, message, *args, **kwargs)

    def _handle_error(self, exception: Exception):
        try:
            message = f"""ERROR: {type(exception).__name__} {str(exception)}"""

            self._log(ERROR, message, True)
        finally:
            raise exception

    @staticmethod
    def _round_to_significant_digits(number: Decimal, significant_digits: int):
        return round(number, significant_digits - int(math.floor(math.log10(abs(number)))) - 1)

    @staticmethod
    def _dump(target: Any):
        try:
            return jsonpickle.encode(target, unpicklable=True, indent=2)
        except (Exception,):
            return target
