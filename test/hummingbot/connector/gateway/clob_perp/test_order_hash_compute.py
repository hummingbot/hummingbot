import asyncio
import time
import unittest
from decimal import Decimal

from pyinjective.async_client import AsyncClient
from pyinjective.composer import Composer as ProtoMsgComposer
from pyinjective.constant import Network

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_api_data_source import OrderHashManager
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class TestScript(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.client_config_map = ClientConfigAdapter(ClientConfigMap())
        cls.client_config_map.gateway.gateway_api_host = "localhost"
        cls.client_config_map.gateway.gateway_api_port = "15888"
        cls.client_config_map.certs_path = ""

    def setUp(self) -> None:
        self._account_address = "inj1w26juqraq8x94smrfy5g7fxwr0v39nkluxrq07"  # noqa: mock
        self._subaccount_id = "0x72b52e007d01cc5ac36349288f24ce1bd912cedf000000000000000000000000"  # noqa: mock

        # INJ-USDT Perp on mainnet
        self._market_id = "0x9b9980167ecc3645ff1a5517886652d94a0825e54a77d2057cbbe3ebee015963"  # noqa: mock

        self.mainnet_k8s = Network.mainnet(node="k8s")
        self.mainnet_lb = Network.mainnet(node="lb")
        self.mainnet_sentry3 = Network.mainnet(node="sentry3")

        self.mainnet_k8s_client = AsyncClient(network=self.mainnet_k8s)
        self.mainnet_lb_client = AsyncClient(network=self.mainnet_lb)
        self.mainnet_sentry3_client = AsyncClient(network=self.mainnet_sentry3)

        self.mainnet_k8s_order_hash_mgr = OrderHashManager(network=self.mainnet_k8s, sub_account_id=self._subaccount_id)
        self.mainnet_lb_order_hash_mgr = OrderHashManager(network=self.mainnet_lb, sub_account_id=self._subaccount_id)
        self.mainnet_sentry3_order_hash_mgr = OrderHashManager(
            network=self.mainnet_sentry3, sub_account_id=self._subaccount_id
        )

        self.gateway_instance = GatewayHttpClient.get_instance()

    async def test_order_computation(self):

        await self.mainnet_k8s_order_hash_mgr.start()
        await self.mainnet_lb_order_hash_mgr.start()
        await self.mainnet_sentry3_order_hash_mgr.start()

        mainnet_k8s_composer = ProtoMsgComposer(network=self.mainnet_k8s.string())
        mainnet_lb_composer = ProtoMsgComposer(network=self.mainnet_lb.string())
        mainnet_sentry3_composer = ProtoMsgComposer(network=self.mainnet_sentry3.string())

        order: GatewayInFlightOrder = GatewayInFlightOrder(
            client_order_id="someClienOrderId",
            trading_pair="INJ-USDT",
            order_type=OrderType.LIMIT_MAKER,
            trade_type=TradeType.BUY,
            creation_timestamp=time.time(),
            price=Decimal(4),
            amount=Decimal(1),
            position=PositionAction.OPEN,
            leverage=1,
        )

        order_hash_mainnet_k8s_resp = self.mainnet_k8s_order_hash_mgr.compute_order_hashes(
            spot_orders=[],
            derivative_orders=[
                mainnet_k8s_composer.DerivativeOrder(
                    market_id=self._market_id,
                    subaccount_id=self._subaccount_id,
                    fee_recipient=self._account_address,
                    price=float(order.price),
                    quantity=float(order.amount),
                    is_buy=order.trade_type == TradeType.BUY,
                    is_po=order.order_type == OrderType.LIMIT_MAKER,
                    leverage=float(order.leverage),
                )
            ],
        )
        order_hash_mainnet_k8s = order_hash_mainnet_k8s_resp.derivative[0]
        print(f"mainnet_k8s OrderHash: {order_hash_mainnet_k8s}")

        order_hash_mainnet_lb_resp = self.mainnet_lb_order_hash_mgr.compute_order_hashes(
            spot_orders=[],
            derivative_orders=[
                mainnet_lb_composer.DerivativeOrder(
                    market_id=self._market_id,
                    subaccount_id=self._subaccount_id,
                    fee_recipient=self._account_address,
                    price=float(order.price),
                    quantity=float(order.amount),
                    is_buy=order.trade_type == TradeType.BUY,
                    is_po=order.order_type == OrderType.LIMIT_MAKER,
                    leverage=float(order.leverage),
                )
            ],
        )
        order_hash_mainnet_lb = order_hash_mainnet_lb_resp.derivative[0]
        print(f"mainnet_lb OrderHash: {order_hash_mainnet_lb}")

        order_hash_mainnet_sentry3_resp = self.mainnet_sentry3_order_hash_mgr.compute_order_hashes(
            spot_orders=[],
            derivative_orders=[
                mainnet_sentry3_composer.DerivativeOrder(
                    market_id=self._market_id,
                    subaccount_id=self._subaccount_id,
                    fee_recipient=self._account_address,
                    price=float(order.price),
                    quantity=float(order.amount),
                    is_buy=order.trade_type == TradeType.BUY,
                    is_po=order.order_type == OrderType.LIMIT_MAKER,
                    leverage=float(order.leverage),
                )
            ],
        )
        order_hash_mainnet_sentry3 = order_hash_mainnet_sentry3_resp.derivative[0]
        print(f"mainnet_sentry3 OrderHash: {order_hash_mainnet_sentry3}")

        hash_map = {"k8s": order_hash_mainnet_k8s, "lb": order_hash_mainnet_lb, "sentry": order_hash_mainnet_sentry3}

        order_creation_result = await self.gateway_instance.clob_perp_place_order(
            connector="injective_perpetual",
            chain="injective",
            network="mainnet",
            trading_pair=order.trading_pair,
            address=self._subaccount_id,
            trade_type=order.trade_type,
            order_type=order.order_type,
            price=order.price,
            size=order.amount,
            leverage=order.leverage,
        )

        print(f"Gateway Order Creation Response: {order_creation_result}")

        await asyncio.sleep(5)

        get_orders_response = await self.gateway_instance.clob_perp_get_orders(
            connector="injective_perpetual",
            chain="injective",
            network="mainnet",
            market="INJ-USDT",
            address=self._subaccount_id,
        )

        match_found = False
        for order_details in get_orders_response["orders"]:
            order_hash = order_details["orderHash"]
            for network, pre_computed_hash in hash_map.items():
                if order_hash == pre_computed_hash:
                    print(f"Match found for {network}")
                    match_found = True

            if match_found:
                break

        print(match_found)

    async def test_get_orders(self):
        get_orders_response = await self.gateway_instance.clob_perp_get_orders(
            connector="injective_perpetual",
            chain="injective",
            network="mainnet",
            market="INJ-USDT",
            address=self._subaccount_id,
        )
        print(get_orders_response)
