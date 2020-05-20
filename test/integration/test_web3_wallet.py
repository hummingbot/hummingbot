#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
from typing import (
    Optional,
    List
)
import time
import unittest
from web3.eth import Contract
from web3 import Web3

import conf
from hummingbot.core.clock import (
    Clock,
    ClockMode
)
from hummingbot.core.event.events import (
    WalletEvent,
    WalletReceivedAssetEvent,
    TokenApprovedEvent,
    EthereumGasUsedEvent,
)
from hummingbot.wallet.ethereum.erc20_token import ERC20Token
from hummingbot.wallet.ethereum.web3_wallet import Web3Wallet
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)


class Web3WalletUnitTest(unittest.TestCase):
    wallet_a: Optional[Web3Wallet] = None
    wallet_b: Optional[Web3Wallet] = None
    erc20_token: Optional[ERC20Token] = None
    events: List[WalletEvent] = [
        WalletEvent.ReceivedAsset,
        WalletEvent.GasUsed,
        WalletEvent.TokenApproved,
        WalletEvent.TransactionFailure
    ]

    logger_a: EventLogger
    logger_b: EventLogger

    @classmethod
    def setUpClass(cls):
        cls.clock: Clock = Clock(ClockMode.REALTIME)
        cls.erc20_token_address = conf.test_erc20_token_address
        cls.w3 = Web3(Web3.HTTPProvider(conf.test_web3_provider_list[0]))

        cls.wallet_a = Web3Wallet(
            conf.web3_test_private_key_a, conf.test_web3_provider_list, [cls.erc20_token_address])
        cls.wallet_b = Web3Wallet(
            conf.web3_test_private_key_b, conf.test_web3_provider_list, [cls.erc20_token_address])

        cls.erc20_token: ERC20Token = list(cls.wallet_a.current_backend.erc20_tokens.values())[0]

        cls.clock.add_iterator(cls.wallet_a)
        cls.clock.add_iterator(cls.wallet_b)
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()

        next_iteration = (time.time() // 5.0 + 1) * 5
        cls.ev_loop.run_until_complete(cls.clock.run_til(next_iteration))

    def setUp(self):
        self.logger_a = EventLogger()
        self.logger_b = EventLogger()
        for event_tag in self.events:
            self.wallet_a.add_listener(event_tag, self.logger_a)
            self.wallet_b.add_listener(event_tag, self.logger_b)

    def tearDown(self):
        for event_tag in self.events:
            self.wallet_a.remove_listener(event_tag, self.logger_a)
            self.wallet_b.remove_listener(event_tag, self.logger_b)
        self.logger_a = None
        self.logger_b = None

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            now = time.time()
            next_iteration = now // 1.0 + 1
            await self.clock.run_til(next_iteration)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def test_send_balances(self):
        # Check the initial conditions. There should be a certain number of initial tokens before the test can be
        # carried out.
        self.assertGreater(self.wallet_a.get_balance("ETH"), 1.0)
        self.assertGreater(self.wallet_b.get_balance("ETH"), 1.0)
        self.assertGreater(self.wallet_a.get_balance("BNB"), 0.1)
        self.assertGreater(self.wallet_b.get_balance("BNB"), 0.1)

        # Send some Ether between wallets.
        eth_tx_hash: str = self.wallet_a.send(self.wallet_b.address, "ETH", 0.1)
        bnb_tx_hash: str = self.wallet_b.send(self.wallet_a.address, "BNB", 0.01)
        bnb_asset_received, eth_asset_received, eth_gas_used, bnb_gas_used = self.run_parallel(
            self.logger_a.wait_for(WalletReceivedAssetEvent),
            self.logger_b.wait_for(WalletReceivedAssetEvent),
            self.logger_a.wait_for(EthereumGasUsedEvent),
            self.logger_b.wait_for(EthereumGasUsedEvent)
        )
        eth_asset_received: WalletReceivedAssetEvent = eth_asset_received
        eth_gas_used: EthereumGasUsedEvent = eth_gas_used
        self.assertEqual(eth_tx_hash, eth_asset_received.tx_hash)
        self.assertEqual(self.wallet_a.address, eth_asset_received.from_address)
        self.assertEqual(self.wallet_b.address, eth_asset_received.to_address)
        self.assertEqual("ETH", eth_asset_received.asset_name)
        self.assertEqual(0.1, eth_asset_received.amount_received)
        self.assertEqual(int(1e17), eth_asset_received.raw_amount_received)
        self.assertEqual(eth_tx_hash, eth_gas_used.tx_hash)
        self.assertEqual(21000, eth_gas_used.gas_used)

        bnb_asset_received: WalletReceivedAssetEvent = bnb_asset_received
        bnb_gas_used: EthereumGasUsedEvent = bnb_gas_used
        self.assertEqual(bnb_tx_hash, bnb_asset_received.tx_hash)
        self.assertEqual(self.wallet_b.address, bnb_asset_received.from_address)
        self.assertEqual(self.wallet_a.address, bnb_asset_received.to_address)
        self.assertEqual("BNB", bnb_asset_received.asset_name)
        self.assertEqual(0.01, bnb_asset_received.amount_received)
        self.assertEqual(int(1e16), bnb_asset_received.raw_amount_received)
        self.assertEqual(bnb_tx_hash, bnb_gas_used.tx_hash)
        self.assertTrue(bnb_gas_used.gas_used > 21000)

        # Send out the reverse transactions.
        self.wallet_b.send(self.wallet_a.address, "ETH", 0.1)
        self.wallet_a.send(self.wallet_b.address, "BNB", 0.01)

    def test_transaction_failure(self):
        # Produce a transfer failure, by not transferring more than the account has.
        erc20_token_contract: Contract = self.erc20_token.contract
        failure_hash: str = self.wallet_a.execute_transaction(
            erc20_token_contract.functions.transfer(self.wallet_b.address, int(1e30)), gas=500000
        )
        failure_tx, gas_used_event = self.run_parallel(
            self.logger_a.wait_for(str),
            self.logger_a.wait_for(EthereumGasUsedEvent)
        )
        failure_tx: str = failure_tx
        gas_used_event: EthereumGasUsedEvent = gas_used_event
        self.assertEqual(failure_hash, failure_tx)
        self.assertGreater(gas_used_event.gas_used, 21000)

    def test_token_approval(self):
        approval_hash: str = self.wallet_a.approve_token_transfer(self.erc20_token.symbol, self.wallet_b.address, 1.0)
        approval_event, gas_used_event = self.run_parallel(
            self.logger_a.wait_for(TokenApprovedEvent),
            self.logger_a.wait_for(EthereumGasUsedEvent)
        )
        approval_event: TokenApprovedEvent = approval_event
        gas_used_event: EthereumGasUsedEvent = gas_used_event
        self.assertEqual(approval_hash, approval_event.tx_hash)
        self.assertEqual(approval_hash, gas_used_event.tx_hash)
        self.assertEqual(self.wallet_a.address, approval_event.owner_address)
        self.assertEqual(self.wallet_b.address, approval_event.spender_address)
        self.assertEqual(self.erc20_token.symbol, approval_event.asset_name)
        self.assertEqual(1.0, approval_event.amount)
        self.assertEqual(int(1e18), approval_event.raw_amount)

        self.wallet_a.approve_token_transfer(self.erc20_token.symbol, self.wallet_b.address, 0.0)
        self.run_parallel(
            self.logger_a.wait_for(TokenApprovedEvent),
            self.logger_a.wait_for(EthereumGasUsedEvent)
        )


if __name__ == "__main__":
    unittest.main()
