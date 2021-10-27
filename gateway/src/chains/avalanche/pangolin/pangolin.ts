import { ConfigManager } from '../../../services/config-manager';
import { BigNumber, Contract, Transaction, Wallet } from 'ethers';
import { AvalancheConfig } from '../avalanche.config';
import { Avalanche } from '../avalanche';
import { PangolinConfig } from './pangolin.config';
import {
  CurrencyAmount,
  Fetcher,
  Router,
  Token,
  TokenAmount,
  Trade,
} from '@pangolindex/sdk';
import { logger } from '../../../services/logger';
import routerAbi from './IPangolinRouter.json';
export interface ExpectedTrade {
  trade: Trade;
  expectedAmount: CurrencyAmount;
}

export class Pangolin {
  private static instance: Pangolin;
  private _pangolinRouter: string;
  private chainId;
  private avalanche = Avalanche.getInstance();
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor() {
    let config;
    switch (ConfigManager.config.AVALANCHE_CHAIN) {
      case 'avalanche':
        config = PangolinConfig.config.avalanche;
        this._pangolinRouter = config.routerAddress;
        this.chainId = AvalancheConfig.config.avalanche.chainId;
        break;
      case 'fuji':
        config = PangolinConfig.config.fuji;
        this._pangolinRouter = config.routerAddress;
        this.chainId = AvalancheConfig.config.fuji.chainId;
        break;
      default:
        throw new Error('ETHEREUM_CHAIN not valid');
    }
  }

  public static getInstance(): Pangolin {
    if (!Pangolin.instance) {
      Pangolin.instance = new Pangolin();
    }

    return Pangolin.instance;
  }

  public async init() {
    if (!this.avalanche.ready()) throw new Error('Avalanche is not available');
    for (const token of this.avalanche.storedTokenList) {
      this.tokenList[token.address] = new Token(
        this.chainId,
        token.address,
        token.decimals,
        token.symbol,
        token.name
      );
    }
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  public get pangolinRouter(): string {
    return this._pangolinRouter;
  }

  // get the expected amount of token out, for a given pair and a token amount in.
  // this only considers direct routes.
  async priceSwapIn(
    tokenInAddress: string,
    tokenOutAddress: string,
    tokenInAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
    const tokenIn = this.tokenList[tokenInAddress];
    if (!tokenIn)
      return `priceSwapIn: tokenInAddress ${tokenInAddress} not found in tokenList.`;
    const tokenOut = this.tokenList[tokenOutAddress];
    if (!tokenOut)
      return `priceSwapIn: tokenOutAddress ${tokenOutAddress} not found in tokenList.`;

    const tokenInAmount_ = new TokenAmount(tokenIn, tokenInAmount.toString());
    logger.info(
      `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
    );
    const pair = await Fetcher.fetchPairData(
      tokenIn,
      tokenOut,
      this.avalanche.provider
    );
    const trades = Trade.bestTradeExactIn([pair], tokenInAmount_, tokenOut, {
      maxHops: 1,
    });
    if (!trades || trades.length === 0)
      return `priceSwapIn: no trade pair found for ${tokenInAddress} to ${tokenOutAddress}.`;
    logger.info(
      `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
    );
    const expectedAmount = trades[0].minimumAmountOut(
      ConfigManager.getSlippagePercentage(
        ConfigManager.config.PANGOLIN_ALLOWED_SLIPPAGE
      )
    );
    return { trade: trades[0], expectedAmount };
  }

  async priceSwapOut(
    tokenInAddress: string,
    tokenOutAddress: string,
    tokenOutAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
    const tokenIn = this.tokenList[tokenInAddress];
    if (!tokenIn)
      return `priceSwapOut: tokenInAddress ${tokenInAddress} not found in tokenList.`;
    const tokenOut = this.tokenList[tokenOutAddress];
    if (!tokenOut)
      return `priceSwapOut: tokenOutAddress ${tokenOutAddress} not found in tokenList.`;
    const tokenOutAmount_ = new TokenAmount(
      tokenOut,
      tokenOutAmount.toString()
    );

    logger.info(
      `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
    );
    const pair = await Fetcher.fetchPairData(
      tokenIn,
      tokenOut,
      this.avalanche.provider
    );
    const trades = Trade.bestTradeExactOut([pair], tokenIn, tokenOutAmount_, {
      maxHops: 1,
    });
    if (!trades || trades.length === 0)
      return `priceSwapOut: no trade pair found for ${tokenInAddress} to ${tokenOutAddress}.`;
    logger.info(
      `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
    );

    const expectedAmount = trades[0].maximumAmountIn(
      ConfigManager.getSlippagePercentage(
        ConfigManager.config.PANGOLIN_ALLOWED_SLIPPAGE
      )
    );
    return { trade: trades[0], expectedAmount };
  }

  // given a wallet and a Uniswap trade, try to execute it on the Avalanche block chain.
  async executeTrade(
    wallet: Wallet,
    trade: Trade,
    gasPrice: number,
    nonce?: number
  ): Promise<Transaction> {
    const result = Router.swapCallParameters(trade, {
      ttl: ConfigManager.config.PANGOLIN_TTL,
      recipient: wallet.address,
      allowedSlippage: ConfigManager.getSlippagePercentage(
        ConfigManager.config.PANGOLIN_ALLOWED_SLIPPAGE
      ),
    });
    const contract = new Contract(this._pangolinRouter, routerAbi.abi, wallet);
    if (!nonce) {
      nonce = await this.avalanche.nonceManager.getNonce(wallet.address);
    }
    const tx = await contract[result.methodName](...result.args, {
      gasPrice: gasPrice * 1e9,
      gasLimit: ConfigManager.config.PANGOLIN_GAS_LIMIT,
      value: result.value,
      nonce: nonce,
    });

    logger.info(tx);
    await this.avalanche.nonceManager.commitNonce(wallet.address, nonce);
    return tx;
  }
}
