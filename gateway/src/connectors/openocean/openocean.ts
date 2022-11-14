import { percentRegexp } from '../../services/config-manager-v2';
import { BigNumber, ContractInterface, Transaction, Wallet } from 'ethers';
import { OpenoceanConfig } from './openocean.config';
import {
  Token,
  TokenAmount,
  Trade,
  Pair,
  TradeType,
  Route,
  Price,
} from '@uniswap/sdk';
import Decimal from 'decimal.js-light';
import axios from 'axios';
import { logger } from '../../services/logger';
import { Avalanche } from '../../chains/avalanche/avalanche';
import { ExpectedTrade, Uniswapish } from '../../services/common-interfaces';
import {
  HttpException,
  TRADE_FAILED_ERROR_CODE,
  TRADE_FAILED_ERROR_MESSAGE,
  UniswapishPriceError,
  UNKNOWN_ERROR_ERROR_CODE,
  UNKNOWN_ERROR_MESSAGE,
} from '../../services/error-handler';

export function newFakeTrade(
  tokenIn: Token,
  tokenOut: Token,
  tokenInAmount: BigNumber,
  tokenOutAmount: BigNumber
): Trade {
  const baseAmount = new TokenAmount(tokenIn, tokenInAmount.toString());
  const quoteAmount = new TokenAmount(tokenOut, tokenOutAmount.toString());
  // Pair needs the reserves but this is not possible to pull in sushiswap contract
  const pair = new Pair(baseAmount, quoteAmount);
  const route = new Route([pair], tokenIn, tokenOut);
  const trade = new Trade(route, baseAmount, TradeType.EXACT_INPUT);
  // hack to set readonly component given we can't easily get pool token amounts
  (trade.executionPrice as Price) = new Price(
    tokenIn,
    tokenOut,
    tokenInAmount.toBigInt(),
    tokenOutAmount.toBigInt()
  );
  return trade;
}

export class Openocean implements Uniswapish {
  private static _instances: { [name: string]: Openocean };
  private avalanche: Avalanche;
  private _chain: string;
  private _router: string;
  private _gasLimitEstimate: number;
  private _ttl: number;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor(chain: string, network: string) {
    this._chain = chain;
    const config = OpenoceanConfig.config;
    this.avalanche = Avalanche.getInstance(network);
    this.chainId = this.avalanche.chainId;
    this._router = config.routerAddress(network);
    this._ttl = config.ttl;
    this._gasLimitEstimate = config.gasLimitEstimate;
  }

  public static getInstance(chain: string, network: string): Openocean {
    if (Openocean._instances === undefined) {
      Openocean._instances = {};
    }
    if (!(chain + network in Openocean._instances)) {
      Openocean._instances[chain + network] = new Openocean(chain, network);
    }

    return Openocean._instances[chain + network];
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
    if (!this.avalanche.ready()) {
      await this.avalanche.init();
    }
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
    return '';
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

  public get chainName(): string {
    return this._chain === 'avalanche' ? 'avax' : this._chain;
  }

  getSlippageNumberage(): number {
    const allowedSlippage = OpenoceanConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return Number(nd[1]);
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
    amount: BigNumber
  ): Promise<ExpectedTrade> {
    logger.info(
      `estimateSellTrade getting amounts out ${baseToken.address}-${quoteToken.address}.`
    );

    const reqAmount = new Decimal(amount.toString())
      .div(new Decimal((10 ** baseToken.decimals).toString()))
      .toNumber();
    logger.info(`reqAmount:${reqAmount}`);
    const gasPrice = this.avalanche.gasPrice;
    let quoteRes;
    try {
      quoteRes = await axios.get(
        `https://open-api.openocean.finance/v3/${this.chainName}/quote`,
        {
          params: {
            inTokenAddress: baseToken.address,
            outTokenAddress: quoteToken.address,
            amount: reqAmount,
            gasPrice: gasPrice,
          },
        }
      );
    } catch (e) {
      if (e instanceof Error) {
        logger.error(`Could not get trade info. ${e.message}`);
        throw new HttpException(
          500,
          TRADE_FAILED_ERROR_MESSAGE + e.message,
          TRADE_FAILED_ERROR_CODE
        );
      } else {
        logger.error('Unknown error trying to get trade info.');
        throw new HttpException(
          500,
          UNKNOWN_ERROR_MESSAGE,
          UNKNOWN_ERROR_ERROR_CODE
        );
      }
    }

    if (quoteRes.status == 200) {
      if (
        quoteRes.data.code == 200 &&
        Number(quoteRes.data.data.outAmount) > 0
      ) {
        const quoteData = quoteRes.data.data;
        const amounts = [quoteData.inAmount, quoteData.outAmount];
        const maximumOutput = new TokenAmount(
          quoteToken,
          amounts[1].toString()
        );
        const trade = newFakeTrade(
          baseToken,
          quoteToken,
          BigNumber.from(amounts[0]),
          BigNumber.from(amounts[1])
        );
        return { trade: trade, expectedAmount: maximumOutput };
      } else {
        throw new UniswapishPriceError(
          `priceSwapIn: no trade pair found for ${baseToken.address} to ${quoteToken.address}.`
        );
      }
    }
    throw new HttpException(
      quoteRes.status,
      `Could not get trade info. ${quoteRes.statusText}`,
      TRADE_FAILED_ERROR_CODE
    );
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
    amount: BigNumber
  ): Promise<ExpectedTrade> {
    logger.info(
      `estimateBuyTrade getting amounts in ${quoteToken.address}-${baseToken.address}.`
    );

    const reqAmount = new Decimal(amount.toString())
      .div(new Decimal((10 ** baseToken.decimals).toString()))
      .toNumber();
    logger.info(`reqAmount:${reqAmount}`);
    const gasPrice = this.avalanche.gasPrice;
    let quoteRes;
    try {
      quoteRes = await axios.get(
        `https://open-api.openocean.finance/v3/${this.chainName}/reverseQuote`,
        {
          params: {
            inTokenAddress: baseToken.address,
            outTokenAddress: quoteToken.address,
            amount: reqAmount,
            gasPrice: gasPrice,
          },
        }
      );
    } catch (e) {
      if (e instanceof Error) {
        logger.error(`Could not get trade info. ${e.message}`);
        throw new HttpException(
          500,
          TRADE_FAILED_ERROR_MESSAGE + e.message,
          TRADE_FAILED_ERROR_CODE
        );
      } else {
        logger.error('Unknown error trying to get trade info.');
        throw new HttpException(
          500,
          UNKNOWN_ERROR_MESSAGE,
          UNKNOWN_ERROR_ERROR_CODE
        );
      }
    }
    if (quoteRes.status == 200) {
      if (
        quoteRes.data.code == 200 &&
        Number(quoteRes.data.data.reverseAmount) > 0
      ) {
        const quoteData = quoteRes.data.data;
        const amounts = [quoteData.reverseAmount, quoteData.inAmount];
        const minimumInput = new TokenAmount(quoteToken, amounts[0].toString());
        const trade = newFakeTrade(
          quoteToken,
          baseToken,
          BigNumber.from(amounts[0]),
          BigNumber.from(amounts[1])
        );
        return { trade: trade, expectedAmount: minimumInput };
      } else {
        throw new UniswapishPriceError(
          `priceSwapIn: no trade pair found for ${baseToken} to ${quoteToken}.`
        );
      }
    }
    throw new HttpException(
      quoteRes.status,
      `Could not get trade info. ${quoteRes.statusText}`,
      TRADE_FAILED_ERROR_CODE
    );
  }

  /**
   * Given a wallet and a Uniswap-ish trade, try to execute it on blockchain.
   *
   * @param wallet Wallet
   * @param trade Expected trade
   * @param gasPrice Base gas price, for pre-EIP1559 transactions
   * @param openoceanRouter smart contract address
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
    openoceanRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction> {
    logger.info(
      `executeTrade ${openoceanRouter}-${ttl}-${abi}-${gasPrice}-${gasLimit}-${nonce}-${maxFeePerGas}-${maxPriorityFeePerGas}.`
    );
    const inToken: any = trade.route.input;
    const outToken: any = trade.route.output;
    let swapRes;
    try {
      swapRes = await axios.get(
        `https://open-api.openocean.finance/v3/${this.chainName}/swap_quote`,
        {
          params: {
            inTokenAddress: inToken.address,
            outTokenAddress: outToken.address,
            amount: trade.inputAmount.toExact(),
            slippage: this.getSlippageNumberage(),
            account: wallet.address,
            gasPrice: gasPrice.toString(),
          },
        }
      );
    } catch (e) {
      if (e instanceof Error) {
        logger.error(`Could not get trade info. ${e.message}`);
        throw new HttpException(
          500,
          TRADE_FAILED_ERROR_MESSAGE + e.message,
          TRADE_FAILED_ERROR_CODE
        );
      } else {
        logger.error('Unknown error trying to get trade info.');
        throw new HttpException(
          500,
          UNKNOWN_ERROR_MESSAGE,
          UNKNOWN_ERROR_ERROR_CODE
        );
      }
    }
    if (swapRes.status == 200 && swapRes.data.code == 200) {
      const swapData = swapRes.data.data;
      return this.avalanche.nonceManager.provideNonce(
        nonce,
        wallet.address,
        async (nextNonce) => {
          const gas = Math.ceil(Number(swapData.estimatedGas) * 1.15);
          const trans = {
            nonce: nextNonce,
            from: swapData.from,
            to: swapData.to,
            gasLimit: BigNumber.from(gas.toString()),
            data: swapData.data,
            value: BigNumber.from(swapData.value),
            chainId: this.chainId,
          };
          const tx = await wallet.sendTransaction(trans);
          logger.info(JSON.stringify(tx));

          return tx;
        }
      );
    }
    throw new HttpException(
      swapRes.status,
      `Could not get trade info. ${swapRes.statusText}`,
      TRADE_FAILED_ERROR_CODE
    );
  }
}
