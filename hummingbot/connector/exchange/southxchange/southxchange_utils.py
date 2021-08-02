import random
import string
import requests

from typing import Dict, Tuple
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce_low_res

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.connector.exchange.southxchange.southxchange_constants import EXCHANGE_NAME, REST_URL
from decimal import Decimal
import asyncio
import json
import aiohttp

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = [0.1, 0.1]


HBOT_BROKER_ID = "HMBot"

def get_markets_enabled() -> Dict[int , str]:
    url = f"{REST_URL}markets"
    resp = requests.get(url)
    if resp.status_code != 200:
        falla = 12
    resp_text = json.loads(resp.text)
    list_markets_enabled :Dict[int , str] = {}
    try:
        for item in resp_text:
            list_markets_enabled[item[2]] = (f"{item[0]}-{item[1]}")
    except Exception as e:
        fall = e
    return list_markets_enabled
        
def get_rest_url_private(account_id: int) -> str:
    return f"https://www.southxchange.com/api/v4"


def get_ws_url_private(account_id: int) -> str:
    return f"wss://www.southxchange.com/api/v4"


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "/")

# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return get_tracking_nonce_low_res()

# get timestamp in milliseconds
def time_to_num(time_str) -> int:
    hh, mm , ss = map(int, time_str.split(':'))
    return ss + 60*(mm + 60*hh)

def uuid32():
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(32))


def derive_order_id(user_uid: str, cl_order_id: str, ts: int) -> str:
    """
    Server order generator based on user info and input.
    :param user_uid: user uid
    :param cl_order_id: user random digital and number id
    :param ts: order timestamp in milliseconds
    :return: order id of length 32
    """
    return (HBOT_BROKER_ID + format(ts, 'x')[-11:] + user_uid[-11:] + cl_order_id[-5:])[:32]

def convert_bookWebSocket_to_bookApi(t: any) -> Dict[str, list]:
    arrayBuy = []
    arraySell = []
    for item in t:
        valueItem = item
        if item.get("b") == True:
            buyOrder = {
                "Amount": item.get("a"),
                "Price": item.get("p")
            }
            arrayBuy.append(buyOrder)
        else:
            sellOrder = {
                "Amount": item.get("a"),
                "Price": item.get("p")
            }
            arraySell.append(sellOrder)                   
    result = {
                "BuyOrders": arrayBuy,
                "SellOrders": arraySell,
    }
    return result

def gen_exchange_order_id(userUid: str, client_order_id: str) -> Tuple[str, int]:
    """
    Generates the exchange order id based on user uid and client order id.
    :param user_uid: user uid,
    :param client_order_id: client order id used for local order tracking
    :return: order id of length 32
    """
    time = get_ms_timestamp()
    return [
        derive_order_id(
            userUid,
            client_order_id,
            time
        ),
        time
    ]


def gen_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{HBOT_BROKER_ID}-{side}-{trading_pair}-{get_tracking_nonce()}"


KEYS = {
    "southxchange_api_key":
        ConfigVar(key="southxchange_api_key",
                  prompt="Enter your SouthXchange API key >>> ",
                  required_if=using_exchange("southxchange"),
                  is_secure=True,
                  is_connect_key=True),
    "southxchange_secret_key":
        ConfigVar(key="southxchange_secret_key",
                  prompt="Enter your SouthXchange secret key >>> ",
                  required_if=using_exchange("southxchange"),
                  is_secure=True,
                  is_connect_key=True),
}
