#!/usr/bin/env python

EXCHANGE_NAME = "ndax"

REST_URL = "https://api.ndax.io:8443/AP"
WSS_URL = "wss://api.ndax.io/WSGateway/"
TEST_WSS_URL = "wss://ndaxmarginstaging.cdnhop.net/WSGateway"

# REST API Public Endpoints
MARKETS_URL = f"{REST_URL}/GetInstruments"
ORDER_BOOK_URL = f"{REST_URL}/GetL2Snapshot"
