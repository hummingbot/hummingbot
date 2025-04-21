import time
from datetime import datetime
import sys
import os
import asyncio
import requests
from decimal import Decimal
import aiohttp
from aiohttp import ClientTimeout, ClientSession, TCPConnector

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.append(project_root)
from hummingbot.logger import HummingbotLogger
from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange
from hummingbot.connector.exchange.bybit.bybit_exchange import BybitExchange
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.fluxlayer_api.get_chain_gas import get_gas_prices, get_btc_fee
from hummingbot.core.data_type.order_book_tracker import OrderBookTracker
from hummingbot.connector.exchange.binance.binance_api_order_book_data_source import BinanceAPIOrderBookDataSource
from hummingbot.connector.exchange.gate_io.gate_io_api_order_book_data_source import GateIoAPIOrderBookDataSource
from hummingbot.connector.exchange.bybit.bybit_api_order_book_data_source import BybitAPIOrderBookDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.connector.exchange.binance import binance_constants as BINANCE_CONSTANTS
from hummingbot.connector.exchange.gate_io import gate_io_constants as GATE_IO_CONSTANTS
from hummingbot.connector.exchange.bybit import bybit_constants as BYBIT_CONSTANTS
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.client_config_map import AnonymizedMetricsEnabledMode

# 配置日志
_logger = HummingbotLogger(__name__)

# 交易所配置
EXCHANGES = {
    "binance": {
        "exchange_class": BinanceExchange,
        "data_source_class": BinanceAPIOrderBookDataSource,
        "constants": BINANCE_CONSTANTS,
        "proxy": "http://127.0.0.1:33210",
        "required_params": {
            "binance_api_key": "",
            "binance_api_secret": ""
        }
    },
    "gate_io": {
        "exchange_class": GateIoExchange,
        "data_source_class": GateIoAPIOrderBookDataSource,
        "constants": GATE_IO_CONSTANTS,
        "proxy": "http://127.0.0.1:33210",
        "required_params": {
            "gate_io_api_key": "",
            "gate_io_secret_key": ""
        }
    },
    "bybit": {
        "exchange_class": BybitExchange,
        "data_source_class": BybitAPIOrderBookDataSource,
        "constants": BYBIT_CONSTANTS,
        "proxy": "http://127.0.0.1:33210",
        "required_params": {
            "bybit_api_key": "",
            "bybit_api_secret": ""
        }
    }
}

# 全局变量
_exchange = None
_order_book_tracker = None
_initialized = False
_throttler = None
_initialization_lock = asyncio.Lock()
_session = None

async def initialize_exchange(exchange_name: str = "binance", trading_pairs: list = None):
    """初始化交易所连接"""
    global _exchange, _order_book_tracker, _initialized, _throttler, _session
    
    if exchange_name not in EXCHANGES:
        raise ValueError(f"Unsupported exchange: {exchange_name}")
        
    exchange_config = EXCHANGES[exchange_name]
    
    async with _initialization_lock:
        if not _initialized:
            try:
                # 创建客户端配置
                client_config = ClientConfigMap()
                client_config.anonymized_metrics_mode = AnonymizedMetricsEnabledMode()
                client_config_adapter = ClientConfigAdapter(client_config)
                
                # 创建交易所实例
                exchange_params = {
                    "client_config_map": client_config_adapter,
                    "trading_pairs": trading_pairs or ["BTC-USDT"],
                    "trading_required": False
                }
                # 添加交易所特定的必要参数
                exchange_params.update(exchange_config["required_params"])
                
                _exchange = exchange_config["exchange_class"](**exchange_params)
                
                # 创建 throttler
                _throttler = AsyncThrottler(exchange_config["constants"].RATE_LIMITS)
                
                # 创建带代理的 ClientSession
                connector = TCPConnector(ssl=False)
                _session = ClientSession(
                    connector=connector,
                    timeout=ClientTimeout(total=30),
                    trust_env=True
                )
                
                # 创建 WebAssistantsFactory
                api_factory = WebAssistantsFactory(
                    throttler=_throttler
                )
                
                # 创建订单簿数据源
                data_source = exchange_config["data_source_class"](
                    trading_pairs=trading_pairs or ["BTC-USDT"],
                    connector=_exchange,
                    api_factory=api_factory
                )
                
                # 创建订单簿跟踪器
                _order_book_tracker = OrderBookTracker(
                    data_source=data_source,
                    trading_pairs=trading_pairs or ["BTC-USDT"]
                )
                
                # 启动订单簿跟踪器
                _order_book_tracker.start()
                
                # 等待订单簿数据加载
                await _order_book_tracker.wait_ready()
                
                _initialized = True
                _logger.info(f"Successfully initialized {exchange_name} exchange")
                
            except Exception as e:
                _logger.error(f"Failed to initialize exchange: {e}")
                raise

async def cleanup():
    """清理资源"""
    global _order_book_tracker, _initialized, _throttler, _session
    
    try:
        if _order_book_tracker is not None:
            _order_book_tracker.stop()
        if _session is not None:
            await _session.close()
        _initialized = False
        _logger.info("Successfully cleaned up resources")
    except Exception as e:
        _logger.error(f"Error during cleanup: {e}")
        raise

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

async def get_token_price(exchange_name: str = "binance", token: str = "BTC"):
    """获取代币的USDT价格"""
    symbol = f"{token}-USDT"
    try:
        # 确保交易所已初始化
        await initialize_exchange(exchange_name, [symbol])
        
        # 获取订单簿数据
        order_book = _order_book_tracker.order_books[symbol]
        
        # 获取买卖单
        bids = [(str(price), str(amount)) for price, amount, _ in order_book.bid_entries()]
        asks = [(str(price), str(amount)) for price, amount, _ in order_book.ask_entries()]
        return {
            'lastUpdateId': int(time.time() * 1000),
            'bids': bids,
            'asks': asks
        }
    except Exception as e:
        _logger.error(f"Error getting price for {token}: {e}")
        return None

def calculate_gas_fee(chain: str):
    """计算链上的gas费用"""
    if chain.upper() == "BTC":
        btc_fee = get_btc_fee()
        return btc_fee["regular"] * 0.00000001  # 转换为BTC
    else:
        gas_prices = get_gas_prices(chain)
        return gas_prices["base_fee"] * 21000 / 1e9

async def rfq_demo(
    src_chain: str,
    src_token: str,
    src_amount: float,
    tar_chain: str,
    tar_token: str,
    exchange_name: str = "binance"
):
    """计算跨链交易后的数量"""
    try:
        # 解析src链和target链信息
        src_chain_name, src_chain_token = parse_chain_token(src_chain)
        tar_chain_name, tar_chain_token = parse_chain_token(tar_chain)
        
        # 获取代币价格
        src_price_orderbook = await get_token_price(exchange_name, src_chain_token)
        await cleanup()
        if not src_price_orderbook or not src_price_orderbook['asks']:
            return {"error": f"Failed to get price for source token {src_chain_token}"}
            
        src_price = float(src_price_orderbook['asks'][0][0])
        
        tar_price_orderbook = await get_token_price(exchange_name, tar_chain_token)
        await cleanup()
        if not tar_price_orderbook or not tar_price_orderbook['asks']:
            return {"error": f"Failed to get price for target token {tar_chain_token}"}
            
        tar_recent_price = float(tar_price_orderbook['asks'][0][0])
        
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
            "exchange": exchange_name
        }
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        # 在所有操作完成后清理资源
        await cleanup()

# # 运行入口
# if __name__ == "__main__":
#     try:
#         # 示例调用
#         result = asyncio.run(rfq_demo(
#             src_chain="ETH_ETH",
#             src_token="ETH",
#             src_amount=1.0,
#             tar_chain="BTC_BTC",
#             tar_token="BTC",
#             exchange_name="binance"  # 可选：binance, gate_io, bybit
#         ))
#         print(result)
#     except KeyboardInterrupt:
#         print("\nExiting...")
#     except Exception as e:
#         print(f"Unexpected error: {e}")