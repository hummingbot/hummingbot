import base64

import websocket
from hummingbot.connector.exchange.polkadex import polkadex_constants as CONSTANTS


def on_message(ws, message):
    print(message)


def on_error(ws, error):
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws):
    print("Opened connection")


if __name__ == "__main__":
    websocket.enableTrace(True)
    header = {
            "host": "x6sbwzrbzvbabpujfy2phgq6ka.appsync-api.ap-south-1.amazonaws.com",
            "x-api-key": CONSTANTS.GRAPHQL_API_KEY,
        }
    wss_url = 'wss://x6sbwzrbzvbabpujfy2phgq6ka.appsync-realtime-api.ap-south-1.amazonaws.com/graphql'
    connection_url = wss_url + '?header=' +"ewogICAgICAgICAgICAiaG9zdCI6ICJ4NnNid3pyYnp2YmFicHVqZnkycGhncTZrYS5hcHBzeW5jLWFwaS5hcC1zb3V0aC0xLmFtYXpvbmF3cy5jb20iLAogICAgICAgICAgICAieC1hcGkta2V5IjogImRhMi13bGFoZmtnc3puaDI3YWhqMjUzaDdvZWZwNCIsCn0="+ '&payload=e30='
    print(connection_url)
    ws = websocket.WebSocketApp(
        connection_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close)
    ws.run_forever()  # Set dispatcher to automatic reconnection
