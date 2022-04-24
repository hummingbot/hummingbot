import {
  InitializationError,
  UniswapishPriceError,
  SERVICE_UNITIALIZED_ERROR_CODE,
  SERVICE_UNITIALIZED_ERROR_MESSAGE,
} from '../../services/error-handler';
import { logger } from '../../services/logger';
import { UniswapConfig } from './uniswap.config';
import { Contract, ContractInterface } from '@ethersproject/contracts';
import { Token, CurrencyAmount, TradeType } from '@uniswap/sdk-core';
import * as uniV3 from '@uniswap/v3-sdk';
import { BigNumber, Transaction, Wallet, utils } from 'ethers';
import { ExpectedTrade, Uniswapish } from '../../services/common-interfaces';
import { UniswapV3Helper } from './uniswap.v3.helper';

const MaxUint128 = BigNumber.from(2).pow(128).sub(1);

export type Overrides = {
  gasLimit: string;
  gasPrice?: string;
  value?: string;
  nonce?: number;
  maxFeePerGas?: BigNumber;
  maxPriorityFeePerGas?: BigNumber;
};

type SellTrade = uniV3.Trade<Token, Token, TradeType.EXACT_INPUT>;
type BuyTrade = uniV3.Trade<Token, Token, TradeType.EXACT_OUTPUT>;

export class UniswapV3 extends UniswapV3Helper implements Uniswapish {
  private static _instances: { [name: string]: UniswapV3 };
  private _chain: string;
  private _gasLimit: number;
  private _ready: boolean = false;

  private constructor(chain: string, network: string) {
    super(network);
    this._chain = chain;
    this._gasLimit = UniswapConfig.config.gasLimit(3);
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

  public async init() {
    if (this._chain == 'ethereum' && !this.ethereum.ready())
      throw new InitializationError(
        SERVICE_UNITIALIZED_ERROR_MESSAGE('ETH'),
        SERVICE_UNITIALIZED_ERROR_CODE
      );
    this._ready = true;
  }

  public ready(): boolean {
    return this._ready;
  }

  /**
   * Default gas limit for swap transactions.
   */
  public get gasLimit(): number {
    return this._gasLimit;
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
    const tokenAmountIn: CurrencyAmount<Token> = CurrencyAmount.fromRawAmount(
      baseToken,
      amount.toString()
    );
    const pools: uniV3.Pool[] = await this.getPairs(baseToken, quoteToken);
    const trades: SellTrade[] = await uniV3.Trade.bestTradeExactIn(
      pools,
      tokenAmountIn,
      quoteToken,
      { maxHops: 1 }
    );
    if (!trades || trades.length === 0) {
      throw new UniswapishPriceError(
        `priceSwapOut: no trade pair found for ${baseToken.address} to ${quoteToken.address}.`
      );
    }
    const trade: SellTrade = trades[0];
    const expectedAmount: CurrencyAmount<Token> = trade.minimumAmountOut(
      this.getSlippagePercentage()
    );
    return { trade, expectedAmount };
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
    const tokenAmountOut: CurrencyAmount<Token> = CurrencyAmount.fromRawAmount(
      baseToken,
      amount.toString()
    );
    const pools: uniV3.Pool[] = await this.getPairs(quoteToken, baseToken);
    const trades: BuyTrade[] = await uniV3.Trade.bestTradeExactOut(
      pools,
      quoteToken,
      tokenAmountOut,
      { maxHops: 1 }
    );
    if (!trades || trades.length === 0) {
      throw new UniswapishPriceError(
        `priceSwapOut: no trade pair found for ${quoteToken.address} to ${baseToken.address}.`
      );
    }
    const trade: BuyTrade = trades[0];
    const expectedAmount: CurrencyAmount<Token> = trade.maximumAmountIn(
      this.getSlippagePercentage()
    );
    return { trade, expectedAmount };
  }

  /**
   * Given a wallet and a Uniswap-ish trade, try to execute it on blockchain.
   *
   * @param wallet Wallet
   * @param trade Expected trade
   * @param gasPrice Base gas price, for pre-EIP1559 transactions
   * @param uniswapRouter Router smart contract address
   * @param ttl How long the swap is valid before expiry, in seconds
   * @param abi Router contract ABI
   * @param gasLimit Gas limit
   * @param nonce (Optional) EVM transaction nonce
   * @param maxFeePerGas (Optional) Maximum total fee per gas you want to pay
   * @param maxPriorityFeePerGas (Optional) Maximum tip per gas you want to pay
   */
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
    const contract: Contract = new Contract(uniswapRouter, abi, wallet);

    const tx: Transaction = await contract.multicall(
      [calldata],
      this.generateOverrides(
        gasLimit,
        gasPrice,
        nonce,
        maxFeePerGas,
        maxPriorityFeePerGas,
        value
      )
    );
    logger.info(`Uniswap V3 swap Tx Hash: ${tx.hash}`);
    return tx;
  }

  async getPosition(
    wallet: Wallet,
    tokenId: number
  ): Promise<{
    token0: string | undefined;
    token1: string | undefined;
    fee: string | undefined;
    lowerPrice: string;
    upperPrice: string;
    amount0: string;
    amount1: string;
    unclaimedToken0: string;
    unclaimedToken1: string;
  }> {
    const contract = this.getContract('nft', wallet);
    const requests = [
      contract.positions(tokenId),
      this.collectFees(wallet, tokenId, true),
    ];
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
    const feeInfo = positionInfo[1];
    const token0 = this.getTokenByAddress(position.token0);
    const token1 = this.getTokenByAddress(position.token1);
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

  async addPosition(
    wallet: Wallet,
    tokenIn: Token,
    tokenOut: Token,
    amount0: string,
    amount1: string,
    fee: uniV3.FeeAmount,
    lowerPrice: number,
    upperPrice: number,
    tokenId: number = 0,
    gasLimit: number,
    gasPrice: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction> {
    const { calldata, value } = await this.addPositionHelper(
      wallet,
      tokenIn,
      tokenOut,
      amount0,
      amount1,
      fee,
      lowerPrice,
      upperPrice,
      tokenId
    );
    const nftContract = this.getContract('nft', wallet);
    const tx = await nftContract.multicall(
      [calldata],
      this.generateOverrides(
        gasLimit,
        gasPrice,
        nonce,
        maxFeePerGas,
        maxPriorityFeePerGas,
        value
      )
    );
    logger.info(`Uniswap V3 Add position Tx Hash: ${tx.hash}`);
    return tx;
  }

  async reducePosition(
    wallet: Wallet,
    tokenId: number,
    decreasePercent: number = 100,
    getFee: boolean = false,
    gasLimit: number,
    gasPrice: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<BigNumber | Transaction> {
    // Reduce position and burn
    const contract = this.getContract('nft', wallet);
    const { calldata, value } = await this.reducePositionHelper(
      wallet,
      tokenId,
      decreasePercent
    );
    if (getFee) {
      return await contract.estimateGas.multicall([calldata], {
        value: value,
      });
    } else {
      const tx = await contract.multicall(
        [calldata],
        this.generateOverrides(
          gasLimit,
          gasPrice,
          nonce,
          maxFeePerGas,
          maxPriorityFeePerGas,
          value
        )
      );
      logger.info(`Uniswap V3 Remove position Tx Hash: ${tx.hash}`);
      return tx;
    }
  }

  async collectFees(
    wallet: Wallet,
    tokenId: number,
    isStatic: boolean = false,
    gasLimit: number = this.gasLimit,
    gasPrice: number = 0,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction | { amount0: BigNumber; amount1: BigNumber }> {
    const contract = this.getContract('nft', wallet);
    const collectData = {
      tokenId: tokenId,
      recipient: wallet.address,
      amount0Max: MaxUint128,
      amount1Max: MaxUint128,
    };
    return isStatic
      ? await contract.callStatic.collect(collectData)
      : await contract.collect(
          collectData,
          this.generateOverrides(
            gasLimit,
            gasPrice,
            nonce,
            maxFeePerGas,
            maxPriorityFeePerGas
          )
        );
  }

  generateOverrides(
    gasLimit: number,
    gasPrice: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber,
    value?: string
  ): Overrides {
    const overrides: Overrides = { gasLimit: gasLimit.toFixed(0) };
    if (maxFeePerGas && maxPriorityFeePerGas) {
      overrides.maxFeePerGas = maxFeePerGas;
      overrides.maxPriorityFeePerGas = maxPriorityFeePerGas;
    } else {
      overrides.gasPrice = (gasPrice * 1e9).toFixed(0);
    }
    if (nonce) overrides.nonce = nonce;
    if (value) overrides.value = value;
    return overrides;
  }
}
