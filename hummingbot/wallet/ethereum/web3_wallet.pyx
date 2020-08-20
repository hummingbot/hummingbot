import asyncio
from collections import OrderedDict
import itertools
from eth_account import Account
import logging
import time
from typing import List, Dict
from web3.contract import (
    ContractFunction
)

from hummingbot.core.clock import Clock, ClockMode
from hummingbot.core.clock cimport Clock
from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.events import (
    WalletEvent,
    ZeroExEvent
)
from decimal import Decimal
from hummingbot.wallet.ethereum.ethereum_chain import EthereumChain
from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.pubsub cimport PubSub
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.wallet.wallet_base import WalletBase
from hummingbot.wallet.ethereum.erc20_token import ERC20Token
from hummingbot.wallet.ethereum.web3_wallet_backend import Web3WalletBackend

class_logger = None


cdef class Web3WalletBackendEventForwarder(EventListener):
    cdef:
        Web3Wallet _owner
        int64_t _event_tag

    def __init__(self, owner: Web3Wallet, event_tag: int):
        super().__init__()
        self._owner = owner
        self._event_tag = event_tag

    @property
    def event_tag(self) -> int:
        return self._event_tag

    cdef c_call(self, object arg):
        self._owner.c_receive_forwarded_event(self._event_tag, arg)


cdef class Web3Wallet(WalletBase):
    BACKEND_SELECTION_INTERVAL = 15.0
    WALLET_EVENT_DEDUP_WINDOW_SIZE = 1024

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global class_logger
        if class_logger is None:
            class_logger = logging.getLogger(__name__)
        return class_logger

    def __init__(self,
                 private_key: any,
                 backend_urls: List[str],
                 erc20_token_addresses: List[str],
                 chain: EthereumChain = EthereumChain.ROPSTEN):
        super().__init__()

        self._local_account = Account.privateKeyToAccount(private_key)
        self._wallet_backends = [Web3WalletBackend(private_key, url, erc20_token_addresses, chain=chain)
                                 for url in backend_urls]
        self._best_backend = self._wallet_backends[0]
        self._last_backend_network_states = [NetworkStatus.STOPPED] * len(self._wallet_backends)

        self._select_best_backend_task = None
        self._chain = chain
        self._event_dedup_window = OrderedDict()

        self._received_asset_forwarder = Web3WalletBackendEventForwarder(
            self, WalletEvent.ReceivedAsset.value
        )
        self._gas_used_forwarder = Web3WalletBackendEventForwarder(
            self, WalletEvent.GasUsed.value
        )
        self._token_approved_forwarder = Web3WalletBackendEventForwarder(
            self, WalletEvent.TokenApproved.value
        )
        self._eth_wrapped_forwarder = Web3WalletBackendEventForwarder(
            self, WalletEvent.WrappedEth.value
        )
        self._eth_unwrapped_forwarder = Web3WalletBackendEventForwarder(
            self, WalletEvent.UnwrappedEth.value
        )
        self._token_approved_forwarder = Web3WalletBackendEventForwarder(
            self, WalletEvent.TokenApproved.value
        )
        self._transaction_failure_forwarder = Web3WalletBackendEventForwarder(
            self, WalletEvent.TransactionFailure.value
        )
        self._zeroex_fill_forwarder = Web3WalletBackendEventForwarder(
            self, ZeroExEvent.Fill.value
        )

        # The check network operation can be done more frequently since it's only an indirect check.
        self.check_network_interval = 2.0

    @property
    def erc20_tokens(self) -> Dict[str, ERC20Token]:
        return self._best_backend._erc20_tokens

    @property
    def address(self) -> str:
        return self._local_account.address

    @property
    def private_key(self) -> str:
        return self._local_account.privateKey.hex()

    @property
    def block_number(self) -> int:
        return self._best_backend.block_number

    @property
    def chain(self) -> EthereumChain:
        return self._chain

    @property
    def gas_price(self) -> int:
        return self._best_backend.gas_price

    @property
    def current_backend(self) -> Web3WalletBackend:
        return self._best_backend

    def get_all_balances(self) -> Dict[str, Decimal]:
        return self._best_backend.get_all_balances()

    def get_raw_balances(self) -> Dict[str, int]:
        return self._best_backend.get_raw_balances()

    async def _select_best_backend_loop(self):
        cdef:
            double next_iteration_timestamp
            double now
            list block_numbers
            int max_index

        while True:
            current_block_number = self._best_backend.block_number
            block_numbers = [backend.block_number for backend in self._wallet_backends]
            max_index = max(range(len(block_numbers)), key=block_numbers.__getitem__)

            # Allow some leniency in selecting wallet backends, since +1 differences due to small network delays
            # between nodes aren't really meaningful.
            if block_numbers[max_index] > current_block_number + 1:
                self._best_backend = self._wallet_backends[max_index]

            # Wait for the next iteration
            now = time.time()
            next_iteration_timestamp = (int(now / self.BACKEND_SELECTION_INTERVAL) + 1) * \
                self.BACKEND_SELECTION_INTERVAL
            await asyncio.sleep(next_iteration_timestamp - now)

    def approve_token_transfer(self, asset_name: str, spender_address: str, amount: float, **kwargs) -> str:
        return self._best_backend.approve_token_transfer(asset_name, spender_address, amount, **kwargs)

    def wrap_eth(self, amount: Decimal) -> str:
        return self._best_backend.wrap_eth(amount)

    def unwrap_eth(self, amount: Decimal) -> str:
        return self._best_backend.unwrap_eth(amount)

    def execute_transaction(self, contract_function: ContractFunction, **kwargs) -> str:
        return self._best_backend.execute_transaction(contract_function, **kwargs)

    def to_nominal(self, asset_name: str, raw_amount: int) -> Decimal:
        return self._best_backend.to_nominal(asset_name, raw_amount)

    def to_raw(self, asset_name: str, nominal_amount: Decimal) -> int:
        return self._best_backend.to_raw(asset_name, nominal_amount)

    async def start_network(self):
        self._select_best_backend_task = safe_ensure_future(self._select_best_backend_loop())

        all_forwarders = [
            self._received_asset_forwarder,
            self._gas_used_forwarder,
            self._token_approved_forwarder,
            self._eth_wrapped_forwarder,
            self._eth_unwrapped_forwarder,
            self._transaction_failure_forwarder,
            self._zeroex_fill_forwarder
        ]
        for backend, event_forwarder in itertools.product(self._wallet_backends, all_forwarders):
            event_tag = event_forwarder.event_tag
            (<PubSub>backend).c_add_listener(event_tag, event_forwarder)

    async def stop_network(self):
        if self._select_best_backend_task is not None:
            self._select_best_backend_task.cancel()
            self._select_best_backend_task = None

        all_forwarders = [
            self._received_asset_forwarder,
            self._gas_used_forwarder,
            self._token_approved_forwarder,
            self._eth_wrapped_forwarder,
            self._eth_unwrapped_forwarder,
            self._transaction_failure_forwarder,
            self._zeroex_fill_forwarder
        ]
        for backend, event_forwarder in itertools.product(self._wallet_backends, all_forwarders):
            event_tag = event_forwarder.event_tag
            (<PubSub>backend).c_remove_listener(event_tag, event_forwarder)

    async def check_network(self) -> NetworkStatus:
        new_backend_network_states = [backend.network_status for backend in self._wallet_backends]

        for backend, last_state, new_state in zip(
                self._wallet_backends,
                self._last_backend_network_states,
                new_backend_network_states):
            if last_state != new_state:
                if new_state is NetworkStatus.CONNECTED:
                    await backend.start_network()
                elif new_state is NetworkStatus.NOT_CONNECTED:
                    await backend.stop_network()

        self._last_backend_network_states = new_backend_network_states

        return (NetworkStatus.CONNECTED
                if any([s is NetworkStatus.CONNECTED for s in new_backend_network_states])
                else NetworkStatus.NOT_CONNECTED)

    cdef c_start(self, Clock clock, double timestamp):
        WalletBase.c_start(self, clock, timestamp)
        if clock.clock_mode is not ClockMode.REALTIME:
            raise EnvironmentError("Web3 wallet can only run in real time mode. Do not use this for back-testing.")
        for backend in self._wallet_backends:
            backend.start()

    cdef c_stop(self, Clock clock):
        WalletBase.c_stop(self, clock)
        for backend in self._wallet_backends:
            backend.stop()

    cdef str c_send(self, str address, str asset_name, object amount):
        return self._best_backend.send(address, asset_name, amount)

    cdef object c_get_balance(self, str asset_name):
        return self._best_backend.get_balance(asset_name)

    cdef object c_get_raw_balance(self, str asset_name):
        return self._best_backend.get_raw_balance(asset_name)

    cdef c_receive_forwarded_event(self, int64_t event_tag, object args):
        event_key = (event_tag, args if isinstance(args, str) else args.tx_hash)
        if event_key in self._event_dedup_window:
            # This is a duplicate event. Ignore.
            return
        self.c_trigger_event(event_tag, args)
        self._event_dedup_window[event_key] = 1
        while len(self._event_dedup_window) > self.WALLET_EVENT_DEDUP_WINDOW_SIZE:
            self._event_dedup_window.popitem(last=False)
