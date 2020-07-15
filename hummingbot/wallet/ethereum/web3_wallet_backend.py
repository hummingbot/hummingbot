import asyncio
from collections import OrderedDict
from decimal import Decimal
from eth_account import Account
from eth_account.signers.local import LocalAccount
from eth_account.messages import defunct_hash_message
from hexbytes import HexBytes
import logging
import math
import time
from typing import (
    Any,
    List,
    Dict,
    Optional,
    Set,
    Coroutine
)
from web3 import Web3
from web3.contract import (
    Contract,
    ContractFunction
)
from web3.datastructures import AttributeDict
from web3.exceptions import (
    BlockNotFound,
    TransactionNotFound
)

from hummingbot.core.utils.async_call_scheduler import AsyncCallScheduler
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.core.event.event_forwarder import EventForwarder
from hummingbot.core.event.events import (
    WalletEvent,
    WalletReceivedAssetEvent,
    TokenApprovedEvent,
    EthereumGasUsedEvent,
    ERC20WatcherEvent,
    IncomingEthWatcherEvent,
    WalletWrappedEthEvent,
    WalletUnwrappedEthEvent,
    NewBlocksWatcherEvent,
    ZeroExEvent,
    ZeroExFillEvent
)
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub import PubSub
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)
from hummingbot.wallet.ethereum.watcher import (
    AccountBalanceWatcher,
    ERC20EventsWatcher,
    IncomingEthWatcher,
    WethWatcher,
    ZeroExFillWatcher,
)
from hummingbot.wallet.ethereum.watcher.websocket_watcher import WSNewBlocksWatcher
from hummingbot.wallet.ethereum.erc20_token import ERC20Token
from hummingbot.logger import HummingbotLogger
from hummingbot.client.config.global_config_map import global_config_map

s_decimal_0 = Decimal(0)


class Web3WalletBackend(PubSub):
    DEFAULT_GAS_PRICE = 1e9  # 1 gwei = 1e9 wei
    TRANSACTION_RECEIPT_POLLING_TICK = 10.0

    _w3wb_logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._w3wb_logger is None:
            cls._w3wb_logger = logging.getLogger(__name__)
        return cls._w3wb_logger

    def __init__(self,
                 private_key: Any,
                 jsonrpc_url: str,
                 erc20_token_addresses: List[str],
                 chain: EthereumChain = EthereumChain.ROPSTEN):
        super().__init__()

        # Initialize Web3, accounts and contracts.
        self._w3: Web3 = Web3(Web3.HTTPProvider(jsonrpc_url))
        self._chain: EthereumChain = chain
        self._account: LocalAccount = Account.privateKeyToAccount(private_key)
        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

        # Initialize ERC20 tokens data structures.
        self._erc20_token_list: List[ERC20Token] = [
            ERC20Token(self._w3, erc20_token_address, self._chain) for erc20_token_address in erc20_token_addresses
        ]
        self._erc20_tokens: Dict[str, ERC20Token] = OrderedDict()
        self._asset_decimals: Dict[str, int] = {"ETH": 18}
        self._weth_token: Optional[ERC20Token] = None

        # Initialize the event forwarders.
        self._received_asset_event_forwarder: EventForwarder = EventForwarder(
            self._received_asset_event_listener
        )
        self._approved_token_event_forwarder: EventForwarder = EventForwarder(
            self._token_approved_event_listener
        )
        self._wrapped_eth_event_forwarder: EventForwarder = EventForwarder(
            self._eth_wrapped_event_listener
        )
        self._unwrapped_eth_event_forwarder: EventForwarder = EventForwarder(
            self._eth_unwrapped_event_listener
        )
        self._zeroex_fill_event_forwarder: EventForwarder = EventForwarder(
            self._zeroex_fill_event_listener
        )

        # Blockchain data
        self._local_nonce: int = -1

        # Watchers
        self._new_blocks_watcher: Optional[WSNewBlocksWatcher] = None
        self._account_balance_watcher: Optional[AccountBalanceWatcher] = None
        self._erc20_events_watcher: Optional[ERC20EventsWatcher] = None
        self._incoming_eth_watcher: Optional[IncomingEthWatcher] = None
        self._weth_watcher: Optional[WethWatcher] = None
        self._zeroex_fill_watcher: Optional[ZeroExFillWatcher] = None

        # Tasks and transactions
        self._check_network_task: Optional[asyncio.Task] = None
        self._network_status: NetworkStatus = NetworkStatus.STOPPED
        self._outgoing_transactions_queue: asyncio.Queue = asyncio.Queue()
        self._outgoing_transactions_task: Optional[asyncio.Task] = None
        self._check_transaction_receipts_task: Optional[asyncio.Task] = None
        self._pending_tx_dict: Dict[str, any] = {}
        self._gas_price: int = self.DEFAULT_GAS_PRICE
        self._last_timestamp_received_blocks: float = 0.0
        self._event_forwarder: EventForwarder = EventForwarder(self._did_receive_new_blocks)

    @property
    def address(self) -> str:
        return self._account.address

    @property
    def block_number(self) -> int:
        return self._new_blocks_watcher.block_number if self._new_blocks_watcher is not None else -1

    @property
    def gas_price(self) -> int:
        """
        Warning: This property causes network access, even though it's synchronous.

        :return: Gas price in wei
        """
        # TODO: The gas price from Parity is not reliable. Convert to use internal gas price calculator
        return self._gas_price

    @property
    def nonce(self) -> int:
        """
        Warning: This property causes network access, even though it's synchronous.

        :return: Gas price in wei
        """
        remote_nonce: int = self.get_remote_nonce()
        retval: int = max(remote_nonce, self._local_nonce)
        self._local_nonce = retval
        return retval

    @property
    def chain(self) -> EthereumChain:
        return self._chain

    @property
    def erc20_tokens(self) -> Dict[str, ERC20Token]:
        return self._erc20_tokens.copy()

    @property
    def started(self) -> bool:
        return self._check_network_task is not None

    @property
    def network_status(self) -> NetworkStatus:
        return self._network_status

    @property
    def account(self) -> LocalAccount:
        return self._account

    @property
    def zeroex_fill_watcher(self) -> ZeroExFillWatcher:
        return self._zeroex_fill_watcher

    def start(self):
        if self.started:
            self.stop()

        self._check_network_task = safe_ensure_future(self._check_network_loop())
        self._network_status = NetworkStatus.NOT_CONNECTED

    def stop(self):
        if self._check_network_task is not None:
            self._check_network_task.cancel()
            self._check_network_task = None
        safe_ensure_future(self.stop_network())
        self._network_status = NetworkStatus.STOPPED

    async def start_network(self):
        if self._outgoing_transactions_task is not None:
            await self.stop_network()

        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        if len(self._erc20_tokens) < len(self._erc20_token_list):
            # Fetch token data.
            fetch_symbols_tasks: List[Coroutine] = [
                token.get_symbol()
                for token in self._erc20_token_list
            ]

            token_symbols: List[str] = await safe_gather(*fetch_symbols_tasks)
            fetch_decimals_tasks: List[Coroutine] = [
                token.get_decimals()
                for token in self._erc20_token_list
            ]
            token_decimals: List[int] = await safe_gather(*fetch_decimals_tasks)
            for token, symbol, decimals in zip(self._erc20_token_list, token_symbols, token_decimals):
                self._erc20_tokens[symbol] = token
                self._asset_decimals[symbol] = decimals
            self._weth_token = self._erc20_tokens.get("WETH")

        # Fetch blockchain data.
        self._local_nonce = await async_scheduler.call_async(
            lambda: self.get_remote_nonce()
        )

        # Create event watchers.
        websocket_url: str = global_config_map["ethereum_rpc_ws_url"].value
        self._new_blocks_watcher = WSNewBlocksWatcher(self._w3, websocket_url)
        self._account_balance_watcher = AccountBalanceWatcher(
            self._w3,
            self._new_blocks_watcher,
            self._account.address,
            [erc20_token.address for erc20_token in self._erc20_tokens.values()],
            [token.abi for token in self._erc20_tokens.values()]
        )
        self._erc20_events_watcher = ERC20EventsWatcher(
            self._w3,
            self._new_blocks_watcher,
            [token.address for token in self._erc20_tokens.values()],
            [token.abi for token in self._erc20_tokens.values()],
            [self._account.address]
        )
        self._incoming_eth_watcher = IncomingEthWatcher(
            self._w3,
            self._new_blocks_watcher,
            [self._account.address]
        )
        if self._weth_token is not None:
            self._weth_watcher = WethWatcher(
                self._w3,
                self._weth_token,
                self._new_blocks_watcher,
                [self._account.address]
            )
        self._zeroex_fill_watcher = ZeroExFillWatcher(
            self._w3,
            self._new_blocks_watcher
        )

        # Connect the event forwarders.
        self._new_blocks_watcher.add_listener(NewBlocksWatcherEvent.NewBlocks,
                                              self._event_forwarder)
        self._erc20_events_watcher.add_listener(ERC20WatcherEvent.ReceivedToken,
                                                self._received_asset_event_forwarder)
        self._erc20_events_watcher.add_listener(ERC20WatcherEvent.ApprovedToken,
                                                self._approved_token_event_forwarder)
        self._incoming_eth_watcher.add_listener(IncomingEthWatcherEvent.ReceivedEther,
                                                self._received_asset_event_forwarder)
        self._zeroex_fill_watcher.add_listener(ZeroExEvent.Fill,
                                               self._zeroex_fill_event_forwarder)

        if self._weth_watcher is not None:
            self._weth_watcher.add_listener(WalletEvent.WrappedEth,
                                            self._wrapped_eth_event_forwarder)
            self._weth_watcher.add_listener(WalletEvent.UnwrappedEth,
                                            self._unwrapped_eth_event_forwarder)

        # Start the transaction processing tasks.
        self._outgoing_transactions_task = safe_ensure_future(self.outgoing_eth_transactions_loop())
        self._check_transaction_receipts_task = safe_ensure_future(self.check_transaction_receipts_loop())

        # Start the event watchers.
        await self._new_blocks_watcher.start_network()
        await self._account_balance_watcher.start_network()
        await self._erc20_events_watcher.start_network()
        await self._incoming_eth_watcher.start_network()
        if self._weth_watcher is not None:
            await self._weth_watcher.start_network()

    async def stop_network(self):
        # Disconnect the event forwarders.
        if self._erc20_events_watcher is not None:
            self._erc20_events_watcher.remove_listener(ERC20WatcherEvent.ReceivedToken,
                                                       self._received_asset_event_forwarder)
            self._erc20_events_watcher.remove_listener(ERC20WatcherEvent.ApprovedToken,
                                                       self._approved_token_event_forwarder)
        if self._incoming_eth_watcher is not None:
            self._incoming_eth_watcher.remove_listener(IncomingEthWatcherEvent.ReceivedEther,
                                                       self._received_asset_event_forwarder)
        if self._weth_watcher is not None:
            self._weth_watcher.remove_listener(WalletEvent.WrappedEth,
                                               self._wrapped_eth_event_forwarder)
            self._weth_watcher.remove_listener(WalletEvent.UnwrappedEth,
                                               self._unwrapped_eth_event_forwarder)

        # Stop the event watchers.
        if self._new_blocks_watcher is not None:
            self._new_blocks_watcher.remove_listener(NewBlocksWatcherEvent.NewBlocks, self._event_forwarder)
            await self._new_blocks_watcher.stop_network()
        if self._account_balance_watcher is not None:
            await self._account_balance_watcher.stop_network()
        if self._erc20_events_watcher is not None:
            await self._erc20_events_watcher.stop_network()
        if self._incoming_eth_watcher is not None:
            await self._incoming_eth_watcher.stop_network()
        if self._weth_watcher is not None:
            await self._weth_watcher.stop_network()
        if self._zeroex_fill_watcher is not None:
            await self._zeroex_fill_watcher.stop_network()

        # Stop the transaction processing tasks.
        if self._outgoing_transactions_task is not None:
            self._outgoing_transactions_task.cancel()
            self._outgoing_transactions_task = None
        if self._check_transaction_receipts_task is not None:
            self._check_transaction_receipts_task.cancel()
            self._check_transaction_receipts_task = None

    async def check_network(self) -> NetworkStatus:
        # Assume connected if received new blocks in last 2 minutes
        if time.time() - self._last_timestamp_received_blocks < 60 * 2:
            return NetworkStatus.CONNECTED

        try:
            await self._update_gas_price()
        except asyncio.CancelledError:
            raise
        except Exception:
            return NetworkStatus.NOT_CONNECTED
        return NetworkStatus.CONNECTED

    async def _check_network_loop(self):
        while True:
            try:
                new_status = await asyncio.wait_for(self.check_network(), timeout=10.0)
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                new_status = NetworkStatus.NOT_CONNECTED
            except Exception:
                self.logger().network("Unexpected error while checking for network status.", exc_info=True,
                                      app_warning_msg="Unexpected error while checking for network status. "
                                                      "Check wallet network connection")
                new_status = NetworkStatus.NOT_CONNECTED

            self._network_status = new_status
            await asyncio.sleep(5.0)

    async def check_transaction_receipts_loop(self):
        while True:
            try:
                await self.check_transaction_receipts()

                now: float = time.time()
                next_tick: float = ((now // self.TRANSACTION_RECEIPT_POLLING_TICK + 1) *
                                    self.TRANSACTION_RECEIPT_POLLING_TICK)
                await asyncio.sleep(next_tick - now)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    "Unknown error occurred while checking for transaction receipts.", exc_info=True,
                    app_warning_msg="Unknown error occurred while checking for transaction receipts. "
                                    "Check wallet network connection")
                await asyncio.sleep(5.0)

    async def _check_transaction_receipt(self, tx_hash: str, timestamp: int):
        """
        Look for transaction receipt, only raise not found error if they are missing for longer than two minutes.
        """
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        try:
            return await async_scheduler.call_async(self._w3.eth.getTransactionReceipt, tx_hash)
        except TransactionNotFound as e:
            now: float = time.time()
            if now - timestamp > 120:
                stop_tx_hash = e.args[0].split(" ")[3]
                self._stop_tx_tracking(stop_tx_hash)
                self.logger().info(f"Stopped tracking transaction with hash: {stop_tx_hash}.")
            return None

    async def check_transaction_receipts(self):
        """
        Look for failed transactions, and emit transaction fail event if any are found.
        """
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        tasks = [self._check_transaction_receipt(tx_hash, self._pending_tx_dict[tx_hash]['timestamp'])
                 for tx_hash in self._pending_tx_dict.keys()]
        transaction_receipts: List[AttributeDict] = [tr for tr in await safe_gather(*tasks)
                                                     if (tr is not None and tr.get("blockHash") is not None)]
        block_hash_set: Set[HexBytes] = set(tr.blockHash for tr in transaction_receipts)
        fetch_block_tasks = [async_scheduler.call_async(self._w3.eth.getBlock, block_hash)
                             for block_hash in block_hash_set]
        blocks: Dict[HexBytes, AttributeDict] = dict((block.hash, block)
                                                     for block
                                                     in await safe_gather(*fetch_block_tasks)
                                                     if block is not None)

        for receipt in transaction_receipts:
            # Emit gas used event.
            tx_hash: str = receipt.transactionHash.hex()
            gas_price_wei: int = self._pending_tx_dict[tx_hash]['gas_price']
            gas_used: int = receipt.gasUsed
            gas_eth_amount_raw: int = gas_price_wei * gas_used

            if receipt.blockHash in blocks:
                block: AttributeDict = blocks[receipt.blockHash]

                if receipt.status == 0:
                    self.logger().warning(f"The transaction {tx_hash} has failed.")
                    self.trigger_event(WalletEvent.TransactionFailure, tx_hash)

                self.trigger_event(WalletEvent.GasUsed, EthereumGasUsedEvent(
                    float(block.timestamp),
                    tx_hash,
                    float(gas_price_wei * 1e-9),
                    gas_price_wei,
                    gas_used,
                    float(gas_eth_amount_raw * 1e-18),
                    gas_eth_amount_raw
                ))

                # Stop tracking the transaction.
                self._stop_tx_tracking(tx_hash)

    async def outgoing_eth_transactions_loop(self):
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        while True:
            signed_transaction: AttributeDict = await self._outgoing_transactions_queue.get()
            tx_hash: str = signed_transaction.hash.hex()
            try:
                await async_scheduler.call_async(self._w3.eth.sendRawTransaction, signed_transaction.rawTransaction)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().network(
                    f"Error sending transaction {tx_hash}.", exc_info=True,
                    app_warning_msg=f"Error sending transaction {tx_hash}. Check wallet network connection")
                self.trigger_event(WalletEvent.TransactionFailure, tx_hash)
                self._local_nonce -= 1

    def _start_tx_tracking(self, tx_hash: str, gas_price: int):
        self._pending_tx_dict[tx_hash] = {
            'gas_price': gas_price,
            'timestamp': time.time()
        }

    def _stop_tx_tracking(self, tx_hash: str):
        if tx_hash in self._pending_tx_dict:
            del self._pending_tx_dict[tx_hash]

    def schedule_eth_transaction(self, signed_transaction: AttributeDict, gas_price: int):
        if self._network_status is not NetworkStatus.CONNECTED:
            raise EnvironmentError("Cannot send transactions when network status is not connected.")

        self._outgoing_transactions_queue.put_nowait(signed_transaction)
        tx_hash: str = signed_transaction.hash.hex()
        self._start_tx_tracking(tx_hash, gas_price)
        self._local_nonce += 1

    def get_balance(self, symbol: str) -> Decimal:
        if self._account_balance_watcher is not None:
            return self._account_balance_watcher.get_balance(symbol)
        else:
            return s_decimal_0

    def get_all_balances(self) -> Dict[str, Decimal]:
        if self._account_balance_watcher is not None:
            return self._account_balance_watcher.get_all_balances()
        return {}

    def get_raw_balance(self, symbol: str) -> int:
        if self._account_balance_watcher is not None:
            return self._account_balance_watcher.get_raw_balance(symbol)
        return 0

    def get_raw_balances(self) -> Dict[str, int]:
        if self._account_balance_watcher is not None:
            return self._account_balance_watcher.get_raw_balances()
        return {}

    def sign_hash(self, text: str = None, hexstr: str = None) -> str:
        msg_hash: str = defunct_hash_message(hexstr=hexstr, text=text)
        signature_dict: AttributeDict = self._account.signHash(msg_hash)
        signature: str = signature_dict["signature"].hex()
        return signature

    def execute_transaction(self, contract_function: ContractFunction, **kwargs) -> str:
        """
        This function WILL result in immediate network calls (e.g. to get the gas price, nonce and gas cost), even
        though it is written in sync manner.

        :param contract_function:
        :param kwargs:
        :return:
        """
        if self._network_status is not NetworkStatus.CONNECTED:
            raise EnvironmentError("Cannot send transactions when network status is not connected.")

        gas_price: int = self.gas_price
        transaction_args: Dict[str, Any] = {
            "from": self.address,
            "nonce": self.nonce,
            "chainId": self.chain.value,
            "gasPrice": gas_price,
        }
        transaction_args.update(kwargs)
        transaction: Dict[str, Any] = contract_function.buildTransaction(transaction_args)
        if "gas" not in transaction:
            estimate_gas: int = 1000000
            try:
                estimate_gas = self._w3.eth.estimateGas(transaction)
            except ValueError:
                self.logger().error("Failed to estimate gas. Using default of 1000000.")
            transaction["gas"] = estimate_gas
        signed_transaction: AttributeDict = self._account.signTransaction(transaction)
        tx_hash: str = signed_transaction.hash.hex()
        self.schedule_eth_transaction(signed_transaction, gas_price)
        return tx_hash

    def send(self, address: str, asset_name: str, amount: Decimal) -> str:
        """
        Warning: This function WILL result in immediate network calls, even though it is written in sync manner.

        :param address:
        :param asset_name:
        :param amount:
        :return:
        """
        if self._network_status is not NetworkStatus.CONNECTED:
            raise EnvironmentError("Cannot send transactions when network status is not connected.")

        if asset_name == "ETH":
            gas_price: int = self.gas_price
            transaction: Dict[str, Any] = {
                "to": address,
                "value": int(amount * 1e18),
                "gas": 21000,
                "gasPrice": gas_price,
                "nonce": self.nonce,
                "chainId": self.chain.value
            }
            signed_transaction: AttributeDict = self._account.signTransaction(transaction)
            tx_hash: str = signed_transaction.hash.hex()
            self.schedule_eth_transaction(signed_transaction, gas_price)
            self.logger().info(f"Sending {amount} ETH from {self.address} to {address}. tx_hash = {tx_hash}.")
            return tx_hash
        else:
            decimals: int = self._asset_decimals[asset_name]
            proper_amount: int = int(amount * math.pow(10, decimals))
            token_contract: Contract = self.erc20_tokens[asset_name].contract
            contract_func: ContractFunction = token_contract.functions.transfer(address, proper_amount)
            tx_hash: str = self.execute_transaction(contract_func)
            self.logger().info(f"Sending {amount} {asset_name} from {self.address} to {address}. tx_hash = {tx_hash}.")
            return tx_hash

    def approve_token_transfer(self, asset_name: str, spender_address: str, amount: Decimal, **kwargs) -> str:
        if asset_name not in self.erc20_tokens:
            raise ValueError(f"{asset_name} is not a known ERC20 token to this wallet.")

        contract: Contract = self.erc20_tokens[asset_name].contract
        decimals: int = self._asset_decimals[asset_name]
        contract_func: ContractFunction = contract.functions.approve(spender_address,
                                                                     int(amount *
                                                                         Decimal(f"1e{decimals}")))
        return self.execute_transaction(contract_func, **kwargs)

    def to_nominal(self, asset_name: str, raw_amount: int) -> Decimal:
        if asset_name not in self._asset_decimals:
            raise ValueError(f"Unrecognized asset name '{asset_name}'.")

        decimals: int = self._asset_decimals[asset_name]
        return Decimal(raw_amount) * Decimal(f"1e-{decimals}")

    def to_raw(self, asset_name: str, nominal_amount: Decimal) -> int:
        if asset_name not in self._asset_decimals:
            raise ValueError(f"Unrecognized asset name '{asset_name}'.")
        decimals: int = self._asset_decimals[asset_name]
        return int(nominal_amount * Decimal(f"1e{decimals}"))

    @staticmethod
    def to_raw_static(nominal_amount: Decimal) -> int:
        return int(nominal_amount * Decimal("1e18"))

    def _received_asset_event_listener(self, received_asset_event: WalletReceivedAssetEvent):
        self.logger().info(f"Received {received_asset_event.amount_received} {received_asset_event.asset_name} at "
                           f"transaction {received_asset_event.tx_hash}.")
        self.trigger_event(WalletEvent.ReceivedAsset, received_asset_event)

    def _token_approved_event_listener(self, token_approved_event: TokenApprovedEvent):
        self.trigger_event(WalletEvent.TokenApproved, token_approved_event)

    def _eth_wrapped_event_listener(self, wrapped_eth_event: WalletWrappedEthEvent):
        self.trigger_event(WalletEvent.WrappedEth, wrapped_eth_event)

    def _eth_unwrapped_event_listener(self, unwrapped_eth_event: WalletUnwrappedEthEvent):
        self.trigger_event(WalletEvent.UnwrappedEth, unwrapped_eth_event)

    def _zeroex_fill_event_listener(self, zeroex_fill_event: ZeroExFillEvent):
        self.logger().info(f"ZeroEx order {zeroex_fill_event.order_hash} was filled at "
                           f"transaction {zeroex_fill_event.tx_hash}.")
        self.trigger_event(ZeroExEvent.Fill, zeroex_fill_event)

    async def check_and_fix_approval_amounts(self, spender: str) -> List[str]:
        """
        Maintain the approve amounts for a token.
        This function will be used to ensure trade execution using exchange protocols such as 0x, but should be
        defined in child classes

        Allowance amounts to manage:
         1. Allow external contract to pull tokens from local wallet
        """
        min_approve_amount: int = int(Decimal("1e35"))
        target_approve_amount: int = int(Decimal("1e36"))
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()

        # Get currently approved amounts
        get_approved_amounts_tasks: List[Coroutine] = [
            async_scheduler.call_async(erc20_token.contract.functions.allowance(self.address, spender).call)
            for erc20_token in self._erc20_token_list
        ]
        approved_amounts: List[int] = await safe_gather(*get_approved_amounts_tasks)

        # Check and fix the approved amounts
        tx_hashes: List[str] = []
        for approved_amount, erc20_token in zip(approved_amounts, self._erc20_token_list):
            token_name: str = await erc20_token.get_name()
            token_contract: Contract = erc20_token.contract
            if approved_amount >= min_approve_amount:
                self.logger().info(f"Approval already exists for {token_name} from wallet address {self.address}.")
                continue
            self.logger().info(f"Approving spender for drawing {token_name} from wallet address {self.address}.")
            tx_hash: str = self.execute_transaction(token_contract.functions.approve(
                spender,
                target_approve_amount
            ))
            tx_hashes.append(tx_hash)
        return tx_hashes

    def wrap_eth(self, amount: Decimal) -> str:
        if self._weth_token is None:
            raise EnvironmentError("No WETH token address was used to initialize this wallet.")

        contract_func = self._weth_token.contract.functions.deposit()
        self.logger().info(f"Wrapping {amount} ether from wallet address {self.address}.")
        return self.execute_transaction(contract_func, value=self.to_raw_static(amount))

    def unwrap_eth(self, amount: Decimal) -> str:
        if self._weth_token is None:
            raise EnvironmentError("No WETH token address was used to initialize this wallet.")

        contract_func = self._weth_token.contract.functions.withdraw(self.to_raw_static(amount))
        self.logger().info(f"Unwrapping {amount} ether from wallet address {self.address}.")
        return self.execute_transaction(contract_func)

    def _did_receive_new_blocks(self, new_blocks: List[AttributeDict]):
        self._last_timestamp_received_blocks = time.time()
        safe_ensure_future(self._update_gas_price())

    async def _update_gas_price(self):
        async_scheduler: AsyncCallScheduler = AsyncCallScheduler.shared_instance()
        new_gas_price: int = await async_scheduler.call_async(getattr, self._w3.eth, "gasPrice")
        self._gas_price = new_gas_price

    def get_remote_nonce(self):
        try:
            remote_nonce = self._w3.eth.getTransactionCount(self.address, block_identifier="pending")
            return remote_nonce
        except BlockNotFound:
            return None
