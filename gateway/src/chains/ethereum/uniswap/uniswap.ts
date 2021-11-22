import { ConfigManager } from '../../../services/config-manager';
import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../../services/error-handler';
import { EthereumConfig } from '../ethereum.config';
import { Ethereum } from '../ethereum';
import { UniswapConfig } from './uniswap.config';
import {
  CurrencyAmount,
  Fetcher,
  Percent,
  Router,
  Token,
  TokenAmount,
  Trade,
} from '@uniswap/sdk';
import routerAbi from './uniswap_v2_router_abi.json';
import { UniswapBase } from '../../../services/uniswap-base';
import { ContractInterface } from '@ethersproject/contracts';
export interface ExpectedTrade {
  trade: Trade;
  expectedAmount: CurrencyAmount;
}
export class Uniswap extends UniswapBase {
  private static instance: Uniswap;
  private _uniswapRouter: string;
  private _routerAbi: ContractInterface;
  private _gasLimit: number;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;
  private _ttl: number;

  private constructor() {
    super(Ethereum.getInstance());
    let config;
    if (ConfigManager.config.ETHEREUM_CHAIN === 'mainnet') {
      config = UniswapConfig.config.mainnet;
    } else {
      config = UniswapConfig.config.kovan;
    }
    this._ttl = ConfigManager.config.UNISWAP_TTL;
    this._routerAbi = routerAbi.abi;
    this._gasLimit = ConfigManager.config.UNISWAP_GAS_LIMIT;

    this._uniswapRouter = config.uniswapV2RouterAddress;
    if (ConfigManager.config.ETHEREUM_CHAIN === 'mainnet') {
      this.chainId = EthereumConfig.config.mainnet.chainId;
    } else {
      this.chainId = EthereumConfig.config.kovan.chainId;
    }
  }

  public static getInstance(): Uniswap {
    if (!Uniswap.instance) {
      Uniswap.instance = new Uniswap();
    }

    return Uniswap.instance;
  }

  public getTokenByAddress(address: string): Token {
    return this.tokenList[address];
  }

  public async init() {
    if (!Ethereum.getInstance().ready())
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    for (const token of Ethereum.getInstance().storedTokenList) {
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

  public get uniswapRouter(): string {
    return this._uniswapRouter;
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
    const allowedSlippage = ConfigManager.config.UNISWAP_ALLOWED_SLIPPAGE;
    const nd = allowedSlippage.match(ConfigManager.percentRegexp);
    if (nd) return new Percent(nd[1], nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  // // get the expected amount of token out, for a given pair and a token amount in.
  // // this only considers direct routes.
  // async priceSwapIn(
  //   tokenInAddress: string,
  //   tokenOutAddress: string,
  //   tokenInAmount: BigNumber
  // ): Promise<ExpectedTrade | string> {
  //   const tokenIn = this.tokenList[tokenInAddress];
  //   if (!tokenIn)
  //     return `priceSwapIn: tokenInAddress ${tokenInAddress} not found in tokenList.`;
  //   const tokenOut = this.tokenList[tokenOutAddress];
  //   if (!tokenOut)
  //     return `priceSwapIn: tokenOutAddress ${tokenOutAddress} not found in tokenList.`;

  //   const tokenInAmount_ = new TokenAmount(tokenIn, tokenInAmount.toString());
  //   logger.info(
  //     `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
  //   );
  //   const pair = await Fetcher.fetchPairData(tokenIn, tokenOut);
  //   const trades = Trade.bestTradeExactIn([pair], tokenInAmount_, tokenOut, {
  //     maxHops: 1,
  //   });
  //   if (!trades || trades.length === 0)
  //     return `priceSwapIn: no trade pair found for ${tokenInAddress} to ${tokenOutAddress}.`;
  //   logger.info(
  //     `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
  //   );
  //   const expectedAmount = trades[0].minimumAmountOut(
  //     this.getSlippagePercentage(ConfigManager.config.UNISWAP_ALLOWED_SLIPPAGE)
  //   );
  //   return { trade: trades[0], expectedAmount };
  // }

  // async priceSwapOut(
  //   tokenInAddress: string,
  //   tokenOutAddress: string,
  //   tokenOutAmount: BigNumber
  // ): Promise<ExpectedTrade | string> {
  //   const tokenIn = this.tokenList[tokenInAddress];
  //   if (!tokenIn)
  //     return `priceSwapOut: tokenInAddress ${tokenInAddress} not found in tokenList.`;
  //   const tokenOut = this.tokenList[tokenOutAddress];
  //   if (!tokenOut)
  //     return `priceSwapOut: tokenOutAddress ${tokenOutAddress} not found in tokenList.`;
  //   const tokenOutAmount_ = new TokenAmount(
  //     tokenOut,
  //     tokenOutAmount.toString()
  //   );

  //   logger.info(
  //     `Fetching pair data for ${tokenIn.address}-${tokenOut.address}.`
  //   );
  //   const pair = await Fetcher.fetchPairData(tokenIn, tokenOut);
  //   const trades = Trade.bestTradeExactOut([pair], tokenIn, tokenOutAmount_, {
  //     maxHops: 1,
  //   });
  //   if (!trades || trades.length === 0)
  //     return `priceSwapOut: no trade pair found for ${tokenInAddress} to ${tokenOutAddress}.`;
  //   logger.info(
  //     `Best trade for ${tokenIn.address}-${tokenOut.address}: ${trades[0]}`
  //   );

  //   const expectedAmount = trades[0].maximumAmountIn(
  //     this.getSlippagePercentage(ConfigManager.config.UNISWAP_ALLOWED_SLIPPAGE)
  //   );
  //   return { trade: trades[0], expectedAmount };
  // }

  // // given a wallet and a Uniswap trade, try to execute it on the Ethereum block chain.
  // async executeTrade(
  //   wallet: Wallet,
  //   trade: Trade,
  //   gasPrice: number,
  //   nonce?: number,
  //   maxFeePerGas?: BigNumber,
  //   maxPriorityFeePerGas?: BigNumber
  // ): Promise<Transaction> {
  //   const result = Router.swapCallParameters(trade, {
  //     ttl: ConfigManager.config.UNISWAP_TTL,
  //     recipient: wallet.address,
  //     allowedSlippage: this.getSlippagePercentage(
  //       ConfigManager.config.UNISWAP_ALLOWED_SLIPPAGE
  //     ),
  //   });

  //   const contract = new Contract(this._uniswapRouter, routerAbi.abi, wallet);
  //   if (!nonce) {
  //     nonce = await this.ethereum.nonceManager.getNonce(wallet.address);
  //   }
  //   let tx;
  //   if (maxFeePerGas || maxPriorityFeePerGas) {
  //     tx = await contract[result.methodName](...result.args, {
  //       gasLimit: ConfigManager.config.UNISWAP_GAS_LIMIT,
  //       value: result.value,
  //       nonce: nonce,
  //       maxFeePerGas,
  //       maxPriorityFeePerGas,
  //     });
  //   } else {
  //     tx = await contract[result.methodName](...result.args, {
  //       gasPrice: gasPrice * 1e9,
  //       gasLimit: ConfigManager.config.UNISWAP_GAS_LIMIT,
  //       value: result.value,
  //       nonce: nonce,
  //     });
  //   }

  //   logger.info(tx);
  //   await this.ethereum.nonceManager.commitNonce(wallet.address, nonce);
  //   return tx;
  // }
}
