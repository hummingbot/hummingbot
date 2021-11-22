import {
  BigNumber,
  Contract,
  ContractInterface,
  Transaction,
  Wallet,
} from 'ethers';
import { logger } from './logger';
import { Ethereumish } from '../chains/ethereum/ethereum';

import {
  CurrencyAmount,
  Fetcher,
  Percent,
  Router,
  Token,
  TokenAmount,
  Trade,
} from '@uniswap/sdk';

export interface ExpectedTrade {
  trade: Trade;
  expectedAmount: CurrencyAmount;
}

// export interface uniswapishSdk {
//   CurrencyAmount: '@uniswap/sdk.CurrencyAmount';
//   Fetcher: '@uniswap/sdk.Fetcher' | '@pangolin/sdk.Fetcher';
//   Percent: '@uniswap/sdk.Percent' | '@pangolin/sdk.Percent';
//   Router: '@uniswap/sdk.Router' | '@pangolin/sdk.Router';
//   Token: '@uniswap/sdk.Token' | '@pangolin/sdk.Token';
//   TokenAmount: '@uniswap/sdk.TokenAmount' | '@pangolin/sdk.TokenAmount';
//   Trade: '@uniswap/sdk.Trade' | '@pangolin/sdk.Trade';
// }

// export interface ExpectedTrade {
//   trade: uniswapishSdk['Trade'];
//   expectedAmount: uniswapishSdk['CurrencyAmount'];
// }

export class UniswapBase {
  private ethereumish: Ethereumish;

  constructor(ethereumish: Ethereumish) {
    this.ethereumish = ethereumish;
  }

  // get the expected amount of token out, for a given pair and a token amount in.
  // this only considers direct routes.
  async priceSwapIn(
    tokenIn: Token,
    tokenOut: Token,
    tokenInAmount: BigNumber,
    slippagePercentage: Percent
  ): Promise<ExpectedTrade | string> {
    const tokenInAmount_ = new TokenAmount(tokenIn, tokenInAmount.toString());
    logger.info(
      `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
    );
    const pair = await Fetcher.fetchPairData(tokenIn, tokenOut);
    const trades = Trade.bestTradeExactIn([pair], tokenInAmount_, tokenOut, {
      maxHops: 1,
    });
    if (!trades || trades.length === 0)
      return `priceSwapIn: no trade pair found for ${tokenIn} to ${tokenOut}.`;
    logger.info(
      `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
    );
    const expectedAmount = trades[0].minimumAmountOut(slippagePercentage);
    return { trade: trades[0], expectedAmount };
  }

  async priceSwapOut(
    tokenIn: Token,
    tokenOut: Token,
    tokenOutAmount: BigNumber,
    slippagePercentage: Percent
  ): Promise<ExpectedTrade | string> {
    const tokenOutAmount_ = new TokenAmount(
      tokenOut,
      tokenOutAmount.toString()
    );
    logger.info(
      `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
    );
    const pair = await Fetcher.fetchPairData(tokenIn, tokenOut);
    const trades = Trade.bestTradeExactOut([pair], tokenIn, tokenOutAmount_, {
      maxHops: 1,
    });
    if (!trades || trades.length === 0)
      return `priceSwapOut: no trade pair found for ${tokenIn.address} to ${tokenOut.address}.`;
    logger.info(
      `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
    );

    const expectedAmount = trades[0].maximumAmountIn(slippagePercentage);
    return { trade: trades[0], expectedAmount };
  }

  // given a wallet and a Uniswap trade, try to execute it on the Ethereum block chain.
  async executeTrade(
    wallet: Wallet,
    trade: Trade,
    gasPrice: number,
    slippagePercentage: Percent,
    uniswapRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction> {
    const result = Router.swapCallParameters(trade, {
      ttl,
      recipient: wallet.address,
      allowedSlippage: slippagePercentage,
    });

    const contract = new Contract(uniswapRouter, abi, wallet);
    if (!nonce) {
      nonce = await this.ethereumish.nonceManager.getNonce(wallet.address);
    }
    let tx;
    if (maxFeePerGas || maxPriorityFeePerGas) {
      tx = await contract[result.methodName](...result.args, {
        gasLimit: gasLimit,
        value: result.value,
        nonce: nonce,
        maxFeePerGas,
        maxPriorityFeePerGas,
      });
    } else {
      tx = await contract[result.methodName](...result.args, {
        gasPrice: gasPrice * 1e9,
        gasLimit: gasLimit,
        value: result.value,
        nonce: nonce,
      });
    }

    logger.info(tx);
    await this.ethereumish.nonceManager.commitNonce(wallet.address, nonce);
    return tx;
  }
}
