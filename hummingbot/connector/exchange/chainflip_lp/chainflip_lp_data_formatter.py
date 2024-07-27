import math
from typing import Dict, List, Literal, Any
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.connector.exchange.chainflip_lp import chainflip_lp_constants as CONSTANTS 


class DataFormatter:
    @classmethod
    def hex_str_to_int(cls, data: str):
        return int(data, 16)
    @classmethod
    def format_hex_balance(cls, balance:str, asset:Dict[str, str]):
        int_balance = cls.hex_str_to_int(balance)
        precision = cls.format_asset_precision(asset)
        return int_balance/precision
    @classmethod
    def format_amount(cls, amount: float| int, asset:Dict[str, str]):
        precision = cls.format_asset_precision(asset)
        long_amount = amount * precision
        return cls.int_to_hex_str(long_amount)
    @classmethod
    def format_price(
        cls, 
        price:int, 
        base_asset:Dict[str, str], 
        quote_asset:Dict[str, str], 
        sqrt_price = True
        ):
        """
        for example: to get the price of the ETH/USDC pair from the sqrt_price
        where the provided price is 4512835869581138250956800
        We Calculate:
        current_price = 4512835869581138250956800 / 2**96 
        current_price = current_price ** 2 (provided the price is a square-root price)
        formated_price = (current_price * base_asset_precision)/quote_asset_precision
        """
        base_precision = cls.format_asset_precision(base_asset)
        quote_precision = cls.format_asset_precision(quote_asset)
        current_price = price /(2 ** CONSTANTS.FRACTIONAL_BITS)
        if sqrt_price:
            current_price = current_price ** 2
        formated_price = (current_price * base_precision)/quote_precision
        return formated_price
    
    @classmethod
    def int_to_hex_str(cls, data: int):
        return str(hex(data))
    @classmethod
    def format_order_response(cls, response, base_asset, quote_asset):
        data = response["result"]
        limit_orders = data["limit_orders"]
        asks = []
        bids = []
        for order in limit_orders["asks"]:
            price = cls.format_hex_balance(
                order["original_sell_amount"],
                base_asset
            )
            tick = order["tick"]
            asks.append({
                "price": price,
                "tick": tick
            })
        for order in limit_orders["bids"]:
            price = cls.format_hex_balance(
                order["original_sell_amount"],
                quote_asset
            )
            tick = order["tick"]
            asks.append({
                "price": price,
                "tick": tick
            })
        return {
            "asks": asks,
            "bids": bids
        }
    @classmethod
    def format_balance_response(cls,response):
        data = response["result"]
        keys = data.keys()
        balance_map = {}
        for key in keys:
            for asset in data[key]:
                balance_map[asset["asset"]] = cls.format_hex_balance(
                    asset["balance"], {"chain":key, "asset":asset}
                )
        return balance_map
    @classmethod
    def format_all_market_response(cls, response):
        """
        return as a list of dict containing just base asset dict and quote asset dict
        """
        data:Dict = response["result"]["fees"]
        keys:List = data.keys()
        format_list = []
        for key in keys:
            chain = key
            for symbol in data[key]:
                try:

                    base_asset  = {"chain":chain, "asset": symbol}
                    quote_asset = data[key][symbol]["quote_asset"]
                    trading_symbol = cls.format_assets_to_market_symbol(base_asset, quote_asset)
                    format_list.append({
                        "symbol": trading_symbol,
                        "base_asset": base_asset,
                        "quote_asset": quote_asset
                    })
                except Exception:
                    continue
        return format_list
    @classmethod
    def format_all_assets_response(cls,response:Dict):
        result = response["result"]
        return result
    @classmethod
    def format_error_response(cls, response:Dict):
        # figure a better way to handle errors
        return None
    @classmethod
    def format_asset_precision(cls,asset:Dict[str,str]):
        precisions = CONSTANTS.ASSET_PRECISIONS
        if asset["chain"] in precisions.keys():
            asset_precision = precisions[asset["chain"]]
        else:
            asset_precision = precisions["Ethereum"]
        if asset["asset"] in CONSTANTS.STABLE_ASSETS:
            asset_precision = precisions["Stable"]
        return asset_precision
        
    @classmethod
    def format_orderbook_response(cls,response:Dict, base_asset:Dict[str,str], quote_asset:Dict[str,str]):
        data = response["result"]
        bids = list(
            map(
                lambda x: {
                    "amount": cls.format_hex_balance(
                        x["amount"],
                        base_asset
                        ),
                    "price": cls.format_price(
                        x["sqrt_price"],
                        base_asset,
                        quote_asset,
                        ),
                },
                data["bids"]
            
            )
            )
        asks = list(
            map(
                lambda x: {
                    "amount": cls.format_hex_balance(
                        x["amount"],
                        quote_asset
                        ),
                    "price": cls.format_price(
                        x["sqrt_price"],
                        base_asset,
                        quote_asset,
                    ),
                },
                data["asks"]
            
            )
            )
        format_data = {
            "bids": bids,
            "asks": asks
        }
        return format_data
    @classmethod
    def format_supported_assets(cls, all_pairs:List[Dict[str, str]]):
        """
        format the trading pair list of dict to a list of string in
        the format of {base_asset}-{quote-asset} 
        """
        pairs = []
        for pair in all_pairs:
            pairs.append(cls.format_assets_to_market_symbol(
                pair["base_asset"],
                pair["quote_asset"]
            ))
        return pairs


    @classmethod
    def format_trading_pair(cls, pair:str, all_assets:List[Dict[str, str]]):
        """
        format a trading pair from {base_asset}-{quote_asset}
        to the format needed for lp rpc calls
        e.g ETH-USDT => 
        {
            "base_asset":{"chain":"Ethereum","asset":"ETH"},
            "quote_asset":{"chain":"Ethereum","asset":"USDT"},
        }
        """
        data = {}
        base_asset, quote_asset = pair.split("-")
        base_asset_list = list(
            filter(
                lambda x: x["asset"].upper() == base_asset.upper(),
                all_assets
            )
        )
        quote_asset_list = list(
            filter(
                lambda x: x["asset"].upper() == quote_asset.upper(),
                all_assets
            )
        )
        data["base_asset"] = base_asset_list[0] if base_asset_list else None
        data["quote_asset"] = quote_asset_list[0] if quote_asset_list else None

        return data
    @classmethod
    def format_symbol_list(cls, all_assets:List[Dict[str, str]]):
        """
        returns a list of just the symbols e.g ["ETH","USDT","BTC"]
        """
        return list(map(lambda x: x["asset"], all_assets))
    @classmethod
    def format_market_pairs(cls, all_market:List[Dict[str,Dict]]):
        """
        Convert our symbol to HB Symbol
        """
        format_list = []
        for market in all_market:
            base_asset = market["base_asset"]["asset"]
            quote_asset  = market["quote_asset"]["asset"]
            format_list.append(
                combine_to_hb_trading_pair(base_asset, quote_asset)
            )
        return format_list
    @classmethod
    def format_market_price(cls, response:Dict[str,Any]):
        """
        return the float formatted price
        """
        data = response["result"]
        base_asset = data["base_asset"]
        quote_asset = data["quote_asset"]
        sell_price = cls.hex_str_to_int(data["sell"])
        buy_price = cls.hex_str_to_int(data["buy"])
        formatted_buy_price = cls.format_price(
            buy_price, base_asset, quote_asset
        )
        formatted_sell_price = cls.format_price(
            sell_price, base_asset, quote_asset
        )
        normal_price = (formatted_buy_price + formatted_sell_price)/2
        formatted_data = {
            "buy": formatted_buy_price,
            "sell": formatted_sell_price,
            "price": normal_price
        }
        return formatted_data
    @classmethod
    def format_assets_to_market_symbol(
        cls, 
        base_asset:Dict[str, str], 
        quote_asset:Dict[str, str]
    ):
        base = base_asset["asset"]
        quote = quote_asset["asset"]
        return f'{base}-{quote}'
    # @classmethod
    # def convert_tick_to_price(
    #     cls,  
    #     tick: int,
    #     base_asset:Dict[str, str],
    #     quote_asset:Dict[str, str]
    # ):
    #     base_precision = cls.format_asset_precision(base_asset)
    #     quote_precision = cls.format_asset_precision(quote_asset)
    #     log_price = tick / math.log()



        
