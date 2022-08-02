import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
  UniswapishPriceError,
} from '../../services/error-handler';
import { BalancerConfig } from './balancer.config';
import routerAbi from './balancer_router.json';

import { ContractInterface } from '@ethersproject/contracts';
import { parseFixed } from '@ethersproject/bignumber';

import {
  Token as UniswapishToken,
  Trade as UniswapishTrade,
  Pair as UniswapishPair,
  Route as UniswapRoute,
  TradeType,
  CurrencyAmount,
} from '@sushiswap/sdk';

import POOLS from './pools.json';
import {
  BalancerSDK,
  BalancerSdkConfig,
  Network,
  Pool,
  StaticPoolProvider,
  Token,
} from '@balancer-labs/sdk';

import { ExpectedTrade, Uniswapish } from '../../services/common-interfaces';
import { Ethereum } from '../../chains/ethereum/ethereum';
import { BigNumber, Wallet, Transaction } from 'ethers';
import { logger } from '../../services/logger';

export class Balancer implements Uniswapish {
  private static _instances: { [name: string]: Balancer };
  private ethereum: Ethereum;
  private _chain: string;
  private _routerAbi: ContractInterface;
  private _gasLimitEstimate: number;
  private _ttl: number;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;
  private config: BalancerSdkConfig;
  private balancer: BalancerSDK;
  private poolProvider: StaticPoolProvider;

  private constructor(chain: string, network: string) {
    this._chain = chain;
    this.ethereum = Ethereum.getInstance(network);
    this.chainId = this.ethereum.chainId;
    this._ttl = BalancerConfig.config.ttl;
    this._routerAbi = routerAbi.abi;
    this._gasLimitEstimate = BalancerConfig.config.gasLimitEstimate;
    // ['mainnet', 'kovan', 'rinkeby']
    let balancerNetwork = Network.MAINNET;
    if (network === 'mainnet') {
      balancerNetwork = Network.MAINNET;
    } else if (network === 'kovan') {
      balancerNetwork = Network.KOVAN;
    } else if (network === 'rinkeby') {
      balancerNetwork = Network.RINKEBY;
    }
    this.config = {
      network: balancerNetwork,
      rpcUrl: this.ethereum.rpcUrl,
    };
    this.balancer = new BalancerSDK(this.config);
    this.poolProvider = new StaticPoolProvider(POOLS as Pool[]);
  }

  public static getInstance(chain: string, network: string): Balancer {
    if (Balancer._instances === undefined) {
      Balancer._instances = {};
    }
    if (!(chain + network in Balancer._instances)) {
      Balancer._instances[chain + network] = new Balancer(chain, network);
    }

    return Balancer._instances[chain + network];
  }

  /**
   * Given a token's address, return the connector's native representation of
   * the token.
   *
   * @param address Token address
   */
  public getTokenByAddress(address: string): UniswapishToken {
    const tok = this.tokenList[address];
    return new UniswapishToken(
      this.chainId,
      tok.address,
      tok.decimals ?? 0,
      tok.symbol,
      tok.symbol // balancer does not give us token names
    );
  }

  public async init() {
    if (this._chain == 'ethereum' && !this.ethereum.ready())
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    for (const token of this.ethereum.storedTokenList) {
      this.tokenList[token.address] = new UniswapishToken(
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
    return '';
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
    baseToken: UniswapishToken,
    quoteToken: UniswapishToken,
    amount: BigNumber
  ): Promise<ExpectedTrade> {
    const balancerRoute = await this.balancer.swaps.findRouteGivenIn({
      tokenIn: baseToken.address,
      tokenOut: quoteToken.address,
      amount: parseFixed(amount.toString(), 18),
      gasPrice: parseFixed('10', 18),
      maxPools: BalancerConfig.config.maximumHops,
    });
    const zero = new BigNumber(0, '10');
    if (
      !balancerRoute ||
      balancerRoute.returnAmount === zero ||
      balancerRoute.swaps.length === 0
    ) {
      throw new UniswapishPriceError(
        `findRouteGivenIn: no trade pair found for ${baseToken} to ${quoteToken}.`
      );
    }
    const executionPrice = balancerRoute.returnAmountConsideringFees.div(
      balancerRoute.swapAmount
    );
    logger.info(
      `Best trade for ${baseToken.address}-${quoteToken.address}: ` +
        `${executionPrice.toNumber().toFixed(6)}` +
        `${baseToken.name}.`
    );
    const unipairs: UniswapishPair[] = [];
    for (let x = 0; x < balancerRoute.swaps.length; x++) {
      const pool = await this.poolProvider.find(balancerRoute.swaps[x].poolId);
      if (!pool) {
        throw new UniswapishPriceError(
          `poolProvider: no pool found for ${balancerRoute.swaps[x].poolId}.`
        );
      }
      const swapInBalancer = pool.tokens[balancerRoute.swaps[x].assetInIndex];
      if (!swapInBalancer) {
        throw new UniswapishPriceError(
          `poolProvider: no token ${
            pool.tokens[balancerRoute.swaps[x].assetInIndex]
          } found in pool for ${balancerRoute.swaps[x].poolId}.`
        );
      }
      const swapIn = new UniswapishToken(
        this.chainId,
        swapInBalancer.address,
        swapInBalancer.decimals ?? 18,
        swapInBalancer.symbol,
        swapInBalancer.symbol
      );
      const swapOutBalancer = pool.tokens[balancerRoute.swaps[x].assetOutIndex];
      if (!swapOutBalancer) {
        throw new UniswapishPriceError(
          `poolProvider: no token ${
            pool.tokens[balancerRoute.swaps[x].assetOutIndex]
          } found in pool for ${balancerRoute.swaps[x].poolId}.`
        );
      }
      const swapOut = new UniswapishToken(
        this.chainId,
        swapOutBalancer.address,
        swapOutBalancer.decimals ?? 18,
        swapOutBalancer.symbol,
        swapOutBalancer.symbol
      );

      const first = CurrencyAmount.fromRawAmount(
        swapIn,
        swapInBalancer.balance
      );
      const second = CurrencyAmount.fromRawAmount(
        swapOut,
        swapOutBalancer.balance
      );
      const newpair = new UniswapishPair(first, second);
      unipairs.push(newpair);
    }
    const uniroute = new UniswapRoute(unipairs, baseToken, quoteToken);
    const expectedAmount = CurrencyAmount.fromRawAmount(
      quoteToken,
      balancerRoute.returnAmountConsideringFees.toNumber()
    );
    const unitrade = new UniswapishTrade(
      uniroute,
      CurrencyAmount.fromRawAmount(
        baseToken,
        balancerRoute.swapAmount.toString()
      ),
      0
    );
    return { trade: unitrade, expectedAmount };
  }
  async estimateBuyTrade(
    quoteToken: UniswapishToken,
    baseToken: UniswapishToken,
    amount: BigNumber
  ): Promise<ExpectedTrade> {
    const balancerRoute = await this.balancer.swaps.findRouteGivenOut({
      tokenIn: baseToken.address,
      tokenOut: quoteToken.address,
      amount: parseFixed(amount.toString(), 18),
      gasPrice: parseFixed('10', 18),
      maxPools: BalancerConfig.config.maximumHops,
    });
    const zero = new BigNumber(0, '10');
    const one = new BigNumber(1, '10');
    if (
      !balancerRoute ||
      balancerRoute.returnAmount === zero ||
      balancerRoute.swaps.length === 0
    ) {
      throw new UniswapishPriceError(
        `findRouteGivenIn: no trade pair found for ${baseToken} to ${quoteToken}.`
      );
    }

    const executionPrice = one.div(
      balancerRoute.returnAmountConsideringFees.div(balancerRoute.swapAmount)
    );
    logger.info(
      `Best trade for ${baseToken.address}-${quoteToken.address}: ` +
        `${executionPrice.toNumber().toFixed(6)}` +
        `${baseToken.name}.`
    );
    const unipairs: UniswapishPair[] = [];
    for (let x = 0; x < balancerRoute.swaps.length; x++) {
      const pool = await this.poolProvider.find(balancerRoute.swaps[x].poolId);
      if (!pool) {
        throw new UniswapishPriceError(
          `poolProvider: no pool found for ${balancerRoute.swaps[x].poolId}.`
        );
      }
      const swapInBalancer = pool.tokens[balancerRoute.swaps[x].assetInIndex];
      if (!swapInBalancer) {
        throw new UniswapishPriceError(
          `poolProvider: no token ${
            pool.tokens[balancerRoute.swaps[x].assetInIndex]
          } found in pool for ${balancerRoute.swaps[x].poolId}.`
        );
      }
      const swapIn = new UniswapishToken(
        this.chainId,
        swapInBalancer.address,
        swapInBalancer.decimals ?? 18,
        swapInBalancer.symbol,
        swapInBalancer.symbol
      );
      const swapOutBalancer = pool.tokens[balancerRoute.swaps[x].assetOutIndex];
      if (!swapOutBalancer) {
        throw new UniswapishPriceError(
          `poolProvider: no token ${
            pool.tokens[balancerRoute.swaps[x].assetOutIndex]
          } found in pool for ${balancerRoute.swaps[x].poolId}.`
        );
      }
      const swapOut = new UniswapishToken(
        this.chainId,
        swapOutBalancer.address,
        swapOutBalancer.decimals ?? 18,
        swapOutBalancer.symbol,
        swapOutBalancer.symbol
      );

      const first = CurrencyAmount.fromRawAmount(
        swapIn,
        swapInBalancer.balance
      );
      const second = CurrencyAmount.fromRawAmount(
        swapOut,
        swapOutBalancer.balance
      );
      const newpair = new UniswapishPair(first, second);
      unipairs.push(newpair);
    }
    const uniroute = new UniswapRoute(unipairs, baseToken, quoteToken);
    const expectedAmount = CurrencyAmount.fromRawAmount(
      quoteToken,
      balancerRoute.swapAmount.toNumber()
    );
    const unitrade = new UniswapishTrade(
      uniroute,
      CurrencyAmount.fromRawAmount(
        baseToken,
        balancerRoute.returnAmountConsideringFees.toString()
      ),
      1
    );
    return { trade: unitrade, expectedAmount };
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
    trade: UniswapishTrade<
      UniswapishToken,
      UniswapishToken,
      TradeType.EXACT_INPUT | TradeType.EXACT_OUTPUT
    >,
    gasPrice: number,
    balancerRouter: string, // not used
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction> {
    if (balancerRouter.length === 0 || !abi) {
      throw new UniswapishPriceError(`null values.`);
    }
    let route;
    if (trade.tradeType === TradeType.EXACT_INPUT) {
      route = await this.balancer.swaps.findRouteGivenIn({
        tokenIn: trade.route.input.address,
        tokenOut: trade.route.output.address,
        amount: parseFixed(trade.inputAmount.toString(), 18),
        gasPrice: parseFixed('10', 18),
        maxPools: BalancerConfig.config.maximumHops,
      });
    } else {
      route = await this.balancer.swaps.findRouteGivenOut({
        tokenIn: trade.route.input.address,
        tokenOut: trade.route.output.address,
        amount: parseFixed(trade.inputAmount.toString(), 18),
        gasPrice: parseFixed('10', 18),
        maxPools: 4,
      });
    }
    const deadline = new BigNumber(ttl, '10');
    // Prepares transaction attributes based on the route
    const transactionAttributes = this.balancer.swaps.buildSwap({
      userAddress: wallet.address,
      swapInfo: route,
      kind: trade.tradeType.valueOf(), // 0 - givenIn, 1 - givenOut
      deadline,
      maxSlippage: Number(BalancerConfig.config.allowedSlippage),
    });

    // Extract parameters required for sendTransaction
    const { to, data, value } = transactionAttributes;

    // Execution with ethers.js
    if (nonce === undefined) {
      nonce = await this.ethereum.nonceManager.getNonce(wallet.address);
    }
    let tx;
    if (maxFeePerGas !== undefined || maxPriorityFeePerGas !== undefined) {
      tx = await wallet.sendTransaction({
        to,
        data,
        value,
        nonce,
        maxFeePerGas,
        maxPriorityFeePerGas,
        gasLimit,
      });
    } else {
      tx = await wallet.sendTransaction({
        to,
        data,
        value,
        nonce,
        gasPrice,
        gasLimit,
      });
    }

    logger.info(tx);
    await this.ethereum.nonceManager.commitNonce(wallet.address, nonce);
    return tx;
  }
}
