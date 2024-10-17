import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import eth_account
from bidict import bidict
from web3 import Web3
from web3.middleware import geth_poa_middleware

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.tegro import tegro_constants as CONSTANTS, tegro_utils, tegro_web_utils as web_utils
from hummingbot.connector.exchange.tegro.tegro_api_order_book_data_source import TegroAPIOrderBookDataSource
from hummingbot.connector.exchange.tegro.tegro_api_user_stream_data_source import TegroUserStreamDataSource
from hummingbot.connector.exchange.tegro.tegro_auth import TegroAuth
from hummingbot.connector.exchange.tegro.tegro_messages import encode_typed_data
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter

s_logger = None
s_decimal_0 = Decimal(0)
s_float_NaN = float("nan")
MAX_UINT256 = 2**256 - 1


class TegroExchange(ExchangePyBase):
    UPDATE_ORDER_STATUS_MIN_INTERVAL = 10.0

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 tegro_api_key: str,
                 tegro_api_secret: str,
                 chain_name: str = CONSTANTS.DEFAULT_CHAIN,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEFAULT_DOMAIN
                 ):
        self.api_key = tegro_api_key
        self._chain = chain_name
        self.secret_key = tegro_api_secret
        self._api_factory = WebAssistantsFactory
        self._domain = domain
        self._trading_required = trading_required
        self._trading_pairs = trading_pairs
        self._last_trades_poll_tegro_timestamp = 1.0
        super().__init__(client_config_map)
        self._allowance_polling_task: Optional[asyncio.Task] = None
        self.real_time_balance_update = False

    @property
    def authenticator(self):
        return TegroAuth(
            api_key=self.api_key,
            api_secret=self.secret_key
        )

    @property
    def name(self) -> str:
        return self._domain

    @property
    def rate_limits_rules(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def domain(self):
        return self._domain

    @property
    def node_rpc(self):
        return f"tegro_{self._chain}_testnet" if self._domain.endswith("_testnet") else self._chain

    @property
    def chain_id(self):
        return self._chain

    @property
    def client_order_id_max_length(self):
        return CONSTANTS.MAX_ORDER_ID_LEN

    @property
    def chain(self):
        chain = 8453
        if self._domain.endswith("_testnet"):
            chain = CONSTANTS.TESTNET_CHAIN_IDS[self.chain_id]
        elif self._domain == "tegro":
            chain_id = CONSTANTS.DEFAULT_CHAIN
            # In this case tegro is default to base mainnet
            chain = CONSTANTS.MAINNET_CHAIN_IDS[chain_id]
        return chain

    @property
    def client_order_id_prefix(self):
        return CONSTANTS.HBOT_ORDER_ID_PREFIX

    @property
    def trading_rules_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL

    @property
    def trading_pairs_request_path(self):
        return CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL

    @property
    def check_network_request_path(self):
        return CONSTANTS.PING_PATH_URL

    @property
    def trading_pairs(self):
        return self._trading_pairs

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        return True

    @property
    def is_trading_required(self) -> bool:
        return self._trading_required

    def supported_order_types(self):
        return [OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET]

    async def _get_all_pairs_prices(self) -> Dict[str, Any]:
        results = {}
        pairs_prices = await self._api_get(
            path_url=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL.format(self.chain),
            params={"page": 1, "sort_order": "desc", "sort_by": "volume", "page_size": 20, "verified": "true"},
            limit_id=CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL
        )
        for pair_price_data in pairs_prices:
            results[pair_price_data["symbol"]] = {
                "best_bid": pair_price_data["ticker"]["price"],
                "best_ask": pair_price_data["ticker"]["price"],
            }
        return results

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        error_description = str(request_exception)
        is_time_synchronizer_related = ("-1021" in error_description
                                        and "Timestamp for this request" in error_description)
        return is_time_synchronizer_related

    def _is_request_result_an_error_related_to_time_synchronizer(self, request_result: Dict[str, Any]) -> bool:
        # The exchange returns a response failure and not a valid response
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        return str(CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE) in str(
            status_update_exception
        ) and CONSTANTS.ORDER_NOT_EXIST_MESSAGE in str(status_update_exception)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        return str(CONSTANTS.UNKNOWN_ORDER_ERROR_CODE) in str(
            cancelation_exception
        ) and CONSTANTS.UNKNOWN_ORDER_MESSAGE in str(cancelation_exception)

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self._domain,
            auth=self._auth)

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return TegroAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain)

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return TegroUserStreamDataSource(
            auth=self._auth,
            domain=self.domain,
            throttler=self._throttler,
            api_factory=self._web_assistants_factory,
        )

    def _get_fee(
        self,
        base_currency: str,
        quote_currency: str,
        order_type: OrderType,
        order_side: TradeType,
        amount: Decimal,
        price: Decimal = s_decimal_NaN,
        is_maker: Optional[bool] = None,
    ) -> TradeFeeBase:
        is_maker = True if is_maker is None else is_maker
        return DeductedFromReturnsTradeFee(percent=self.estimate_fee_pct(is_maker))

    async def start_network(self):
        await super().start_network()
        self._allowance_polling_task = safe_ensure_future(self.approve_allowance())

    async def stop_network(self):
        await super().stop_network()
        if self._allowance_polling_task is not None:
            self._allowance_polling_task.cancel()
            self._allowance_polling_task = None

    async def get_chain_list(self):
        account_info = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.CHAIN_LIST,
            limit_id=CONSTANTS.CHAIN_LIST,
            is_auth_required=False)

        return account_info

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        transaction_data = await self._generate_typed_data(amount, order_type, price, trade_type, trading_pair)
        s = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        symbol: str = s.replace('-', '_')
        signature = self.sign_inner(transaction_data)
        api_params = {
            "chain_id": self.chain,
            "base_asset": transaction_data["limit_order"]["base_asset"],
            "quote_asset": transaction_data["limit_order"]["quote_asset"],
            "side": transaction_data["limit_order"]["side"],
            "volume_precision": transaction_data["limit_order"]["volume_precision"],
            "price_precision": transaction_data["limit_order"]["price_precision"],
            "order_hash": transaction_data["limit_order"]["order_hash"],
            "raw_order_data": transaction_data["limit_order"]["raw_order_data"],
            "signature": signature,
            "signed_order_type": "tegro",
            "market_id": transaction_data["limit_order"]["market_id"],
            "market_symbol": symbol,
        }
        try:
            data = await self._api_request(
                path_url = CONSTANTS.ORDER_PATH_URL,
                method = RESTMethod.POST,
                data = api_params,
                is_auth_required = False,
                limit_id = CONSTANTS.ORDER_PATH_URL)
        except IOError as e:
            error_description = str(e)
            insufficient_allowance = ("insufficient allowance" in error_description)
            is_server_overloaded = ("status is 503" in error_description
                                    and "Unknown error, please check your request or try again later." in error_description)
            if insufficient_allowance:
                await self.approve_allowance(token=symbol)
            if is_server_overloaded:
                o_id = "Unknown"
                transact_time = int(datetime.now(timezone.utc).timestamp() * 1e3)
            else:
                raise
        else:
            o_id = f"{data['order_id']}"
            transact_time = data["timestamp"] * 1e-3
        return o_id, transact_time

    async def _generate_typed_data(self, amount, order_type, price, trade_type, trading_pair) -> Dict[str, Any]:
        side_str = CONSTANTS.SIDE_BUY if trade_type is TradeType.BUY else CONSTANTS.SIDE_SELL
        params = {
            "chain_id": self.chain,
            "market_symbol": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "side": side_str,
            "wallet_address": self.api_key
        }
        data = await self.initialize_verified_market()
        # quote_precision = int(data["quote_precision"])
        base_precision = int(data["base_precision"])
        price_precision = 18
        params["amount"] = f"{amount:.{base_precision}g}"
        if order_type is OrderType.LIMIT or order_type is OrderType.LIMIT_MAKER:
            price_str = price
            params["price"] = f"{price_str:.{price_precision}g}"
        try:
            return await self._api_request(
                path_url = CONSTANTS.GENERATE_SIGN_URL,
                method = RESTMethod.POST,
                data = params,
                is_auth_required = False,
                limit_id = CONSTANTS.GENERATE_SIGN_URL)
        except IOError as e:
            raise IOError(f"Error submitting order {e}")

    async def _generate_cancel_order_typed_data(self, order_id: str, ids: list) -> Dict[str, Any]:
        try:
            params = {
                "order_ids": ids,
                "user_address": self.api_key.lower()
            }
            data = await self._api_request(
                path_url=CONSTANTS.GENERATE_ORDER_URL,
                method=RESTMethod.POST,
                data=params,
                is_auth_required=False,
                limit_id=CONSTANTS.GENERATE_ORDER_URL,
            )
            return self.sign_inner(data)
        except IOError as e:
            error_description = str(e)
            is_not_active = ("Orders not found" in error_description)
            if is_not_active:
                self.logger().debug(f"The order {order_id} does not exist on tegro."
                                    f"No cancelation needed.")
                return "Order not found"
            else:
                raise

    def sign_inner(self, data):
        message = "Order" if "Order" in data["sign_data"]["types"] else "CancelOrder"
        domain_data = data["sign_data"]["domain"]
        message_data = data["sign_data"]["message"]
        message_types = {message: data["sign_data"]["types"][message]}
        # encode and sign
        structured_data = encode_typed_data(domain_data, message_types, message_data)
        return eth_account.Account.from_key(self.secret_key).sign_message(structured_data).signature.hex()

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        ids = []
        ex_oid = (await tracked_order.get_exchange_order_id()).split("+")[0]
        ids.append(ex_oid)
        signature = await self._generate_cancel_order_typed_data(order_id, ids)
        if signature is not None and signature != "Order not found":
            params = {
                "user_address": self.api_key,
                "order_ids": ids,
                "Signature": signature,
            }
            cancel_result = await self._api_request(
                path_url=CONSTANTS.CANCEL_ORDER_URL,
                method=RESTMethod.POST,
                data=params,
                is_auth_required=False,
                limit_id=CONSTANTS.CANCEL_ORDER_URL)
            result = cancel_result["cancelled_order_ids"][0]
            return True if result == ids[0] else False
        elif signature == "Order not found":
            await self._order_tracker.process_order_not_found(order_id)

    async def _format_trading_rules(self, exchange_info: List[Dict[str, Any]]) -> List[TradingRule]:
        """
        Example:
            {
                "id": "80002_0xfd655398df1c2e40c383b022fba15751e8e2ab49_0x7551122e441edbf3fffcbcf2f7fcc636b636482b",
                "symbol": "AYB_USDT",
                "chainId": 80002,
                "state": "verified",
                "base_contract_address": "0xfd655398df1c2e40c383b022fba15751e8e2ab49",
                "base_symbol": "AYB",
                "base_decimal": 18,
                "base_precision": 0,
                "quote_contract_address": "0x7551122e441edbf3fffcbcf2f7fcc636b636482b",
                "quote_symbol": "USDT",
                "quote_decimal": 6,
                "quote_precision": 10,
                "ticker": {
                    "base_volume": 0,
                    "quote_volume": 0,
                    "price": 0,
                    "price_change_24h": 0,
                    "price_high_24h": 0,
                    "price_low_24h": 0,
                    "ask_low": 0,
                    "bid_high": 0
                }
            }
        """
        retval = []
        for rule in filter(tegro_utils.is_exchange_information_valid, exchange_info):
            try:
                trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=rule.get("symbol"))
                min_order_size = Decimal(f'1e-{rule["base_precision"]}')
                min_price_inc = Decimal(f"1e-{rule['quote_precision']}")
                step_size = Decimal(f'1e-{rule["base_precision"]}')
                retval.append(
                    TradingRule(trading_pair,
                                min_order_size = Decimal(min_order_size),
                                min_price_increment = Decimal(min_price_inc),
                                min_base_amount_increment = Decimal(step_size)))
            except Exception:
                self.logger().exception(f"Error parsing the trading pair rule {rule}. Skipping.")
        return retval

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        pass

    async def _user_stream_event_listener(self):
        """
        Listens to messages from _user_stream_tracker.user_stream queue.
        Traders, Orders, and Balance updates from the WS.
        """
        user_channels = CONSTANTS.USER_METHODS
        async for event_message in self._iter_user_event_queue():
            try:
                channel: str = event_message.get("action", None)
                results: Dict[str, Any] = event_message.get("data", {})
                if "code" not in event_message and channel not in user_channels.values():
                    self.logger().error(
                        f"Unexpected message in user stream: {event_message}.", exc_info = True)
                    continue
                elif channel == CONSTANTS.USER_METHODS["ORDER_SUBMITTED"]:
                    await self._process_order_message(results)
                elif channel == CONSTANTS.USER_METHODS["ORDER_TRADE_PROCESSED"]:
                    await self._process_order_message(results, fetch_trades = True)

            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error(
                    "Unexpected error in user stream listener loop.", exc_info=True)
                await self._sleep(5.0)

    def _create_order_update_with_order_status_data(self, order_status: Dict[str, Any], order: InFlightOrder):
        new_states = self.get_state(order_status)
        confirmed_state = CONSTANTS.ORDER_STATE[new_states]
        order_update = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=order_status["timestamp"] * 1e-3,
            new_state=confirmed_state,
            client_order_id=order.client_order_id,
            exchange_order_id=f"{str(order_status['order_id'])}",
        )
        return order_update

    async def _process_order_message(self, raw_msg: Dict[str, Any], fetch_trades = False):
        client_order_id = f"{raw_msg['order_id']}"
        tracked_order = self._order_tracker.all_fillable_orders_by_exchange_order_id.get(client_order_id)
        if not tracked_order:
            self.logger().debug(f"Ignoring order message with id {client_order_id}: not in in_flight_orders.")
            return
        if fetch_trades:
            # process trade fill
            await self._all_trade_updates_for_order(order=tracked_order)
        order_update = self._create_order_update_with_order_status_data(order_status=raw_msg, order=tracked_order)
        self._order_tracker.process_order_update(order_update=order_update)

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        trade_updates = []

        if order.exchange_order_id is not None:
            exchange_order_id = (await order.get_exchange_order_id()).split("+")[0]
            trading_pair = await self.exchange_symbol_associated_to_pair(trading_pair=order.trading_pair)
            all_fills_response = await self._api_get(
                path_url=CONSTANTS.TRADES_FOR_ORDER_PATH_URL.format(exchange_order_id),
                is_auth_required=False,
                limit_id=CONSTANTS.TRADES_FOR_ORDER_PATH_URL)

            if len(all_fills_response) > 0:
                for trade in all_fills_response:
                    timestamp = trade["timestamp"]
                    symbol = trade["symbol"].split('_')[1]
                    fees = "0"
                    if order.trade_type == TradeType.BUY:
                        fees = trade["maker_fee"] if trade["is_buyer_maker"] else trade["taker_fee"]
                    if order.trade_type == TradeType.SELL:
                        fees = trade["taker_fee"] if trade["is_buyer_maker"] else trade["maker_fee"]
                    fee = TradeFeeBase.new_spot_fee(
                        fee_schema = self.trade_fee_schema(),
                        trade_type = order.trade_type,
                        percent_token = symbol,
                        flat_fees = [TokenAmount(amount=Decimal(fees), token=symbol)]
                    )
                    trade_update = TradeUpdate(
                        trade_id=trade["id"],
                        client_order_id=order.client_order_id,
                        exchange_order_id=order.exchange_order_id,
                        trading_pair=trading_pair,
                        fee=fee,
                        fill_base_amount=Decimal(trade["amount"]),
                        fill_quote_amount=Decimal(trade["amount"]) * Decimal(trade["price"]),
                        fill_price=Decimal(trade["price"]),
                        fill_timestamp=timestamp * 1e-3)
                    self._order_tracker.process_trade_update(trade_update)
                    trade_updates.append(trade_update)

        return trade_updates

    def get_state(self, updated_order_data):
        new_states = ""
        data = {}
        if isinstance(updated_order_data, list):
            state = updated_order_data[0]["status"]
            data = updated_order_data[0]
        else:
            state = updated_order_data["status"]
            data = updated_order_data
        if state == "closed" and Decimal(data["quantity_pending"]) == Decimal("0"):
            new_states = "completed"
        elif state == "open" and Decimal(data["quantity_filled"]) < Decimal("0"):
            new_states = "open"
        elif state == "open" and Decimal(data["quantity_filled"]) > Decimal("0"):
            new_states = "partial"
        elif state == "closed" and Decimal(data["quantity_pending"]) > Decimal("0"):
            new_states = "pending"
        elif state == "cancelled" and data["cancel"]["code"] == 611:
            new_states = "cancelled"
        elif state == "cancelled" and data["cancel"]["code"] != 611:
            new_states = "failed"
        else:
            new_states = data["status"]
        return new_states

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        o_id = (await tracked_order.get_exchange_order_id()).split("+")[0]
        updated_order_data = await self._api_get(
            path_url=CONSTANTS.TEGRO_USER_ORDER_PATH_URL.format(self.api_key),
            params = {
                "chain_id": self.chain,
                "order_id": o_id
            },
            limit_id=CONSTANTS.TEGRO_USER_ORDER_PATH_URL,
            is_auth_required=False)
        new_states = self.get_state(updated_order_data)
        confirmed_state = CONSTANTS.ORDER_STATE[new_states]
        order_update = OrderUpdate(
            client_order_id=tracked_order.client_order_id,
            exchange_order_id=tracked_order.exchange_order_id,
            trading_pair=tracked_order.trading_pair,
            update_timestamp=updated_order_data[0]["timestamp"] * 1e-3,
            new_state=confirmed_state)
        return order_update

    async def _update_balances(self):
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()

        balances = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.ACCOUNTS_PATH_URL.format(self.chain, self.api_key),
            limit_id=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=False)

        for balance_entry in balances:
            asset_name = balance_entry["symbol"]
            bal = float(str(balance_entry["balance"]))
            balance = Decimal(bal)
            self._account_available_balances[asset_name] = balance
            self._account_balances[asset_name] = balance
            remote_asset_names.add(asset_name)
        asset_names_to_remove = local_asset_names.difference(remote_asset_names)
        for asset in asset_names_to_remove:
            del self._account_available_balances[asset]
            del self._account_balances[asset]

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: list[Dict[str, Any]]):
        mapping = bidict()
        for symbol_data in exchange_info:
            if tegro_utils.is_exchange_information_valid(exchange_info=symbol_data):
                try:
                    base, quote = symbol_data['symbol'].split('_')
                    mapping[symbol_data["symbol"]] = combine_to_hb_trading_pair(base=base, quote=quote)
                except Exception as exception:
                    self.logger().error(f"There was an error parsing a trading pair information ({exception})")
        self._set_trading_pair_symbol_map(mapping)

    async def approve_allowance(self, token=None, fail_silently: bool = True):
        """
        Approves the allowance for a specific token on a decentralized exchange.

        This function retrieves the trading pairs, determines the associated
        symbols, and approves the maximum allowance for each token in the
        trading pairs on the specified exchange contract.

        Returns:
        dict or None: The transaction receipt if the transaction is successful, otherwise None.
        """
        exchange_con_addr = ""
        token_list = []
        data = {}

        # Fetching trading pairs and determining associated symbols
        for trading_pair in self.trading_pairs:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            base, quote = symbol.split("_")
            token_list.append(base)
            token_list.append(quote)

        # If a specific token is provided, use only that token
        if token:
            base, quote = token.split("_")
            token_list = [base, quote]

        # Setting up Web3
        w3 = Web3(Web3.HTTPProvider(CONSTANTS.Node_URLS[self.node_rpc]))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        approve_abi = CONSTANTS.ABI["approve"]

        # Fetching token and chain information
        tokens = await self.tokens_info()
        chain_data = await self.get_chain_list()
        exchange_con_addr = [
            Web3.to_checksum_address(chain["exchange_contract"])
            for chain in chain_data if int(chain["id"]) == self.chain][0]
        receipts = []
        # Organizing token data
        for t in tokens:
            data[t["symbol"]] = {"address": t["address"]}
        # Loop through each token and approve allowance

        for token in token_list:
            con_addr = Web3.to_checksum_address(data[token]["address"])
            addr = Web3.to_checksum_address(self.api_key)
            contract = w3.eth.contract(con_addr, abi=approve_abi)
            # Get nonce
            nonce = w3.eth.get_transaction_count(addr)
            # Prepare transaction parameters
            tx_params = {"from": addr, "nonce": nonce, "gasPrice": w3.eth.gas_price}
            try:
                # Estimate gas for the approval transaction
                gas_estimate = contract.functions.approve(exchange_con_addr, MAX_UINT256).estimate_gas({
                    "from": addr, })
                tx_params["gas"] = gas_estimate

                # Building, signing, and sending the approval transaction
                approval_contract = contract.functions.approve(exchange_con_addr, MAX_UINT256).build_transaction(tx_params)
                signed_tx = w3.eth.account.sign_transaction(approval_contract, self.secret_key)
                txn_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                reciept = w3.eth.wait_for_transaction_receipt(txn_hash)
                print(f"Approved allowance for token {token} with transaction hash {txn_hash}")
                receipts.append(reciept)
            except Exception as e:
                # Log the error and continue with the next token
                self.logger().debug("Error occurred while approving allowance for token %s: %s", token, str(e))
                if not fail_silently:
                    raise e
        return receipts if len(receipts) > 0 else None

    async def initialize_market_list(self):
        return await self._api_request(
            method=RESTMethod.GET,
            params={"page": 1, "sort_order": "desc", "sort_by": "volume", "page_size": 20, "verified": "true"},
            path_url = CONSTANTS.MARKET_LIST_PATH_URL.format(self.chain),
            is_auth_required = False,
            limit_id = CONSTANTS.MARKET_LIST_PATH_URL)

    async def initialize_verified_market(self):
        data = await self.initialize_market_list()
        id = []
        for trading_pair in self.trading_pairs:
            symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        for market in data:
            if market["chainId"] == self.chain and market["symbol"] == symbol:
                id.append(market)
        return await self._api_request(
            path_url = CONSTANTS.EXCHANGE_INFO_PATH_URL.format(self.chain, id[0]["id"]),
            method=RESTMethod.GET,
            is_auth_required = False,
            limit_id = CONSTANTS.EXCHANGE_INFO_PATH_URL)

    async def _get_last_traded_price(self, trading_pair: str) -> float:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
        if symbol is not None:
            data = await self.initialize_verified_market()
            resp_json = await self._api_request(
                method=RESTMethod.GET,
                path_url = CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL.format(self.chain, data["id"]),
                is_auth_required = False,
                limit_id = CONSTANTS.TICKER_PRICE_CHANGE_PATH_URL
            )
            return Decimal(resp_json["ticker"]["price"])

    async def _make_network_check_request(self):
        return await self._api_request(
            path_url = self.check_network_request_path,
            method=RESTMethod.GET,
            is_auth_required = False,
            limit_id = CONSTANTS.PING_PATH_URL)

    async def _make_trading_rules_request(self) -> Any:
        data: list[dict[str, Any]] = await self._api_request(
            path_url = self.trading_pairs_request_path.format(self.chain),
            method=RESTMethod.GET,
            params={"page": 1, "sort_order": "desc", "sort_by": "volume", "page_size": 20, "verified": "true"},
            is_auth_required = False,
            limit_id = CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL)
        return data

    async def _make_trading_pairs_request(self) -> Any:
        resp = await self._api_request(
            path_url = self.trading_pairs_request_path.format(self.chain),
            method=RESTMethod.GET,
            params={
                "page": 1,
                "sort_order": "desc",
                "sort_by": "volume",
                "page_size": 20,
                "verified": "true"
            },
            is_auth_required = False,
            limit_id = CONSTANTS.EXCHANGE_INFO_PATH_LIST_URL)
        return resp

    async def tokens_info(self):
        account_info = await self._api_request(
            method=RESTMethod.GET,
            path_url=CONSTANTS.ACCOUNTS_PATH_URL.format(self.chain, self.api_key),
            limit_id=CONSTANTS.ACCOUNTS_PATH_URL,
            is_auth_required=False)
        data = []
        for dats in (account_info):
            token_data = {"symbol": dats["symbol"], "address": dats["address"]}
            data.append(token_data)
        return data
