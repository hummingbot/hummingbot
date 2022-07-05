from scalecodec.base import RuntimeConfigurationObject
from scalecodec.type_registry import load_type_registry_preset
from substrateinterface import SubstrateInterface

from hummingbot.connector.exchange.polkadex.polkadex_constants import POLKADEX_SS58_PREFIX


def main():
    custom_types = {
        "types": {
            "AssetId": {
                "type": "enum",
                "type_mapping": [
                    ["polkadex", "Null"],
                    ["asset", "u128"],

                ]
            },
            "OrderPayload": {
                "type": "struct",
                "type_mapping": [
                    ["user", "AccountId"],
                    ["pair", "TradingPair"],
                    ["side", "OrderSide"],
                    ["order_type", "OrderType"],
                    ["qty", "u128"],
                    ["price", "u128"],
                    ["nonce", "u32"],
                ]
            },
            "CancelOrderPayload": {
                "type": "struct",
                "type_mapping": [
                    ["id", "String"]
                ]},
            "TradingPair": {
                "type": "struct",
                "type_mapping": [
                    ["base_asset", "AssetId"],
                    ["quote_asset", "AssetId"],
                ]
            },
            "OrderSide": {
                "type": "enum",
                "type_mapping": [
                    ["Ask", "Null"],
                    ["Bid", "Null"],
                ],
            },
            "OrderType": {
                "type": "enum",
                "type_mapping": [
                    ["LIMIT", "Null"],
                    ["MARKET", "Null"],
                ],
            },
        }
    }

    blockchain = SubstrateInterface(
        url="wss://blockchain.polkadex.trade",
        ss58_format=POLKADEX_SS58_PREFIX,
        type_registry=custom_types
    )

    runtime_config = RuntimeConfigurationObject(ss58_format=POLKADEX_SS58_PREFIX)
    runtime_config.update_type_registry(custom_types)

    print(create_order(runtime_config, 10, 100,
                       "LIMIT", "Bid", "eskmPnwDNLNCuZKa3aWuvNS6PshJoKsgBtwbdxyyipS2F2TR5", "polkadex", 1, 2))


def create_asset(asset):
    if asset == "polkadex":
        return {"polkadex": None}
    else:
        return {"asset": asset}


def cancel_order(runtime_config, order_id):
    cancel_req = {
        "id": str(order_id)
    }
    return runtime_config.create_scale_object("CancelOrderPayload").encode(cancel_req)

def create_order(runtime_config, price, qty, order_type, side, proxy, base, quote, nonce):
    order = {
        "user": proxy,
        "pair": {
            "base_asset": create_asset(base),
            "quote_asset": create_asset(quote)
        },
        "qty": qty,
        "price": price,
        "nonce": nonce
    }
    if order_type == "LIMIT":
        order["order_type"] = {"LIMIT": None}
    else:
        order["order_type"] = {"MARKET": None}

    if side == "Bid":
        order["side"] = {"Bid": None}
    else:
        order["side"] = {"Ask": None}

    print(order)
    return runtime_config.create_scale_object("OrderPayload").encode(order)





main()
