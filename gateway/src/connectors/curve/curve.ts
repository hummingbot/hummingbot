import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
  // UniswapishPriceError,
} from '../../services/error-handler';
import { CurveConfig } from './curve.config';
import routerAbi from './curve_router_abi.json';

import { ContractInterface } from '@ethersproject/contracts';
import { Fraction } from '@uniswap/sdk-core';
import {
  Percent,
  Router,
  Token,
  CurrencyAmount,
  Trade,
  Pair,
  SwapParameters,
  TradeType,
} from '@sushiswap/sdk';
// import { Trade as CurveTrade } from '../curve/curve_helper';
import IUniswapV2Pair from '@uniswap/v2-core/build/IUniswapV2Pair.json';
import JSBI from 'jsbi';
export declare type BigintIsh = JSBI | string | number;
import { ExpectedTrade, Uniswapish } from '../../services/common-interfaces';
import { Ethereum } from '../../chains/ethereum/ethereum';
import {
  BigNumber,
  Wallet,
  Transaction,
  Contract,
  ContractTransaction,
  utils,
} from 'ethers';
import { percentRegexp } from '../../services/config-manager-v2';
import { logger } from '../../services/logger';

export class Curve implements Uniswapish {
  private static _instances: { [name: string]: Curve };
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
    const config = CurveConfig.config;
    this.ethereum = Ethereum.getInstance(network);
    this.chainId = this.ethereum.chainId;
    this._ttl = CurveConfig.config.ttl;
    this._routerAbi = routerAbi.abi;
    this._gasLimit = CurveConfig.config.gasLimit;
    this._router = config.curveRouterAddress(network);
  }

  public static getInstance(chain: string, network: string): Curve {
    if (Curve._instances === undefined) {
      Curve._instances = {};
    }
    if (!(chain + network in Curve._instances)) {
      Curve._instances[chain + network] = new Curve(chain, network);
    }
    logger.info(`Fetching pair data for ${chain}-${network}.`);
    return Curve._instances[chain + network];
  }

  /**
   * Given a token's address, return the connector's native representation of
   * the token.
   *
   * @param address Token address
   */
  public getTokenByAddress(address: string): Token {
    logger.info(`token address ${address}.`);

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
  public get gasLimit(): number {
    return this._gasLimit;
  }

  /**
   * Default time-to-live for swap transactions, in seconds.
   */
  public get ttl(): number {
    return this._ttl;
  }

  /**
   * Gets the allowed slippage percent from configuration.
   */
  getSlippagePercentage(): Percent {
    const allowedSlippage = CurveConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return new Percent(nd[1], nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  /**
   * Fetches information about a pair and constructs a pair from the given two tokens.
   * This is to replace the Fetcher Class
   * param tokenA first token
   * param tokenB second token
   */

  async fetchData(baseToken: Token, quoteToken: Token): Promise<Pair> {
    logger.info(`FetchDatafor.`);

    const pairAddress = Pair.getAddress(baseToken, quoteToken);
    const contract = new Contract(
      pairAddress,
      IUniswapV2Pair.abi,
      this.ethereum.provider
    );
    const [reserves0, reserves1] = await contract.getReserves();
    const balances = baseToken.sortsBefore(quoteToken)
      ? [reserves0, reserves1]
      : [reserves1, reserves0];
    const pair = new Pair(
      CurrencyAmount.fromRawAmount(baseToken, balances[0]),
      CurrencyAmount.fromRawAmount(quoteToken, balances[1])
    );
    return pair;
  }

  async estimateSellTrade(
    baseToken: Token,
    quoteToken: Token,
    amount: BigNumber
  ): Promise<ExpectedTrade> {
    logger.info(`Fetching pair data for ${'cxd'}-${'USDC'}.`);

    const CURVE_CXD_ADDRESSES = {
      1: '0x4535913573D299A6372ca43b90aA6Be1CF68f779',
      4: '0x4535913573D299A6372ca43b90aA6Be1CF68f779',
    };
    const CRV_CXD_Address = CURVE_CXD_ADDRESSES[1];
    const ifaceGetDy = new utils.Interface([
      'function get_dy(uint256 i, uint256 j, uint256 dx) view returns (uint256)',
    ]);
    console.log(amount);
    console.log(amount.toString());
    const encodeGetDy = ifaceGetDy.encodeFunctionData('get_dy', [
      1,
      0,
      amount.toString(),
    ]);
    logger.info(`Encoded Request: ${encodeGetDy}`);

    const provider = this.ethereum.provider;
    logger.info(`Provider: ${provider._network}`);

    const getDyHexString = await provider.call({
      to: CRV_CXD_Address,
      data: encodeGetDy,
    });
    console.log(getDyHexString);
    const dy = BigNumber.from(getDyHexString.toString());
    const expectedAmount = CurrencyAmount.fromRawAmount(
      baseToken,
      dy.toString()
    );

    logger.info(`dy_tostring": ${dy.toString()}`);
    logger.info(`expectedAmount: ${expectedAmount}`);

    const executionPrice = new Fraction(amount.toString(), dy.toString());
    logger.info(`executionPrice: ${executionPrice}`);

    const trades = {
      executionPrice: executionPrice,
      baseToken: baseToken,
      quoteToken: quoteToken,
    };
    logger.info(`trades: ${trades}`);

    return { trade: trades, expectedAmount: expectedAmount };
  }

  async estimateBuyTrade(
    quoteToken: Token,
    baseToken: Token,
    amount: BigNumber
  ): Promise<ExpectedTrade> {
    logger.info(`Fetching pair data for ${'cxd'}-${'USDC'}.`);

    const CURVE_CXD_ADDRESSES = {
      1: '0x4535913573D299A6372ca43b90aA6Be1CF68f779',
      4: '0x4535913573D299A6372ca43b90aA6Be1CF68f779',
    };
    const CRV_CXD_Address = CURVE_CXD_ADDRESSES[1];
    const ifaceGetDy = new utils.Interface([
      'function get_dy(uint256 i, uint256 j, uint256 dx) view returns (uint256)',
    ]);
    console.log(amount);
    console.log(amount.toString());
    const encodeGetDy = ifaceGetDy.encodeFunctionData('get_dy', [
      1,
      0,
      amount.toString(),
    ]);
    logger.info(`Encoded Request: ${encodeGetDy}`);

    const provider = this.ethereum.provider;
    logger.info(`Provider: ${provider._network}`);

    const getDyHexString = await provider.call({
      to: CRV_CXD_Address,
      data: encodeGetDy,
    });
    console.log(getDyHexString);
    const dy = BigNumber.from(getDyHexString.toString());
    const expectedAmount = CurrencyAmount.fromRawAmount(
      baseToken,
      dy.toString()
    );

    logger.info(`dy_tostring": ${dy.toString()}`);
    logger.info(`expectedAmount: ${expectedAmount}`);

    const executionPrice = new Fraction(amount.toString(), dy.toString());
    logger.info(`executionPrice: ${executionPrice}`);

    const trades = {
      executionPrice: executionPrice,
      baseToken: baseToken,
      quoteToken: quoteToken,
    };
    logger.info(`trades: ${trades}`);

    return { trade: trades, expectedAmount: expectedAmount };
  }

  /**
   * Given a wallet and a Uniswap trade, try to execute it on blockchain.
   *
   * @param _wallet Wallet
   * @param _trade Expected trade
   * @param _gasPrice Base gas price, for pre-EIP1559 transactions
   * @param uniswapRouter Router smart contract address
   * @param _ttl How long the swap is valid before expiry, in seconds
   * @param _abi Router contract ABI
   * @param _gasLimit Gas limit
   * @param _nonce (Optional) EVM transaction nonce
   * @param _maxFeePerGas (Optional) Maximum total fee per gas you want to pay
   * @param _maxPriorityFeePerGas (Optional) Maximum tip per gas you want to pay
   */

  async executeTrade(
    wallet: Wallet,
    trade: Trade<Token, Token, TradeType.EXACT_INPUT | TradeType.EXACT_OUTPUT>,
    gasPrice: number,
    curveRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction> {
    const result: SwapParameters = Router.swapCallParameters(trade, {
      ttl,
      recipient: wallet.address,
      allowedSlippage: this.getSlippagePercentage(),
    });
    const contract: Contract = new Contract(curveRouter, abi, wallet);
    if (nonce === undefined) {
      nonce = await this.ethereum.nonceManager.getNonce(wallet.address);
    }
    let tx: ContractTransaction;
    if (maxFeePerGas !== undefined || maxPriorityFeePerGas !== undefined) {
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
    await this.ethereum.nonceManager.commitNonce(wallet.address, nonce);
    return tx;
  }
}
