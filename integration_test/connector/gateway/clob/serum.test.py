import asyncio
import os

from hummingbot.client.config.config_crypt import ETHKeyFileSecretManger
from hummingbot.client.config.security import Security
from hummingbot.core.gateway.gateway_http_client import GatewayHttpClient


class Serum:

    def __init__(self):
        self.__chain = 'solana'
        self.__network = 'mainnet-beta'
        self.__connector = 'serum'

        self.__gateway_http_client: GatewayHttpClient = GatewayHttpClient.get_instance()

    async def main(self):
        print(await self.get_markets())

    async def get_markets(self):
        return await self.__gateway_http_client.clob_get_markets(
            self.__chain,
            self.__network,
            self.__connector
        )

    async def get_order_books(self):
        return await self.__gateway_http_client.clob_get_order_books(
            self.__chain,
            self.__network,
            self.__connector
        )

    async def get_tickers(self):
        return await self.__gateway_http_client.clob_get_tickers(
            self.__chain,
            self.__network,
            self.__connector
        )

    async def get_all_orders(self):
        return await self.__gateway_http_client.clob_get_orders(
            self.__chain,
            self.__network,
            self.__connector
        )

    async def get_all_open_orders(self):
        return await self.__gateway_http_client.clob_get_open_orders(
            self.__chain,
            self.__network,
            self.__connector
        )

    async def get_all_filled_orders(self):
        return await self.__gateway_http_client.clob_get_filled_orders(
            self.__chain,
            self.__network,
            self.__connector
        )

    async def cancel_all_orders(self):
        return await self.__gateway_http_client.clob_delete_orders(
            self.__chain,
            self.__network,
            self.__connector
        )

    async def settle_all_funds(self):
        return await self.__gateway_http_client.clob_post_settle_funds(
            self.__chain,
            self.__network,
            self.__connector
        )


if __name__ == "__main__":
    """
        In order to run these tests check the following:
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
