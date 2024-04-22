import requests
import certifi
import grpc
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from google.protobuf import message as _message
from google.protobuf import json_format

from v4_proto.dydxprotocol.clob.tx_pb2 import MsgPlaceOrder, MsgCancelOrder
from v4_proto.dydxprotocol.clob.order_pb2 import Order, OrderId
from v4_proto.dydxprotocol.subaccounts.subaccount_pb2 import SubaccountId

from v4_proto.cosmos.tx.v1beta1.service_pb2_grpc import ServiceStub as TxGrpcClient
from v4_proto.cosmos.bank.v1beta1 import (
    query_pb2_grpc as bank_query_grpc,
    query_pb2 as bank_query,
)

from v4_proto.cosmos.base.tendermint.v1beta1 import (
    query_pb2_grpc as tendermint_query_grpc,
    query_pb2 as tendermint_query,
)

from v4_proto.cosmos.auth.v1beta1.query_pb2_grpc import QueryStub as AuthGrpcClient
from v4_proto.cosmos.auth.v1beta1.query_pb2 import QueryAccountRequest
from v4_proto.cosmos.auth.v1beta1.auth_pb2 import BaseAccount

from v4_proto.cosmos.tx.v1beta1.service_pb2 import (
    BroadcastMode,
    BroadcastTxRequest,
    GetTxRequest,
    SimulateRequest,
)

from hummingbot.connector.derivative.dydx_perpetual.data_sources.tx import Transaction, SigningCfg
from hummingbot.connector.derivative.dydx_perpetual.data_sources.keypairs import PrivateKey, PublicKey

from hummingbot.connector.derivative.dydx_perpetual import (
    dydx_perpetual_constants as CONSTANTS
)

AERIAL_GRPC_OR_REST_PREFIX = "grpc"
AERIAL_CONFIG_URL = 'https://dydx-grpc.publicnode.com:443'

if TYPE_CHECKING:
    from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_derivative import DydxPerpetualDerivative


class DydxPerpetualV4Client:

    def __init__(
            self,
            private_key: str,
            dydx_chain_address: str,
            connector: DydxPerpetualDerivative,
            subaccount_num=0,
    ):
        self._private_key = PrivateKey(private_key)
        self._dydx_chain_address = dydx_chain_address
        self._connector = connector
        self._subaccount_num = subaccount_num

        with open(certifi.where(), "rb") as f:
            trusted_certs = f.read()
        credentials = grpc.ssl_channel_credentials(
            root_certificates=trusted_certs
        )

        host_and_port = AERIAL_GRPC_OR_REST_PREFIX + AERIAL_CONFIG_URL
        grpc_client = (
            grpc.aio.secure_channel(host_and_port, credentials)
            if credentials is not None else grpc.aio.insecure_channel(host_and_port)
        )
        self.stubBank = bank_query_grpc.QueryStub(grpc_client)
        self.auth_client = AuthGrpcClient(grpc_client)
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
        quantums = round(raw_quantums, step_base_quantums)
        return max(quantums, step_base_quantums)

    @staticmethod
    def calculate_subticks(
            price: float,
            atomic_resolution: int,
            quantum_conversion_exponent: int,
            subticks_per_tick: int
    ):
        exponent = atomic_resolution - quantum_conversion_exponent - CONSTANTS.QUOTE_QUANTUMS_ATOMIC_RESOLUTION
        raw_subticks = price * 10 ** (exponent)
        subticks = round(raw_subticks, subticks_per_tick)
        return max(subticks, subticks_per_tick)

    def calculate_good_til_block_time(self, good_til_time_in_seconds: int) -> int:
        now = datetime.now()
        interval = timedelta(seconds=good_til_time_in_seconds)
        future = now + interval
        return int(future.timestamp())

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

    # default client methods
    # sync_timeout_height, inj 这里有个初始化的轮训，是否考虑加上
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
    def bank_balances(self, address: str):
        '''
        Get wallet account balances

        :returns: All assets in the wallet
        '''
        resp = self.stubBank.AllBalances(
            bank_query.QueryAllBalancesRequest(address=address)
        )
        # result = json_format.MessageToDict(
        #     message=resp,
        #     including_default_value_fields=True,
        # )
        return resp

    # order_flags要改
    async def cancel_order(
            self,
            client_id: int,
            clob_pair_id: int,
            order_flags: int,
            good_til_block_time: int,
    ):

        subaccount_id = SubaccountId(owner=self._dydx_chain_address, number=self._subaccount_num)
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
        async with self._connector.throttler.execute_task(limit_id=CONSTANTS.LIMIT_ID_ORDER_CANCEL):
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

        # msg
        subaccount_id = SubaccountId(owner=self._dydx_chain_address, number=self._subaccount_num)

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
        # 这里sequence可以加一个初始化
        request = QueryAccountRequest(address=self._dydx_chain_address)
        response = await self.auth_client.Account(request)

        account = BaseAccount()
        if not response.account.Is(BaseAccount.DESCRIPTOR):
            raise RuntimeError("Unexpected account type returned from query")
        response.account.Unpack(account)
        sequence = account.sequence
        return sequence

    async def prepare_and_broadcast_basic_transaction(
            self,
            tx: "Transaction",  # type: ignore # noqa: F821
            memo: Optional[str] = None,
    ):
        # query the account information for the sender
        # if account is None:
        sequence = await self.query_account()

        # 这些可以写死在 constants里
        fee = 0
        gas_limit = 0
        fee_denomination = "afet"
        chain_id = 'dydx-mainnet-1'
        # finally, build the final transaction that will be executed with the correct gas and fee values
        tx.seal(
            # SigningCfg.direct(sender.public_key(), account.sequence),
            # 这里注意一下，ender.public_key() 应该指的是 keypairs.py中的 PublicKey
            SigningCfg.direct(self._private_key, sequence),
            fee=f"{fee}{fee_denomination}",
            gas_limit=gas_limit,
            memo=memo,
        )
        tx.sign(self._private_key, chain_id, self._subaccount_num)
        tx.complete()

        broadcast_req = BroadcastTxRequest(
            tx_bytes=tx.tx.SerializeToString(), mode=BroadcastMode.BROADCAST_MODE_SYNC
        )
        resp = await self.txs.BroadcastTx(broadcast_req)

        result = json_format.MessageToDict(
            message=resp,
            including_default_value_fields=True,
        )

        return result
