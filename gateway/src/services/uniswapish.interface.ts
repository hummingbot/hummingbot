import { CurrencyAmount, Token, Trade } from '@uniswap/sdk';
import { Trade as UniswapV3Trade } from '@uniswap/v3-sdk';
import {
  TradeType,
  Currency,
  CurrencyAmount as UniswapCoreCurrencyAmount,
  Token as UniswapCoreToken,
} from '@uniswap/sdk-core';
import {
  Token as TokenPangolin,
  CurrencyAmount as CurrencyAmountPangolin,
  Trade as TradePangolin,
} from '@pangolindex/sdk';

import { BigNumber, ContractInterface, Transaction, Wallet } from 'ethers';

export interface ExpectedTrade {
  trade:
    | Trade
    | TradePangolin
    | UniswapV3Trade<Currency, UniswapCoreToken, TradeType>;
  expectedAmount:
    | CurrencyAmount
    | CurrencyAmountPangolin
    | UniswapCoreCurrencyAmount<Currency>;
}

export interface Uniswapish {
  router: string;
  routerAbi: ContractInterface;
  gasLimit: number;
  ttl: number;
  getTokenByAddress(address: string): Token | TokenPangolin | UniswapCoreToken;
  priceSwapIn(
    baseToken: Token | TokenPangolin | UniswapCoreToken,
    quoteToken: Token | TokenPangolin | UniswapCoreToken,
    amount: BigNumber
  ): Promise<ExpectedTrade | string>;
  priceSwapOut(
    quoteToken: Token | TokenPangolin | UniswapCoreToken,
    baseToken: Token | TokenPangolin | UniswapCoreToken,
    amount: BigNumber
  ): Promise<ExpectedTrade | string>;
  executeTrade(
    wallet: Wallet,
    trade:
      | Trade
      | TradePangolin
      | UniswapV3Trade<Currency, UniswapCoreToken, TradeType>,
    gasPrice: number,
    uniswapRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction>;
}
