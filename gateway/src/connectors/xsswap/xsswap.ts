import { percentRegexp } from '../../services/config-manager-v2';
import { UniswapishPriceError } from '../../services/error-handler';
import { BigNumber, Contract, ContractInterface, Transaction, Wallet } from 'ethers';
import { isFractionString } from '../../services/validators';
import { XsswapConfig } from './xsswap.config';
import routerAbi from './xsswap_v2_router_abi.json';
import { Fetcher, Percent, Router, Token, TokenAmount, Trade, Pair } from 'xsswap-sdk';
import { logger } from '../../services/logger';
import { Xdc } from '../../chains/xdc/xdc';
import { ExpectedTrade, Uniswapish } from '../../services/common-interfaces';

export class Xsswap implements Uniswapish {
  private static _instances: { [name: string]: Xsswap };
  private xdc: Xdc;
  private _router: string;
  private _routerAbi: ContractInterface;
  private _gasLimitEstimate: number;
  private _ttl: number;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor(network: string) {
    const config = XsswapConfig.config;
    this.xdc = Xdc.getInstance(network);
    this.chainId = this.xdc.chainId;
    this._router = config.routerAddress(network);
    this._ttl = config.ttl;
    this._routerAbi = routerAbi.abi;
    this._gasLimitEstimate = config.gasLimitEstimate;
  }

  public static getInstance(chain: string, network: string): Xsswap {
    if (Xsswap._instances === undefined) {
      Xsswap._instances = {};
    }
    if (!(chain + network in Xsswap._instances)) {
      Xsswap._instances[chain + network] = new Xsswap(network);
    }

    return Xsswap._instances[chain + network];
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
    if (!this.xdc.ready()) {
      await this.xdc.init();
    }
    for (const token of this.xdc.storedTokenList) {
      this.tokenList[token.address] = new Token(this.chainId, token.address, token.decimals, token.symbol, token.name);
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
   * Router smart contract ABI.
   */
  public get routerAbi(): ContractInterface {
    return this._routerAbi;
  }

  /**
   * Default gas limit used to estimate cost for swap transactions.
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

    const allowedSlippage = XsswapConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return new Percent(nd[1], nd[2]);
    throw new Error('Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.');
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
  async estimateSellTrade(baseToken: Token, quoteToken: Token, amount: BigNumber, allowedSlippage?: string): Promise<ExpectedTrade> {
    const nativeTokenAmount: TokenAmount = new TokenAmount(baseToken, amount.toString());
    logger.info(`Fetching pair data for ${baseToken.address}-${quoteToken.address}.`);
    const pair: Pair = await Fetcher.fetchPairData(baseToken, quoteToken, this.xdc.provider);
    const trades: Trade[] = Trade.bestTradeExactIn([pair], nativeTokenAmount, quoteToken, { maxHops: 1 });
    if (!trades || trades.length === 0) {
      throw new UniswapishPriceError(`priceSwapIn: no trade pair found for ${baseToken} to ${quoteToken}.`);
    }
    logger.info(`Best trade for ${baseToken.address}-${quoteToken.address}: ${trades[0]}`);
    const expectedAmount = trades[0].minimumAmountOut(this.getAllowedSlippage(allowedSlippage));
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
  async estimateBuyTrade(quoteToken: Token, baseToken: Token, amount: BigNumber, allowedSlippage?: string): Promise<ExpectedTrade> {
    const nativeTokenAmount: TokenAmount = new TokenAmount(baseToken, amount.toString());
    logger.info(`Fetching pair data for ${quoteToken.address}-${baseToken.address}.`);
    const pair: Pair = await Fetcher.fetchPairData(quoteToken, baseToken, this.xdc.provider);
    const trades: Trade[] = Trade.bestTradeExactOut([pair], quoteToken, nativeTokenAmount, { maxHops: 1 });
    if (!trades || trades.length === 0) {
      throw new UniswapishPriceError(`priceSwapOut: no trade pair found for ${quoteToken.address} to ${baseToken.address}.`);
    }
    logger.info(`Best trade for ${quoteToken.address}-${baseToken.address}: ${trades[0]}`);

    const expectedAmount = trades[0].maximumAmountIn(this.getAllowedSlippage(allowedSlippage));
    return { trade: trades[0], expectedAmount };
  }

  /**
   * Given a wallet and a Uniswap-ish trade, try to execute it on blockchain.
   *
   * @param wallet Wallet
   * @param trade Expected trade
   * @param gasPrice Base gas price, for pre-EIP1559 transactions
   * @param xsswapRouter smart contract address
   * @param ttl How long the swap is valid before expiry, in seconds
   * @param abi Router contract ABI
   * @param gasLimit Gas limit
   * @param nonce (Optional) EVM transaction nonce
   * @param maxFeePerGas (Optional) Maximum total fee per gas you want to pay
   * @param maxPriorityFeePerGas (Optional) Maximum tip per gas you want to pay
   */
  async executeTrade(
    wallet: Wallet,
    trade: Trade,
    gasPrice: number,
    xsswapRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber,
    allowedSlippage?: string
  ): Promise<Transaction> {
    const result = Router.swapCallParameters(trade, {
      ttl,
      recipient: wallet.address,
      allowedSlippage: this.getAllowedSlippage(allowedSlippage),
    });

    const contract = new Contract(xsswapRouter, abi, wallet);
    if (!nonce) {
      nonce = await this.xdc.nonceManager.getNextNonce(wallet.address);
    }
    let tx;
    if (maxFeePerGas || maxPriorityFeePerGas) {
      tx = await contract[result.methodName](...result.args, {
        gasLimit: gasLimit.toFixed(0),
        value: result.value,
        nonce: nonce,
        maxFeePerGas,
        maxPriorityFeePerGas,
      });
    } else {
      tx = await contract[result.methodName](...result.args, {
        gasPrice: (gasPrice * 1e9).toFixed(0),
        gasLimit: gasLimit.toFixed(0),
        value: result.value,
        nonce: nonce,
      });
    }

    logger.info(tx);
    await this.xdc.nonceManager.commitNonce(wallet.address, nonce);
    return tx;
  }
}
