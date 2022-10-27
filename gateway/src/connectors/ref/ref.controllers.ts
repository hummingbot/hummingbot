import Decimal from 'decimal.js-light';
import {
  HttpException,
  TOKEN_NOT_SUPPORTED_ERROR_CODE,
  TOKEN_NOT_SUPPORTED_ERROR_MESSAGE,
  PRICE_FAILED_ERROR_CODE,
  PRICE_FAILED_ERROR_MESSAGE,
  TRADE_FAILED_ERROR_CODE,
  TRADE_FAILED_ERROR_MESSAGE,
  SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE,
  SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE,
  SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE,
  SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE,
  UNKNOWN_ERROR_ERROR_CODE,
  UNKNOWN_ERROR_MESSAGE,
} from '../../services/error-handler';
import { TokenInfo } from '../../services/ethereum-base';
import { latency } from '../../services/base';
import { Nearish, RefAMMish } from '../../services/common-interfaces';
import { logger } from '../../services/logger';
import {
  EstimateGasResponse,
  PriceRequest,
  PriceResponse,
  TradeRequest,
  TradeResponse,
} from '../../amm/amm.requests';
import { EstimateSwapView, TokenMetadata } from 'coinalpha-ref-sdk';
import { Account } from 'near-api-js';
import { ExpectedTrade } from './ref';

export interface TradeInfo {
  baseToken: TokenMetadata;
  quoteToken: TokenMetadata;
  requestAmount: string;
  expectedTrade: EstimateSwapView[];
}

export async function getTradeInfo(
  nearish: Nearish,
  refAMMish: RefAMMish,
  baseAsset: string,
  quoteAsset: string,
  amount: string,
  tradeSide: string,
  allowedSlippage?: string
): Promise<TradeInfo> {
  const baseToken: TokenMetadata = getFullTokenFromSymbol(
    nearish,
    refAMMish,
    baseAsset
  );
  const quoteToken: TokenMetadata = getFullTokenFromSymbol(
    nearish,
    refAMMish,
    quoteAsset
  );

  let expectedTrade: ExpectedTrade;
  if (tradeSide === 'BUY') {
    expectedTrade = await refAMMish.estimateBuyTrade(
      quoteToken,
      baseToken,
      amount,
      allowedSlippage
    );
  } else {
    expectedTrade = await refAMMish.estimateSellTrade(
      baseToken,
      quoteToken,
      amount,
      allowedSlippage
    );
  }

  return {
    baseToken,
    quoteToken,
    requestAmount: amount,
    expectedTrade: expectedTrade.trade,
  };
}

export async function price(
  nearish: Nearish,
  refAMMish: RefAMMish,
  req: PriceRequest
): Promise<PriceResponse> {
  const startTimestamp: number = Date.now();
  let tradeInfo: TradeInfo;
  try {
    tradeInfo = await getTradeInfo(
      nearish,
      refAMMish,
      req.base,
      req.quote,
      req.amount,
      req.side,
      req.allowedSlippage
    );
  } catch (e) {
    if (e instanceof Error) {
      throw new HttpException(
        500,
        PRICE_FAILED_ERROR_MESSAGE + e.message,
        PRICE_FAILED_ERROR_CODE
      );
    } else {
      throw new HttpException(
        500,
        UNKNOWN_ERROR_MESSAGE,
        UNKNOWN_ERROR_ERROR_CODE
      );
    }
  }

  const { estimatedPrice, expectedAmount } = refAMMish.parseTrade(
    tradeInfo.expectedTrade,
    req.side
  );

  const gasLimitTransaction = nearish.gasLimitTransaction;
  const gasPrice = nearish.gasPrice;
  const gasLimitEstimate = refAMMish.gasLimitEstimate;
  return {
    network: nearish.chain,
    timestamp: startTimestamp,
    latency: latency(startTimestamp, Date.now()),
    base: tradeInfo.baseToken.id,
    quote: tradeInfo.quoteToken.id,
    amount: new Decimal(req.amount).toFixed(tradeInfo.baseToken.decimals),
    rawAmount: tradeInfo.requestAmount.toString(),
    expectedAmount: expectedAmount,
    price: estimatedPrice,
    gasPrice: gasPrice,
    gasPriceToken: nearish.nativeTokenSymbol,
    gasLimit: gasLimitTransaction,
    gasCost: String((gasPrice * gasLimitEstimate) / 1e24),
  };
}

export async function trade(
  nearish: Nearish,
  refAMMish: RefAMMish,
  req: TradeRequest
): Promise<TradeResponse> {
  const startTimestamp: number = Date.now();

  const limitPrice = req.limitPrice;
  const account: Account = await nearish.getWallet(req.address);

  let tradeInfo: TradeInfo;
  try {
    tradeInfo = await getTradeInfo(
      nearish,
      refAMMish,
      req.base,
      req.quote,
      req.amount,
      req.side
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

  const gasPrice: number = nearish.gasPrice;
  const gasLimitTransaction: number = nearish.gasLimitTransaction;
  const gasLimitEstimate: number = refAMMish.gasLimitEstimate;
  const { estimatedPrice, expectedAmount } = refAMMish.parseTrade(
    tradeInfo.expectedTrade,
    req.side
  );

  logger.info(
    `Expected execution price is ${estimatedPrice}, ` +
      `limit price is ${limitPrice}.`
  );

  if (req.side === 'BUY') {
    if (limitPrice && new Decimal(estimatedPrice).gt(new Decimal(limitPrice))) {
      logger.error('Swap price exceeded limit price.');
      throw new HttpException(
        500,
        SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_MESSAGE(
          estimatedPrice,
          limitPrice
        ),
        SWAP_PRICE_EXCEEDS_LIMIT_PRICE_ERROR_CODE
      );
    }

    const amountIn = new Decimal(req.amount)
      .mul(new Decimal(estimatedPrice))
      .toString();

    const tx = await refAMMish.executeTrade(
      account,
      tradeInfo.expectedTrade,
      amountIn,
      tradeInfo.quoteToken,
      tradeInfo.baseToken,
      req.allowedSlippage
    );

    logger.info(`Buy Ref swap has been executed.`);

    return {
      network: nearish.chain,
      timestamp: startTimestamp,
      latency: latency(startTimestamp, Date.now()),
      base: tradeInfo.baseToken.id,
      quote: tradeInfo.quoteToken.id,
      amount: new Decimal(req.amount).toFixed(tradeInfo.baseToken.decimals),
      rawAmount: tradeInfo.requestAmount.toString(),
      expectedIn: expectedAmount,
      price: estimatedPrice,
      gasPrice: gasPrice,
      gasPriceToken: nearish.nativeTokenSymbol,
      gasLimit: gasLimitTransaction,
      gasCost: String((gasPrice * gasLimitEstimate) / 1e24),
      txHash: tx,
    };
  } else {
    if (limitPrice && new Decimal(estimatedPrice).lt(new Decimal(limitPrice))) {
      logger.error('Swap price lower than limit price.');
      throw new HttpException(
        500,
        SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_MESSAGE(
          estimatedPrice,
          limitPrice
        ),
        SWAP_PRICE_LOWER_THAN_LIMIT_PRICE_ERROR_CODE
      );
    }

    const tx = await refAMMish.executeTrade(
      account,
      tradeInfo.expectedTrade,
      req.amount,
      tradeInfo.baseToken,
      tradeInfo.quoteToken,
      req.allowedSlippage
    );

    logger.info(`Sell Ref swap has been executed.`);

    return {
      network: nearish.chain,
      timestamp: startTimestamp,
      latency: latency(startTimestamp, Date.now()),
      base: tradeInfo.baseToken.id,
      quote: tradeInfo.quoteToken.id,
      amount: new Decimal(req.amount).toFixed(tradeInfo.baseToken.decimals),
      rawAmount: tradeInfo.requestAmount.toString(),
      expectedOut: expectedAmount,
      price: estimatedPrice,
      gasPrice: gasPrice,
      gasPriceToken: nearish.nativeTokenSymbol,
      gasLimit: gasLimitTransaction,
      gasCost: String((gasPrice * gasLimitEstimate) / 1e24),
      txHash: tx,
    };
  }
}

export function getFullTokenFromSymbol(
  nearish: Nearish,
  refAMMish: RefAMMish,
  tokenSymbol: string
): TokenMetadata {
  const tokenInfo: TokenInfo | undefined =
    nearish.getTokenBySymbol(tokenSymbol);
  let fullToken: TokenMetadata | undefined;
  if (tokenInfo) {
    fullToken = refAMMish.getTokenByAddress(tokenInfo.address);
  }
  if (!fullToken)
    throw new HttpException(
      500,
      TOKEN_NOT_SUPPORTED_ERROR_MESSAGE + tokenSymbol,
      TOKEN_NOT_SUPPORTED_ERROR_CODE
    );
  return fullToken;
}

export async function estimateGas(
  nearish: Nearish,
  refAMMish: RefAMMish
): Promise<EstimateGasResponse> {
  const gasPrice: number = nearish.gasPrice;
  const gasLimitTransaction: number = nearish.gasLimitTransaction;
  const gasLimitEstimate: number = refAMMish.gasLimitEstimate;
  return {
    network: nearish.chain,
    timestamp: Date.now(),
    gasPrice,
    gasPriceToken: nearish.nativeTokenSymbol,
    gasLimit: gasLimitTransaction,
    gasCost: String((gasPrice * gasLimitEstimate) / 1e24),
  };
}
