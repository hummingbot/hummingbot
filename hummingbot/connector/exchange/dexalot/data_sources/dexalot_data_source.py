import asyncio
from asyncio import Lock
from decimal import Decimal
from typing import Dict, List

from eth_account import Account
from eth_account.signers.local import LocalAccount
from hexbytes import HexBytes
from web3 import AsyncWeb3, Web3
from web3.middleware import async_geth_poa_middleware

from hummingbot.connector.exchange.dexalot import dexalot_constants as CONSTANTS
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType

DEXALOT_TRADEPAIRS_ABI = '[{"name": "cancelAddList", "type": "function", "inputs": [{"name": "_orderIdsToCancel", "type": "bytes32[]", "internalType": "bytes32[]"}, {"name": "_orders", "type": "tuple[]", "components": [{"name": "clientOrderId", "type": "bytes32", "internalType": "bytes32"}, {"name": "tradePairId", "type": "bytes32", "internalType": "bytes32"}, {"name": "price", "type": "uint256", "internalType": "uint256"}, {"name": "quantity", "type": "uint256", "internalType": "uint256"}, {"name": "traderaddress", "type": "address", "internalType": "address"}, {"name": "side", "type": "uint8", "internalType": "enum ITradePairs.Side"}, {"name": "type1", "type": "uint8", "internalType": "enum ITradePairs.Type1"}, {"name": "type2", "type": "uint8", "internalType": "enum ITradePairs.Type2"}, {"name": "stp", "type": "uint8", "internalType": "enum ITradePairs.STP"}], "internalType": "struct ITradePairs.NewOrder[]"}], "outputs": [], "stateMutability": "nonpayable"}, {"name": "addOrderList", "type": "function", "inputs": [{"name": "_orders", "type": "tuple[]", "components": [{"name": "clientOrderId", "type": "bytes32", "internalType": "bytes32"}, {"name": "tradePairId", "type": "bytes32", "internalType": "bytes32"}, {"name": "price", "type": "uint256", "internalType": "uint256"}, {"name": "quantity", "type": "uint256", "internalType": "uint256"}, {"name": "traderaddress", "type": "address", "internalType": "address"}, {"name": "side", "type": "uint8", "internalType": "enum ITradePairs.Side"}, {"name": "type1", "type": "uint8", "internalType": "enum ITradePairs.Type1"}, {"name": "type2", "type": "uint8", "internalType": "enum ITradePairs.Type2"}, {"name": "stp", "type": "uint8", "internalType": "enum ITradePairs.STP"}], "internalType": "struct ITradePairs.NewOrder[]"}], "outputs": [], "stateMutability": "nonpayable"}, {"name": "cancelOrderList", "type": "function", "inputs": [{"name": "_orderIds", "type": "bytes32[]", "internalType": "bytes32[]"}], "outputs": [], "stateMutability": "nonpayable"}]'

DEXALOT_PORTFOLIOSUB_ABI = '[{"name": "getBalances", "type": "function", "inputs": [{"name": "_owner", "type": "address", "internalType": "address"}, {"name": "_pageNo", "type": "uint256", "internalType": "uint256"}], "outputs": [{"name": "symbols", "type": "bytes32[]", "internalType": "bytes32[]"}, {"name": "total", "type": "uint256[]", "internalType": "uint256[]"}, {"name": "available", "type": "uint256[]", "internalType": "uint256[]"}], "stateMutability": "view"}]'


class DexalotClient:

    def __init__(
            self,
            dexalot_api_secret: str,
            connector,
            domain: str = CONSTANTS.DEFAULT_DOMAIN,
            trading_required: bool = True,
    ):
        self._private_key = dexalot_api_secret
        self._connector = connector
        self._domain = domain
        self._trading_required = trading_required
        self.last_nonce = 0
        self.transaction_lock = Lock()
        self.balance_evm_params = {}

        self.provider = CONSTANTS.DEXALOT_SUBNET_RPC_URL if self._domain == "dexalot" else CONSTANTS.TESTNET_DEXALOT_SUBNET_RPC_URL
        # Note: The or trading_capability here is required because an instance is created by calling
        # "connect" command which does not require trading (trading_capability=False)
        self.account: LocalAccount = Account.from_key(dexalot_api_secret) if self.trading_required \
            or self.trading_capability else None  # See the above comment for details
        self.async_w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(self.provider))
        self.async_w3.eth.default_account = self.account.address if self.account else None
        self._w3 = Web3(Web3.HTTPProvider(self.provider))
        self.async_w3.middleware_onion.inject(async_geth_poa_middleware, layer=0)
        self.async_w3.strict_bytes_type_checking = False
        TRADEPAIRS_ADDRESS = CONSTANTS.DEXALOT_TRADEPAIRS_ADDRESS if self._domain == "dexalot" else CONSTANTS.TESTNET_DEXALOT_TRADEPAIRS_ADDRESS
        PORTFOLIOSUB_ADDRESS = CONSTANTS.DEXALOT_PORTFOLIOSUB_ADDRESS if self._domain == "dexalot" else CONSTANTS.TESTNET_DEXALOT_PORTFOLIOSUB_ADDRESS

        self.trade_pairs_manager = self.async_w3.eth.contract(address=TRADEPAIRS_ADDRESS,
                                                              abi=DEXALOT_TRADEPAIRS_ABI)

        self.portfolio_sub_manager = self.async_w3.eth.contract(address=PORTFOLIOSUB_ADDRESS,
                                                                abi=DEXALOT_PORTFOLIOSUB_ABI)

    @property
    def trading_required(self):
        return self._trading_required

    @property
    def trading_capability(self) -> bool:
        return self._private_key not in (None, "")

    async def _get_token_info(self):
        token_raw_info_list = await self._connector._api_get(
            path_url=CONSTANTS.TOKEN_INFO_PATH_URL,
            params={},
            is_auth_required=False,
            limit_id=CONSTANTS.IP_REQUEST_WEIGHT)
        for token_info in token_raw_info_list:
            self.balance_evm_params[token_info["subnet_symbol"]] = {
                "token_evmdecimals": token_info["evmdecimals"]
            }

    async def get_balances(self, account_balances: Dict, account_available_balances: Dict):
        if not self.balance_evm_params:
            await self._get_token_info()
        balances = await self.portfolio_sub_manager.functions.getBalances(self.account.address, 50).call()
        coin_list = balances[0]
        total_list = balances[1]
        for index, evm_total_balance in enumerate(total_list):
            if evm_total_balance != 0:
                coin = coin_list[index].decode('utf-8').rstrip('\x00')
                for k, v in self.balance_evm_params.items():
                    if k == coin:
                        evmdecimals = v["token_evmdecimals"]
                        total_balance = evm_total_balance * Decimal(f'1e-{evmdecimals}')
                        account_balances[coin.upper()] = total_balance
                        account_available_balances[coin.upper()] = total_balance
                        break
        return account_balances, account_available_balances

    async def cancel_and_add_order_list(
            self,
            orders_to_cancel: List[GatewayInFlightOrder],
            order_list: List[GatewayInFlightOrder]):
        new_order_list = []
        if order_list:
            symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=order_list[0].trading_pair)
            pairByte32 = HexBytes(symbol.encode('utf-8'))
            trader_address = Account.from_key(self._private_key).address
            for order in order_list:
                trading_pair = order_list[0].trading_pair
                _trade_address = trader_address
                _client_order_id = order.client_order_id
                _trade_pair_id = pairByte32
                _price = int(order.price * 10 ** self._connector._evm_params[trading_pair]["base_evmdecimals"])
                _quantity = int(order.amount * 10 ** self._connector._evm_params[trading_pair]["quote_evmdecimals"])
                _side = 1 if order.trade_type == TradeType.SELL else 0
                _type1 = 0 if order.order_type is OrderType.MARKET else 1
                _type2 = 3 if order.order_type == OrderType.LIMIT_MAKER else 0
                _stp = 3  # self trade prevention mode,0 = CANCELTAKER,1 = CANCELMAKER,2 = CANCELBOTH,3 = NONE
                new_order_list.append(
                    (_client_order_id, _trade_pair_id, _price, _quantity, _trade_address, _side, _type1, _type2, _stp)
                )
        gas = len(order_list) * CONSTANTS.PLACE_ORDER_GAS_LIMIT + len(orders_to_cancel) * CONSTANTS.CANCEL_GAS_LIMIT

        cancel_order_list = [i.exchange_order_id for i in orders_to_cancel]
        function = self.trade_pairs_manager.functions.cancelAddList(cancel_order_list, new_order_list)
        result = await self._build_and_send_tx(function, gas)
        return result

    async def cancel_order_list(self, orders_to_cancel: List[GatewayInFlightOrder]):
        cancel_order_list = [i.exchange_order_id for i in orders_to_cancel]
        gas = len(orders_to_cancel) * CONSTANTS.CANCEL_GAS_LIMIT
        function = self.trade_pairs_manager.functions.cancelOrderList(cancel_order_list)
        result = await self._build_and_send_tx(function, gas)
        return result

    async def _build_and_send_tx(self, function, gas):
        """
        Build and send a transaction.
        If gasPrice is not specified, the average price of the whole network is used by default

        """
        async with self.transaction_lock:
            result = None
            for retry_attempt in range(CONSTANTS.TRANSACTION_REQUEST_ATTEMPTS):
                current_nonce = await self.async_w3.eth.get_transaction_count(self.account.address)
                try:
                    tx_params = {
                        'nonce': current_nonce if current_nonce > self.last_nonce else self.last_nonce,
                        'gas': gas,
                    }
                    transaction = await function.build_transaction(tx_params)
                    signed_txn = self.async_w3.eth.account.sign_transaction(
                        transaction, private_key=self._private_key
                    )
                    result = await self.async_w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    return result.hex()
                except ValueError as e:
                    self._connector.logger().warning(
                        f"{str(e)} "
                        f"Attempt {function.abi['name']} {retry_attempt + 1}/{CONSTANTS.TRANSACTION_REQUEST_ATTEMPTS}"
                    )
                    arg = str(e)
                    if "replacement transaction underpriced" in arg:
                        self.last_nonce = current_nonce + 1
                    else:
                        self.last_nonce = int(arg[arg.find('next nonce ') + 11: arg.find(", tx nonce")])
                    await asyncio.sleep(CONSTANTS.RETRY_INTERVAL ** retry_attempt)
                    continue
            if not result:
                raise IOError(f"Error fetching data from {function.abi['name']}.")
            return result
