import asyncio

from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network
from pyinjective.transaction import Transaction
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
    client = AsyncClient(NETWORK, insecure=False)
    composer = await client.composer()
    await client.sync_timeout_height()

    # load account
    granter_private_key = PrivateKey.from_hex(GRANTER_ACCOUNT_PRIVATE_KEY)
    granter_public_key = granter_private_key.to_public_key()
    granter_address = granter_public_key.to_address()
    account = await client.get_account(granter_address.to_acc_bech32())  # noqa: F841
    granter_subaccount_id = granter_address.get_subaccount_id(index=GRANTER_SUBACCOUNT_INDEX)

    msg_spot_market = composer.MsgGrantTyped(
        granter=granter_address.to_acc_bech32(),
        grantee=GRANTEE_PUBLIC_INJECTIVE_ADDRESS,
        msg_type="CreateSpotMarketOrderAuthz",
        expire_in=GRANT_EXPIRATION_IN_DAYS * SECONDS_PER_DAY,
        subaccount_id=granter_subaccount_id,
        market_ids=SPOT_MARKET_IDS,
    )

    msg_derivative_market = composer.MsgGrantTyped(
        granter=granter_address.to_acc_bech32(),
        grantee=GRANTEE_PUBLIC_INJECTIVE_ADDRESS,
        msg_type="CreateDerivativeMarketOrderAuthz",
        expire_in=GRANT_EXPIRATION_IN_DAYS * SECONDS_PER_DAY,
        subaccount_id=granter_subaccount_id,
        market_ids=DERIVATIVE_MARKET_IDS,
    )

    msg_batch_update = composer.MsgGrantTyped(
        granter = granter_address.to_acc_bech32(),
        grantee = GRANTEE_PUBLIC_INJECTIVE_ADDRESS,
        msg_type = "BatchUpdateOrdersAuthz",
        expire_in=GRANT_EXPIRATION_IN_DAYS * SECONDS_PER_DAY,
        subaccount_id=granter_subaccount_id,
        spot_markets=SPOT_MARKET_IDS,
        derivative_markets=DERIVATIVE_MARKET_IDS,
    )

    tx = (
        Transaction()
        .with_messages(msg_spot_market, msg_derivative_market, msg_batch_update)
        .with_sequence(client.get_sequence())
        .with_account_num(client.get_number())
        .with_chain_id(NETWORK.chain_id)
    )
    sim_sign_doc = tx.get_sign_doc(granter_public_key)
    sim_sig = granter_private_key.sign(sim_sign_doc.SerializeToString())
    sim_tx_raw_bytes = tx.get_tx_data(sim_sig, granter_public_key)

    # simulate tx
    (sim_res, success) = await client.simulate_tx(sim_tx_raw_bytes)
    if not success:
        print(sim_res)
        return

    # build tx
    gas_price = 500000000
    gas_limit = sim_res.gas_info.gas_used + 20000
    gas_fee = "{:.18f}".format((gas_price * gas_limit) / pow(10, 18)).rstrip("0")
    fee = [composer.coin(
        amount=gas_price * gas_limit,
        denom=NETWORK.fee_denom,
    )]

    tx = tx.with_gas(gas_limit).with_fee(fee).with_memo("").with_timeout_height(client.timeout_height)
    sign_doc = tx.get_sign_doc(granter_public_key)
    sig = granter_private_key.sign(sign_doc.SerializeToString())
    tx_raw_bytes = tx.get_tx_data(sig, granter_public_key)

    res = await client.send_tx_sync_mode(tx_raw_bytes)
    print(res)
    print("gas wanted: {}".format(gas_limit))
    print("gas fee: {} INJ".format(gas_fee))


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
