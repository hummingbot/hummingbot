import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml
from yaml import Loader

from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.security import Security
from hummingbot.connector.gateway.clob.clob_types import OrderSide, OrderType
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class Helper:

    def __init__(self):
        self.configuration_folder = os.path.realpath(os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            '../../../../conf/scripts'
        ))
        self.configuration_path = os.path.realpath(os.path.join(
            self.configuration_folder,
            'clob_example.yml'
        ))

        Path(self.configuration_folder).mkdir(parents=True, exist_ok=True)

        template = {
            'chain': 'solana',
            'network': 'mainnet-beta',
            'connector': 'serum',
            'markets': [
                'SOL/USDC',
                'SOL/USDT',
                'SRM/SOL'
            ],
            'wallets': {
                'owner': {
                    'public_key': ''
                },
                'payer': {
                    'SOL/USDC': {
                        'public_key': ''
                    },
                    'SOL/USDT': {
                        'public_key': ''
                    },
                    'SRM/SOL': {
                        'public_key': ''
                    }
                }
            }
        }

        if not os.path.exists(self.configuration_path):
            with open(self.configuration_path, 'w') as file:
                file.write(yaml.dump(template))

        with open(self.configuration_path, encoding='utf-8') as stream:
            self.configuration = yaml.load(stream, Loader=Loader)

    def create_new_candidate_order(
        self,
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
            id = int(round(1000 * datetime.now().timestamp()))
        if not market_name:
            market_name = self.get_random_choice(self.configuration['markets'])
        if not owner_address:
            owner_address = self.configuration['wallets']['owner']['public_key']
        if not side:
            side = self.get_random_choice([OrderSide.BUY, OrderSide.SELL])
        if not type:
            type = self.get_random_choice([OrderType.LIMIT, OrderType.IOC])
        if not payer_address:
            if side == OrderSide.SELL:
                payer_address = self.configuration['wallets']['owner']['public_key']
            elif side == OrderSide.BUY:
                payer_address = self.configuration['wallets']['payer'][market_name]['public_key']
                if not payer_address:
                    payer_address = None
        if not price:
            price = 0.1 if side == OrderSide.BUY else 9999.99
        if not amount:
            amount = 0.1

        return {
            'id': id,
            'marketName': market_name,
            'ownerAddress': owner_address,
            'payerAddress': payer_address,
            'side': side.value[0],
            'price': price,
            'amount': amount,
            'type': type.value[0]
        }

    def get_random_choice(self, choices: List[Any]):
        return random.choice(choices)

    def dump(self, target: Any):
        print(json.dumps(target, indent=2))


class Serum:

    def __init__(self):
        self.helper = Helper()
        self.__gateway_http_client: GatewayHttpClient = GatewayHttpClient.get_instance()

    async def main(self):
        try:
            pass
            # self.helper.dump(await self.auto_create_token_accounts(self.helper.configuration['markets']))
            # self.helper.dump(await self.get_markets())
            # self.helper.dump(await self.get_order_books())
            # self.helper.dump(await self.get_tickers())
            # self.helper.dump(await self.get_open_orders(self.helper.configuration['wallets']['owner']['public_key']))
            # self.helper.dump(await self.get_filled_orders(self.helper.configuration['wallets']['owner']['public_key']))
            # self.helper.dump(await self.get_orders(self.helper.configuration['wallets']['owner']['public_key']))
            # self.helper.dump(await self.place_orders(order=self.helper.create_new_candidate_order(side=OrderSide.SELL, type=OrderType.IOC)))
            # self.helper.dump(await self.place_orders(orders=[{}]))
            # self.helper.dump(await self.cancel_orders(self.helper.configuration['wallets']['owner']['public_key']))
        except Exception as exception:
            print(exception)

    async def auto_create_token_accounts(self, market_names: List[str] = None):
        output = {}

        if market_names:
            for market_name in market_names:
                output[market_name] = (await GatewayHttpClient.get_instance().solana_post_token(
                    self.helper.configuration['network'],
                    self.helper.configuration['wallets']['owner']['public_key'],
                    market_name
                ))['accountAddress']

        return output

    async def get_markets(self, name: str = None, names: List[str] = None):
        return await self.__gateway_http_client.clob_get_markets(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            name,
            names
        )

    async def get_order_books(self, market_name: str = None, market_names: List[str] = None):
        return await self.__gateway_http_client.clob_get_order_books(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            market_name,
            market_names
        )

    async def get_tickers(self, market_name: str = None, market_names: List[str] = None):
        return await self.__gateway_http_client.clob_get_tickers(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            market_name,
            market_names
        )

    async def get_orders(self, owner_address: str = None, order: Dict[str, Any] = None,
                         orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_get_orders(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            owner_address,
            order,
            orders
        )

    async def get_open_orders(self, owner_address: str = None, order: Dict[str, Any] = None,
                              orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_get_open_orders(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            owner_address,
            order,
            orders
        )

    async def get_filled_orders(self, owner_address: str = None, order: Dict[str, Any] = None,
                                orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_get_filled_orders(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            owner_address,
            order,
            orders
        )

    async def place_orders(self, order: Dict[str, Any] = None, orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_post_orders(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            order,
            orders
        )

    async def cancel_orders(self, owner_address: str = None, order: Dict[str, Any] = None,
                            orders: List[Dict[str, Any]] = None):
        return await self.__gateway_http_client.clob_delete_orders(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            owner_address,
            order,
            orders
        )

    async def settle_funds(self, owner_address: str = None, market_name: str = None, market_names: List[str] = None):
        return await self.__gateway_http_client.clob_post_settle_funds(
            self.helper.configuration['chain'],
            self.helper.configuration['network'],
            self.helper.configuration['connector'],
            owner_address,
            market_name,
            market_names
        )


if __name__ == '__main__':
    '''
        In order to run these tests check the following:
            - If the file `gateway/conf/ssl.yml` is configured correctly.
            - If the file `conf/conf_client.yml` has the instance id pointing to the correct certificates path.
            - If the `$GATEWAY_PASSPHRASE` environment variable is set to the correct value.
            - If the Gateway is up and running at the correct port.
            - Maybe change the `gateway/conf/serum.yml` whitelisted markets to have only some few options so the script
                does not load all of the available markets.
            - If the file `conf/scripts/clob_example.yml` exists and it is configured correctly (template in the code above).
    '''
    try:
        event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
        Security.secrets_manager = ETHKeyFileSecretManger(password=os.environ['GATEWAY_PASSPHRASE'])
        serum = Serum()
        event_loop.run_until_complete(serum.main())
    except KeyboardInterrupt:
        pass
