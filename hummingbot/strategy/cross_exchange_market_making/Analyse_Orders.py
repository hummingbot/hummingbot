# -*- coding: utf-8 -*-
"""
Created on Thu Mar 25 09:29:51 2021

@author: BenjaSmea
"""

import pandas as pd
pd.options.display.max_columns = None
pd.options.mode.chained_assignment = None 

import ccxt
from os.path import exists


api_keybinance = 'XXX'
sec_keybinance = 'XXX'
api_keykucoin = 'XXX'
sec_keykucoin = 'XXX'
api_keyascendex = 'XXX'
sec_keyascendex = 'XXX'
api_keygateio = 'XXX'
sec_keygateio = 'XXX'

client1 = ccxt.binance({'apiKey': api_keybinance,'secret': sec_keybinance,'enableRateLimit': True,'options': { 'adjustForTimeDifference': True }})
client2 = ccxt.kucoin({"apiKey": api_keykucoin,"secret": sec_keykucoin,"password": "XXXX"})
client3 = ccxt.ascendex({'apiKey': api_keyascendex,'secret': sec_keyascendex,'enableRateLimit': True,'options': { 'adjustForTimeDifference': True }})
client4 = ccxt.gateio({'apiKey': api_keygateio,'secret': sec_keygateio,'enableRateLimit': True,'options': { 'adjustForTimeDifference': True }})

# Input data for Currency pairs and exchange
currency_pairs = ['FRONT/BTC','EXRD/USDT','AKT/USDT','MITX/USDT','XCAD/USDT','HOTCROSS/USDT','FEAR/USDT','TARA/USDT']
currency_exchange = [client1,client2,client3,client3,client2,client2,client2,client3]

#client1 = binance, client2 = kucoin, client3 = ascendex, client4 = gateio.
sigma = 3 #No of standard deviations from the mean to report order size in base currency
no_trades = 1000 # No of results to return from historic trade data
result_mat = pd.DataFrame()

def scrapetrades(limit, main,pair):
    orderbook = main.fetch_trades(pair, limit = limit)
    takerf = pd.DataFrame(orderbook)
    takerf["timestamp"] = pd.to_datetime(takerf["timestamp"], unit='ms') 
    period = takerf["timestamp"][len(takerf)-1] - takerf["timestamp"][0]
    return takerf, period

def run(client,pair):
        hist_orders, period = scrapetrades(no_trades,client,pair)
        max_var = hist_orders['amount'].max()
        result_mat.loc[pd.Timestamp.now().round('10min').to_pydatetime(),str(pair)] = max_var
        return result_mat
    
if __name__ == "__main__":
    for x in range(len(currency_pairs)):
        pair = currency_pairs[x]
        clientid = currency_exchange[x]
        orders = run(clientid,pair)
    file_exists = exists('maxorders.xlsx')
    if not file_exists:
        orders.to_excel("maxorders.xlsx",index=False)
    df = pd.read_excel('maxorders.xlsx')
    df_mix = pd.concat([df.tail(100),orders], ignore_index=True,sort=False)
    df_mix.to_excel("maxorders.xlsx",index=False)
    for x in range(len(currency_pairs)):
        mean = df_mix[currency_pairs[x]].mean()
        std_dev = df_mix[currency_pairs[x]].std()
        print("Standard deviation for pair: " + str(currency_pairs[x]) + " = " + str(mean+(std_dev*sigma)))
    
        
        
