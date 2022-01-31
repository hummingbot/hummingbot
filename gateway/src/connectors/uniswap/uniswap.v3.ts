import {
  InitializationError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { logger } from '../../services/logger';
import { UniswapConfig } from './uniswap.config';
import { Contract, ContractInterface } from '@ethersproject/contracts';
import {
  Token,
  CurrencyAmount,
  Percent,
  Price,
  TradeType,
} from '@uniswap/sdk-core';
import * as uniV3 from '@uniswap/v3-sdk';
import {
  BigNumber,
  Transaction,
  providers,
  Wallet,
  Signer,
  utils,
} from 'ethers';
import { ExpectedTrade, Uniswapish } from '../../services/uniswapish.interface';
import { percentRegexp } from '../../services/config-manager-v2';
import { Ethereum } from '../../chains/ethereum/ethereum';
import * as math from 'mathjs';

const MaxUint128 = BigNumber.from(2).pow(128).sub(1);

export class UniswapV3 implements Uniswapish {
  private static _instances: { [name: string]: UniswapV3 };
  private ethereum: Ethereum;
  private _chain: string;
  private _router: string;
  private _nftManager: string;
  private _routerAbi: ContractInterface;
  private _nftAbi: ContractInterface;
  private _poolAbi: ContractInterface;
  private _gasLimit: number;
  private _ttl: number;
  private chainId;
  private tokenList: Record<string, Token> = {};
  private _ready: boolean = false;

  private constructor(chain: string, network: string) {
    this._chain = chain;
    this.ethereum = Ethereum.getInstance(network);
    this.chainId = this.ethereum.chainId;
    this._ttl = UniswapConfig.config.ttl;
    this._routerAbi =
      require('@uniswap/v3-periphery/artifacts/contracts/SwapRouter.sol/SwapRouter.json').abi;
    this._nftAbi =
      require('@uniswap/v3-periphery/artifacts/contracts/NonfungiblePositionManager.sol/NonfungiblePositionManager.json').abi;
    this._poolAbi =
      require('@uniswap/v3-core/artifacts/contracts/UniswapV3Pool.sol/UniswapV3Pool.json').abi;
    this._gasLimit = UniswapConfig.config.gasLimit;
    this._router = UniswapConfig.config.uniswapV3RouterAddress;
    this._nftManager = UniswapConfig.config.uniswapV3NftManagerAddress;
  }

  public static getInstance(chain: string, network: string): UniswapV3 {
    if (UniswapV3._instances === undefined) {
      UniswapV3._instances = {};
    }
    if (!(chain + network in UniswapV3._instances)) {
      UniswapV3._instances[chain + network] = new UniswapV3(chain, network);
    }

    return UniswapV3._instances[chain + network];
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

  public get nftManager(): string {
    return this._nftManager;
  }

  public get ttl(): number {
    return this._ttl;
  }

  public get routerAbi(): ContractInterface {
    return this._routerAbi;
  }

  public get nftAbi(): ContractInterface {
    return this._nftAbi;
  }

  public get poolAbi(): ContractInterface {
    return this._poolAbi;
  }

  public get gasLimit(): number {
    return this._gasLimit;
  }

  getPercentage(rawPercent: number | string): Percent {
    const slippage = math.fraction(rawPercent) as math.Fraction;
    return new Percent(slippage.n, slippage.d * 100);
  }

  getSlippagePercentage(): Percent {
    const allowedSlippage = UniswapConfig.config.allowedSlippage;
    const nd = allowedSlippage.match(percentRegexp);
    if (nd) return new Percent(nd[1], nd[2]);
    throw new Error(
      'Encountered a malformed percent string in the config for ALLOWED_SLIPPAGE.'
    );
  }

  getContract(contract: string, wallet: Wallet | Signer): Contract {
    if (contract === 'router') {
      return new Contract(this.router, this.routerAbi, wallet);
    } else {
      return new Contract(this.nftManager, this.nftAbi, wallet);
    }
  }

  async getPoolState(
    poolAddress: string,
    fee: uniV3.FeeAmount,
    wallet: providers.StaticJsonRpcProvider | Signer
  ): Promise<any> {
    const poolContract = new Contract(poolAddress, this.poolAbi, wallet);
    const minTick = uniV3.nearestUsableTick(
      uniV3.TickMath.MIN_TICK,
      uniV3.TICK_SPACINGS[fee]
    );
    const maxTick = uniV3.nearestUsableTick(
      uniV3.TickMath.MAX_TICK,
      uniV3.TICK_SPACINGS[fee]
    );
    const poolDataReq = await Promise.allSettled([
      poolContract.liquidity(),
      poolContract.slot0(),
      poolContract.ticks(minTick),
      poolContract.ticks(maxTick),
    ]);

    const rejected = poolDataReq.filter(
      (r) => r.status === 'rejected'
    ) as PromiseRejectedResult[];

    if (rejected.length > 0) throw 'Unable to fetch pool state';

    const poolData = (
      poolDataReq.filter(
        (r) => r.status === 'fulfilled'
      ) as PromiseFulfilledResult<any>[]
    ).map((r) => r.value);

    return {
      liquidity: poolData[0],
      sqrtPriceX96: poolData[1][0],
      tick: poolData[1][1],
      observationIndex: poolData[1][2],
      observationCardinality: poolData[1][3],
      observationCardinalityNext: poolData[1][4],
      feeProtocol: poolData[1][5],
      unlocked: poolData[1][6],
      fee: fee,
      tickProvider: [
        {
          index: minTick,
          liquidityNet: poolData[2][1],
          liquidityGross: poolData[2][0],
        },
        {
          index: maxTick,
          liquidityNet: poolData[3][1],
          liquidityGross: poolData[3][0],
        },
      ],
    };
  }

  async getPairs(firstToken: Token, secondToken: Token): Promise<uniV3.Pool[]> {
    const poolDataRequests = [];
    const pools: uniV3.Pool[] = [];
    try {
      for (const tier of Object.values(uniV3.FeeAmount)) {
        if (typeof tier !== 'string') {
          const poolAddress = uniV3.Pool.getAddress(
            firstToken,
            secondToken,
            tier
          );
          poolDataRequests.push(
            this.getPoolState(poolAddress, tier, this.ethereum.provider)
          );
        }
      }
      const poolDataRaw = await Promise.allSettled(poolDataRequests);
      const poolDataRes = (
        poolDataRaw.filter(
          (r) => r.status === 'fulfilled'
        ) as PromiseFulfilledResult<any>[]
      ).map((r) => r.value);

      for (const poolData of poolDataRes) {
        pools.push(
          new uniV3.Pool(
            firstToken,
            secondToken,
            poolData.fee,
            poolData.sqrtPriceX96.toString(),
            poolData.liquidity.toString(),
            poolData.tick,
            poolData.tickProvider
          )
        );
      }
    } catch (err) {
      logger.error(err);
    }
    return pools;
  }

  // get the expected amount of token out, for a given pair and a token amount in.
  // this only considers direct routes.

  async priceSwapIn(
    tokenIn: Token,
    tokenOut: Token,
    tokenInAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
    const tokenAmountIn = CurrencyAmount.fromRawAmount(
      tokenIn,
      tokenInAmount.toString()
    );
    const pools = await this.getPairs(tokenIn, tokenOut);
    const trades = await uniV3.Trade.bestTradeExactIn(
      pools,
      tokenAmountIn,
      tokenOut,
      { maxHops: 1 }
    );
    if (!trades || trades.length === 0)
      return `priceSwapOut: no trade pair found for ${tokenIn.address} to ${tokenOut.address}.`;
    const trade = trades[0];
    const expectedAmount = trade.minimumAmountOut(this.getSlippagePercentage());
    return { trade, expectedAmount };
  }

  async priceSwapOut(
    tokenIn: Token,
    tokenOut: Token,
    tokenOutAmount: BigNumber
  ): Promise<ExpectedTrade | string> {
    const tokenAmountOut = CurrencyAmount.fromRawAmount(
      tokenOut,
      tokenOutAmount.toString()
    );
    const pools = await this.getPairs(tokenIn, tokenOut);
    const trades = await uniV3.Trade.bestTradeExactOut(
      pools,
      tokenIn,
      tokenAmountOut,
      { maxHops: 1 }
    );
    if (!trades || trades.length === 0)
      return `priceSwapOut: no trade pair found for ${tokenIn.address} to ${tokenOut.address}.`;
    const trade = trades[0];
    const expectedAmount = trade.maximumAmountIn(this.getSlippagePercentage());
    return { trade, expectedAmount };
  }

  async executeTrade(
    wallet: Wallet,
    trade: uniV3.Trade<Token, Token, TradeType>,
    gasPrice: number,
    uniswapRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction> {
    const { calldata, value } = uniV3.SwapRouter.swapCallParameters(trade, {
      deadline: ttl,
      recipient: wallet.address,
      slippageTolerance: this.getSlippagePercentage(),
    });
    const contract = new Contract(uniswapRouter, abi, wallet);

    let tx;
    if (maxFeePerGas || maxPriorityFeePerGas) {
      tx = await contract.multicall([calldata], {
        gasLimit: gasLimit,
        value: value,
        nonce: nonce,
        maxFeePerGas,
        maxPriorityFeePerGas,
      });
    } else {
      tx = await contract.multicall([calldata], {
        gasPrice: gasPrice * 1e9,
        gasLimit: gasLimit,
        value: value,
        nonce: nonce,
      });
    }
    logger.info(`Uniswap V3 swap Tx Hash: ${tx.hash}`);
    return tx;
  }

  async getPosition(
    wallet: Wallet,
    tokenId: number,
    isRaw: boolean = false
  ): Promise<any> {
    const contract = this.getContract('nft', wallet);
    const requests = [contract.positions(tokenId)];
    if (!isRaw) requests.push(this.collectFees(wallet, tokenId, true));
    const positionInfoReq = await Promise.allSettled(requests);
    const rejected = positionInfoReq.filter(
      (r) => r.status === 'rejected'
    ) as PromiseRejectedResult[];
    if (rejected.length > 0) throw 'Unable to fetch position';
    const positionInfo = (
      positionInfoReq.filter(
        (r) => r.status === 'fulfilled'
      ) as PromiseFulfilledResult<any>[]
    ).map((r) => r.value);
    const position = positionInfo[0];
    if (isRaw) {
      return position;
    } else {
      const feeInfo = positionInfo[1];
      const token0 = this.getTokenByAddress(position.token0);
      const token1 = this.getTokenByAddress(position.token1);
      if (!token0 || !token1)
        throw 'Cannot identify one of the tokens in this pair.';
      const fee = position.fee;
      const poolAddress = uniV3.Pool.getAddress(token0, token1, fee);
      const poolData = await this.getPoolState(poolAddress, fee, wallet);
      const positionInst = new uniV3.Position({
        pool: new uniV3.Pool(
          token0,
          token1,
          poolData.fee,
          poolData.sqrtPriceX96.toString(),
          poolData.liquidity.toString(),
          poolData.tick
        ),
        tickLower: position.tickLower,
        tickUpper: position.tickUpper,
        liquidity: position.liquidity,
      });
      return {
        token0: token0.symbol,
        token1: token1.symbol,
        fee: Object.keys(uniV3.FeeAmount).find(
          (key) => uniV3.FeeAmount[Number(key)] === position.fee
        ),
        lowerPrice: positionInst.token0PriceLower.toFixed(8),
        upperPrice: positionInst.token0PriceUpper.toFixed(8),
        amount0: positionInst.amount0.toFixed(8),
        amount1: positionInst.amount1.toFixed(8),
        unclaimedToken0: utils.formatUnits(
          feeInfo.amount0.toString(),
          token0.decimals
        ),
        unclaimedToken1: utils.formatUnits(
          feeInfo.amount1.toString(),
          token1.decimals
        ),
      };
    }
  }

  getReduceLiquidityData(
    percent: number,
    tokenId: number,
    token0: Token,
    token1: Token,
    wallet: Wallet
  ) {
    return {
      tokenId: tokenId,
      liquidityPercentage: this.getPercentage(percent),
      slippageTolerance: this.getSlippagePercentage(),
      deadline: this.ttl,
      burnToken: false, // percent == 100 ? true : false,
      collectOptions: {
        expectedCurrencyOwed0: CurrencyAmount.fromRawAmount(token0, '0'),
        expectedCurrencyOwed1: CurrencyAmount.fromRawAmount(token1, '0'),
        recipient: wallet.address,
      },
    };
  }

  getAddLiquidityData(wallet: Wallet, tokenId: number) {
    let extraData;
    const commonData = {
      slippageTolerance: this.getSlippagePercentage(),
      deadline: this.ttl,
    };
    if (tokenId == 0) {
      extraData = { recipient: wallet.address, createPool: true };
    } else {
      extraData = { tokenId: tokenId };
    }
    return { ...commonData, ...extraData };
  }

  async addPosition(
    wallet: Wallet,
    tokenIn: Token,
    tokenOut: Token,
    amount0: string,
    amount1: string,
    fee: uniV3.FeeAmount,
    lowerPrice: number,
    upperPrice: number,
    tokenId: number = 0
  ) {
    const nftContract = this.getContract('nft', wallet);
    const lowerPriceInFraction = math.fraction(lowerPrice) as math.Fraction;
    const upperPriceInFraction = math.fraction(upperPrice) as math.Fraction;
    const poolAddress = uniV3.Pool.getAddress(tokenIn, tokenOut, fee);
    const poolData = await this.getPoolState(poolAddress, fee, wallet);
    const position = uniV3.Position.fromAmounts({
      pool: new uniV3.Pool(
        tokenIn,
        tokenOut,
        poolData.fee,
        poolData.sqrtPriceX96.toString(),
        poolData.liquidity.toString(),
        poolData.tick
      ),
      tickLower: uniV3.nearestUsableTick(
        uniV3.priceToClosestTick(
          new Price(
            tokenIn,
            tokenOut,
            lowerPriceInFraction.d,
            lowerPriceInFraction.n
          )
        ),
        uniV3.TICK_SPACINGS[fee]
      ),
      tickUpper: uniV3.nearestUsableTick(
        uniV3.priceToClosestTick(
          new Price(
            tokenIn,
            tokenOut,
            upperPriceInFraction.d,
            upperPriceInFraction.n
          )
        ),
        uniV3.TICK_SPACINGS[fee]
      ),
      amount0: utils.parseUnits(amount0, tokenIn.decimals).toString(),
      amount1: utils.parseUnits(amount1, tokenOut.decimals).toString(),
      useFullPrecision: true,
    });
    const callData = uniV3.NonfungiblePositionManager.addCallParameters(
      position,
      this.getAddLiquidityData(wallet, tokenId)
    );
    return await nftContract.multicall([callData.calldata], {
      value: callData.value,
      gasLimit: this.gasLimit,
    });
  }

  async reducePosition(
    wallet: Wallet,
    tokenId: number,
    decreasePercent: number = 100,
    getFee: boolean = false
  ) {
    // Reduce position and burn
    const contract = this.getContract('nft', wallet);
    const positionData = await this.getPosition(wallet, tokenId, true);
    const tokenIn = this.getTokenByAddress(positionData.token0);
    const tokenOut = this.getTokenByAddress(positionData.token1);
    const fee = positionData.fee;
    const poolAddress = uniV3.Pool.getAddress(tokenIn, tokenOut, fee);
    const poolData = await this.getPoolState(poolAddress, fee, wallet);
    const position = new uniV3.Position({
      pool: new uniV3.Pool(
        tokenIn,
        tokenOut,
        poolData.fee,
        poolData.sqrtPriceX96.toString(),
        poolData.liquidity.toString(),
        poolData.tick
      ),
      tickLower: positionData.tickLower,
      tickUpper: positionData.tickUpper,
      liquidity: positionData.liquidity,
    });
    const callData = uniV3.NonfungiblePositionManager.removeCallParameters(
      position,
      this.getReduceLiquidityData(
        decreasePercent,
        tokenId,
        tokenIn,
        tokenOut,
        wallet
      )
    );
    if (getFee) {
      return await contract.estimateGas.multicall([callData.calldata], {
        value: callData.value,
        gasLimit: this.gasLimit,
      });
    } else {
      return await contract.multicall([callData.calldata], {
        value: callData.value,
        gasLimit: this.gasLimit,
      });
    }
  }

  async collectFees(
    wallet: Wallet,
    tokenId: number,
    isStatic: boolean = false
  ) {
    const contract = this.getContract('nft', wallet);
    const collectData = {
      tokenId: tokenId,
      recipient: wallet.address,
      amount0Max: MaxUint128,
      amount1Max: MaxUint128,
    };
    return isStatic
      ? await contract.callStatic.collect(collectData, {
          gasLimit: this.gasLimit,
        })
      : await contract.collect(collectData, { gasLimit: this.gasLimit });
  }
}
