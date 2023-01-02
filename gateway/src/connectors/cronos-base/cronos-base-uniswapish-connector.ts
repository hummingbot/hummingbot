import {
  ExpectedTrade,
  Pairish,
  Percentish,
  TokenAmountish,
  Tokenish,
  Uniswapish,
  UniswapishAmount,
  UniswapishCurrency,
  UniswapishSwapParameters,
  UniswapishTrade,
} from '../../services/common-interfaces';
import {
  BigNumber,
  Contract,
  ContractInterface,
  ContractTransaction,
  Transaction,
  Wallet,
} from 'ethers';
import { CronosBaseUniswapishConnectorConfig } from './cronos-base-uniswapish-connector.config';
import { Cronos } from '../../chains/cronos/cronos';
import { logger } from '../../services/logger';
import { UniswapishPriceError } from '../../services/error-handler';
import { isFractionString } from '../../services/validators';
import { percentRegexp } from '../../services/config-manager-v2';

export abstract class CronosBaseUniswapishConnector implements Uniswapish {
  private static _instances: { [name: string]: CronosBaseUniswapishConnector };
  private _config: CronosBaseUniswapishConnectorConfig.NetworkConfig;
  private _cronos: Cronos;
  private _chainId: number;
  private _chain: string;
  private _router: string;
  private _ttl: number;
  private _gasLimitEstimate: number;
  private _tokenList: Record<string, Tokenish> = {};
  private _ready: boolean = false;

  protected constructor(
    private _sdkProvider: CronosBaseUniswapishSDKProvider,
    private readonly _routerAbi: ContractInterface,
    chain: string,
    network: string
  ) {
    this._config = this.buildConfig();
    this._cronos = Cronos.getInstance(network);
    this._chainId = this._cronos.chainId;
    this._chain = chain;
    this._router = this._config.routerAddress(network);
    this._ttl = this._config.ttl;
    this._gasLimitEstimate = this._config.gasLimitEstimate;
  }

  public async init() {
    if (this._chain == 'cronos' && !this._cronos.ready())
      throw new Error('Cronos is not available');
    for (const token of this._cronos.storedTokenList) {
      this._tokenList[token.address] = this._sdkProvider.buildToken(
        this._chainId,
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

  protected abstract buildConfig(): CronosBaseUniswapishConnectorConfig.NetworkConfig;

  /**
   * Router address.
   */
  public get router(): string {
    return this._router;
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
   * Given a token's address, return the connector's native representation of
   * the token.
   *
   * @param address Token address
   */
  public getTokenByAddress(address: string): Tokenish {
    return this._tokenList[address];
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
   * @param allowedSlippage The slippage amount allowed
   */
  public async estimateSellTrade(
    baseToken: Tokenish,
    quoteToken: Tokenish,
    amount: BigNumber,
    allowedSlippage?: string
  ): Promise<ExpectedTrade> {
    const nativeTokenAmount: TokenAmountish =
      this._sdkProvider.buildTokenAmount(baseToken, amount);
    logger.info(
      `Fetching pair data for ${baseToken.address}-${quoteToken.address}.`
    );
    const pair: Pairish = await this._sdkProvider.fetchPairData(
      baseToken,
      quoteToken,
      this._cronos.provider
    );
    const trades: UniswapishTrade[] = this._sdkProvider.bestTradeExactIn(
      [pair],
      nativeTokenAmount,
      quoteToken,
      { maxHops: 1 }
    );
    if (!trades || trades.length === 0) {
      throw new UniswapishPriceError(
        `priceSwapIn: no trade pair found for ${baseToken} to ${quoteToken}.`
      );
    }
    logger.info(
      `Best trade for ${baseToken.address}-${quoteToken.address}: ${trades[0]}`
    );
    const expectedAmount = this._sdkProvider.minimumAmountOut(
      trades[0],
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
   * @param allowedSlippage The slippage amount allowed
   */
  public async estimateBuyTrade(
    quoteToken: Tokenish,
    baseToken: Tokenish,
    amount: BigNumber,
    allowedSlippage?: string
  ): Promise<ExpectedTrade> {
    const nativeTokenAmount: TokenAmountish =
      this._sdkProvider.buildTokenAmount(baseToken, amount);
    logger.info(
      `Fetching pair data for ${quoteToken.address}-${baseToken.address}.`
    );
    const pair: Pairish = await this._sdkProvider.fetchPairData(
      quoteToken,
      baseToken,
      this._cronos.provider
    );
    const trades: UniswapishTrade[] = this._sdkProvider.bestTradeExactOut(
      [pair],
      quoteToken,
      nativeTokenAmount,
      { maxHops: 1 }
    );
    if (!trades || trades.length === 0) {
      throw new UniswapishPriceError(
        `priceSwapOut: no trade pair found for ${quoteToken.address} to ${baseToken.address}.`
      );
    }
    logger.info(
      `Best trade for ${quoteToken.address}-${baseToken.address}: ${trades[0]}`
    );

    const expectedAmount = this._sdkProvider.maximumAmountIn(
      trades[0],
      this.getAllowedSlippage(allowedSlippage)
    );
    return { trade: trades[0], expectedAmount };
  }

  /**
   * Given a wallet and a Uniswap-ish trade, try to execute it on blockchain.
   *
   * @param wallet Wallet
   * @param trade Expected trade
   * @param gasPrice Base gas price, for pre-EIP1559 transactions
   * @param CronosBaseUniswapishConnectorRoute Router smart contract address
   * @param ttl How long the swap is valid before expiry, in seconds
   * @param abi Router contract ABI
   * @param gasLimit Gas limit
   * @param nonce (Optional) EVM transaction nonce
   * @param maxFeePerGas (Optional) Maximum total fee per gas you want to pay
   * @param maxPriorityFeePerGas (Optional) Maximum tip per gas you want to pay
   * @param allowedSlippage The slippage amount allowe
   */
  public async executeTrade(
    wallet: Wallet,
    trade: UniswapishTrade,
    gasPrice: number,
    CronosBaseUniswapishConnectorRoute: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber,
    allowedSlippage?: string
  ): Promise<Transaction> {
    const result = this._sdkProvider.swapCallParameters(trade, {
      ttl,
      recipient: wallet.address,
      allowedSlippage: this.getAllowedSlippage(allowedSlippage),
    });

    const contract = new Contract(
      CronosBaseUniswapishConnectorRoute,
      abi,
      wallet
    );
    return this._cronos.nonceManager.provideNonce(
      nonce,
      wallet.address,
      async (nextNonce) => {
        let tx: ContractTransaction;
        if (maxFeePerGas || maxPriorityFeePerGas) {
          tx = await contract[result.methodName](...result.args, {
            gasLimit: gasLimit,
            value: result.value,
            nonce: nextNonce,
            maxFeePerGas,
            maxPriorityFeePerGas,
          });
        } else {
          tx = await contract[result.methodName](...result.args, {
            gasPrice: (gasPrice * 1e9).toFixed(0),
            gasLimit: gasLimit.toFixed(0),
            value: result.value,
            nonce: nextNonce,
          });
        }

        logger.info(`Transaction Details: ${JSON.stringify(tx)}`);
        return tx;
      }
    );
  }

  /**
   * Gets the allowed slippage percent from the optional parameter or the value
   * in the configuration.
   *
   * @param allowedSlippageStr (Optional) should be of the form '1/10'.
   */
  public getAllowedSlippage(allowedSlippageStr?: string): Percentish {
    if (allowedSlippageStr != null && isFractionString(allowedSlippageStr)) {
      const fractionSplit = allowedSlippageStr.split('/');
      return this._sdkProvider.buildPercent(fractionSplit[0], fractionSplit[1]);
    }

    const allowedSlippage = this._config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return this._sdkProvider.buildPercent(nd[1], nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  public static getInstance<T extends CronosBaseUniswapishConnector>(
    this: { new (chain: string, network: string): T }, // see https://stackoverflow.com/questions/45123761/instantiating-child-class-from-a-static-method-in-base-class-using-typescript
    chain: string,
    network: string
  ): CronosBaseUniswapishConnector {
    if (CronosBaseUniswapishConnector._instances == undefined) {
      CronosBaseUniswapishConnector._instances = {};
    }

    const instanceName = chain + network + this.name;

    if (!(instanceName in CronosBaseUniswapishConnector._instances)) {
      CronosBaseUniswapishConnector._instances[instanceName] = new this(
        chain,
        network
      );
    }

    return CronosBaseUniswapishConnector._instances[instanceName];
  }
}

export interface CronosBaseUniswapishSDKProvider {
  buildToken(
    chainId: number,
    address: string,
    decimals: number,
    symbol?: string,
    name?: string,
    projectLink?: string
  ): Tokenish;

  buildTokenAmount(token: Tokenish, amount: BigNumber): TokenAmountish;

  fetchPairData(
    tokenA: Tokenish,
    tokenB: Tokenish,
    provider?: import('@ethersproject/providers').BaseProvider
  ): Promise<Pairish>;

  bestTradeExactIn(
    pairs: Pairish[],
    currencyAmountIn: UniswapishAmount,
    currencyOut: UniswapishCurrency,
    bestTradeOptions?: {
      maxNumResults?: number;
      maxHops?: number;
    },
    currentPairs?: Pairish[],
    originalAmountIn?: UniswapishAmount,
    bestTrades?: UniswapishTrade[]
  ): UniswapishTrade[];

  bestTradeExactOut(
    pairs: Pairish[],
    currencyIn: UniswapishCurrency,
    currencyAmountOut: UniswapishAmount,
    bestTradeOptions?: {
      maxNumResults?: number;
      maxHops?: number;
    },
    currentPairs?: Pairish[],
    originalAmountOut?: UniswapishAmount,
    bestTrades?: UniswapishTrade[]
  ): UniswapishTrade[];

  buildPercent(numerator: string, denominator?: string): Percentish;

  minimumAmountOut(
    trade: UniswapishTrade,
    slippageTolerance: Percentish
  ): UniswapishAmount;

  maximumAmountIn(
    trade: UniswapishTrade,
    slippageTolerance: Percentish
  ): UniswapishAmount;

  swapCallParameters(
    trade: UniswapishTrade,
    tradeOptions: {
      allowedSlippage: Percentish;
      ttl: number;
      recipient: string;
      feeOnTransfer?: boolean;
      deadline?: number;
    }
  ): UniswapishSwapParameters;
}
