import asyncio
import json
import os
import random
from datetime import datetime
from typing import Any, Dict, List

from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.security import Security
from hummingbot.connector.gateway.clob.clob_types import OrderSide, OrderType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class Helper:

    chain = 'solana'
    network = 'mainnet-beta'
    connector = 'serum'

    market_names: List[str] = None
    wallets: Dict[str, Any] = None

    def __init__(self):
        owner_address = os.environ.get('SOLANA_OWNER_ADDRESS')
        payer_addresses = os.environ.get('SOLANA_PAYER_ADDRESSES').split(',')

        self.market_names = ['SOL/USDC', 'SOL/USDT', 'SRM/SOL']

        Helper.wallets = {
            'owner': {
                'public_key': owner_address,
            },
            'payer': {
                'SOL/USDC': payer_addresses[0],
                'SOL/USDT': payer_addresses[1],
                'SRM/SOL': payer_addresses[2],
            }
        }

    @staticmethod
    def create_new_candidate_order(
        id: str = None,
        market_name: str = None,
        owner_address: str = None,
        payer_address: str = None,
        side: OrderSide = None,
        price: float = None,
        amount: float = None,
        type: OrderType = None
    ):
        if not id:
            id = datetime.now()
        if not market_name:
            market_name = Helper.get_random_choice(Helper.market_names)
        if not owner_address:
            owner_address = Helper.wallets['owner']['public_key']
        if not side:
            side = Helper.get_random_choice([OrderSide.BUY, OrderSide.SELL])
        if not type:
            type = Helper.get_random_choice([OrderType.LIMIT])
        if not payer_address:
            if side == OrderSide.SELL:
                payer_address = Helper.wallets['owner']['public_key']
            elif side == OrderSide.BUY:
                payer_address = Helper.wallets['payer'][market_name]
        if not price:
            price = 0.1 if side == OrderSide.BUY else 9999.99
        if not amount:
            amount = 0.1

        return {
            'id': id,
            'market_name': market_name,
            'owner_address': owner_address,
            'payer_address': payer_address,
            'side': side,
            'price': price,
            'amount': amount,
            'type': type,
        }

    @staticmethod
    def get_random_choice(choices: List[Any]):
        return random.choice(choices)

    @staticmethod
    def dump(target: Any):
        print(json.dumps(target, indent=2))


class Serum:

    def __init__(self):
        self.__gateway_http_client: GatewayHttpClient = GatewayHttpClient.get_instance()

    async def main(self):
        # Helper.dump(await self.get_markets())
        # Helper.dump(await self.get_order_books())
        # Helper.dump(await self.get_tickers())
        # Helper.dump(await self.get_open_orders(Helper.owner_address))
        # Helper.dump(await self.get_filled_orders(Helper.owner_address))
        # Helper.dump(await self.get_orders(Helper.owner_address))
        Helper.dump(await self.place_orders(order=Helper.create_new_candidate_order(side=OrderSide.BUY)))
        # Helper.dump(await self.place_orders(orders=[{}]))
        # Helper.dump(await self.cancel_orders(orders=[{}]))

    async def get_markets(self, name: str = None, names: List[str] = None):
        return await self.__gateway_http_client.clob_get_markets(
            Helper.chain,
            Helper.network,
            Helper.connector,
            name,
            names
        )

    async def get_order_books(self, market_name: str = None, market_names: List[str] = None):
        return await self.__gateway_http_client.clob_get_order_books(
            Helper.chain,
            Helper.network,
            Helper.connector,
            market_name,
            market_names
        )

    async def get_tickers(self, market_name: str = None, market_names: List[str] = None):
        return await self.__gateway_http_client.clob_get_tickers(
            Helper.chain,
            Helper.network,
            Helper.connector,
            market_name,
            market_names
        )

    async def get_orders(self, owner_address: str = None, order: Dict[str, Any] = None,
                         orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_get_orders(
            Helper.chain,
            Helper.network,
            Helper.connector,
            owner_address,
            order,
            orders
        )

    async def get_open_orders(self, owner_address: str = None, order: Dict[str, Any] = None,
                              orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_get_open_orders(
            Helper.chain,
            Helper.network,
            Helper.connector,
            owner_address,
            order,
            orders
        )

    async def get_filled_orders(self, owner_address: str = None, order: Dict[str, Any] = None,
                                orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_get_filled_orders(
            Helper.chain,
            Helper.network,
            Helper.connector,
            owner_address,
            order,
            orders
        )

    async def place_orders(self, order: Dict[str, Any] = None, orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_post_orders(
            Helper.chain,
            Helper.network,
            Helper.connector,
            order,
            orders
        )

    async def cancel_orders(self, owner_address: str = None, order: Dict[str, Any] = None,
                            orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_delete_orders(
            Helper.chain,
            Helper.network,
            Helper.connector,
            owner_address,
            order,
            orders
        )

    async def settle_funds(self, owner_address: str = None, market_name: str = None, market_names: List[str] = None):
        return await self.__gateway_http_client.clob_post_settle_funds(
            Helper.chain,
            Helper.network,
            Helper.connector,
            owner_address,
            market_name,
            market_names
        )


if __name__ == "__main__":
    """
        In order to run these tests check the following:
            - If the `$SOLANA_WALLET_ADDRESS` environment variable is set.
            - If the file `gateway/conf/ssl.yml` is configured correctly.
            - If the file `conf/conf_client.yml` has the instance id pointing to the correct certificates path.
            - If the `$GATEWAY_PASSPHRASE` environment variable is set to the correct value.
            - If the Gateway is up and running at the correct port.
            - Maybe change the `gateway/conf/serum.yml` whitelisted markets to have only some few options so the script
                does not load all of the available markets.
    """
    try:
        event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        Security.secrets_manager = ETHKeyFileSecretManger(password=os.environ["GATEWAY_PASSPHRASE"])
        serum = Serum()
        event_loop.run_until_complete(serum.main())
    except KeyboardInterrupt:
        pass
