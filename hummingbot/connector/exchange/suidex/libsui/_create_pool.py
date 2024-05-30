import os

from dotenv import load_dotenv
from pysui import handle_result
from pysui.sui.sui_txn import SyncTransaction

# from pysui.sui.sui_types.address import SuiAddress
from pysui.sui.sui_types.scalars import ObjectID, SuiU64

from hummingbot.connector.exchange.suidex.libsui._sui_client_config import cfg, client

load_dotenv()

network = "localnet"


def create_pool():
    """Creates a pool with REALUSDC and SUI"""

    if network == "testnet":
        package_id = os.getenv("TESTNET_PACKAGE_ID")
    elif network == "localnet":
        package_id = os.getenv("LOCALNET_PACKAGE_ID")
    else:
        raise ValueError("Network not supported")

    # TODO: add case for sponsoredTransaction
    txn = SyncTransaction(client=client)

    # TODO: get SUI coin objects using gql
    # Retrieved somehow
    # coin_to_split = "0xfa50148afdbbaadb5bd509600845c7f01001ef1dd52f8d880548aaf1444e47e1"  # noqa: mock
    # txn.transfer_objects(transfers=[txn.split_coin(coin=coin_to_split, amounts=[1000000000])], recipient=cfg.active_address)
    # txn.split_coin(coin=coin_to_split, amounts=[1000000000])
    # gas_object = txn.split_coin_and_return(coin=coin_to_split, split_count=2)

    returned_pool = txn.move_call(
        target=f"{package_id}::clob_v2::create_pool_with_return",
        arguments=[SuiU64("100000"), SuiU64("100000"), txn.split_coin(coin=txn.gas, amounts=[1000000000])],
        type_arguments=[
            "0x2::sui::SUI",
            f"{package_id}::realusdc::REALUSDC",
        ],
    )
    txn.transfer_objects(
        transfers=[returned_pool],
        recipient=cfg.active_address,
    )
    tx_result = handle_result(txn.execute(gas_budget="10000000"))

    print(tx_result.to_json(indent=2))


if __name__ == "__main__":
    create_pool()
