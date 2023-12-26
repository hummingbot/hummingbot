import asyncio
import copy
import json
import logging
import random
import time
from collections import Counter
from decimal import Decimal
from typing import Dict

import aiohttp
from aiohttp_socks import ProxyConnector

from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.core.data_type.common import OrderType, PositionAction, PriceType
from hummingbot.core.utils.async_utils import safe_gather
from hummingbot.strategy.script_strategy_base import ScriptStrategyBase

from .hashkey_trade.api import web_headers_template
from .hashkey_trade.async_total import get_assets, get_trades
from .hashkey_trade.models import Account, Side
from .hashkey_trade.utils import generate_random_str, get_account


class MakeManualTrades(ScriptStrategyBase):
    # Parameters to modify -----------------------------------------
    asset = "BTC"
    trading_pair = "BTC-USD"
    trading_symbol = "BTCUSD"
    exchange = "hashkey"
    hedging_exchange = "binance_perpetual"
    hedging_trading_pair = "BTC-USDT"
    order_amount = Decimal(0.008)
    spread_threshold = Decimal(10)
    trade_interval = 20
    # Optional ----------------------
    order_type = "market"
    price_source = PriceType.MidPrice
    ask_source = PriceType.BestAsk
    bid_source = PriceType.BestBid
    account1_id = "H009"
    account2_id = "H006"
    max_trades = 500
    max_amount = 133340
    # ----------------------------------------------------------------

    markets = {
        exchange: {trading_pair},
        hedging_exchange: {hedging_trading_pair}
    }
    create_timestamp = 0
    start_init = False
    ping_pong = False

    def __init__(self, connectors: Dict[str, ConnectorBase]):
        super().__init__(connectors)
        try:
            self.account1 = get_account(self.account1_id)
            self.account2 = get_account(self.account2_id)
            self.trade_counter = Counter()
            self.amount_counter = Counter()
            asyncio.create_task(self.init_counter())
        except Exception as e:
            self.logger().error(e)

    async def init_counter(self):
        for trade_result in await safe_gather(*[get_trades(self.account1), get_trades(self.account2)], return_exceptions=True):
            if isinstance(trade_result, Exception):
                self.logger().error(f"Init trade counter error: {trade_result}")
                continue

            account_id, total_usdt, order_count = trade_result
            self.logger().info(f"账号{account_id}已交易{order_count}笔 共计{int(total_usdt)}U")
            self.trade_counter[account_id] += order_count
            self.amount_counter[account_id] += total_usdt

    def on_stop(self):
        self.close_open_positions()

    def finish(self):
        HummingbotApplication.main_application().stop()

    def on_tick(self):
        if not self.start_init:
            self.open_positions()
            self.start_init = True

        if self.check_finish():
            self.finish()
            return

        best_ask = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.ask_source)
        best_bid = self.connectors[self.exchange].get_price_by_type(self.trading_pair, self.bid_source)
        ask_result = self.connectors[self.exchange].get_price_for_volume(self.trading_pair, True, self.order_amount)
        bid_result = self.connectors[self.exchange].get_price_for_volume(self.trading_pair, False, self.order_amount)
        self.logger().info(f"Best ask: {best_ask}, Best bid: {best_bid}")
        self.logger().info(f"Cost: {ask_result.result_price - bid_result.result_price}")
        self.display_account(self.account1)
        self.display_account(self.account2)

        if ask_result.result_price - bid_result.result_price <= self.spread_threshold:
            if self.create_timestamp <= self.current_timestamp:
                self.place_order()

    def check_finish(self):
        account1_order_count = self.trade_counter[self.account1_id]
        account2_order_count = self.trade_counter[self.account2_id]
        account1_amount_count = self.amount_counter[self.account1_id]
        account2_amount_count = self.amount_counter[self.account2_id]

        if account1_order_count >= self.max_trades and account2_order_count >= self.max_trades:
            self.logger().info(f"账号{self.account1_id}已交易{account1_order_count}笔 共计{int(account1_amount_count)}U")
            self.logger().info(f"账号{self.account2_id}已交易{account2_order_count}笔 共计{int(account2_amount_count)}U")
            return True

        if account1_amount_count >= self.max_amount and account2_amount_count >= self.max_amount:
            self.logger().info(f"账号{self.account1_id}已交易{account1_order_count}笔 共计{int(account1_amount_count)}U")
            self.logger().info(f"账号{self.account2_id}已交易{account2_order_count}笔 共计{int(account2_amount_count)}U")
            return True

        return False

    def display_account(self, account: Account):
        account_order_count = self.trade_counter[account.id]
        account_amount_count = self.amount_counter[account.id]
        self.logger().info(f"账号{account.id}已交易{account_order_count}笔 共计{int(account_amount_count)}U")

    def place_order(self):
        self.place_two_orders()
        self.ping_pong = not self.ping_pong

        next_cycle = self.current_timestamp + random.randint(int(self.trade_interval * 0.8), self.trade_interval)
        if self.create_timestamp <= self.current_timestamp:
            self.create_timestamp = next_cycle

    def place_two_orders(self):
        if self.ping_pong:
            tasks = [
                self.trade_to_target(self.account1, self.order_amount),
                self.trade_to_target(self.account2, Decimal(0.0))
            ]
        else:
            tasks = [
                self.trade_to_target(self.account1, Decimal(0.0)),
                self.trade_to_target(self.account2, self.order_amount)
            ]
        asyncio.create_task(safe_gather(*tasks))

    def open_positions(self):
        self.sell(
            connector_name=self.hedging_exchange,
            trading_pair=self.hedging_trading_pair,
            amount=self.order_amount,
            order_type=OrderType.MARKET,
            position_action=PositionAction.OPEN,
        )

        asyncio.create_task(safe_gather(*[
            self.trade_to_target(self.account1, self.order_amount),
            self.trade_to_target(self.account2, Decimal(0.0))
        ]))

    def close_open_positions(self):
        for trading_pair, position in self.connectors[self.hedging_exchange].account_positions.items():
            if trading_pair in self.markets[self.hedging_exchange]:
                self.buy(
                    connector_name=self.hedging_exchange,
                    trading_pair=position.trading_pair,
                    amount=self.order_amount,
                    order_type=OrderType.MARKET,
                    price=self.connectors[self.hedging_exchange].get_mid_price(position.trading_pair),
                    position_action=PositionAction.CLOSE)

        asyncio.create_task(safe_gather(*[
            self.trade_to_target(self.account1, Decimal(0.0)),
            self.trade_to_target(self.account2, Decimal(0.0))
        ]))

    def format_status(self) -> str:
        """
        Returns status of the current strategy on user balances and current active orders. This function is called
        when status command is issued. Override this function to create custom status display output.
        """
        if not self.ready_to_trade:
            return "Market connectors are not ready."
        lines = []

        balance_df = self.get_balance_df()
        lines.extend(["", "  Balances:"] + ["    " + line for line in balance_df.to_string(index=False).split("\n")])

        return "\n".join(lines)

    async def trade_to_target(self, account: Account, target_amount: Decimal):
        asset = await self.get_account_asset(account)

        trade_amount = target_amount - asset
        if trade_amount > 0:
            await self.do_manual_trade(account, Side.BUY, trade_amount)
        elif trade_amount < 0:
            await self.do_manual_trade(account, Side.SELL, abs(trade_amount))

    async def do_manual_trade(self, account: Account, side: Side, quantity: float):
        now = int(time.time() * 1000)

        headers = copy.deepcopy(web_headers_template)
        headers["Device-Id"] = account.device_id
        headers["Cookie"] = account.cookie

        buy_url = "https://bapi-pro.hashkey.com/api/v1.1/order/create?r={}&c_token={}".format(
            generate_random_str(11), account.token
        )

        # form-data格式的数据
        buy_data = {
            "quantity": round(float(quantity), 6),
            "type": "market",
            "side": side.value,
            "symbol_id": self.trading_symbol,
            "client_order_id": str(now),
            "confirm_acr": 1,
        }
        connector = ProxyConnector.from_url(account.proxy)
        async with aiohttp.ClientSession(connector=connector) as session:
            retries = 3
            trade_qty = 0

            while retries > 0:
                try:
                    async with session.post(buy_url, data=buy_data, headers=headers) as response:
                        # 打印响应内容
                        data = await response.json()
                        if "orderId" not in data:
                            self.logger().error(f"账号{account.id}{side.alias}异常: {data['msg']}")
                            raise Exception("TRADE ERROR")

                        if data["status"] == "FILLED":
                            self.logger().info(f"账号{account.id}成功{side.alias}{data['executedQty']}个{data['baseTokenName']}")
                            trade_qty = float(data['executedQty'])
                        elif data["status"] == "PARTIALLY_CANCELED":
                            lack = float(quantity) - float(data['executedQty'])
                            self.log_with_clock(
                                logging.INFO,
                                f"账号{account.id}{side.alias}{data['executedQty']}个{data['baseTokenName']}，还缺少{lack}，继续{side.alias}"
                            )
                            time.sleep(3)
                            trade_qty = float(data['executedQty']) + await self.do_manual_trade(
                                account, side, lack)
                        else:
                            self.logger().error(f"账号{account.id}{side.alias}异常: {json.dumps(data)}")
                            raise Exception("TRADE ERROR")

                        self.trade_counter[account.id] += 1
                        self.amount_counter[account.id] += float(data['executedAmount'])
                except Exception as e:
                    self.logger().error(f"请求异常{e}, retries: {retries}")
                    retries -= 1
                    time.sleep(3)

                return trade_qty

    async def get_account_asset(self, account: Account):
        retries = 3

        while retries > 0:
            asset_result = await get_assets(account)

            if isinstance(asset_result, Exception):
                self.logger().error(f"Init trade counter error: {asset_result}")
                retries -= 1
                continue

            _, assets = asset_result
            for asset in assets:
                if asset["tokenName"] == self.asset:
                    return Decimal(asset['total'])

            return Decimal(0.0)
