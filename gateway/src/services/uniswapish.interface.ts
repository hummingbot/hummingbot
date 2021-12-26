import { CurrencyAmount, Token, Trade } from '@uniswap/sdk';
import {
  Token as TokenPangolin,
  CurrencyAmount as CurrencyAmountPangolin,
  Trade as TradePangolin,
} from '@pangolindex/sdk';

import { BigNumber, ContractInterface, Transaction, Wallet } from 'ethers';

export interface ExpectedTrade {
  trade: Trade | TradePangolin;
  expectedAmount: CurrencyAmount | CurrencyAmountPangolin;
}

export interface Uniswapish {
  router: string;
  routerAbi: ContractInterface;
  gasLimit: number;
  ttl: number;
  getTokenByAddress(address: string): Token | TokenPangolin;
  priceSwapIn(
    baseToken: Token | TokenPangolin,
    quoteToken: Token | TokenPangolin,
    amount: BigNumber
  ): Promise<ExpectedTrade | string>;
  priceSwapOut(
    quoteToken: Token | TokenPangolin,
    baseToken: Token | TokenPangolin,
    amount: BigNumber
  ): Promise<ExpectedTrade | string>;
  executeTrade(
    wallet: Wallet,
    trade: Trade | TradePangolin,
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
