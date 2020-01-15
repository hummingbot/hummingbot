#!/usr/bin/env python
import logging
import asyncio
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))
from hummingbot.market.bancor.bancor_api_order_book_data_source import  BancorAPIOrderBookDataSource as BancorDataSource
from hummingbot.market.ddex.ddex_api_order_book_data_source import  DDEXAPIOrderBookDataSource as DDEXDataSource
from hummingbot.market.binance.binance_api_order_book_data_source import  BinanceAPIOrderBookDataSource as BinanceDataSource
from hummingbot.market.kyber.kyber_api_order_book_data_source import  KyberAPIOrderBookDataSource as KyberDataSource
ddex = DDEXDataSource()
bancor = BancorDataSource()
binance = BinanceDataSource()
kyber = KyberDataSource( trading_pairs=["0xdd974d5c2e2928dea5f71b9825b8b646686bd200"])

async def speak_async():
    print('call asynchronicity!')
    # res =  bancor.exchange_name
    # print(res)
    pairs = await kyber.get_tracking_pairs()
    print(pairs)
    # pairs = await ddex.get_tracking_pairs()
    # print(pairs)

loop = asyncio.get_event_loop()
loop.run_until_complete(speak_async())
loop.close()