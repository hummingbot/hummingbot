import os
import numpy
import datetime
from pysui import handle_result
from pysui.sui.sui_txn import SyncTransaction
from sui_client_config import client, cfg
from pysui.sui.sui_types.address import SuiAddress
from pysui.sui.sui_types.scalars import ObjectID, SuiU64, SuiBoolean, SuiU8
from dotenv import load_dotenv
from numpy.random import Generator, PCG64

load_dotenv()


class DeepbookConnector:
    def __init__(self, client, cfg):
        self.client = client
        self.cfg = cfg
        self.package_id = os.getenv("TESTNET_PACKAGE_ID")
        self.pool_object_id = os.getenv("POOL_OBJECT_ID")

    def create_account(self):
        coin_to_split = "0xcd562ff3ccd7ea887f3c10a5641f1529371367afc0aea97ec0467d3749641022"
        txn = SyncTransaction(client=client)
        account_cap = txn.move_call(target=f"{self.package_id}::clob_v2::create_account", arguments=[], )
        txn.transfer_objects(transfers=[account_cap], recipient=self.cfg.active_address, )
        tx_result = handle_result(txn.execute(gas_budget="10000000"))
        print(tx_result.to_json(indent=4))

    def deposit_base(self, account_cap="0x37f5c9ae948df3e6363b0c28e8777deea60ea7066c8ae5d2582ce91bd55930d5"):
        coin_to_split = "0xcd562ff3ccd7ea887f3c10a5641f1529371367afc0aea97ec0467d3749641022"

        # TODO: add case for sponsoredTransaction
        txn = SyncTransaction(client=client)
        txn.move_call(target=f"{self.package_id}::clob_v2::deposit_base", arguments=[ObjectID(self.pool_object_id), txn.split_coin(coin=coin_to_split, amounts=[1000000000]), ObjectID(account_cap)],
                      type_arguments=["0x2::sui::SUI", f"{self.package_id}::realusdc::REALUSDC", ], )

        tx_result = handle_result(txn.execute(gas_budget="10000000"))
        print(tx_result.to_json(indent=4))

    # WIP
    def place_limit_order(self, price = 1000000000, quantity=1000000000, is_bid=True, account_cap="0x37f5c9ae948df3e6363b0c28e8777deea60ea7066c8ae5d2582ce91bd55930d5"):

        # TODO: add case for sponsoredTransaction
        txn = SyncTransaction(client=client)
        txn.move_call(target=f"{self.package_id}::clob_v2::place_limit_order", arguments=[
            ObjectID(self.pool_object_id),
            SuiU64(numpy.random.Generator(PCG64()).integers(1, 100000000, size=1)),
            SuiU64(price), SuiU64(quantity),
            SuiU8(0),
            SuiBoolean(is_bid), SuiU64(round(int(datetime.datetime.utcnow().timestamp())*1000 + 24*60*60*1000)), SuiU8(1),
            ObjectID("0x6"),
            ObjectID(account_cap)],
                      type_arguments=["0x2::sui::SUI", f"{self.package_id}::realusdc::REALUSDC", ], )
        tx_result = handle_result(txn.execute(gas_budget="10000000"))
        print(tx_result.to_json(indent=4))

    # WIP
    def get_level2_book_status_bid_side(self):
        txn = SyncTransaction(client=client)
        return_value = txn.move_call(target=f"{self.package_id}::clob_v2::get_level2_book_status_bid_side", arguments=[ObjectID(self.pool_object_id), SuiU64(10000000),SuiU64(100000000000),
            ])
        result = handle_result(txn.inspect_all())
        print(return_value)
        print(result)


if __name__ == "__main__":
    connector = DeepbookConnector(client, cfg)
    connector.deposit_base()
    connector.place_limit_order()
