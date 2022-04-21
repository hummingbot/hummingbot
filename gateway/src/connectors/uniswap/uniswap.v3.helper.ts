import { logger } from '../../services/logger';
import { UniswapConfig } from './uniswap.config';
import { Contract, ContractInterface } from '@ethersproject/contracts';
import { Token, CurrencyAmount, Percent, Price } from '@uniswap/sdk-core';
import * as uniV3 from '@uniswap/v3-sdk';
import { providers, Wallet, Signer, utils } from 'ethers';
import { percentRegexp } from '../../services/config-manager-v2';
import { Ethereum } from '../../chains/ethereum/ethereum';
import {
  PoolState,
  RawPosition,
  AddLiquidityData,
  IncreaseLiquidityData,
  ReduceLiquidityData,
} from './uniswap.v3.interfaces';
import * as math from 'mathjs';

export class UniswapV3Helper {
  protected ethereum: Ethereum;
  private _router: string;
  private _nftManager: string;
  private _ttl: number;
  private _routerAbi: ContractInterface;
  private _nftAbi: ContractInterface;
  private _poolAbi: ContractInterface;

  constructor(network: string) {
    this.ethereum = Ethereum.getInstance(network);
    this._router = UniswapConfig.config.uniswapV3RouterAddress(network);
    this._nftManager = UniswapConfig.config.uniswapV3NftManagerAddress(network);
    this._ttl = UniswapConfig.config.ttl(3);
    this._routerAbi =
      require('@uniswap/v3-periphery/artifacts/contracts/SwapRouter.sol/SwapRouter.json').abi;
    this._nftAbi =
      require('@uniswap/v3-periphery/artifacts/contracts/NonfungiblePositionManager.sol/NonfungiblePositionManager.json').abi;
    this._poolAbi =
      require('@uniswap/v3-core/artifacts/contracts/UniswapV3Pool.sol/UniswapV3Pool.json').abi;
  }

  public get router(): string {
    return this._router;
  }

  public get nftManager(): string {
    return this._nftManager;
  }

  public get ttl(): number {
    return parseInt(String(Date.now() / 1000)) + this._ttl;
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

  public getTokenByAddress(address: string): Token {
    const tokenFilter = this.ethereum.storedTokenList.filter(
      (t) => t.address === address
    );
    if (tokenFilter.length === 0) {
      throw `Cannot find token info for token address ${address}.`;
    }
    return new Token(
      this.ethereum.chainId,
      tokenFilter[0].address,
      tokenFilter[0].decimals,
      tokenFilter[0].symbol,
      tokenFilter[0].name
    );
  }

  getPercentage(rawPercent: number | string): Percent {
    const slippage = math.fraction(rawPercent) as math.Fraction;
    return new Percent(slippage.n, slippage.d * 100);
  }

  getSlippagePercentage(): Percent {
    const allowedSlippage = UniswapConfig.config.allowedSlippage(3);
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

  getPoolContract(
    pool: string,
    wallet: providers.StaticJsonRpcProvider | Signer
  ): Contract {
    return new Contract(pool, this.routerAbi, wallet);
  }

  async getPoolState(
    poolAddress: string,
    fee: uniV3.FeeAmount,
    wallet: providers.StaticJsonRpcProvider | Signer
  ): Promise<PoolState> {
    const poolContract = this.getPoolContract(poolAddress, wallet);
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

  async getRawPosition(wallet: Wallet, tokenId: number): Promise<RawPosition> {
    const contract = this.getContract('nft', wallet);
    const requests = [contract.positions(tokenId)];
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
    return positionInfo[0];
  }

  getReduceLiquidityData(
    percent: number,
    tokenId: number,
    token0: Token,
    token1: Token,
    wallet: Wallet
  ): ReduceLiquidityData {
    return {
      tokenId: tokenId,
      liquidityPercentage: this.getPercentage(percent),
      slippageTolerance: this.getSlippagePercentage(),
      deadline: this.ttl,
      burnToken: false,
      collectOptions: {
        expectedCurrencyOwed0: CurrencyAmount.fromRawAmount(token0, '0'),
        expectedCurrencyOwed1: CurrencyAmount.fromRawAmount(token1, '0'),
        recipient: wallet.address,
      },
    };
  }

  getAddLiquidityData(
    wallet: Wallet,
    tokenId: number
  ): AddLiquidityData | IncreaseLiquidityData {
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

  async addPositionHelper(
    wallet: Wallet,
    tokenIn: Token,
    tokenOut: Token,
    amount0: string,
    amount1: string,
    fee: uniV3.FeeAmount,
    lowerPrice: number,
    upperPrice: number,
    tokenId: number = 0
  ): Promise<uniV3.MethodParameters> {
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
    return uniV3.NonfungiblePositionManager.addCallParameters(
      position,
      this.getAddLiquidityData(wallet, tokenId)
    );
  }

  async reducePositionHelper(
    wallet: Wallet,
    tokenId: number,
    decreasePercent: number
  ): Promise<uniV3.MethodParameters> {
    // Reduce position and burn
    const positionData = await this.getRawPosition(wallet, tokenId);
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
    return uniV3.NonfungiblePositionManager.removeCallParameters(
      position,
      this.getReduceLiquidityData(
        decreasePercent,
        tokenId,
        tokenIn,
        tokenOut,
        wallet
      )
    );
  }
}
