import asyncio
from getpass import getpass
import argparse

from pyinjective.async_client import AsyncClient
from pyinjective.core.network import Network
from pyinjective.transaction import Transaction
from pyinjective.wallet import PrivateKey

# Fixed values, do not change
SECONDS_PER_DAY = 60 * 60 * 24

parser = argparse.ArgumentParser(
    description='Delegate Injective funds for trading.',
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--network', type=str, default='mainnet')
parser.add_argument('--grantee_address', type=str, required=True)
parser.add_argument('--granter_subaccount_index', type=int, default=0)
parser.add_argument('--grant_expiration_days',
                    type=int,
                    default=365,
                    help='Expiration of the grant (in days)')
parser.add_argument(
    '--spot_market_ids',
    type=str,
    help=
    'Comma-separated list of spot market IDs to accept (see: mainnet: https://lcd.injective.network/injective/exchange/v1beta1/spot/markets testnet: https://k8s.testnet.lcd.injective.network/injective/exchange/v1beta1/spot/markets)'
)
parser.add_argument(
    '--derivative_market_ids',
    type=str,
    help=
    'Comma-separated list of derivative market IDs to accept (see: mainnet: https://lcd.injective.network/injective/exchange/v1beta1/derivative/markets testnet: https://k8s.testnet.lcd.injective.network/injective/exchange/v1beta1/derivative/markets)'
)


async def main() -> None:
    args = parser.parse_args()
    network = None
    if args.network == 'mainnet':
        network = Network.mainnet()
    elif args.network == 'testnet':
        network = Network.testnet()

    if args.spot_market_ids == None:
        spot_market_ids = []
    else:
        spot_market_ids = args.spot_market_ids.split(",")

    if args.derivative_market_ids == None:
        derivative_market_ids = []
    else:
        derivative_market_ids = args.derivative_market_ids.split(",")

    assert len(spot_market_ids) > 0 or len(
        derivative_market_ids
    ) > 0, "You need to select at least 1 derivative or spot market!"

    GRANTER_ACCOUNT_PRIVATE_KEY = getpass("Granter private key: ")
    # initialize grpc client
    client = AsyncClient(network)
    composer = await client.composer()
    await client.sync_timeout_height()
    # load account
    if GRANTER_ACCOUNT_PRIVATE_KEY.index(" ") == -1:
        granter_private_key = PrivateKey.from_hex(GRANTER_ACCOUNT_PRIVATE_KEY)
    else:
        # Seed phrase
        granter_private_key = PrivateKey.from_mnemonic(
            GRANTER_ACCOUNT_PRIVATE_KEY)

    granter_public_key = granter_private_key.to_public_key()
    granter_address = granter_public_key.to_address()
    print(f"Granter address: {granter_address.to_acc_bech32()}")
    account = await client.fetch_account(granter_address.to_acc_bech32())
    granter_subaccount_id = granter_address.get_subaccount_id(
        index=args.granter_subaccount_index)

    messages = []

    if len(spot_market_ids) > 0:
        msg_spot_market = composer.MsgGrantTyped(
            granter=granter_address.to_acc_bech32(),
            grantee=args.grantee_address,
            msg_type="CreateSpotMarketOrderAuthz",
            expire_in=args.grant_expiration_days * SECONDS_PER_DAY,
            subaccount_id=granter_subaccount_id,
            market_ids=spot_market_ids,
        )
        messages.append(msg_spot_market)

    if len(derivative_market_ids) > 0:
        msg_derivative_market = composer.MsgGrantTyped(
            granter=granter_address.to_acc_bech32(),
            grantee=args.grantee_address,
            msg_type="CreateDerivativeMarketOrderAuthz",
            expire_in=args.grant_expiration_days * SECONDS_PER_DAY,
            subaccount_id=granter_subaccount_id,
            market_ids=derivative_market_ids,
        )
        messages.append(msg_derivative_market)

    msg_batch_update = composer.MsgGrantTyped(
        granter=granter_address.to_acc_bech32(),
        grantee=args.grantee_address,
        msg_type="BatchUpdateOrdersAuthz",
        expire_in=args.grant_expiration_days * SECONDS_PER_DAY,
        subaccount_id=granter_subaccount_id,
        spot_markets=spot_market_ids,
        derivative_markets=derivative_market_ids,
    )
    messages.append(msg_batch_update)

    tx = (Transaction().with_messages(*messages).with_sequence(
        client.get_sequence()).with_account_num(
            client.get_number()).with_chain_id(network.chain_id))
    sim_sign_doc = tx.get_sign_doc(granter_public_key)
    sim_sig = granter_private_key.sign(sim_sign_doc.SerializeToString())
    sim_tx_raw_bytes = tx.get_tx_data(sim_sig, granter_public_key)

    # simulate tx
    sim_res = await client.simulate(sim_tx_raw_bytes)

    # build tx
    gas_price = 500000000
    gas_limit = int(sim_res['gasInfo']['gasUsed']) + 50000
    gas_fee = "{:.18f}".format(
        (gas_price * gas_limit) / pow(10, 18)).rstrip("0")
    fee = [
        composer.coin(
            amount=gas_price * gas_limit,
            denom=network.fee_denom,
        )
    ]

    tx = tx.with_gas(gas_limit).with_fee(fee).with_memo(
        "").with_timeout_height(client.timeout_height)
    sign_doc = tx.get_sign_doc(granter_public_key)
    sig = granter_private_key.sign(sign_doc.SerializeToString())
    tx_raw_bytes = tx.get_tx_data(sig, granter_public_key)

    res = await client.broadcast_tx_sync_mode(tx_raw_bytes)
    print(res)
    print("gas wanted: {}".format(gas_limit))
    print("gas fee: {} INJ".format(gas_fee))


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
