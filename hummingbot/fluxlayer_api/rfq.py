import time
from datetime import datetime
import sys
import os
import asyncio
import requests
current_file_path = os.path.abspath(__file__)

project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

# 将项目根目录添加到 Python 路径
sys.path.append(project_root)

# from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
# from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.fluxlayer_api.get_chain_gas import get_gas_prices, get_btc_fee

binance_price_url = "https://api.binance.com/api/v3/depth"
money_depth = 10000

def get_order_book(symbol='BTCUSDT', limit=100):
    """获取币安深度数据"""
    try:
        response = requests.get(binance_price_url, params={'symbol': symbol, 'limit': limit})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting depth data: {e}")
        return None
    
# async def get_order_book_hummingbot(symbol='BTCUSDT', limit=100):
#     app = HummingbotApplication.main_application()
#     client_config_map = app.client_config_map
#     binance_exchange_obj = BinanceExchange(
#         client_config_map=client_config_map,
#         binance_api_key="",
#         binance_api_secret="",
#     )
#     order_book_data_source = binance_exchange_obj._create_order_book_data_source()
#     snapshot_msg = await order_book_data_source._order_book_snapshot(symbol)
#     json_data = {
#         'lastUpdateId': snapshot_msg.timestamp,
#         'bids': snapshot_msg.content["bids"],
#         'asks': snapshot_msg.content["asks"],
#     }
#     return json_data

def calculate_price_impact(asks, budget_usdt=10000):
    """计算指定预算对价格的影响"""
    remaining_budget = budget_usdt
    total_amount = 0
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
            total_amount += qty
            executed_orders.append((price, qty))
            last_price = price
        else:
            # 部分吃单
            executable_qty = remaining_budget / price
            total_amount += executable_qty
            executed_orders.append((price, executable_qty))
            remaining_budget = 0
            last_price = price

    return {
        'final_price': last_price,
        'total_amount': total_amount,
        'average_price': budget_usdt / total_amount if total_amount > 0 else None,
        'price_impact': (last_price - float(asks[0][0])) / float(asks[0][0]) * 100
    }

def parse_chain_token(chain_token: str):
    """解析链和代币信息"""
    try:
        chain, token = chain_token.split('_')
        return chain, token
    except:
        raise ValueError(f"Invalid chain_token format: {chain_token}")

def get_token_price(token: str):
    """获取代币的USDT价格"""
    symbol = f"{token}USDT"
    try:
        response = requests.get(binance_price_url, params={'symbol': symbol, 'limit': 1000})
        response.raise_for_status()
        return response.json()

    except Exception as e:
        print(f"Error getting price for {token}: {e}")
        return None

def calculate_gas_fee(chain: str):
    """计算链上的gas费用"""
    if chain.upper() == "BTC":
        btc_fee = get_btc_fee()
        return btc_fee["regular"] * 0.00000001  # 转换为BTC
    else:
        gas_prices = get_gas_prices(chain)
        return gas_prices["base_fee"] * 21000 / 1e9  # 

def rfq_demo(src_chain: str, src_token: str, src_amount: float, tar_chain: str, tar_token: str):
    """计算跨链交易后的数量"""
    # try:
        # 解析src链和target链信息
    src_chain_name, src_chain_token = parse_chain_token(src_chain)
    tar_chain_name, tar_chain_token = parse_chain_token(tar_chain)
    
    # 获取代币价格
    src_price_orderbook = get_token_price(src_chain_token)
    src_price = float(src_price_orderbook['asks'][0][0])
    tar_price_orderbook = get_token_price(tar_chain_token)
    tar_recent_price = float(tar_price_orderbook['asks'][0][0])
    if not src_price or not tar_recent_price:
        return {"error": "Failed to get token prices"}
    
    # 计算src代币的USDT价值
    src_value_usdt = src_amount * src_price
    
    # 计算gas费用
    tar_gas_fee = calculate_gas_fee(tar_chain_name)
    
    # 将gas费用转换为USDT
    tar_gas_fee_usdt = tar_gas_fee * tar_recent_price if tar_chain_name.upper() != "BTC" else tar_gas_fee * tar_recent_price
    
    # 计算扣除gas费用后的USDT价值
    net_value_usdt = src_value_usdt - tar_gas_fee_usdt

    # 计算价格影响
    analysis = calculate_price_impact(tar_price_orderbook['asks'], net_value_usdt)

    average_price = analysis['average_price']
    price_impact = analysis['price_impact']
    if price_impact * 10000 > 10:
        fluxlayer_price = average_price * 1.01
    else:
        fluxlayer_price = average_price * 1.004
    
    # 计算target代币数量
    tar_amount = net_value_usdt / fluxlayer_price
    
    return {
        "src_chain": src_chain,
        "src_token": src_token,
        "src_amount": src_amount,
        "src_price": src_price,
        "tar_chain": tar_chain,
        "tar_token": tar_token,
        "tar_amount": tar_amount,
        "tar_price": fluxlayer_price,
    }
        
    # except Exception as e:
    #     return {"error": str(e)}

# async def main():
#     # 直接 await 调用
#     res = await rfq_demo()
#     print(res)

# # 运行入口
# asyncio.run(main())

