import asyncio
import time
import unittest
from decimal import Decimal

from pyinjective.async_client import AsyncClient
from pyinjective.constant import Network

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.security import Security
from hummingbot.connector.gateway.clob_spot.data_sources.injective.injective_utils import Composer, OrderHashManager
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
        self._account_address = "inj1ycfk9k7pmqmst2craxteyd2k3xj93xuw2x0vgp"  # noqa: mock
        self._subaccount_id = "0x261362dbc1d83705ab03e99792355689a4589b8e000000000000000000000000"  # noqa: mock

        # ATOM-USDT Perp on mainnet
        self._market_id = "0xc559df216747fc11540e638646c384ad977617d6d8f0ea5ffdfc18d52e58ab01"  # noqa: mock

        secrets_manager = ETHKeyFileSecretManger(password="123")
        Security.login(secrets_manager=secrets_manager)

        self.mainnet_lb = Network.mainnet(node="lb")

        self.mainnet_lb_client = AsyncClient(network=self.mainnet_lb)

        self.mainnet_lb_order_hash_mgr = OrderHashManager(network=self.mainnet_lb, sub_account_id=self._subaccount_id)

        self.gateway_instance = GatewayHttpClient.get_instance()

    async def test_order_computation(self):

        await self.mainnet_lb_order_hash_mgr.start()

        mainnet_lb_composer = Composer(network=self.mainnet_lb.string())

        trading_pair = "ATOM-USDT"

        order: GatewayInFlightOrder = GatewayInFlightOrder(
            client_order_id="someClienOrderId",
            trading_pair=trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=time.time(),
            price=Decimal("8.206"),
            amount=Decimal("0.4"),
            position=PositionAction.OPEN,
            leverage=1,
        )

        derivative_orders_to_compute_hashes = [
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
        ]
        order_hash_mainnet_lb_resp = self.mainnet_lb_order_hash_mgr.compute_order_hashes(
            spot_orders=[],
            derivative_orders=derivative_orders_to_compute_hashes,
        )
        order_hash_mainnet_lb = order_hash_mainnet_lb_resp.derivative[0]
        print(f"mainnet_lb OrderHash: {order_hash_mainnet_lb}")
        # return

        hash_map = {"lb": order_hash_mainnet_lb}

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
            market=trading_pair,
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

        print(f"Match found: {match_found}")
        self.assertTrue(match_found)

    async def test_get_orders(self):
        trading_pair = "ATOM-USDT"
        get_orders_response = await self.gateway_instance.clob_perp_get_orders(
            connector="injective_perpetual",
            chain="injective",
            network="mainnet",
            market=trading_pair,
            address=self._subaccount_id,
        )
        print(get_orders_response)
