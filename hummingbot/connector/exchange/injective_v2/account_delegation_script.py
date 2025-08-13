import asyncio
import json

from pyinjective.async_client_v2 import AsyncClient
from pyinjective.core.broadcaster import MsgBroadcasterWithPk
from pyinjective.core.network import Network
from pyinjective.wallet import PrivateKey

# Values to be configured by the user
NETWORK = Network.testnet()  # Select the correct network: mainnet, testnet, devnet, local or custom
GRANT_EXPIRATION_IN_DAYS = 365
GRANTER_ACCOUNT_PRIVATE_KEY = ""
GRANTER_SUBACCOUNT_INDEX = 0
GRANTEE_PUBLIC_INJECTIVE_ADDRESS = ""
SPOT_MARKET_IDS = []
DERIVATIVE_MARKET_IDS = []
# List of the ids of all the markets the grant will include, for example:
# SPOT_MARKET_IDS = ["0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"]  # noqa: mock
# Mainnet spot markets: https://lcd.injective.network/injective/exchange/v1beta1/spot/markets
# Testnet spot markets: https://k8s.testnet.lcd.injective.network/injective/exchange/v1beta1/spot/markets
# Mainnet derivative markets: https://lcd.injective.network/injective/exchange/v1beta1/derivative/markets
# Testnet derivative markets: https://k8s.testnet.lcd.injective.network/injective/exchange/v1beta1/derivative/markets

# Fixed values, do not change
SECONDS_PER_DAY = 60 * 60 * 24


async def main() -> None:
    # initialize grpc client
    client = AsyncClient(NETWORK)
    composer = await client.composer()

    gas_price = await client.current_chain_gas_price()
    # adjust gas price to make it valid even if it changes between the time it is requested and the TX is broadcasted
    gas_price = int(gas_price * 1.1)

    message_broadcaster = MsgBroadcasterWithPk.new_using_gas_heuristics(
        network=NETWORK,
        private_key=GRANTER_ACCOUNT_PRIVATE_KEY,
        gas_price=gas_price,
        client=client,
        composer=composer,
    )

    # load account
    granter_private_key = PrivateKey.from_hex(GRANTER_ACCOUNT_PRIVATE_KEY)
    granter_public_key = granter_private_key.to_public_key()
    granter_address = granter_public_key.to_address()
    granter_subaccount_id = granter_address.get_subaccount_id(index=GRANTER_SUBACCOUNT_INDEX)

    msg_spot_market = composer.msg_grant_typed(
        granter=granter_address.to_acc_bech32(),
        grantee=GRANTEE_PUBLIC_INJECTIVE_ADDRESS,
        msg_type="CreateSpotMarketOrderAuthz",
        expiration_time_seconds=GRANT_EXPIRATION_IN_DAYS * SECONDS_PER_DAY,
        subaccount_id=granter_subaccount_id,
        market_ids=SPOT_MARKET_IDS,
    )

    msg_derivative_market = composer.msg_grant_typed(
        granter=granter_address.to_acc_bech32(),
        grantee=GRANTEE_PUBLIC_INJECTIVE_ADDRESS,
        msg_type="CreateDerivativeMarketOrderAuthz",
        expiration_time_seconds=GRANT_EXPIRATION_IN_DAYS * SECONDS_PER_DAY,
        subaccount_id=granter_subaccount_id,
        market_ids=DERIVATIVE_MARKET_IDS,
    )

    msg_batch_update = composer.msg_grant_typed(
        granter = granter_address.to_acc_bech32(),
        grantee = GRANTEE_PUBLIC_INJECTIVE_ADDRESS,
        msg_type = "BatchUpdateOrdersAuthz",
        expiration_time_seconds=GRANT_EXPIRATION_IN_DAYS * SECONDS_PER_DAY,
        subaccount_id=granter_subaccount_id,
        spot_markets=SPOT_MARKET_IDS,
        derivative_markets=DERIVATIVE_MARKET_IDS,
    )

    # broadcast the transaction
    result = await message_broadcaster.broadcast([msg_spot_market, msg_derivative_market, msg_batch_update])
    print("---Transaction Response---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
