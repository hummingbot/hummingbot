import { percentRegexp } from '../../services/config-manager-v2';
import {
  BigNumber,
  Contract,
  ContractInterface,
  Transaction,
  Wallet,
} from 'ethers';
import { AvalancheConfig } from '../../chains/avalanche/avalanche.config';
import { Avalanche } from '../../chains/avalanche/avalanche';
import { PangolinConfig } from './pangolin.config';
import routerAbi from './IPangolinRouter.json';
import {
  Fetcher,
  Percent,
  Router,
  Token,
  TokenAmount,
  Trade,
} from '@pangolindex/sdk';
import { logger } from '../../services/logger';
import { ExpectedTrade, Uniswapish } from '../../services/uniswapish.interface';
export class Pangolin implements Uniswapish {
  private static instance: Pangolin;
  private avalanche = Avalanche.getInstance();
  private _router: string;
  private _routerAbi: ContractInterface;
  private _gasLimit: number;
  private _ttl: number;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor() {
    const config = PangolinConfig.config;
    this.chainId = AvalancheConfig.config.network.chainID;
    this._router = config.routerAddress;
    this._ttl = config.ttl;
    this._routerAbi = routerAbi.abi;
    this._gasLimit = config.gasLimit;
  }

  public static getInstance(): Pangolin {
    if (!Pangolin.instance) {
      Pangolin.instance = new Pangolin();
    }

    return Pangolin.instance;
  }

  public getTokenByAddress(address: string): Token {
    return this.tokenList[address];
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

  public get router(): string {
    return this._router;
  }

  public get ttl(): number {
    return this._ttl;
  }

  public get routerAbi(): ContractInterface {
    return this._routerAbi;
  }

  public get gasLimit(): number {
    return this._gasLimit;
  }

  getSlippagePercentage(): Percent {
    const allowedSlippage = PangolinConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return new Percent(nd[1], nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  // get the expected amount of token out, for a given pair and a token amount in.
  // this only considers direct routes.
  async priceSwapIn(
    tokenIn: Token,
    tokenOut: Token,
    tokenInAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
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
      return `priceSwapIn: no trade pair found for ${tokenIn} to ${tokenOut}.`;
    logger.info(
      `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
    );
    const expectedAmount = trades[0].minimumAmountOut(
      this.getSlippagePercentage()
    );
    return { trade: trades[0], expectedAmount };
  }

  async priceSwapOut(
    tokenIn: Token,
    tokenOut: Token,
    tokenOutAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
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
      return `priceSwapOut: no trade pair found for ${tokenIn.address} to ${tokenOut.address}.`;
    logger.info(
      `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
    );

    const expectedAmount = trades[0].maximumAmountIn(
      this.getSlippagePercentage()
    );
    return { trade: trades[0], expectedAmount };
  }

  // given a wallet and a Uniswap trade, try to execute it on the Avalanche block chain.
  async executeTrade(
    wallet: Wallet,
    trade: Trade,
    gasPrice: number,
    pangolinRouter: string,
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
      allowedSlippage: this.getSlippagePercentage(),
    });

    const contract = new Contract(pangolinRouter, abi, wallet);
    if (!nonce) {
      nonce = await this.avalanche.nonceManager.getNonce(wallet.address);
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
    await this.avalanche.nonceManager.commitNonce(wallet.address, nonce);
    return tx;
  }
}
