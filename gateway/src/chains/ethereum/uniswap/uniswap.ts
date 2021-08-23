import { ConfigManager } from '../../../services/config-manager';
import { BigNumber, Contract, Transaction, Wallet } from 'ethers';
import { EthereumConfig } from '../ethereum.config';
import { Ethereum } from '../ethereum';
import { UniswapConfig } from './uniswap.config';
import {
  CurrencyAmount,
  Fetcher,
  Router,
  Token,
  TokenAmount,
  Trade,
} from '@uniswap/sdk';
import { logger } from '../../../services/logger';
import routerAbi from './uniswap_v2_router_abi.json';

export interface ExpectedTrade {
  trade: Trade;
  expectedAmount: CurrencyAmount;
}

export class Uniswap {
  private _uniswapRouter: string;
  private chainId;
  private ethereum = new Ethereum();

  private tokenList: Record<string, Token> = {};

  constructor() {
    let config;
    if (ConfigManager.config.ETHEREUM_CHAIN === 'mainnet') {
      config = UniswapConfig.config.mainnet;
    } else {
      config = UniswapConfig.config.kovan;
    }

    this._uniswapRouter = config.uniswapV2RouterAddress;
    if (ConfigManager.config.ETHEREUM_CHAIN === 'mainnet') {
      this.chainId = EthereumConfig.config.mainnet.chainId;
    } else {
      this.chainId = EthereumConfig.config.kovan.chainId;
    }

    for (const token of this.ethereum.getStoredTokenList()) {
      this.tokenList[token.address] = new Token(
        this.chainId,
        token.address,
        token.decimals,
        token.symbol,
        token.name
      );
    }
  }

  public get uniswapRouter(): string {
    return this._uniswapRouter;
  }

  // get the expected amount of token out, for a given pair and a token amount in.
  // this only considers direct routes.
  async priceSwapIn(
    tokenInAddress: string,
    tokenOutAddress: string,
    tokenInAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
    const tokenIn = this.tokenList[tokenInAddress];
    if (tokenIn) {
      const tokenOut = this.tokenList[tokenOutAddress];
      if (tokenOut) {
        const tokenInAmount_ = new TokenAmount(
          tokenIn,
          tokenInAmount.toString()
        );

        logger.info(
          `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
        );
        const pair = await Fetcher.fetchPairData(tokenIn, tokenOut);
        const trades = Trade.bestTradeExactIn(
          [pair],
          tokenInAmount_,
          tokenOut,
          {
            maxHops: 1,
          }
        );

        if (trades.length > 0) {
          logger.info(
            `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
          );
          const expectedAmount = trades[0].minimumAmountOut(
            ConfigManager.config.UNISWAP_ALLOWED_SLIPPAGE
          );
          return { trade: trades[0], expectedAmount };
        } else {
          return `priceSwapIn: no trade pair found for ${tokenInAddress} to ${tokenOutAddress}.`;
        }
      } else {
        return `priceSwapIn: tokenOutAddress ${tokenOutAddress} not found in tokenList.`;
      }
    } else {
      return `priceSwapIn: tokenInAddress ${tokenInAddress} not found in tokenList.`;
    }
  }

  async priceSwapOut(
    tokenInAddress: string,
    tokenOutAddress: string,
    tokenOutAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
    const tokenIn = this.tokenList[tokenInAddress];
    if (tokenIn) {
      const tokenOut = this.tokenList[tokenOutAddress];
      if (tokenOut) {
        const tokenOutAmount_ = new TokenAmount(
          tokenOut,
          tokenOutAmount.toString()
        );

        logger.info(
          `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
        );
        const pair = await Fetcher.fetchPairData(tokenIn, tokenOut);
        const trades = Trade.bestTradeExactOut(
          [pair],
          tokenIn,
          tokenOutAmount_,
          {
            maxHops: 1,
          }
        );
        if (trades.length > 0) {
          logger.info(
            `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
          );
          const expectedAmount = trades[0].maximumAmountIn(
            ConfigManager.config.UNISWAP_ALLOWED_SLIPPAGE
          );
          return { trade: trades[0], expectedAmount };
        } else {
          return `priceSwapOut: no trade pair found for ${tokenInAddress} to ${tokenOutAddress}.`;
        }
      } else {
        return `priceSwapOut: tokenOutAddress ${tokenOutAddress} not found in tokenList.`;
      }
    } else {
      return `priceSwapOut: tokenInAddress ${tokenInAddress} not found in tokenList.`;
    }
  }

  // given a wallet and a Uniswap trade, try to execute it on the Ethereum block chain.
  async executeTrade(
    wallet: Wallet,
    trade: Trade,
    gasPrice: number
  ): Promise<Transaction> {
    logger.info(`Performing trade ${trade}.`);
    const result = Router.swapCallParameters(trade, {
      ttl: ConfigManager.config.UNISWAP_TTL,
      recipient: wallet.address,
      allowedSlippage: ConfigManager.config.UNISWAP_ALLOWED_SLIPPAGE,
    });

    const contract = new Contract(this._uniswapRouter, routerAbi.abi, wallet);

    const tx = await contract[result.methodName](...result.args, {
      gasPrice: gasPrice * 1e9,
      gasLimit: ConfigManager.config.UNISWAP_GAS_LIMIT,
      value: result.value,
    });

    logger.info(`Trade tx ${tx}.`);

    return tx;
  }
}
