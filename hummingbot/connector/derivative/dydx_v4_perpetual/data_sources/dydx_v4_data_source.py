from asyncio import Lock
from datetime import datetime, timedelta
from typing import Optional, Tuple

import certifi
import grpc
from google.protobuf import json_format, message as _message
from v4_proto.cosmos.auth.v1beta1.auth_pb2 import BaseAccount
from v4_proto.cosmos.auth.v1beta1.query_pb2 import QueryAccountRequest
from v4_proto.cosmos.auth.v1beta1.query_pb2_grpc import QueryStub as AuthGrpcClient
from v4_proto.cosmos.bank.v1beta1 import query_pb2_grpc as bank_query_grpc
from v4_proto.cosmos.base.tendermint.v1beta1 import (
    query_pb2 as tendermint_query,
    query_pb2_grpc as tendermint_query_grpc,
)
from v4_proto.cosmos.tx.v1beta1.service_pb2 import BroadcastMode, BroadcastTxRequest
from v4_proto.cosmos.tx.v1beta1.service_pb2_grpc import ServiceStub as TxGrpcClient
from v4_proto.dydxprotocol.clob.order_pb2 import Order, OrderId
from v4_proto.dydxprotocol.clob.tx_pb2 import MsgCancelOrder, MsgPlaceOrder
from v4_proto.dydxprotocol.subaccounts.subaccount_pb2 import SubaccountId

from hummingbot.connector.derivative.dydx_v4_perpetual import dydx_v4_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.dydx_v4_perpetual.data_sources.keypairs import PrivateKey
from hummingbot.connector.derivative.dydx_v4_perpetual.data_sources.tx import SigningCfg, Transaction


class DydxPerpetualV4Client:

    def __init__(
            self,
            secret_phrase: str,
            dydx_v4_chain_address: str,
            connector,
            subaccount_num=0,
    ):
        self._private_key = PrivateKey.from_mnemonic(secret_phrase)
        self._dydx_v4_chain_address = dydx_v4_chain_address
        self._connector = connector
        self._subaccount_num = subaccount_num
        self.transaction_lock = Lock()
        self.number = 0
        self.sequence = 0
        self._is_trading_account_initialized = False

        with open(certifi.where(), "rb") as f:
            trusted_certs = f.read()
        credentials = grpc.ssl_channel_credentials(
            root_certificates=trusted_certs
        )

        host_and_port = CONSTANTS.DYDX_V4_AERIAL_CONFIG_URL
        grpc_client = (
            grpc.aio.secure_channel(host_and_port, credentials)
            if credentials is not None else grpc.aio.insecure_channel(host_and_port)
        )
        query_grpc_client = (
            grpc.aio.secure_channel(CONSTANTS.DYDX_V4_QUERY_AERIAL_CONFIG_URL, credentials)
            if credentials is not None else grpc.aio.insecure_channel(host_and_port)
        )
        self.stubBank = bank_query_grpc.QueryStub(grpc_client)
        self.auth_client = AuthGrpcClient(query_grpc_client)
        self.txs = TxGrpcClient(grpc_client)
        self.stubCosmosTendermint = tendermint_query_grpc.ServiceStub(
            grpc_client
        )

    @staticmethod
    def calculate_quantums(
            size: float,
            atomic_resolution: int,
            step_base_quantums: int,
    ):
        raw_quantums = size * 10 ** (-1 * atomic_resolution)
        return int(max(raw_quantums, step_base_quantums))

    @staticmethod
    def calculate_subticks(
            price: float,
            atomic_resolution: int,
            quantum_conversion_exponent: int,
            subticks_per_tick: int
    ):
        exponent = atomic_resolution - quantum_conversion_exponent - CONSTANTS.QUOTE_QUANTUMS_ATOMIC_RESOLUTION
        raw_subticks = price * 10 ** (exponent)
        return int(max(raw_subticks, subticks_per_tick))

    def calculate_good_til_block_time(self, good_til_time_in_seconds: int) -> int:
        now = datetime.now()
        interval = timedelta(seconds=good_til_time_in_seconds)
        future = now + interval
        return int(future.timestamp())

    def get_sequence(self):
        current_seq = self.sequence
        self.sequence += 1
        return current_seq

    def get_number(self):
        return self.number

    async def trading_account_sequence(self) -> int:
        if not self._is_trading_account_initialized:
            await self.initialize_trading_account()
        return self.get_sequence()

    async def trading_account_number(self) -> int:
        if not self._is_trading_account_initialized:
            await self.initialize_trading_account()
        return self.get_number()

    async def initialize_trading_account(self):
        await self.query_account()
        self._is_trading_account_initialized = True

    def generate_good_til_fields(
            self,
            order_flags: int,
            good_til_block: int,
            good_til_time_in_seconds: int,
    ) -> Tuple[int, int]:
        if order_flags == CONSTANTS.ORDER_FLAGS_LONG_TERM:
            return 0, self.calculate_good_til_block_time(good_til_time_in_seconds)
        else:
            return good_til_block, 0

    async def latest_block(self) -> tendermint_query.GetLatestBlockResponse:
        '''
        Get lastest block

        :returns: Response, containing block information

        '''
        return await self.stubCosmosTendermint.GetLatestBlock(
            tendermint_query.GetLatestBlockRequest()
        )

    async def send_message(
            self,
            msg: _message.Message,
    ):
        tx = Transaction()
        tx.add_message(msg)
        return await self.prepare_and_broadcast_basic_transaction(
            tx=tx,
            memo=None,
        )

    async def cancel_order(
            self,
            client_id: int,
            clob_pair_id: int,
            order_flags: int,
            good_til_block_time: int,
    ):

        subaccount_id = SubaccountId(owner=self._dydx_v4_chain_address, number=self._subaccount_num)
        order_id = OrderId(
            subaccount_id=subaccount_id,
            client_id=client_id,
            order_flags=order_flags,
            clob_pair_id=int(clob_pair_id)
        )
        msg = MsgCancelOrder(
            order_id=order_id,
            good_til_block_time=good_til_block_time
        )
        result = await self.send_message(msg)
        return result

    async def place_order(
            self,
            market,
            type,
            side,
            price,
            size,
            client_id: int,
            post_only: bool,
            reduce_only: bool = False,
            good_til_time_in_seconds: int = 6000,
    ):

        clob_pair_id = self._connector._margin_fractions[market]["clob_pair_id"]
        atomic_resolution = self._connector._margin_fractions[market]["atomicResolution"]
        step_base_quantums = self._connector._margin_fractions[market]["stepBaseQuantums"]
        quantum_conversion_exponent = self._connector._margin_fractions[market]["quantumConversionExponent"]
        subticks_per_tick = self._connector._margin_fractions[market]["subticksPerTick"]

        order_side = Order.SIDE_BUY if side == "BUY" else Order.SIDE_SELL
        quantums = self.calculate_quantums(size, atomic_resolution, step_base_quantums)
        subticks = self.calculate_subticks(price, atomic_resolution, quantum_conversion_exponent, subticks_per_tick)
        order_flags = CONSTANTS.ORDER_FLAGS_SHORT_TERM if type == "MARKET" else CONSTANTS.ORDER_FLAGS_LONG_TERM

        if type == "MARKET":
            time_in_force = CONSTANTS.TIME_IN_FORCE_IOC
            latest_block_result = await self.latest_block()
            good_til_block = latest_block_result.block.header.height + 1 + 10
        else:
            good_til_block = 0
            if post_only:
                time_in_force = CONSTANTS.TIME_IN_FORCE_POST_ONLY
            else:
                time_in_force = CONSTANTS.TIME_IN_FORCE_UNSPECIFIED

        good_til_block, good_til_block_time = self.generate_good_til_fields(
            order_flags,
            good_til_block,
            good_til_time_in_seconds,
        )
        client_metadata = 1 if type == "MARKET" else 0
        condition_type = Order.CONDITION_TYPE_UNSPECIFIED
        conditional_order_trigger_subticks = 0

        subaccount_id = SubaccountId(owner=self._dydx_v4_chain_address, number=self._subaccount_num)

        order_id = OrderId(
            subaccount_id=subaccount_id,
            client_id=client_id,
            order_flags=order_flags,
            clob_pair_id=int(clob_pair_id)
        )
        order = Order(
            order_id=order_id,
            side=order_side,
            quantums=quantums,
            subticks=subticks,
            good_til_block=good_til_block,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            client_metadata=client_metadata,
            condition_type=condition_type,
            conditional_order_trigger_subticks=conditional_order_trigger_subticks,
        ) if (good_til_block != 0) else Order(
            order_id=order_id,
            side=order_side,
            quantums=quantums,
            subticks=subticks,
            good_til_block_time=good_til_block_time,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            client_metadata=client_metadata,
            condition_type=condition_type,
            conditional_order_trigger_subticks=conditional_order_trigger_subticks,
        )
        msg = MsgPlaceOrder(order=order)
        return await self.send_message(msg=msg)

    async def query_account(self):
        request = QueryAccountRequest(address=self._dydx_v4_chain_address)
        response = await self.auth_client.Account(request)

        account = BaseAccount()
        if not response.account.Is(BaseAccount.DESCRIPTOR):
            raise RuntimeError("Unexpected account type returned from query")
        response.account.Unpack(account)
        self.sequence = account.sequence
        self.number = account.account_number
        return account.sequence, account.account_number

    async def prepare_and_broadcast_basic_transaction(
            self,
            tx: "Transaction",  # type: ignore # noqa: F821
            memo: Optional[str] = None,
    ):
        async with self.transaction_lock:
            # query the account information for the sender
            sequence = await self.trading_account_sequence()
            number = await self.trading_account_number()
            # finally, build the final transaction that will be executed with the correct gas and fee values
            tx.seal(
                SigningCfg.direct(self._private_key, sequence),
                fee=f"{CONSTANTS.TX_FEE}{CONSTANTS.FEE_DENOMINATION}",
                gas_limit=CONSTANTS.TX_GAS_LIMIT,
                memo=memo,
            )
            tx.sign(self._private_key, CONSTANTS.CHAIN_ID, number)
            tx.complete()

            broadcast_req = BroadcastTxRequest(
                tx_bytes=tx.tx.SerializeToString(), mode=BroadcastMode.BROADCAST_MODE_SYNC
            )
            result = await self.send_tx_sync_mode(broadcast_req)
            err_msg = result.get("raw_log", "")
            if CONSTANTS.ACCOUNT_SEQUENCE_MISMATCH_ERROR in err_msg:
                await self.initialize_trading_account()

            return result

    async def send_tx_sync_mode(self, broadcast_req):
        resp = await self.txs.BroadcastTx(broadcast_req)
        result = json_format.MessageToDict(
            message=resp,
            always_print_fields_with_no_presence=True,
            preserving_proto_field_name=True,
            use_integers_for_enums=True,
        ).get("tx_response", {})
        return result
