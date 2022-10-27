import { UniswapishPriceError } from '../../services/error-handler';
import { isFractionString } from '../../services/validators';
import { DefiraConfig } from './defira.config';
import routerAbi from './defira_v2_router_abi.json';
import {
  Contract,
  ContractInterface,
  ContractTransaction,
} from '@ethersproject/contracts';
import {
  Router as DefiraRouter,
  Pair as DefiraPair,
  SwapParameters,
  Trade as DefiraTrade,
  Fetcher as DefiraFetcher,
} from '@zuzu-cat/defira-sdk';

import { Percent, Token, CurrencyAmount, TradeType } from '@uniswap/sdk-core';
import { BigNumber, Transaction, Wallet } from 'ethers';
import { logger } from '../../services/logger';
import { percentRegexp } from '../../services/config-manager-v2';
import { Harmony } from '../../chains/harmony/harmony';
import { ExpectedTrade, Uniswapish } from '../../services/common-interfaces';

export class Defira implements Uniswapish {
  private static _instances: { [name: string]: Defira };
  private harmony: Harmony;
  private _router: string;
  private _factory: string | null;
  private _routerAbi: ContractInterface;
  private _initCodeHash: string;
  private _gasLimitEstimate: number;
  private _ttl: number;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor(network: string) {
    const config = DefiraConfig.config;
    this.harmony = Harmony.getInstance(network);
    this.chainId = this.harmony.chainId;
    this._ttl = config.ttl();
    this._routerAbi = routerAbi.abi;
    this._gasLimitEstimate = config.gasLimitEstimate();
    this._router = config.routerAddress(network);
    this._initCodeHash = config.initCodeHash(network);
    this._factory = null;
  }

  public static getInstance(chain: string, network: string): Defira {
    if (Defira._instances === undefined) {
      Defira._instances = {};
    }
    if (!(chain + network in Defira._instances)) {
      Defira._instances[chain + network] = new Defira(network);
    }

    return Defira._instances[chain + network];
  }

  /**
   * Given a token's address, return the connector's native representation of
   * the token.
   *
   * @param address Token address
   */
  public getTokenByAddress(address: string): Token {
    return this.tokenList[address];
  }

  public async init() {
    if (!this.harmony.ready()) {
      await this.harmony.init();
    }
    for (const token of this.harmony.storedTokenList) {
      this.tokenList[token.address] = new Token(
        token.chainId || this.chainId,
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

  /**
   * Router address.
   */
  public get router(): string {
    return this._router;
  }

  /**
   * Lazily computed factory address.
   */
  public get factory(): Promise<string> {
    // boilerplate to support async getter
    return (async () => {
      if (!this._factory) {
        const routerContract = new Contract(
          this.router,
          this.routerAbi,
          this.provider()
        );
        this._factory = await routerContract.factory();
      }
      return this._factory as string;
    })();
  }

  /**
   * Init code hash of Defira DEX Pair contract, used to compute individual pair addresses without network lookups
   */
  public get initCodeHash(): string {
    return this._initCodeHash;
  }

  // in place for mocking
  async fetchPairData(tokenA: Token, tokenB: Token): Promise<DefiraPair> {
    return await DefiraFetcher.fetchPairData(
      tokenA,
      tokenB,
      await this.factory,
      this.initCodeHash,
      this.provider()
    );
  }

  // in place for mocking
  provider(): any {
    return this.harmony.provider;
  }

  /**
   * Router smart contract ABI.
   */
  public get routerAbi(): ContractInterface {
    return this._routerAbi;
  }

  /**
   * Default gas limit for swap transactions.
   */
  public get gasLimitEstimate(): number {
    return this._gasLimitEstimate;
  }

  /**
   * Default time-to-live for swap transactions, in seconds.
   */
  public get ttl(): number {
    return this._ttl;
  }

  /**
   * Gets the allowed slippage percent from the optional parameter or the value
   * in the configuration.
   *
   * @param allowedSlippageStr (Optional) should be of the form '1/10'.
   */
  public getAllowedSlippage(allowedSlippageStr?: string): Percent {
    if (allowedSlippageStr != null && isFractionString(allowedSlippageStr)) {
      const fractionSplit = allowedSlippageStr.split('/');
      return new Percent(fractionSplit[0], fractionSplit[1]);
    }

    const allowedSlippage = DefiraConfig.config.allowedSlippage();
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return new Percent(nd[1], nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  /**
   * Given the amount of `baseToken` to put into a transaction, calculate the
   * amount of `quoteToken` that can be expected from the transaction.
   *
   * This is typically used for calculating token sell prices.
   *
   * @param baseToken Token input for the transaction
   * @param quoteToken Output from the transaction
   * @param amount Amount of `baseToken` to put into the transaction
   */
  async estimateSellTrade(
    baseToken: Token,
    quoteToken: Token,
    amount: BigNumber,
    allowedSlippage?: string
  ): Promise<ExpectedTrade> {
    const baseTokenAmount = CurrencyAmount.fromRawAmount(
      baseToken,
      amount.toString()
    );

    logger.info(
      `Fetching pair data for ${baseToken.address}-${quoteToken.address}.`
    );

    const pair: DefiraPair = await this.fetchPairData(quoteToken, baseToken);
    const trades: DefiraTrade<Token, Token, TradeType.EXACT_INPUT>[] =
      DefiraTrade.bestTradeExactIn([pair], baseTokenAmount, quoteToken, {
        maxHops: 1,
      });
    if (!trades || trades.length === 0) {
      throw new UniswapishPriceError(
        `priceSwapIn: no trade pair found for ${baseToken.address} to ${quoteToken.address}.`
      );
    }
    logger.info(
      `Best trade for ${baseToken.address}-${quoteToken.address}: ` +
        `${trades[0].executionPrice.toFixed(6)}` +
        `${baseToken.name}.`
    );
    const expectedAmount = trades[0].minimumAmountOut(
      this.getAllowedSlippage(allowedSlippage)
    );
    return { trade: trades[0], expectedAmount };
  }

  /**
   * Given the amount of `baseToken` desired to acquire from a transaction,
   * calculate the amount of `quoteToken` needed for the transaction.
   *
   * This is typically used for calculating token buy prices.
   *
   * @param quoteToken Token input for the transaction
   * @param baseToken Token output from the transaction
   * @param amount Amount of `baseToken` desired from the transaction
   */
  async estimateBuyTrade(
    quoteToken: Token,
    baseToken: Token,
    amount: BigNumber,
    allowedSlippage?: string
  ): Promise<ExpectedTrade> {
    const baseTokenAmount = CurrencyAmount.fromRawAmount(
      baseToken,
      amount.toString()
    );
    logger.info(
      `Fetching pair data for ${quoteToken.address}-${baseToken.address}.`
    );
    const pair: DefiraPair = await this.fetchPairData(quoteToken, baseToken);
    const trades: DefiraTrade<Token, Token, TradeType.EXACT_OUTPUT>[] =
      DefiraTrade.bestTradeExactOut([pair], quoteToken, baseTokenAmount, {
        maxHops: 1,
      });
    if (!trades || trades.length === 0) {
      throw new UniswapishPriceError(
        `priceSwapOut: no trade pair found for ${quoteToken.address} to ${baseToken.address}.`
      );
    }
    logger.info(
      `Best trade for ${quoteToken.address}-${baseToken.address}: ` +
        `${trades[0].executionPrice.invert().toFixed(6)} ` +
        `${baseToken.name}.`
    );

    const expectedAmount = trades[0].maximumAmountIn(
      this.getAllowedSlippage(allowedSlippage)
    );
    return { trade: trades[0], expectedAmount };
  }

  /**
   * Given a wallet and a defira trade, try to execute it on blockchain.
   *
   * @param wallet Wallet
   * @param trade Expected trade
   * @param gasPrice Base gas price, for pre-EIP1559 transactions
   * @param defiraRouter Router smart contract address
   * @param ttl How long the swap is valid before expiry, in seconds
   * @param abi Router contract ABI
   * @param gasLimit Gas limit
   * @param nonce (Optional) EVM transaction nonce
   */
  async executeTrade(
    wallet: Wallet,
    trade: DefiraTrade<Token, Token, TradeType>,
    gasPrice: number,
    defiraRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    _1?: BigNumber,
    _2?: BigNumber,
    allowedSlippage?: string
  ): Promise<Transaction> {
    const result: SwapParameters = DefiraRouter.swapCallParameters(trade, {
      ttl,
      recipient: wallet.address,
      allowedSlippage: this.getAllowedSlippage(allowedSlippage),
    });

    const contract: Contract = new Contract(defiraRouter, abi, wallet);
    return this.harmony.nonceManager.provideNonce(
      nonce,
      wallet.address,
      async (nextNonce) => {
        const tx: ContractTransaction = await contract[result.methodName](
          ...result.args,
          {
            gasPrice: (gasPrice * 1e9).toFixed(0),
            gasLimit: gasLimit.toFixed(0),
            value: result.value,
            nonce: nextNonce,
          }
        );

        logger.info(JSON.stringify(tx));
        return tx;
      }
    );
  }
}
