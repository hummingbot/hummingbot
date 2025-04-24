import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from typing import Any, Dict
import sys
import os

current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file_path))))
sys.path.append(project_root)

from hummingbot.fluxlayer_api.api_server import server, GetRFQRequest, GetBestRFQRequest

client = TestClient(app=server)

# 测试数据模板
valid_rfq_request = {
    "src_chain":"Ethereum_ETH",
    "src_token":"Ethereum_ETH",
    "src_amount":10.0,
    "tar_chain":"BSC_BNB",
    "tar_token":"BSC_BNB",
    "exchange_name":"binance"
}

valid_best_rfq_request = {
    "src_chain":"Ethereum_ETH",
    "src_token":"Ethereum_ETH",
    "src_amount":10.0,
    "tar_chain":"BSC_BNB",
    "tar_token":"BSC_BNB",
}

# 辅助函数
def validate_response_structure(response_data: Dict[str, Any]):
    """验证RFQ响应结构的基础校验"""
    assert "src_chain" in response_data
    assert "src_token" in response_data
    assert "src_amount" in response_data
    assert "src_price" in response_data
    assert "tar_chain" in response_data
    assert "tar_token" in response_data
    assert "tar_amount" in response_data
    assert "tar_price" in response_data
    assert "exchange" in response_data

# /rfq_request 接口测试
@patch('hummingbot.fluxlayer_api.rfq.get_single_exchange_rfq', new_callable=AsyncMock)
def test_get_rfq_success(mock_get_single):
    mock_response = {
        "src_chain":"Ethereum_ETH",
        "src_token":"Ethereum_ETH",
        "src_amount":10.0,
        "src_price":1627.45,
        "tar_chain":"BSC_BNB",
        "tar_token":"BSC_BNB",
        "tar_amount":26.971578202754966,
        "tar_price":603.39396,
        "exchange":"binance"
    }
    mock_get_single.return_value = mock_response

    response = client.post("/rfq_request", json=valid_rfq_request)
    print("aaaaaaaaa11111", response.json())
    assert response.status_code == 200
    validate_response_structure(response.json())
    assert response.json()["exchange"] == "binance"

def test_get_rfq_missing_field():
    invalid_request = valid_rfq_request.copy()
    del invalid_request["src_chain"]
    
    response = client.post("/rfq_request", json=invalid_request)
    
    assert response.status_code == 422
    assert "src_chain" in str(response.json())

@patch('hummingbot.fluxlayer_api.rfq.get_single_exchange_rfq', new_callable=AsyncMock)
def test_get_rfq_invalid_exchange(mock_get_single):
    mock_get_single.return_value = None
    
    invalid_request = valid_rfq_request.copy()
    invalid_request["exchange_name"] = "unknown_exchange"
    
    response = client.post("/rfq_request", json=invalid_request)

    assert response.status_code == 200
    assert response.json() == None

# /get_best_rfq 接口测试
@patch('hummingbot.fluxlayer_api.rfq.get_best_rfq', new_callable=AsyncMock)
def test_get_best_rfq_success(mock_get_best):
    mock_response = {
        "src_chain":"Ethereum_ETH","src_token":"Ethereum_ETH",
        "src_amount":10.0,
        "src_price":1633.91,
        "tar_chain":"BSC_BNB",
        "tar_token":"BSC_BNB",
        "tar_amount":26.871621341291814,
        "tar_price":608.04248,
        "exchange":"okx",
        "all_exchanges":{
            "binance":{"tar_amount":26.670581752349467,"tar_price":612.0596628778818},
            "gate_io":{"tar_amount":26.670581752349467,"tar_price":612.0596628778818},
            "bybit":{"tar_amount":26.687147665226465,"tar_price":611.9532699296216},
            "bing_x":{"tar_amount":26.687147665226465,"tar_price":611.9532699296216},
            "kucoin":{"tar_amount":26.654837112462484,"tar_price":612.6800624575749},
            "bitmart":{"tar_amount":26.654837112462484,"tar_price":612.6800624575749},
            "okx":{"tar_amount":26.871621341291814,"tar_price":608.04248},
            "mexc":{"tar_amount":26.871621341291814,"tar_price":608.04248}
        }
    }
    mock_get_best.return_value = mock_response

    response = client.post("/get_best_rfq", json=valid_best_rfq_request)
    
    assert response.status_code == 200
    validate_response_structure(response.json())
    assert response.json()["exchange"] == "okx"

def test_get_best_rfq_invalid_amount():
    invalid_request = valid_best_rfq_request.copy()
    invalid_request["src_amount"] = -100
    
    response = client.post("/get_best_rfq", json=invalid_request)
    
    assert response.status_code == 200
    assert "greater than 0" in str(response.json())

# execute command: pytest test_api.py -v