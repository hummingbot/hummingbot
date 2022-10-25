import { UniswapishPriceError as AMMishPriceError } from '../../services/error-handler';
import { isFractionString } from '../../services/validators';
import { RefConfig } from './ref.config';
import {
  estimateSwap,
  EstimateSwapView,
  fetchAllPools,
  instantSwap,
  SwapOptions,
  TokenMetadata,
  Transaction,
  toReadableNumber,
  Pool,
} from 'coinalpha-ref-sdk';
import { logger } from '../../services/logger';
import { percentRegexp } from '../../services/config-manager-v2';
import { RefAMMish } from '../../services/common-interfaces';
import { Near } from '../../chains/near/near';
import { Account } from 'near-api-js';
import { SignedTransaction } from 'near-api-js/lib/transaction';
import { getSignedTransactions, sendTransactions } from './ref.helper';
import { FinalExecutionOutcome } from 'near-api-js/lib/providers';

export type ExpectedTrade = {
  trade: EstimateSwapView[];
  expectedAmount: string;
};

type PoolEntries = {
  [key: string]: { inputAmount: string; outputAmount: string };
};

export class Ref implements RefAMMish {
  private static _instances: { [name: string]: Ref };
  private near: Near;
  private _router: string;
  private _gasLimitEstimate: number;
  private _ttl: number;
  private tokenList: Record<string, TokenMetadata> = {};
  private _ready: boolean = false;
  private _cachedPools: Pool[] = [];

  private constructor(network: string) {
    const config = RefConfig.config;
    this.near = Near.getInstance(network);
    this._ttl = RefConfig.config.ttl;
    this._gasLimitEstimate = RefConfig.config.gasLimitEstimate;
    this._router = config.routerAddress(network);
  }

  public static getInstance(chain: string, network: string): Ref {
    if (Ref._instances === undefined) {
      Ref._instances = {};
    }
    if (!(chain + network in Ref._instances)) {
      Ref._instances[chain + network] = new Ref(network);
    }

    return Ref._instances[chain + network];
  }

  /**
   * Given a token's address, return the connector's native representation of
   * the token.
   *
   * @param address Token address
   */
  public getTokenByAddress(address: string): TokenMetadata {
    return this.tokenList[address];
  }

  public async init() {
    if (!this.near.ready()) {
      await this.near.init();
    }
    for (const token of this.near.storedTokenList) {
      this.tokenList[token.address] = {
        id: token.address,
        decimals: token.decimals,
        symbol: token.symbol,
        name: token.name,
        icon: '',
      };
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
  public getAllowedSlippage(allowedSlippageStr?: string): number {
    if (allowedSlippageStr != null && isFractionString(allowedSlippageStr)) {
      const fractionSplit = allowedSlippageStr.split('/');
      return Number(fractionSplit[0]) / Number(fractionSplit[1]);
    }

    const allowedSlippage = RefConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return Number(nd[1]) / Number(nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  /**
   * Calculated expected execution price and expected amount in after a swap/trade
   * @param trades The trade path object
   */
  parseTrade(
    trades: EstimateSwapView[],
    side: string
  ): {
    estimatedPrice: string;
    expectedAmount: string;
  } {
    const paths: PoolEntries = {};
    for (const trade of trades) {
      if (trade.nodeRoute) {
        if (!paths[trade.nodeRoute.join()])
          paths[trade.nodeRoute.join()] = {
            inputAmount: '0',
            outputAmount: '0',
          };

        if (trade.inputToken === trade.nodeRoute[0]) {
          const token: TokenMetadata[] = <TokenMetadata[]>(
            trade.tokens?.filter((t) => t.id === trade.inputToken)
          );

          paths[trade.nodeRoute.join()].inputAmount = toReadableNumber(
            token[0].decimals,
            trade.pool.partialAmountIn
          );
        } else if (
          trade.outputToken === trade.nodeRoute[trade.nodeRoute.length - 1]
        ) {
          paths[trade.nodeRoute.join()].outputAmount = trade.estimate;
        }
      }
    }
    let expectedAmount = 0,
      amountIn = 0;
    Object.values(paths).forEach((entries) => {
      expectedAmount += Number(entries.outputAmount);
      amountIn += Number(entries.inputAmount);
    });
    return {
      estimatedPrice:
        side.toUpperCase() === 'BUY'
          ? String(amountIn / expectedAmount)
          : String(expectedAmount / amountIn),
      expectedAmount: String(expectedAmount),
    };
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
    baseToken: TokenMetadata,
    quoteToken: TokenMetadata,
    amount: string,
    _allowedSlippage?: string
  ): Promise<ExpectedTrade> {
    logger.info(`Fetching pair data for ${baseToken.id}-${quoteToken.id}.`);

    const { simplePools } = await fetchAllPools();
    this._cachedPools = simplePools;

    const options: SwapOptions = {
      enableSmartRouting: true,
    };
    const trades: EstimateSwapView[] = await estimateSwap({
      tokenIn: baseToken,
      tokenOut: quoteToken,
      amountIn: amount,
      simplePools,
      options,
    });
    if (!trades || trades.length === 0) {
      throw new AMMishPriceError(
        `priceSwapIn: no trade pair found for ${baseToken} to ${quoteToken}.`
      );
    }
    const { estimatedPrice, expectedAmount } = this.parseTrade(trades, 'SELL');
    logger.info(
      `Best trade for ${baseToken.id}-${quoteToken.id}: ` +
        `${estimatedPrice}` +
        `${baseToken.name}.`
    );
    return { trade: trades, expectedAmount };
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
    quoteToken: TokenMetadata,
    baseToken: TokenMetadata,
    amount: string,
    _allowedSlippage?: string
  ): Promise<ExpectedTrade> {
    const buyEstimate: ExpectedTrade = await this.estimateSellTrade(
      baseToken,
      quoteToken,
      amount
    );

    const options: SwapOptions = {
      enableSmartRouting: true,
    };

    const trades: EstimateSwapView[] = await estimateSwap({
      tokenIn: quoteToken,
      tokenOut: baseToken,
      amountIn: buyEstimate.expectedAmount,
      simplePools: this._cachedPools,
      options,
    });
    if (!trades || trades.length === 0) {
      throw new AMMishPriceError(
        `priceSwapOut: no trade pair found for ${quoteToken.id} to ${baseToken.id}.`
      );
    }

    const { estimatedPrice, expectedAmount } = this.parseTrade(trades, 'BUY');
    logger.info(
      `Best trade for ${quoteToken.id}-${baseToken.id}: ` +
        `${estimatedPrice} ` +
        `${baseToken.name}.`
    );

    return { trade: trades, expectedAmount };
  }

  /**
   * Given an Account and a Ref trade, try to execute it on blockchain.
   *
   * @param account Account
   * @param trade Expected trade
   * @param amountIn Amount to swap in
   * @param tokenIn Token to be sent
   * @param tokenOut Token to be received
   * @param allowedSlippage Maximum allowable slippage
   */
  async executeTrade(
    account: Account,
    trade: EstimateSwapView[],
    amountIn: string,
    tokenIn: TokenMetadata,
    tokenOut: TokenMetadata,
    allowedSlippage?: string
  ): Promise<FinalExecutionOutcome> {
    const transactionsRef: Transaction[] = await instantSwap({
      tokenIn,
      tokenOut,
      amountIn,
      slippageTolerance: this.getAllowedSlippage(allowedSlippage),
      swapTodos: trade,
      AccountId: account.accountId,
    });

    const signedTransactions: SignedTransaction[] = await getSignedTransactions(
      { transactionsRef, account }
    );
    const transaction: FinalExecutionOutcome[] = await sendTransactions({
      signedTransactions,
      provider: account.connection.provider,
    });

    logger.info(JSON.stringify(transaction));
    return transaction[0];
  }
}
