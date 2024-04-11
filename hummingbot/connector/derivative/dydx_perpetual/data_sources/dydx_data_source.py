
import requests
import certifi
import grpc
from typing import Any, Dict, List, Optional, Tuple

from google.protobuf import message as _message
from google.protobuf import json_format

from v4_proto.dydxprotocol.clob.tx_pb2 import MsgPlaceOrder, MsgCancelOrder
from v4_proto.dydxprotocol.clob.order_pb2 import Order, OrderId
from v4_proto.dydxprotocol.subaccounts.subaccount_pb2 import SubaccountId

from v4_proto.cosmos.tx.v1beta1.service_pb2_grpc import ServiceStub as TxGrpcClient
from v4_proto.cosmos.auth.v1beta1.query_pb2_grpc import QueryStub as AuthGrpcClient
from v4_proto.cosmos.auth.v1beta1.query_pb2 import QueryAccountRequest
from v4_proto.cosmos.auth.v1beta1.auth_pb2 import BaseAccount


from v4_proto.cosmos.tx.v1beta1.service_pb2 import (
    BroadcastMode,
    BroadcastTxRequest,
    GetTxRequest,
    SimulateRequest,
)
# from ..constants import ValidatorConfig

# 这composer暂时保留，place_order要用到
from ..composer import Composer
# from ..dydx_subaccount import Subaccount

from hummingbot.connector.derivative.dydx_perpetual.data_sources.tx import Transaction, SigningCfg
# from ...chain.aerial.tx_helpers import SubmittedTx
# from ...chain.aerial.client import LedgerClient, NetworkConfig

Public_key = None
Address = None
Private_key = None
Subaccount_NUM = 0

AERIAL_GRPC_OR_REST_PREFIX = "grpc"
AERIAL_CONFIG_URL = 'https://dydx-grpc.publicnode.com:443'

class DydxPerpetualV4Client:
    def __init__(
            self,
            private_key:str,
            dydx_chain_address:str,
            subaccount_num = 0,
    ):
        # self.config = config
        self._private_key = private_key
        self._dydx_chain_address = dydx_chain_address
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
        self.auth_client = AuthGrpcClient(grpc_client)
        self.txs = TxGrpcClient(grpc_client)

        # place_order结束后去掉
        self.composer = Composer()

        # 把 prepare_and_broadcast_basic_transaction 加到这里来
        # self.auth = AuthGrpcClient(grpc_client)

    def send_message(
            self,
            msg: _message.Message,
            zeroFee: bool = False,
    ):
        tx = Transaction()
        tx.add_message(msg)
        gas_limit = 0 if zeroFee else None

        return self.prepare_and_broadcast_basic_transaction(
            tx=tx,
            memo=None,
        )
        # 对接 _place_cancel
    def cancel_order(
            self,
            client_id: int,
            clob_pair_id: int,
            order_flags: int,
            good_til_block: int,
            good_til_block_time: int,
            broadcast_mode: BroadcastMode = None,
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
        return self.send_message(msg, zeroFee=True)

    def place_order(
            self,
            # subaccount: Subaccount,
            client_id: int,
            clob_pair_id: int,
            side: Order.Side,
            quantums: int,
            subticks: int,
            time_in_force: Order.TimeInForce,
            order_flags: int,
            reduce_only: bool,
            good_til_block: int,
            good_til_block_time: int,
            client_metadata: int,
            condition_type: Order.ConditionType = Order.ConditionType.CONDITION_TYPE_UNSPECIFIED,
            conditional_order_trigger_subticks: int = 0,
            broadcast_mode: BroadcastMode = None,
    ):

        # prepare tx msg
        subaccount_number = Subaccount_NUM

        msg = self.composer.compose_msg_place_order(
            address=Address,
            subaccount_number=subaccount_number,
            client_id=client_id,
            clob_pair_id=clob_pair_id,
            order_flags=order_flags,
            good_til_block=good_til_block,
            good_til_block_time=good_til_block_time,
            side=side,
            quantums=quantums,
            subticks=subticks,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
            client_metadata=client_metadata,
            condition_type=condition_type,
            conditional_order_trigger_subticks=conditional_order_trigger_subticks,
        )
        return self.send_message(msg=msg, zeroFee=True)

    def place_order_object(
            self,
            # subaccount: Subaccount,
            place_order: any,
            broadcast_mode: BroadcastMode = None,
    ):
        return self.place_order(
            # subaccount,
            place_order["client_id"],
            place_order["clob_pair_id"],
            place_order["side"],
            place_order["quantums"],
            place_order["subticks"],
            place_order["time_in_force"],
            place_order["order_flags"],
            place_order["reduce_only"],
            place_order.get("good_til_block", 0),
            place_order.get("good_til_block_time", 0),
            place_order.get("client_metadata", 0),
            broadcast_mode,
        )
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
        # account = client.query_account(sender.address())
        # 改成 await 和asycn request

        sequence = requests.get(f"https://dydx-grpc.publicnode.com:443/cosmos/auth/v1beta1/accounts/{self._dydx_chain_address}")
        number = Subaccount_NUM
        # 这些可以写死在 constants里
        fee = 0
        gas_limit = 0
        fee_denomination = "afet"
        chain_id = 'dydx-mainnet-1'
        # finally, build the final transaction that will be executed with the correct gas and fee values
        tx.seal(
            # SigningCfg.direct(sender.public_key(), account.sequence),
            #这里注意一下，ender.public_key() 应该指的是 keypairs.py中的 PublicKey
            SigningCfg.direct(Public_key, sequence),
            fee=f"{fee}{fee_denomination}",
            gas_limit=gas_limit,
            memo=memo,
        )
        # 这里签名需要用到 private_key
        tx.sign(Private_key, chain_id, Subaccount_NUM)
        tx.complete()

        ##
        # result = client.broadcast_tx(tx)

        broadcast_req = BroadcastTxRequest(
            tx_bytes=tx.tx.SerializeToString(), mode=BroadcastMode.BROADCAST_MODE_SYNC
        )
        # with open(certifi.where(), "rb") as f:
        #     trusted_certs = f.read()
        # credentials = grpc.ssl_channel_credentials(
        #     root_certificates=trusted_certs
        # )
        # AERIAL_GRPC_OR_REST_PREFIX = "grpc"
        # AERIAL_CONFIG_URL = 'https://dydx-grpc.publicnode.com:443'
        #
        # host_and_port = AERIAL_GRPC_OR_REST_PREFIX + AERIAL_CONFIG_URL
        # grpc_client = (
        #     grpc.aio.secure_channel(host_and_port, credentials)
        #     if credentials is not None else grpc.aio.insecure_channel(host_and_port)
        # )
        auth_client = AuthGrpcClient(grpc_client)
        resp = await TxGrpcClient(grpc_client).BroadcastTx(broadcast_req)

        result = json_format.MessageToDict(
            message=resp,
            including_default_value_fields=True,
        )

        return result