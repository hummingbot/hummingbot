import requests
from web3 import Web3
from web3.gas_strategies.time_based import medium_gas_price_strategy


# 配置不同链的RPC节点
CHAIN_CONFIG = {
    "Ethereum": {
        "rpc": "https://mainnet.infura.io/v3/67f13cc641054e588b1bf8ba94f2585b",
        "explorer": "https://api.etherscan.io/api",
        "gas_api": "https://ethgasstation.info/api/ethgasAPI.json"
    },
    "BSC": {
        "rpc": "https://bsc-dataseed.binance.org/",
        "explorer": "https://api.bscscan.com/api"
    },
    "Polygon": {
        "rpc": "https://polygon-rpc.com",
        "explorer": "https://api.polygonscan.com/api"
    }
}

def get_btc_fee():
    url = "https://api.blockchain.info/mempool/fees"
    response = requests.get(url)
    data = response.json()
    return {
        "priority": data["priority"],  # 高优先级费率（sat/vB） 1 sat = 0.00000001 BTC 1 vB = 1字节
        "regular": data["regular"],    # 普通费率（sat/vB）
    }

def get_gas_prices(chain_name):
    config = CHAIN_CONFIG.get(chain_name, {})
    if config == {}:
        return {}
    params = {
        "module": "gastracker",
        "action": "gasoracle",
        "apikey": "R7R78C3U98KZ2MVQQE5XGRG1VCVFQSAYAU"
    }
    if chain_name == "Ethereum":
        try:
            response = requests.get(config['explorer'], params=params)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "1":
                    result = data["result"]
                    return {
                        "base_fee": result["ProposeGasPrice"],
                        "priority_fee": result["FastGasPrice"]
                    }
                else:
                    return f"Error: {data['message']}"
            else:
                return f"HTTP Error: {response.status_code}"
        except Exception as e:
            return f"HTTP Error: {e}"
    else:
        # 使用Web3直接估算
        w3 = Web3(Web3.HTTPProvider(config["rpc"]))
        w3.eth.set_gas_price_strategy(medium_gas_price_strategy)
        return {
            "base_fee": w3.eth.gas_price/1000000000,
            "priority_fee": w3.eth.max_priority_fee/1000000000
        }


