import os

from dotenv import load_dotenv
from pysui import handle_result
from pysui.sui.sui_txn import SyncTransaction
from pysui.sui.sui_types.scalars import SuiU64
from sui_client_config import cfg, client

load_dotenv()


def create_pool():
    """Creates a pool with REALUSDC and SUI"""

    # package_id = os.getenv("TESTNET_PACKAGE_ID")
    package_id = os.getenv("LOCALNET_PACKAGE_ID")

    # TODO: add case for sponsoredTransaction
    txn = SyncTransaction(client=client)

    # TODO: get SUI coin objects using gql
    coin_to_split = (
        "0x0abd6f0eea07c1d7498c2c3f0b64256b8bb579774cf164d0f2c2e73b9274e992"  # noqa: mock  // TODO: retrieve somehow
    )
    # txn.transfer_objects(transfers=[txn.split_coin(coin=coin_to_split, amounts=[1000000000])], recipient=cfg.active_address)
    # txn.split_coin(coin=coin_to_split, amounts=[1000000000])
    # gas_object = txn.split_coin_and_return(coin=coin_to_split, split_count=2)

    returned_pool = txn.move_call(
        target=f"{package_id}::clob_v2::create_pool_with_return",
        arguments=[
            SuiU64("100000"),
            SuiU64("100000"),
            txn.split_coin(coin=coin_to_split, amounts=[1000000000]),
        ],
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
