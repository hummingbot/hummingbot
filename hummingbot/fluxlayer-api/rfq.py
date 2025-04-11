import requests
import time
from datetime import datetime
import sys
import os
import asyncio
current_file_path = os.path.abspath(__file__)

project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

# 将项目根目录添加到 Python 路径
sys.path.append(project_root)

from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.client.hummingbot_application import HummingbotApplication

# binance_price_url = "https://api.binance.com/api/v3/depth"
# money_depth = 10000

# def get_order_book(symbol='BTCUSDT', limit=100):
#     """获取币安深度数据"""
#     try:
#         response = requests.get(binance_price_url, params={'symbol': symbol, 'limit': limit})
#         response.raise_for_status()
#         return response.json()
#     except Exception as e:
#         print(f"Error getting depth data: {e}")
#         return None
    
async def get_order_book_hummingbot(symbol='BTCUSDT', limit=100):
    # bbb = get_order_book()
    # print("bbbb", bbb)
    app = HummingbotApplication.main_application()
    client_config_map = app.client_config_map
    binance_exchange_obj = BinanceExchange(
        client_config_map=client_config_map,
        binance_api_key="",
        binance_api_secret="",
    )
    order_book_data_source = binance_exchange_obj._create_order_book_data_source()
    snapshot_msg = await order_book_data_source._order_book_snapshot(symbol)
    json_data = {
        'lastUpdateId': snapshot_msg.timestamp,
        'bids': snapshot_msg.content["bids"],
        'asks': snapshot_msg.content["asks"],
    }
    # print("aaaa", json_data)
    return json_data


def calculate_price_impact(asks, budget_usdt=10000):
    """计算指定预算对价格的影响"""
    remaining_budget = budget_usdt
    total_btc = 0
    last_price = None
    executed_orders = []

    for price_str, qty_str in asks:
        if remaining_budget <= 0:
            break

        price = float(price_str)
        qty = float(qty_str)
        order_value = price * qty

        if order_value <= remaining_budget:
            # 全量吃单
            remaining_budget -= order_value
            total_btc += qty
            executed_orders.append((price, qty))
            last_price = price
        else:
            # 部分吃单
            executable_qty = remaining_budget / price
            total_btc += executable_qty
            executed_orders.append((price, executable_qty))
            remaining_budget = 0
            last_price = price

    return {
        'final_price': last_price,
        'total_btc': total_btc,
        'average_price': budget_usdt / total_btc if total_btc > 0 else None,
        'price_impact': (last_price - float(asks[0][0])) / float(asks[0][0]) * 100
    }

async def rfq_demo():
    while True:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 获取订单簿数据
        order_book = await get_order_book_hummingbot()
        # return
        if not order_book:
            time.sleep(1)
            continue

        # 获取实时价格
        spot_price = float(order_book['asks'][0][0])  # 最佳卖价作为当前价格

        # 计算价格影响
        analysis = calculate_price_impact(order_book['asks'], money_depth)

        total_btc = analysis['total_btc']
        final_price = analysis['final_price']
        average_price = analysis['average_price']
        price_impact = analysis['price_impact']
        if price_impact * 10000 > 10:
            fluxlayer_price = average_price * 1.01
        else:
            fluxlayer_price = average_price * 1.004
        
        # 输出结果
        print(f"\n[{current_time}] BTC/USDT 实时价格: ${spot_price:.2f}")
        print(f"用 $10,000 买入后：")
        print(f"⋙ 可买入数量: {total_btc:.6f} BTC")
        print(f"⋙ 触及最高价格: ${final_price:.2f}")
        print(f"⋙ 成交均价: ${average_price:.2f}")
        print(f"⋙ 价格影响: {price_impact:.4f}%")
        print(f"⋙ fluxlayer 提供的价格: ${fluxlayer_price:.2f}")
        break

# asyncio.run(rfq_demo())
