import pytest
import asyncio
from dataclasses import (
    dataclass,
)
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Generator,
    List,
    Tuple,
    Union,
    cast,
)

from eth_typing import (
    ChecksumAddress,
    HexStr,
)
from eth_utils import (
    is_hexstr,
)
from hexbytes import (
    HexBytes,
)

from web3 import (
    AsyncWeb3,
    PersistentConnectionProvider,
)
from web3.beacon import (
    AsyncBeacon,
)
from web3.datastructures import (
    AttributeDict,
)
from web3.middleware import (
    ExtraDataToPOAMiddleware,
)
from web3.types import (
    BlockData,
    FormattedEthSubscriptionResponse,
    LogReceipt,
    Nonce,
    RPCEndpoint,
    TxData,
    Wei,
)
from web3.utils import (
    EthSubscription,
)
from web3.utils.subscriptions import (
    LogsSubscription,
    LogsSubscriptionContext,
    NewHeadsSubscription,
    NewHeadsSubscriptionContext,
    PendingTxSubscription,
    PendingTxSubscriptionContext,
)

if TYPE_CHECKING:
    from web3.contract.async_contract import (
        AsyncContract,
        AsyncContractFunction,
    )
    from web3.providers.persistent.subscription_manager import (
        SubscriptionContainer,
    )


# LogIndexedAndNotIndexed event args
INDEXED_ADDR = "0xdEad000000000000000000000000000000000000"
INDEXED_UINT256 = 1337
NON_INDEXED_ADDR = "0xbeeF000000000000000000000000000000000000"
NON_INDEXED_UINT256 = 1999
NON_INDEXED_STRING = "test logs subscriptions"

SOME_BLOCK_KEYS = [
    "number",
    "hash",
    "parentHash",
    "transactionsRoot",
    "stateRoot",
    "receiptsRoot",
    "gasLimit",
    "gasUsed",
    "timestamp",
    "baseFeePerGas",
    "withdrawalsRoot",
]


@dataclass
class SubscriptionHandlerTest:
    passed: bool = False


async def new_heads_handler(
    handler_context: NewHeadsSubscriptionContext,
) -> None:
    w3 = handler_context.async_w3
    sub = handler_context.subscription
    assert isinstance(w3, AsyncWeb3)
    provider = cast(PersistentConnectionProvider, w3.provider)
    assert isinstance(provider.get_endpoint_uri_or_ipc_path(), str)

    assert isinstance(sub, EthSubscription)

    block = handler_context.result
    assert block is not None
    assert all(k in block.keys() for k in SOME_BLOCK_KEYS)

    assert handler_context.new_heads_handler_test.passed is False
    handler_context.new_heads_handler_test.passed = True
    assert await sub.unsubscribe()


async def pending_tx_handler(
    handler_context: PendingTxSubscriptionContext,
) -> None:
    w3 = handler_context.async_w3
    sub = handler_context.subscription
    tx = handler_context.result

    assert w3 is not None
    provider = cast(PersistentConnectionProvider, w3.provider)
    assert isinstance(provider.get_endpoint_uri_or_ipc_path(), str)

    assert isinstance(sub, PendingTxSubscription)

    assert tx is not None
    tx = cast(TxData, tx)
    accts = await w3.eth.accounts
    assert tx["from"] == accts[0]
    await w3.eth.wait_for_transaction_receipt(tx["hash"])

    assert handler_context.pending_tx_handler_test.passed is False
    handler_context.pending_tx_handler_test.passed = True
    assert await sub.unsubscribe()


async def logs_handler(
    handler_context: LogsSubscriptionContext,
) -> None:
    w3 = handler_context.async_w3
    sub = handler_context.subscription
    log_receipt = handler_context.result

    assert w3 is not None
    provider = cast(PersistentConnectionProvider, w3.provider)
    assert isinstance(provider.get_endpoint_uri_or_ipc_path(), str)

    assert isinstance(sub, LogsSubscription)
    event_data = handler_context.event.process_log(log_receipt)
    assert event_data.args.indexedAddress == INDEXED_ADDR
    assert event_data.args.indexedUint256 == INDEXED_UINT256
    assert event_data.args.nonIndexedAddress == NON_INDEXED_ADDR
    assert event_data.args.nonIndexedUint256 == NON_INDEXED_UINT256
    assert event_data.args.nonIndexedString == NON_INDEXED_STRING

    assert handler_context.logs_handler_test.passed is False
    handler_context.logs_handler_test.passed = True
    assert await sub.unsubscribe()


async def idle_handler(
    _handler_context: Any,
) -> None:
    pass


async def emit_contract_event(
    async_w3: AsyncWeb3,
    acct: ChecksumAddress,
    contract_function: "AsyncContractFunction",
    args: Any = (),
    delay: float = 0.25,
) -> None:
    await asyncio.sleep(delay)
    tx_hash = await contract_function(*args).transact({"from": acct})
    receipt = await async_w3.eth.wait_for_transaction_receipt(tx_hash)
    assert receipt["status"] == 1


async def log_indexed_and_non_indexed_args_task(
    async_w3: AsyncWeb3,
    async_emitter_contract: "AsyncContract",
    acct: ChecksumAddress,
    delay: float = 0.1,
) -> "asyncio.Task[None]":
    return asyncio.create_task(
        emit_contract_event(
            async_w3,
            acct,
            async_emitter_contract.functions.logIndexedAndNotIndexedArgs,
            args=(
                INDEXED_ADDR,
                INDEXED_UINT256,
                NON_INDEXED_ADDR,
                NON_INDEXED_UINT256,
                NON_INDEXED_STRING,
            ),
            delay=delay,
        )
    )


def assert_no_subscriptions_left(sub_container: "SubscriptionContainer") -> None:
    assert len(sub_container) == 0
    assert len(sub_container.subscriptions) == 0
    assert len(sub_container.subscriptions_by_id) == 0
    assert len(sub_container.subscriptions_by_label) == 0
    assert len(sub_container.handler_subscriptions) == 0


async def clean_up_task(task: "asyncio.Task[Any]") -> None:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class PersistentConnectionProviderTest:
    @pytest.fixture(autouse=True)
    def clear_caches(self, async_w3: AsyncWeb3) -> Generator[None, None, None]:
        yield
        async_w3.provider._request_processor.clear_caches()
        async_w3.subscription_manager.total_handler_calls = 0

    @staticmethod
    async def seed_transactions_to_geth(
        async_w3: AsyncWeb3,
        acct: ChecksumAddress,
        num_txs: int = 1,
        delay: float = 0.1,
    ) -> None:
        nonce = int(await async_w3.eth.get_transaction_count(acct))

        async def send_tx() -> None:
            nonlocal nonce
            await async_w3.eth.send_transaction(
                {
                    "from": acct,
                    "to": acct,
                    "value": Wei(nonce),
                    "gas": 21000,
                    "nonce": Nonce(nonce),
                }
            )
            nonce += 1

        for _ in range(num_txs):
            await asyncio.sleep(delay)
            await send_tx()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "subscription_params,ws_subscription_response,expected_formatted_result",
        (
            (
                ("syncing",),
                {
                    "jsonrpc": "2.0",
                    "method": "eth_subscription",
                    "params": {
                        "subscription": "THIS_WILL_BE_REPLACED_IN_THE_TEST",
                        "result": False,
                    },
                },
                False,
            ),
            (
                ("syncing",),
                {
                    "jsonrpc": "2.0",
                    "method": "eth_subscription",
                    "params": {
                        "subscription": "THIS_WILL_BE_REPLACED_IN_THE_TEST",
                        "result": {
                            "isSyncing": True,
                            "startingBlock": "0x0",
                            "currentBlock": "0x4346fe",
                            "highestBlock": "0x434806",
                        },
                    },
                },
                AttributeDict(
                    {
                        "isSyncing": True,
                        "startingBlock": 0,
                        "currentBlock": 4409086,
                        "highestBlock": 4409350,
                    }
                ),
            ),
        ),
        ids=[
            "syncing-False",
            "syncing-True",
        ],
    )
    async def test_async_eth_subscribe_syncing_mocked(
        self,
        async_w3: AsyncWeb3,
        subscription_params: Tuple[Any, ...],
        ws_subscription_response: Dict[str, Any],
        expected_formatted_result: Any,
    ) -> None:
        sub_id = await async_w3.eth.subscribe(*subscription_params)
        assert is_hexstr(sub_id)

        # stub out the subscription id so we know how to process the response
        ws_subscription_response["params"]["subscription"] = sub_id

        # add the response to the subscription response cache as if it came from the
        # websocket connection
        await async_w3.provider._request_processor.cache_raw_response(
            ws_subscription_response, subscription=True
        )

        async for msg in async_w3.socket.process_subscriptions():
            response = cast(FormattedEthSubscriptionResponse, msg)
            assert response["subscription"] == sub_id
            assert response["result"] == expected_formatted_result

            # only testing one message, so break here
            await async_w3.eth.unsubscribe(sub_id)
            break

        assert_no_subscriptions_left(
            async_w3.subscription_manager._subscription_container
        )

    @pytest.mark.asyncio
    async def test_async_eth_subscribe_new_heads(self, async_w3: AsyncWeb3) -> None:
        sub_id = await async_w3.eth.subscribe("newHeads")
        assert is_hexstr(sub_id)

        async for msg in async_w3.socket.process_subscriptions():
            response = cast(FormattedEthSubscriptionResponse, msg)
            assert response["subscription"] == sub_id
            result = cast(BlockData, response["result"])
            assert all(k in result.keys() for k in SOME_BLOCK_KEYS)
            break

        assert await async_w3.eth.unsubscribe(sub_id)
        assert_no_subscriptions_left(
            async_w3.subscription_manager._subscription_container
        )

    @pytest.mark.asyncio
    async def test_async_eth_subscribe_creates_and_handles_new_heads_subscription_type(
        self,
        async_w3: AsyncWeb3,
    ) -> None:
        sub_manager = async_w3.subscription_manager
        new_heads_handler_test = SubscriptionHandlerTest()

        sub_id = await async_w3.eth.subscribe(
            "newHeads",
            handler=new_heads_handler,
            handler_context={"new_heads_handler_test": new_heads_handler_test},
        )
        assert is_hexstr(sub_id)

        assert len(sub_manager.subscriptions) == 1
        sub = sub_manager.subscriptions[0]
        assert isinstance(sub, NewHeadsSubscription)

        await sub_manager.handle_subscriptions()

        assert new_heads_handler_test.passed
        assert len(sub_manager.subscriptions) == 0

        assert sub_manager.total_handler_calls == 1
        assert sub.handler_call_count == 1

    @pytest.mark.asyncio
    async def test_async_eth_subscribe_process_pending_tx_true(
        self,
        async_w3: AsyncWeb3,
    ) -> None:
        sub_id = await async_w3.eth.subscribe("newPendingTransactions", True)
        assert is_hexstr(sub_id)

        accts = await async_w3.eth.accounts
        acct = accts[0]

        num_txs = 2
        original_nonce = await async_w3.eth.get_transaction_count(acct)
        tx_seeder_task = asyncio.create_task(
            self.seed_transactions_to_geth(async_w3, acct, num_txs=num_txs)
        )

        nonce = int(original_nonce)
        tx_hash = None
        async for msg in async_w3.socket.process_subscriptions():
            response = cast(FormattedEthSubscriptionResponse, msg)
            assert response["subscription"] == sub_id
            result = cast(TxData, response["result"])
            assert result["gas"] == 21000
            assert result["from"] == acct
            assert result["to"] == acct
            assert int(result["value"]) == int(nonce)
            tx_hash = result["hash"]
            assert tx_hash is not None

            nonce += 1
            if nonce == int(original_nonce) + num_txs:
                break

        # cleanup
        assert await async_w3.eth.unsubscribe(sub_id)
        assert_no_subscriptions_left(
            async_w3.subscription_manager._subscription_container
        )
        async_w3.provider._request_processor.clear_caches()
        await async_w3.eth.wait_for_transaction_receipt(tx_hash)
        await clean_up_task(tx_seeder_task)

    @pytest.mark.asyncio
    async def test_async_eth_subscribe_and_process_pending_tx_false(
        self,
        async_w3: AsyncWeb3,
    ) -> None:
        sub_id = await async_w3.eth.subscribe("newPendingTransactions")
        assert is_hexstr(sub_id)

        accts = await async_w3.eth.accounts
        acct = accts[0]
        await async_w3.eth.get_transaction_count(acct)

        num_txs = 2
        tx_seeder_task = asyncio.create_task(
            self.seed_transactions_to_geth(async_w3, acct, num_txs=num_txs)
        )

        tx_hash = None
        i = 0
        async for msg in async_w3.socket.process_subscriptions():
            response = cast(FormattedEthSubscriptionResponse, msg)
            assert response["subscription"] == sub_id
            assert isinstance(response["result"], HexBytes)
            tx_hash = response["result"]

            i += 1
            if i == num_txs:
                break

        # cleanup
        await async_w3.eth.unsubscribe(sub_id)
        assert_no_subscriptions_left(
            async_w3.subscription_manager._subscription_container
        )
        await async_w3.eth.wait_for_transaction_receipt(tx_hash)
        await clean_up_task(tx_seeder_task)

    @pytest.mark.asyncio
    async def test_async_eth_subscribe_creates_and_handles_pending_tx_subscription_type(
        self,
        async_w3: AsyncWeb3,
    ) -> None:
        sub_manager = async_w3.subscription_manager
        pending_tx_handler_test = SubscriptionHandlerTest()

        sub_id = await async_w3.eth.subscribe(
            "newPendingTransactions",
            True,
            handler=pending_tx_handler,
            handler_context={"pending_tx_handler_test": pending_tx_handler_test},
        )
        assert is_hexstr(sub_id)

        assert len(sub_manager.subscriptions) == 1
        sub = sub_manager.subscriptions[0]
        assert isinstance(sub, PendingTxSubscription)

        # seed transactions to geth
        accts = await async_w3.eth.accounts
        acct = accts[0]
        tx_seeder_task = asyncio.create_task(
            self.seed_transactions_to_geth(async_w3, acct)
        )
        await sub_manager.handle_subscriptions()

        assert pending_tx_handler_test.passed
        assert len(sub_manager.subscriptions) == 0

        assert sub_manager.total_handler_calls == 1
        assert sub.handler_call_count == 1

        # cleanup
        sub_manager.total_handler_calls = 0
        await clean_up_task(tx_seeder_task)

    @pytest.mark.asyncio
    async def test_async_eth_subscribe_and_process_logs(
        self, async_w3: AsyncWeb3, async_emitter_contract: "AsyncContract"
    ) -> None:
        event = async_emitter_contract.events.LogIndexedAndNotIndexed
        event_topic = async_w3.keccak(text=event.abi_element_identifier).to_0x_hex()

        sub_id = await async_w3.eth.subscribe(
            "logs",
            {
                "address": async_emitter_contract.address,
                "topics": [HexStr(event_topic)],
            },
        )
        assert is_hexstr(sub_id)

        accts = await async_w3.eth.accounts
        acct = accts[0]
        emit_event_task = await log_indexed_and_non_indexed_args_task(
            async_w3, async_emitter_contract, acct
        )

        async for msg in async_w3.socket.process_subscriptions():
            response = cast(FormattedEthSubscriptionResponse, msg)
            assert response["subscription"] == sub_id
            log_receipt = cast(LogReceipt, response["result"])
            event_data = event.process_log(log_receipt)
            assert event_data.args.indexedAddress == INDEXED_ADDR
            assert event_data.args.indexedUint256 == INDEXED_UINT256
            assert event_data.args.nonIndexedAddress == NON_INDEXED_ADDR
            assert event_data.args.nonIndexedUint256 == NON_INDEXED_UINT256
            assert event_data.args.nonIndexedString == NON_INDEXED_STRING
            break

        assert await async_w3.eth.unsubscribe(sub_id)
        assert len(async_w3.subscription_manager.subscriptions) == 0
        await clean_up_task(emit_event_task)

    @pytest.mark.asyncio
    async def test_async_eth_subscribe_creates_and_handles_logs_subscription_type(
        self,
        async_w3: AsyncWeb3,
        async_emitter_contract: "AsyncContract",
    ) -> None:
        sub_manager = async_w3.subscription_manager

        event = async_emitter_contract.events.LogIndexedAndNotIndexed

        logs_handler_test = SubscriptionHandlerTest()
        sub_id = await async_w3.eth.subscribe(
            "logs",
            {
                "address": async_emitter_contract.address,
                "topics": [event.topic],
            },
            handler=logs_handler,
            handler_context={
                "logs_handler_test": logs_handler_test,
                "event": event,
            },
        )
        assert is_hexstr(sub_id)

        assert len(sub_manager.subscriptions) == 1
        sub = sub_manager.subscriptions[0]
        assert isinstance(sub, LogsSubscription)

        accts = await async_w3.eth.accounts
        acct = accts[0]
        emit_event_task = await log_indexed_and_non_indexed_args_task(
            async_w3, async_emitter_contract, acct
        )

        await sub_manager.handle_subscriptions()

        assert logs_handler_test.passed
        assert len(sub_manager.subscriptions) == 0

        assert sub_manager.total_handler_calls == 1
        assert sub.handler_call_count == 1

        # cleanup
        sub_manager.total_handler_calls = 0
        await clean_up_task(emit_event_task)

    @pytest.mark.asyncio
    async def test_async_extradata_poa_middleware_on_eth_subscription(
        self,
        async_w3: AsyncWeb3,
    ) -> None:
        async_w3.middleware_onion.inject(
            ExtraDataToPOAMiddleware, "poa_middleware", layer=0
        )

        sub_id = await async_w3.eth.subscribe("newHeads")
        assert is_hexstr(sub_id)

        # add the response to the subscription response cache as if it came from the
        # websocket connection
        await async_w3.provider._request_processor.cache_raw_response(
            {
                "jsonrpc": "2.0",
                "method": "eth_subscription",
                "params": {
                    "subscription": sub_id,
                    "result": {
                        "extraData": f"0x{'00' * 100}",
                    },
                },
            },
            subscription=True,
        )

        async for msg in async_w3.socket.process_subscriptions():
            response = cast(FormattedEthSubscriptionResponse, msg)
            assert response.keys() == {"subscription", "result"}
            assert response["subscription"] == sub_id
            assert response["result"]["proofOfAuthorityData"] == HexBytes(  # type: ignore  # noqa: E501
                f"0x{'00' * 100}"
            )

            # only testing one message, so break here
            break

        # clean up
        assert await async_w3.eth.unsubscribe(sub_id)
        async_w3.middleware_onion.remove("poa_middleware")

    @pytest.mark.asyncio
    async def test_asyncio_gather_for_multiple_requests_matches_the_responses(
        self,
        async_w3: AsyncWeb3,
    ) -> None:
        (
            latest,
            chain_id,
            block_num,
            chain_id2,
            pending,
            chain_id3,
        ) = await asyncio.gather(
            async_w3.eth.get_block("latest"),
            async_w3.eth.chain_id,
            async_w3.eth.block_number,
            async_w3.eth.chain_id,
            async_w3.eth.get_block("pending"),
            async_w3.eth.chain_id,
        )

        # assert attrdict middleware was applied appropriately
        assert isinstance(latest, AttributeDict)
        assert isinstance(pending, AttributeDict)

        # assert block values
        assert latest is not None
        assert all(k in latest.keys() for k in SOME_BLOCK_KEYS)
        assert pending is not None
        assert all(k in pending.keys() for k in SOME_BLOCK_KEYS)

        assert isinstance(block_num, int)
        assert latest["number"] == block_num

        assert isinstance(chain_id, int)
        assert isinstance(chain_id2, int)
        assert isinstance(chain_id3, int)

    @pytest.mark.asyncio
    async def test_async_public_socket_api(self, async_w3: AsyncWeb3) -> None:
        # clear all caches and queues
        async_w3.provider._request_processor.clear_caches()

        # send a request over the socket
        await async_w3.socket.send(
            RPCEndpoint("eth_getBlockByNumber"), ["latest", True]
        )

        # recv and validate the unprocessed response
        response = await async_w3.socket.recv()
        assert "id" in response, "Expected 'id' key in response."
        assert "jsonrpc" in response, "Expected 'jsonrpc' key in response."
        assert "result" in response, "Expected 'result' key in response."
        assert all(k in response["result"].keys() for k in SOME_BLOCK_KEYS)
        assert not isinstance(response["result"]["number"], int)  # assert not processed

        # make a request over the socket
        response = await async_w3.socket.make_request(
            RPCEndpoint("eth_getBlockByNumber"), ["latest", True]
        )
        assert "id" in response, "Expected 'id' key in response."
        assert "jsonrpc" in response, "Expected 'jsonrpc' key in response."
        assert "result" in response, "Expected 'result' key in response."
        assert all(k in response["result"].keys() for k in SOME_BLOCK_KEYS)
        assert not isinstance(response["result"]["number"], int)  # assert not processed

    @pytest.mark.asyncio
    async def test_async_subscription_manager_subscribes_to_many_subscriptions(
        self, async_w3: AsyncWeb3, async_emitter_contract: "AsyncContract"
    ) -> None:
        sub_manager = async_w3.subscription_manager

        event = async_emitter_contract.events.LogIndexedAndNotIndexed
        event_topic = async_w3.keccak(text=event.abi_element_identifier).to_0x_hex()

        new_heads_handler_test = SubscriptionHandlerTest()
        pending_tx_handler_test = SubscriptionHandlerTest()
        logs_handler_test = SubscriptionHandlerTest()

        await sub_manager.subscribe(
            [
                NewHeadsSubscription(
                    handler=new_heads_handler,
                    handler_context={"new_heads_handler_test": new_heads_handler_test},
                ),
                PendingTxSubscription(
                    full_transactions=True,
                    handler=pending_tx_handler,
                    handler_context={
                        "pending_tx_handler_test": pending_tx_handler_test
                    },
                ),
                LogsSubscription(
                    address=async_emitter_contract.address,
                    topics=[HexStr(event_topic)],
                    handler=logs_handler,
                    handler_context={
                        "logs_handler_test": logs_handler_test,
                        "event": event,
                    },
                ),
            ]
        )

        # emit contract event for `logs` subscription
        accts = await async_w3.eth.accounts
        acct = accts[0]
        emit_event_task = await log_indexed_and_non_indexed_args_task(
            async_w3, async_emitter_contract, acct
        )

        # get subscriptions before they are unsubscribed and removed
        subs = sub_manager.subscriptions

        await sub_manager.handle_subscriptions()

        # assert unsubscribed and removed subscriptions
        assert len(sub_manager.subscriptions) == 0

        assert sub_manager.total_handler_calls == 3
        assert all(sub.handler_call_count == 1 for sub in subs)

        assert new_heads_handler_test.passed
        assert pending_tx_handler_test.passed
        assert logs_handler_test.passed

        # cleanup
        sub_manager.total_handler_calls = 0
        await clean_up_task(emit_event_task)

    @pytest.mark.asyncio
    async def test_subscription_handler_context(self, async_w3: AsyncWeb3) -> None:
        base_url = "http://localhost:1337"
        async_beacon = AsyncBeacon(base_url)
        handler_test = SubscriptionHandlerTest()

        async def test_sub_handler(
            handler_context: NewHeadsSubscriptionContext,
        ) -> None:
            beacon = handler_context.beacon
            assert isinstance(beacon, AsyncBeacon)
            assert beacon.base_url == base_url
            assert handler_context.int1 == 1337
            assert handler_context.str1 == "foo"
            assert handler_context.int2 == 1999
            assert handler_context.str2 == "bar"

            handler_context.handler_test.passed = True
            unsubscribed = await handler_context.subscription.unsubscribe()
            assert unsubscribed

        subscribed = await async_w3.eth.subscribe(
            "newHeads",
            label="foo",
            handler=test_sub_handler,
            handler_context={
                "beacon": async_beacon,
                "int1": 1337,
                "str1": "foo",
                "int2": 1999,
                "str2": "bar",
                "handler_test": handler_test,
            },
        )
        assert is_hexstr(subscribed)

        sub_manager = async_w3.subscription_manager

        await sub_manager.handle_subscriptions()

        assert len(sub_manager.subscriptions) == 0
        assert sub_manager.total_handler_calls == 1
        assert handler_test.passed

        # cleanup
        sub_manager.total_handler_calls = 0

    @pytest.mark.asyncio
    async def test_subscriptions_with_handler_and_without(
        self, async_w3: AsyncWeb3
    ) -> None:
        handler_test = SubscriptionHandlerTest()
        stream_passed = False

        async def test_sub_handler(
            handler_context: NewHeadsSubscriptionContext,
        ) -> None:
            handler_context.handler_test.passed = True
            await handler_context.subscription.unsubscribe()

        async def handle_subscription_stream() -> None:
            nonlocal stream_passed
            async for msg in async_w3.socket.process_subscriptions():
                response = cast(FormattedEthSubscriptionResponse, msg)
                assert sub_manager.get_by_id(response["subscription"]) is not None
                assert response["result"] is not None
                # wait for the handler to unsubscribe:
                stream_passed = True
                await async_w3.eth.unsubscribe(response["subscription"])
                break

        await async_w3.eth.subscribe(
            "newHeads",
            handler=test_sub_handler,
            label="managed",
            handler_context={"handler_test": handler_test},
        )
        await async_w3.eth.subscribe("newHeads", label="streamed")

        sub_manager = async_w3.subscription_manager
        assert len(sub_manager.subscriptions) == 2

        await asyncio.gather(
            sub_manager.handle_subscriptions(),
            handle_subscription_stream(),
        )

        assert len(sub_manager.subscriptions) == 0
        assert sub_manager.total_handler_calls == 1
        assert handler_test.passed
        assert stream_passed

        # cleanup
        sub_manager.total_handler_calls = 0

    @pytest.mark.asyncio
    async def test_handle_subscriptions_breaks_on_unsubscribe(
        self,
        async_w3: AsyncWeb3,
    ) -> None:
        async def unsubscribe_subs(
            subs: List[Union[NewHeadsSubscription, LogsSubscription]]
        ) -> None:
            for sub in subs:
                await sub.unsubscribe()

        sub_manager = async_w3.subscription_manager
        sub1 = NewHeadsSubscription(label="foo", handler=idle_handler)
        sub2 = LogsSubscription(label="bar", handler=idle_handler)

        await sub_manager.subscribe([sub1, sub2])

        assert sub_manager.subscriptions == [sub1, sub2]

        unsubscribe_task = asyncio.create_task(unsubscribe_subs([sub1, sub2]))
        # With no subscriptions in the queue, ``handle_subscriptions`` should hang
        # indefinitely. Test that when the last subscription is unsubscribed from,
        # the method breaks out of the loop. This is done via a raised
        # ``SubscriptionProcessingFinished`` within the ``TaskReliantQueue``.
        await sub_manager.handle_subscriptions()

        assert_no_subscriptions_left(sub_manager._subscription_container)
        await clean_up_task(unsubscribe_task)

    @pytest.mark.asyncio
    async def test_run_forever_starts_with_0_subs_and_runs_until_task_cancelled(
        self, async_w3: AsyncWeb3
    ) -> None:
        sub_manager = async_w3.subscription_manager
        assert_no_subscriptions_left(sub_manager._subscription_container)

        run_forever_task = asyncio.create_task(
            sub_manager.handle_subscriptions(run_forever=True)
        )

        await asyncio.sleep(0.1)
        assert run_forever_task.done() is False
        assert sub_manager.subscriptions == []

        # subscribe to newHeads and validate it
        new_heads_handler_test = SubscriptionHandlerTest()
        sub1 = NewHeadsSubscription(
            label="foo",
            handler=new_heads_handler,
            handler_context={"new_heads_handler_test": new_heads_handler_test},
        )
        sub_id = await sub_manager.subscribe(sub1)
        assert is_hexstr(sub_id)
        assert len(sub_manager.subscriptions) == 1
        assert sub_manager.subscriptions[0] == sub1

        # wait for the handler to unsubscribe
        while sub_manager.subscriptions:
            await asyncio.sleep(0.1)

        assert new_heads_handler_test.passed
        assert run_forever_task.done() is False
        assert run_forever_task.cancelled() is False

        # cleanup
        await clean_up_task(run_forever_task)
