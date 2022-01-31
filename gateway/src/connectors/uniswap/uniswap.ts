import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { UniswapConfig } from './uniswap.config';
import routerAbi from './uniswap_v2_router_abi.json';
import { Contract, ContractInterface } from '@ethersproject/contracts';
import {
  Fetcher,
  Percent,
  Router,
  Token,
  TokenAmount,
  Trade,
} from '@uniswap/sdk';
import { BigNumber, Transaction, Wallet } from 'ethers';
import { logger } from '../../services/logger';
import { percentRegexp } from '../../services/config-manager-v2';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { ExpectedTrade, Uniswapish } from '../../services/common-interfaces';
export class Uniswap implements Uniswapish {
  private static _instances: { [name: string]: Uniswap };
  private ethereum: Ethereum;
  private _chain: string;
  private _router: string;
  private _routerAbi: ContractInterface;
  private _gasLimit: number;
  private _ttl: number;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor(chain: string, network: string) {
    this._chain = chain;
    const config = UniswapConfig.config;
    this.ethereum = Ethereum.getInstance(network);
    this.chainId = this.ethereum.chainId;
    this._ttl = UniswapConfig.config.ttl;
    this._routerAbi = routerAbi.abi;
    this._gasLimit = UniswapConfig.config.gasLimit;
    this._router = config.uniswapV2RouterAddress(network);
  }

  public static getInstance(chain: string, network: string): Uniswap {
    if (Uniswap._instances === undefined) {
      Uniswap._instances = {};
    }
    if (!(chain + network in Uniswap._instances)) {
      Uniswap._instances[chain + network] = new Uniswap(chain, network);
    }

    return Uniswap._instances[chain + network];
  }

  public getTokenByAddress(address: string): Token {
    return this.tokenList[address];
  }

  public async init() {
    if (this._chain == 'ethereum' && !this.ethereum.ready())
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    for (const token of this.ethereum.storedTokenList) {
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
    const allowedSlippage = UniswapConfig.config.allowedSlippage;
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
      this.ethereum.provider
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
      this.ethereum.provider
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

  // given a wallet and a Uniswap trade, try to execute it on the Ethereum block chain.
  async executeTrade(
    wallet: Wallet,
    trade: Trade,
    gasPrice: number,
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
      allowedSlippage: this.getSlippagePercentage(),
    });

    const contract = new Contract(uniswapRouter, abi, wallet);
    if (!nonce) {
      nonce = await this.ethereum.nonceManager.getNonce(wallet.address);
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
    await this.ethereum.nonceManager.commitNonce(wallet.address, nonce);
    return tx;
  }
}
