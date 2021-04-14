import logging
from decimal import Decimal
import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
import json
import time
import ssl
import copy
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.core.event.events import TradeFee
from hummingbot.core.utils import async_ttl_cache
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.utils.estimate_fee import estimate_fee
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.cancellation_result import CancellationResult
from hummingbot.core.event.events import (
    MarketEvent,
    BuyOrderCreatedEvent,
    SellOrderCreatedEvent,
    BuyOrderCompletedEvent,
    SellOrderCompletedEvent,
    MarketOrderFailureEvent,
    FundingPaymentCompletedEvent,
    OrderFilledEvent,
    OrderType,
    TradeType,
    PositionSide,
    PositionAction
)
from hummingbot.connector.derivative_base import DerivativeBase
from hummingbot.connector.derivative.perpetual_finance.perpetual_finance_in_flight_order import PerpetualFinanceInFlightOrder
from hummingbot.connector.derivative.perpetual_finance.perpetual_finance_utils import convert_to_exchange_trading_pair
from hummingbot.client.settings import GATEAWAY_CA_CERT_PATH, GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH
from hummingbot.client.config.global_config_map import global_config_map
from hummingbot.connector.derivative.position import Position


s_logger = None
s_decimal_0 = Decimal("0")
s_decimal_NaN = Decimal("nan")
logging.basicConfig(level=METRICS_LOG_LEVEL)


class PerpetualFinanceDerivative(DerivativeBase):
    """
    PerpetualFinanceConnector connects with perpetual_finance gateway APIs and provides pricing, user account tracking and trading
    functionality.
    """
    API_CALL_TIMEOUT = 10.0
    POLL_INTERVAL = 1.0
    UPDATE_BALANCE_INTERVAL = 5.0

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global s_logger
        if s_logger is None:
            s_logger = logging.getLogger(__name__)
        return s_logger

    def __init__(self,
                 trading_pairs: List[str],
                 wallet_private_key: str,
                 ethereum_rpc_url: str,  # not used, but left in place to be consistent with other gateway connectors
                 trading_required: bool = True
                 ):
        """
        :param trading_pairs: a list of trading pairs
        :param wallet_private_key: a private key for eth wallet
        :param trading_required: Whether actual trading is needed.
        """
        super().__init__()
        self._trading_pairs = trading_pairs
        self._wallet_private_key = wallet_private_key
        self._trading_required = trading_required
        self._ev_loop = asyncio.get_event_loop()
        self._shared_client = None
        self._last_poll_timestamp = 0.0
        self._last_balance_poll_timestamp = time.time()
        self._in_flight_orders = {}
        self._allowances = {}
        self._status_polling_task = None
        self._auto_approve_task = None
        self._real_time_balance_update = False
        self._poll_notifier = None
        self._funding_payment_span = [120, 120]
        self._fundingPayment = {}

    @property
    def name(self):
        return "perpetual_finance"

    @property
    def limit_orders(self) -> List[LimitOrder]:
        return [
            in_flight_order.to_limit_order()
            for in_flight_order in self._in_flight_orders.values()
        ]

    async def load_metadata(self):
        status = await self._api_request("get", "perpfi/")
        loadedMetadata = status["loadedMetadata"]
        while (not loadedMetadata):
            resp = await self._api_request("get", "perpfi/load-metadata")
            loadedMetadata = resp.get("loadedMetadata", False)
        return

    async def auto_approve(self):
        """
        Automatically approves PerpetualFinance contract as a spender for token in trading pairs.
        It first checks if there are any already approved amount (allowance)
        """
        self.logger().info("Checking for allowances...")
        self._allowances = await self.get_allowances()
        for token, amount in self._allowances.items():
            if amount <= s_decimal_0:
                amount_approved = await self.approve_perpetual_finance_spender()
                if amount_approved > 0:
                    self._allowances[token] = amount_approved
                    await asyncio.sleep(2)
                else:
                    break

    async def approve_perpetual_finance_spender(self) -> Decimal:
        """
        Approves PerpetualFinance contract as a spender for default USDC token.
        """
        resp = await self._api_request("post", "perpfi/approve")
        amount_approved = Decimal(str(resp["amount"]))
        if amount_approved > 0:
            self.logger().info("Approved PerpetualFinance spender contract.")
        else:
            self.logger().info("PerpetualFinance spender contract approval failed.")
        return amount_approved

    async def get_allowances(self) -> Dict[str, Decimal]:
        """
        Retrieves allowances for token in trading_pairs
        :return: A dictionary of token and its allowance (how much PerpetualFinance can spend).
        """
        ret_val = {}
        resp = await self._api_request("post", "perpfi/allowances")
        for asset, amount in resp["approvals"].items():
            ret_val[asset] = Decimal(str(amount))
        return ret_val

    @async_ttl_cache(ttl=5, maxsize=10)
    async def get_quote_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Optional[Decimal]:
        """
        Retrieves a quote price.
        :param trading_pair: The market trading pair
        :param is_buy: True for an intention to buy, False for an intention to sell
        :param amount: The amount required (in base token unit)
        :return: The quote price.
        """

        try:
            side = "buy" if is_buy else "sell"
            resp = await self._api_request("post",
                                           "perpfi/price",
                                           {"side": side,
                                            "pair": convert_to_exchange_trading_pair(trading_pair),
                                            "amount": amount})
            if resp["price"] is not None:
                return Decimal(str(resp["price"]))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger().network(
                f"Error getting quote price for {trading_pair}  {side} order for {amount} amount.",
                exc_info=True,
                app_warning_msg=str(e)
            )

    async def get_order_price(self, trading_pair: str, is_buy: bool, amount: Decimal) -> Decimal:
        """
        This is simply the quote price
        """
        return await self.get_quote_price(trading_pair, is_buy, amount)

    def buy(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Buys an amount of base token for a given price (or cheaper).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The maximum price for the order.
        :param position_action: Either OPEN or CLOSE position action.
        :return: A newly created order id (internal).
        """
        return self.place_order(True, trading_pair, amount, price, kwargs["position_action"])

    def sell(self, trading_pair: str, amount: Decimal, order_type: OrderType, price: Decimal, **kwargs) -> str:
        """
        Sells an amount of base token for a given price (or at a higher price).
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param order_type: Any order type is fine, not needed for this.
        :param price: The minimum price for the order.
        :param position_action: Either OPEN or CLOSE position action.
        :return: A newly created order id (internal).
        """
        return self.place_order(False, trading_pair, amount, price, kwargs["position_action"])

    def place_order(self, is_buy: bool, trading_pair: str, amount: Decimal, price: Decimal, position_action: PositionAction) -> str:
        """
        Places an order.
        :param is_buy: True for buy order
        :param trading_pair: The market trading pair
        :param amount: The order amount (in base token unit)
        :param price: The minimum price for the order.
        :param position_action: Either OPEN or CLOSE position action.
        :return: A newly created order id (internal).
        """
        side = TradeType.BUY if is_buy else TradeType.SELL
        order_id = f"{side.name.lower()}-{trading_pair}-{get_tracking_nonce()}"
        safe_ensure_future(self._create_order(side, order_id, trading_pair, amount, price, position_action))
        return order_id

    async def _create_order(self,
                            trade_type: TradeType,
                            order_id: str,
                            trading_pair: str,
                            amount: Decimal,
                            price: Decimal,
                            position_action: PositionAction):
        """
        Calls buy or sell API end point to place an order, starts tracking the order and triggers relevant order events.
        :param trade_type: BUY or SELL
        :param order_id: Internal order id (also called client_order_id)
        :param trading_pair: The market to place order
        :param amount: The order amount (in base token value)
        :param price: The order price
        :param position_action: Either OPEN or CLOSE position action.
        """

        amount = self.quantize_order_amount(trading_pair, amount)
        price = self.quantize_order_price(trading_pair, price)
        base, quote = trading_pair.split("-")
        api_params = {"pair": convert_to_exchange_trading_pair(trading_pair)}
        if position_action == PositionAction.OPEN:
            api_params.update({"side": 0 if trade_type == TradeType.BUY else 1,
                               "margin": self.quantize_order_amount(trading_pair, (amount / self._leverage[trading_pair] * price)),
                               "leverage": self._leverage[trading_pair],
                               "minBaseAssetAmount": Decimal("0")})
        else:
            # api_params.update({"minimalQuoteAsset": price * amount})
            api_params.update({"minimalQuoteAsset": Decimal("0")})
        self.start_tracking_order(order_id, None, trading_pair, trade_type, price, amount, self._leverage[trading_pair], position_action.name)
        try:
            order_result = await self._api_request("post", f"perpfi/{position_action.name.lower()}", api_params)
            hash = order_result.get("txHash")
            tracked_order = self._in_flight_orders.get(order_id)
            if tracked_order is not None:
                self.logger().info(f"Created {trade_type.name} order {order_id} txHash: {hash} "
                                   f"for {amount} {trading_pair}.")
                tracked_order.update_exchange_order_id(hash)
            if hash is not None:
                tracked_order.fee_asset = "XDAI"
                tracked_order.executed_amount_base = amount
                tracked_order.executed_amount_quote = amount * price
                event_tag = MarketEvent.BuyOrderCreated if trade_type is TradeType.BUY else MarketEvent.SellOrderCreated
                event_class = BuyOrderCreatedEvent if trade_type is TradeType.BUY else SellOrderCreatedEvent
                self.trigger_event(event_tag, event_class(self.current_timestamp, OrderType.LIMIT, trading_pair, amount,
                                                          price, order_id, hash, leverage=self._leverage[trading_pair],
                                                          position=position_action.name))
            else:
                self.trigger_event(MarketEvent.OrderFailure,
                                   MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.stop_tracking_order(order_id)
            self.logger().network(
                f"Error submitting {trade_type.name} order to PerpetualFinance for "
                f"{amount} {trading_pair} "
                f"{price}.",
                exc_info=True,
                app_warning_msg=str(e)
            )
            self.trigger_event(MarketEvent.OrderFailure,
                               MarketOrderFailureEvent(self.current_timestamp, order_id, OrderType.LIMIT))

    def start_tracking_order(self,
                             order_id: str,
                             exchange_order_id: str,
                             trading_pair: str,
                             trade_type: TradeType,
                             price: Decimal,
                             amount: Decimal,
                             leverage: int,
                             position: str,):
        """
        Starts tracking an order by simply adding it into _in_flight_orders dictionary.
        """
        self._in_flight_orders[order_id] = PerpetualFinanceInFlightOrder(
            client_order_id=order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=trade_type,
            price=price,
            amount=amount,
            leverage=leverage,
            position=position
        )

    def stop_tracking_order(self, order_id: str):
        """
        Stops tracking an order by simply removing it from _in_flight_orders dictionary.
        """
        if order_id in self._in_flight_orders:
            del self._in_flight_orders[order_id]

    async def _update_order_status(self):
        """
        Calls REST API to get status update for each in-flight order.
        """
        if len(self._in_flight_orders) > 0:
            tracked_orders = list(self._in_flight_orders.values())

            tasks = []
            for tracked_order in tracked_orders:
                order_id = await tracked_order.get_exchange_order_id()
                tasks.append(self._api_request("post",
                                               "perpfi/receipt",
                                               {"txHash": order_id}))
            update_results = await safe_gather(*tasks, return_exceptions=True)
            for update_result in update_results:
                self.logger().info(f"Polling for order status updates of {len(tasks)} orders.")
                if isinstance(update_result, Exception):
                    raise update_result
                if "txHash" not in update_result:
                    self.logger().info(f"_update_order_status txHash not in resp: {update_result}")
                    continue
                if update_result["confirmed"] is True:
                    if update_result["receipt"]["status"] == 1:
                        fee = estimate_fee("perpetual_finance", False)
                        fee = TradeFee(fee.percent, [("XDAI", Decimal(str(update_result["receipt"]["gasUsed"])))])
                        self.trigger_event(
                            MarketEvent.OrderFilled,
                            OrderFilledEvent(
                                self.current_timestamp,
                                tracked_order.client_order_id,
                                tracked_order.trading_pair,
                                tracked_order.trade_type,
                                tracked_order.order_type,
                                Decimal(str(tracked_order.price)),
                                Decimal(str(tracked_order.amount)),
                                fee,
                                exchange_trade_id=order_id,
                                leverage=self._leverage[tracked_order.trading_pair],
                                position=tracked_order.position
                            )
                        )
                        tracked_order.last_state = "FILLED"
                        self.logger().info(f"The {tracked_order.trade_type.name} order "
                                           f"{tracked_order.client_order_id} has completed "
                                           f"according to order status API.")
                        event_tag = MarketEvent.BuyOrderCompleted if tracked_order.trade_type is TradeType.BUY \
                            else MarketEvent.SellOrderCompleted
                        event_class = BuyOrderCompletedEvent if tracked_order.trade_type is TradeType.BUY \
                            else SellOrderCompletedEvent
                        self.trigger_event(event_tag,
                                           event_class(self.current_timestamp,
                                                       tracked_order.client_order_id,
                                                       tracked_order.base_asset,
                                                       tracked_order.quote_asset,
                                                       tracked_order.fee_asset,
                                                       tracked_order.executed_amount_base,
                                                       tracked_order.executed_amount_quote,
                                                       float(fee.fee_amount_in_quote(tracked_order.trading_pair,
                                                                                     Decimal(str(tracked_order.price)),
                                                                                     Decimal(str(tracked_order.amount)))),  # this ignores the gas fee, which is fine for now
                                                       tracked_order.order_type))
                        self.stop_tracking_order(tracked_order.client_order_id)
                    else:
                        self.logger().info(
                            f"The market order {tracked_order.client_order_id} has failed according to order status API. ")
                        self.trigger_event(MarketEvent.OrderFailure,
                                           MarketOrderFailureEvent(
                                               self.current_timestamp,
                                               tracked_order.client_order_id,
                                               tracked_order.order_type
                                           ))
                        self.stop_tracking_order(tracked_order.client_order_id)

    def get_taker_order_type(self):
        return OrderType.LIMIT

    def get_order_price_quantum(self, trading_pair: str, price: Decimal) -> Decimal:
        return Decimal("1e-6")

    def get_order_size_quantum(self, trading_pair: str, order_size: Decimal) -> Decimal:
        return Decimal("1e-6")

    @property
    def ready(self):
        return all(self.status_dict.values())

    def has_allowances(self) -> bool:
        """
        Checks if all tokens have allowance (an amount approved)
        """
        return all(amount > s_decimal_0 for amount in self._allowances.values())

    @property
    def status_dict(self) -> Dict[str, bool]:
        return {
            "account_balance": len(self._account_balances) > 0 if self._trading_required else True,
            "allowances": self.has_allowances() if self._trading_required else True,
            "funding_info": len(self._funding_info) > 0
        }

    async def start_network(self):
        if self._trading_required:
            self._status_polling_task = safe_ensure_future(self._status_polling_loop())
            self._auto_approve_task = safe_ensure_future(self.auto_approve())
            self._funding_info_polling_task = safe_ensure_future(self._funding_info_polling_loop())

    async def stop_network(self):
        if self._status_polling_task is not None:
            self._status_polling_task.cancel()
            self._status_polling_task = None
        if self._auto_approve_task is not None:
            self._auto_approve_task.cancel()
            self._auto_approve_task = None
        if self._funding_info_polling_task is not None:
            self._funding_info_polling_task.cancel()
            self._funding_info_polling_task = None

    async def check_network(self) -> NetworkStatus:
        try:
            response = await self._api_request("get", "api")
            if response["status"] != "ok":
                raise Exception(f"Error connecting to Gateway API. HTTP status is {response.status}.")
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    def tick(self, timestamp: float):
        """
        Is called automatically by the clock for each clock's tick (1 second by default).
        It checks if status polling task is due for execution.
        """
        if time.time() - self._last_poll_timestamp > self.POLL_INTERVAL:
            if self._poll_notifier is not None and not self._poll_notifier.is_set():
                self._poll_notifier.set()

    async def _status_polling_loop(self):
        while True:
            try:
                self._poll_notifier = asyncio.Event()
                await self._poll_notifier.wait()
                await safe_gather(
                    self._update_positions(),
                    self._update_balances(),
                    self._update_order_status(),
                )
                self._last_poll_timestamp = self.current_timestamp
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger().error(str(e), exc_info=True)
                self.logger().network("Unexpected error while fetching account updates.",
                                      exc_info=True,
                                      app_warning_msg="Could not fetch balances from Gateway API.")
                await asyncio.sleep(0.5)

    async def _update_balances(self):
        """
        Calls Eth API to update total and available balances.
        """
        last_tick = self._last_balance_poll_timestamp
        current_tick = self.current_timestamp
        if (current_tick - last_tick) > self.UPDATE_BALANCE_INTERVAL:
            self._last_balance_poll_timestamp = current_tick
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        balances_resp = await self._api_request("post", "perpfi/balances")
        margin_resp = await self._api_request("post", "perpfi/margin")
        for token, bal in balances_resp["balances"].items():
            self._account_available_balances[token] = Decimal(str(bal))
            self._account_balances[token] = Decimal(str(bal)) + Decimal(str(margin_resp["margin"])) if token == "USDC" \
                else Decimal(str(bal))
            remote_asset_names.add(token)

        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset_name in asset_names_to_remove:
            del self._account_available_balances[asset_name]
            del self._account_balances[asset_name]

        self._in_flight_orders_snapshot = {k: copy.copy(v) for k, v in self._in_flight_orders.items()}
        self._in_flight_orders_snapshot_timestamp = self.current_timestamp

    async def _update_positions(self):
        position_tasks = []
        for pair in self._trading_pairs:
            position_tasks.append(self._api_request("post",
                                                    "perpfi/position",
                                                    {"pair": convert_to_exchange_trading_pair(pair)}))
        positions = await safe_gather(*position_tasks, return_exceptions=True)
        for trading_pair, position in zip(self._trading_pairs, positions):
            position = position.get("position", {})
            amount = self.quantize_order_amount(trading_pair, Decimal(position.get("size")))
            if amount != Decimal("0"):
                position_side = PositionSide.LONG if amount > 0 else PositionSide.SHORT
                unrealized_pnl = self.quantize_order_amount(trading_pair, Decimal(position.get("pnl")))
                entry_price = self.quantize_order_price(trading_pair, Decimal(position.get("entryPrice")))
                leverage = self._leverage[trading_pair]
                self._account_positions[trading_pair] = Position(
                    trading_pair=trading_pair,
                    position_side=position_side,
                    unrealized_pnl=unrealized_pnl,
                    entry_price=entry_price,
                    amount=amount,
                    leverage=leverage
                )
            else:
                if trading_pair in self._account_positions:
                    del self._account_positions[trading_pair]

                payment = Decimal(str(position.get("fundingPayment")))
                oldPayment = self._fundingPayment.get(trading_pair, 0)
                if payment != oldPayment:
                    self._fundingPayment[trading_pair] = oldPayment
                    action = "paid" if payment < 0 else "received"
                    if payment != Decimal("0"):
                        self.logger().info(f"Funding payment of {payment} {action} on {trading_pair} market.")
                        self.trigger_event(MarketEvent.FundingPaymentCompleted,
                                           FundingPaymentCompletedEvent(timestamp=time.time(),
                                                                        market=self.name,
                                                                        funding_rate=self._funding_info[trading_pair]["rate"],
                                                                        trading_pair=trading_pair,
                                                                        amount=payment))

    async def _funding_info_polling_loop(self):
        while True:
            try:
                funding_info_tasks = []
                for pair in self._trading_pairs:
                    funding_info_tasks.append(self._api_request("post",
                                                                "perpfi/funding",
                                                                {"pair": convert_to_exchange_trading_pair(pair)}))
                funding_infos = await safe_gather(*funding_info_tasks, return_exceptions=True)
                for trading_pair, funding_info in zip(self._trading_pairs, funding_infos):
                    self._funding_info[trading_pair] = funding_info["fr"]
            except Exception:
                self.logger().network("Unexpected error while fetching funding info.", exc_info=True,
                                      app_warning_msg="Could not fetch new funding info from Perpetual Finance protocol. "
                                                      "Check network connection on gateway.")
            await asyncio.sleep(30)

    def get_funding_info(self, trading_pair):
        return self._funding_info[trading_pair]

    def set_leverage(self, trading_pair: str, leverage: int = 1):
        self._leverage[trading_pair] = leverage

    async def _http_client(self) -> aiohttp.ClientSession:
        """
        :returns Shared client session instance
        """
        if self._shared_client is None:
            ssl_ctx = ssl.create_default_context(cafile=GATEAWAY_CA_CERT_PATH)
            ssl_ctx.load_cert_chain(GATEAWAY_CLIENT_CERT_PATH, GATEAWAY_CLIENT_KEY_PATH)
            conn = aiohttp.TCPConnector(ssl_context=ssl_ctx)
            self._shared_client = aiohttp.ClientSession(connector=conn)
        return self._shared_client

    async def _api_request(self,
                           method: str,
                           path_url: str,
                           params: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Sends an aiohttp request and waits for a response.
        :param method: The HTTP method, e.g. get or post
        :param path_url: The path url or the API end point
        :param params: A dictionary of required params for the end point
        :returns A response in json format.
        """
        base_url = f"https://{global_config_map['gateway_api_host'].value}:" \
                   f"{global_config_map['gateway_api_port'].value}"
        url = f"{base_url}/{path_url}"
        client = await self._http_client()
        if method == "get":
            if len(params) > 0:
                response = await client.get(url, params=params)
            else:
                response = await client.get(url)
        elif method == "post":
            params["privateKey"] = self._wallet_private_key
            if params["privateKey"][:2] != "0x":
                params["privateKey"] = "0x" + params["privateKey"]
            response = await client.post(url, data=params)

        parsed_response = json.loads(await response.text())
        if response.status != 200:
            err_msg = ""
            if "error" in parsed_response:
                err_msg = f" Message: {parsed_response['error']}"
            raise IOError(f"Error fetching data from {url}. HTTP status is {response.status}.{err_msg}")
        if "error" in parsed_response:
            raise Exception(f"Error: {parsed_response['error']}")

        return parsed_response

    async def cancel_all(self, timeout_seconds: float) -> List[CancellationResult]:
        return []

    @property
    def in_flight_orders(self) -> Dict[str, PerpetualFinanceInFlightOrder]:
        return self._in_flight_orders
