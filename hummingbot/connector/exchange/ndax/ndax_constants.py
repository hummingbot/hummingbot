#!/usr/bin/env python

EXCHANGE_NAME = "ndax"

REST_URL = "https://api.ndax.io:8443/AP"
WSS_URL = "wss://api.ndax.io/WSGateway/"
TEST_WSS_URL = "wss://ndaxmarginstaging.cdnhop.net/WSGateway"

# REST API Public Endpoints
MARKETS_URL = f"{REST_URL}/GetInstruments"
ORDER_BOOK_URL = f"{REST_URL}/GetL2Snapshot"
LAST_TRADE_PRICE_URL = f"{REST_URL}/GetLevel1"

# WebSocket Public Endpoints
WS_ORDER_BOOK_CHANNEL = "SubscribeLevel2"

# WebSocket Message Events
WS_ORDER_BOOK_L2_UPDATE_EVENT = "Level2UpdateEvent"
