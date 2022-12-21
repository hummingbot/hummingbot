# This is an application similar screener and it only tries to provide you with some good insight by looking and comparing different trading pairs in an exchange
# By default the format_status command refreshes at .1 seconds, so I recommend changing it to 10 or bigger number for this script to run without any issues.
# You can go to the line 144 in status_command.py file and update the number to 10
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase
import pandas as pd
from binance.client import Client
from hummingbot.core.data_type.common import PriceType

class IdentifyOpportunity(ScriptStrategyBase):
    """
    This example shows how to add a custom format_status to a strategy and query the order book.
    Run the command status --live, once the strategy starts.
    """

    exchange = "binance_us_paper_trade"
    top_nrows=int(5)
	
	#Below are binance_us api_key and secrets I used to get all the assets from the exchange
    api_key = <api_key>
    api_secret = <api_secret>



    client = Client(api_key, api_secret, tld='us')

    #Below section of the code gives us all the assets that are tradable
    columns = ['symbol','baseAsset','quoteAsset','permissions','ocoAllowed','isMarginTradingAllowed','isSpotTradingAllowed']
    tradable_assets=[]
    for i in client.get_exchange_info()['symbols']:
      if (i['status']=='TRADING'):
        #print(list(map(i.get,columns)))
        tradable_assets.append(list(map(i.get,columns)))
    tradable_assets = pd.DataFrame(tradable_assets,columns=columns)
    tradable_assets_usd = tradable_assets[tradable_assets['quoteAsset']=='USD']
    # display(tradable_assets_usd)
    # print("Number of tickers that can be bought with Margin - {}".format(len(tradable_assets_usd[tradable_assets_usd['isMarginTradingAllowed']==True])))
         
        
    markets = {
        #"binance_us_paper_trade": (tradable_assets_usd['baseAsset']+'-'+tradable_assets_usd['quoteAsset']).to_list(),
        exchange : {"ETH-USD","BTC-USD","ATOM-USD"},
        # "kucoin_paper_trade": {"ETH-USDT","BTC-USDT"},
        # "gate_io_paper_trade": {"ETH-USDT"},
        #"coinbase_pro_paper_trade": {"ETH-USDT"},
        # "crypto_com_paper_trade": {"ETH-USDT"}
        #"ascend_ex_paper_trade": {"ETH-USDT"},
    }
    # price_source=PriceType.LastTrade
    

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []
        warning_lines = []
        warning_lines.extend(self.network_warning(self.get_market_trading_pair_tuples()))

        # balance_df = self.get_balance_df()
        # lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])
        market_status_df = self.get_market_status_df_with_depth()

        market_status_df_volume_sort=market_status_df.sort_values('Total Volume', ascending=False).head(self.top_nrows)

        lines.extend(["", "  Top tickers with high Volume:"] + ["    " + line for line in market_status_df_volume_sort.to_string(index=False).split("\n")])

        market_status_df_ask_bid_sort=market_status_df.sort_values('ask_bid_pc_basis', ascending=False).head(self.top_nrows)

        lines.extend(["", "  Top tickers with high ask-bid price spread percentage basis:"] + ["    " + line for line in market_status_df_ask_bid_sort.to_string(index=False).split("\n")])

        market_status_df_mid_last_sort=market_status_df.sort_values('mid_last_pc_basis', ascending=False).head(self.top_nrows)

        lines.extend(["", "  Top tickers with high mid-last price spread percentage basis:"] + ["    " + line for line in market_status_df_mid_last_sort.to_string(index=False).split("\n")])

        market_status_df_ask_bid_volume_sort_desc=market_status_df.sort_values('ask_bid_volume_pc_basis', ascending=False).head(self.top_nrows)

        lines.extend(["", "  Top tickers with high ask-bid volume spread percentage basis:"] + ["    " + line for line in market_status_df_ask_bid_volume_sort_desc.to_string(index=False).split("\n")])

        market_status_df_ask_bid_volume_sort_asc=market_status_df.sort_values('ask_bid_volume_pc_basis', ascending=True).head(self.top_nrows)

        lines.extend(["", "  Top tickers with low ask-bid volume spread percentage basis:"] + ["    " + line for line in market_status_df_ask_bid_volume_sort_asc.to_string(index=False).split("\n")])

        #warning_lines.extend(self.balance_warning(self.get_market_trading_pair_tuples()))
        if len(warning_lines) > 0:
            lines.extend(["", "*** WARNINGS ***"] + warning_lines)
        return "\n".join(lines)

    def get_market_status_df_with_depth(self):
        market_status_df = self.market_status_data_frame(self.get_market_trading_pair_tuples())
        market_status_df["Exchange"] = market_status_df.apply(lambda x: x["Exchange"].strip("PaperTrade") + "paper_trade", axis=1)
        market_status_df["Volume (+1%)"] = market_status_df.apply(lambda x: self.get_volume_for_percentage_from_mid_price(x, 0.01), axis=1)
        market_status_df["Volume (-1%)"] = market_status_df.apply(lambda x: self.get_volume_for_percentage_from_mid_price(x, -0.01), axis=1)
        market_status_df["Total Volume"] = market_status_df["Volume (+1%)"] + market_status_df["Volume (-1%)"]
        market_status_df["ask_bid_pc_basis"] = (market_status_df['Best Ask Price'] - market_status_df['Best Bid Price'])*10000 / market_status_df['Best Bid Price']
        market_status_df["Last Trade Price"] = market_status_df.apply(lambda x: float(self.get_lasttrade_price(x)), axis=1)
        market_status_df["mid_last_pc_basis"] = (round(market_status_df["Mid Price"],3) - round(market_status_df["Last Trade Price"],3))*10000 / round(market_status_df["Last Trade Price"],3)
        market_status_df["ask_bid_volume_pc_basis"] = (market_status_df["Volume (+1%)"] - market_status_df["Volume (-1%)"])*10000 / market_status_df["Volume (-1%)"]
        return market_status_df

    def get_volume_for_percentage_from_mid_price(self, row, percentage):
        price = row["Mid Price"] * (1 + percentage)
        is_buy = percentage > 0
        result = self.connectors[row["Exchange"]].get_quote_volume_for_base_amount(row["Market"], is_buy, price)
        return round(result.result_volume)

    def get_lasttrade_price(self, row):
        
        return round(self.connectors[row["Exchange"]].get_price_by_type(row["Market"], PriceType.LastTrade),3)

